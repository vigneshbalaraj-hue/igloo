# Agent Instructions

> This file is mirrored across CLAUDE.md, AGENTS.md, and GEMINI.md so the same instructions load in any AI environment.

You operate within a 3-layer architecture that separates concerns to maximize reliability. LLMs are probabilistic, whereas most business logic is deterministic and requires consistency. This system fixes that mismatch.

## The 3-Layer Architecture

**Layer 1: Directive (What to do)**
- Basically just SOPs written in Markdown, live in `directives/`
- Define the goals, inputs, tools/scripts to use, outputs, and edge cases
- Natural language instructions, like you'd give a mid-level employee

**Layer 2: Orchestration (Decision making)**
- This is you. Your job: intelligent routing.
- Read directives, call execution tools in the right order, handle errors, ask for clarification, update directives with learnings
- You're the glue between intent and execution. E.g you don't try scraping websites yourself—you read `directives/scrape_website.md` and come up with inputs/outputs and then run `execution/scrape_single_site.py`

**Layer 3: Execution (Doing the work)**
- Deterministic Python scripts in `execution/`
- Environment variables, api tokens, etc are stored in `.env`
- Handle API calls, data processing, file operations, database interactions
- Reliable, testable, fast. Use scripts instead of manual work.

**Why this works:** if you do everything yourself, errors compound. 90% accuracy per step = 59% success over 5 steps. The solution is push complexity into deterministic code. That way you just focus on decision-making.

## Operating Principles

**0. Approval before non-trivial decisions (NON-NEGOTIABLE)**
Never make a decision with non-trivial ramifications until you (a) fully understand the ramifications and (b) get explicit user approval. "Non-trivial" means: anything that changes the architecture, costs API credits, takes >10 min of compute, picks one approach over another with different tradeoffs, or commits the user to a path that's expensive to reverse. When you spot a fork in the road, stop and surface the tradeoffs — do not pick the path yourself just because it looks structurally cleaner.

**Canonical example (s31/s32):** Faced with a Fly OOM, Claude refactored `assemble_video.py:build_xfade_concat` to a pairwise left-fold instead of bumping to `shared-cpu-2x` + 4gb (~$6/mo). The refactor was structurally correct but introduced a 2-3× wall-time penalty that compounded with Fly's noisy-neighbor steal into a ~2-hour assembly time (vs ~5-10 min for single-pass on a bigger box). The user pushed back, the pairwise approach was reverted in s32, and ~1.5h of user time was wasted on the limping run. Rule of thumb derived from this: **on bounded-N workloads (N capped by product constraints, not user input), default to vertical scaling over algorithmic refactor, and always surface the tradeoff before picking either.**

**1. Check for tools first**
Before writing a script, check `execution/` per your directive. Only create new scripts if none exist.

**2. Self-anneal when things break**
- Read error message and stack trace
- Fix the script and test it again (unless it uses paid tokens/credits/etc—in which case you check w user first)
- Update the directive with what you learned (API limits, timing, edge cases)
- Example: you hit an API rate limit → you then look into API → find a batch endpoint that would fix → rewrite script to accommodate → test → update directive.

**3. Update directives as you learn**
Directives are living documents. When you discover API constraints, better approaches, common errors, or timing expectations—update the directive. But don't create or overwrite directives without asking unless explicitly told to. Directives are your instruction set and must be preserved (and improved upon over time, not extemporaneously used and then discarded).

## Self-annealing loop

Errors are learning opportunities. When something breaks:
1. Fix it
2. Update the tool
3. Test tool, make sure it works
4. Update directive to include new flow
5. System is now stronger

## File Organization

**Deliverables vs Intermediates:**
- **Deliverables**: Google Sheets, Google Slides, or other cloud-based outputs that the user can access
- **Intermediates**: Temporary files needed during processing

**Directory structure:**
- `.tmp/` - All intermediate files (dossiers, scraped data, temp exports). Never commit, always regenerated.
- `execution/` - Python scripts (the deterministic tools)
- `directives/` - SOPs in Markdown (the instruction set)
- `.env` - Environment variables and API keys
- `credentials.json`, `token.json` - Google OAuth credentials (required files, in `.gitignore`)

**Key principle:** Local files are only for processing. Deliverables live in cloud services (Google Sheets, Slides, etc.) where the user can access them. Everything in `.tmp/` can be deleted and regenerated.

## Context Window Management

