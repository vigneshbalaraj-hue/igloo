// POST /api/razorpay/order
// Creates a Razorpay order so the browser can open Checkout.
// Auth: Clerk session required.

import { NextRequest, NextResponse } from "next/server";
import { auth } from "@clerk/nextjs/server";
import { getRazorpay, PRICING_TIERS, REEL_CURRENCY } from "@/lib/razorpay";
import type { PricingTier } from "@/lib/pricing";

export const runtime = "nodejs"; // razorpay sdk needs node, not edge

export async function POST(req: NextRequest) {
  const { userId } = await auth();
  if (!userId) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  let body: { topic?: string; tier?: string };
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

  const rzp = getRazorpay();
  try {
    const order = await rzp.orders.create({
      amount: tierConfig.price_paise,
      currency: REEL_CURRENCY,
      receipt: `igloo_${Date.now()}`,
      notes: { clerk_user_id: userId, topic: topic.slice(0, 200), tier },
    });

    return NextResponse.json({
      orderId: order.id,
      amount: order.amount,
      currency: order.currency,
      keyId: process.env.RAZORPAY_KEY_ID,
      tier,
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
