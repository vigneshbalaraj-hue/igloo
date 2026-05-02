-- Migration 0011: Email drip system.
--
-- Adds the table that records every drip email we send (idempotency),
-- per-user unsubscribe flag + token, second promo (WELCOME25 for the
-- new-signup T+7 last-chance email), and pg_cron schedule for the hourly
-- sweep that fires due-but-not-yet-sent emails via an internal HTTP
-- endpoint.
--
-- Reads existing tables: users, runs, payments.
-- New table: sent_emails. New columns on users: email_unsubscribed,
-- unsubscribe_token.
--
-- Idempotent: safe to re-run. The pg_cron job is unscheduled+rescheduled.

-- ============================================================
-- A. sent_emails
--   One row per (user, email_type) we successfully attempted to send.
--   Insert BEFORE calling Resend so concurrent webhook + cron firings
--   collapse on the unique index. status tracks the resend outcome.
-- ============================================================
CREATE TABLE IF NOT EXISTS public.sent_emails (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  email_type        text NOT NULL CHECK (email_type IN (
                      'winback_d0',  'winback_d3',  'winback_d7',
                      'welcome_t0',  'onboard_t1',  'onboard_t3', 'onboard_t7'
                    )),
  status            text NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'sent', 'failed', 'skipped')),
  resend_message_id text,
  error_message     text,
  sent_at           timestamptz,
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS sent_emails_user_type_unique
  ON public.sent_emails (user_id, email_type);

CREATE INDEX IF NOT EXISTS sent_emails_status_idx     ON public.sent_emails (status);
CREATE INDEX IF NOT EXISTS sent_emails_created_at_idx ON public.sent_emails (created_at desc);

ALTER TABLE public.sent_emails ENABLE ROW LEVEL SECURITY;

DROP TRIGGER IF EXISTS sent_emails_set_updated_at ON public.sent_emails;
CREATE TRIGGER sent_emails_set_updated_at
  BEFORE UPDATE ON public.sent_emails
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ============================================================
-- B. users — unsubscribe support
--   - email_unsubscribed: hard gate; checked before every send
--   - unsubscribe_token: random per-user UUID for one-click unsubscribe
--     URLs (igloo.video/unsubscribe/<token>). Pre-populated for existing
--     rows via the UPDATE below.
-- ============================================================
ALTER TABLE public.users
  ADD COLUMN IF NOT EXISTS email_unsubscribed boolean NOT NULL DEFAULT false;

ALTER TABLE public.users
  ADD COLUMN IF NOT EXISTS unsubscribe_token uuid NOT NULL DEFAULT gen_random_uuid();

-- Pre-populate tokens for any rows that existed before the column was added.
-- (DEFAULT only fires on INSERT — pre-existing rows would have NULL without this.
--  The NOT NULL above protects the future; this UPDATE backfills the past.)
UPDATE public.users
   SET unsubscribe_token = gen_random_uuid()
 WHERE unsubscribe_token IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS users_unsubscribe_token_unique
  ON public.users (unsubscribe_token);

-- first_name from Clerk, used in email personalization. Nullable —
-- when missing we derive a first name from the email local-part.
ALTER TABLE public.users
  ADD COLUMN IF NOT EXISTS first_name text;

-- ============================================================
-- C. WELCOME25 promo seed (relies on migration 0010 having run first)
--   25% off, single-tier, 1-per-user, 30-day window.
--   Gets handed out in the new-signup T+7 last-chance email.
-- ============================================================
INSERT INTO public.promo_codes (
  code, discount_pct, applies_to_tier, valid_until, max_redemptions_per_user
) VALUES (
  'WELCOME25', 25, 'single', now() + interval '30 days', 1
)
ON CONFLICT (code) DO UPDATE SET
  discount_pct             = EXCLUDED.discount_pct,
  applies_to_tier          = EXCLUDED.applies_to_tier,
  valid_until              = EXCLUDED.valid_until,
  max_redemptions_per_user = EXCLUDED.max_redemptions_per_user,
  active                   = true;

-- ============================================================
-- D. pg_cron sweep
--   Fires every hour. Calls the internal Next.js endpoint which
--   queries Supabase, finds users due for each drip type, and
--   dispatches via Resend. The endpoint is idempotent on
--   sent_emails (user_id, email_type), so cron retries are safe.
--
--   We use pg_net for the HTTP call (Supabase pre-enables it).
--   The endpoint requires a shared secret in the X-Internal-Secret
--   header — set both INTERNAL_DRIP_SECRET in Vercel env and the
--   matching value in Supabase via:
--     SELECT vault.create_secret('paste-secret-here', 'internal_drip_secret');
--   Or, simpler for now, hardcode it in this migration after deploying
--   (and rotate before going public). See deploy notes.
-- ============================================================
CREATE EXTENSION IF NOT EXISTS pg_cron;
CREATE EXTENSION IF NOT EXISTS pg_net;

-- The sweep function pg_cron will call. Keeping the URL + secret as
-- function parameters — pass them in the cron.schedule call so the
-- secret isn't stored in the function body itself.
CREATE OR REPLACE FUNCTION public.email_drip_sweep_call(
  p_endpoint_url text,
  p_secret       text
) RETURNS bigint AS $$
DECLARE
  v_request_id bigint;
BEGIN
  SELECT net.http_post(
    url     := p_endpoint_url,
    headers := jsonb_build_object(
      'Content-Type',       'application/json',
      'X-Internal-Secret',  p_secret
    ),
    body    := jsonb_build_object('source', 'pg_cron'),
    timeout_milliseconds := 60000
  ) INTO v_request_id;
  RETURN v_request_id;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
  PERFORM cron.unschedule('email_drip_hourly');
EXCEPTION WHEN OTHERS THEN
  NULL;
END;
$$;

-- The cron job itself is registered via a separate one-time SQL run
-- after the user has set INTERNAL_DRIP_SECRET in Vercel. Template:
--
--   SELECT cron.schedule(
--     'email_drip_hourly',
--     '7 * * * *',  -- :07 every hour
--     $$SELECT public.email_drip_sweep_call(
--         'https://igloo.video/api/internal/send-drip',
--         '<paste INTERNAL_DRIP_SECRET value here>'
--       );$$
--   );
--
-- Why we don't auto-schedule in this migration: the secret would have to
-- be hardcoded in the migration file (which is committed to git). Better
-- to register the cron job from the Supabase SQL Editor as a one-shot
-- after the secret is in Vercel. Documented in the deploy notes.
