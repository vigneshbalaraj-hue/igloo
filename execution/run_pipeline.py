"""
run_pipeline.py — Full pipeline orchestrator for the Reel Engine.

Runs all steps (0-8) in order with GO/NO-GO gates between each step.
Can start from scratch (--new) or from an existing script JSON.

Usage:
    # From existing script:
    py execution/run_pipeline.py .tmp/fasting_healing/fasting_healing_40s_script.json

    # From scratch:
    py execution/run_pipeline.py --new --theme "Health & Wellness" --topic "Fasting when sick"

    # With options:
    py execution/run_pipeline.py .tmp/topic/script.json --speed 1.3 --audio-mode option-c
    py execution/run_pipeline.py .tmp/topic/script.json --start-from 5 --dry-run
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_env_value(key: str) -> str | None:
    """Read a key from process env or .env. Returns None if not found (does NOT exit)."""
    # 1. Process environment (Modal secrets, CI, shell exports) — preferred
    val = os.environ.get(key)
    if val and not val.startswith("<"):
        return val
    # 2. Fall back to .env file (local dev convenience)
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return None
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith(f"{key}="):
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                if val and not val.startswith("<"):
                    return val
    return None


def format_size(path: Path) -> str:
    """Human-readable file size."""
    if not path.exists():
        return "missing"
    size = path.stat().st_size
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.0f} KB"
    else:
        return f"{size / (1024 * 1024):.1f} MB"


def format_duration(seconds: float) -> str:
    """Format seconds as Xm Ys or Xs."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    m = int(seconds // 60)
    s = seconds % 60
    return f"{m}m {s:.0f}s"


def prompt_gate(message: str, valid: list[str]) -> str:
    """Prompt user, return validated lowercase response."""
    valid_lower = [v.lower() for v in valid]
    while True:
        response = input(f"{message} ").strip().lower()
        if response in valid_lower:
            return response
        if response in ("", "\n") and "" in valid:
            return ""
        print(f"  Enter one of: {', '.join(valid)}")


def print_divider(title: str = ""):
    if title:
        print(f"\n{'=' * 55}")
        print(f"  {title}")
        print(f"{'=' * 55}")
    else:
        print(f"{'_' * 55}")


# ---------------------------------------------------------------------------
# State Persistence
# ---------------------------------------------------------------------------

class PipelineState:
    """Tracks pipeline execution state to pipeline_state.json."""

    def __init__(self, script_dir: Path, script_path: str):
        self.path = script_dir / "pipeline_state.json"
        self.data = self._load_or_create(script_path)

    def _load_or_create(self, script_path: str) -> dict:
        if self.path.exists():
            try:
                with open(self.path) as f:
                    return json.load(f)
            except json.JSONDecodeError:
                pass
        return {
            "script_path": str(script_path),
            "started_at": datetime.now().isoformat(),
            "steps": {}
        }

    def mark_started(self, step: int):
        self.data["steps"][str(step)] = {
            "status": "running",
            "started": datetime.now().isoformat()
        }
        self._save()

    def mark_completed(self, step: int, outputs: list[str], elapsed: float):
        entry = self.data["steps"].get(str(step), {})
        entry["status"] = "completed"
        entry["ended"] = datetime.now().isoformat()
        entry["elapsed_seconds"] = round(elapsed, 1)
        entry["outputs"] = outputs
        self.data["steps"][str(step)] = entry
        self._save()

    def mark_skipped(self, step: int, reason: str):
        self.data["steps"][str(step)] = {
            "status": "skipped",
            "reason": reason
        }
        self._save()

    def mark_failed(self, step: int, error: str):
        entry = self.data["steps"].get(str(step), {})
        entry["status"] = "failed"
        entry["ended"] = datetime.now().isoformat()
        entry["error"] = error
        self.data["steps"][str(step)] = entry
        self._save()

    def _save(self):
        with open(self.path, "w") as f:
            json.dump(self.data, f, indent=2)


# ---------------------------------------------------------------------------
# Script helpers
# ---------------------------------------------------------------------------

def get_anchor_scenes(script_data: dict) -> list[int]:
    """Return scene_ids of anchor scenes."""
    ids = []
    for s in script_data.get("scenes", []):
        if s.get("type") == "anchor":
            ids.append(s["scene_id"])
        elif s.get("video_generation", {}).get("method") == "lip-sync":
            ids.append(s["scene_id"])
    return ids


