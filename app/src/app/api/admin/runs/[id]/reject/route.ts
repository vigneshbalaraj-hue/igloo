// POST /api/admin/runs/:id/reject
// Marks a run as rejected and inserts a +1 credit refund row tied
// to the rejected run, restoring the user's spendable balance.

import { NextResponse } from "next/server";
import { requireAdmin, AdminAuthError } from "@/lib/admin";
import { getServerSupabase } from "@/lib/supabase-server";

export const runtime = "nodejs";

export async function POST(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    await requireAdmin();
  } catch (e) {
    if (e instanceof AdminAuthError) {
      return NextResponse.json({ error: e.message }, { status: e.status });
    }
    throw e;
  }

  const { id } = await params;

  let body: { reason?: string } = {};
  try {
    body = await req.json();
  } catch {
    /* optional body */
  }
  const reason = (body.reason ?? "no_reason").slice(0, 500);

  const supabase = getServerSupabase();

  const { data: run, error: fetchErr } = await supabase
    .from("runs")
    .select("id, status, user_id")
    .eq("id", id)
    .maybeSingle();
  if (fetchErr) {
    return NextResponse.json({ error: fetchErr.message }, { status: 500 });
  }
  if (!run) {
    return NextResponse.json({ error: "not_found" }, { status: 404 });
  }
  if (run.status !== "awaiting_review") {
    return NextResponse.json(
      { error: `cannot_reject_from_${run.status}` },
      { status: 400 }
    );
  }

  // Idempotency: check if a refund credit row for this run already exists.
  const { data: existingRefund } = await supabase
    .from("credits")
    .select("id")
    .eq("run_id", run.id)
    .eq("reason", "refund")
    .maybeSingle();

  if (!existingRefund) {
    const { error: refundErr } = await supabase.from("credits").insert({
      user_id: run.user_id,
      delta: 1,
      reason: "refund",
      run_id: run.id,
      note: `admin reject: ${reason}`,
    });
    if (refundErr) {
      return NextResponse.json({ error: refundErr.message }, { status: 500 });
    }
  }

  const { error: updateErr } = await supabase
    .from("runs")
    .update({
      status: "rejected",
      rejection_reason: reason,
    })
    .eq("id", id);

  if (updateErr) {
    return NextResponse.json({ error: updateErr.message }, { status: 500 });
  }

  return NextResponse.json({ ok: true });
}
