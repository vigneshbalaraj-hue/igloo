# Directive: Analyze Video

## Goal
Extract a detailed, frame-by-frame (1-second interval) breakdown of a video file using Gemini 2.5 Pro's multimodal video understanding. The output is a structured JSON template that serves as a **directorial reference** — detailed enough to recreate the video from scratch.

## Inputs
- Video file path (e.g., `Examples/Example_video.mp4`)
- Analysis duration in seconds (default: 60)

## Tools / Scripts
- `execution/analyze_video.py` — uploads video to Gemini Files API, sends analysis prompt, saves JSON output
- Uses Gemini REST API directly (no SDK dependency)
- Requires `GEMINI_API_KEY` in `.env`

## Process
1. Upload video to Gemini Files API (resumable upload)
2. Wait for file processing to complete (poll status)
3. Send analysis prompt to `gemini-2.5-pro` with the uploaded file
4. Parse response into structured JSON
5. Save to `.tmp/{video_name}_analysis.json`

## Output Schema
```json
{
  "video_file": "Example_video.mp4",
  "analyzed_duration_seconds": 60,
  "total_segments": 60,
  "segments": [
    {
      "segment_id": 1,
      "timestamp": "00:00 - 00:01",
      "visual": {
        "scene_description": "...",
        "camera_angle": "close-up / wide / medium / bird's-eye / over-the-shoulder / etc.",
        "camera_movement": "static / pan left / zoom in / tracking / tilt up / handheld / etc.",
        "screenplay_action": "Detailed action line — what subjects do, enter, exit, gesture, express"
      },
      "audio": {
        "narration_text": "Exact words spoken (empty string if none)",
        "speaker": "narrator / character name / off-screen / etc.",
        "tone_of_voice": "enthusiastic / calm / urgent / whispered / etc.",
        "sound_effects": "Description of non-speech, non-music sounds",
        "music_description": "Genre, mood, instruments, tempo changes"
      }
    }
  ]
}
```

## Prompt Template
The prompt sent to Gemini is embedded in the script. Key instructions:
- Analyze at 1-second intervals
- Describe visuals as a film director would — specific enough to recreate the shot
- Capture ALL audio elements separately: speech, SFX, music
- Use precise film terminology for angles and movements
- Include emotional tone and pacing notes

## Cost
~$0.10-0.20 per minute of video analyzed (Gemini 2.5 Pro pricing).

## Edge Cases / Learnings
- Python 3.14 does not support `google-genai` SDK — use REST API instead
- Correct model name is `gemini-2.5-pro` (not `gemini-2.5-pro-preview-*`)
- Gemini Files API returns `name` as `files/xxx` — use `/v1beta/{name}` not `/v1beta/files/{name}`
- Gemini Files API requires polling for upload processing (can take 10-30s for video)
- Response may need JSON extraction from markdown code blocks