def get_expected_images(script_data: dict) -> list[str]:
    """Return list of expected image filenames."""
    images = ["anchor.png"]
    for s in script_data.get("scenes", []):
        if s.get("type") != "b-roll":
            continue
        vg = s.get("video_generation", {})
        if "clips" in vg:
            for clip in vg["clips"]:
                images.append(f"broll_scene{clip['clip_id']}.png")
        else:
            images.append(f"broll_scene{s['scene_id']}.png")
    return images


def get_expected_clips(script_data: dict) -> list[str]:
    """Return list of expected video clip filenames."""
    clips = []
    for s in script_data.get("scenes", []):
        sid = s["scene_id"]
        if s.get("type") == "anchor":
            clips.append(f"anchor_scene{sid}.mp4")
        else:
            vg = s.get("video_generation", {})
            if "clips" in vg:
                for clip in vg["clips"]:
                    clips.append(f"broll_scene{clip['clip_id']}.mp4")
            else:
                clips.append(f"broll_scene{sid}.mp4")
    return clips


# ---------------------------------------------------------------------------
# Step Definitions
# ---------------------------------------------------------------------------

def _build_cmd_step0(ctx: dict) -> list[str]:
    cmd = [sys.executable, "execution/generate_script.py",
           "--theme", ctx["theme"], "--topic", ctx["topic"],
           "--duration", str(ctx.get("duration", 40))]
    if ctx.get("script_text"):
        cmd.extend(["--script", ctx["script_text"]])
    if ctx.get("output_dir"):
        cmd.extend(["--output-dir", str(ctx["output_dir"])])
    if ctx.get("auto_go"):
        cmd.append("--non-interactive")
    return cmd


def _skip_step0(ctx: dict) -> str | None:
    if ctx.get("script_path") and Path(ctx["script_path"]).exists():
        return f"Script JSON already exists: {ctx['script_path']}"
    return None


def _outputs_step0(ctx: dict) -> list[Path]:
    if ctx.get("script_path"):
        return [Path(ctx["script_path"])]
    return []


def _build_cmd_step1(ctx: dict) -> list[str]:
    return [sys.executable, "execution/select_voice.py",
            str(ctx["script_path"]), "--auto"]


def _skip_step1(ctx: dict) -> str | None:
    vid = load_env_value("ELEVENLABS_VOICE_ID")
    if vid:
        return f"ELEVENLABS_VOICE_ID already set ({vid[:8]}...)"
    return None


def _outputs_step1(ctx: dict) -> list[Path]:
    return [ctx["script_dir"] / "voice_previews"]


def _build_cmd_step2(ctx: dict) -> list[str]:
    cmd = [sys.executable, "execution/generate_voiceover.py",
           str(ctx["script_path"])]
    if ctx.get("speed", 1.0) != 1.0:
        cmd.extend(["--speed", str(ctx["speed"])])
    return cmd


def _skip_step2(ctx: dict) -> str | None:
    vo = ctx["script_dir"] / "voiceover.mp3"
    if vo.exists():
        return f"voiceover.mp3 exists ({format_size(vo)})"
    return None


def _outputs_step2(ctx: dict) -> list[Path]:
    d = ctx["script_dir"]
    return [d / "voiceover.mp3", d / "voiceover_timestamps.json"]


def _build_cmd_step3(ctx: dict) -> list[str]:
    return [sys.executable, "execution/extract_word_timestamps.py",
            str(ctx["script_dir"] / "voiceover_timestamps.json"),
            "--update-script", str(ctx["script_path"])]


def _skip_step3(ctx: dict) -> str | None:
    words = ctx["script_dir"] / "voiceover_words.json"
    if not words.exists():
        return None
    scenes = ctx["script_data"].get("scenes", [])
    if scenes and "narration_start" in scenes[0]:
        return "voiceover_words.json exists and script has timestamps"
    return None


def _outputs_step3(ctx: dict) -> list[Path]:
    return [ctx["script_dir"] / "voiceover_words.json", Path(ctx["script_path"])]


