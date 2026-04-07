# Directive: Automated Reel Factory Pipeline

> Single-command pipeline that generates a reel from theme + topic to final video.
> Last updated: 2026-04-03 (Session 14)
> Previous manual pipeline: `directives/archive/pipeline_order_manual.md`

## Quick Start

```bash
# New reel from scratch:
py execution/run_pipeline.py --new --theme "Health & Wellness" --topic "Fasting when sick" --speed 1.3

# New reel with your own narration:
py execution/run_pipeline.py --new --theme "Tennis" --topic "Forehand technique" --script-text "The forehand is..."

# From existing script JSON:
py execution/run_pipeline.py .tmp/fasting_healing/fasting_healing_40s_script.json --speed 1.3

# Dry run (show what would happen):
py execution/run_pipeline.py .tmp/topic/script.json --dry-run

# Skip all gates (fully automated):
py execution/run_pipeline.py .tmp/topic/script.json --auto-go

# Resume from a specific step:
py execution/run_pipeline.py .tmp/topic/script.json --start-from 5
```

## CLI Flags

| Flag | Default | Purpose |
|------|---------|---------|
| `--new` | - | Start from Step 0 (script generation) |
| `--theme` | - | Theme category (required with `--new`) |
| `--topic` | - | Specific topic (required with `--new`) |
| `--script-text` | - | User narration (optional with `--new`) |
| `--speed` | 1.0 | Voiceover speed multiplier |
| `--audio-mode` | option-c | Assembly audio: `original`, `option-a`, `option-c` |
| `--no-captions` | false | Skip caption burn-in |
| `--start-from N` | 0 or 1 | Start from step N (0-8) |
| `--auto-go` | false | Skip all gates |
| `--dry-run` | false | Show plan without executing |

## Pipeline Steps (0-8)

### Step 0: Script Generation -- `execution/generate_script.py`

Interactive, Gemini-powered script creation with 4 sub-steps:

| Sub-step | What happens | User action |
|----------|-------------|-------------|
| **0a** Theme + Topic | Display theme/topic, create output dir | Automatic |
| **0b** Narration | Gemini generates or adapts user script into scenes | Approve / Edit / Regenerate |
| **0c** Character | Gemini suggests 3 character options (description + image prompt + voice) | Pick 1-3 / Custom / Regenerate |
| **0d** Full JSON | Gemini assembles complete script with all prompts | Approve / Edit / Regenerate |

**Output:** `.tmp/{topic_slug}/{topic_slug}_script.json`

**Standalone usage:**
```bash
py execution/generate_script.py --theme "Health & Wellness" --topic "Fasting when sick"
py execution/generate_script.py --theme "Parenting" --topic "Raising confident child" --duration 35
py execution/generate_script.py --theme "Tennis" --topic "Forehand" --script "The forehand is the most important shot..."
```

**Skip condition:** Script JSON already exists at expected path.

---

### Step 1: Voice Selection -- `execution/select_voice.py`
- **Command:** `select_voice.py <script> --auto`
- **Output:** Updates `.env ELEVENLABS_VOICE_ID` + script JSON
- **Skip if:** `ELEVENLABS_VOICE_ID` already set in `.env`

### Step 2: Voiceover -- `execution/generate_voiceover.py`
- **Command:** `generate_voiceover.py <script> --speed {speed}`
- **Output:** `voiceover.mp3` + `voiceover_timestamps.json`
- **Skip if:** `voiceover.mp3` exists

### Step 3: Timestamp Extraction -- `execution/extract_word_timestamps.py`
- **Command:** `extract_word_timestamps.py <timestamps_json> --update-script <script>`
- **Output:** `voiceover_words.json` + updates script JSON in-place
- **THIS IS THE SINGLE SOURCE OF TRUTH FOR ALL TIMING.**
- **Skip if:** `voiceover_words.json` exists AND script has `narration_start` fields

### Step 4: Audio Slicing -- `execution/slice_audio.py`
- **Command:** `slice_audio.py <script>`
- **Output:** `audio_slices/scene{N}.mp3` per anchor scene
- **Skip if:** `audio_slices/` has correct number of files

### Step 5: Image Generation -- `execution/generate_images.py`
- **Command:** `generate_images.py <script>`
- **Output:** `images/anchor.png` + `images/broll_scene{N}.png`
- **Skip if:** All expected images exist

