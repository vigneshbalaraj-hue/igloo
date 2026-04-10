-- 0004_add_draft_status.sql
--
-- Add 'draft' to the runs.status enum.
--
-- Background: before this migration, a run was inserted at payment-capture time
-- with status='queued', and the Next.js app immediately fired a headless Modal
-- worker that ran the full pipeline from a bare topic string. That flow threw
-- away the interactive Flask wizard in execution/web_app.py.
--
-- New flow: payment capture creates the run with status='draft'. The user is
-- then redirected to the Flask studio (hosted on Modal) where they go through
-- the theme → narration → character → script wizard. When they click
-- "Create My Reel", the studio atomically promotes the run to 'running' (or
-- 'queued' if ≥ IGLOO_MAX_PIPELINES pipelines are already running).
--
-- Status transitions:
--   draft           → queued (wizard done, waiting for pipeline slot)
--   draft           → running (wizard done, slot available)
--   queued          → running (slot freed, atomic UPDATE in Flask)
--   running         → awaiting_review (pipeline finished, MP4 uploaded)
--   running         → failed (pipeline error)
--   awaiting_review → delivered (admin approved)
--   awaiting_review → rejected (admin rejected + credit refund)
--
-- Idempotent: DROP IF EXISTS then re-add.

alter table public.runs drop constraint if exists runs_status_check;

alter table public.runs add constraint runs_status_check
  check (status in (
    'draft',
    'queued',
    'running',
    'awaiting_review',
    'delivered',
    'rejected',
    'failed'
  ));
