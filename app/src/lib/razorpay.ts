// Server-only Razorpay SDK instance.
// Currently in TEST MODE — see memory/project_phase6_scale_debt.md.

import "server-only";
import Razorpay from "razorpay";

const KEY_ID = process.env.RAZORPAY_KEY_ID!;
const KEY_SECRET = process.env.RAZORPAY_KEY_SECRET!;

export const REEL_PRICE_PAISE = 42000; // ₹420
export const REEL_CURRENCY = "INR";

let cached: Razorpay | null = null;

export function getRazorpay(): Razorpay {
  if (!cached) {
    cached = new Razorpay({ key_id: KEY_ID, key_secret: KEY_SECRET });
  }
  return cached;
}
