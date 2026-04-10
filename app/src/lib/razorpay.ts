// Server-only Razorpay SDK instance.
// Currently in TEST MODE — see memory/project_phase6_scale_debt.md.

import "server-only";
import Razorpay from "razorpay";

const KEY_ID = process.env.RAZORPAY_KEY_ID!;
const KEY_SECRET = process.env.RAZORPAY_KEY_SECRET!;

// Charged amount (actual money). Keep in INR until Razorpay International
// Cards activates — see .tmp/checkpoint_2026-04-08_session27.md.
export const REEL_PRICE_PAISE = 124900; // ₹1,249
export const REEL_CURRENCY = "INR";

// Display-only positioning (sticker price shown on landing + /create).
// The INR charge is disclosed next to it for consumer-protection compliance.
export const REEL_DISPLAY_USD = "14.99";
export const REEL_DISPLAY_STRIKETHROUGH_USD = "19.99";
export const REEL_DISPLAY_INR_DISCLOSURE = "Charged as ₹1,249 INR";

let cached: Razorpay | null = null;

export function getRazorpay(): Razorpay {
  if (!cached) {
    cached = new Razorpay({ key_id: KEY_ID, key_secret: KEY_SECRET });
  }
  return cached;
}
