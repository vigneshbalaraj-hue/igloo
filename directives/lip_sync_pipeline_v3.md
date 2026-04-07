# Directive: Lip-Sync Pipeline v3 — Analysis & Design

> **Lip-sync is the #1 product feature.** We do not accept "close enough" lip-sync. If the mouth movements don't match the audio the viewer hears, the reel is broken. Every design decision must be evaluated against this constraint first.

---

## The Proposed Pipeline (v3 native audio + ElevenLabs voice clone)

```
1. Script Generation          → scene-by-scene JSON
2. Image Generation            → anchor.png + b-roll images
3. Anchor Video (kling-v3)     → anchor clips with native voice + lip-sync
4. Extract Voice Sample        → ffmpeg extract audio from anchor clip
5. Clone Voice (ElevenLabs)    → instant voice clone from Kling sample
6. Voiceover (ElevenLabs)      → full narration track with cloned voice
7. Word Timestamps             → per-word timing from voiceover
8. Audio Slicing               → per-scene audio slices
9. B-roll Video (kling-v2-1)   → b-roll clips, no audio
10. Background Music           → ambient track
11. Assembly                   → mute clip audio, overlay voiceover + music + captions
```

---

## CRITICAL FAILURE ANALYSIS

### FAILURE 1: Timing Mismatch (SEVERITY: FATAL)

**This is the single biggest problem with the proposed pipeline.**

Kling v3 generates its own speech at its own pace. ElevenLabs generates speech at a different pace. Even with identical words, the timing will differ:

- Kling says "Your kid spends four hours" in 2.1s
- ElevenLabs says the same words in 2.6s
- Result: mouth closes 0.5s before the audio finishes the phrase

**Why this is worse than it sounds:**

On anchor scenes, the viewer is staring directly at the face. A 0.2s mismatch is noticeable. A 0.5s mismatch is distracting. A 1.0s mismatch looks like a dubbed foreign film.

This isn't a fixable post-production problem. The lip movements are baked into the video pixels. You can't shift them.

**Drift compounds within each clip:**
- Word 1 might be off by 0.1s (tolerable)
- Word 5 might be off by 0.4s (noticeable)
- Word 10 might be off by 0.8s (broken)

The longer the anchor scene, the worse the drift. Scene 5 is 5.19s — that's enough time for severe compounding.

### FAILURE 2: Content Mismatch (SEVERITY: FATAL)

Kling v3 does NOT guarantee it will say our exact script. We put dialogue in the prompt, but:

- The model may paraphrase ("Your child" instead of "Your kid")
- The model may add filler words ("Well, your kid spends...")
- The model may skip words or rearrange
- The model may speak only for part of the clip duration and go silent

Different words = different mouth shapes. Even if timing matched perfectly, "F" in "four" and "TH" in "three" produce completely different visemes. The viewer hears "four" but sees the mouth shape for a different word.

**We have no control over what Kling says.** The prompt is a suggestion, not a command.

### FAILURE 3: Voice Inconsistency Across Anchor Clips (SEVERITY: HIGH)

Each anchor scene is a separate API call. Kling v3 may generate:

- Different voice timbre per clip (higher pitch on Scene 1, lower on Scene 3)
- Different speaking pace per clip
- Different accent or delivery style
- Male voice on one, female on another (unlikely but possible)

We clone the voice from ONE clip (say Scene 1). But clips 3, 5, 8 may have different voices. So:

- The ElevenLabs voiceover matches Scene 1's lip movements reasonably well
- But it's out of sync with Scenes 3, 5, 8 which were generated with different voices

### FAILURE 4: Duration Control (SEVERITY: HIGH)

Current pipeline: anchor clip duration = audio slice duration (exact match, guaranteed).

Proposed pipeline: we request a duration (e.g., 5s) from Kling v3, but:

- Kling's speech may fill only 3s of the 5s clip → 2s of mouth-closed silence
- Or Kling may try to speak for all 5s but our voiceover for that scene is 3.75s
- Assembly trims the video to match scene timing, but the mouth movements don't align with our audio timeline

### FAILURE 5: Scene 8 Duration (SEVERITY: MEDIUM)

