"""
generate_images.py — Generate images via Google Imagen 3 REST API.

Uses Imagen 3 (imagen-3.0-generate-002) through the Gemini API. No SDK needed.

Usage:
    py execution/generate_images.py .tmp/screen_addiction_children/screen_addiction_36s_script.json

Output:
    {script_dir}/images/anchor.png
    {script_dir}/images/broll_scene2.png
    {script_dir}/images/broll_scene4a.png
    {script_dir}/images/broll_scene4b.png
    {script_dir}/images/broll_scene6.png
    {script_dir}/images/broll_scene7.png
"""

import argparse
import base64
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path


API_URL = "https://generativelanguage.googleapis.com/v1beta/models/imagen-4.0-generate-001:predict"


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


def generate_image(prompt: str, api_key: str, aspect_ratio: str = "9:16") -> bytes:
    """Call Imagen 3 API and return PNG bytes."""
    payload = {
        "instances": [{"prompt": prompt}],
        "parameters": {
            "sampleCount": 1,
            "aspectRatio": aspect_ratio,
            "personGeneration": "allow_all"
        }
    }

    data = json.dumps(payload).encode()
    req = urllib.request.Request(f"{API_URL}?key={api_key}", data=data, method="POST")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"  ERROR {e.code}: {error_body[:500]}", file=sys.stderr)
        raise

    predictions = result.get("predictions", [])
    if not predictions:
        raise RuntimeError(f"No predictions returned. Response: {json.dumps(result)[:300]}")

    image_b64 = predictions[0].get("bytesBase64Encoded", "")
    if not image_b64:
        raise RuntimeError(f"No image data in prediction. Keys: {list(predictions[0].keys())}")

    return base64.b64decode(image_b64)


def extract_image_jobs(script: dict) -> list:
    """Parse script JSON and return list of {name, prompt} dicts for all images needed."""
    jobs = []

    for scene in script["scenes"]:
        sid = scene["scene_id"]
        vg = scene.get("video_generation", {})

        # Handle scenes with sub-clips (like scene 4 with 4a/4b)
        if "clips" in vg:
            for clip in vg["clips"]:
                clip_id = clip["clip_id"]
                prompt = clip.get("image_prompt")
                if prompt:
                    jobs.append({"name": f"broll_scene{clip_id}", "prompt": prompt})
        else:
            prompt = vg.get("image_prompt")
            if prompt:
                if scene["type"] == "anchor":
                    # Only need one anchor image (reused across all anchor scenes)
                    if not any(j["name"] == "anchor" for j in jobs):
                        jobs.append({"name": "anchor", "prompt": prompt})
                else:
                    jobs.append({"name": f"broll_scene{sid}", "prompt": prompt})

    return jobs


def main():
    parser = argparse.ArgumentParser(description="Generate images via Imagen 3")
    parser.add_argument("script", help="Path to script JSON file")
    parser.add_argument("--aspect-ratio", default="9:16", help="Aspect ratio (default: 9:16)")
    parser.add_argument("--only", help="Generate only this image name (e.g. 'anchor' or 'broll_scene2')")
    args = parser.parse_args()

    script_path = Path(args.script)
    if not script_path.exists():
        print(f"ERROR: Script not found: {script_path}", file=sys.stderr)
        sys.exit(1)

    with open(script_path, encoding="utf-8") as f:
        script = json.load(f)

    api_key = load_env("GEMINI_API_KEY")
    output_dir = script_path.parent / "images"
    output_dir.mkdir(parents=True, exist_ok=True)

    jobs = extract_image_jobs(script)
    if args.only:
        jobs = [j for j in jobs if j["name"] == args.only]
        if not jobs:
            print(f"ERROR: No image job found with name '{args.only}'", file=sys.stderr)
            sys.exit(1)

    print(f"Generating {len(jobs)} images with Imagen 3 ({args.aspect_ratio})...")
    print()

    for i, job in enumerate(jobs):
        name = job["name"]
        prompt = job["prompt"]
        out_path = output_dir / f"{name}.png"

        # Skip if already exists
        if out_path.exists():
            print(f"[{i+1}/{len(jobs)}] {name} — already exists, skipping")
            continue

        print(f"[{i+1}/{len(jobs)}] {name}")
        print(f"  Prompt: {prompt[:80]}...")

        try:
            img_bytes = generate_image(prompt, api_key, args.aspect_ratio)
            with open(out_path, "wb") as f:
                f.write(img_bytes)
            print(f"  Saved: {out_path} ({len(img_bytes) / 1024:.0f} KB)")
        except Exception as e:
            print(f"  FAILED: {e}", file=sys.stderr)
            continue

        # Small delay to avoid rate limiting
        if i < len(jobs) - 1:
            time.sleep(1)

    print()
    print(f"Done. Images saved to {output_dir}")


if __name__ == "__main__":
    main()
