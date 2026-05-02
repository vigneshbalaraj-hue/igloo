// POST /api/internal/notify-awaiting-review
// Triggered by Postgres `runs_notify_awaiting_review` trigger via pg_net
// when a row's status flips to 'awaiting_review'. Sends an email to
// every address in ADMIN_NOTIFICATION_EMAILS via Resend.
//
// Auth: shared secret (same INTERNAL_DRIP_SECRET as the drip sweep).
// Idempotency: checks runs.awaiting_review_notified_at; bails if set.
// On success, stamps awaiting_review_notified_at = now().

import { NextRequest, NextResponse } from "next/server";
import { getServerSupabase } from "@/lib/supabase-server";
import { renderAdminReview } from "@/lib/emails/admin_review";

export const runtime = "nodejs";

const INTERNAL_SECRET = process.env.INTERNAL_DRIP_SECRET ?? "";
const RESEND_API_KEY = process.env.RESEND_API_KEY ?? "";
const APP_URL = process.env.NEXT_PUBLIC_APP_URL ?? "https://igloo.video";
const FROM_ADDRESS = "Igloo <support@igloo.video>";

function getAdminRecipients(): string[] {
  const raw = process.env.ADMIN_NOTIFICATION_EMAILS ?? "";
  return raw
    .split(",")
    .map((s) => s.trim())
    .filter((s) => s.length > 0);
}

type RunRow = {
  id: string;
  user_id: string;
  prompt: string;
  status: string;
  duration_seconds: number | null;
  finished_at: string | null;
  awaiting_review_notified_at: string | null;
};

type UserRow = {
  email: string;
  first_name: string | null;
};

export async function POST(req: NextRequest): Promise<NextResponse> {
  const provided = req.headers.get("x-internal-secret") ?? "";
  if (!INTERNAL_SECRET || provided !== INTERNAL_SECRET) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  if (!RESEND_API_KEY) {
    console.error("[notify-awaiting-review] RESEND_API_KEY not set");
    return NextResponse.json({ error: "resend_key_missing" }, { status: 500 });
  }

  let body: { run_id?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid_json" }, { status: 400 });
  }
  const runId = body.run_id;
  if (!runId) {
    return NextResponse.json({ error: "run_id_required" }, { status: 400 });
  }

  const recipients = getAdminRecipients();
  if (recipients.length === 0) {
    console.warn("[notify-awaiting-review] ADMIN_NOTIFICATION_EMAILS is empty; nothing to send");
    return NextResponse.json({ ok: true, status: "skipped", reason: "no_recipients" });
  }

  const supabase = getServerSupabase();

  const { data: run, error: runErr } = await supabase
    .from("runs")
    .select("id, user_id, prompt, status, duration_seconds, finished_at, awaiting_review_notified_at")
    .eq("id", runId)
    .maybeSingle<RunRow>();

  if (runErr) {
    console.error("[notify-awaiting-review] run lookup failed", runErr);
    return NextResponse.json({ error: "run_lookup_failed" }, { status: 500 });
  }
  if (!run) {
    return NextResponse.json({ error: "run_not_found" }, { status: 404 });
  }

  // Idempotency: skip if already notified (defensive — trigger only
  // fires once per status transition, but pg_net retries can fire the
  // endpoint multiple times for the same request).
  if (run.awaiting_review_notified_at) {
    return NextResponse.json({ ok: true, status: "skipped", reason: "already_notified" });
  }

  // Sanity check the status — if the row has since moved past
  // awaiting_review (e.g., to delivered/rejected), still send the
  // notification. The state machine doesn't go back, so the admin
  // info is still useful.
  if (run.status !== "awaiting_review") {
    console.warn("[notify-awaiting-review] run no longer in awaiting_review", {
      runId,
      currentStatus: run.status,
    });
    // Continue anyway — admin still wants to know it happened.
  }

  const { data: user, error: userErr } = await supabase
    .from("users")
    .select("email, first_name")
    .eq("id", run.user_id)
    .maybeSingle<UserRow>();

  if (userErr) {
    console.error("[notify-awaiting-review] user lookup failed", userErr);
    return NextResponse.json({ error: "user_lookup_failed" }, { status: 500 });
  }

  const rendered = renderAdminReview({
    runId: run.id,
    topic: run.prompt,
    userEmail: user?.email ?? "(unknown)",
    userFirstName: user?.first_name ?? null,
    durationSeconds: run.duration_seconds,
    finishedAt: run.finished_at,
    appUrl: APP_URL,
  });

  let sendError: string | null = null;
  let resendMessageId: string | null = null;

  try {
    const res = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${RESEND_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        from: FROM_ADDRESS,
        to: recipients,
        subject: rendered.subject,
        html: rendered.html,
        text: rendered.text,
        tags: [
          { name: "kind", value: "admin_review" },
          { name: "run_id", value: run.id },
        ],
      }),
    });

    if (!res.ok) {
      const text = await res.text();
      sendError = `resend_${res.status}: ${text.slice(0, 500)}`;
    } else {
      const json = (await res.json()) as { id?: string };
      resendMessageId = json.id ?? null;
    }
  } catch (e) {
    sendError = e instanceof Error ? e.message : String(e);
  }

  if (sendError) {
    console.error("[notify-awaiting-review] resend send failed", { runId, sendError });
    return NextResponse.json({ ok: false, error: sendError }, { status: 502 });
  }

  // Stamp the column so we don't re-send.
  const { error: updateErr } = await supabase
    .from("runs")
    .update({ awaiting_review_notified_at: new Date().toISOString() })
    .eq("id", runId);

  if (updateErr) {
    // The email already went out — just log. Worst case duplicate
    // notification on a future trigger fire (unlikely).
    console.warn("[notify-awaiting-review] failed to stamp notified_at", updateErr);
  }

  return NextResponse.json({
    ok: true,
    status: "sent",
    recipients: recipients.length,
    resend_message_id: resendMessageId,
  });
}
