"use client";

import { useState } from "react";
import { useUser } from "@clerk/nextjs";

// Display-only pricing (sticker). The actual charge is ₹1,249 INR via
// Razorpay — disclosed below the sticker. Keep these values in sync with
// app/src/lib/razorpay.ts.
const DISPLAY_USD = "14.99";
const DISPLAY_STRIKETHROUGH_USD = "19.99";
const DISPLAY_INR_DISCLOSURE = "Charged as ₹1,249 INR";

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
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

      // 1. Create a Razorpay order on the server
      const orderRes = await fetch("/api/razorpay/order", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ topic }),
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
          description: "1 reel",
          order_id: orderId,
          prefill: {
            email: user.primaryEmailAddress?.emailAddress ?? "",
            name: user.fullName ?? "",
          },
          theme: { color: "#0a0a0a" },
          handler: async (response: RazorpayHandlerResponse) => {
            // 3. Payment successful — trigger the run
            try {
              const triggerRes = await fetch("/api/trigger-run", {
                method: "POST",
                headers: { "content-type": "application/json" },
                body: JSON.stringify({
                  topic,
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
              // Full navigation so the Flask session cookie lands on
              // the Modal subdomain.
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

        <div className="mt-8 rounded-2xl border border-neutral-800 bg-neutral-950 px-6 py-5">
          <div className="flex items-baseline gap-3">
            <span className="text-4xl font-semibold tracking-tight">${DISPLAY_USD}</span>
            <span className="text-lg text-neutral-500 line-through">${DISPLAY_STRIKETHROUGH_USD}</span>
          </div>
          <p className="mt-1 text-sm text-neutral-400">{DISPLAY_INR_DISCLOSURE}</p>
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
          {busy ? "Working…" : `Buy 1 reel — $${DISPLAY_USD}`}
        </button>

      </div>
    </main>
  );
}
