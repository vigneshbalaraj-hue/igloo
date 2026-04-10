// Server-only Razorpay SDK instance + re-exports of shared pricing.

import "server-only";
import Razorpay from "razorpay";

// Re-export pricing constants so existing server-side imports keep working.
export { PRICING_TIERS, REEL_CURRENCY } from "@/lib/pricing";
export type { PricingTier } from "@/lib/pricing";

const KEY_ID = process.env.RAZORPAY_KEY_ID!;
const KEY_SECRET = process.env.RAZORPAY_KEY_SECRET!;

let cached: Razorpay | null = null;

export function getRazorpay(): Razorpay {
  if (!cached) {
    cached = new Razorpay({ key_id: KEY_ID, key_secret: KEY_SECRET });
  }
  return cached;
}
