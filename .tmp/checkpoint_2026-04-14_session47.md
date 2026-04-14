# Session 47 Checkpoint — 2026-04-14

## Headline

Fixed the draft credit leak deferred from s46. Credit consumption now happens at pipeline launch instead of draft creation, so abandoned wizards no longer silently burn the user's credit. Nightly pg_cron cleans up >24h abandoned drafts. Kaushik's 1 pre-migration orphan refunded. All live on prod.

## What was done

### Plan
Approved plan at `C:\Users\vigne\.claude\plans\stateless-hatching-spindle.md`. Three decisions locked in with user: scheduler = Supabase pg_cron (not Fly cron), backfill scope = all users, UI toast deferred.

### Migration 0008 (`infra/supabase/migrations/0008_credit_redeem_at_launch.sql`)
Applied on Supabase SQL editor. Four parts:
- **A.** `redeem_credit(p_user_id, p_topic)` rewritten — still takes advisory lock, still checks balance ≥ 1 (raises `insufficient_credits`), still inserts draft run — but no longer inserts the `-1` consumption row.
- **B.** New `consume_credit_for_run(p_run_id uuid)` RPC. Advisory-locked on user_id. Idempotent: no-op if a `credits` row with `reason='run'` already exists for this run_id. Raises `insufficient_credits` if balance < 1, `run_not_found` if unknown run.
- **C.** `cleanup_orphan_drafts()` SQL function — updates all `status='draft' AND created_at < now() - 24h` runs to `status='rejected'`, `rejection_reason='abandoned_draft'`. Returns count. No refund needed (under new flow no credit was consumed).
- **D.** pg_cron job `cleanup_orphan_drafts_nightly` scheduled `0 3 * * *`. Returned job id `2`. pg_cron extension already enabled.

### Fly code (`execution/web_app.py`, commit `9c3efb7`)
- Added `InsufficientCreditsError` class + `consume_credit_for_run(run_id)` helper at module level (near `SlotAcquireError`).
- `try_acquire_slot()` calls `consume_credit_for_run(run_id)` **after** slot availability check, **before** the `UPDATE ... status='running'`. Idempotent RPC means promoting queued→running later re-calls cleanly.
- `mark_run_queued()` also calls `consume_credit_for_run(run_id)` before the UPDATE. Same idempotency guarantee covers the draft→queued→running path.
- Route `/api/pipeline/launch` catches `InsufficientCreditsError` from both `try_acquire_slot` and `mark_run_queued`, returns HTTP 402 with `{"error": "insufficient_credits"}`.
- Route `/api/pipeline/queue-status` catches the same, clears `queue_status` state, returns 402.

### Vercel code (`app/src/lib/process-payment.ts`, commit `9c3efb7`)
Deleted step 6 (lines 200-212 of pre-s47 file) — the `-1` consumption insert. Replaced with a 3-line comment explaining the new flow. Payment grant (step 4) unchanged. Rest of the function untouched.

### Backfill (one-shot, `.tmp/backfill_orphan_refunds_s47.sql`)
Dry-run returned `orphan_count = 1` — Kaushik's run `21ee1766` from 2026-04-13, consistent with prior audit. Transactional APPLY block executed in Supabase SQL editor. Result row: `orphans_found=1, credits_refunded=1, runs_rejected=1`. User committed the transaction. Net effect: one `credits` row with `delta=+1, reason='refund', note='abandoned_draft_backfill', run_id=21ee1766`, and run `21ee1766` status=rejected, rejection_reason=abandoned_draft. Idempotent via the `note` marker — re-running skips processed runs.

### Deployments
- Migration: user pasted 0008 into Supabase SQL editor, returned `schedule=2`.
- Git: commit `9c3efb7` pushed to `main`. Vercel auto-deploys from `app/` root dir.
- Fly: `deployment-01KP5E0FRBMX5WH8CCQ3DZFTM4` shipped, machine `857556f4470e78` healthy.

## What was NOT done

- **UI toast on `/create` for preserved drafts.** Deferred per user decision. Low priority — balance simply stays accurate, which is the correct UX.
- **End-to-end testing in prod.** No paid-path test run of the new flow. The full exercise (buy credit → open wizard → abandon → verify balance preserved → create second reel) would cost ~₹999 live. Deferred to natural beta traffic.
- **Monitoring the nightly cron.** First scheduled fire is 2026-04-15 03:00 UTC. Should be checked after first run via `SELECT * FROM cron.job_run_details WHERE jobid=2 ORDER BY start_time DESC LIMIT 5;` to confirm it executed.
- **Commit of s47 code changes and this checkpoint.** Commit `9c3efb7` covered the code + migration. This checkpoint file + CLAUDE.md update are a separate commit to come.
- **Loose working-tree files untouched (same as s46):** repo-root `package.json`/`package-lock.json`, `"Landing page/"` directory.

