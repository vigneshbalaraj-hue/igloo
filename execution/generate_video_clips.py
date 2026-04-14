"""
generate_video_clips.py -- Generate video clips via Kling AI API (parallel).

Handles two types:
  1. B-roll: image-to-video (5s clips from b-roll images) — all submitted in parallel
  2. Anchor lip-sync: Avatar API (image + audio → lip-synced video in 1 step)
     - All anchors submitted in parallel, polled, downloaded

Uses Kling REST API with JWT auth. Requires PyJWT.

Usage:
    py execution/generate_video_clips.py .tmp/.../script.json
    py execution/generate_video_clips.py .tmp/.../script.json --only broll
    py execution/generate_video_clips.py .tmp/.../script.json --only anchor
    py execution/generate_video_clips.py .tmp/.../script.json --only scene2
"""

import argparse
import base64
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FFPROBE = str(PROJECT_ROOT / "tools" / "ffprobe.exe")
if not Path(FFPROBE).exists():
    FFPROBE = "ffprobe"

import jwt

BASE_URL = "https://api-singapore.klingai.com"
POLL_INTERVAL = 10  # seconds between poll rounds
MAX_POLL_TIME = 600  # max seconds to wait


def load_env(key: str) -> str:
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


def make_jwt(access_key: str, secret_key: str) -> str:
    headers = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "iss": access_key,
        "exp": int(time.time()) + 1800,
        "nbf": int(time.time()) - 5
    }
    return jwt.encode(payload, secret_key, headers=headers)


