# Directive: Audio-Video Sync — Lessons Learned

> Living document. Update after every production run with new findings.
> Last updated: 2026-04-01 (Session 2 — first manual video build)

## Why this matters

**Lip-sync is the #1 product feature.** It is not one quality factor among many — it is THE quality gate. A reel with mediocre b-roll but perfect lip-sync is shippable. A reel with stunning visuals but broken lip-sync is unwatchable. We are not forgiving on any lip-sync issues.

A 0.3s lip-sync mismatch makes the entire video look broken. Every decision about clip duration, scene boundaries, and assembly order flows from one question: does the audio match the video at every frame?

**Hierarchy of priorities:**
1. Lip-sync accuracy (mouth shapes match the audio the viewer hears)
2. Audio timing (scene boundaries align with voiceover timestamps)
3. Voice quality (natural, authoritative, consistent)
4. Visual quality (video fidelity, motion naturalness)
5. Everything else (captions, music, color grading)

## Core principle

**Audio is the source of truth. Video conforms to audio, never the other way around.**

All scene boundaries, clip durations, and assembly timings must be derived from the actual generated voiceover timestamps — not estimated from script word count or assumed speaking pace.

---

## ElevenLabs voice generation

### Speed parameter is unreliable
- Tested `eleven_multilingual_v2` at 1.0x (35.9s), 1.2x (34.5s), 1.4x (37.9s — *longer* than 1.2x)
- The speed parameter does not scale linearly. Higher values can produce longer audio due to re-interpretation of pacing and pauses
- `eleven_turbo_v2_5` gives more consistent speed control than `eleven_multilingual_v2`
- **Rule:** always check the actual output duration. Never assume speed multiplier = proportional duration reduction

### Timestamp extraction is a two-step process
- ElevenLabs returns **character-level** timestamps, not word-level
- Must convert to word-level by finding space boundaries in the character array
- Word-level timestamps are what you need for scene boundary alignment
- Use `execution/extract_word_timestamps.py` for this conversion
- **Rule:** always extract word timestamps after generating voiceover. The script JSON must reference real timestamps, not estimated ones

### Sentence pacing varies by content
- Short declarative sentences ("No screens.") take 1.1-1.3s
- Lists with dashes ("books, homework, conversations") add pauses that inflate duration beyond word count estimates
- Emotional/dramatic lines get natural slowdowns even at higher speed settings
- **Rule:** never estimate scene duration from word count. The pauses between sentences and around punctuation (dashes, commas) are significant

---

## Kling video generation

### Duration constraints
- **B-roll clips (kling-v2-1, image-to-video):** only 5s or 10s — no arbitrary durations
- **Anchor clips (kling-v3, image-to-video):** flexible 3-15s durations. We generate `ceil(audio_duration)` to minimize silent tail, then assembly trims to exact narration window
- **Lip-sync clips:** duration is driven by input audio length. The output video matches the audio duration
- Minimum generation is 5s for v2-1 standard clips, 3s for v3
- **Lip-sync minimum:** `sound_end_time` must be ≥ 2000ms. Any anchor scene with <2s audio will fail. Ensure narration text is long enough

### Two different sync strategies based on scene type

**Anchor scenes (kling-v3 + lip-sync, 3-step):**
1. Measure audio slice duration via ffprobe
2. Generate v3 base video with `duration = ceil(audio_duration)`, min 3s, sound=off
3. identify-face → advanced-lip-sync with exact ffprobe-measured `sound_end_time`
- Output video ≈ audio duration (may have small silent tail from ceil overshoot)
- Assembly trims to exact narration window — silent tail is removed
- `sound_end_time` must exactly match audio file duration (ffprobe) — overestimating by even 150ms causes task failure

**B-roll scenes (image-to-video):**
- Generate 5s clips (Kling minimum)
- Trim to exact scene duration in FFMPEG assembly
- Sync is irrelevant because there are no lip movements — narrator speaks over cutaway footage
- Trim from the end of the clip (keep the beginning where the motion is most natural)

