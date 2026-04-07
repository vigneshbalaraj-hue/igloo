# Directive: Integrate Voice Prompt Bank into Igloo Pipeline

> Last updated: 2026-04-07

---

## Goal

Wire `execution/voice_prompt_bank.md` into Igloo's voice generation step so that every reel's narration is emotionally aligned with the script. The voice prompt bank sits between the validated script and ElevenLabs TTS — it reads the script's 4 phases (hook, agitation, reframe, CTA), generates a tailored voice prompt for each, and makes 4 separate TTS calls. The result is per-section audio files with emotion-matched delivery.

**This replaces the current single-call voice generation.** Today: full script → one TTS call → one MP3 → slice. After: script sections → 4 voice-prompted TTS calls → 4 MP3s → stitch → downstream pipeline.

---

## Pipeline Position

### Before (current flow)

```
Script → select_voice.py → generate_voiceover.py → voiceover.mp3 → slice_audio.py → per-scene MP3s
              (voice ID)       (one TTS call)          (one file)      (ffmpeg cut)
```

### After (with voice prompt bank)

```
                                    ┌──────────────────────────────────────┐
                                    │  Voice Prompt Assembly (NEW)         │
                                    │                                      │
Validated   ──▶  Section    ──▶     │  For each section:                   │  ──▶  Stitch  ──▶  voiceover.mp3
Script           Splitter           │  1. Read voice_prompt_bank.md        │       Audio        (combined)
                 (NEW)              │  2. Build base prompt + phase mod    │       (NEW)            │
                                    │  3. Annotate script text             │                        ▼
                                    │  4. Set phase-specific TTS params    │                  Timestamps
                                    │  5. Call ElevenLabs Voice Design     │                  + downstream
                                    │  6. Output: section_N.mp3           │
                                    └──────────────────────────────────────┘
```

**Key change:** The pipeline goes from 1 TTS call to 4 TTS calls per reel, each with a unique voice prompt and TTS parameter set. The stitched output (`voiceover.mp3`) is format-compatible with the existing downstream pipeline — timestamps, slicing, video generation, and assembly see no difference.

---

## Inputs

| Field | Source | Description |
|-------|--------|-------------|
| `validated_script` | Output of script generation + validation (from `integrate_prompt_bank.md`) | The full script, already validated against the script prompt bank |
| `voice_prompt_bank` | `execution/voice_prompt_bank.md` | The voice rulebook — base narrator prompt, phase modifiers, TTS params, annotation rules |

**No new user inputs required.** The voice prompt bank derives everything it needs from the script itself. The user's niche, topic, and tone choices already shaped the script — the voice prompt bank reads the script's emotional arc, not the user's raw input.

---

## Process (Step by Step)

### Step 1: Split the Script into Sections

Parse the validated script into its 4 structural phases:

```python
# Pseudocode — adapt to actual script format
sections = split_script_into_phases(validated_script)
# Returns:
# {
#     "hook":      "Gratitude journaling... is the most popular form of spiritual bypassing on the planet.",
#     "agitation": "Every therapist, every guru, every morning-routine influencer tells you the same thing...",
#     "reframe":   "Gratitude without examination is just mood management...",
#     "cta":       "If this shifted something, follow for the teachings nobody posts about."
# }
```

**How to split:** The script follows the universal structure defined in `execution/prompt_bank.md`:
- **Hook:** First 1-2 sentences (the opening pattern interrupt)
- **Agitation:** Sentences that build the case after the hook, before the reveal
- **Reframe:** The sentences containing the core insight / paradigm shift
- **CTA:** Final 1-2 sentences driving to action

**Splitting logic:** Use an LLM call to identify the boundaries. The 4-phase structure is explicit in the script prompt bank's rules — the script was generated to follow this arc. The LLM reads the script and outputs section boundaries (start/end sentence indices).

