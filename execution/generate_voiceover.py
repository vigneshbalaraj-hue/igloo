"""
generate_voiceover.py — Generate voice-over audio with word-level timestamps via ElevenLabs API.

Supports two modes:
  - Scene-by-scene (default): generates each scene separately with per-scene emotion settings,
    then concatenates via ffmpeg. Produces more expressive, natural-sounding voiceovers.
  - Single-pass (--single): generates the full script in one API call. Faster but monotone.

Usage:
    py execution/generate_voiceover.py .tmp/.../script.json --speed 1.15
    py execution/generate_voiceover.py .tmp/.../script.json --speed 1.15 --single
    py execution/generate_voiceover.py .tmp/.../script.json --speed 1.15 --gap 250

Output:
    {script_dir}/voiceover.mp3              — final concatenated audio
    {script_dir}/voiceover_timestamps.json   — character-level timestamps (merged)
    {script_dir}/voiceover_scenes/           — per-scene audio files (scene-by-scene mode)
"""

import argparse
import base64
import json
import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Emotion presets — map to ElevenLabs voice_settings
# ---------------------------------------------------------------------------

EMOTION_PRESETS = {
    "firm":          {"stability": 0.40, "similarity_boost": 0.70, "style": 0.85},
    "urgent":        {"stability": 0.35, "similarity_boost": 0.65, "style": 0.90},
    "contemplative": {"stability": 0.50, "similarity_boost": 0.75, "style": 0.75},
    "informative":   {"stability": 0.50, "similarity_boost": 0.70, "style": 0.80},
    "warm":          {"stability": 0.55, "similarity_boost": 0.75, "style": 0.80},
    "reassuring":    {"stability": 0.50, "similarity_boost": 0.70, "style": 0.85},
    "gentle":        {"stability": 0.55, "similarity_boost": 0.75, "style": 0.75},
    "confident":     {"stability": 0.45, "similarity_boost": 0.70, "style": 0.85},
    "default":       {"stability": 0.45, "similarity_boost": 0.70, "style": 0.80},
}


def load_env(key: str) -> str:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        print(f"ERROR: .env not found at {env_path}", file=sys.stderr)
        sys.exit(1)
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith(f"{key}="):
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                if val and not val.startswith("<"):
                    return val
    print(f"ERROR: {key} not set in .env", file=sys.stderr)
    sys.exit(1)


def find_ffmpeg() -> str:
    for candidate in ["ffmpeg", r"C:\ffmpeg\bin\ffmpeg.exe", r"C:\ProgramData\chocolatey\bin\ffmpeg.exe"]:
        try:
            subprocess.run([candidate, "-version"], capture_output=True, check=True)
            return candidate
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
    print("ERROR: ffmpeg not found", file=sys.stderr)
    sys.exit(1)


def find_ffprobe() -> str:
    for candidate in ["ffprobe", r"C:\ffmpeg\bin\ffprobe.exe", r"C:\ProgramData\chocolatey\bin\ffprobe.exe"]:
        try:
            subprocess.run([candidate, "-version"], capture_output=True, check=True)
            return candidate
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
    print("ERROR: ffprobe not found", file=sys.stderr)
    sys.exit(1)


def get_audio_duration_s(filepath: str) -> float:
    ffprobe = find_ffprobe()
    result = subprocess.run(
        [ffprobe, "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", filepath],
        capture_output=True, text=True
    )
    return float(result.stdout.strip())


# ---------------------------------------------------------------------------
# ElevenLabs TTS — single scene
# ---------------------------------------------------------------------------

def generate_scene_audio(text: str, voice_id: str, api_key: str, emotion: str,
                         speed: float, output_path: Path) -> dict:
    """Generate TTS for a single text segment. Returns alignment dict."""
    import urllib.request
    import urllib.error

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"

    settings = EMOTION_PRESETS.get(emotion, EMOTION_PRESETS["default"]).copy()
    settings["use_speaker_boost"] = True

    payload = {
        "text": text,
        "model_id": "eleven_turbo_v2_5",
        "voice_settings": settings,
    }
    if speed != 1.0:
        payload["speed"] = speed

    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("xi-api-key", api_key)
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"  ERROR {e.code}: {error_body}", file=sys.stderr)
        sys.exit(1)

    audio_b64 = result.get("audio_base64", "")
    if not audio_b64:
        print(f"  ERROR: No audio returned for: {text[:50]}...", file=sys.stderr)
        sys.exit(1)

    audio_bytes = base64.b64decode(audio_b64)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(audio_bytes)

    return result.get("alignment", {})


