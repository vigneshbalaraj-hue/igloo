// GET /api/credits/history
// Returns the authenticated user's credit transaction log ordered by newest first.
// Auth: Clerk session required.

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
    return NextResponse.json({ history: [] });
  }

  const { data: history, error } = await supabase
    .from("credits")
    .select("id, delta, reason, note, created_at")
    .eq("user_id", user.id)
    .order("created_at", { ascending: false });

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({ history: history ?? [] });
}