**Fallback:** If the LLM can't cleanly split (e.g., the script doesn't follow the 4-phase structure), split by timing approximation:
- Hook: first 15% of word count
- Agitation: next 35%
- Reframe: next 35%
- CTA: final 15%

### Step 2: Annotate Script Text Per Section

Apply the text annotation rules from Part 3 of the voice prompt bank to each section's text.

```python
# Pseudocode
for section_name, section_text in sections.items():
    annotated_text = annotate_for_voice(
        text=section_text,
        phase=section_name,
        rules=voice_prompt_bank.part_3  # Annotation rules per phase
    )
    sections[section_name] = annotated_text
```

**What annotation does:**
- **Hook:** Adds `...` after first clause, ensures `—` for pivots, removes any `!`
- **Agitation:** Adds commas for breath points, ensures progressive sentence shortening
- **Reframe:** Isolates the key insight as its own sentence, uses `.` between punches
- **CTA:** Removes ellipses, removes `!`, ensures period between callback and action

**Implementation:** This can be an LLM call with the annotation rules injected as instructions, or a deterministic regex/NLP script for the mechanical rules (remove `!`, add `...` after first clause). Hybrid recommended: deterministic rules for banned characters, LLM for structural adjustments.

### Step 3: Assemble Voice Prompts Per Section

For each section, construct the full ElevenLabs voice prompt by concatenating:

```
1. Base narrator description (Part 1 of voice_prompt_bank.md)
2. Phase-specific voice modifier (Part 2 of voice_prompt_bank.md)
3. Script-specific word emphasis (generated by LLM reading the section text)
```

**Template for assembled voice prompt:**

```python
def assemble_voice_prompt(section_name, section_text, voice_prompt_bank):
    base = voice_prompt_bank.base_narrator_prompt  # Part 1
    phase_modifier = voice_prompt_bank.phase_modifiers[section_name]  # Part 2
    
    # Generate emphasis callouts for specific words in THIS script
    emphasis_words = identify_emphasis_words(section_text, section_name)
    # e.g., for agitation about turmeric: ["1%", "piperine", "2,000%", "fourteen"]
    
    emphasis_instruction = f"Extra weight on: {', '.join(emphasis_words)}."
    
    return f"{base} {phase_modifier} {emphasis_instruction}"
```

**Word emphasis identification:** Use an LLM call that reads the section text and the niche context to identify 2-4 words/phrases that carry the most argumentative or emotional weight. These are typically:
- Numbers and dates (specificity anchors)
- Names of people, studies, or institutions (authority anchors)
- The single word that embodies the contrarian claim (e.g., "bypassing," "guess," "product")

### Step 4: Set TTS Parameters Per Section

Each section uses the phase-specific TTS parameter overrides from Part 2:

```python
TTS_PARAMS = {
    "hook": {
        "stability": 0.35,
        "similarity_boost": 0.75,
        "style": 0.70,
        "use_speaker_boost": True
    },
    "agitation": {
        "stability": 0.40,
        "similarity_boost": 0.75,
        "style": 0.65,
        "use_speaker_boost": True
    },
    "reframe": {
        "stability": 0.30,
        "similarity_boost": 0.75,
        "style": 0.75,
        "use_speaker_boost": True
    },
    "cta": {
        "stability": 0.50,
        "similarity_boost": 0.75,
        "style": 0.55,
        "use_speaker_boost": True
    }
}
```

**The emotional arc in parameters:**
- **Stability:** 0.35 → 0.40 → 0.30 → 0.50 (dips at reframe for max expression, highest at CTA for natural trust)
- **Style:** 0.70 → 0.65 → 0.75 → 0.55 (peaks at reframe, drops at CTA for authenticity)

### Step 5: Call ElevenLabs Voice Design TTS (Per Section)

Make 4 separate API calls — one per section:

