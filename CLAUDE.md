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

## MANDATORY: Landing Agent Brief

**`app/LANDING_AGENT.md` is the binding contract for ALL landing page work.** Every AI agent MUST read it in full before touching any file in `app/`. It defines:
- Exactly which files you may edit (section 1) and which are off-limits (section 2)
- CTA route contracts (`/sign-up`, `/sign-in`, `/create`) — no deviations
- Clerk 7 rules (`<Show>`, not `<SignedIn>`)
- Dependency policy (no `npm install` without human approval)
- Git workflow (branch, never merge to main)
- Brand rules (name, tagline, tone, colors)

**Violations cause broken payments, broken auth, and merge conflicts with production work. When in doubt, stop and ask the human.**

## MANDATORY: Impact Mapping

**`directives/impact_mapping.md` is the systems-thinking reference for the landing page revamp.** Every AI agent MUST read it before making changes to the landing page. It maps:
- Full system architecture and file ownership
- Dependency graph (what imports what, what CSS classes are used where)
- Cross-system impact matrix (if you change X, what else breaks?)
- Active risks and technical debt
- Contract compliance verification
- Pre-change checklist

**This file must be kept up to date as changes are made.**

## MANDATORY: Impact Contract Gate — Present Before Executing

**Every time the human asks you to execute a change (code, config, asset, or structural), you MUST present an Impact Contract for approval BEFORE writing any code.** Do not skip this step. Do not start implementation until the human explicitly approves.

The Impact Contract uses the Prompt Contracts format (see `Prompt Contracts.md`) extended with an impact section derived from `directives/impact_mapping.md`:

```markdown
## Impact Contract

GOAL: [What does success look like? Measurable outcome.]

IMPACT ANALYSIS (from impact_mapping.md):
- Files touched: [list every file that will be created/modified/deleted]
- Files affected downstream: [list files that won't be edited but whose behavior changes]
- Cross-system impact: [what other pages/routes/services are affected and how]
- Risk level: [LOW / MEDIUM / HIGH — justify]

CONSTRAINTS:
- [Hard limits from LANDING_AGENT.md, impact_mapping.md, and task context]

FORMAT:
- [Exact deliverables — files, structure, what's included]

FAILURE (any of these = not done):
- [Specific failure conditions]

CONSEQUENCES:
- [What will happen in the future as a result of this change?]
- [Who/what else is affected beyond the immediate scope?]
```

**The human must approve this contract before you write a single line of code.** If the human says "go" or "approved" or similar, proceed. If they push back, revise the contract. This is non-negotiable — it prevents cascading failures and ensures the human maintains full control over what enters the codebase.

## MANDATORY: Reverse Prompting — Brand Assets Before Design

**Before choosing ANY colors, typography, or visual direction, you MUST first inspect existing brand assets** (`igloo/logo-final.png`, `local_files_read_only/positioning.md`, old `landing/src/index.css` for prior palette) and derive the design from those sources. Never invent a color palette or theme without consulting the source of truth. If anything is ambiguous, ask the human.

## Current state (Igloo launch)

**Latest checkpoint:** `.tmp/checkpoint_2026-04-08_session24.md` — start here for pipeline/backend context.

**Landing page revamp checkpoint:** `directives/checkpoints/web_revamp_in_probgress.md` — start here for landing page work (Sessions 1–11).