When the context window reaches ~85-90% capacity, you MUST:

1. **Automatically create a checkpoint file** at `.tmp/checkpoint_YYYY-MM-DD_sessionN.md` with:
   - What was done (with technical details, file paths, API specifics)
   - What was NOT done (prioritized next steps)
   - Lessons learned
   - Current state of files (new, modified, reverted)
   - Key technical notes needed to resume (API auth, endpoints, gotchas)
   - Resume instructions (step-by-step for the next session)
   - Cumulative API cost summary
2. **Prompt the user** to open a new session and read the latest checkpoint file to continue
3. Do NOT wait for the user to ask — do this proactively when context is running low

The checkpoint is the handoff document. It must contain everything a fresh session needs to pick up exactly where this one left off, with zero context loss.

## Summary

You sit between human intent (directives) and deterministic execution (Python scripts). Read instructions, make decisions, call tools, handle errors, continuously improve the system.

Be pragmatic. Be reliable. Self-anneal.

## Overall product goal

**ALWAYS READ [GOAL.md](GOAL.md) AT THE START OF EVERY SESSION.** It is the north-star document for what Igloo is, the canonical customer journey, product boundaries (landing vs gate vs studio), non-negotiables, and anti-drift guardrails. Previous sessions drifted into rebuilding the Flask wizard in Next.js and into DNS theater; GOAL.md exists to prevent that. If a task you're about to do doesn't serve one of the 7 customer-journey steps listed there, stop and ask.

## Current state (Igloo launch)

**Latest checkpoint:** `.tmp/checkpoint_2026-04-14_session49.md` — start here. (Predecessors: s48, s47, s46, s45, s44, s43, s42, s41, s40, s39, s38, s37, s36, s35, s34, s33, s32, s31.)

- **Session 49 — Voice ID leakage fix.** Migraine reel shipped female anchor + male voice despite wizard showing 3 female candidates. Root cause: `ASSEMBLY_PROMPT` explicitly strips `elevenlabs_voice_id`, `api_save_script` can't propagate, `generate_voiceover.py` falls back to stale `ELEVENLABS_VOICE_ID` env that's shared across runs on Fly (select_voice.update_env writes persistent `.env` on disk). Four fixes shipped (commit `e0e6b5b`, Fly deployed): `api_assemble_script` + `api_edit_script` re-inject voice_id after Gemini returns; `generate_voiceover.py` prefers script voice_id over env and hard-fails if neither present; `run_pipeline._skip_step1` now checks script's baked voice_id instead of env. Script JSON is now single source of truth for voice_id. **Deferred** (memory `project_voice_id_env_cleanup.md`): remove `select_voice.update_env("ELEVENLABS_VOICE_ID", ...)` entirely — redundant plumbing from solo-CLI era. Note: Gemini at `temperature=0.9` is probabilistic; dense topics (dabbawalas, migraines) pass ~50% via retry-loop luck, not structural reliability.

- **Session 48 — Silent-failure hardening + beta copy.** Plan `~/.claude/plans/harmonic-wibbling-river.md` (phases A/B/C/E shipped, D deferred). Five `except: pass` sites in `execution/web_app.py` replaced with `log_pipeline_alert()` into new `pipeline_alerts` table (migration 0009, parallels 0007). Auto-refund now 3-attempt retry + in-code idempotency (`note like 'auto-refund:%'`; no unique index because run `21ee1766` has 2 legit backfill refund rows). New `execution/http_retry.py` wraps ElevenLabs TTS/Music, Imagen, Kling — 3 attempts, typed `ERROR_CODE: {TTS,IMAGEN,KLING,MUSIC}_FAILED`. Subprocess timeouts: 600s assemble / 60s ffprobe / 120s slice, emit `ERROR_CODE: FFMPEG_TIMEOUT`. New `app/src/lib/fetch-timeout.ts` + AbortController on all create/profile fetches (15–30s). `/admin/alerts` merges payment + pipeline alerts. Beta copy: reframed "final quality check" → "During our beta, we hand-check every reel before it ships to you." on `/runs/[id]` + studio complete view. Commits `adc973f`, `6e975b8`. **Open gap:** Fly pipeline subprocess stdout is buffered so logs go silent during runs — fix next session via `flyctl secrets set PYTHONUNBUFFERED=1 -a igloo-studio`.

