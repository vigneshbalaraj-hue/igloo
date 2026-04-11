# Igloo — Overall Goal

> **This document exists because the assistant has drifted before.** Sessions 24–25 lost the plot: building DNS plumbing for a Next.js page that was quietly re-implementing a Flask wizard that already existed. Read this file at the start of every session before touching code. If what you're about to do doesn't serve the product described below, stop and ask.

## What Igloo is (one sentence)

**Igloo turns a paid topic into a finished, reviewed short-form vertical video without the customer ever touching a video editor.**

## The product in one paragraph

A creator visits `igloo.video`, clicks "Create your first reel", pays the sticker price **$14.99** (strikethrough $19.99), which is charged in INR equivalent (~₹1,249) via Razorpay on `app.igloo.video`, then is handed off to a guided wizard (Flask, hosted on Modal) where they pick a theme, approve the AI-generated narration, pick an anchor character, approve the full script, and hit go. The backend runs the 9-step reel pipeline (script → voice → timestamps → slicing → images → video → music → assembly) which produces a final vertical MP4. The MP4 goes to Supabase Storage and sits in an admin review queue. The operator (the user of this codebase) watches the reel, either **delivers** it to the customer (who downloads via a signed URL and eventually gets an email) or **rejects** it with a +1 credit refund. No self-serve download; every reel is human-QC'd before the customer sees it.

## The customer journey (canonical flow)

```
1. Discover      → igloo.video (landing page)
2. Sign up       → igloo.video/sign-up (Clerk)
3. Pay           → igloo.video/create → Razorpay (display $14.99, charged ~₹1,249 INR)
4. Create        → Flask studio on Fly.io (theme → narration → character → script)
5. Render        → 9-step pipeline runs (capped at IGLOO_MAX_PIPELINES concurrent)
6. Review        → Operator watches in igloo.video/admin
7. Deliver       → Customer notified → downloads via signed Supabase URL
   OR Reject     → Credit refunded in ledger, customer notified, refund handled
```

Every architectural decision in this codebase should serve one of these 7 steps. If a task doesn't, it's either infrastructure (fine) or drift (stop).

## Product boundaries (the thing that keeps getting lost)

The product is **three distinct applications** with clear responsibilities. Do not mix them up:

### 1. Landing (`landing/`) — the front door

- **Stack:** React + Vite, deployed to Vercel at `igloo.video`
- **Role:** Marketing site + policy pages (privacy, refund, pricing, contact — required by Razorpay)
- **Owns:** brand, copy, CTAs pointing to `igloo.video/sign-up`
- **Does NOT own:** authentication, payment, the wizard, admin, anything stateful
- **Touch only when:** copy/pricing/CTAs change, or policy pages need updates

### 2. Gate (`app/`) — the authenticated shell

- **Stack:** Next.js 16 + React 19 + Tailwind 4 + Clerk 7, deployed to Vercel at `igloo.video`
- **Role:** Authentication, payment collection, run status polling, admin review UI, delivery
- **Owns:**
  - `/sign-in`, `/sign-up` — Clerk auth
  - `/create` — minimal "pay to unlock" page (topic input + Razorpay button). **NOT** the creation wizard.
  - `/api/razorpay/*` — order creation + webhook
  - `/runs/[id]` — customer-facing run status (polling Supabase)
  - `/admin/*` — operator review, deliver, reject
  - `/api/admin/runs/[id]/deliver` + `reject` — state transitions
  - `process-payment.ts` — creates `runs` row with `status='draft'`, mints signed HMAC token, returns studio URL
- **Does NOT own:** the wizard itself, the pipeline, the video files, the creation flow
- **Hard rule:** if you catch yourself adding a theme picker, narration editor, or character selector here, STOP. That lives in the studio.

### 3. Studio (`execution/web_app.py` + `execution/templates/`) — the wizard + pipeline

- **Stack:** Flask + vanilla JS frontend + 8 Python step scripts, hosted on Fly.io (gunicorn, single-machine, `igloo-studio.fly.dev`). Modal (`@modal.wsgi_app()`) is kept alive as one-line rollback until 24h post-Fly green.
- **Role:** The entire creative experience after payment — theme/topic/narration/character/script wizard, pipeline execution with SSE live progress, final MP4 upload to Supabase
- **Owns:**
  - The full interactive wizard ([execution/templates/index.html](execution/templates/index.html))
  - The 9-step pipeline orchestration ([execution/run_pipeline.py](execution/run_pipeline.py))
  - The 8 step scripts (voice, voiceover, timestamps, slicing, images, video, music, assembly)
  - The final MP4 upload to `reels/<run_id>/final.mp4` in Supabase Storage
  - Updating `runs.status` from `draft` → `queued` → `running` → `awaiting_review`
  - Per-user state (keyed by `user_id` from the signed token)
  - Pipeline slot enforcement (`IGLOO_MAX_PIPELINES`, default 3)
- **Does NOT own:** authentication, payment, admin review, email, delivery
- **Hard rule:** the studio trusts its input. If a request arrives with a valid HMAC token, the user has paid. The studio does not check Clerk, does not talk to Razorpay, does not send emails.

## The 3-layer architecture (from the engineering CLAUDE.md)

- **Layer 1 — Directives** (`directives/`): SOPs in Markdown. Natural language instructions.
- **Layer 2 — Orchestration:** The AI assistant. Reads directives, calls Python tools, handles errors, asks when unsure, updates directives.
- **Layer 3 — Execution** (`execution/`): Deterministic Python scripts. Pipeline steps, API integrations, file operations.

**Why this exists:** 90% × 90% × 90% × 90% × 90% = 59%. Compounding LLM errors across a 9-step pipeline are fatal. The fix is to push determinism into Python and keep the LLM for decision-making. **Never refactor the pipeline to be LLM-driven end-to-end.** The pipeline is hard-coded on purpose.

