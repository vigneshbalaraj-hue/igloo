# P0 Triage — post-Fly-migration backlog

**Created:** 2026-04-09 (session 32)
**Type:** Triage only — no implementation detail beyond fix shape and size.
**Source:** User's bug/feature spreadsheet, P0 items only. P1/P2/P3 items captured at the bottom for the next triage cycle.
**Status:** Parked for review. User will comment on items after Fly migration lands.

---

## Context

The Igloo reel pipeline is mid-migration to Fly.io (s31 checkpoint). Once acceptance criterion #3 lands green (current retry in flight), the migration is done and we need a sequenced P0 backlog to work through next.

The user filtered the original 21-item list to P0s only. This plan triages those P0s into a recommended execution order with fix locations, sizes, dependencies, and verification paths. No code is being written here — this is the work order for the next several sessions.

Two items in the original list are already accounted for and **not** re-triaged here:
- **#2 Setting up payment** — done.
- **#3 Hosting the tool (Fly migration)** — in flight, this whole plan is gated on it landing.
- **#20 Local archive sync** — separately scoped in [FEATURE_LOCAL_ARCHIVE_SYNC.md](FEATURE_LOCAL_ARCHIVE_SYNC.md), P2 anyway.

One item is explicitly deferred by the user:
- **#19 Merging landing page** — "Leave it for now."

---

## P0 backlog (8 items, sequenced)

### Block A — Quick wins (do first to build momentum)

#### A1. #10 — Caption full narration, not just keywords  `XS`