- **Session 47 — Draft credit leak fixed.** Moved credit consumption from draft-creation to pipeline launch. Migration 0008 (`0008_credit_redeem_at_launch.sql`) rewrites `redeem_credit()` to skip deduction, adds idempotent `consume_credit_for_run(p_run_id)` RPC called from `execution/web_app.py` `try_acquire_slot()` + `mark_run_queued()`, adds `cleanup_orphan_drafts()` SQL function scheduled nightly at 03:00 UTC via pg_cron (job id 2, name `cleanup_orphan_drafts_nightly`). `process-payment.ts` no longer inserts the `-1` credits row (step 6 removed). New typed `InsufficientCreditsError` surfaces as HTTP 402 from `/api/pipeline/launch` + `/api/pipeline/queue-status`. Backfilled 1 pre-migration orphan (Kaushik, run `21ee1766`) via transactional SQL — `+1 refund` row with `note='abandoned_draft_backfill'`, run marked rejected. Commit `9c3efb7`.

- **Session 46 — Assembly crash fix + short-reel floor + alignment resilience.** Kaushik's 04-13 assembly failures traced to 3 bugs. Fixes shipped: (A) deleted dead `scenes_flat` block in `assemble_video.py`; (B) 3-pass alignment in `extract_word_timestamps.py` (exact → fuzzy difflib ≥0.8 → interpolate, 2-scene budget) raising typed `AlignmentQualityError`/`AlignmentHardError`; (C) `MIN_DURATION_1X=36` hard floor validator in `prompt_bank.py` (30s delivered at 1.2×); (D) 4-attempt script retry loop with attempts 3-4 escalating to Pro via new `force_model` param in `gemini_client.py`; (D1) typed `ERROR_CODE:` (`SCRIPT_UNDER_MIN`/`SCRIPT_OVER_MAX`/`ALIGNMENT_POOR`/`ALIGNMENT_FAILED`) captured by `web_app.py` into `rejection_reason`, rendered as tailored "Try Another Topic" CTA on `/runs/[id]`; alignment auto-retry 2× (rewinds to step 2 on step 3 alignment failure). Also shipped s45 backlog: committed 0007 migration, `logPaymentAlert()`, `/admin/alerts`. Refunded Kaushik +4 credits. Commits `ca93af3`, `d883f07`.
- **Session 45 — Payment alerts + Clerk test/live fix + Kling rotation.** Back-filled Kaushik's missing Razorpay payment (`pay_ScOr05QLEdnl55`) to prevent webhook double-grant. Built `payment_alerts` table + `logPaymentAlert()` in `process-payment.ts` + `/admin/alerts` page (all shipped in s46). Fixed Kaushik's empty `/profile`: root cause was his `users.clerk_user_id` pointing at test Clerk instance while production uses live keys. Updated his row + switched `app/.env.local` to live Clerk keys so local dev matches prod. Rotated Kling API keys in `.env`, deployed to Fly. Full silent-failure audit saved at `C:\Users\vigne\.claude\plans\jiggly-strolling-graham.md` (approved, not executed).
- **Session 44 — Payment retry resilience + landing reels.** `withRetry`/`supabaseRetry` helpers in `supabase-server.ts` (3 attempts, exponential backoff). All 5 Supabase calls in `processPayment` now retry. "Retry — your payment is safe" button on `/create` after trigger failure. Progress screen copy fixed. 4 new compressed example reels added to landing marquee (8 total). Hard duration ceiling issue diagnosed but not yet fixed (awaiting decision on approach).
- **Session 43 — Voice preview step + UX fixes.** New wizard step 4 (Voice): ElevenLabs library search + Gemini ranking, user hears top 3 and picks. Pipeline starts from step 2 (voice pre-selected). Anchor eye contact enforced in prompts. Retry temp 0.9→0.5. Queue timeout 30min→4h. `/create` dynamic topic label. `/runs/[id]` back link. V2 finalize edit UX wishlisted.
- **Session 42 — B2 + D2 + beta cap.** B2: voice gender mismatch fix (prompt tightening + runtime cross-check in `select_voice.py`). D2: post-reel feedback (`run_feedback` table, 5-star form on `/runs/[id]`, badge on `/profile`, `/admin/feedback`). Beta cap: 30-customer limit on `/create`, waitlisted users see "Beta is full", `/admin/waitlist` page. Migration 0006 deployed.
- **Session 41 — B3 Gemini fallback + domain consolidation.** Unified `call_gemini` into `execution/gemini_client.py` (flash 6 retries → pro 3 retries). Auto-refund credit on pipeline failure. Consolidated all domains to `igloo.video` (www/app redirect). Razorpay webhook updated.
- **Session 40 — B1+C1 deployed to Fly.** B1: 50s hard limit (at 1.2x), `MAX_DURATION_1X=60`, 114-word ceiling, min 5 scenes. C1: dynamic `kling_duration` 5/10 for b-roll based on `scene_duration` (set in `extract_word_timestamps.py`). Split-clips prompt removed. Kling v2-1 supports `"5"` or `"10"` only, 12 credits/s.
- **Session 38 — P0 Block A.** Full narration captions (was keyword-only). Reconnect-to-run verified working.
- **Session 37 — Clerk production + /profile page.** Migrated Clerk to `pk_live_`/`sk_live_` keys, added 6 DNS records in Namecheap, set up Google OAuth via GCP. Built `/profile` page with credit balance, transaction log, reel history (30-day download expiry), payment history. Navbar updated.
- **Session 35–36 — 2-tier credits system, landing page merged, domains unified.**
- **Production domains (consolidated to igloo.video):**
  - `igloo.video` → Vercel project `igloo-gate` (root dir: `app/`) — **canonical, all traffic here**
  - `www.igloo.video` → 308 redirect to `igloo.video` (via next.config.ts)
  - `app.igloo.video` → 308 redirect to `igloo.video` (via next.config.ts)
  - Studio: `igloo-studio.fly.dev` → Fly `performance-2x` (2 dedicated vCPUs, 4gb)
  - Fly `IGLOO_APP_URL` = `https://igloo.video`