### Audio slicing for lip-sync
- Each anchor scene needs its own audio file sliced from the master voiceover
- Slice points must be at exact word boundaries from the timestamp data
- **No silence prepend** — Session 8 confirmed there is no Kling lip-sync startup lag. The previous 150ms silence was harmful (inflated durations, delayed speech onset)
- `audio_slice` values are now auto-derived from actual voiceover word timestamps via `extract_word_timestamps.py --update-script`

---

## Scene boundary alignment

### Scene breaks must land on sentence boundaries
- Never split a scene in the middle of a sentence — it creates unnatural audio-visual discontinuity
- Use periods, long pauses after dashes, or natural breath points as scene boundaries
- The word timestamp data shows exact pause locations between sentences

### Multi-clip scenes (scenes longer than 5s)
- When a b-roll scene exceeds 5s, it needs two Kling clips stitched together
- **The stitch point must coincide with a visual scene change** — use a different b-roll image for each sub-clip
- This way the viewer reads the cut as intentional (editorial cut between two shots), not a technical artifact
- Use cross-dissolve (0.3s) at the stitch point to smooth it further
- Best stitch points: natural pauses in narration (after commas, dashes, periods)
- Example: "books, homework, conversations — feels painfully slow" splits at the dash. Clip 4a shows boy staring at book, clip 4b shows close-up of his glazed expression. The scene change masks the stitch

### Anchor scenes longer than 5s
- Lip-sync handles this automatically — Kling accepts audio up to ~10-15s
- No stitching needed for anchor scenes under 10s
- If an anchor scene exceeds 10s (unlikely in reel format), it would need splitting — but split at a sentence boundary and use the same anchor image for both clips to maintain character continuity

---

## FFMPEG assembly rules (anticipated — not yet tested)

### Timeline construction
1. Lay down the full voiceover as the audio master track
2. Place each video clip at its exact `narration_start` timestamp
3. Anchor clips already match their audio duration — no adjustment needed
4. B-roll clips: trim from end to match `scene_duration`
5. Apply cross-dissolve transitions (0.3s) between all scenes
6. Layer background music at low volume under everything
7. Add captions synced to word timestamps

### Known risks (to be validated)
- Cross-dissolve transitions consume 0.3s from adjacent clips — account for this in trim calculations
- Caption timing must use the word-level timestamps, not scene-level — captions appear word-by-word or phrase-by-phrase
- Background music volume must duck during anchor scenes (voice is dominant) and can be slightly louder during b-roll
- Color grading must be consistent across all clips to avoid jarring visual shifts at scene boundaries

---

## Cost observations

| Component | Observation |
|-----------|-------------|
| ElevenLabs voiceover | ~$0.13 for 34s of audio. Cheap. Multiple regenerations for speed testing are affordable |
| Kling lip-sync | Priced per second of output video. Audio-driven duration means you pay for exactly what you need |
| Kling b-roll | You pay for 5s even if you only use 2s. At scale, this waste adds up — 5 b-roll clips × 5s = 25s generated but only ~19s used (24% waste) |
| Optimization idea | For b-roll, consider generating 10s clips and splitting into two scenes — less waste than two 5s clips where one gets heavily trimmed |

---

## Checklist for future pipeline automation

Before assembly, validate:
- [ ] Every scene's `narration_start`/`narration_end` matches actual word timestamps from the generated audio
- [ ] Audio slices for lip-sync scenes have been cut at exact boundaries
- [ ] All Kling lip-sync clips have the same duration as their input audio (±0.1s tolerance)
- [ ] All b-roll clips are ≥ their scene duration (so trimming is possible)
- [ ] Scene 4 (or any multi-clip b-roll scene) has different images for each sub-clip
- [ ] Cross-dissolve time (0.3s) is accounted for in trim calculations
- [ ] Total timeline duration matches voiceover duration (±0.5s)

---

## Kling lip-sync quality (v2-1) — learned 2026-04-02

### The problem is phoneme accuracy, NOT timing lag

