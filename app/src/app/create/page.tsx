"use client";

import { useState, useEffect } from "react";
import { useUser } from "@clerk/nextjs";
import { PRICING_TIERS } from "@/lib/pricing";
import type { PricingTier } from "@/lib/pricing";

type RazorpayHandlerResponse = {
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
};

type RazorpayOptions = {
  key: string;
  amount: number | string;
  currency: string;
  name: string;
  description?: string;
  order_id: string;
  prefill?: { email?: string; name?: string };
  theme?: { color?: string };
  handler: (response: RazorpayHandlerResponse) => void;
  modal?: { ondismiss?: () => void };
};

type RazorpayInstance = { open: () => void };
type RazorpayCtor = new (opts: RazorpayOptions) => RazorpayInstance;

declare global {
  interface Window {
    Razorpay: RazorpayCtor;
  }
}

const RAZORPAY_SCRIPT = "https://checkout.razorpay.com/v1/checkout.js";

function loadRazorpayScript(): Promise<boolean> {
  return new Promise((resolve) => {
    if (typeof window === "undefined") return resolve(false);
    if (window.Razorpay) return resolve(true);
    const script = document.createElement("script");
    script.src = RAZORPAY_SCRIPT;
    script.onload = () => resolve(true);
    script.onerror = () => resolve(false);
    document.body.appendChild(script);
  });
}

