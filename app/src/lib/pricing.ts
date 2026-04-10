// Shared pricing constants — safe for both server and client imports.
// Do NOT add "server-only" here; the create page and landing Pricing
// component both need these values.

export type PricingTier = "single" | "double";

export const PRICING_TIERS = {
  single: {
    price_paise: 99900, // ₹999
    credits: 1,
    display_usd: "9.99",
    display_inr: "₹999",
    label: "1 reel",
  },
  double: {
    price_paise: 124900, // ₹1,249
    credits: 2,
    display_usd: "14.99",
    display_inr: "₹1,249",
    label: "2 reels",
    badge: "Save 25%",
  },
} as const;

export const REEL_CURRENCY = "INR";
