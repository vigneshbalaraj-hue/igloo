-- Migration 0012: Notify admins when a reel hits awaiting_review.
--
-- AFTER UPDATE trigger on public.runs fires the moment a row's status
-- transitions into 'awaiting_review' from anything else. The trigger
-- calls /api/internal/notify-awaiting-review via pg_net.http_post.
-- The Next.js endpoint sends an email to the ADMIN_NOTIFICATION_EMAILS
-- list (Vercel env var) and stamps awaiting_review_notified_at to
-- prevent duplicate sends if the trigger fires twice (it shouldn't,
-- but defense in depth).
--
-- Secret handling: the shared secret (same as INTERNAL_DRIP_SECRET) is
-- read from a database-level config parameter `app.internal_drip_secret`.
-- That parameter is NOT set by this migration — see deploy notes for the
-- one-shot ALTER DATABASE command to set it without committing the
-- secret to git.
--
-- Idempotent: safe to re-run. The trigger and function are dropped and
-- recreated; the column add is IF NOT EXISTS.

-- ============================================================
-- A. New column: awaiting_review_notified_at
--   Set to now() once the notification has been dispatched.
--   The endpoint short-circuits if it's already non-null (defensive).
-- ============================================================
ALTER TABLE public.runs
  ADD COLUMN IF NOT EXISTS awaiting_review_notified_at timestamptz;

-- ============================================================
-- B. Trigger function
--   Fires only on the specific transition into 'awaiting_review'.
--   Reads the shared secret from a session/database setting so we
--   don't have to hardcode it in the function body (which would put
--   it in git via this migration).
-- ============================================================
CREATE OR REPLACE FUNCTION public.notify_awaiting_review_trigger()
RETURNS TRIGGER AS $$
DECLARE
  v_secret text;
  v_endpoint text := 'https://igloo.video/api/internal/notify-awaiting-review';
BEGIN
  -- Only fire on transitions INTO awaiting_review (not updates while in it).
  IF NOT (TG_OP = 'UPDATE'
          AND OLD.status IS DISTINCT FROM NEW.status
          AND NEW.status = 'awaiting_review') THEN
    RETURN NEW;
  END IF;

  -- Bail if a notification has already been sent for this run.
  IF NEW.awaiting_review_notified_at IS NOT NULL THEN
    RETURN NEW;
  END IF;

  -- Read shared secret. The 'true' arg = "missing_ok" — return NULL
  -- if not set, so we don't error out the UPDATE that triggered us.
  v_secret := current_setting('app.internal_drip_secret', true);
  IF v_secret IS NULL OR length(v_secret) = 0 THEN
    RAISE WARNING '[notify_awaiting_review] app.internal_drip_secret is not configured; skipping HTTP call';
    RETURN NEW;
  END IF;

  -- Fire-and-forget HTTP call. pg_net is async — does not block the
  -- UPDATE. If the endpoint is down, pg_net retries on its own; we'll
  -- see the request id in net._http_response.
  PERFORM net.http_post(
    url     := v_endpoint,
    headers := jsonb_build_object(
      'Content-Type',      'application/json',
      'X-Internal-Secret', v_secret
    ),
    body    := jsonb_build_object('run_id', NEW.id::text),
    timeout_milliseconds := 30000
  );

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- C. Register the trigger.
--   AFTER UPDATE OF status — only re-evaluates when the column we care
--   about changes (skips noise from script/qc_notes/etc updates).
-- ============================================================
DROP TRIGGER IF EXISTS runs_notify_awaiting_review ON public.runs;
CREATE TRIGGER runs_notify_awaiting_review
  AFTER UPDATE OF status ON public.runs
  FOR EACH ROW
  EXECUTE FUNCTION public.notify_awaiting_review_trigger();