def api_request(method: str, path: str, token: str, body: dict = None, retries: int = 3) -> dict:
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode() if body else None

    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=data, method=method)
            req.add_header("Authorization", f"Bearer {token}")
            req.add_header("Content-Type", "application/json")

            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode())

            if result.get("code") != 0:
                raise RuntimeError(f"API error: code={result.get('code')}, msg={result.get('message')}")
            return result

        except urllib.error.HTTPError as e:
            error_body = ""
            try:
                error_body = e.read().decode()
            except Exception:
                pass
            retryable = e.code == 429 or 500 <= e.code < 600
            print(f"  API ERROR {e.code}: {error_body[:500]}", file=sys.stderr)
            if retryable and attempt < retries - 1:
                wait = 5 * (attempt + 1)
                print(f"  {e.code} is transient; retrying in {wait}s (attempt {attempt+1}/{retries})...")
                time.sleep(wait)
                continue
            raise
        except (urllib.error.URLError, ConnectionError, OSError) as e:
            if attempt < retries - 1:
                wait = 5 * (attempt + 1)
                print(f"  Connection error (attempt {attempt+1}/{retries}): {e}. Retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise


def image_to_base64(image_path: Path) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def audio_to_base64_url(audio_path: Path) -> str:
    with open(audio_path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def get_audio_duration_ms(audio_path: Path) -> int:
    cmd = [FFPROBE, "-v", "error", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    duration_s = float(result.stdout.strip())
    return int(duration_s * 1000)


def download_video(url: str, output_path: Path):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=120) as resp:
        with open(output_path, "wb") as f:
            f.write(resp.read())


# ---------------------------------------------------------------------------
# Batch polling — wait for multiple tasks at once
# ---------------------------------------------------------------------------

def poll_tasks_batch(poll_path: str, token: str, tasks: list) -> dict:
    """
    Poll multiple tasks in parallel.
    tasks: list of {"task_id": str, "label": str}
    Returns: dict of {task_id: task_data} for succeeded tasks.
    Raises on any failure.
    """
    pending = {t["task_id"]: t["label"] for t in tasks}
    results = {}
    start = time.time()

    print(f"  Polling {len(pending)} tasks in parallel...")

    while pending and (time.time() - start) < MAX_POLL_TIME:
        completed = []
        for task_id, label in list(pending.items()):
            try:
                result = api_request("GET", f"{poll_path}/{task_id}", token)
                data = result.get("data", {})
                status = data.get("task_status", "")

                if status == "succeed":
                    elapsed = int(time.time() - start)
                    print(f"  [{elapsed}s] {label} — done!")
                    results[task_id] = data
                    completed.append(task_id)
                elif status == "failed":
                    msg = data.get("task_status_msg", "unknown error")
                    print(f"  {label} — FAILED: {msg}", file=sys.stderr)
                    completed.append(task_id)
            except Exception as e:
                print(f"  {label} — poll error: {e}", file=sys.stderr)

        for tid in completed:
            pending.pop(tid, None)

        if pending:
            time.sleep(POLL_INTERVAL)

    if pending:
        labels = [pending[tid] for tid in pending]
        print(f"  WARNING: {len(pending)} tasks timed out: {labels}", file=sys.stderr)

    return results


# ---------------------------------------------------------------------------
# Job extraction from script JSON
# ---------------------------------------------------------------------------

def extract_jobs(script: dict) -> list:
    jobs = []
    for scene in script["scenes"]:
        sid = scene["scene_id"]
        vg = scene.get("video_generation", {})
        method = vg.get("method", "")

        if method == "image-to-video":
            if "clips" in vg:
                for clip in vg["clips"]:
                    cid = clip["clip_id"]
                    jobs.append({
                        "type": "broll",
                        "name": f"broll_scene{cid}",
                        "image_file": f"broll_scene{cid}.png",
                        "video_prompt": clip["video_prompt"],
                        "kling_duration": clip.get("kling_duration", 5),
                        "trim_to": clip.get("trim_to")
                    })
            else:
                jobs.append({
                    "type": "broll",
                    "name": f"broll_scene{sid}",
                    "image_file": f"broll_scene{sid}.png",
                    "video_prompt": vg["video_prompt"],
                    "kling_duration": vg.get("kling_duration", 5),
                    "trim_to": vg.get("trim_to")
                })

        elif method == "lip-sync":
            audio_slice = vg.get("audio_slice", [0, 5])
            audio_duration = audio_slice[1] - audio_slice[0]
            jobs.append({
                "type": "anchor",
                "name": f"anchor_scene{sid}",
                "scene_id": sid,
                "video_prompt": vg["video_prompt"],
                "audio_duration": audio_duration,
            })

    return jobs


# ---------------------------------------------------------------------------
# Parallel B-roll generation
# ---------------------------------------------------------------------------

def generate_broll_parallel(broll_jobs: list, token: str, images_dir: Path, output_dir: Path):
    """Submit all b-roll tasks, poll in batch, download results."""
    if not broll_jobs:
        return

    print(f"{'='*60}")
    print(f"B-ROLL: Submitting {len(broll_jobs)} tasks in parallel")
    print(f"{'='*60}")

    # Submit all
    tasks = []
    job_map = {}  # task_id -> job
    for job in broll_jobs:
        name = job["name"]
        image_path = images_dir / job["image_file"]
        if not image_path.exists():
            print(f"  ERROR: Image not found: {image_path}", file=sys.stderr)
            continue

        image_b64 = image_to_base64(image_path)
        body = {
            "model_name": "kling-v2-1",
            "image": image_b64,
            "prompt": job["video_prompt"],
            "duration": str(job.get("kling_duration", 5)),
            "mode": "std",
            "sound": "off"
        }

        result = api_request("POST", "/v1/videos/image2video", token, body)
        task_id = result["data"]["task_id"]
        print(f"  {name} — submitted (task: {task_id})")
        tasks.append({"task_id": task_id, "label": name})
        job_map[task_id] = job

        time.sleep(0.5)  # Small delay to avoid rate limiting on submit

    # Poll all
    print()
    results = poll_tasks_batch("/v1/videos/image2video", token, tasks)

    # Download all
    print()
    for task_id, data in results.items():
        job = job_map[task_id]
        video_url = data["task_result"]["videos"][0]["url"]
        out_path = output_dir / f"{job['name']}.mp4"
        download_video(video_url, out_path)
        print(f"  {job['name']} — saved: {out_path}")

    print(f"\n  B-roll complete: {len(results)}/{len(broll_jobs)} succeeded\n")
    if len(results) < len(broll_jobs):
        missing = [j["name"] for j in broll_jobs if not any(job_map[tid]["name"] == j["name"] for tid in results)]
        print(f"ERROR: {len(broll_jobs) - len(results)} b-roll clip(s) failed/timed out: {missing}", file=sys.stderr)
        print("ERROR_CODE: KLING_FAILED", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Parallel Anchor generation (Avatar API — single step)
# ---------------------------------------------------------------------------

def generate_anchors_avatar(anchor_jobs: list, token: str, images_dir: Path,
                            audio_dir: Path, output_dir: Path,
                            access_key: str, secret_key: str):
    """Generate all anchors via Avatar API: image + audio → lip-synced video in 1 call."""
    if not anchor_jobs:
        return

    print(f"{'='*60}")
    print(f"ANCHOR: {len(anchor_jobs)} clips (Avatar API — single step)")
    print(f"{'='*60}")

    avatar_tasks = []
    task_map = {}  # task_id -> job name

    image_path = images_dir / "anchor.png"
    if not image_path.exists():
        print(f"  ERROR: Anchor image not found: {image_path}", file=sys.stderr)
        return

    image_b64 = image_to_base64(image_path)

    for job in anchor_jobs:
        name = job["name"]
        scene_id = job["scene_id"]
        audio_path = audio_dir / f"scene{scene_id}.mp3"

        if not audio_path.exists():
            print(f"  ERROR: Audio slice not found: {audio_path}", file=sys.stderr)
            continue

        audio_duration_ms = get_audio_duration_ms(audio_path)
        audio_b64 = audio_to_base64_url(audio_path)

        body = {
            "image": image_b64,
            "sound_file": audio_b64,
            "prompt": job["video_prompt"],
            "mode": "std",
        }

        result = api_request("POST", "/v1/videos/avatar/image2video", token, body)
        task_id = result["data"]["task_id"]
        print(f"  {name} — avatar submitted (audio={audio_duration_ms}ms, task: {task_id})")

        avatar_tasks.append({"task_id": task_id, "label": name})
        task_map[task_id] = name

        time.sleep(0.5)

    # Poll all avatar tasks
    if avatar_tasks:
        print()
        token = make_jwt(access_key, secret_key)
        avatar_results = poll_tasks_batch("/v1/videos/avatar/image2video", token, avatar_tasks)

        # Download final videos
        print()
        for task_id, data in avatar_results.items():
            name = task_map[task_id]
            video_url = data["task_result"]["videos"][0]["url"]
            duration = data["task_result"]["videos"][0].get("duration", "?")
            out_path = output_dir / f"{name}.mp4"
            download_video(video_url, out_path)
            print(f"  {name} — avatar saved: {out_path} ({duration}s)")

    succeeded = sum(1 for n in task_map.values() if (output_dir / f"{n}.mp4").exists())
    print(f"\n  Anchor complete: {succeeded}/{len(anchor_jobs)} succeeded\n")
    if succeeded < len(anchor_jobs):
        missing = [n for n in task_map.values() if not (output_dir / f"{n}.mp4").exists()]
        print(f"ERROR: {len(anchor_jobs) - succeeded} anchor clip(s) failed/timed out: {missing}", file=sys.stderr)
        print("ERROR_CODE: KLING_FAILED", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Unified parallel generation — submit ALL jobs at once, poll together
# ---------------------------------------------------------------------------

def generate_all_parallel(broll_jobs: list, anchor_jobs: list, token: str,
                          images_dir: Path, audio_dir: Path, output_dir: Path,
                          access_key: str, secret_key: str):
    """Submit ALL b-roll and anchor jobs at once, poll everything together, download."""
    if not broll_jobs and not anchor_jobs:
        print("  No jobs to run.")
        return

    total = len(broll_jobs) + len(anchor_jobs)
    print(f"{'='*60}")
    print(f"SUBMITTING ALL {total} CLIPS IN PARALLEL")
    print(f"  {len(broll_jobs)} b-roll + {len(anchor_jobs)} anchor")
    print(f"{'='*60}\n")

    all_tasks = []     # {"task_id", "label", "poll_path"}
    job_map = {}       # task_id -> {"name", "type"}

    # --- Submit b-roll ---
    for job in broll_jobs:
        name = job["name"]
        image_path = images_dir / job["image_file"]
        if not image_path.exists():
            print(f"  ERROR: Image not found: {image_path}", file=sys.stderr)
            continue

        image_b64 = image_to_base64(image_path)
        body = {
            "model_name": "kling-v2-1",
            "image": image_b64,
            "prompt": job["video_prompt"],
            "duration": str(job.get("kling_duration", 5)),
            "mode": "std",
            "sound": "off"
        }

        result = api_request("POST", "/v1/videos/image2video", token, body)
        task_id = result["data"]["task_id"]
        print(f"  [b-roll] {name} -- submitted (task: {task_id})")
        all_tasks.append({"task_id": task_id, "label": name, "poll_path": "/v1/videos/image2video"})
        job_map[task_id] = {"name": name, "type": "broll"}
        time.sleep(0.3)

    # --- Submit anchors ---
    image_path = images_dir / "anchor.png"
    if anchor_jobs and not image_path.exists():
        print(f"  ERROR: Anchor image not found: {image_path}", file=sys.stderr)
    else:
        image_b64 = image_to_base64(image_path) if anchor_jobs else None

        for job in anchor_jobs:
            name = job["name"]
            scene_id = job["scene_id"]
            audio_path = audio_dir / f"scene{scene_id}.mp3"

            if not audio_path.exists():
                print(f"  ERROR: Audio slice not found: {audio_path}", file=sys.stderr)
                continue

            audio_duration_ms = get_audio_duration_ms(audio_path)
            audio_b64 = audio_to_base64_url(audio_path)

            body = {
                "image": image_b64,
                "sound_file": audio_b64,
                "prompt": job["video_prompt"],
                "mode": "std",
            }

            result = api_request("POST", "/v1/videos/avatar/image2video", token, body)
            task_id = result["data"]["task_id"]
            print(f"  [anchor] {name} -- submitted (audio={audio_duration_ms}ms, task: {task_id})")
            all_tasks.append({"task_id": task_id, "label": name, "poll_path": "/v1/videos/avatar/image2video"})
            job_map[task_id] = {"name": name, "type": "anchor"}
            time.sleep(0.3)

    if not all_tasks:
        print("  No tasks submitted.")
        return

    # --- Poll ALL tasks together ---
    print(f"\n  Polling {len(all_tasks)} tasks...\n")

    # Refresh token before polling (submissions may have taken time)
    token = make_jwt(access_key, secret_key)

    pending = {t["task_id"]: t for t in all_tasks}
    results = {}
    start = time.time()

    while pending and (time.time() - start) < MAX_POLL_TIME:
        completed = []
        for task_id, task_info in list(pending.items()):
            try:
                result = api_request("GET", f"{task_info['poll_path']}/{task_id}", token)
                data = result.get("data", {})
                status = data.get("task_status", "")

                if status == "succeed":
                    elapsed = int(time.time() - start)
                    print(f"  [{elapsed}s] {task_info['label']} -- done!")
                    results[task_id] = data
                    completed.append(task_id)
                elif status == "failed":
                    msg = data.get("task_status_msg", "unknown error")
                    print(f"  {task_info['label']} -- FAILED: {msg}", file=sys.stderr)
                    completed.append(task_id)
            except Exception as e:
                print(f"  {task_info['label']} -- poll error: {e}", file=sys.stderr)

        for tid in completed:
            pending.pop(tid, None)

        if pending:
            remaining = [t["label"] for t in pending.values()]
            elapsed = int(time.time() - start)
            print(f"  [{elapsed}s] Waiting on {len(pending)}: {', '.join(remaining)}")
            time.sleep(POLL_INTERVAL)

    if pending:
        labels = [pending[tid]["label"] for tid in pending]
        print(f"  WARNING: {len(pending)} tasks timed out: {labels}", file=sys.stderr)

    # --- Download ALL results ---
    print(f"\n  Downloading {len(results)} clips...\n")
    for task_id, data in results.items():
        info = job_map[task_id]
        video_url = data["task_result"]["videos"][0]["url"]
        duration = data["task_result"]["videos"][0].get("duration", "?")
        out_path = output_dir / f"{info['name']}.mp4"
        download_video(video_url, out_path)
        print(f"  {info['name']} -- saved ({duration}s)")

    print(f"\n  All clips: {len(results)}/{total} succeeded\n")
    if len(results) < len(all_tasks):
        missing = [t["label"] for t in all_tasks if t["task_id"] not in results]
        print(f"ERROR: {len(all_tasks) - len(results)} clip(s) failed/timed out: {missing}", file=sys.stderr)
        print("ERROR_CODE: KLING_FAILED", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate video clips via Kling API (parallel)")
    parser.add_argument("script", help="Path to script JSON file")
    parser.add_argument("--only", help="Filter: 'broll', 'anchor', or specific name like 'scene2'")
    args = parser.parse_args()

    script_path = Path(args.script)
    if not script_path.exists():
        print(f"ERROR: Script not found: {script_path}", file=sys.stderr)
        sys.exit(1)

    with open(script_path, encoding="utf-8") as f:
        script = json.load(f)

    access_key = load_env("KLING_ACCESS_KEY")
    secret_key = load_env("KLING_SECRET_KEY")
    token = make_jwt(access_key, secret_key)

    base_dir = script_path.parent
    images_dir = base_dir / "images"
    audio_dir = base_dir / "audio_slices"

    # Each run gets a fresh timestamped folder
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    clips_root = base_dir / "video_clips"
    output_dir = clips_root / f"run_{run_id}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write pointer so assembly can find the latest run
    (clips_root / ".latest").write_text(f"run_{run_id}")
    print(f"Run: {output_dir}")

    jobs = extract_jobs(script)

    # Apply filter
    if args.only:
        if args.only in ("broll", "anchor"):
            jobs = [j for j in jobs if j["type"] == args.only]
        else:
            jobs = [j for j in jobs if args.only in j["name"]]

    broll_jobs = [j for j in jobs if j["type"] == "broll"]
    anchor_jobs = [j for j in jobs if j["type"] == "anchor"]

    print(f"Jobs: {len(broll_jobs)} b-roll, {len(anchor_jobs)} anchor")
    print(f"Output: {output_dir}")
    print()

    # Submit ALL jobs (b-roll + anchor) at once, then poll everything together
    generate_all_parallel(broll_jobs, anchor_jobs, token, images_dir, audio_dir,
                          output_dir, access_key, secret_key)

    print("=" * 60)
    print("Done. All video clips generated.")
    print(f"Output: {output_dir}")


if __name__ == "__main__":
    main()
