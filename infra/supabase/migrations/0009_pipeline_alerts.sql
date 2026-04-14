-- Pipeline failure alerts.
-- Inserted by execution/web_app.py when a DB write or side-effect fails
-- that would otherwise be silently swallowed (previously all `except: pass`).
-- Kinds of alerts:
--   'refund_failed'           auto-refund insert after pipeline failure lost
--   'mark_failed_update_lost' DB update to flip run->failed lost
--   'mark_queued_update_lost' DB update to flip run->queued lost; credit already consumed
--   'queue_sweep_failed'      _sweep_orphan_queued DB error
--   'queue_position_failed'   queue_position lookup DB error (shown 0 to user, which is misleading)
--   'api_retry_exhausted'     external API (TTS/Imagen/Kling/Music) failed after retries
--   'subprocess_timeout'      ffmpeg/sox subprocess hit its timeout
-- Keep the schema parallel to payment_alerts so the admin view can merge both.

CREATE TABLE IF NOT EXISTS public.pipeline_alerts (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id          UUID,
  user_id         UUID,
  kind            TEXT NOT NULL,
  error_message   TEXT,
  context         JSONB,                            -- extra: step name, api name, etc.
  resolved        BOOLEAN NOT NULL DEFAULT FALSE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX pipeline_alerts_resolved_idx ON public.pipeline_alerts (resolved) WHERE NOT resolved;
CREATE INDEX pipeline_alerts_created_at_idx ON public.pipeline_alerts (created_at DESC);
CREATE INDEX pipeline_alerts_run_id_idx ON public.pipeline_alerts (run_id) WHERE run_id IS NOT NULL;

-- NOTE: no unique index on (run_id) WHERE reason='refund' — existing data
-- has multiple manual refund rows for run 21ee1766 (s46 + s47 backfills)
-- that would conflict. Idempotency is enforced in code instead (see
-- mark_run_failed in execution/web_app.py: it checks for an existing
-- auto-refund row before inserting).
