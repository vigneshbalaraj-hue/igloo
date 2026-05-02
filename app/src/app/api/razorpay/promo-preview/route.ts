// POST /api/razorpay/promo-preview
// Live validation for the "Apply" button on the create page.
// Returns the discounted amount + promo_id, OR a friendly error code.
// Does NOT create a Razorpay order or insert any payment row.
//
// Auth: Clerk session required.
// Side effects: getOrCreateUser may insert a public.users row if it's
// the user's first server-side call. That mirrors what /order does.

import { NextRequest, NextResponse } from "next/server";
import { auth, currentUser } from "@clerk/nextjs/server";
import { PRICING_TIERS } from "@/lib/pricing";
import type { PricingTier } from "@/lib/pricing";
import { getServerSupabase, getOrCreateUser } from "@/lib/supabase-server";

export const runtime = "nodejs";

const PROMO_ENABLED = process.env.PROMO_CODES_ENABLED === "true";

type ValidatePromoResult =
  | {
      ok: true;
      promo_id: string;
      code: string;
      discount_pct: number;
      original_amount_paise: number;
      discounted_amount_paise: number;
    }
  | { ok: false; error: string };

export async function POST(req: NextRequest) {
  if (!PROMO_ENABLED) {
    return NextResponse.json({ ok: false, error: "promo_disabled" }, { status: 503 });
  }

  const { userId } = await auth();
  if (!userId) {
    return NextResponse.json({ ok: false, error: "unauthorized" }, { status: 401 });
  }

  const user = await currentUser();
  const email = user?.primaryEmailAddress?.emailAddress;
  if (!email) {
    return NextResponse.json({ ok: false, error: "no_email" }, { status: 400 });
  }

  let body: { code?: string; tier?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ ok: false, error: "invalid_json" }, { status: 400 });
  }

  const code = (body.code ?? "").trim();
  if (!code) {
    return NextResponse.json({ ok: false, error: "invalid_code" }, { status: 400 });
  }

  const tier = (body.tier ?? "single") as PricingTier;
  if (!(tier in PRICING_TIERS)) {
    return NextResponse.json({ ok: false, error: "invalid_tier" }, { status: 400 });
  }
  const tierConfig = PRICING_TIERS[tier];

  let dbUser;
  try {
    dbUser = await getOrCreateUser(userId, email);
  } catch (e) {
    console.error("[promo-preview] getOrCreateUser failed", e);
    return NextResponse.json({ ok: false, error: "user_create_failed" }, { status: 500 });
  }

  const supabase = getServerSupabase();
  const { data, error } = await supabase.rpc("validate_promo", {
    p_code: code,
    p_user_id: dbUser.id,
    p_tier: tier,
    p_base_amount_paise: tierConfig.price_paise,
  });

  if (error) {
    console.error("[promo-preview] validate_promo RPC error", error);
    return NextResponse.json({ ok: false, error: "validation_failed" }, { status: 500 });
  }

  const result = data as ValidatePromoResult;
  if (!result.ok) {
    // Surface the specific error code (invalid_code, expired, wrong_tier,
    // already_used, cap_reached, inactive) so the UI can map to copy.
    return NextResponse.json(result, { status: 200 });
  }

  return NextResponse.json(result);
}