## Who we're building for

**Primary audience (s27 reality): Indian creators at a premium price point, branded as globally-positioned.** Pricing moved from ₹420 → ₹1,249 INR (equivalent of $14.99). The sticker is `$14.99 (~~$19.99~~)` for brand positioning; the actual charge is in INR because Razorpay International Cards is not yet enabled on the account. See session 27 checkpoint for the workaround rationale.

**Future audience: international creators.** Once Razorpay International Cards activates (or an alternative processor like Stripe/Paddle ships), the same price point becomes a real USD charge and foreign cards stop bouncing. That's a future workstream — do NOT build it speculatively.

The ideal customer — regardless of geography — is a content creator, coach, solopreneur, or small-business owner who wants to publish short-form video but:
- Does not know how to edit video
- Does not want to be on camera (the anchor is AI-generated)
- Cares about quality (hence the human QC gate)
- Will pay $14.99 (or ₹1,249 equivalent) for a single finished reel instead of learning Premiere

## What this product is NOT (anti-drift list)

The assistant has real tendencies to drift into the items below. Do not build any of these unless explicitly asked.

- **Not a video editor.** No timeline UI, no clip trimming, no effects panel. The wizard collects text and the pipeline renders.
- **Not a self-serve SaaS (yet).** Every reel is manually reviewed. There is no "instant download" path. Do not build one.
- **Not multi-tenant enterprise software.** There is one operator (the user of this codebase), one admin panel, one queue. Do not add workspaces, teams, roles, or RBAC.
- **Not a video hosting service.** Supabase Storage is a delivery mechanism, not a library. Do not build playlists, sharing, embeds, or public video pages.
- **Not a subscription product.** Pay-per-reel only. Do not add monthly plans, usage tiers, or seat-based pricing.
- **Not a creation-tool clone in Next.js.** The wizard lives in Flask. Do not rebuild it in React. Session 25's biggest mistake.
- **Not real-time collaborative.** One user, one reel, one pipeline run. No shared editing.
- **Not chat-driven.** No "tell me what you want and I'll make it" LLM frontend. The wizard's structured steps exist because free-form chat produces inconsistent reels.

## Non-negotiables (things that must stay true)

1. **Human review before customer download.** Every reel is QC'd by the operator. No exceptions. This is the quality moat and the reason the product can charge $14.99.
2. **Deterministic pipeline steps.** Each of the 8 Python step scripts is a pure function of its inputs. The LLM makes decisions at step 0 (script generation) and step 5 (image prompts); everything else is deterministic.
3. **Cash-on-failure refunds.** If a pipeline fails or the operator rejects, the customer gets a +1 credit refund in the ledger. (Actual Razorpay money-back is deferred, credit is the MVP substitute.)
4. **One pipeline per user.** A customer can't have two reels rendering at the same time under their account. Enforced in the studio.
5. **Global pipeline cap.** `IGLOO_MAX_PIPELINES` (default 3) limits total concurrent renders. Currently bounded by Kling/ElevenLabs rate limits and our own cost model.
6. **Auth at the gate, not the studio.** Clerk lives in the Next.js app. The studio trusts signed HMAC tokens. Do not introduce Clerk into Flask.
7. **Operator = the user of this codebase.** There is one admin. Do not build a multi-admin workflow.

## Known deferred capabilities (Phase 10+)

These are intentionally missing today and should be deferred, not built ad-hoc:

- **Email notifications** on delivery/rejection. Will use Resend. Stub comment lives in [app/src/app/api/admin/runs/[id]/deliver/route.ts](app/src/app/api/admin/runs/%5Bid%5D/deliver/route.ts).
- **Razorpay refund API** (actual money-back, not just credit ledger). Pending Razorpay dashboard flow verification.
- **30-customer waitlist** gating.
- **Live Razorpay mode** (currently TEST).
- **Custom domain + DNS** — consolidated to `igloo.video` (done s41). `www` and `app` subdomains redirect.

## Reference map

- **Engineering rules + session state:** [CLAUDE.md](CLAUDE.md) (the 3-layer architecture section is canonical; the "Current state" section is the rolling pointer).
- **Latest session checkpoint:** `.tmp/checkpoint_YYYY-MM-DD_sessionN.md` — whichever CLAUDE.md points to.
- **Active implementation plan:** whatever plan file CLAUDE.md currently references.
- **Reel pipeline SOP:** [directives/automated_pipeline_order.md](directives/automated_pipeline_order.md) and companions in [directives/](directives/).
- **Product UI (the wizard):** [execution/web_app.py](execution/web_app.py) + [execution/templates/index.html](execution/templates/index.html).
- **Pipeline orchestrator:** [execution/run_pipeline.py](execution/run_pipeline.py).
- **Modal host:** [infra/modal/igloo_worker.py](infra/modal/igloo_worker.py).
- **Next.js gate:** [app/src/app/](app/src/app/) (Clerk protected, Razorpay, admin, runs status).
- **Database schema:** [infra/supabase/migrations/](infra/supabase/migrations/).
- **Cleanup tool:** [infra/cleanup_test_rows.py](infra/cleanup_test_rows.py) (dry-run default).

## How to use this document

**At the start of every session:**
1. Read this file.
2. Read the "Current state" section of [CLAUDE.md](CLAUDE.md) to find the latest checkpoint.
3. Read the latest checkpoint.
4. Read the active plan file if one exists.
5. Only then begin work.

**When proposing a change:** ask "which of the 7 customer-journey steps does this serve?" If the answer is "none", it's probably drift.

**When tempted to build something not in this document:** stop and ask the user. Do not silently expand scope.