```python
section_audio_files = {}

for section_name in ["hook", "agitation", "reframe", "cta"]:
    response = elevenlabs_text_to_speech(
        text=sections[section_name],           # Annotated script text
        voice_description=voice_prompts[section_name],  # Assembled voice prompt
        model_id="eleven_turbo_v2_5",
        voice_settings={
            "stability": TTS_PARAMS[section_name]["stability"],
            "similarity_boost": TTS_PARAMS[section_name]["similarity_boost"],
            "style": TTS_PARAMS[section_name]["style"],
            "use_speaker_boost": TTS_PARAMS[section_name]["use_speaker_boost"]
        }
    )
    
    output_path = f".tmp/{slug}/voice_sections/{section_name}.mp3"
    save_audio(response, output_path)
    section_audio_files[section_name] = output_path
```

**Important:** ElevenLabs Voice Design creates a new voice from the text description on each call. Since all 4 calls share the same base narrator prompt (Part 1), the voice identity should remain consistent. The phase-specific modifiers change *delivery*, not *identity*.

**If voice consistency drifts between sections:** Generate the voice once using just the base narrator prompt, save the resulting voice ID, then use that voice ID for all 4 sections with per-section voice settings. This sacrifices some per-section voice prompt control but guarantees identity consistency. This is the fallback, not the default.

### Step 6: Stitch Section Audio

Concatenate the 4 section MP3s into a single `voiceover.mp3`:

```python
# Using ffmpeg — matches existing pipeline tooling
stitch_command = f"""
ffmpeg -i "concat:{hook_path}|{agitation_path}|{reframe_path}|{cta_path}" \
    -acodec copy \
    .tmp/{slug}/voiceover.mp3
"""
```

**Crossfade between sections:** Add a 50-100ms crossfade between sections to prevent audible cuts. The voice prompt's pacing descriptions create natural transition points, but a micro-crossfade ensures no hard edges.

```python
# ffmpeg with crossfade
ffmpeg -i hook.mp3 -i agitation.mp3 -i reframe.mp3 -i cta.mp3 \
    -filter_complex "[0][1]acrossfade=d=0.08:c1=tri:c2=tri[a01]; \
                      [a01][2]acrossfade=d=0.08:c1=tri:c2=tri[a012]; \
                      [a012][3]acrossfade=d=0.08:c1=tri:c2=tri" \
    .tmp/{slug}/voiceover.mp3
```

### Step 7: Resume Existing Pipeline

The stitched `voiceover.mp3` is placed in the same location the current pipeline expects it. From here, the existing flow continues unchanged:

```
voiceover.mp3 → extract_word_timestamps.py → slice_audio.py → ... → assembly
```

**No changes to downstream steps.** The stitched MP3 is format-identical to what `generate_voiceover.py` currently produces. Timestamps, slicing, video generation, and assembly see no difference.

---

## Validation

After stitching, before passing downstream:

### Automated Checks

```python
checks = {
    "total_duration": 35 <= duration_seconds(voiceover_mp3) <= 70,  # 40-60s target with tolerance
    "no_silence_gaps": max_silence_gap(voiceover_mp3) < 1.5,  # No dead spots from bad stitching
    "section_count": len(section_audio_files) == 4,  # All 4 sections generated
    "format_match": is_valid_mp3(voiceover_mp3),  # Downstream pipeline expects MP3
}
```

### Manual Verification (Until Automated Quality Gate Exists)

Listen to the stitched `voiceover.mp3` and verify:

1. **Emotional arc is audible:** Hook sounds tense/deliberate, agitation builds, reframe slows with weight, CTA feels warm and definitive
2. **No tonal whiplash between sections:** Transitions feel natural, not like 4 different people
3. **Key words land with emphasis:** The numbers, names, and contrarian claims get extra vocal weight
4. **Pacing varies across sections:** The reel doesn't sound like one monotone narration
5. **No robotic artifacts:** No unnatural pitch jumps, word repetitions, or pronunciation errors

**If voice consistency fails across sections:** Switch to the fallback approach (Step 5 note) — generate voice ID once, reuse across sections with per-section settings only.