Scene 8 narration is 1.68s ("Follow for more like this"). Kling v3 minimum duration is 3s. We must generate 3s and trim, but Kling will try to fill 3s of speech. If Kling speaks slowly to fill 3s, the mouth movements for 1.68s of ElevenLabs audio will be completely misaligned.

### FAILURE 6: Voice Clone Quality (SEVERITY: MEDIUM)

ElevenLabs Instant Voice Clone from a ~4s sample may:

- Not capture the voice accurately (needs 30s+ for Professional Voice Clone)
- Pick up Kling's ambient audio artifacts, room tone, or compression
- Sound "off" compared to Kling's native voice — defeating the purpose

### FAILURE 7: Kling Native Audio Quality (SEVERITY: MEDIUM)

Kling's native speech quality is unknown at scale:

- May sound robotic on longer phrases
- May have pronunciation errors on specific words
- May have inconsistent volume/quality across clips
- The test clip was only 5s — problems may emerge on 3-15s clips

---

## APPROACH COMPARISON

### Approach A: "Naive" v3 clone (the proposed pipeline)

```
kling-v3 (sound=on) → extract audio → clone in ElevenLabs → voiceover → assembly (mute Kling audio)
```

- Lip-sync quality: **POOR** — timing mismatch between Kling lips and ElevenLabs audio
- Voice consistency: **MEDIUM** — clone quality depends on sample
- Automation: **HIGH** — fully automatable
- Cost: ~$5-6 per reel

**Verdict: REJECTED.** Fatal timing mismatch. Lip-sync could be worse than current v2-1 approach because at least v2-1 uses our actual audio timing.

---

### Approach B: v3 video-only + existing lip-sync pipeline

```
kling-v3 (sound=off) → identify-face → advanced-lip-sync (with our ElevenLabs audio slices)
```

- Lip-sync quality: **SAME AS CURRENT** — same post-hoc lip-sync, same phoneme accuracy limits
- Video quality: **BETTER** — v3 base video is higher quality
- Duration flexibility: **BETTER** — v3 supports 3-15s vs v2-1's 5/10
- Automation: **HIGH** — minimal changes to current pipeline
- Cost: ~$5-6 per reel (3 calls per anchor, but flexible duration saves waste)

**Verdict: INCREMENTAL IMPROVEMENT.** Better video quality and flexible duration, but doesn't solve the core lip-sync phoneme problem.

---

### Approach C: Use Kling's native audio directly (the "flip" approach)

```
kling-v3 (sound=on) for anchor → use Kling's audio AS the anchor voiceover → clone voice → ElevenLabs for b-roll narration only → stitch audio
```

How it works:
1. Generate anchor clips with v3 native audio (perfect lip-sync, by construction)
2. Extract audio from anchor clips
3. Clone that voice in ElevenLabs
4. Generate ElevenLabs narration ONLY for the b-roll scenes
5. Assembly: anchor scenes use Kling's native audio (unmuted). B-roll scenes use ElevenLabs audio.
6. The voice timbre matches because ElevenLabs cloned Kling's voice

- Lip-sync quality: **PERFECT on anchor** — lips and audio generated together
- Voice consistency: **GOOD** — depends on clone quality at the Kling→ElevenLabs boundary
- Automation: **MEDIUM** — requires audio stitching logic, transition smoothing

**Problems:**
- Kling may not say our exact script → the WORDS are wrong even if the lips look right
- Audio quality differs between Kling and ElevenLabs segments → audible transition at scene boundaries
- No control over Kling's speaking pace → scene durations may not match our script timings
- Kling voice may vary between anchor clips → multiple voices in the reel

**Verdict: PROMISING BUT UNRELIABLE.** Perfect lip-sync in theory, but no control over spoken content.

---

### Approach D: Kling v3 native audio for EVERYTHING (fully Kling-voiced)

```
kling-v3 multi-shot (sound=on) → single generation with storyboard prompts → use Kling's audio as the entire voiceover
```

