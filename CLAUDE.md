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

## Current state (Igloo launch)

**Latest checkpoint:** `.tmp/checkpoint_2026-04-08_session24.md` — start here.

- Phases 1–8 ✅ complete. Sign up → buy → pipeline → admin review → customer download all working end-to-end locally.
- **Next.js app** lives in `app/` (Next 16 + React 19 + Tailwind 4 + Clerk 7). Middleware file is `src/proxy.ts` (Next 16 rename), not `middleware.ts`. Razorpay is in TEST mode.
- **Phase 9 next:** Vercel deploy + flip Razorpay to live + ₹420 end-to-end charge.
- Modal trigger URL: `https://vigneshbalaraj-hue--igloo-trigger.modal.run`
- Modal deploys must use `PYTHONIOENCODING=utf-8` prefix on Windows
- Local webhook testing uses cloudflared tunnel — URL is ephemeral, dies on terminal close. Razorpay dashboard webhook will need re-pointing each restart until Vercel deploy.
- Use local tsc (`./node_modules/.bin/tsc`) not `npx tsc` (npx grabs unrelated tsc@2 package).