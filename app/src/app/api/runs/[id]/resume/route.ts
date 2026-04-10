// POST /api/runs/:id/resume
// Mints a fresh studio HMAC token for a draft run and returns the
// studio URL. Used by the /runs/[id] page "Return to studio" button
// when a user closed the wizard tab mid-flow.
//
// Auth: Clerk session required AND the run must belong to the user
// AND status must be 'draft'. Re-entering a running/awaiting_review
// run via the studio would corrupt per-user state.

import { NextResponse } from "next/server";
import { auth } from "@clerk/nextjs/server";
import { getServerSupabase } from "@/lib/supabase-server";
import { mintStudioToken } from "@/lib/studio-token";

export const runtime = "nodejs";

const IGLOO_STUDIO_URL = process.env.IGLOO_STUDIO_URL!;
const STUDIO_TOKEN_TTL_MS = 24 * 60 * 60 * 1000;

export async function POST(
  _req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { userId } = await auth();
  if (!userId) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const { id } = await params;
  const supabase = getServerSupabase();

  const { data: run, error } = await supabase
    .from("runs")
    .select("id, status, user_id, users!inner(clerk_user_id)")
    .eq("id", id)
    .maybeSingle();

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
  if (!run) {
    return NextResponse.json({ error: "not_found" }, { status: 404 });
  }

  const owner = (run as unknown as {
    users: { clerk_user_id: string } | { clerk_user_id: string }[];
  }).users;
  const ownerClerkId = Array.isArray(owner) ? owner[0]?.clerk_user_id : owner?.clerk_user_id;
  if (ownerClerkId !== userId) {
    return NextResponse.json({ error: "forbidden" }, { status: 403 });
  }

  if (run.status !== "draft") {
    return NextResponse.json(
      { error: "not_resumable", status: run.status },
      { status: 400 }
    );
  }

  const token = mintStudioToken({
    run_id: run.id,
    user_id: run.user_id,
    exp: Date.now() + STUDIO_TOKEN_TTL_MS,
  });
  const studio_url = `${IGLOO_STUDIO_URL}/?token=${encodeURIComponent(token)}`;

  return NextResponse.json({ studio_url });
}
