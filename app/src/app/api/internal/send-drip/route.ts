// POST /api/internal/send-drip
// Hourly sweep called by pg_cron. Finds users due for each delayed
// drip email and dispatches via Resend.
//
// Auth: shared-secret header (X-Internal-Secret == INTERNAL_DRIP_SECRET).
// Idempotency: sendDripEmail handles per-(user, type) idempotency, so
// double-firings of the cron job are safe.
//
// Eligibility rules per email type (see plan):
//   winback_d3   = winback_d0 sent ≥ 3 days ago, no captured payment since
//   winback_d7   = winback_d0 sent ≥ 7 days ago, no captured payment since
//   onboard_t1   = welcome_t0 sent ≥ 1 day ago, no runs yet
//   onboard_t3   = welcome_t0 sent ≥ 3 days ago, no captured payment
//   onboard_t7   = welcome_t0 sent ≥ 7 days ago, no captured payment
//
// Failed sends from prior sweeps are picked up by the same query (the
// sendDripEmail wrapper re-uses the existing 'failed' row if present).

import { NextRequest, NextResponse } from "next/server";
import { getServerSupabase } from "@/lib/supabase-server";
import { sendDripEmail } from "@/lib/email";
import type { EmailType } from "@/lib/emails/templates";

export const runtime = "nodejs";

const INTERNAL_SECRET = process.env.INTERNAL_DRIP_SECRET ?? "";

type DueRule = {
  type: EmailType;
  /** which earlier email's sent_at we measure delay from */
  sourceType: EmailType;
  /** delay in days from sourceType.sent_at to "due" */
  delayDays: number;
  /** Skip if user has any captured payment */
  skipIfPaid?: boolean;
  /** Skip if user has any runs row (paid OR draft) */
  skipIfHasRun?: boolean;
};

const RULES: DueRule[] = [
  { type: "winback_d3", sourceType: "winback_d0", delayDays: 3, skipIfPaid: true },
  { type: "winback_d7", sourceType: "winback_d0", delayDays: 7, skipIfPaid: true },
  { type: "onboard_t1", sourceType: "welcome_t0", delayDays: 1, skipIfHasRun: true },
  { type: "onboard_t3", sourceType: "welcome_t0", delayDays: 3, skipIfPaid: true },
  { type: "onboard_t7", sourceType: "welcome_t0", delayDays: 7, skipIfPaid: true },
];

type SweepReport = {
  ok: true;
  ranAt: string;
  perRule: Array<{
    type: EmailType | "retry_stuck";
    candidates: number;
    sent: number;
    skipped: number;
    failed: number;
  }>;
  totalSent: number;
  totalFailed: number;
};