Frame-by-frame analysis of all 4 anchor clips (Scenes 1, 3, 5, 8) revealed that Kling v2-1's lip-sync model does **not** map individual phonemes to correct mouth shapes (visemes). Instead it generates a generic "talking" oscillation — the mouth opens and closes rhythmically in time with speech cadence, but the shapes are wrong:

- **"F" sounds** (four, Follow, for) never show upper teeth on lower lip
- **"M" sounds** (more) never show closed lips
- **"Y" sounds** (Your) render as wide "O" instead of narrow opening
- **"B" sounds** (brain, bed) don't start with lips pressed together
- The model cycles between ~3-4 generic positions: open, closed, rounded, smile

There is **no startup lag**. Mouth movement begins from frame 1 in every clip. Attempting to fix this with timing offsets (trimming the start of anchor clips) caused worse problems — it clipped the opening word "Your" in Scene 1.

### Excessive eye blinking

Kling v2-1 generates unnaturally frequent eye blinks (~every 400-500ms vs natural ~3-4s). This makes the anchor character look drowsy or distracted. There is no known prompt-level fix for this.

### Video prompts can override lip-sync

**This is the most actionable finding.** When the `video_prompt` includes strong emotional or gestural directions, Kling prioritizes those over lip-sync accuracy:

- **Scene 8** prompt: *"warm natural smile, slight nod, points casually at camera"* → the model grinned through the entire clip, completely ignoring speech. The smile emotion overrode lip movement.
- **Scene 5** prompt: *"leans forward with conviction, holds up one finger then makes a firm slicing gesture, expression shifts from serious to encouraging"* → too many simultaneous instructions. The model split attention between body motion, hand gesture, emotional transition, AND lip-sync. Lip accuracy suffered most.

### Rules for anchor video prompts

1. **Keep prompts minimal.** Let lip-sync be the primary task.
   - Good: *"Woman speaking directly to camera, calm expression, subtle natural movement"*
   - Bad: *"Woman leans forward with conviction, holds up one finger, shifts from serious to encouraging"*
2. **Never describe emotions that conflict with speaking.** "Warm smile" and "speaking" are contradictory — you can't grin and articulate at the same time.
3. **Avoid multi-gesture choreography.** One subtle gesture is fine (e.g., "slight hand gesture"). A sequence ("holds up finger THEN makes slicing gesture THEN shifts expression") overloads the model.
4. **Separate gesture from lip-sync when possible.** If you need specific body language, consider generating the base video (image-to-video with gesture prompt) first, THEN applying lip-sync as a separate step. This lets each model focus on one job.

### Improvement options for future reels

| Option | Quality | Cost | Complexity |
|--------|---------|------|------------|
| Better Kling prompts (rules above) | Moderate improvement | Free | Low |
| Kling newer model (v2-master or v3 when available) | Unknown — test when available | Same | Low |
| Post-process with Wav2Lip / SadTalker | Best phoneme accuracy | GPU time or API cost | Medium — adds pipeline step |
| Reduce anchor screen time, increase b-roll | Hides the problem | Free | Low — script adjustment |

### Background music generation

- ElevenLabs Music API can generate vocals/lyrics by default
- **Always include** "instrumental only, no vocals, no lyrics, no singing, no humming" in the prompt
- The prompt structure that works: start with exclusions, then genre/BPM, then scene-by-scene mood description

---

## Voice selection and regeneration — learned 2026-04-02

### Auto voice selection works via `execution/select_voice.py`

Two-pass approach:
1. **Library search** — queries ElevenLabs `/v1/shared-voices` with structured filters (gender, accent, age) + keyword search. Broadens progressively if too few results (drops category filter, then search text). Gemini ranks candidates against the character profile.
2. **Fallback** — generates a custom AI voice via `/v1/text-to-voice/create-previews` if library search yields poor matches.

Preview downloads from the voice library are **free** (no credits). Credits are only spent on TTS generation.

### Voice settings matter as much as voice selection

The original settings produced feeble output even with a decent voice ID:
- `stability: 0.5`, `similarity_boost: 0.75`, `style: 0.3` → flat, weak delivery

Updated to stronger settings:
- `stability: 0.6`, `similarity_boost: 0.80`, `style: 0.6` → more expressive, authoritative