def _build_cmd_step4(ctx: dict) -> list[str]:
    return [sys.executable, "execution/slice_audio.py",
            str(ctx["script_path"])]


def _skip_step4(ctx: dict) -> str | None:
    slices_dir = ctx["script_dir"] / "audio_slices"
    if not slices_dir.exists():
        return None
    anchor_ids = get_anchor_scenes(ctx["script_data"])
    expected = len(anchor_ids)
    actual = len(list(slices_dir.glob("scene*.mp3")))
    if actual >= expected:
        return f"audio_slices/ has {actual} files (expected {expected})"
    return None


def _outputs_step4(ctx: dict) -> list[Path]:
    slices_dir = ctx["script_dir"] / "audio_slices"
    return list(slices_dir.glob("scene*.mp3")) if slices_dir.exists() else []


def _build_cmd_step5(ctx: dict) -> list[str]:
    return [sys.executable, "execution/generate_images.py",
            str(ctx["script_path"])]


def _skip_step5(ctx: dict) -> str | None:
    images_dir = ctx["script_dir"] / "images"
    if not images_dir.exists():
        return None
    expected = get_expected_images(ctx["script_data"])
    for img_name in expected:
        if not (images_dir / img_name).exists():
            return None
    return f"All {len(expected)} images exist"


def _outputs_step5(ctx: dict) -> list[Path]:
    images_dir = ctx["script_dir"] / "images"
    return list(images_dir.glob("*.png")) if images_dir.exists() else []


def _build_cmd_step6(ctx: dict) -> list[str]:
    return [sys.executable, "execution/generate_video_clips.py",
            str(ctx["script_path"])]


def _skip_step6(ctx: dict) -> str | None:
    latest_file = ctx["script_dir"] / "video_clips" / ".latest"
    if not latest_file.exists():
        return None
    run_name = latest_file.read_text().strip()
    run_dir = ctx["script_dir"] / "video_clips" / run_name
    if not run_dir.exists():
        return None
    expected = get_expected_clips(ctx["script_data"])
    for clip_name in expected:
        if not (run_dir / clip_name).exists():
            return None
    return f"All {len(expected)} clips exist in {run_name}"


def _outputs_step6(ctx: dict) -> list[Path]:
    latest_file = ctx["script_dir"] / "video_clips" / ".latest"
    if not latest_file.exists():
        return []
    run_name = latest_file.read_text().strip()
    run_dir = ctx["script_dir"] / "video_clips" / run_name
    return list(run_dir.glob("*.mp4")) if run_dir.exists() else []


def _build_cmd_step7(ctx: dict) -> list[str]:
    return [sys.executable, "execution/generate_music.py",
            str(ctx["script_path"])]


def _skip_step7(ctx: dict) -> str | None:
    music = ctx["script_dir"] / "background_music.mp3"
    if music.exists():
        return f"background_music.mp3 exists ({format_size(music)})"
    return None


def _outputs_step7(ctx: dict) -> list[Path]:
    return [ctx["script_dir"] / "background_music.mp3"]


def _build_cmd_step8(ctx: dict) -> list[str]:
    cmd = [sys.executable, "execution/assemble_video.py",
           str(ctx["script_path"]),
           "--audio-mode", ctx.get("audio_mode", "option-c")]
    if ctx.get("no_captions"):
        cmd.append("--no-captions")
    return cmd


def _skip_step8(ctx: dict) -> str | None:
    return None  # Never skip assembly


def _outputs_step8(ctx: dict) -> list[Path]:
    mode = ctx.get("audio_mode", "option-c")
    suffix_map = {"original": "", "option-a": "_optiona", "option-c": "_optionc"}
    suffix = suffix_map.get(mode, "")
    return [ctx["script_dir"] / f"final_reel{suffix}.mp4"]


