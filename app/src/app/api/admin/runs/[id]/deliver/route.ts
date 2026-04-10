// POST /api/admin/runs/:id/deliver
// Marks a run as delivered. No credit movement (consumption row was
// already inserted at run creation time).

import { NextResponse } from "next/server";
import { requireAdmin, AdminAuthError } from "@/lib/admin";
import { getServerSupabase } from "@/lib/supabase-server";

export const runtime = "nodejs";

export async function POST(
  _req: Request,
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
  const supabase = getServerSupabase();

  const { data: run, error: fetchErr } = await supabase
    .from("runs")
    .select("id, status")
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
      { error: `cannot_deliver_from_${run.status}` },
      { status: 400 }
    );
  }

  const { error: updateErr } = await supabase
    .from("runs")
    .update({
      status: "delivered",
      delivered_at: new Date().toISOString(),
    })
    .eq("id", id);

  if (updateErr) {
    return NextResponse.json({ error: updateErr.message }, { status: 500 });
  }

  // TODO Phase 10: send customer delivery email via Resend with signed
  // download link. Intentionally deferred — see GOAL.md "Known deferred
  // capabilities" and .tmp/checkpoint_2026-04-08_session27.md.

  return NextResponse.json({ ok: true });
}