## Lessons

- **pg_cron beats Fly cron for SQL-only logic.** Original plan had a Python `cleanup_orphan_drafts.py` cron on Fly. User pushed for pg_cron — cleaner: no process, no extra deploy target, logic lives next to the data. Rule: when cleanup is expressible in pure SQL, schedule in the database.
- **Idempotency keys unlock safe deploy ordering.** Because `consume_credit_for_run` no-ops when a `credits` row already exists for the run_id, the deploy order (migration → Fly → Vercel) has no dangerous window. Old-flow in-flight drafts whose credit was already consumed simply don't double-charge when they reach launch under the new code. Worth patterning for future schema migrations that touch money.
- **Two transition points need the same side effect.** `try_acquire_slot` (draft→running direct) and `mark_run_queued` (draft→queued) both enter the "credit is owed" regime. Covering both was the trickiest part of the design — initially I considered consuming only at `try_acquire_slot`, but a queued-then-promoted run would have entered `queued` status without the credit consumed. Idempotent RPC from both callers is the right answer.
- **Transactional backfill with explicit COMMIT/ROLLBACK** saved a "run twice" fear — the `note='abandoned_draft_backfill'` marker plus `BEGIN;...COMMIT;` means user verified counts before persisting. Worth keeping as the default pattern for refund-style backfills.

## Current state of files

### New
- `infra/supabase/migrations/0008_credit_redeem_at_launch.sql` (committed `9c3efb7`)
- `.tmp/backfill_orphan_refunds_s47.sql` (one-shot, keep for reference)
- `.tmp/checkpoint_2026-04-14_session47.md` (this file)

### Modified + committed this session (commit `9c3efb7`)
- `execution/web_app.py` — `InsufficientCreditsError` class, `consume_credit_for_run()` helper, `try_acquire_slot()` and `mark_run_queued()` now call it, route handlers return 402 on insufficient credits.
- `app/src/lib/process-payment.ts` — step 6 (`-1` credits insert) removed.

### Modified, to be committed next (this commit)
- `CLAUDE.md` — "Current state" updated with s47 entry, latest-checkpoint pointer bumped.
- `.tmp/checkpoint_2026-04-14_session47.md` — this file.

### Still uncommitted (deliberate, same as s46)
- `package.json`, `package-lock.json` at repo root — stray.
- `"Landing page/"` directory — unknown provenance.

## Resume instructions for next session

1. Read `GOAL.md`.
2. Read this checkpoint.
3. Verify pg_cron executed overnight:
   ```sql
   SELECT jobid, runid, status, return_message, start_time, end_time
   FROM cron.job_run_details
   WHERE jobid = 2
   ORDER BY start_time DESC
   LIMIT 5;
   ```
   Any new `draft→rejected abandoned_draft` rows in `runs` with `created_at < now() - 24h` → cron working.
4. Verify new flow end-to-end by watching real beta traffic:
   - `SELECT id, user_id, status, created_at FROM runs WHERE created_at > now() - interval '48 hours' ORDER BY created_at DESC;`
   - Any `draft` rows older than 24h that don't have a matching `credits.reason='run'` row → credit correctly preserved.
   - Any `running` or `queued` rows — confirm each has exactly one `credits.reason='run', run_id=X` row.
5. Monitor `/admin/alerts` and `/admin/runs` from s46 — same watchlist.
6. Open items:
   - **UI toast** on `/create` when user returns to a preserved draft.
   - **Silent-failure plan** at `C:\Users\vigne\.claude\plans\jiggly-strolling-graham.md` (approved s45, not executed).
   - **CDN for landing assets** (~10MB).
   - **Supabase Storage cleanup cron** (30-day reel expiry).
   - **Email on deliver**.
   - **Razorpay refund API** + **Razorpay reconciliation cron**.
   - **`run_pipeline.py:251` CLI `--speed` fix**.

## API cost

No paid API calls in s47. Supabase migration + Fly deploy + git push only.

## Deployment state (end of session)

- Fly `igloo-studio`: `deployment-01KP5E0FRBMX5WH8CCQ3DZFTM4`, machine `857556f4470e78` healthy, 2026-04-14.
- Vercel `igloo-gate`: autodeployed from `9c3efb7`.
- Supabase: migration 0008 applied, pg_cron job id 2 scheduled for `0 3 * * *`.