STEPS = {
    0: {"name": "Script Generation",     "build_cmd": _build_cmd_step0,
        "skip_check": _skip_step0,        "outputs": _outputs_step0},
    1: {"name": "Voice Selection",        "build_cmd": _build_cmd_step1,
        "skip_check": _skip_step1,        "outputs": _outputs_step1},
    2: {"name": "Voiceover",              "build_cmd": _build_cmd_step2,
        "skip_check": _skip_step2,        "outputs": _outputs_step2},
    3: {"name": "Timestamp Extraction",   "build_cmd": _build_cmd_step3,
        "skip_check": _skip_step3,        "outputs": _outputs_step3},
    4: {"name": "Audio Slicing",          "build_cmd": _build_cmd_step4,
        "skip_check": _skip_step4,        "outputs": _outputs_step4},
    5: {"name": "Image Generation",       "build_cmd": _build_cmd_step5,
        "skip_check": _skip_step5,        "outputs": _outputs_step5},
    6: {"name": "Video Clip Generation",  "build_cmd": _build_cmd_step6,
        "skip_check": _skip_step6,        "outputs": _outputs_step6},
    7: {"name": "Background Music",       "build_cmd": _build_cmd_step7,
        "skip_check": _skip_step7,        "outputs": _outputs_step7},
    8: {"name": "Assembly",               "build_cmd": _build_cmd_step8,
        "skip_check": _skip_step8,        "outputs": _outputs_step8},
}

STEP_ORDER = [0, 1, 2, 3, 4, 5, 6, 7, 8]

# Future parallelization:
# Phase A (parallel): [steps 1-4 serial] || [step 5] || [step 7]
# Phase B (serial):   step 6 (needs 4+5)
# Phase C (serial):   step 8 (needs 3+6+7)


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

def run_step(cmd: list[str], step_name: str) -> int:
    """Run subprocess, streaming output. Returns exit code."""
    print(f"\n  Running: {' '.join(cmd)}\n")
    proc = subprocess.Popen(
        cmd,
        stdout=sys.stdout,
        stderr=sys.stderr,
        cwd=str(PROJECT_ROOT)
    )
    return proc.wait()


def gate(step_num: int, step_name: str, outputs: list[Path],
         elapsed: float, next_step: int | None, next_name: str | None,
         auto_go: bool) -> str:
    """Post-step gate. Returns 'go', 'skip', or 'quit'."""

    print_divider(f"Step {step_num} ({step_name}) COMPLETED -- {format_duration(elapsed)}")

    # Show outputs
    if outputs:
        print("  Outputs:")
        for p in outputs:
            if p.exists():
                if p.is_dir():
                    count = len(list(p.iterdir()))
                    print(f"    - {p.name}/ ({count} files)")
                else:
                    print(f"    - {p.name} ({format_size(p)})")

    if next_step is not None:
        print(f"\n  Next: Step {next_step} -- {next_name}")

    if auto_go:
        print("  [auto-go] Continuing...")
        return "go"

    if next_step is None:
        return "go"  # Last step, no gate needed

    print_divider()
    choice = prompt_gate(
        "  [G]o  [S]kip next  [Q]uit:",
        ["g", "go", "", "s", "skip", "q", "quit"])

    if choice in ("g", "go", ""):
        return "go"
    elif choice in ("s", "skip"):
        return "skip"
    else:
        return "quit"


def handle_failure(step_num: int, step_name: str, auto_go: bool) -> str:
    """Handle step failure. Returns 'retry' or 'quit'."""
    if auto_go:
        print(f"\n  Step {step_num} ({step_name}) FAILED. --auto-go: aborting.")
        return "quit"

    choice = prompt_gate(
        f"\n  Step {step_num} ({step_name}) FAILED.\n  [R]etry  [Q]uit:",
        ["r", "retry", "q", "quit"])

    if choice in ("r", "retry"):
        return "retry"
    return "quit"