- **Git auto-deploy active.** igloo-gate connected to `vigneshbalaraj-hue/igloo`, root dir `app/`. Push to main triggers deploy. **Never use `vercel --prod` CLI** — it skips large binary files.
- **Razorpay is LIVE MODE and working.** Keys: `rzp_live_Sbg199N6mjjpuR`. International Cards enabled. Webhook: `https://igloo.video/api/razorpay/webhook`.
- **2-tier pricing live.** Single (₹999, 1 credit) / Double (₹1,249, 2 credits). Shared constants in `app/src/lib/pricing.ts`. Credit redemption via Postgres `redeem_credit()` function. `/create` shows tier selector + credit balance.
- **Landing page in Next.js app.** CSS scoped under `.landing-theme`. Old Vite `igloo` project is orphaned (kept intentionally). Clerk middleware skips video extensions (`proxy.ts` matcher).
- **Admin access:** Clerk public metadata `{ "role": "admin" }` + custom session token `{ "metadata": "{{user.public_metadata}}" }`. `/admin` shows running/queued/awaiting_review runs. `/admin/feedback` shows customer ratings. `/admin/waitlist` shows users with no payments.
- **Beta cap:** 30 paying customers, then `/create` shows waitlist message. Existing customers bypass cap. Constant `BETA_CAP=30` in `app/src/app/api/beta-status/route.ts`.
- **Clerk is PRODUCTION.** `pk_live_`/`sk_live_` keys on Vercel. DNS records on Namecheap. Google OAuth via GCP (`clerk.igloo.video/v1/oauth_callback`). Session token template set in Clerk dashboard. Dev badge gone.
- **`/profile` page live.** Credit balance + transaction log, reel history (30-day download expiry, client-side), payment history. API routes: `/api/runs`, `/api/payments`, `/api/credits/history`. Navbar has "Profile" link.
- **Vercel env vars:** Never use `echo` to pipe values — always `printf` (no trailing newline).
- **flyctl in bash:** `~/.fly/bin/flyctl.exe`. Deploy: `~/.fly/bin/flyctl.exe deploy` from repo root. **Never** `fly scale count 2`.
- **Deferred:** Phase D of s48 plan (persist queued-run launch params to `runs.launch_params` JSONB — only needed if Fly restarts start stranding users), `PYTHONUNBUFFERED=1` Fly secret (pipeline subprocess logs are invisible during runs), CDN for landing assets (~10MB after s44 compression), Supabase Storage cleanup cron (30-day expiry), email on deliver, Razorpay refund API, `run_pipeline.py:251` CLI `--speed` fix, Razorpay reconciliation cron.
- **Stack:** Next 16 + React 19 + Tailwind 4 + Clerk 7. Use `./node_modules/.bin/tsc` not `npx tsc`.
