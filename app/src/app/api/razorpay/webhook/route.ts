// POST /api/razorpay/webhook
// Razorpay → us. Server-to-server. Verifies HMAC-SHA256 signature
// against the raw request body using the webhook secret.
//
// Auth: NOT a Clerk session. Public route in proxy.ts.
// Idempotency: delegates to processPayment(), which is idempotent
// on razorpay_payment_id.
//
// Razorpay retries failed webhooks for several hours. Always 200
// quickly on signature failure or unknown event types so they stop
// retrying — but log loudly.

import { NextRequest, NextResponse } from "next/server";
import crypto from "node:crypto";
import { processPayment } from "@/lib/process-payment";
import type { PricingTier } from "@/lib/pricing";

export const runtime = "nodejs";

const WEBHOOK_SECRET = process.env.RAZORPAY_WEBHOOK_SECRET ?? "";

type RazorpayPaymentEntity = {
  id: string;
  order_id: string;
  status: string;
  amount: number;
  currency: string;
  email?: string;
  contact?: string;
  notes?: Record<string, string>;
};

type RazorpayWebhookPayload = {
  event: string;
  payload?: {
    payment?: { entity?: RazorpayPaymentEntity };
  };
};

function verifyWebhookSignature(rawBody: string, signature: string): boolean {
  if (!WEBHOOK_SECRET) {
    console.error("[razorpay/webhook] RAZORPAY_WEBHOOK_SECRET is not set");
    return false;
  }
  const expected = crypto
    .createHmac("sha256", WEBHOOK_SECRET)
    .update(rawBody)
    .digest("hex");
  const a = Buffer.from(expected);
  const b = Buffer.from(signature);
  if (a.length !== b.length) return false;
  return crypto.timingSafeEqual(a, b);
}

export async function POST(req: NextRequest) {
  // CRITICAL: Razorpay signs the raw bytes. Do NOT parse-then-stringify.
  const rawBody = await req.text();
  const signature = req.headers.get("x-razorpay-signature") ?? "";

  if (!verifyWebhookSignature(rawBody, signature)) {
    console.warn("[razorpay/webhook] invalid signature");
    // 400 — Razorpay treats non-2xx as a retry signal. Invalid sig
    // is not transient so we'd loop forever. But returning 200 here
    // would mask real attacks in logs. We accept the retry noise as
    // a cost of correctness; verify the secret is set right.
    return NextResponse.json({ error: "invalid_signature" }, { status: 400 });
  }

  let body: RazorpayWebhookPayload;
  try {
    body = JSON.parse(rawBody) as RazorpayWebhookPayload;
  } catch {
    return NextResponse.json({ error: "invalid_json" }, { status: 400 });
  }

  // We only act on payment.captured. Other events (payment.failed,
  // refund.*, order.paid) are 200'd and ignored for now.
  if (body.event !== "payment.captured") {
    console.log(`[razorpay/webhook] ignoring event: ${body.event}`);
    return NextResponse.json({ ok: true, ignored: body.event });
  }

  const payment = body.payload?.payment?.entity;
  if (!payment) {
    console.error("[razorpay/webhook] payment.captured missing entity");
    return NextResponse.json({ error: "missing_entity" }, { status: 400 });
  }

  const clerkUserId = payment.notes?.clerk_user_id;
  const topic = payment.notes?.topic;
  const tier = (payment.notes?.tier ?? "single") as PricingTier;
  const email = payment.email;

  if (!clerkUserId || !topic) {
    // This will happen for any payment NOT created via our /api/razorpay/order
    // endpoint (e.g. someone testing in the Razorpay dashboard). 200 to
    // stop retries; not actionable for us.
    console.warn("[razorpay/webhook] payment missing notes.clerk_user_id or notes.topic", {
      payment_id: payment.id,
    });
    return NextResponse.json({ ok: true, ignored: "no_notes" });
  }

  if (!email) {
    console.warn("[razorpay/webhook] payment missing email", { payment_id: payment.id });
    return NextResponse.json({ ok: true, ignored: "no_email" });
  }

  const result = await processPayment({
    clerkUserId,
    email,
    topic,
    razorpay_order_id: payment.order_id,
    razorpay_payment_id: payment.id,
    razorpay_signature: null,
    amount_paise: payment.amount,
    tier,
    source: "webhook",
  });

  if (!result.ok) {
    console.error("[razorpay/webhook] processPayment failed", result);
    // Return 5xx for transient failures so Razorpay retries.
    // Return 200 for permanent failures (validation, etc.) so it stops.
    if (result.status >= 500) {
      return NextResponse.json({ error: result.error }, { status: 502 });
    }
    return NextResponse.json({ ok: true, ignored: result.error });
  }

  return NextResponse.json({ ok: true, run_id: result.run_id, created: result.created });
}
