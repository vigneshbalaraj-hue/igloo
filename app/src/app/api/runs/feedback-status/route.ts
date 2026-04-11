// GET /api/runs/feedback-status
// Returns run IDs that have feedback for the authenticated user.
// Used by the profile page to show "Feedback given" badges.

import { NextResponse } from "next/server";
import { auth } from "@clerk/nextjs/server";
import { getServerSupabase } from "@/lib/supabase-server";

export const runtime = "nodejs";

export async function GET() {
  const { userId } = await auth();
  if (!userId) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const supabase = getServerSupabase();

  const { data: user } = await supabase
    .from("users")
    .select("id")
    .eq("clerk_user_id", userId)
    .maybeSingle();

  if (!user) {
    return NextResponse.json({ runIds: [] });
  }

  const { data, error } = await supabase
    .from("run_feedback")
    .select("run_id")
    .eq("user_id", user.id);

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({
    runIds: (data ?? []).map((r: { run_id: string }) => r.run_id),
  });
}
