-- Migration 0005: 2-tier pricing support
-- Adds tier column to payments, idempotency index on credit grants,
-- and atomic redeem_credit() function to prevent double-spend.

-- A. Add tier column to payments
ALTER TABLE public.payments ADD COLUMN IF NOT EXISTS tier text
  CHECK (tier IN ('single', 'double')) DEFAULT 'single';

-- B. Unique index to prevent double credit grants from webhook retries.
-- Only one credit grant row per payment_id where reason = 'payment'.
CREATE UNIQUE INDEX IF NOT EXISTS credits_payment_id_payment_unique
  ON public.credits (payment_id) WHERE reason = 'payment';

-- C. Atomic credit redemption function.
-- Serializes per-user via advisory lock, checks balance, inserts run + consumption.
-- Returns the new run UUID. Raises 'insufficient_credits' if balance < 1.
CREATE OR REPLACE FUNCTION public.redeem_credit(p_user_id uuid, p_topic text)
RETURNS uuid AS $$
DECLARE
  v_balance int;
  v_run_id uuid;
BEGIN
  -- Advisory lock keyed on user to serialize concurrent redemptions
  PERFORM pg_advisory_xact_lock(hashtext(p_user_id::text));

  SELECT COALESCE(balance, 0) INTO v_balance
    FROM public.user_balances WHERE user_id = p_user_id;

  IF v_balance IS NULL OR v_balance < 1 THEN
    RAISE EXCEPTION 'insufficient_credits';
  END IF;

  INSERT INTO public.runs (user_id, status, prompt)
    VALUES (p_user_id, 'draft', p_topic)
    RETURNING id INTO v_run_id;

  INSERT INTO public.credits (user_id, delta, reason, run_id, note)
    VALUES (p_user_id, -1, 'run', v_run_id, 'credit redemption');

  RETURN v_run_id;
END;
$$ LANGUAGE plpgsql;
