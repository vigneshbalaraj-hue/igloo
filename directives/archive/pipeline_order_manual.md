# Directive: Reel Factory Pipeline Order

> The canonical execution order for generating a reel from script to final video.
> Last updated: 2026-04-03 (Session 8)

## Pipeline Steps

### 1. Script Generation (Gemini)
- **Output:** Scene-by-scene JSON with narration text, image/video prompts, character profile
- **Key fields:** `narration_text`, `video_generation`, `anchor_character`, `audio.voice_over.full_script`

### 2. Voice Selection — `execution/select_voice.py`
- **Input:** Script JSON
- **Output:** Updates script JSON `voice.elevenlabs_voice_id` + `.env ELEVENLABS_VOICE_ID`
- **How:** Searches ElevenLabs shared library with structured filters, Gemini ranks candidates. Fallback: generates custom AI voice.
- **Note:** Must happen BEFORE voiceover generation. Changing voice after video generation requires re-running steps 3-9.

### 3. Voiceover Generation — `execution/generate_voiceover.py`
- **Input:** Script JSON (reads `full_script` + voice ID from `.env`)
- **Output:** `voiceover.mp3` + `voiceover_timestamps.json` (character-level)
- **Model:** `eleven_turbo_v2_5`

### 4. Word Timestamp Extraction + Script Update — `execution/extract_word_timestamps.py`
- **Input:** `voiceover_timestamps.json` + script JSON
- **Output:** `voiceover_words.json` (word-level) + **UPDATES script JSON in-place**
- **Command:** `py execution/extract_word_timestamps.py .tmp/.../voiceover_timestamps.json --update-script .tmp/.../script.json`
- **Updates:** `narration_start`, `narration_end`, `scene_duration`, `audio_slice`, `actual_duration_seconds`
- **THIS IS THE SINGLE SOURCE OF TRUTH FOR ALL TIMING.** After this step, the script JSON reflects the real voiceover audio.

### 5. Audio Slicing — `execution/slice_audio.py`
- **Input:** Script JSON + `voiceover.mp3`
- **Output:** `audio_slices/scene{N}.mp3` for each anchor scene
- **Note:** No silence prepend. Clean slices at exact word boundaries from step 4.

### 6. Image Generation — `execution/generate_images.py`
- **Input:** Script JSON
- **Output:** `images/anchor.png` + `images/broll_scene{N}.png`
- **Model:** Imagen 4 via Gemini API
- **Note:** Single anchor image reused across all anchor scenes.

### 7. Video Clip Generation — `execution/generate_video_clips.py`
- **Input:** Script JSON + images + audio slices
- **Output:** `video_clips/run_YYYYMMDD_HHMMSS/` (fresh folder each run, `.latest` pointer written)

**B-roll clips (1-step):**
- Model: `kling-v2-1`
- Duration: 5s, sound=off
- Trimmed to exact narration window during assembly

**Anchor clips (1-step Avatar API):**
- `POST /v1/videos/avatar/image2video` — image + audio → lip-synced video
- Sends anchor image (base64) + audio slice (base64) + video prompt
- Video duration auto-sized to match audio (~25ms codec padding)
- No fallback — all-or-nothing (no `_base.mp4`)

### 8. Background Music — `execution/generate_music.py`
- **Input:** Script JSON (reads `audio.background_music` spec)
- **Output:** `background_music.mp3`
- **Model:** ElevenLabs Music Compose API
- **Note:** Always include "instrumental only, no vocals" in prompt.

### 9. Assembly — `execution/assemble_video.py`
- **Input:** Script JSON + video clips (from latest run) + voiceover + music
- **Output:** `final_reel.mp4`
- **Process:**
  1. Trim clips to narration windows (anchor clips get any silent tail removed)
  2. Normalize to 1080x1920 @ 30fps
  3. xfade cross transitions (0.3s)
  4. Add voiceover
  5. Mix background music (low volume, fade-out)
  6. Build + burn ASS captions (Kalam Bold, yellow emphasis words)
- **Note:** Always starts fresh — deletes and recreates `assembly_tmp/`.

## Key Constraints

| Constraint | Detail |
|---|---|
| Audio is source of truth | Video conforms to audio, never the other way around |
| Lip-sync is #1 quality gate | Zero tolerance for mismatch. See `directives/av_sync_lessons.md` |
| Lip-sync minimum audio | `sound_end_time` must be >= 2000ms — no anchor scene under 2s |
| Anchor video prompts | Keep minimal — strong emotions/gestures override lip-sync accuracy |
| Avatar API anchor durations | Auto-sized to audio length (~25ms codec padding) |
| Kling v2-1 b-roll durations | 5s or 10s only |
| No stale caches | Video clips use run folders, assembly always starts fresh |

## Quick Run (full pipeline)

```bash
# Assumes script JSON already exists
py execution/select_voice.py .tmp/{topic}/{script}.json --auto
py execution/generate_voiceover.py .tmp/{topic}/{script}.json --speed 1.3
py execution/extract_word_timestamps.py .tmp/{topic}/voiceover_timestamps.json --update-script .tmp/{topic}/{script}.json
py execution/slice_audio.py .tmp/{topic}/{script}.json
py execution/generate_images.py .tmp/{topic}/{script}.json
py execution/generate_video_clips.py .tmp/{topic}/{script}.json
py execution/generate_music.py .tmp/{topic}/{script}.json
py execution/assemble_video.py .tmp/{topic}/{script}.json
```