- Lip-sync quality: **PERFECT** — generated together
- Voice consistency: **PERFECT** — single generation, one voice throughout
- Content control: **NONE** — Kling speaks whatever it wants
- Duration control: **LIMITED** — multi-shot duration per shot, but no word-level control
- Automation: **HIGH** — single API call for all anchor content

**Problems:**
- Cannot guarantee Kling says our exact script (FATAL for an informational reel)
- B-roll scenes still need narration — Kling can't narrate over image-to-video b-roll
- Multi-shot is limited to 15s total — our anchor content is ~13s, tight fit
- One failed generation = redo everything

**Verdict: INTERESTING FOR FUTURE, NOT VIABLE NOW.** No content control means the reel says whatever Kling wants.

---

### Approach E: Kling v3 video-only + dedicated lip-sync service (HeyGen/Wav2Lip/SadTalker)

```
kling-v3 (sound=off) → external lip-sync (driven by our ElevenLabs audio) → assembly
```

- Lip-sync quality: **BEST** — dedicated models (Wav2Lip, SadTalker) have better phoneme mapping than Kling's post-hoc lip-sync
- Voice consistency: **PERFECT** — our ElevenLabs voice throughout
- Video quality: **GOOD** — v3 base, but lip-sync overlay may degrade face region
- Automation: **MEDIUM** — adds external API dependency
- Cost: **HIGHER** — Kling + HeyGen/external

**Verdict: BEST LIP-SYNC QUALITY but adds complexity and cost.**

---

### Approach F: Hybrid — Approach C with forced script matching

```
kling-v3 (sound=on) → extract audio → speech-to-text → compare to script → if match score > 90%: use native audio for that scene. If not: fall back to Approach B for that scene
```

- Generate each anchor clip with v3 native audio
- Run Whisper/STT on the extracted audio
- Compare transcript to our script
- If Kling said the right words: use its audio directly (perfect lip-sync)
- If Kling said wrong words: fall back to v3 video-only + lip-sync overlay

Per-scene decision, not all-or-nothing.

- Lip-sync quality: **PERFECT on matched scenes, MEDIOCRE on fallback scenes**
- Voice consistency: **COMPLEX** — matched scenes have Kling's voice, fallback scenes have ElevenLabs
- Automation: **MEDIUM** — STT comparison + branching logic
- Cost: **MEDIUM** — some scenes use 1 call, others use 3

**Verdict: CLEVER BUT FRAGILE.** The voice switches between Kling and ElevenLabs depending on the scene. Viewer will notice.

---

## RECOMMENDATION

**No single approach solves everything today.** Here's what I recommend:

### Short-term (this reel): Approach B — v3 video-only + existing lip-sync

Why:
- Least risk. Same pipeline, just swap `kling-v2-1` for `kling-v3` in anchor generation
- Better video quality (v3 > v2-1)
- Flexible duration (3-15s, no more 5/10 rigidity)
- Lip-sync quality is the same as today — not perfect, but known and controllable
- Change is literally one line: `"model_name": "kling-v2-1"` → `"model_name": "kling-v3"`

### Medium-term: Approach C with verification — forced script matching

Why:
- Perfect lip-sync on scenes where Kling cooperates
- Graceful fallback on scenes where it doesn't
- Building the STT verification pipeline is reusable infrastructure

### Long-term: Wait for Kling Voice Clone API

When Kling exposes Voice Clone via API:
- Clone our ElevenLabs voice into Kling
- Use v3 + `voice_list` + `sound=on`
- Perfect lip-sync + our voice + our script (via prompt) + our timing

---

## OPEN QUESTIONS (require testing)

1. Does Kling v3 with `sound=off` still generate natural mouth movements (lip-sync-ready) or does it generate a static/closed mouth?
2. Does the existing `identify-face` → `advanced-lip-sync` pipeline work on v3-generated videos?
3. What is the actual Kling v3 native audio word accuracy rate vs our prompt?
4. Does v3 multi-shot maintain voice consistency across shots?
5. Can we pass longer/more specific dialogue in the prompt to improve content accuracy?

---

## Update log

| Date | What |
|------|------|
| 2026-04-02 | Initial analysis. Six approaches evaluated. Approach B recommended for immediate use. Lip-sync declared #1 product feature — no compromises. |
