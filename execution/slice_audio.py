"""
slice_audio.py — Slice voiceover.mp3 into per-scene audio clips for Kling lip-sync.

Uses ffmpeg (must be on PATH). No Python dependencies.

Usage:
    py execution/slice_audio.py .tmp/screen_addiction_children/screen_addiction_36s_script.json

Output:
    {script_dir}/audio_slices/scene1.mp3
    {script_dir}/audio_slices/scene3.mp3
    {script_dir}/audio_slices/scene5.mp3
    {script_dir}/audio_slices/scene8.mp3
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

# Use local ffmpeg if available (tools/ directory in project root)
FFMPEG = str(Path(__file__).resolve().parent.parent / "tools" / "ffmpeg.exe")
if not Path(FFMPEG).exists():
    FFMPEG = "ffmpeg"  # fall back to PATH

# Session 7 analysis proved there is NO lip-sync startup lag in Kling.
# The previous 150ms silence prepend was harmful — it delayed speech onset
# and inflated ffprobe-measured durations used for v3 video generation.
LIP_SYNC_SILENCE_MS = 0


def extract_anchor_slices(script: dict) -> list:
    """Parse script JSON and return list of {scene_id, start, end} for anchor scenes."""
    slices = []
    for scene in script["scenes"]:
        if scene["type"] == "anchor":
            vg = scene.get("video_generation", {})
            audio_slice = vg.get("audio_slice")
            if audio_slice:
                slices.append({
                    "scene_id": scene["scene_id"],
                    "start": audio_slice[0],
                    "end": audio_slice[1],
                    "duration": round(audio_slice[1] - audio_slice[0], 3)
                })
    return slices


def slice_audio(voiceover_path: Path, output_dir: Path, slices: list):
    """Use ffmpeg to extract audio segments for lip-sync."""
    output_dir.mkdir(parents=True, exist_ok=True)

    for s in slices:
        sid = s["scene_id"]
        out_path = output_dir / f"scene{sid}.mp3"

        start = s["start"]
        duration = s["duration"]

        cmd = [
            FFMPEG, "-y",
            "-i", str(voiceover_path),
            "-ss", f"{start:.3f}",
            "-t", f"{duration:.3f}",
            "-c:a", "libmp3lame",
            "-q:a", "2",
            str(out_path)
        ]

        print(f"  Scene {sid}: {start:.2f}s -> {s['end']:.2f}s ({duration:.2f}s)")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired:
            print(f"    FFMPEG TIMEOUT slicing scene {sid}", file=sys.stderr)
            print("ERROR_CODE: FFMPEG_TIMEOUT", file=sys.stderr)
            sys.exit(1)
        if result.returncode != 0:
            print(f"    FFMPEG ERROR: {result.stderr[:300]}", file=sys.stderr)
            continue

        print(f"    Saved: {out_path}")


def main():
    parser = argparse.ArgumentParser(description="Slice voiceover into per-scene audio clips")
    parser.add_argument("script", help="Path to script JSON file")
    args = parser.parse_args()

    script_path = Path(args.script)
    if not script_path.exists():
        print(f"ERROR: Script not found: {script_path}", file=sys.stderr)
        sys.exit(1)

    with open(script_path, encoding="utf-8") as f:
        script = json.load(f)

    voiceover_path = script_path.parent / "voiceover.mp3"
    if not voiceover_path.exists():
        print(f"ERROR: Voiceover not found: {voiceover_path}", file=sys.stderr)
        sys.exit(1)

    slices = extract_anchor_slices(script)
    print(f"Slicing voiceover into {len(slices)} anchor clips...")

    output_dir = script_path.parent / "audio_slices"
    slice_audio(voiceover_path, output_dir, slices)

    print(f"\nDone. Audio slices saved to {output_dir}")


if __name__ == "__main__":
    main()
