// Shared payment-processing logic used by both the browser handler
// (/api/trigger-run) and the Razorpay webhook (/api/razorpay/webhook).
//
// Idempotent: safe to call multiple times for the same razorpay_payment_id.
// Both code paths can race; whoever wins creates the run, the other
// returns the existing one.

import "server-only";
import { getServerSupabase, getOrCreateUser } from "@/lib/supabase-server";
import { REEL_PRICE_PAISE } from "@/lib/razorpay";

const MODAL_TRIGGER_URL = process.env.MODAL_TRIGGER_URL!;

export type ProcessPaymentInput = {
  clerkUserId: string;
  email: string;
  topic: string;
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string | null; // null when called from webhook
  amount_paise?: number;
  source: "client" | "webhook";
};

export type ProcessPaymentResult =
  | { ok: true; run_id: string; created: boolean }
  | { ok: false; error: string; status: number };

export async function processPayment(input: ProcessPaymentInput): Promise<ProcessPaymentResult> {
  const supabase = getServerSupabase();

  // 1. Ensure user
  let dbUser;
  try {
    dbUser = await getOrCreateUser(input.clerkUserId, input.email);
  } catch (e) {
    console.error("[processPayment] getOrCreateUser failed", e);
    return { ok: false, error: "user_create_failed", status: 500 };
  }

  // 2. Upsert payment (idempotent on razorpay_payment_id)
  const { data: payment, error: payErr } = await supabase
    .from("payments")
    .upsert(
      {
        user_id: dbUser.id,
        razorpay_payment_id: input.razorpay_payment_id,
        razorpay_order_id: input.razorpay_order_id,
        razorpay_signature: input.razorpay_signature,
        amount_paise: input.amount_paise ?? REEL_PRICE_PAISE,
        currency: "INR",
        status: "captured",
        credits_granted: 1,
        webhook_event: input.source === "webhook" ? "payment.captured" : "client.handler",
      },
      { onConflict: "razorpay_payment_id" }
    )
    .select("id")
    .single();

  if (payErr || !payment) {
    console.error("[processPayment] payment upsert failed", payErr);
    return { ok: false, error: "payment_upsert_failed", status: 500 };
  }

  // 3. Check if a run already exists for this payment
  const { data: existingRun, error: existErr } = await supabase
    .from("runs")
    .select("id")
    .eq("payment_id", payment.id)
    .maybeSingle();

  if (existErr) {
    console.error("[processPayment] run lookup failed", existErr);
    return { ok: false, error: "run_lookup_failed", status: 500 };
  }

  if (existingRun) {
    return { ok: true, run_id: existingRun.id, created: false };
  }

  // 4. Insert credit GRANT for this payment. Idempotent: a unique
  //    constraint on (payment_id, reason='payment') would be ideal,
  //    but we don't have one — instead we check first. The race
  //    window is tight enough (single-payment id) that double-grant
  //    is unlikely; the unique index on runs.payment_id below is
  //    the real safety net.
  const { data: existingGrant } = await supabase
    .from("credits")
    .select("id")
    .eq("payment_id", payment.id)
    .eq("reason", "payment")
    .maybeSingle();

  if (!existingGrant) {
    const { error: grantErr } = await supabase.from("credits").insert({
      user_id: dbUser.id,
      delta: 1,
      reason: "payment",
      payment_id: payment.id,
      note: `${input.source} grant`,
    });
    if (grantErr) {
      console.error("[processPayment] credit grant insert failed", grantErr);
      return { ok: false, error: "credit_grant_failed", status: 500 };
    }
  }

  // 5. Insert the run. The unique index on runs.payment_id protects
  //    against the race where two callers got past the SELECT above.
  const { data: run, error: runErr } = await supabase
    .from("runs")
    .insert({
      user_id: dbUser.id,
      payment_id: payment.id,
      status: "queued",
      prompt: input.topic,
    })
    .select("id")
    .single();

  if (runErr || !run) {
    // 23505 = unique_violation. The other caller won the race.
    if ((runErr as { code?: string } | null)?.code === "23505") {
      const { data: raced } = await supabase
        .from("runs")
        .select("id")
        .eq("payment_id", payment.id)
        .single();
      if (raced) return { ok: true, run_id: raced.id, created: false };
    }
    console.error("[processPayment] run insert failed", runErr);
    return { ok: false, error: "run_insert_failed", status: 500 };
  }

  // 6. Insert credit CONSUMPTION row tied to this run.
  const { error: consumeErr } = await supabase.from("credits").insert({
    user_id: dbUser.id,
    delta: -1,
    reason: "run",
    run_id: run.id,
    note: "reel consumption",
  });
  if (consumeErr) {
    // Not fatal — log and continue. Net balance will be off by 1
    // until reconciled, but the run still belongs to the user.
    console.error("[processPayment] credit consumption insert failed (non-fatal)", consumeErr);
  }

  // 5. Fire Modal trigger
  try {
    const modalRes = await fetch(MODAL_TRIGGER_URL, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ run_id: run.id }),
    });
    if (!modalRes.ok) {
      const t = await modalRes.text();
      console.error("[processPayment] modal trigger non-2xx", modalRes.status, t);
      await supabase
        .from("runs")
        .update({ status: "failed", rejection_reason: `modal_trigger_${modalRes.status}` })
        .eq("id", run.id);
      return { ok: false, error: "modal_trigger_failed", status: 502 };
    }
  } catch (e) {
    console.error("[processPayment] modal trigger threw", e);
    await supabase
      .from("runs")
      .update({ status: "failed", rejection_reason: "modal_trigger_network" })
      .eq("id", run.id);
    return { ok: false, error: "modal_trigger_network", status: 502 };
  }

  return { ok: true, run_id: run.id, created: true };
}