- **Current:** [execution/assemble_video.py:508](execution/assemble_video.py#L508) reads `scene.get("caption_text", "")`, which is intentionally only 1-3 keywords in ALL CAPS (per [execution/prompt_bank.py:534,625-627](execution/prompt_bank.py#L534)).
- **Fix shape:** One-line change — read `narration_text` instead of `caption_text`. Verify word-wrap at [execution/assemble_video.py:528](execution/assemble_video.py#L528) handles longer lines on mobile aspect.
- **Size:** XS (1-line fix + 1 wrap-test).
- **Risk:** Low. Possible cosmetic issue if long narration overflows the safe area; mitigate by re-checking the wrap math with a worst-case 12-15 word line.
- **Dependencies:** None.

#### A2. #15a — Verify reconnect-to-run actually works  `XS`

- **Current:** [app/src/app/runs/[id]/page.tsx:62-93](app/src/app/runs/[id]/page.tsx#L62-L93) already polls Supabase `runs` every 5s. RLS at [infra/supabase/migrations/0002_rls_policies.sql:33-41](infra/supabase/migrations/0002_rls_policies.sql#L33-L41) allows owner SELECT.
- **Fix shape:** No code change yet — **this is a verification task**. Manual test: start a real run, close the browser tab, log back in via Clerk on a different tab, navigate to `/runs/<id>`, confirm status updates appear. If it works → close item with "verified, no fix needed." If it breaks → debug RLS (likely cause: `users` row not created on first Clerk login, blocking the SELECT).
- **Size:** XS to S (XS if it works as designed, S if RLS user-row needs a Clerk webhook fix).
- **Risk:** Low.
- **Dependencies:** Fly migration must be green so we can run a real test.

---

### Block B — Foundation fixes (script + voice quality)

These are the items that improve every reel going forward. Do them before the harder structural items in Block C.

#### B1. #11 — Strict 60s hard limit on reels  `S`

- **Current:** [execution/prompt_bank.py:696-757](execution/prompt_bank.py#L696) has `validate_scenes()` enforcing a soft word-count band (`±WPS_BAND=0.15` around `duration × wps`). For 60s @ 2.5 wps that's ~128-172 words. Gemini frequently overshoots, validator allows retry but no hard ceiling.
- **Fix shape:** Two changes:
  1. Add an explicit "MUST be under 150 words for a 60-second reel" line to the script generation prompt.
  2. Tighten the validator: `if word_count > duration * 2.8: fail`. On fail, auto-retry up to 2x with the hard limit re-emphasized.
- **Size:** S (~30-50 lines, 2-3 prompt edits + validator tightening).
- **Risk:** Medium. Stricter limits may frustrate users with rich content; slow voices may still overshoot 60s even with 150 words. Mitigate by measuring real WPS per voice in a follow-up.
- **Dependencies:** None. **This is the highest-leverage fix in Block B** because it indirectly mitigates Bug #6 (fewer scenes will exceed the 5s b-roll cap if total reel length is hard-capped).

#### B2. #9 — Voice gender mismatch (Dutch dyke anchor)  `S`

- **Current:** [execution/select_voice.py:100-157](execution/select_voice.py#L100-L157) does keyword matching on `script.anchor_character.voice.gender`, populated by Gemini's character generation prompt at [execution/web_app.py:544-547](execution/web_app.py#L544-L547). Prompt asks for gender but does NOT explicitly tie it to the visual description in `image_prompt`.
- **Fix shape:** Two changes:
  1. Tighten the character prompt: "voice.gender MUST match the visual gender described in image_prompt."
  2. Add a post-generation cross-check in `select_voice.py`: if `image_prompt` contains explicit gender markers ("woman", "man", "elderly female", etc.) that disagree with `voice.gender`, force-correct or flag for review.
- **Size:** S (~50 lines: prompt edit + simple keyword cross-check).
- **Risk:** Low. Edge case for androgynous/non-binary characters; default to whatever the visual implies.
- **Dependencies:** None.

#### B3. #17 — Gemini same-family fallback (2.5-flash → 2.5-pro)  `M`

- **Current:** [execution/web_app.py:421-460](execution/web_app.py#L421-L460) `call_gemini` retries 6× with backoff (s31 fix), but model is hardcoded to `gemini-2.5-flash`. **22+ call sites** across `web_app.py` (9), `generate_script.py` (11), `prompt_bank.py` (2). `generate_script.py` has its own duplicate `call_gemini` at [execution/generate_script.py:64](execution/generate_script.py#L64).
- **Fix shape:**
  1. Add `fallback_model="gemini-2.5-pro"` parameter to `call_gemini`. After exhausting flash retries, swap model URL and retry once on pro.
  2. **Unify the duplicate** — `generate_script.py` and `prompt_bank.py` should import the canonical `call_gemini` from `web_app.py` (or extract to `execution/gemini_client.py`). Eliminates the maintenance fork.
  3. Log fallback events (metric for billing — pro is ~10× flash cost).
- **Size:** M (~150-250 lines: function refactor + 22 import-site updates + telemetry).
- **Risk:** Medium. Pro response format may differ subtly from flash; validate parsing on each call site. Cost spike if pro fallback fires too often → add a circuit breaker (e.g., disable fallback for 5min if 3+ pro fallbacks in a window).
- **Dependencies:** Should land **after B1** so the script generator's hardened budget is in effect when it gets retried on pro (otherwise pro inherits the same overshoot problem at 10× cost).

---

### Block C — Structural / harder items

#### C1. #6 — B-roll 5s cap → freeze artifact  `M (research-gated)`

- **Current:** [execution/generate_video_clips.py:251](execution/generate_video_clips.py#L251) submits b-roll to Kling v2-1 with `kling_duration=5` (hardcoded). When narration exceeds 5s, video freezes on last frame. Anchor scene boundary doesn't help because the next scene's audio crosses the freeze.
- **Fix shape:** **Depends on a Kling v2-1 API fact I don't have yet.** Two paths:
  - **Path A (cheap):** If Kling v2-1 supports >5s clips (e.g., 10s), just pass `narration_duration` capped at the API max. ~10 lines change. **XS**.
  - **Path B (expensive):** If Kling v2-1 is hard-capped at 5s, generate N×5s clips for scenes > 5s, then crossfade-concat them in [execution/assemble_video.py](execution/assemble_video.py) using the same pairwise pattern from s31. **M-L** (~200-400 lines).
- **Step 0 of this item: 30-min research spike** — read Kling v2-1 docs (or test the API) to determine max duration. The plan picks Path A or B based on the answer. Pre-research, treat this as **M with a wide error bar**.
- **Risk:** High variance. Path B is significant work and adds cost (multiple Kling generations per long scene). B1 (60s hard cap) partially mitigates by reducing the number of long scenes.
- **Dependencies:** Should land **after B1** because B1 reduces the population of scenes that hit this bug. Possibly defer entirely if B1 makes >5s b-roll scenes rare enough.

---

### Block D — User-facing additions

#### D1. #15b — Email on delivery  `S`

- **Current:** [app/src/app/api/admin/runs/[id]/deliver/route.ts:57-59](app/src/app/api/admin/runs/[id]/deliver/route.ts#L57-L59) has a TODO comment for email, no email client imported.
- **Fix shape:**
  1. Pick a transactional email provider — **recommend Resend** (best Next.js DX, generous free tier, simple SDK).
  2. Install `resend` package, add `RESEND_API_KEY` to env.
  3. Build a minimal HTML template: subject "Your reel is ready", body with a signed Supabase Storage URL (7-day expiry) to the final MP4.
  4. Send from the deliver route after the status update. Wrap in try/except — email failure must NOT block delivery.
  5. Fetch user email from Supabase `users` table (already synced via Clerk webhook — verify this).
- **Size:** S (~80-120 lines + 1 env var + 1 template).
- **Risk:** Low. Email failure is best-effort, doesn't break the user flow.
- **Dependencies:** None. Can land any time after Fly migration.

#### D2. #18 — Post-reel feedback (rating + text)  `S`

- **Current:** No feedback collection exists today.
- **Fix shape:**
  1. Migration `0006_add_run_feedback.sql`: new table `run_feedback` with `run_id`, `user_id`, `rating INT (1-5)`, `feedback_text TEXT`, `submitted_at`. RLS: owner can INSERT/SELECT their own.
  2. New page or modal on the runs page (after status='delivered'): 5-star rating widget + optional textarea + submit button.
  3. New API route `app/src/app/api/runs/[id]/feedback/route.ts` to POST the feedback.
  4. Optional: admin page `/admin/feedback` to read aggregated feedback.
- **Size:** S (~150-200 lines: migration + 1 page + 1 route + RLS).
- **Risk:** Low. Standard CRUD pattern.
- **Dependencies:** None.

---

## Recommended execution order

```
Block A (quick wins, ~half session)
  ├─ A1: #10 captions full narration                          [XS]
  └─ A2: #15a verify reconnect works                          [XS]

Block B (foundation, ~1-1.5 sessions)
  ├─ B1: #11 strict 60s hard limit  ◀ highest leverage        [S]
  ├─ B2: #9  voice gender match                               [S]
  └─ B3: #17 Gemini fallback (depends on B1)                  [M]

Block C (structural, ~1-2 sessions, research-gated)
  └─ C1: #6  b-roll 5s cap (Kling research first, then fix)   [M]

Block D (user-facing, ~1 session)
  ├─ D1: #15b email on delivery                               [S]
  └─ D2: #18 post-reel feedback                               [S]

Always ready (do whenever):
  └─ #21 Fly shared-cpu-2x + 4gb bump + revert pairwise       [XS]
       ◀ gated on current run landing, then before any other block
```

**Why this order:**
- Block A first because both items are XS and validate that the post-migration system is healthy before we start changing things.
- Block B before Block C because (a) B1 hardens script length, which (b) reduces the population of scenes that hit C1's b-roll bug, possibly making C1 unnecessary or cheaper.
- B3 after B1 because Gemini Pro fallback is 10× more expensive — we want the script budget tight before we ever hit the fallback, otherwise we pay 10× for a still-too-long script.
- Block C is research-gated and high variance; doing it last protects the schedule.
- Block D items are independent and can interleave or run in parallel; they don't block anything else.

---

## Verification (how you know each item is done)

| Item | Verification |
|---|---|
| A1 #10 | Generate a reel, watch playback, confirm every word of every scene's narration appears as a caption. |
| A2 #15a | Start a real run, close browser, reopen `/runs/<id>` from another tab, confirm status updates appear. If RLS blocks → debug user-row creation. |
| B1 #11 | Generate 5 reels, measure final MP4 duration of each. All must be ≤ 60.0s. None should hit the validator-retry exhaustion path. |
| B2 #9 | Generate a reel with an explicitly female anchor description, confirm voice gender matches. Repeat for male, elderly, child. |
| B3 #17 | Manually trigger a Gemini 503 storm (e.g., during peak hours), confirm pipeline completes via Pro fallback. Check telemetry shows the fallback fired. |
| C1 #6 | Generate a reel where at least one b-roll scene exceeds 5s. Final MP4 should show no freeze frame, video and audio aligned end-to-end on that scene. |
| D1 #15b | Deliver a test run, confirm the user receives an email with a working signed URL within ~30s. |
| D2 #18 | Submit feedback on a delivered reel, confirm row appears in `run_feedback` table with correct rating and text. |
| #21 Fly bump | After current run lands → `~/.fly/bin/flyctl.exe deploy` with shared-cpu-2x + 4gb + reverted single-pass xfade. Run a fresh reel end-to-end, confirm assembly wall time drops vs pairwise. |

---

## Items NOT in this triage cycle

These were in the original 21-item list but are P1/P2/P3 and were not part of this round:

- **P1:** #5 reels longer than requested (probably auto-fixed by B1), #8 voice refinement + manual gate, #13 script direction styles
- **P2:** #1 Hanuman anchor selection, #4 time estimate copy, #7 API pricing conversion, #12 "Edit video prompt" empty screen, #20 local archive sync (already specced)
- **P3:** #16 NSFW error handling

**Re-triage these in the next planning session** after the P0 block lands. Several may auto-resolve as side effects of the P0 fixes (especially #5 from B1, and #1/#4 from B2/UX work).

---

## Open questions (none blocking, but worth flagging)

1. **C1 Kling research:** Need 30 minutes with Kling v2-1 docs/API before committing to Path A or B. Could be done as a precursor "research spike" task at the start of Block C.
2. **D1 user email source:** Need to confirm that Clerk → Supabase user.email sync is actually populating the `users` table. If not, D1 needs an extra step to fetch from Clerk API directly.
3. **B3 telemetry:** Where to log fallback events? Supabase `runs` row, or a new `gemini_fallback_log` table, or just structured logs to stdout? Recommend Supabase column for now (cheap, queryable).
4. **B1 voice WPS calibration:** A 60s × 2.5 wps = 150 word target assumes "average" voice speed. Different ElevenLabs voices speak at different rates. Worth a follow-up to measure WPS per voice and store it in the voice config so the budget adapts. Defer until B1 ships and we see whether 150 is right.