export default function CreatePage() {
  const { user, isLoaded } = useUser();
  const [topic, setTopic] = useState("");
  const [tier, setTier] = useState<PricingTier>("double");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [creditBalance, setCreditBalance] = useState<number | null>(null);
  const [betaAllowed, setBetaAllowed] = useState<boolean | null>(null);

  // Fetch credit balance + beta status on mount
  useEffect(() => {
    if (!isLoaded || !user) return;
    Promise.all([
      fetch("/api/credits/balance").then((r) => r.json()),
      fetch("/api/beta-status").then((r) => r.json()),
    ])
      .then(([balData, betaData]) => {
        setCreditBalance(balData.balance ?? 0);
        setBetaAllowed(betaData.allowed ?? false);
      })
      .catch(() => {
        setCreditBalance(0);
        setBetaAllowed(false);
      });
  }, [isLoaded, user]);

  async function handleBuy() {
    setError(null);
    if (!topic.trim()) {
      setError("Give it a topic first.");
      return;
    }
    if (!isLoaded || !user) {
      setError("Still loading your session — try again in a sec.");
      return;
    }
    setBusy(true);

    try {
      const ok = await loadRazorpayScript();
      if (!ok) throw new Error("Failed to load Razorpay checkout.");

      const tierConfig = PRICING_TIERS[tier];

      // 1. Create a Razorpay order on the server
      const orderRes = await fetch("/api/razorpay/order", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ topic, tier }),
      });
      if (!orderRes.ok) {
        const t = await orderRes.text();
        throw new Error(`Order create failed: ${t}`);
      }
      const { orderId, amount, currency, keyId } = await orderRes.json();

      // 2. Open Razorpay checkout
      await new Promise<void>((resolve, reject) => {
        const rzp = new window.Razorpay({
          key: keyId,
          amount,
          currency,
          name: "Igloo",
          description: tierConfig.label,
          order_id: orderId,
          prefill: {
            email: user.primaryEmailAddress?.emailAddress ?? "",
            name: user.fullName ?? "",
          },
          theme: { color: "#0a0a0a" },
          handler: async (response: RazorpayHandlerResponse) => {
            try {
              const triggerRes = await fetch("/api/trigger-run", {
                method: "POST",
                headers: { "content-type": "application/json" },
                body: JSON.stringify({
                  topic,
                  tier,
                  razorpay_order_id: response.razorpay_order_id,
                  razorpay_payment_id: response.razorpay_payment_id,
                  razorpay_signature: response.razorpay_signature,
                }),
              });
              if (!triggerRes.ok) {
                const t = await triggerRes.text();
                throw new Error(`Trigger failed: ${t}`);
              }
              const { studio_url } = await triggerRes.json();
              if (!studio_url) throw new Error("Missing studio URL in response.");
              window.location.href = studio_url;
              resolve();
            } catch (e) {
              reject(e);
            }
          },
          modal: {
            ondismiss: () => reject(new Error("Checkout dismissed.")),
          },
        });
        rzp.open();
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function handleRedeemCredit() {
    setError(null);
    if (!topic.trim()) {
      setError("Give it a topic first.");
      return;
    }
    setBusy(true);

    try {
      const res = await fetch("/api/redeem-credit", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ topic }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        if (data.error === "insufficient_credits") {
          setCreditBalance(0);
          throw new Error("No credits left. Please purchase a new reel.");
        }
        throw new Error(`Redeem failed: ${data.error ?? res.statusText}`);
      }
      const { studio_url } = await res.json();
      if (!studio_url) throw new Error("Missing studio URL in response.");
      window.location.href = studio_url;
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const singleTier = PRICING_TIERS.single;
  const doubleTier = PRICING_TIERS.double;
  const hasCredits = creditBalance !== null && creditBalance > 0;

  // Beta full — waitlist screen
  if (betaAllowed === false) {
    return (
      <main className="flex-1 flex flex-col items-center justify-center px-6 py-16">
        <div className="w-full max-w-xl text-center">
          <div className="rounded-xl border border-neutral-800 bg-neutral-900 px-8 py-12">
            <h1 className="text-3xl font-semibold tracking-tight mb-3">
              Beta is full
            </h1>
            <p className="text-neutral-400 leading-relaxed max-w-md mx-auto">
              Thank you for your interest in Igloo! We&apos;re at capacity for
              our beta launch. We have your email on file and will reach out as
              soon as spots open up.
            </p>
            <p className="text-neutral-500 text-sm mt-6">
              We appreciate your patience — it won&apos;t be long.
            </p>
          </div>
        </div>
      </main>
    );
  }

  // Still loading beta status
  if (betaAllowed === null) {
    return (
      <main className="flex-1 flex items-center justify-center">
        <p className="text-neutral-500">Loading...</p>
      </main>
    );
  }

  return (
    <main className="flex-1 flex flex-col items-center justify-center px-6 py-16">
      <div className="w-full max-w-xl">
        <h1 className="text-3xl font-semibold tracking-tight mb-2">
          Create a reel
        </h1>
        <p className="text-neutral-400 mb-8">
          Tell us what it&apos;s about. We handle the rest.
        </p>

        <label className="block text-sm font-medium mb-2">Topic</label>
        <textarea
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          rows={4}
          placeholder="e.g. The history of the espresso machine"
          className="w-full rounded-xl bg-neutral-900 border border-neutral-800 px-4 py-3 text-base resize-y focus:outline-none focus:ring-2 focus:ring-white/30"
        />

        {/* Credit balance banner */}
        {hasCredits && (
          <div className="mt-6 rounded-xl border border-emerald-800 bg-emerald-950/50 px-5 py-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-emerald-300">
                  You have {creditBalance} credit{creditBalance !== 1 ? "s" : ""}
                </p>
                <p className="text-xs text-emerald-400/70 mt-0.5">
                  Use a credit to skip payment
                </p>
              </div>
              <button
                onClick={handleRedeemCredit}
                disabled={busy}
                className="rounded-full bg-emerald-600 text-white px-5 py-2.5 text-sm font-medium hover:bg-emerald-500 transition disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {busy ? "Working…" : "Use 1 credit"}
              </button>
            </div>
          </div>
        )}

        {/* Divider when credits available */}
        {hasCredits && (
          <div className="flex items-center gap-4 mt-6">
            <div className="flex-1 h-px bg-neutral-800" />
            <span className="text-xs text-neutral-500 uppercase tracking-wider">or buy more</span>
            <div className="flex-1 h-px bg-neutral-800" />
          </div>
        )}

        {/* Tier selector */}
        <div className="mt-6 grid grid-cols-2 gap-3">
          {/* Single tier */}
          <button
            type="button"
            onClick={() => setTier("single")}
            className={`rounded-2xl border px-5 py-5 text-left transition ${
              tier === "single"
                ? "border-white bg-neutral-900"
                : "border-neutral-800 bg-neutral-950 hover:border-neutral-700"
            }`}
          >
            <span className="text-2xl font-semibold tracking-tight">
              ${singleTier.display_usd}
            </span>
            <p className="mt-1 text-sm text-neutral-400">{singleTier.label}</p>
            <p className="mt-0.5 text-xs text-neutral-500">
              {singleTier.display_inr}
            </p>
          </button>

          {/* Double tier */}
          <button
            type="button"
            onClick={() => setTier("double")}
            className={`relative rounded-2xl border px-5 py-5 text-left transition ${
              tier === "double"
                ? "border-white bg-neutral-900"
                : "border-neutral-800 bg-neutral-950 hover:border-neutral-700"
            }`}
          >
            {doubleTier.badge && (
              <span className="absolute -top-2.5 right-3 rounded-full bg-white text-black text-[10px] font-semibold px-2.5 py-0.5 uppercase tracking-wider">
                {doubleTier.badge}
              </span>
            )}
            <span className="text-2xl font-semibold tracking-tight">
              ${doubleTier.display_usd}
            </span>
            <p className="mt-1 text-sm text-neutral-400">{doubleTier.label}</p>
            <p className="mt-0.5 text-xs text-neutral-500">
              {doubleTier.display_inr}
            </p>
          </button>
        </div>

        {error && (
          <div className="mt-4 rounded-lg bg-red-950 border border-red-900 text-red-200 px-4 py-3 text-sm">
            {error}
          </div>
        )}

        <button
          onClick={handleBuy}
          disabled={busy}
          className="mt-6 w-full rounded-full bg-white text-black px-6 py-4 font-medium hover:bg-neutral-200 transition disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {busy
            ? "Working…"
            : `Buy ${PRICING_TIERS[tier].label} — $${PRICING_TIERS[tier].display_usd}`}
        </button>
      </div>
    </main>
  );
}
