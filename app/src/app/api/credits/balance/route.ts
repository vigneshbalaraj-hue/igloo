// GET /api/credits/balance
// Returns the authenticated user's credit balance.
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

  // Look up internal user ID
  const { data: user } = await supabase
    .from("users")
    .select("id")
    .eq("clerk_user_id", userId)
    .maybeSingle();

  if (!user) {
    // User hasn't made a payment yet — balance is 0
    return NextResponse.json({ balance: 0 });
  }

  const { data: row } = await supabase
    .from("user_balances")
    .select("balance")
    .eq("user_id", user.id)
    .maybeSingle();

  return NextResponse.json({ balance: row?.balance ?? 0 });
}
