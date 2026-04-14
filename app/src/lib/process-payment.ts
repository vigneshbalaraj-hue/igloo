// Shared payment-processing logic used by both the browser handler
// (/api/trigger-run) and the Razorpay webhook (/api/razorpay/webhook).
//
// Idempotent: safe to call multiple times for the same razorpay_payment_id.
// Both code paths can race; whoever wins creates the run, the other
// returns the existing one.

import "server-only";
import { getServerSupabase, getOrCreateUser, withRetry, supabaseRetry } from "@/lib/supabase-server";
import { PRICING_TIERS } from "@/lib/pricing";
import type { PricingTier } from "@/lib/pricing";
import { mintStudioToken } from "@/lib/studio-token";

const IGLOO_STUDIO_URL = process.env.IGLOO_STUDIO_URL!;
const STUDIO_TOKEN_TTL_MS = 24 * 60 * 60 * 1000; // 24h

function buildStudioUrl(run_id: string, user_id: string): string {
  const token = mintStudioToken({
    run_id,
    user_id,
    exp: Date.now() + STUDIO_TOKEN_TTL_MS,
  });
  return `${IGLOO_STUDIO_URL}/?token=${encodeURIComponent(token)}`;
}

export type ProcessPaymentInput = {
  clerkUserId: string;
  email: string;
  topic: string;
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string | null; // null when called from webhook
  amount_paise?: number;
  tier?: PricingTier;
  source: "client" | "webhook";
};

export type ProcessPaymentResult =
  | { ok: true; run_id: string; created: boolean; studio_url: string }
  | { ok: false; error: string; status: number };

/** Fire-and-forget: log a payment failure to the payment_alerts table. */
function logPaymentAlert(
  supabase: ReturnType<typeof getServerSupabase>,
  input: ProcessPaymentInput,
  step: string,
  errorMessage: string
) {
  supabase
    .from("payment_alerts")
    .insert({
      razorpay_payment_id: input.razorpay_payment_id,
      razorpay_order_id: input.razorpay_order_id,
      email: input.email,
      clerk_user_id: input.clerkUserId,
      step,
      error_message: errorMessage,
      source: input.source,
    })
    .then(({ error }) => {
      if (error) console.error("[payment_alert] failed to insert alert", error);
    });
}

export async function processPayment(input: ProcessPaymentInput): Promise<ProcessPaymentResult> {
  const supabase = getServerSupabase();
  const tier = input.tier ?? "single";
  const tierConfig = PRICING_TIERS[tier];

  // 1. Ensure user
  let dbUser;
  try {
    dbUser = await getOrCreateUser(input.clerkUserId, input.email);
  } catch (e) {
    console.error("[processPayment] getOrCreateUser failed", e);
    logPaymentAlert(supabase, input, "user_create_failed", String(e));
    return { ok: false, error: "user_create_failed", status: 500 };
  }

  // 2. Upsert payment (idempotent on razorpay_payment_id)
  let payment: { id: string };
  try {
    payment = await supabaseRetry(() =>
      supabase
        .from("payments")
        .upsert(
          {
            user_id: dbUser.id,
            razorpay_payment_id: input.razorpay_payment_id,
            razorpay_order_id: input.razorpay_order_id,
            razorpay_signature: input.razorpay_signature,
            amount_paise: input.amount_paise ?? tierConfig.price_paise,
            currency: "INR",
            status: "captured",
            credits_granted: tierConfig.credits,
            tier,
            webhook_event: input.source === "webhook" ? "payment.captured" : "client.handler",
          },
          { onConflict: "razorpay_payment_id" }
        )
        .select("id")
        .single()
    );
  } catch (e) {
    console.error("[processPayment] payment upsert failed", e);
    logPaymentAlert(supabase, input, "payment_upsert_failed", String(e));
    return { ok: false, error: "payment_upsert_failed", status: 500 };
  }

  // 3. Check if a run already exists for this payment
  let existingRun: { id: string } | null;
  try {
    existingRun = await withRetry(async () => {
      const { data, error } = await supabase
        .from("runs")
        .select("id")
        .eq("payment_id", payment.id)
        .maybeSingle();
      if (error) throw error;
      return data;
    });
  } catch (e) {
    console.error("[processPayment] run lookup failed", e);
    logPaymentAlert(supabase, input, "run_lookup_failed", String(e));
    return { ok: false, error: "run_lookup_failed", status: 500 };
  }

  if (existingRun) {
    return {
      ok: true,
      run_id: existingRun.id,
      created: false,
      studio_url: buildStudioUrl(existingRun.id, dbUser.id),
    };
  }

  // 4. Insert credit GRANT for this payment.
  //    The unique index credits_payment_id_payment_unique (migration 0005)
  //    prevents double grants from webhook retries.
  try {
    await supabaseRetry(() =>
      supabase.from("credits").insert({
        user_id: dbUser.id,
        delta: tierConfig.credits,
        reason: "payment",
        payment_id: payment.id,
        note: `${input.source} grant (${tier})`,
      })
    );
  } catch (e) {
    // 23505 = unique_violation — grant already exists (idempotent, continue)
    if ((e as { code?: string })?.code !== "23505") {
      console.error("[processPayment] credit grant insert failed", e);
      logPaymentAlert(supabase, input, "credit_grant_failed", String(e));
      return { ok: false, error: "credit_grant_failed", status: 500 };
    }
  }

  // 5. Insert the run. The unique index on runs.payment_id protects
  //    against the race where two callers got past the SELECT above.
  //    status='draft' — user has paid but hasn't finished the studio
  //    wizard yet. Flips to 'running' or 'queued' when they click
  //    "Create My Reel" inside the Flask studio.
  let run: { id: string };
  try {
    run = await supabaseRetry(() =>
      supabase
        .from("runs")
        .insert({
          user_id: dbUser.id,
          payment_id: payment.id,
          status: "draft",
          prompt: input.topic,
        })
        .select("id")
        .single()
    );
  } catch (e) {
    // 23505 = unique_violation. The other caller won the race.
    if ((e as { code?: string })?.code === "23505") {
      const { data: raced } = await supabase
        .from("runs")
        .select("id")
        .eq("payment_id", payment.id)
        .single();
      if (raced) {
        return {
          ok: true,
          run_id: raced.id,
          created: false,
          studio_url: buildStudioUrl(raced.id, dbUser.id),
        };
      }
    }
    console.error("[processPayment] run insert failed", e);
    logPaymentAlert(supabase, input, "run_insert_failed", String(e));
    return { ok: false, error: "run_insert_failed", status: 500 };
  }

  // Credit CONSUMPTION is no longer inserted here (migration 0008).
  // It happens at pipeline launch via consume_credit_for_run() so that
  // abandoned-wizard drafts don't silently burn the user's credit.

  // 6. Mint a signed studio URL — the browser navigates here after
  //    payment capture. No Modal trigger call; the Flask studio is
  //    always warm via min_containers=1.
  return {
    ok: true,
    run_id: run.id,
    created: true,
    studio_url: buildStudioUrl(run.id, dbUser.id),
  };
}