- Phases 1–8 ✅ complete. Sign up → buy → pipeline → admin review → customer download all working end-to-end locally.
- **Next.js app** lives in `app/` (Next 16 + React 19 + Tailwind 4 + Clerk 7). Middleware file is `src/proxy.ts` (Next 16 rename), not `middleware.ts`. Razorpay is in TEST mode.
- **Phase 9 next:** Vercel deploy + flip Razorpay to live.
- **Landing page (Session 5):** Font swapped from Geist Sans to Inter (matches logo's geometric thin-weight aesthetic). Apple-level type system: light-weight headings, medium-weight cards, weight+tracking hierarchy. All sections centered. Problem section stripped to one statement. "Reel" → "Video" everywhere. Anti-AI writing pass: all em dashes removed, AI-isms scrubbed, human voice. Delivery promise: "minutes" not "next morning". Pricing section centered + aligned to $14.99/~~$19.99~~ USD (matching hero). Sample hooks marquee removed. Build clean.
- **Video assets (Session 6):** "One Engine, Every World" concept — 5 Kling clips (fitness/finance/parenting/wellness/spirituality) assembled with 0.75s cross-dissolve transitions into a 12.2s 1080p video. Kling watermark cropped. Final: `local_files_read_only/content/nano1/one_engine_every_world_cropped.mp4` (10 MB). Assembly script: `local_files_read_only/content/nano1/assemble.sh`. Full Nanobanana PRO + Kling 3.0 + ElevenLabs prompt packages documented in checkpoint. Human must decide if this replaces the current hero video.
- **AI prompting knowledge (Session 6):** Nanobanana PRO photorealism formula (specificity + imperfection + photography language) and Kling 3.0 video formula (camera angle first + 3-phase motion + multi-shot storyboard) learned from 31 course lesson files. Prompts are reusable for future video generation.
- **Features scroll-pinned video scrub (Session 7):** "What makes Igloo different" section rebuilt as a scroll-driven interactive. 300vh tall section with sticky viewport. Video (`features-scrub.mp4`, 2.4 MB, 720p, all-intra keyframe h264) scrubs frame-by-frame via `video.currentTime` on scroll. 3 specialties (Unscrollable, Cinematic, Niche-proof) rifle in with crossfade + slide transitions. CSS `mask-image` vignette (`.features-vignette`) dissolves video edges seamlessly into the `#050505` background. Text readability via left-side dark gradient + `.features-text-glow` text-shadow. Progress dots below video. Pure vanilla JS, no animation library. Dead marquee CSS cleaned from globals.css. Build clean.
- **HowItWorks ad video + card fixes (Session 8):** `igloo_ad_final.mp4` (founder explaining how Igloo works) added as a contained cinema block in HowItWorks between heading and step cards. Compressed to 1.5 MB MP4 + 1.0 MB WebM (720p, audio preserved, Kling watermark cropped). Borderless `features-vignette` mask (matching Features section). Mute/unmute toggle. HowItWorks heading centered. Pricing + FinalCTA double-bezel borders flattened to single `border-border-subtle bg-surface` (matching step cards). Instagram link added to Footer (`https://www.instagram.com/igloo.video/`). Problem section reverted to text-only. Build clean.
- **Reel marquee in Pricing section (Session 9):** 4 portrait reel videos (`Fasting_wellness`, `Hanuman_Lanka`, `Spiritual_growth`, `igloo_promo_reel`) from `local_files_read_only/content/reels/` compressed to 360x640 (721 KB–1.1 MB each, 3.6 MB total, no audio). Horizontal auto-scrolling marquee of portrait video cards between pricing heading and $14.99 card. CSS `translateX(-50%)` infinite loop, 35s cycle, hover-pause, left/right `mask-image` edge fade. Track uses shuffled second set `[C,A,D,B]` + `currentTime` stagger (15-25s offsets) so same-source videos never show identical frames simultaneously. 16 `<video>` elements (8 × 2 for seamless loop). Pricing.tsx converted to client component. No new dependencies. Build clean.
- **Premium quality upgrade + mobile reliability (Session 11):** All videos re-encoded at 1080p CRF 20 High profile (hero: 2.8 MB, ad: 5.9 MB). Features scroll section completely rewritten: `features-scrub.mp4` deleted, replaced by 59 JPEG frames at 1080p in `app/public/features-frames/` (3.4 MB total). Canvas-based rendering with lerp-smoothed scroll (Apple.com approach). MP4-first source order in Hero + HowItWorks for iOS Safari compatibility. IntersectionObserver lazy video activation in Pricing marquee (prevents iOS decoder overload). Bottom gradient bar in HowItWorks for subtitle readability. Logo compressed 495→100 KB. No new dependencies. Build clean.
- **Pricing: frontend aligned, backend still INR:** Hero and Pricing section both show $14.99/~~$19.99~~ USD. `lib/razorpay.ts` still has `REEL_PRICE_PAISE = 42000` (INR). Backend is off-limits — human must update.
- **Known dev-env issue:** A Chrome extension blocks `<video>` playback. Test in incognito (`Cmd+Shift+N`). Not a production issue.
- **Anti-AI writing style:** `local_files_read_only/content/ANTI AI WRITING STYLE.md` is the reference. All landing page copy must follow it: no puffery, no em dashes, no vague attributions, short specific sentences, human voice.
- Modal trigger URL: `https://vigneshbalaraj-hue--igloo-trigger.modal.run`
- Modal deploys must use `PYTHONIOENCODING=utf-8` prefix on Windows
- Local webhook testing uses cloudflared tunnel — URL is ephemeral, dies on terminal close. Razorpay dashboard webhook will need re-pointing each restart until Vercel deploy.
- Use local tsc (`./node_modules/.bin/tsc`) not `npx tsc` (npx grabs unrelated tsc@2 package).