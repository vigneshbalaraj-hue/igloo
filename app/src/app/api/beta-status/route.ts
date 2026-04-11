// GET /api/beta-status
// Returns whether the current user is allowed to create reels.
// Existing customers (with at least 1 captured payment) are always allowed.
// New customers are allowed only if fewer than BETA_CAP distinct customers exist.
// Side effect: ensures a users row exists for the caller (so waitlisted
// users appear in the admin waitlist).

import { NextResponse } from "next/server";
import { auth, currentUser } from "@clerk/nextjs/server";
import { getServerSupabase, getOrCreateUser } from "@/lib/supabase-server";

export const runtime = "nodejs";

const BETA_CAP = 30;

export async function GET() {
  const { userId: clerkUserId } = await auth();
  if (!clerkUserId) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const supabase = getServerSupabase();

  // Ensure user row exists so waitlisted users show up in admin
  const clerkUser = await currentUser();
  const email = clerkUser?.primaryEmailAddress?.emailAddress ?? "";
  let dbUser: { id: string } | null = null;
  try {
    dbUser = await getOrCreateUser(clerkUserId, email);
  } catch {
    // If getOrCreateUser fails (e.g. no email), fall back to lookup
    const { data } = await supabase
      .from("users")
      .select("id")
      .eq("clerk_user_id", clerkUserId)
      .maybeSingle();
    dbUser = data;
  }

  // Check if this user is an existing paying customer
  if (dbUser) {
    const { count } = await supabase
      .from("payments")
      .select("id", { count: "exact", head: true })
      .eq("user_id", dbUser.id)
      .eq("status", "captured");

    if (count && count > 0) {
      return NextResponse.json({ allowed: true });
    }
  }

  // Count distinct paying customers
  const { data: payingUsers } = await supabase
    .from("payments")
    .select("user_id")
    .eq("status", "captured");

  const distinctCount = new Set((payingUsers ?? []).map((p: { user_id: string }) => p.user_id)).size;

  return NextResponse.json({ allowed: distinctCount < BETA_CAP });
}
