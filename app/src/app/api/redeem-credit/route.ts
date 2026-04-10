// POST /api/redeem-credit
// Redeems 1 saved credit to create a new run (skips Razorpay).
// Uses the Postgres redeem_credit() function for atomic balance check.
// Auth: Clerk session required.

import { NextRequest, NextResponse } from "next/server";
import { auth, currentUser } from "@clerk/nextjs/server";
import { getServerSupabase, getOrCreateUser } from "@/lib/supabase-server";
import { mintStudioToken } from "@/lib/studio-token";

export const runtime = "nodejs";

const IGLOO_STUDIO_URL = process.env.IGLOO_STUDIO_URL!;
const STUDIO_TOKEN_TTL_MS = 24 * 60 * 60 * 1000; // 24h

export async function POST(req: NextRequest) {
  const { userId: clerkUserId } = await auth();
  if (!clerkUserId) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const user = await currentUser();
  const email = user?.primaryEmailAddress?.emailAddress;
  if (!email) {
    return NextResponse.json({ error: "no_email" }, { status: 400 });
  }

  let body: { topic?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid_json" }, { status: 400 });
  }

  const topic = (body.topic ?? "").trim();
  if (!topic) {
    return NextResponse.json({ error: "topic_required" }, { status: 400 });
  }

  const supabase = getServerSupabase();

  // Ensure user exists in DB
  let dbUser;
  try {
    dbUser = await getOrCreateUser(clerkUserId, email);
  } catch (e) {
    console.error("[redeem-credit] getOrCreateUser failed", e);
    return NextResponse.json({ error: "user_create_failed" }, { status: 500 });
  }

  // Call the atomic Postgres function
  const { data, error } = await supabase.rpc("redeem_credit", {
    p_user_id: dbUser.id,
    p_topic: topic,
  });

  if (error) {
    if (error.message?.includes("insufficient_credits")) {
      return NextResponse.json({ error: "insufficient_credits" }, { status: 402 });
    }
    console.error("[redeem-credit] rpc failed", error);
    return NextResponse.json({ error: "redeem_failed" }, { status: 500 });
  }

  const runId = data as string;

  // Mint studio token
  const token = mintStudioToken({
    run_id: runId,
    user_id: dbUser.id,
    exp: Date.now() + STUDIO_TOKEN_TTL_MS,
  });
  const studioUrl = `${IGLOO_STUDIO_URL}/?token=${encodeURIComponent(token)}`;

  return NextResponse.json({
    run_id: runId,
    studio_url: studioUrl,
  });
}