# ---------------------------------------------------------------------------
# Extract scenes from script JSON
# ---------------------------------------------------------------------------

def extract_narration_segments(script: dict) -> list:
    """Extract ordered narration segments from script, handling sub-clips."""
    segments = []
    for scene in script.get("scenes", []):
        vid = scene.get("video_generation", {})
        emotion = scene.get("voice_emotion", "default")

        # Check for sub-clips (e.g., scene 4 with clips 4a, 4b)
        if "clips" in vid:
            for clip in vid["clips"]:
                text = clip.get("narration_text", "")
                clip_id = clip.get("clip_id", "")
                clip_emotion = clip.get("voice_emotion", emotion)
                if text.strip():
                    segments.append({
                        "id": f"scene{scene['scene_id']}_{clip_id}",
                        "text": text.strip(),
                        "emotion": clip_emotion,
                    })
        else:
            text = scene.get("narration_text", "")
            if text.strip():
                segments.append({
                    "id": f"scene{scene['scene_id']}",
                    "text": text.strip(),
                    "emotion": emotion,
                })
    return segments


# ---------------------------------------------------------------------------
# Scene-by-scene generation + concatenation
# ---------------------------------------------------------------------------

def generate_scene_by_scene(script: dict, voice_id: str, api_key: str,
                            output_dir: Path, speed: float, gap_ms: int):
    """Generate each scene separately, concatenate with ffmpeg."""
    segments = extract_narration_segments(script)
    if not segments:
        print("ERROR: No narration segments found", file=sys.stderr)
        sys.exit(1)

    scenes_dir = output_dir / "voiceover_scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)

    ffmpeg = find_ffmpeg()

    # Generate silence file for inter-scene gaps
    gap_path = scenes_dir / "gap.mp3"
    if gap_ms > 0:
        subprocess.run([
            ffmpeg, "-y", "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=mono",
            "-t", f"{gap_ms / 1000:.3f}", "-q:a", "9", str(gap_path)
        ], capture_output=True, check=True)

    # Generate each segment
    scene_files = []
    all_alignments = []
    cumulative_offset = 0.0

    print(f"\nGenerating {len(segments)} scene segments (voice: {voice_id[:12]}..., speed: {speed}x)")
    print(f"{'='*60}")

    for i, seg in enumerate(segments):
        scene_path = scenes_dir / f"{seg['id']}.mp3"
        emotion = seg["emotion"]
        settings = EMOTION_PRESETS.get(emotion, EMOTION_PRESETS["default"])

        print(f"  [{i+1}/{len(segments)}] {seg['id']} ({emotion}) — \"{seg['text'][:50]}...\"")
        print(f"           stability={settings['stability']}, style={settings['style']}")

        alignment = generate_scene_audio(
            text=seg["text"],
            voice_id=voice_id,
            api_key=api_key,
            emotion=emotion,
            speed=speed,
            output_path=scene_path,
        )

        # Get actual duration via ffprobe
        duration = get_audio_duration_s(str(scene_path))
        print(f"           duration={duration:.2f}s")

        # Offset alignment timestamps
        chars = alignment.get("characters", [])
        starts = alignment.get("character_start_times_seconds", [])
        ends = alignment.get("character_end_times_seconds", [])

        offset_starts = [t + cumulative_offset for t in starts]
        offset_ends = [t + cumulative_offset for t in ends]

        all_alignments.append({
            "characters": chars,
            "character_start_times_seconds": offset_starts,
            "character_end_times_seconds": offset_ends,
        })

        scene_files.append(str(scene_path))
        cumulative_offset += duration

        # Add space separator between scenes so extract_word_timestamps can split at boundaries
        if i < len(segments) - 1:
            space_time = cumulative_offset
            all_alignments.append({
                "characters": [" "],
                "character_start_times_seconds": [space_time],
                "character_end_times_seconds": [space_time],
            })

        # Add gap after each segment (except the last)
        if gap_ms > 0 and i < len(segments) - 1:
            scene_files.append(str(gap_path))
            cumulative_offset += gap_ms / 1000.0

    # Merge all alignments and write timestamps FIRST (before concat, so they survive crashes)
    merged = {"characters": [], "character_start_times_seconds": [], "character_end_times_seconds": []}
    for a in all_alignments:
        merged["characters"].extend(a["characters"])
        merged["character_start_times_seconds"].extend(a["character_start_times_seconds"])
        merged["character_end_times_seconds"].extend(a["character_end_times_seconds"])

    ts_path = output_dir / "voiceover_timestamps.json"
    with open(ts_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)

    # Concatenate with ffmpeg
    print(f"\nConcatenating {len(scene_files)} files...")
    concat_list = scenes_dir / "concat.txt"
    with open(concat_list, "w") as f:
        for sf in scene_files:
            # Use absolute paths with forward slashes for ffmpeg compatibility on Windows
            abs_path = str(Path(sf).resolve()).replace("\\", "/")
            f.write(f"file '{abs_path}'\n")

    audio_path = output_dir / "voiceover.mp3"
    subprocess.run([
        ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-c:a", "libmp3lame", "-q:a", "2", str(audio_path)
    ], capture_output=True, check=True)

    total_duration = get_audio_duration_s(str(audio_path))
    file_size = audio_path.stat().st_size / 1024

    print(f"\n{'='*60}")
    print(f"Audio saved: {audio_path} ({file_size:.1f} KB)")
    print(f"Timestamps saved: {ts_path}")
    print(f"Audio duration: ~{total_duration:.1f}s")
    print(f"Scene audio: {scenes_dir}/")

    return audio_path, ts_path


