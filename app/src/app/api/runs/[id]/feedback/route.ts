// GET  /api/runs/:id/feedback — fetch existing feedback for a run
// POST /api/runs/:id/feedback — submit feedback (rating + optional comment)
// Auth: Clerk session required. User must own the run.

import { NextResponse } from "next/server";
import { auth } from "@clerk/nextjs/server";
import { getServerSupabase } from "@/lib/supabase-server";

export const runtime = "nodejs";

async function getUser(clerkUserId: string) {
  const supabase = getServerSupabase();
  const { data } = await supabase
    .from("users")
    .select("id")
    .eq("clerk_user_id", clerkUserId)
    .maybeSingle();
  return data;
}

async function verifyRunOwnership(runId: string, userId: string) {
  const supabase = getServerSupabase();
  const { data } = await supabase
    .from("runs")
    .select("id, status, user_id")
    .eq("id", runId)
    .maybeSingle();
  if (!data) return null;
  if (data.user_id !== userId) return null;
  return data;
}

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { userId: clerkUserId } = await auth();
  if (!clerkUserId) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const user = await getUser(clerkUserId);
  if (!user) {
    return NextResponse.json({ feedback: null });
  }

  const { id } = await params;
  const run = await verifyRunOwnership(id, user.id);
  if (!run) {
    return NextResponse.json({ error: "not_found" }, { status: 404 });
  }

  const supabase = getServerSupabase();
  const { data, error } = await supabase
    .from("run_feedback")
    .select("rating, comment, created_at")
    .eq("run_id", id)
    .maybeSingle();

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({ feedback: data });
}

export async function POST(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { userId: clerkUserId } = await auth();
  if (!clerkUserId) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const user = await getUser(clerkUserId);
  if (!user) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const { id } = await params;
  const run = await verifyRunOwnership(id, user.id);
  if (!run) {
    return NextResponse.json({ error: "not_found" }, { status: 404 });
  }
  if (run.status !== "delivered") {
    return NextResponse.json(
      { error: "feedback_only_for_delivered" },
      { status: 400 }
    );
  }

  let body: { rating?: unknown; comment?: unknown };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid_json" }, { status: 400 });
  }

  const rating = Number(body.rating);
  if (!Number.isInteger(rating) || rating < 1 || rating > 5) {
    return NextResponse.json({ error: "rating_must_be_1_to_5" }, { status: 400 });
  }

  const comment =
    typeof body.comment === "string" ? body.comment.slice(0, 2000).trim() : null;

  const supabase = getServerSupabase();
  const { error } = await supabase.from("run_feedback").insert({
    run_id: id,
    user_id: user.id,
    rating,
    comment: comment || null,
  });

  if (error) {
    // Unique constraint violation — already submitted
    if (error.code === "23505") {
      return NextResponse.json({ error: "already_submitted" }, { status: 409 });
    }
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({ ok: true });
}
