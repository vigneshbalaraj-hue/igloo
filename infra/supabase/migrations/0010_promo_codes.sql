-- Migration 0010: Promo codes + redemption ledger.
--
-- Lets us run discount campaigns (e.g. IGLOO50 win-back blast).
-- Two surfaces:
--   /api/razorpay/promo-preview   -> validate_promo() RPC (no side-effects)
--   /api/razorpay/order            -> validate_promo() RPC + embed promo_id
--                                     in Razorpay notes
--   /api/razorpay/webhook         -> processPayment() reads promo_id and
--                                     calls record_promo_redemption() RPC
--                                     after the payment row is upserted.
--
-- Idempotency: redemption row is keyed on payment_id (unique). If the
-- same payment.captured webhook fires twice, we no-op.
-- Race safety: per-user uniqueness on (promo_id, user_id) prevents the
-- rare double-redeem (user opens two Razorpay sheets, pays both before
-- first webhook fires). Second insert raises 23505; caller logs an alert.
--
-- Idempotent: safe to re-run.

CREATE EXTENSION IF NOT EXISTS citext;

-- ============================================================
-- promo_codes
-- ============================================================
CREATE TABLE IF NOT EXISTS public.promo_codes (
  id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code                     citext UNIQUE NOT NULL,
  discount_pct             integer NOT NULL CHECK (discount_pct > 0 AND discount_pct <= 100),
  applies_to_tier          text NOT NULL DEFAULT 'both'
                           CHECK (applies_to_tier IN ('single', 'double', 'both')),
  valid_from               timestamptz NOT NULL DEFAULT now(),
  valid_until              timestamptz NOT NULL,
  max_redemptions_per_user integer NOT NULL DEFAULT 1
                           CHECK (max_redemptions_per_user >= 1),
  total_redemption_cap     integer,                          -- nullable = no cap
  active                   boolean NOT NULL DEFAULT true,
  created_at               timestamptz NOT NULL DEFAULT now(),
  updated_at               timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS promo_codes_code_idx ON public.promo_codes (code);

DROP TRIGGER IF EXISTS promo_codes_set_updated_at ON public.promo_codes;
CREATE TRIGGER promo_codes_set_updated_at
  BEFORE UPDATE ON public.promo_codes
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ============================================================
-- promo_redemptions
--   One row per captured payment that used a promo. Created by the
--   record_promo_redemption() RPC — never directly from app code.
-- ============================================================
CREATE TABLE IF NOT EXISTS public.promo_redemptions (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  promo_id    uuid NOT NULL REFERENCES public.promo_codes(id) ON DELETE CASCADE,
  user_id     uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  payment_id  uuid NOT NULL REFERENCES public.payments(id) ON DELETE CASCADE,
  -- Snapshot at capture time. Lets reporting work even if the
  -- promo_codes row is later edited or deleted.
  discount_pct           integer NOT NULL,
  original_amount_paise  integer NOT NULL,
  discounted_amount_paise integer NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now()
);

-- One redemption per payment (idempotency for webhook retries).
CREATE UNIQUE INDEX IF NOT EXISTS promo_redemptions_payment_unique
  ON public.promo_redemptions (payment_id);

-- One redemption per (promo, user) — enforces single-use per user
-- when max_redemptions_per_user = 1 (the IGLOO50 case). For codes
-- that allow N redemptions per user, this index has to be dropped
-- and the cap moved to RPC-only checks.
CREATE UNIQUE INDEX IF NOT EXISTS promo_redemptions_user_unique
  ON public.promo_redemptions (promo_id, user_id);

CREATE INDEX IF NOT EXISTS promo_redemptions_user_idx  ON public.promo_redemptions (user_id);
CREATE INDEX IF NOT EXISTS promo_redemptions_promo_idx ON public.promo_redemptions (promo_id);

ALTER TABLE public.promo_codes        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.promo_redemptions  ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- validate_promo()
--   Read-only validation. Used by both /promo-preview and /order.
--   Returns jsonb with discount details on success; { ok: false, error }
--   on failure with one of: invalid_code, expired, wrong_tier,
--   already_used, cap_reached, inactive.
-- ============================================================
CREATE OR REPLACE FUNCTION public.validate_promo(
  p_code              text,
  p_user_id           uuid,
  p_tier              text,
  p_base_amount_paise integer
) RETURNS jsonb AS $$
DECLARE
  v_promo        public.promo_codes;
  v_user_count   int;
  v_global_count int;
  v_discounted   int;
BEGIN
  IF p_code IS NULL OR length(trim(p_code)) = 0 THEN
    RETURN jsonb_build_object('ok', false, 'error', 'invalid_code');
  END IF;

  SELECT * INTO v_promo
    FROM public.promo_codes
    WHERE code = trim(p_code);

  IF NOT FOUND THEN
    RETURN jsonb_build_object('ok', false, 'error', 'invalid_code');
  END IF;

  IF NOT v_promo.active THEN
    RETURN jsonb_build_object('ok', false, 'error', 'inactive');
  END IF;

  IF now() < v_promo.valid_from OR now() > v_promo.valid_until THEN
    RETURN jsonb_build_object('ok', false, 'error', 'expired');
  END IF;

  IF v_promo.applies_to_tier NOT IN ('both', p_tier) THEN
    RETURN jsonb_build_object('ok', false, 'error', 'wrong_tier');
  END IF;

  -- Per-user cap (count captured redemptions only)
  SELECT COUNT(*) INTO v_user_count
    FROM public.promo_redemptions
    WHERE promo_id = v_promo.id
      AND user_id = p_user_id;
  IF v_user_count >= v_promo.max_redemptions_per_user THEN
    RETURN jsonb_build_object('ok', false, 'error', 'already_used');
  END IF;

  -- Global cap
  IF v_promo.total_redemption_cap IS NOT NULL THEN
    SELECT COUNT(*) INTO v_global_count
      FROM public.promo_redemptions
      WHERE promo_id = v_promo.id;
    IF v_global_count >= v_promo.total_redemption_cap THEN
      RETURN jsonb_build_object('ok', false, 'error', 'cap_reached');
    END IF;
  END IF;

  -- Compute discount. Floor to integer paise (Razorpay only accepts integers).
  v_discounted := FLOOR(p_base_amount_paise::numeric * (100 - v_promo.discount_pct) / 100.0);

  RETURN jsonb_build_object(
    'ok',                      true,
    'promo_id',                v_promo.id,
    'code',                    v_promo.code::text,
    'discount_pct',            v_promo.discount_pct,
    'original_amount_paise',   p_base_amount_paise,
    'discounted_amount_paise', v_discounted
  );
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================
-- record_promo_redemption()
--   Called by processPayment() after the payment row is upserted.
--   Idempotent on payment_id (unique constraint).
--   Returns:
--     { ok: true, redemption_id }            on success
--     { ok: true, redemption_id, replayed }  if already recorded
--     { ok: false, error: 'race_lost' }      if another payment for
--                                              the same (promo,user) won
-- ============================================================
CREATE OR REPLACE FUNCTION public.record_promo_redemption(
  p_promo_id   uuid,
  p_user_id    uuid,
  p_payment_id uuid
) RETURNS jsonb AS $$
DECLARE
  v_existing_id uuid;
  v_promo       public.promo_codes;
  v_payment     public.payments;
  v_new_id      uuid;
BEGIN
  -- Replay protection: if this payment already has a redemption row, return it.
  SELECT id INTO v_existing_id
    FROM public.promo_redemptions
    WHERE payment_id = p_payment_id;
  IF FOUND THEN
    RETURN jsonb_build_object('ok', true, 'redemption_id', v_existing_id, 'replayed', true);
  END IF;

  SELECT * INTO v_promo FROM public.promo_codes WHERE id = p_promo_id;
  IF NOT FOUND THEN
    RETURN jsonb_build_object('ok', false, 'error', 'promo_not_found');
  END IF;

  SELECT * INTO v_payment FROM public.payments WHERE id = p_payment_id;
  IF NOT FOUND THEN
    RETURN jsonb_build_object('ok', false, 'error', 'payment_not_found');
  END IF;

  -- Per-user uniqueness handled by UNIQUE INDEX promo_redemptions_user_unique.
  -- Catch the race here so the caller can log a payment_alert.
  BEGIN
    INSERT INTO public.promo_redemptions (
      promo_id, user_id, payment_id,
      discount_pct, original_amount_paise, discounted_amount_paise
    ) VALUES (
      p_promo_id,
      p_user_id,
      p_payment_id,
      v_promo.discount_pct,
      -- Reverse-engineer the original from the payment amount + discount.
      -- This is a snapshot, not authoritative, but useful for reporting.
      ROUND(v_payment.amount_paise::numeric * 100.0 / (100 - v_promo.discount_pct))::int,
      v_payment.amount_paise
    ) RETURNING id INTO v_new_id;

    RETURN jsonb_build_object('ok', true, 'redemption_id', v_new_id);
  EXCEPTION WHEN unique_violation THEN
    RETURN jsonb_build_object('ok', false, 'error', 'race_lost');
  END;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- Seed: IGLOO50 — Phase 1 win-back blast.
--   50% off single-tier reels.
--   1 per user.
--   14-day window.
-- ============================================================
INSERT INTO public.promo_codes (
  code, discount_pct, applies_to_tier, valid_until, max_redemptions_per_user
) VALUES (
  'IGLOO50', 50, 'single', now() + interval '14 days', 1
)
ON CONFLICT (code) DO UPDATE SET
  discount_pct             = EXCLUDED.discount_pct,
  applies_to_tier          = EXCLUDED.applies_to_tier,
  valid_until              = EXCLUDED.valid_until,
  max_redemptions_per_user = EXCLUDED.max_redemptions_per_user,
  active                   = true;