---

## Edge Cases

| Scenario | Handling |
|----------|----------|
| **Script doesn't follow 4-phase structure** | Fall back to timing-based split (15/35/35/15). Log a warning — the script should have been validated against the script prompt bank first |
| **ElevenLabs Voice Design produces inconsistent voices across sections** | Switch to fallback: generate voice ID from base prompt once, then use that ID for all 4 calls with per-section voice settings |
| **One section's TTS call fails** | Retry once with slightly higher stability (+0.10). If still fails, generate that section with default parameters and log for review |
| **Stitched audio has audible cuts between sections** | Increase crossfade to 150ms. If still audible, the voice prompts for adjacent sections may be too different — reduce the delta in style/stability between them |
| **Total duration exceeds 70s or falls below 35s** | Likely a script length issue, not a voice issue. Flag for script regeneration. Do not speed up/slow down the voice — that destroys the emotional calibration |
| **CTA voice sounds too different from reframe** | The CTA's stability jump (0.30 → 0.50) is the biggest parameter shift. If jarring, reduce CTA stability to 0.40 as an intermediate step |
| **Script has more than 4 logical sections** | Map to the nearest 4-phase structure. Multiple agitation paragraphs = one agitation section. The voice prompt bank's phases are emotional arcs, not paragraph counts |

---

## Cost Impact

| Current | With Voice Prompt Bank |
|---------|----------------------|
| 1 TTS call per reel | 4 TTS calls per reel |
| ~$0.24 per reel (ElevenLabs TTS) | ~$0.96 per reel (4x TTS calls) |
| + 1 LLM call for voice prompt assembly | ~$0.02 (Gemini Flash) |
| **Total voice cost: ~$0.24** | **Total voice cost: ~$0.98** |

**Net cost increase: ~$0.74 per reel** (from $3.19 → $3.93 total per reel).

This is a 23% cost increase for a qualitative improvement that addresses the #1 known issue after script quality: flat, emotionless voice delivery. The voice is ~50% of the viewer's experience (they hear it the entire time). Spending $0.74 more per reel to make it sound like a Netflix documentary narrator instead of a text-to-speech engine is the highest-ROI spend in the pipeline after the script prompt bank.

**Cost optimization (later):** Once the voice prompt patterns stabilize, identify which sections benefit most from custom prompts. If the CTA consistently sounds fine with default settings, drop it back to 3 calls. Measure before optimizing.

---

## File Dependencies

| File | Role | Location |
|------|------|----------|
| `execution/voice_prompt_bank.md` | Source of truth for all voice generation prompts | This repo (01_Positioning) |
| `execution/prompt_bank.md` | Script prompt bank — scripts generated from this are the INPUT to voice prompt bank | This repo (01_Positioning) |
| `directives/integrate_prompt_bank.md` | Script integration directive — voice integration runs AFTER this | This repo (01_Positioning) |
| Voice generation module | Where the integration code goes (replaces current `generate_voiceover.py`) | Reel Engine repo |

**Dependency chain:** Script prompt bank → script generation → script validation → **voice prompt bank → per-section TTS** → timestamps → slicing → downstream pipeline.

---

## Testing

After integration, generate one test reel and verify:

1. **A/B listen test:** Play the old single-call voiceover vs. the new per-section voiceover back to back. The emotional range difference should be immediately obvious.
2. **Section transition test:** Listen specifically at the boundary between each section pair (hook→agitation, agitation→reframe, reframe→CTA). No audible cuts, no tonal whiplash.
3. **Emphasis test:** Identify the 3 most important words in the script. Play the voiceover. Do those words land with noticeably more vocal weight?
4. **CTA test:** Does the last 5 seconds feel like a natural close, not a sales pitch or an abrupt stop?
5. **Downstream compatibility test:** Run the full pipeline (timestamps → slicing → video → assembly) with the new voiceover. Final reel should have zero lip-sync drift.