### Step 6: Video Clip Generation -- `execution/generate_video_clips.py`
- **Command:** `generate_video_clips.py <script>`
- **Output:** `video_clips/run_YYYYMMDD_HHMMSS/` + `.latest` pointer
- B-roll: Kling v2-1, 5s, image-to-video
- Anchor: Avatar API, 1-step lip-sync (image + audio -> video)
- **Skip if:** `.latest` run folder has all expected clips

### Step 7: Background Music -- `execution/generate_music.py`
- **Command:** `generate_music.py <script>`
- **Output:** `background_music.mp3`
- **Skip if:** `background_music.mp3` exists

### Step 8: Assembly -- `execution/assemble_video.py`
- **Command:** `assemble_video.py <script> --audio-mode {mode} [--no-captions]`
- **Output:** `final_reel_optionc.mp4` (or other suffix based on audio mode)
- **Never skipped** -- always runs fresh

## Dependency Graph

```
Step 0: Script Generation (interactive, Gemini)
  |
  v
Step 1: Voice Selection --> Step 2: Voiceover --> Step 3: Timestamps --> Step 4: Audio Slicing --\
                                                                                                  |
Step 5: Image Generation (can run parallel with 1-4) -----------------------------------------> Step 6: Video Clips
                                                                                                  |
Step 7: Background Music (can run parallel with 1-6) ------------------------------------------> Step 8: Assembly
```

## Gate System

After every step, the orchestrator pauses:
```
=======================================================
  Step 2 (Voiceover) COMPLETED -- 12.3s
  Outputs:
    - voiceover.mp3 (234 KB)
    - voiceover_timestamps.json (12 KB)

  Next: Step 3 -- Timestamp Extraction
_______________________________________________________
  [G]o  [S]kip next  [Q]uit:
```

- **GO** (g / Enter): proceed to next step
- **SKIP**: skip the next step
- **QUIT**: stop pipeline, print summary
- **`--auto-go`**: skips all gates automatically

## State Persistence

Each run writes `pipeline_state.json` in the topic directory:
```json
{
  "script_path": ".tmp/topic/script.json",
  "started_at": "2026-04-03T12:00:00",
  "steps": {
    "1": {"status": "completed", "elapsed_seconds": 12.3, "outputs": [...]},
    "2": {"status": "skipped", "reason": "voiceover.mp3 exists"}
  }
}
```

If the pipeline crashes, this file shows exactly where it stopped. Use `--start-from N` to resume.

## Error Handling

- Step fails -> prompt: `[R]etry` or `[Q]uit`
- `--auto-go` mode: abort on first failure (no auto-retry for paid APIs)
- Ctrl+C: saves state, prints summary, exits

## Key Constraints

| Constraint | Detail |
|---|---|
| Audio is source of truth | Video conforms to audio timing, never reverse |
| Lip-sync is #1 quality gate | Zero tolerance for mismatch |
| Minimum anchor audio | >= 2000ms (Avatar API minimum) |
| Anchor video prompts | Keep minimal -- strong gestures override lip-sync |
| Avatar audio padding | +46-47ms AAC. Option C trims this. Safety guards validate. |
| B-roll durations | Kling: 5s or 10s. Trimmed during assembly. |
| Image prompts | Concrete visual descriptions only. No abstract emotional cues. |
| Vegan content | All food imagery must be vegan |
| No vocals in music | Enforced by hardcoded suffix in generate_music.py |

## Examples

```bash
# Health reel from scratch
py execution/run_pipeline.py --new --theme "Health & Wellness" --topic "Fasting when sick" --speed 1.3

# Tennis reel with user script
py execution/run_pipeline.py --new --theme "Tennis" --topic "Forehand technique" --script-text "The forehand is the most important shot in tennis. Here's why most players get it wrong."

# Parenting reel
py execution/run_pipeline.py --new --theme "Parenting" --topic "Raising confident child"

# Re-run assembly only on existing project
py execution/run_pipeline.py .tmp/fasting_healing/fasting_healing_40s_script.json --start-from 8

# Full automated run (no gates)
py execution/run_pipeline.py .tmp/topic/script.json --auto-go --speed 1.3
```
