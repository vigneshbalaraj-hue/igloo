"""
analyze_video.py — Extract frame-by-frame directorial breakdown from a video using Gemini 2.5 Pro.

Uses Gemini REST API directly (no SDK needed). Works with Python 3.14+.

Usage:
    py execution/analyze_video.py Examples/Example_video.mp4 [--duration 60]

Output:
    .tmp/{video_name}_analysis.json
"""

import argparse
import json
import mimetypes
import os
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
GEMINI_MODEL = "gemini-2.5-pro"
GEMINI_UPLOAD_URL = "https://generativelanguage.googleapis.com/upload/v1beta/files"
GEMINI_GENERATE_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)
GEMINI_FILE_URL = "https://generativelanguage.googleapis.com/v1beta/{name}"

POLL_INTERVAL = 5  # seconds between file-processing polls
POLL_TIMEOUT = 300  # max seconds to wait for processing


def load_api_key() -> str:
    """Load GEMINI_API_KEY from .env file in project root."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        print(f"ERROR: .env not found at {env_path}", file=sys.stderr)
        sys.exit(1)

    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("GEMINI_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
                if key and not key.startswith("<"):
                    return key

    print("ERROR: GEMINI_API_KEY not set in .env", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Gemini Files API — upload
# ---------------------------------------------------------------------------

def upload_video(file_path: str, api_key: str) -> dict:
    """Upload a video file to Gemini Files API using resumable upload."""
    file_path = Path(file_path)
    file_size = file_path.stat().st_size
    mime_type = mimetypes.guess_type(str(file_path))[0] or "video/mp4"
    display_name = file_path.stem

    print(f"Uploading {file_path.name} ({file_size / 1024 / 1024:.1f} MB)...")

    # Step 1: Initiate resumable upload
    metadata = json.dumps({"file": {"display_name": display_name}}).encode()
    init_url = f"{GEMINI_UPLOAD_URL}?key={api_key}"

    req = urllib.request.Request(init_url, data=metadata, method="POST")
    req.add_header("X-Goog-Upload-Protocol", "resumable")
    req.add_header("X-Goog-Upload-Command", "start")
    req.add_header("X-Goog-Upload-Header-Content-Length", str(file_size))
    req.add_header("X-Goog-Upload-Header-Content-Type", mime_type)
    req.add_header("Content-Type", "application/json")

    with urllib.request.urlopen(req) as resp:
        upload_url = resp.headers.get("X-Goog-Upload-URL")
        if not upload_url:
            print("ERROR: No upload URL returned", file=sys.stderr)
            sys.exit(1)

    # Step 2: Upload the actual bytes
    with open(file_path, "rb") as f:
        data = f.read()

    req2 = urllib.request.Request(upload_url, data=data, method="PUT")
    req2.add_header("Content-Length", str(file_size))
    req2.add_header("X-Goog-Upload-Offset", "0")
    req2.add_header("X-Goog-Upload-Command", "upload, finalize")

    with urllib.request.urlopen(req2) as resp:
        result = json.loads(resp.read().decode())

    file_info = result.get("file", result)
    print(f"Upload complete. File name: {file_info.get('name', 'unknown')}")
    return file_info


def wait_for_processing(file_name: str, api_key: str) -> dict:
    """Poll until the uploaded file is ACTIVE (processed and ready)."""
    url = GEMINI_FILE_URL.format(name=file_name) + f"?key={api_key}"
    start = time.time()

    while time.time() - start < POLL_TIMEOUT:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            info = json.loads(resp.read().decode())

        state = info.get("state", "UNKNOWN")
        if state == "ACTIVE":
            print("File processing complete.")
            return info
        elif state == "FAILED":
            print(f"ERROR: File processing failed: {info}", file=sys.stderr)
            sys.exit(1)

        print(f"  Processing... (state: {state})")
        time.sleep(POLL_INTERVAL)

    print("ERROR: Timed out waiting for file processing", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Gemini generateContent — video analysis
# ---------------------------------------------------------------------------

ANALYSIS_PROMPT = """\
You are a professional film director and screenwriter analyzing a video for the purpose of creating a detailed directorial reference document.

Analyze the FIRST {duration} SECONDS of this video at 1-SECOND INTERVALS. For each 1-second segment, provide:

