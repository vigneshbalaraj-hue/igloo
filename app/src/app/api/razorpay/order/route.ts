// POST /api/razorpay/order
// Creates a Razorpay order so the browser can open Checkout.
// Auth: Clerk session required.
//
// Promo support: when body.promoCode is set and PROMO_CODES_ENABLED=true,
// we validate the code via validate_promo() RPC, create the order at the
// discounted amount, and embed promo_id in Razorpay notes so the webhook
// can record the redemption after capture.

import { NextRequest, NextResponse } from "next/server";
import { auth, currentUser } from "@clerk/nextjs/server";
import { getRazorpay, PRICING_TIERS, REEL_CURRENCY } from "@/lib/razorpay";
import type { PricingTier } from "@/lib/pricing";
import { getServerSupabase, getOrCreateUser } from "@/lib/supabase-server";

export const runtime = "nodejs"; // razorpay sdk needs node, not edge

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
  const { userId } = await auth();
  if (!userId) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  let body: { topic?: string; tier?: string; promoCode?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid_json" }, { status: 400 });
  }
  const topic = (body.topic ?? "").trim();
  if (!topic) {
    return NextResponse.json({ error: "topic_required" }, { status: 400 });
  }

  const tier = (body.tier ?? "single") as PricingTier;
  if (!(tier in PRICING_TIERS)) {
    return NextResponse.json({ error: "invalid_tier" }, { status: 400 });
  }
  const tierConfig = PRICING_TIERS[tier];

  // Default to full-price purchase. If a valid promo code is provided
  // *and* the feature flag is on, we replace these.
  let amountPaise: number = tierConfig.price_paise;
  let promoId: string | null = null;
  let promoCodeCanonical: string | null = null;

  const promoCode = (body.promoCode ?? "").trim();
  if (promoCode && PROMO_ENABLED) {
    const user = await currentUser();
    const email = user?.primaryEmailAddress?.emailAddress;
    if (!email) {
      return NextResponse.json({ error: "no_email" }, { status: 400 });
    }

    let dbUser;
    try {
      dbUser = await getOrCreateUser(userId, email);
    } catch (e) {
      console.error("[razorpay/order] getOrCreateUser failed", e);
      return NextResponse.json({ error: "user_create_failed" }, { status: 500 });
    }

    const supabase = getServerSupabase();
    const { data: validation, error: rpcError } = await supabase.rpc("validate_promo", {
      p_code: promoCode,
      p_user_id: dbUser.id,
      p_tier: tier,
      p_base_amount_paise: tierConfig.price_paise,
    });

    if (rpcError) {
      console.error("[razorpay/order] validate_promo RPC error", rpcError);
      return NextResponse.json({ error: "promo_validation_failed" }, { status: 500 });
    }

    const result = validation as ValidatePromoResult;
    if (!result.ok) {
      // Surface the specific failure code (invalid_code, expired, etc.)
      // 400 — the client should not retry without changing the code.
      return NextResponse.json({ error: "promo_invalid", reason: result.error }, { status: 400 });
    }

    amountPaise = result.discounted_amount_paise;
    promoId = result.promo_id;
    promoCodeCanonical = result.code;
  }

  const rzp = getRazorpay();
  try {
    // Razorpay note values must be strings.
    const notes: Record<string, string> = {
      clerk_user_id: userId,
      topic: topic.slice(0, 200),
      tier,
    };
    if (promoId) {
      notes.promo_id = promoId;
      if (promoCodeCanonical) notes.promo_code = promoCodeCanonical;
    }

    const order = await rzp.orders.create({
      amount: amountPaise,
      currency: REEL_CURRENCY,
      receipt: `igloo_${Date.now()}`,
      notes,
    });

    return NextResponse.json({
      orderId: order.id,
      amount: order.amount,
      currency: order.currency,
      keyId: process.env.RAZORPAY_KEY_ID,
      tier,
      promoId,
      promoCode: promoCodeCanonical,
      originalAmount: promoId ? tierConfig.price_paise : null,
    });
  } catch (e) {
    console.error("[razorpay/order] error", JSON.stringify(e, null, 2));
    const detail = e instanceof Error ? e.message : JSON.stringify(e);
    return NextResponse.json(
      { error: "razorpay_order_failed", detail },
      { status: 500 }
    );
  }
}