**Rule:** For confident/authoritative characters, use `style ≥ 0.5` and `stability ≥ 0.6`. Low style (< 0.3) produces monotone/feeble output regardless of voice choice.

### Gemini ranking prompt must explicitly reject weak voices

The ranking prompt should:
- Explicitly reject voices described as "soft", "gentle", "whisper", "ASMR", "soothing", "breathy"
- Prefer voices described as "clear", "confident", "strong", "authoritative", "professional", "bold"
- This is critical — ElevenLabs library has many ASMR/whisper voices that match gender/accent filters but produce unusable output for authoritative content

### Changing voice mid-pipeline causes timing drift — but it's not a structural problem

- Different voices speak at different speeds. Switching from voice A to voice B changes total duration (e.g., 33.86s → 30.9s)
- The assembly pipeline uses `narration_start`/`narration_end` timestamps from the script JSON to trim clips
- Since the pipeline is **audio-first** (voiceover → timestamps → audio slices → video generation → assembly), changing voice requires:
  1. Re-extract word timestamps
  2. Update `narration_start`/`narration_end` in script JSON
  3. Re-slice audio for anchor scenes
  4. **Re-generate lip-sync videos** (because anchor clips are driven by audio slices)
- B-roll clips do NOT need regeneration — they're trimmed to whatever duration is needed
- **Rule:** Voice selection should happen BEFORE video generation. If changing voice after videos exist, only b-roll scenes are safe to keep; anchor lip-sync clips must be regenerated
- **Workaround:** ElevenLabs `--speed` param can adjust pacing, but it's unreliable (see speed parameter findings above). A 0.91x speed got 32.4s vs target 33.86s — close but not exact

### ElevenLabs model choice

- `eleven_turbo_v2_5` — faster, more consistent speed control, good for iteration
- `eleven_multilingual_v2` — higher quality but speed parameter is erratic
- **Rule:** Use `eleven_turbo_v2_5` during pipeline development. Consider `eleven_multilingual_v2` for final render if quality delta is noticeable

---

## Update log

| Date | Session | What was learned |
|------|---------|-----------------|
| 2026-04-01 | Session 2 | Initial findings from first manual video build. ElevenLabs speed behavior, Kling duration constraints, scene boundary alignment rules, multi-clip stitching strategy |
| 2026-04-02 | Session 3 | Kling v2-1 lip-sync is phoneme-inaccurate (not a timing issue). Video prompts with strong emotions/gestures override lip-sync. Keep anchor prompts minimal. Excessive blink rate (~2x/sec). Background music needs explicit "no vocals" in prompt |
| 2026-04-02 | Session 5 | Voice selection auto-pipeline built (`select_voice.py`). Voice settings (style, stability) matter as much as voice ID. Changing voice mid-pipeline causes timing drift — not structural but requires re-slicing and re-generating anchor clips. Voice selection must happen before video generation |
| 2026-04-02 | Session 6 | Kling v3 confirmed working via API (`kling-v3` model_name). Native audio (`sound=on`) generates perfect lip-sync. Voice Clone and Element endpoints NOT available via API (404 on all paths). Evaluated 6 approaches for v3 lip-sync pipeline — "clone Kling voice into ElevenLabs" approach has FATAL timing mismatch flaw. Recommended Approach B (v3 video-only + existing lip-sync) for immediate use. Full analysis in `directives/lip_sync_pipeline_v3.md`. Lip-sync declared #1 product feature — zero tolerance for mismatch. |
| 2026-04-03 | Session 8 | Upgraded anchor generation to kling-v3 (Approach B). B-roll stays v2-1. Removed 150ms silence prepend from audio slices (no startup lag exists — silence was harmful, inflated ffprobe durations and delayed speech onset). Video duration now `ceil(audio_duration)` with ffprobe-measured `sound_end_time`. Run-based folder structure for video clips (no stale cache). `extract_word_timestamps.py` now updates script JSON timestamps from actual voiceover. Scene 8 CTA text extended past 2s minimum. Base video saved for lip-sync retry. |