export async function POST(req: NextRequest): Promise<NextResponse> {
  const provided = req.headers.get("x-internal-secret") ?? "";
  if (!INTERNAL_SECRET || provided !== INTERNAL_SECRET) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const supabase = getServerSupabase();
  const report: SweepReport = {
    ok: true,
    ranAt: new Date().toISOString(),
    perRule: [],
    totalSent: 0,
    totalFailed: 0,
  };

  // Pass 0: retry every pending or failed sent_emails row.
  //   Picks up:
  //     - rows enqueued by the backfill (winback_d0 for the existing 60)
  //     - rows that failed in a prior sweep (transient Resend errors)
  //   Bounded to 200 per sweep to keep latency manageable.
  {
    const { data: stuckRows, error: stuckErr } = await supabase
      .from("sent_emails")
      .select("user_id, email_type")
      .in("status", ["pending", "failed"])
      .order("created_at", { ascending: true })
      .limit(200);

    if (stuckErr) {
      console.error("[drip] retry-stuck query failed", stuckErr);
    } else {
      let retrySent = 0;
      let retrySkipped = 0;
      let retryFailed = 0;
      for (const row of stuckRows ?? []) {
        try {
          const result = await sendDripEmail({
            userId: row.user_id,
            emailType: row.email_type as EmailType,
          });
          if (result.ok && result.status === "sent") retrySent++;
          else if (result.ok && result.status === "skipped") retrySkipped++;
          else retryFailed++;
        } catch (e) {
          console.error("[drip] retry threw", { row, e });
          retryFailed++;
        }
      }
      report.totalSent += retrySent;
      report.totalFailed += retryFailed;
      report.perRule.push({
        type: "retry_stuck",
        candidates: stuckRows?.length ?? 0,
        sent: retrySent,
        skipped: retrySkipped,
        failed: retryFailed,
      });
    }
  }

  for (const rule of RULES) {
    const cutoff = new Date(Date.now() - rule.delayDays * 24 * 60 * 60 * 1000).toISOString();

    // Step 1: source-type rows older than the cutoff.
    const { data: candidates, error: candidatesErr } = await supabase
      .from("sent_emails")
      .select("user_id")
      .eq("email_type", rule.sourceType)
      .eq("status", "sent")
      .lte("sent_at", cutoff)
      .limit(500);

    if (candidatesErr) {
      console.error(`[drip] candidates query failed for ${rule.type}`, candidatesErr);
      report.perRule.push({
        type: rule.type,
        candidates: 0,
        sent: 0,
        skipped: 0,
        failed: 1,
      });
      report.totalFailed += 1;
      continue;
    }

    const candidateUserIds = Array.from(new Set((candidates ?? []).map((r) => r.user_id)));

    if (candidateUserIds.length === 0) {
      report.perRule.push({ type: rule.type, candidates: 0, sent: 0, skipped: 0, failed: 0 });
      continue;
    }

    // Step 2: filter out users who already have a target-type row in
    // 'sent' or 'skipped' status (failed/pending = retry).
    const { data: existing, error: existingErr } = await supabase
      .from("sent_emails")
      .select("user_id, status")
      .eq("email_type", rule.type)
      .in("user_id", candidateUserIds);

    if (existingErr) {
      console.error(`[drip] existing query failed for ${rule.type}`, existingErr);
      continue;
    }

    const skipUserIds = new Set(
      (existing ?? [])
        .filter((r) => r.status === "sent" || r.status === "skipped")
        .map((r) => r.user_id)
    );
    let eligible = candidateUserIds.filter((id) => !skipUserIds.has(id));

    // Step 3: gate by payment status (if rule requires).
    if (rule.skipIfPaid && eligible.length > 0) {
      const { data: paidRows, error: paidErr } = await supabase
        .from("payments")
        .select("user_id")
        .eq("status", "captured")
        .in("user_id", eligible);
      if (paidErr) {
        console.error(`[drip] payments gate failed for ${rule.type}`, paidErr);
        continue;
      }
      const paidSet = new Set((paidRows ?? []).map((r) => r.user_id));
      eligible = eligible.filter((id) => !paidSet.has(id));
    }

    // Step 4: gate by has-run (skip if user has any runs row at all).
    if (rule.skipIfHasRun && eligible.length > 0) {
      const { data: runRows, error: runErr } = await supabase
        .from("runs")
        .select("user_id")
        .in("user_id", eligible);
      if (runErr) {
        console.error(`[drip] runs gate failed for ${rule.type}`, runErr);
        continue;
      }
      const runSet = new Set((runRows ?? []).map((r) => r.user_id));
      eligible = eligible.filter((id) => !runSet.has(id));
    }

    let sent = 0;
    let skipped = 0;
    let failed = 0;

    for (const userId of eligible) {
      try {
        const result = await sendDripEmail({ userId, emailType: rule.type });
        if (result.ok && result.status === "sent") sent++;
        else if (result.ok && result.status === "skipped") skipped++;
        else failed++;
      } catch (e) {
        console.error(`[drip] send threw for ${rule.type} ${userId}`, e);
        failed++;
      }
    }

    report.perRule.push({
      type: rule.type,
      candidates: candidateUserIds.length,
      sent,
      skipped,
      failed,
    });
    report.totalSent += sent;
    report.totalFailed += failed;
  }

  return NextResponse.json(report);
}