**Visual Analysis:**
- scene_description: What is visible in the frame — subjects, objects, background, colors, lighting, text overlays, graphics
- camera_angle: Use precise film terminology (close-up, extreme close-up, medium shot, wide shot, bird's-eye, low angle, high angle, over-the-shoulder, POV, dutch angle, etc.)
- camera_movement: (static, pan left/right, tilt up/down, zoom in/out, dolly in/out, tracking shot, handheld shake, crane, whip pan, etc.)
- screenplay_action: A director's action line — what subjects do, how they move, enter/exit frame, gestures, facial expressions, transitions between shots

**Audio Analysis:**
- narration_text: Exact words spoken in this second (empty string if silence)
- speaker: Who is speaking (narrator, character name, off-screen voice, AI voice, etc.)
- tone_of_voice: Emotional quality of delivery (enthusiastic, calm, urgent, whispered, authoritative, playful, etc.)
- sound_effects: Non-speech, non-music sounds (whoosh, click, pop, ambient noise, transition sound, etc.)
- music_description: Genre, mood, instruments, tempo, and any changes (e.g., "lo-fi hip-hop beat, mellow, soft piano and vinyl crackle" or "silence")

Return ONLY valid JSON (no markdown, no code fences) in this exact structure:
{{
  "video_file": "<filename>",
  "analyzed_duration_seconds": {duration},
  "total_segments": {duration},
  "segments": [
    {{
      "segment_id": 1,
      "timestamp": "00:00 - 00:01",
      "visual": {{
        "scene_description": "...",
        "camera_angle": "...",
        "camera_movement": "...",
        "screenplay_action": "..."
      }},
      "audio": {{
        "narration_text": "...",
        "speaker": "...",
        "tone_of_voice": "...",
        "sound_effects": "...",
        "music_description": "..."
      }}
    }}
  ]
}}

Be extremely specific and detailed. The goal is that another director could recreate this video shot-for-shot using only your JSON output.
"""


def analyze_video(file_uri: str, file_mime: str, video_name: str, duration: int, api_key: str) -> dict:
    """Send the uploaded video to Gemini for analysis."""
    url = GEMINI_GENERATE_URL.format(model=GEMINI_MODEL) + f"?key={api_key}"
    prompt_text = ANALYSIS_PROMPT.format(duration=duration)

    payload = {
        "contents": [
            {
                "parts": [
                    {"file_data": {"mime_type": file_mime, "file_uri": file_uri}},
                    {"text": prompt_text},
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 65536,
        },
    }

    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")

    print(f"Sending analysis request to {GEMINI_MODEL} (this may take 1-3 minutes)...")
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            result = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"ERROR {e.code}: {error_body}", file=sys.stderr)
        sys.exit(1)

    # Extract text from response
    try:
        text = result["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        print(f"ERROR: Unexpected response structure:\n{json.dumps(result, indent=2)}", file=sys.stderr)
        sys.exit(1)

    # Parse JSON — handle markdown code fences if present
    text = text.strip()
    if text.startswith("```"):
        # Remove ```json and trailing ```
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    try:
        analysis = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"WARNING: Could not parse JSON response. Saving raw text.", file=sys.stderr)
        print(f"Parse error: {e}", file=sys.stderr)
        analysis = {"raw_response": text, "parse_error": str(e)}

    return analysis


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Analyze video using Gemini 2.5 Pro")
    parser.add_argument("video", help="Path to video file")
    parser.add_argument("--duration", type=int, default=60, help="Seconds to analyze (default: 60)")
    args = parser.parse_args()

    video_path = Path(args.video)
    if not video_path.exists():
        print(f"ERROR: File not found: {video_path}", file=sys.stderr)
        sys.exit(1)

    api_key = load_api_key()

    # Upload
    file_info = upload_video(str(video_path), api_key)
    file_name = file_info["name"]
    file_uri = file_info["uri"]
    file_mime = file_info.get("mimeType", "video/mp4")

    # Wait for processing
    wait_for_processing(file_name, api_key)

    # Analyze
    analysis = analyze_video(file_uri, file_mime, video_path.name, args.duration, api_key)

    # Save output
    output_dir = Path(__file__).resolve().parent.parent / ".tmp"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"{video_path.stem}_analysis.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)

    print(f"\nAnalysis saved to: {output_path}")
    segment_count = len(analysis.get("segments", []))
    print(f"Segments extracted: {segment_count}")


if __name__ == "__main__":
    main()
