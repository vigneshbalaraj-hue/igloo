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

**Latest checkpoint:** `.tmp/checkpoint_2026-04-11_session42.md` — start here. (Predecessors: s41, s40, s39, s38, s37, s36, s35, s34, s33, s32, s31.)

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
- **Deferred:** CDN for landing assets (~21MB), Supabase Storage cleanup cron (30-day expiry), email on deliver, Razorpay refund API, `run_pipeline.py:251` CLI `--speed` fix.
- **Stack:** Next 16 + React 19 + Tailwind 4 + Clerk 7. Use `./node_modules/.bin/tsc` not `npx tsc`.
