"""
generate_music.py — Generate background music via ElevenLabs Music API.

Reads music specs from script JSON and generates a background track.

Usage:
    py execution/generate_music.py .tmp/screen_addiction_children/screen_addiction_36s_script.json

Output:
    {script_dir}/background_music.mp3
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path


def load_env(key: str) -> str:
    """Load a key from process env or .env file in project root."""
    # 1. Process environment (Modal secrets, CI, shell exports) — preferred
    val = os.environ.get(key)
    if val and not val.startswith("<"):
        return val
    # 2. Fall back to .env file (local dev convenience)
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith(f"{key}="):
                    v = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if v and not v.startswith("<"):
                        return v
    print(f"ERROR: {key} not set in environment or .env", file=sys.stderr)
    sys.exit(1)


def generate_music(prompt: str, duration_ms: int, api_key: str, output_path: Path):
    """Call ElevenLabs Music Compose API. Retries 3x on 5xx/429/timeouts."""
    from http_retry import retry_with_backoff, RetryExhaustedError

    url = "https://api.elevenlabs.io/v1/music/compose"

    payload = {
        "prompt": prompt,
        "music_length_ms": duration_ms,
    }

    data = json.dumps(payload).encode()

    def _open_request():
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("xi-api-key", api_key)
        req.add_header("Content-Type", "application/json")
        return urllib.request.urlopen(req, timeout=300)

    print(f"Generating music ({duration_ms}ms)...")
    print(f"Prompt: {prompt[:120]}...")

    try:
        resp_cm = retry_with_backoff(_open_request, label="elevenlabs-music")
    except RetryExhaustedError as e:
        print(f"ERROR: ElevenLabs Music failed after retries: {e}", file=sys.stderr)
        print("ERROR_CODE: MUSIC_FAILED", file=sys.stderr)
        sys.exit(1)
    except urllib.error.HTTPError as e:
        # 4xx (e.g. copyrighted content) — not retryable. Fall through to
        # existing handler below, which prints prompt_suggestion.
        error_body = ""
        try:
            error_body = e.read().decode()
        except Exception:
            pass
        print(f"ERROR {e.code}: {error_body}", file=sys.stderr)
        try:
            err = json.loads(error_body)
            if "prompt_suggestion" in err:
                print(f"\nSuggested prompt: {err['prompt_suggestion']}")
        except json.JSONDecodeError:
            pass
        print("ERROR_CODE: MUSIC_FAILED", file=sys.stderr)
        sys.exit(1)

    with resp_cm as resp:
        content_type = resp.headers.get("Content-Type", "")

        if "audio" in content_type or "octet-stream" in content_type:
            # Response is raw audio bytes
            audio_bytes = resp.read()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(audio_bytes)
            print(f"Music saved: {output_path} ({len(audio_bytes) / 1024:.1f} KB)")
            return

        # Response is JSON (may contain base64 audio or generation ID)
        result = json.loads(resp.read().decode())

        # Check for base64 audio in response
        audio_b64 = result.get("audio_base64") or result.get("audio")
        if audio_b64:
            import base64
            audio_bytes = base64.b64decode(audio_b64)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(audio_bytes)
            print(f"Music saved: {output_path} ({len(audio_bytes) / 1024:.1f} KB)")
            return

        # If we get a generation/task ID, we need to poll
        gen_id = result.get("generation_id") or result.get("id") or result.get("task_id")
        if gen_id:
            print(f"Generation started, ID: {gen_id}")
            poll_and_download(gen_id, api_key, output_path)
            return

        # Unknown response format
        print(f"Unexpected response: {json.dumps(result, indent=2)[:500]}", file=sys.stderr)
        print("ERROR_CODE: MUSIC_FAILED", file=sys.stderr)
        sys.exit(1)


def poll_and_download(gen_id: str, api_key: str, output_path: Path):
    """Poll for music generation completion and download."""
    import time

    poll_url = f"https://api.elevenlabs.io/v1/music/compose/{gen_id}"
    max_attempts = 60  # 5 minutes at 5s intervals

    for attempt in range(max_attempts):
        time.sleep(5)
        req = urllib.request.Request(poll_url, method="GET")
        req.add_header("xi-api-key", api_key)

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                content_type = resp.headers.get("Content-Type", "")

                if "audio" in content_type or "octet-stream" in content_type:
                    audio_bytes = resp.read()
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(output_path, "wb") as f:
                        f.write(audio_bytes)
                    print(f"\nMusic saved: {output_path} ({len(audio_bytes) / 1024:.1f} KB)")
                    return

                result = json.loads(resp.read().decode())
                status = result.get("status", "unknown")
                print(f"  Polling ({attempt+1}/{max_attempts}): {status}")

                if status in ("completed", "done", "succeeded"):
                    # Try to get audio URL or base64
                    audio_url = result.get("audio_url") or result.get("url") or result.get("output_url")
                    if audio_url:
                        download_file(audio_url, output_path)
                        return

                    audio_b64 = result.get("audio_base64") or result.get("audio")
                    if audio_b64:
                        import base64
                        audio_bytes = base64.b64decode(audio_b64)
                        with open(output_path, "wb") as f:
                            f.write(audio_bytes)
                        print(f"Music saved: {output_path} ({len(audio_bytes) / 1024:.1f} KB)")
                        return

                elif status in ("failed", "error"):
                    print(f"Generation failed: {result}", file=sys.stderr)
                    sys.exit(1)

        except urllib.error.HTTPError as e:
            if e.code == 404:
                print(f"  Polling ({attempt+1}): not ready yet...")
            else:
                print(f"  Poll error {e.code}: {e.read().decode()[:200]}")

    print("ERROR: Timed out waiting for music generation", file=sys.stderr)
    sys.exit(1)


def download_file(url: str, output_path: Path):
    """Download a file from URL."""
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(data)
    print(f"Music downloaded: {output_path} ({len(data) / 1024:.1f} KB)")


def build_prompt(music_spec: dict) -> str:
    """Build a music generation prompt from script spec."""
    description = music_spec.get("description", "")
    bpm = music_spec.get("bpm", "")
    genre = music_spec.get("genre", "")

    prompt = f"{genre}, {bpm} BPM. {description} Instrumental only, no vocals, no singing, no humming."
    return prompt


def main():
    parser = argparse.ArgumentParser(description="Generate background music via ElevenLabs")
    parser.add_argument("script", help="Path to script JSON file")
    parser.add_argument("--prompt", help="Override music prompt (instead of reading from script)")
    parser.add_argument("--duration-ms", type=int, help="Override duration in ms")
    args = parser.parse_args()

    script_path = Path(args.script)
    if not script_path.exists():
        print(f"ERROR: Script not found: {script_path}", file=sys.stderr)
        sys.exit(1)

    with open(script_path, encoding="utf-8") as f:
        script = json.load(f)

    # Get music spec from script
    music_spec = script.get("audio", {}).get("background_music", {})
    if not music_spec and not args.prompt:
        print("ERROR: No background_music spec in script JSON and no --prompt given", file=sys.stderr)
        sys.exit(1)

    prompt = args.prompt or build_prompt(music_spec)
    total_duration = script.get("actual_duration_seconds", 34)
    duration_ms = args.duration_ms or int(total_duration * 1000)

    api_key = load_env("ELEVENLABS_API_KEY")
    output_path = script_path.parent / "background_music.mp3"

    if output_path.exists():
        print(f"Music already exists: {output_path}")
        print("Delete it to regenerate.")
        return

    generate_music(prompt, duration_ms, api_key, output_path)


if __name__ == "__main__":
    main()
