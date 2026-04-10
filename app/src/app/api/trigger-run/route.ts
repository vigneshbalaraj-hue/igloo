// POST /api/trigger-run
// Browser handler called after a successful Razorpay Checkout.
// Verifies the payment signature, then delegates to processPayment()
// which is shared with the Razorpay webhook for idempotency.

import { NextRequest, NextResponse } from "next/server";
import crypto from "node:crypto";
import { auth, currentUser } from "@clerk/nextjs/server";
import { processPayment } from "@/lib/process-payment";
import type { PricingTier } from "@/lib/pricing";

export const runtime = "nodejs";

const RAZORPAY_KEY_SECRET = process.env.RAZORPAY_KEY_SECRET!;

function verifyRazorpaySignature(
  orderId: string,
  paymentId: string,
  signature: string
): boolean {
  const expected = crypto
    .createHmac("sha256", RAZORPAY_KEY_SECRET)
    .update(`${orderId}|${paymentId}`)
    .digest("hex");
  const a = Buffer.from(expected);
  const b = Buffer.from(signature);
  if (a.length !== b.length) return false;
  return crypto.timingSafeEqual(a, b);
}

export async function POST(req: NextRequest) {
  const { userId } = await auth();
  if (!userId) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const user = await currentUser();
  const email = user?.primaryEmailAddress?.emailAddress;
  if (!email) {
    return NextResponse.json({ error: "no_email" }, { status: 400 });
  }

  let body: {
    topic?: string;
    tier?: string;
    razorpay_order_id?: string;
    razorpay_payment_id?: string;
    razorpay_signature?: string;
  };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid_json" }, { status: 400 });
  }

  const {
    topic,
    tier: rawTier,
    razorpay_order_id,
    razorpay_payment_id,
    razorpay_signature,
  } = body;
  const tier = (rawTier === "double" ? "double" : "single") as PricingTier;

  if (!topic || !razorpay_order_id || !razorpay_payment_id || !razorpay_signature) {
    return NextResponse.json({ error: "missing_fields" }, { status: 400 });
  }

  if (!verifyRazorpaySignature(razorpay_order_id, razorpay_payment_id, razorpay_signature)) {
    return NextResponse.json({ error: "invalid_signature" }, { status: 400 });
  }

  const result = await processPayment({
    clerkUserId: userId,
    email,
    topic,
    razorpay_order_id,
    razorpay_payment_id,
    razorpay_signature,
    tier,
    source: "client",
  });

  if (!result.ok) {
    return NextResponse.json({ error: result.error }, { status: result.status });
  }

  return NextResponse.json({
    run_id: result.run_id,
    created: result.created,
    studio_url: result.studio_url,
  });
}