def print_summary(state: PipelineState, step_timings: dict[int, float],
                   pipeline_start: float, final_output: Path | None = None):
    """Print pipeline summary."""
    total_elapsed = time.time() - pipeline_start

    print_divider("PIPELINE SUMMARY")
    print(f"  Total elapsed: {format_duration(total_elapsed)}\n")

    for step_num in STEP_ORDER:
        name = STEPS[step_num]["name"]
        step_state = state.data.get("steps", {}).get(str(step_num), {})
        status = step_state.get("status", "not run")

        if status == "completed":
            elapsed = step_timings.get(step_num, 0)
            print(f"  Step {step_num}: {name:<25} -- {format_duration(elapsed)}")
        elif status == "skipped":
            reason = step_state.get("reason", "")
            print(f"  Step {step_num}: {name:<25} -- SKIPPED ({reason})")
        elif status == "failed":
            error = step_state.get("error", "")
            print(f"  Step {step_num}: {name:<25} -- FAILED ({error})")
        else:
            print(f"  Step {step_num}: {name:<25} -- {status}")

    if final_output and final_output.exists():
        print(f"\n  Output: {final_output}")
        print(f"  Size: {format_size(final_output)}")
    print_divider()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Reel Engine pipeline orchestrator (steps 0-8)")
    parser.add_argument("script", nargs="?", default=None,
                        help="Path to existing script JSON (omit with --new)")
    parser.add_argument("--new", action="store_true",
                        help="Start from Step 0 (script generation)")
    parser.add_argument("--theme", default=None,
                        help="Theme (required with --new)")
    parser.add_argument("--topic", default=None,
                        help="Topic (required with --new)")
    parser.add_argument("--script-text", default=None,
                        help="User narration text (optional with --new)")
    parser.add_argument("--speed", type=float, default=1.0,
                        help="Voiceover speed (default: 1.0)")
    parser.add_argument("--audio-mode", default="option-c",
                        choices=["original", "option-a", "option-c"],
                        help="Assembly audio mode (default: option-c)")
    parser.add_argument("--no-captions", action="store_true",
                        help="Skip caption burn-in")
    parser.add_argument("--start-from", type=int, default=None,
                        choices=range(0, 9), metavar="N",
                        help="Start from step N (0-8)")
    parser.add_argument("--auto-go", action="store_true",
                        help="Skip all gates, run fully automated")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would run, don't execute")
    parser.add_argument("--workdir", default=None,
                        help="Override output dir for this run. Falls back to "
                             "IGLOO_WORKDIR env var, then PROJECT_ROOT/.tmp/<slug>. "
                             "Use this for concurrency-safe runs (e.g. Modal workers).")
    args = parser.parse_args()

    # --- Validate args ---
    if args.new:
        if not args.theme or not args.topic:
            parser.error("--new requires --theme and --topic")
        start_from = args.start_from if args.start_from is not None else 0
    elif args.script:
        script_path = Path(args.script)
        if not script_path.exists():
            print(f"ERROR: Script not found: {args.script}", file=sys.stderr)
            sys.exit(1)
        start_from = args.start_from if args.start_from is not None else 1
    else:
        parser.error("Provide a script JSON path or use --new")
        return

    # --- Build context ---
    ctx = {
        "speed": args.speed,
        "audio_mode": args.audio_mode,
        "no_captions": args.no_captions,
        "theme": args.theme,
        "topic": args.topic,
        "script_text": args.script_text,
        "auto_go": args.auto_go,
    }

    # Resolve workdir override (CLI flag > env var > None)
    workdir_override = args.workdir or os.environ.get("IGLOO_WORKDIR")

    if args.new:
        # Slug for output dir
        import re
        slug = re.sub(r'[^a-z0-9\s-]', '', args.topic.lower().strip())
        slug = re.sub(r'[\s-]+', '_', slug).strip('_')
        if workdir_override:
            output_dir = Path(workdir_override).resolve()
        else:
            output_dir = PROJECT_ROOT / ".tmp" / slug
        ctx["output_dir"] = output_dir
        ctx["script_dir"] = output_dir
        ctx["script_path"] = str(output_dir / f"{slug}_script.json")
        ctx["script_data"] = {}
    else:
        # Existing-script mode: workdir override is ignored — script's parent
        # dir is authoritative (the script and its sibling artifacts already
        # live together). Workdir override only makes sense for fresh runs.
        if workdir_override:
            print(f"  WARNING: --workdir/IGLOO_WORKDIR ignored in existing-script mode "
                  f"(script's parent dir is used)")
        script_path = Path(args.script).resolve()
        ctx["script_path"] = str(script_path)
        ctx["script_dir"] = script_path.parent
        with open(script_path) as f:
            ctx["script_data"] = json.load(f)

    # --- Pre-flight ---
    print_divider("REEL ENGINE PIPELINE")
    if args.new:
        print(f"  Mode: NEW -- {args.theme} / {args.topic}")
    else:
        print(f"  Script: {ctx['script_path']}")
    print(f"  Speed: {args.speed}x | Audio: {args.audio_mode} | Captions: {not args.no_captions}")
    print(f"  Starting from step {start_from}")
    if args.dry_run:
        print("  ** DRY RUN -- no steps will execute **")
    if args.auto_go:
        print("  ** AUTO-GO -- all gates will be skipped **")

    # --- State ---
    state = PipelineState(ctx["script_dir"], ctx["script_path"])
    step_timings = {}
    pipeline_start = time.time()
    skip_next = False

    try:
        for i, step_num in enumerate(STEP_ORDER):
            if step_num < start_from:
                continue

            step_def = STEPS[step_num]

            # --- User chose to skip from previous gate ---
            if skip_next:
                skip_next = False
                print(f"\n  Step {step_num} ({step_def['name']}): SKIPPED by user")
                state.mark_skipped(step_num, "Skipped by user at gate")
                continue

            # --- Skip check ---
            skip_reason = step_def["skip_check"](ctx)
            if skip_reason:
                print(f"\n  Step {step_num} ({step_def['name']}): SKIPPABLE -- {skip_reason}")
                if args.dry_run:
                    print(f"  [dry-run] Would skip")
                    continue
                if args.auto_go:
                    print(f"  [auto-go] Skipping")
                    state.mark_skipped(step_num, skip_reason)
                    continue
                choice = prompt_gate("  [S]kip  [R]un anyway:",
                                     ["s", "skip", "", "r", "run"])
                if choice in ("s", "skip", ""):
                    state.mark_skipped(step_num, skip_reason)
                    continue

            # --- Build command ---
            cmd = step_def["build_cmd"](ctx)

            if args.dry_run:
                print(f"\n  Step {step_num} ({step_def['name']}):")
                print(f"  Would run: {' '.join(cmd)}")
                continue

            # --- Execute ---
            print_divider(f"Step {step_num}: {step_def['name']}")
            state.mark_started(step_num)
            step_start = time.time()

            exit_code = run_step(cmd, step_def["name"])

            if exit_code != 0:
                elapsed = time.time() - step_start
                state.mark_failed(step_num, f"Exit code {exit_code}")

                action = handle_failure(step_num, step_def["name"], args.auto_go)
                while action == "retry":
                    state.mark_started(step_num)
                    step_start = time.time()
                    exit_code = run_step(cmd, step_def["name"])
                    if exit_code == 0:
                        break
                    state.mark_failed(step_num, f"Exit code {exit_code}")
                    action = handle_failure(step_num, step_def["name"],
                                            args.auto_go)

                if exit_code != 0:
                    print_summary(state, step_timings, pipeline_start)
                    sys.exit(1)

            elapsed = time.time() - step_start
            step_timings[step_num] = elapsed
            outputs = step_def["outputs"](ctx)
            state.mark_completed(step_num,
                                 [str(p) for p in outputs if p.exists()],
                                 elapsed)

            # --- Reload script after step 0 or step 3 (they mutate the JSON) ---
            if step_num == 0:
                sp = Path(ctx["script_path"])
                if sp.exists():
                    with open(sp) as f:
                        ctx["script_data"] = json.load(f)

            if step_num == 3:
                with open(ctx["script_path"]) as f:
                    ctx["script_data"] = json.load(f)

            # --- Gate ---
            next_idx = i + 1
            # Find next step that's not before start_from
            next_step = None
            next_name = None
            while next_idx < len(STEP_ORDER):
                ns = STEP_ORDER[next_idx]
                if ns >= start_from:
                    next_step = ns
                    next_name = STEPS[ns]["name"]
                    break
                next_idx += 1

            decision = gate(step_num, step_def["name"], outputs, elapsed,
                            next_step, next_name, args.auto_go)

            if decision == "quit":
                print_summary(state, step_timings, pipeline_start)
                sys.exit(0)
            elif decision == "skip":
                skip_next = True

        # --- Final summary ---
        final_output = _outputs_step8(ctx)[0] if not args.dry_run else None
        print_summary(state, step_timings, pipeline_start, final_output)

    except KeyboardInterrupt:
        print("\n\n  Interrupted by user.")
        print_summary(state, step_timings, pipeline_start)
        sys.exit(130)


if __name__ == "__main__":
    main()
