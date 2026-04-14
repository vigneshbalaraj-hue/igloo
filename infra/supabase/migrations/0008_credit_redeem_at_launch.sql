-- Migration 0008: Fix draft credit leak.
--
-- Problem: redeem_credit() and process-payment.ts both consume a credit at
-- draft-creation time, before the pipeline actually launches. If the user
-- abandons the wizard, the credit is lost. Evidence: run 21ee1766 on
-- 2026-04-13 (Kaushik, abandoned draft, credit consumed, no reel).
--
-- Fix: consume credit at pipeline launch instead of at draft creation.
--   A. redeem_credit() no longer inserts the -1 consumption row.
--   B. New consume_credit_for_run(run_id) RPC is called by execution/web_app.py
--      at the draft -> queued / draft -> running transition. Idempotent.
--   C. cleanup_orphan_drafts() nightly job rejects >24h-old drafts.
--      (No refund needed under new flow; credit was never consumed.)
--   D. pg_cron schedules cleanup nightly at 03:00 UTC.
--
-- Backfill for pre-migration orphans (already-consumed drafts) is done
-- separately via one-shot SQL in the session-47 checkpoint — not part of
-- this migration.

-- A. Replace redeem_credit(): balance check + draft run insert, no deduction.
CREATE OR REPLACE FUNCTION public.redeem_credit(p_user_id uuid, p_topic text)
RETURNS uuid AS $$
DECLARE
  v_balance int;
  v_run_id uuid;
BEGIN
  -- Advisory lock keyed on user to serialize concurrent wizard opens.
  PERFORM pg_advisory_xact_lock(hashtext(p_user_id::text));

  SELECT COALESCE(balance, 0) INTO v_balance
    FROM public.user_balances WHERE user_id = p_user_id;

  IF v_balance IS NULL OR v_balance < 1 THEN
    RAISE EXCEPTION 'insufficient_credits';
  END IF;

  INSERT INTO public.runs (user_id, status, prompt)
    VALUES (p_user_id, 'draft', p_topic)
    RETURNING id INTO v_run_id;

  -- No credit deduction here. Consumption happens at pipeline launch
  -- via consume_credit_for_run().

  RETURN v_run_id;
END;
$$ LANGUAGE plpgsql;

-- B. Idempotent credit consumption called by the Flask studio at launch.
-- Raises 'insufficient_credits' if balance < 1. No-op if a credits row
-- with reason='run' already exists for this run_id (safe to call twice —
-- e.g. draft->queued then queued->running both invoke this).
CREATE OR REPLACE FUNCTION public.consume_credit_for_run(p_run_id uuid)
RETURNS void AS $$
DECLARE
  v_user_id uuid;
  v_existing int;
  v_balance int;
BEGIN
  SELECT user_id INTO v_user_id
    FROM public.runs WHERE id = p_run_id;

  IF v_user_id IS NULL THEN
    RAISE EXCEPTION 'run_not_found';
  END IF;

  -- Serialize concurrent consumption attempts for the same user.
  PERFORM pg_advisory_xact_lock(hashtext(v_user_id::text));

  -- Idempotency: if a consumption row already exists for this run, no-op.
  SELECT COUNT(*) INTO v_existing
    FROM public.credits
    WHERE run_id = p_run_id AND reason = 'run';
  IF v_existing > 0 THEN
    RETURN;
  END IF;

  SELECT COALESCE(balance, 0) INTO v_balance
    FROM public.user_balances WHERE user_id = v_user_id;
  IF v_balance IS NULL OR v_balance < 1 THEN
    RAISE EXCEPTION 'insufficient_credits';
  END IF;

  INSERT INTO public.credits (user_id, delta, reason, run_id, note)
    VALUES (v_user_id, -1, 'run', p_run_id, 'pipeline launch');
END;
$$ LANGUAGE plpgsql;

-- C. Nightly orphan-draft cleanup. Any draft older than 24h is treated
-- as abandoned. Under the new flow no credit was consumed, so nothing
-- to refund — just mark the run rejected so admin views stay clean.
CREATE OR REPLACE FUNCTION public.cleanup_orphan_drafts()
RETURNS int AS $$
DECLARE
  v_count int;
BEGIN
  WITH updated AS (
    UPDATE public.runs
      SET status = 'rejected',
          rejection_reason = 'abandoned_draft'
      WHERE status = 'draft'
        AND created_at < (now() - interval '24 hours')
      RETURNING id
  )
  SELECT COUNT(*) INTO v_count FROM updated;
  RETURN v_count;
END;
$$ LANGUAGE plpgsql;

-- D. Schedule via pg_cron. Supabase enables pg_cron via Database ->
-- Extensions; if this CREATE EXTENSION fails, enable the extension in
-- the dashboard and re-run the cron.schedule call.
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Unschedule any prior job with the same name (idempotent re-apply).
DO $$
BEGIN
  PERFORM cron.unschedule('cleanup_orphan_drafts_nightly');
EXCEPTION WHEN OTHERS THEN
  NULL;
END;
$$;

SELECT cron.schedule(
  'cleanup_orphan_drafts_nightly',
  '0 3 * * *',
  $$SELECT public.cleanup_orphan_drafts();$$
);
