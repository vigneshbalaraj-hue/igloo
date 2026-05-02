// POST /api/clerk-webhook
// Receives Clerk events (we care about user.created). Signed by svix.
//
// Auth: NOT a Clerk session. Public route (already declared in proxy.ts).
// Idempotency: getOrCreateUser + sendDripEmail are both idempotent, so
// Clerk's at-least-once retries are safe.
//
// On user.created we eagerly create the public.users row (replaces the
// lazy-on-first-request pattern in supabase-server.ts:getOrCreateUser
// — that path remains as a fallback for race + pre-webhook signups)
// and fire the T+0 welcome email.

import { NextRequest, NextResponse } from "next/server";
import crypto from "node:crypto";
import { getServerSupabase, getOrCreateUser } from "@/lib/supabase-server";
import { sendDripEmail } from "@/lib/email";

export const runtime = "nodejs";

const WEBHOOK_SECRET = process.env.CLERK_WEBHOOK_SECRET ?? "";

/**
 * Verify a Clerk/svix webhook signature.
 *
 * Headers contract (per svix docs):
 *   svix-id:        unique message id
 *   svix-timestamp: unix seconds
 *   svix-signature: space-separated list of "<version>,<base64sig>" pairs
 *
 * Secret format: whsec_<base64-encoded-32-byte-key>.
 */
function verifySvixSignature(args: {
  svixId: string;
  svixTimestamp: string;
  svixSignature: string;
  rawBody: string;
}): boolean {
  if (!WEBHOOK_SECRET) {
    console.error("[clerk-webhook] CLERK_WEBHOOK_SECRET not set");
    return false;
  }
  if (!WEBHOOK_SECRET.startsWith("whsec_")) {
    console.error("[clerk-webhook] CLERK_WEBHOOK_SECRET should start with whsec_");
    return false;
  }
  if (!args.svixId || !args.svixTimestamp || !args.svixSignature) return false;

  // Replay protection: reject timestamps outside ±5 min window.
  const ts = parseInt(args.svixTimestamp, 10);
  if (!Number.isFinite(ts)) return false;
  const drift = Math.abs(Math.floor(Date.now() / 1000) - ts);
  if (drift > 5 * 60) {
    console.warn("[clerk-webhook] timestamp outside tolerance window", { drift });
    return false;
  }

  const keyBytes = Buffer.from(WEBHOOK_SECRET.slice(6), "base64");
  const signedContent = `${args.svixId}.${args.svixTimestamp}.${args.rawBody}`;
  const expected = crypto.createHmac("sha256", keyBytes).update(signedContent).digest("base64");

  // svix-signature can carry multiple versions: "v1,abc v1,xyz v2,foo"
  const parts = args.svixSignature.split(" ");
  for (const part of parts) {
    const [, sig] = part.split(",");
    if (!sig) continue;
    if (sig.length === expected.length) {
      const a = Buffer.from(expected);
      const b = Buffer.from(sig);
      try {
        if (crypto.timingSafeEqual(a, b)) return true;
      } catch {
        // length mismatch — keep trying
      }
    }
  }
  return false;
}

type ClerkEmailAddress = {
  id: string;
  email_address: string;
};

type ClerkUserCreatedData = {
  id: string;
  email_addresses?: ClerkEmailAddress[];
  primary_email_address_id?: string | null;
  first_name?: string | null;
};

type ClerkWebhookEvent = {
  type: string;
  data?: ClerkUserCreatedData;
};

export async function POST(req: NextRequest) {
  const rawBody = await req.text();
  const svixId = req.headers.get("svix-id") ?? "";
  const svixTimestamp = req.headers.get("svix-timestamp") ?? "";
  const svixSignature = req.headers.get("svix-signature") ?? "";

  if (!verifySvixSignature({ svixId, svixTimestamp, svixSignature, rawBody })) {
    console.warn("[clerk-webhook] invalid signature");
    return NextResponse.json({ error: "invalid_signature" }, { status: 400 });
  }

  let event: ClerkWebhookEvent;
  try {
    event = JSON.parse(rawBody) as ClerkWebhookEvent;
  } catch {
    return NextResponse.json({ error: "invalid_json" }, { status: 400 });
  }

  if (event.type !== "user.created") {
    // user.updated, user.deleted, session.*, etc — 200 and ignore for now.
    return NextResponse.json({ ok: true, ignored: event.type });
  }

  const data = event.data;
  if (!data?.id) {
    return NextResponse.json({ ok: true, ignored: "no_user_id" });
  }

  const primary = data.email_addresses?.find((e) => e.id === data.primary_email_address_id);
  const email = primary?.email_address;
  if (!email) {
    console.warn("[clerk-webhook] user.created missing primary email", { clerkUserId: data.id });
    return NextResponse.json({ ok: true, ignored: "no_primary_email" });
  }

  // Eagerly create the public.users row.
  let dbUser;
  try {
    dbUser = await getOrCreateUser(data.id, email);
  } catch (e) {
    console.error("[clerk-webhook] getOrCreateUser failed", e);
    // 502 so Clerk retries — transient Supabase failures are recoverable.
    return NextResponse.json({ error: "user_create_failed" }, { status: 502 });
  }

  // If we have a first_name from Clerk, persist it for future drip personalization.
  if (data.first_name && data.first_name.trim().length > 0) {
    const supabase = getServerSupabase();
    const { error: updateErr } = await supabase
      .from("users")
      .update({ first_name: data.first_name.trim() })
      .eq("id", dbUser.id);
    if (updateErr) {
      // Non-fatal — drip will fall back to email-derived first name.
      console.warn("[clerk-webhook] first_name update failed", updateErr);
    }
  }

  // Fire welcome_t0 immediately. Idempotent on (user_id, email_type).
  // We don't await failures — log them and 200 to Clerk so it doesn't
  // retry the whole webhook (which would re-create the user, harmless,
  // but noisy). The hourly drip sweep retries failed sends anyway.
  try {
    const result = await sendDripEmail({
      userId: dbUser.id,
      emailType: "welcome_t0",
      firstNameOverride: data.first_name ?? null,
    });
    if (!result.ok) {
      console.warn("[clerk-webhook] welcome_t0 send failed", result);
    }
  } catch (e) {
    console.error("[clerk-webhook] welcome_t0 threw", e);
  }

  return NextResponse.json({ ok: true, user_id: dbUser.id });
}