# ---------------------------------------------------------------------------
# Single-pass generation (legacy)
# ---------------------------------------------------------------------------

def generate_single_pass(script: dict, voice_id: str, api_key: str,
                         output_dir: Path, speed: float):
    """Generate full script in one API call (legacy mode)."""
    full_text = script.get("audio", {}).get("voice_over", {}).get("full_script", "")
    if not full_text:
        print("ERROR: No full_script found in script JSON", file=sys.stderr)
        sys.exit(1)

    print(f"Generating voice-over single-pass ({len(full_text)} chars)...")

    audio_path = output_dir / "voiceover.mp3"
    alignment = generate_scene_audio(
        text=full_text,
        voice_id=voice_id,
        api_key=api_key,
        emotion="default",
        speed=speed,
        output_path=audio_path,
    )

    ts_path = output_dir / "voiceover_timestamps.json"
    with open(ts_path, "w", encoding="utf-8") as f:
        json.dump(alignment, f, indent=2, ensure_ascii=False)

    file_size = audio_path.stat().st_size / 1024
    ends = alignment.get("character_end_times_seconds", [])
    total_duration = max(ends) if ends else 0

    print(f"Audio saved: {audio_path} ({file_size:.1f} KB)")
    print(f"Timestamps saved: {ts_path}")
    print(f"Audio duration: ~{total_duration:.1f}s")

    return audio_path, ts_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate voice-over via ElevenLabs")
    parser.add_argument("script", help="Path to script JSON file")
    parser.add_argument("--speed", type=float, default=1.0, help="Speech speed (e.g., 1.15)")
    parser.add_argument("--single", action="store_true", help="Single-pass mode (no per-scene emotions)")
    parser.add_argument("--gap", type=int, default=200, help="Inter-scene silence in ms (default: 200)")
    args = parser.parse_args()

    script_path = Path(args.script)
    if not script_path.exists():
        print(f"ERROR: Script not found: {script_path}", file=sys.stderr)
        sys.exit(1)

    with open(script_path, encoding="utf-8") as f:
        script = json.load(f)

    api_key = load_env("ELEVENLABS_API_KEY")
    voice_id = load_env("ELEVENLABS_VOICE_ID")
    output_dir = script_path.parent

    if args.single:
        generate_single_pass(script, voice_id, api_key, output_dir, args.speed)
    else:
        generate_scene_by_scene(script, voice_id, api_key, output_dir, args.speed, args.gap)


if __name__ == "__main__":
    main()
