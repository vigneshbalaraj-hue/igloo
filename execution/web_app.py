"""
web_app.py — Flask web UI for the Reel Engine pipeline.

Provides a browser-based interface for:
  - Step 0: Script generation (theme, topic, narration, character, full JSON)
  - Steps 1-8: Pipeline execution with live logs, gates, and progress

Usage:
    py execution/web_app.py
    # Opens http://localhost:5000

"""

import json
import queue
import re
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, request, jsonify, Response, send_file

# Local — shared with generate_script.py
sys.path.insert(0, str(Path(__file__).resolve().parent))
import prompt_bank as pb  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
app = Flask(__name__)

# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------

# Pipeline execution state (one pipeline at a time)
pipeline_state = {
    "running": False,
    "current_step": None,
    "script_path": None,
    "logs": [],
    "step_statuses": {},  # {step_num: "running"|"completed"|"skipped"|"failed"|"waiting_gate"}
    "gate_pending": False,
    "gate_step": None,
    "process": None,
}

log_queues = {}  # session_id -> queue.Queue for SSE


def broadcast_event(event_type: str, data: dict):
    """Send event to all connected SSE clients."""
    msg = json.dumps({"type": event_type, **data})
    for q in log_queues.values():
        q.put(msg)


# ---------------------------------------------------------------------------
# Gemini helpers (reused from generate_script.py)
# ---------------------------------------------------------------------------

def load_env(key: str) -> str | None:
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


def call_gemini(prompt: str, api_key: str, temperature: float = 0.5,
                max_tokens: int = 8192, timeout: int = 90) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
            "thinkingConfig": {"thinkingBudget": 0}
        }
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        result = json.loads(resp.read().decode())
    parts = result["candidates"][0]["content"]["parts"]
    text = ""
    for part in parts:
        if "text" in part:
            text = part["text"].strip()
    return text


def extract_json_from_text(text: str):
    if "```" in text:
        blocks = text.split("```")
        for block in blocks[1::2]:
            cleaned = block.strip()
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                continue
    # Try raw parse
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', text.strip())
        if match:
            return json.loads(match.group(1))
        raise ValueError(f"Could not extract JSON from response")


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'[\s-]+', '_', text)
    return text.strip('_')


# ---------------------------------------------------------------------------
# Gemini prompts (same as generate_script.py)
# ---------------------------------------------------------------------------

# NARRATION_GENERATE_PROMPT removed — the from-scratch path now goes through
# prompt_bank.build_narration_prompt() (see /api/generate-narration). The
# adapt path below is kept verbatim because user-supplied scripts must be
# preserved word-for-word.

NARRATION_ADAPT_PROMPT = """You are a viral short-form video scriptwriter. The user has provided a narration script. Adapt it into a structured scene-by-scene format for a {duration}-second vertical reel.

TOPIC: {topic}
THEME: {theme}

USER'S SCRIPT:
{script}

RULES:
- Break the script into alternating "anchor" (direct-to-camera) and "b-roll" (cinematic footage) scenes
- Start and end with anchor scenes
- Aim for ~9 scenes (odd number)
- Preserve the user's words and voice as much as possible
- If the script is too long/short for {duration}s, adjust slightly

For each scene provide:
- scene_id (integer, sequential starting at 1)
- type ("anchor" or "b-roll")
- voice_emotion (one of: firm, urgent, contemplative, informative, warm, reassuring, gentle, confident)
- purpose (short description)
- narration_text (the actual words spoken)
- caption_text (same as narration but with 1-2 KEY emphasis words in ALL CAPS)

Return ONLY a JSON array of scene objects. No explanation."""


NARRATION_EDIT_PROMPT = """Revise the following scene-by-scene script based on user feedback.

CURRENT SCRIPT:
{current_script}

USER'S FEEDBACK:
{feedback}

Apply changes while maintaining alternating anchor/b-roll structure. Keep scene_ids sequential.
Return ONLY the revised JSON array. No explanation."""


CHARACTER_PROMPT = """Based on this script for a "{theme}" reel about "{topic}", suggest 3 anchor character options.

SCRIPT NARRATION:
{narration}

For each character option, provide a JSON object with:
- "option": integer (1, 2, or 3)
- "description": Detailed description (ethnicity, age, clothing, setting)
- "image_prompt": Photorealistic Imagen prompt with camera specs (e.g., "shot on Sony A7IV, 50mm f/1.8, shallow depth of field"), lighting. NO abstract emotional cues.
- "voice": object with "gender", "accent", "tone"

Make characters diverse and authentic to the content.
Return ONLY a JSON array of 3 objects. No explanation."""


CHARACTER_CUSTOM_PROMPT = """Generate a full anchor character object from this description.

USER'S DESCRIPTION: {description}
REEL TOPIC: {topic}

Return JSON with:
- "description": expanded detailed description
- "image_prompt": photorealistic Imagen prompt with camera specs, lighting. NO abstract cues.
- "voice": object with "gender", "accent", "tone"

Return ONLY the JSON object. No explanation."""


ASSEMBLY_PROMPT = """Generate a complete Reel Engine script JSON.

THEME: {theme}
TOPIC: {topic}
TARGET DURATION: {duration}s

LOCKED SCENES:
{scenes_json}

ANCHOR CHARACTER:
{character_json}

Structure:
{{
  "video_file": "{slug}.mp4",
  "theme": "{theme}",
  "topic": "{topic}",
  "total_scenes": <count>,
  "voiceover_speed": 1.3,
  "voiceover_model": "eleven_turbo_v2_5",
  "skip_caption_scenes": [],
  "anchor_character": {{
    "description": "<from character>",
    "image_prompt": "<from character>",
    "voice": {{ "gender": "...", "accent": "...", "tone": "..." }}
  }},
  "scenes": [
    <ANCHOR scenes:>
    {{ "scene_id": N, "type": "anchor", "voice_emotion": "...", "purpose": "...",
       "narration_text": "...",
       "video_generation": {{ "method": "lip-sync", "kling_duration": "driven by audio",
         "image_prompt": null (except scene 1 which gets full prompt),
         "image_note": "Reuse anchor image from scene 1",
         "video_prompt": "<minimal gestures, photorealistic>" }},
       "caption_text": "..." }},

    <B-ROLL scenes:>
    {{ "scene_id": N, "type": "b-roll", "voice_emotion": "...", "purpose": "...",
       "narration_text": "...",
       "video_generation": {{ "method": "image-to-video", "kling_duration": 5,
         "trim_to": <estimate 3-5s>,
         "image_prompt": "<photorealistic, camera specs, concrete visuals>",
         "video_prompt": "<slow camera movement + subtle motion>" }},
       "caption_text": "..." }},

    <B-ROLL with >12 words: SPLIT into clips array with clip_id "Na", "Nb">
  ],
  "audio": {{
    "voice_over": {{ "full_script": "<all narration joined>", "file": "voiceover.mp3",
      "timestamps_file": "voiceover_words.json", "speed": 1.3, "model": "eleven_turbo_v2_5" }},
    "background_music": {{ "description": "<mood-matching, MUST end with 'Instrumental only, no vocals, no singing, no humming.'>",
      "bpm": <tempo>, "genre": "<genre>" }}
  }},
  "assembly_notes": {{ "transitions": "0.3s cross-dissolve between all scenes.",
    "captions": "Large white text, bold emphasized words rendered yellow.",
    "color_grade": "<appropriate>", "aspect_ratio": "9:16 (vertical reel format)",
    "audio_sync": "Anchor: lip-sync via Avatar API. B-roll: voiceover over footage." }},
  "production_summary": {{ "total_kling_generations": <count>,
    "images_needed": {{ "anchor": 1, "broll": <count>, "total": <total>,
      "reuse": "Anchor image reused across all anchor scenes" }} }}
}}

Do NOT include narration_start/end, scene_duration, audio_slice, actual_duration_seconds, or elevenlabs_voice_id.
Image prompts: photorealistic, concrete, camera specs. NO abstract emotional cues.
Anchor video prompts: minimal to not override lip-sync.

Return ONLY the JSON object. No explanation."""


# ---------------------------------------------------------------------------
# Routes — Pages
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


# ---------------------------------------------------------------------------
# Routes — Script Generation API
# ---------------------------------------------------------------------------

@app.route("/api/generate-narration", methods=["POST"])
def api_generate_narration():
    data = request.json
    theme = data.get("theme", "")
    topic = data.get("topic", "")
    duration = data.get("duration", 40)
    user_script = data.get("script", "")
    niche = data.get("niche")  # optional override; auto-resolved from theme if absent

    api_key = load_env("GEMINI_API_KEY")
    if not api_key:
        return jsonify({"error": "GEMINI_API_KEY not set in .env"}), 500
    voice_id = load_env("ELEVENLABS_VOICE_ID")  # may be None on first setup

    try:
        if user_script.strip():
            # User-supplied script: preserve their words, only re-shape into scenes.
            prompt = NARRATION_ADAPT_PROMPT.format(
                theme=theme, topic=topic, duration=duration, script=user_script)
            raw = call_gemini(prompt, api_key, temperature=0.7)
            scenes = extract_json_from_text(raw)
            return jsonify({"scenes": scenes, "niche": None})

        # From-scratch path: prompt bank.
        prompt, resolved_niche = pb.build_narration_prompt(
            theme=theme, topic=topic, duration=duration,
            niche=niche, api_key=api_key, voice_id=voice_id)
        raw = call_gemini(prompt, api_key, temperature=0.9)
        scenes = extract_json_from_text(raw)

        # Bug 2 fix: deterministic repair pass before validation. Fixes
        # recoverable LLM drift (typo'd field names, banned chars, missing
        # captions) without burning a retry call.
        scenes, repair_log = pb.repair_scenes(scenes)

        # Step 5 validation with single regenerate-on-failure. The retry
        # prompt restates the FULL schema, not just the failures, to prevent
        # the multi-bug cascade observed in session 19.
        failures = pb.validate_scenes(scenes, duration, voice_id=voice_id)
        retry_repair_log: list[str] = []
        if failures:
            retry_prompt = pb.build_retry_prompt(
                base_prompt=prompt,
                failures=failures,
                duration=duration,
                voice_id=voice_id,
            )
            raw = call_gemini(retry_prompt, api_key, temperature=0.9)
            scenes = extract_json_from_text(raw)
            scenes, retry_repair_log = pb.repair_scenes(scenes)
            failures = pb.validate_scenes(scenes, duration, voice_id=voice_id)

        return jsonify({
            "scenes": scenes,
            "niche": resolved_niche,
            "validation_warnings": failures or None,
            "repair_log": (repair_log + retry_repair_log) or None,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/edit-narration", methods=["POST"])
def api_edit_narration():
    data = request.json
    scenes = data.get("scenes", [])
    feedback = data.get("feedback", "")

    api_key = load_env("GEMINI_API_KEY")
    if not api_key:
        return jsonify({"error": "GEMINI_API_KEY not set in .env"}), 500

    try:
        prompt = NARRATION_EDIT_PROMPT.format(
            current_script=json.dumps(scenes, indent=2), feedback=feedback)
        raw = call_gemini(prompt, api_key, temperature=0.5)
        scenes = extract_json_from_text(raw)
        return jsonify({"scenes": scenes})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/generate-characters", methods=["POST"])
def api_generate_characters():
    data = request.json
    theme = data.get("theme", "")
    topic = data.get("topic", "")
    scenes = data.get("scenes", [])

    api_key = load_env("GEMINI_API_KEY")
    if not api_key:
        return jsonify({"error": "GEMINI_API_KEY not set in .env"}), 500

    try:
        narration = " ".join(s.get("narration_text", "") for s in scenes)
        prompt = CHARACTER_PROMPT.format(
            theme=theme, topic=topic, narration=narration)
        raw = call_gemini(prompt, api_key, temperature=0.7)
        options = extract_json_from_text(raw)
        return jsonify({"characters": options})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/custom-character", methods=["POST"])
def api_custom_character():
    data = request.json
    description = data.get("description", "")
    topic = data.get("topic", "")

    api_key = load_env("GEMINI_API_KEY")
    if not api_key:
        return jsonify({"error": "GEMINI_API_KEY not set in .env"}), 500

    try:
        prompt = CHARACTER_CUSTOM_PROMPT.format(description=description, topic=topic)
        raw = call_gemini(prompt, api_key, temperature=0.5)
        character = extract_json_from_text(raw)
        return jsonify({"character": character})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/assemble-script", methods=["POST"])
def api_assemble_script():
    data = request.json
    theme = data.get("theme", "")
    topic = data.get("topic", "")
    duration = data.get("duration", 40)
    scenes = data.get("scenes", [])
    character = data.get("character", {})

    api_key = load_env("GEMINI_API_KEY")
    if not api_key:
        return jsonify({"error": "GEMINI_API_KEY not set in .env"}), 500

    slug = slugify(topic)
    try:
        prompt = ASSEMBLY_PROMPT.format(
            theme=theme, topic=topic, slug=slug, duration=duration,
            scenes_json=json.dumps(scenes, indent=2),
            character_json=json.dumps(character, indent=2))
        raw = call_gemini(prompt, api_key, temperature=0.3,
                          max_tokens=16384, timeout=120)
        script_json = extract_json_from_text(raw)
        return jsonify({"script": script_json})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/save-script", methods=["POST"])
def api_save_script():
    data = request.json
    topic = data.get("topic", "")
    script_json = data.get("script", {})

    slug = slugify(topic)
    output_dir = PROJECT_ROOT / ".tmp" / slug
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{slug}_script.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(script_json, f, indent=2, ensure_ascii=False)

    return jsonify({"path": str(output_path), "relative": f".tmp/{slug}/{slug}_script.json"})


# ---------------------------------------------------------------------------
# Routes — Pipeline Execution API
# ---------------------------------------------------------------------------

@app.route("/api/list-scripts", methods=["GET"])
def api_list_scripts():
    """List all existing script JSON files."""
    tmp_dir = PROJECT_ROOT / ".tmp"
    scripts = []
    if tmp_dir.exists():
        for script_file in tmp_dir.glob("*/*_script.json"):
            try:
                with open(script_file) as f:
                    data = json.load(f)
                scripts.append({
                    "path": str(script_file),
                    "relative": str(script_file.relative_to(PROJECT_ROOT)),
                    "theme": data.get("theme", ""),
                    "topic": data.get("topic", ""),
                    "scenes": data.get("total_scenes", 0),
                })
            except (json.JSONDecodeError, KeyError):
                continue
    return jsonify({"scripts": scripts})


STEP_NAMES = {
    1: "Voice Selection",
    2: "Voiceover",
    3: "Timestamp Extraction",
    4: "Audio Slicing",
    5: "Image Generation",
    6: "Video Clip Generation",
    7: "Background Music",
    8: "Assembly",
}

CINEMATIC_PHASES = {
    1: "Finding the perfect voice...",
    2: "Crafting your story...",
    3: "Syncing every word...",
    4: "Preparing the narration...",
    5: "Painting the scenes...",
    6: "Bringing your vision to life...",
    7: "Composing the soundtrack...",
    8: "The final cut...",
}

# Estimated seconds per step (for time-remaining calculation)
STEP_TIME_ESTIMATES = {
    1: 10, 2: 20, 3: 10, 4: 5, 5: 45, 6: 210, 7: 45, 8: 30,
}
TOTAL_ESTIMATED = sum(STEP_TIME_ESTIMATES.values())


def run_pipeline_thread(script_path: str, speed: float, audio_mode: str,
                        no_captions: bool, start_from: int,
                        auto_go: bool = False,
                        music_volume: float = 0.10,
                        voice_volume: float = 1.5):
    """Run pipeline steps sequentially in a background thread."""
    global pipeline_state

    pipeline_state["running"] = True
    pipeline_state["script_path"] = script_path
    pipeline_state["logs"] = []
    pipeline_state["step_statuses"] = {i: "pending" for i in range(1, 9)}
    pipeline_state["gate_pending"] = False

    steps_to_run = list(range(max(1, start_from), 9))

    # Mark steps before start_from as skipped
    for i in range(1, start_from):
        pipeline_state["step_statuses"][i] = "skipped"
        broadcast_event("step_status", {"step": i, "status": "skipped", "reason": "Before start step"})

    # Track cumulative time for progress estimation
    elapsed_total = 0

    for step_num in steps_to_run:
        if not pipeline_state["running"]:
            break

        step_name = STEP_NAMES[step_num]
        pipeline_state["current_step"] = step_num
        pipeline_state["step_statuses"][step_num] = "running"
        broadcast_event("step_status", {"step": step_num, "status": "running", "name": step_name})

        # Broadcast cinematic phase + progress
        remaining_est = sum(STEP_TIME_ESTIMATES[s] for s in range(step_num, 9))
        completed_est = sum(STEP_TIME_ESTIMATES[s] for s in range(1, step_num))
        progress_pct = round((completed_est / TOTAL_ESTIMATED) * 100) if TOTAL_ESTIMATED > 0 else 0
        broadcast_event("phase", {
            "step": step_num,
            "message": CINEMATIC_PHASES.get(step_num, step_name),
            "remaining_seconds": remaining_est,
            "progress": progress_pct,
        })

        # Build command
        cmd = _build_step_cmd(step_num, script_path, speed, audio_mode,
                              no_captions, music_volume, voice_volume)
        broadcast_event("log", {"text": f"$ {' '.join(cmd)}", "level": "cmd"})

        step_start = time.time()
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=str(PROJECT_ROOT),
                text=True,
                bufsize=1
            )
            pipeline_state["process"] = proc

            for line in proc.stdout:
                line = line.rstrip('\n')
                pipeline_state["logs"].append(line)
                broadcast_event("log", {"text": line, "level": "info"})

            proc.wait()
            elapsed = time.time() - step_start
            elapsed_total += elapsed

            if proc.returncode != 0:
                pipeline_state["step_statuses"][step_num] = "failed"
                broadcast_event("step_status", {
                    "step": step_num, "status": "failed",
                    "name": step_name, "elapsed": round(elapsed, 1),
                    "error": f"Exit code {proc.returncode}"
                })

                if auto_go:
                    # In auto mode, abort on failure
                    broadcast_event("pipeline_error", {
                        "step": step_num,
                        "error": f"Step {step_num} ({step_name}) failed with exit code {proc.returncode}"
                    })
                    break
                else:
                    # Wait for user decision (retry/skip/abort)
                    pipeline_state["gate_pending"] = True
                    pipeline_state["gate_step"] = step_num
                    broadcast_event("gate", {
                        "step": step_num, "name": step_name,
                        "type": "error",
                        "message": f"Step {step_num} ({step_name}) failed with exit code {proc.returncode}"
                    })
                    while pipeline_state["gate_pending"] and pipeline_state["running"]:
                        time.sleep(0.2)

                    gate_response = pipeline_state.get("gate_response", "abort")
                    if gate_response == "abort":
                        break
                    elif gate_response == "skip":
                        pipeline_state["step_statuses"][step_num] = "skipped"
                        continue
                    elif gate_response == "retry":
                        continue
            else:
                pipeline_state["step_statuses"][step_num] = "completed"
                broadcast_event("step_status", {
                    "step": step_num, "status": "completed",
                    "name": step_name, "elapsed": round(elapsed, 1)
                })

        except Exception as e:
            pipeline_state["step_statuses"][step_num] = "failed"
            broadcast_event("step_status", {
                "step": step_num, "status": "failed",
                "name": step_name, "error": str(e)
            })
            if auto_go:
                broadcast_event("pipeline_error", {
                    "step": step_num, "error": str(e)
                })
            break

        # Gate: wait for user GO between steps (only in manual mode)
        if not auto_go and step_num < 8 and pipeline_state["running"]:
            next_step = step_num + 1
            if next_step <= 8:
                pipeline_state["gate_pending"] = True
                pipeline_state["gate_step"] = step_num
                broadcast_event("gate", {
                    "step": step_num, "name": step_name,
                    "type": "approval",
                    "next_step": next_step, "next_name": STEP_NAMES[next_step],
                    "message": f"Step {step_num} ({step_name}) completed. Proceed to Step {next_step} ({STEP_NAMES[next_step]})?"
                })
                while pipeline_state["gate_pending"] and pipeline_state["running"]:
                    time.sleep(0.2)

                gate_response = pipeline_state.get("gate_response", "go")
                if gate_response == "abort":
                    break
                elif gate_response == "skip":
                    if next_step <= 8:
                        pipeline_state["step_statuses"][next_step] = "skipped"
                        broadcast_event("step_status", {"step": next_step, "status": "skipped", "reason": "Skipped by user"})
                        steps_to_run = [s for s in steps_to_run if s != next_step]

    # Determine success and find output file
    all_ok = all(
        pipeline_state["step_statuses"].get(s) in ("completed", "skipped")
        for s in range(1, 9)
    )
    download_path = None
    if all_ok:
        script_dir = Path(script_path).parent
        for pattern in ["final_reel_optionc.mp4", "final_reel*.mp4"]:
            matches = list(script_dir.glob(pattern))
            if matches:
                download_path = str(matches[0])
                break

    # Final progress update
    broadcast_event("phase", {
        "step": 8, "message": "Done.",
        "remaining_seconds": 0, "progress": 100,
    })

    pipeline_state["running"] = False
    pipeline_state["current_step"] = None
    pipeline_state["process"] = None
    broadcast_event("pipeline_done", {
        "statuses": pipeline_state["step_statuses"],
        "success": all_ok,
        "download_path": download_path,
    })


def _build_step_cmd(step_num: int, script_path: str,
                    speed: float, audio_mode: str, no_captions: bool,
                    music_volume: float = 0.10,
                    voice_volume: float = 1.5) -> list[str]:
    py = sys.executable
    if step_num == 1:
        return [py, "execution/select_voice.py", script_path, "--auto"]
    elif step_num == 2:
        cmd = [py, "execution/generate_voiceover.py", script_path]
        if speed != 1.0:
            cmd.extend(["--speed", str(speed)])
        return cmd
    elif step_num == 3:
        script_dir = str(Path(script_path).parent)
        ts_path = str(Path(script_dir) / "voiceover_timestamps.json")
        return [py, "execution/extract_word_timestamps.py", ts_path,
                "--update-script", script_path]
    elif step_num == 4:
        return [py, "execution/slice_audio.py", script_path]
    elif step_num == 5:
        return [py, "execution/generate_images.py", script_path]
    elif step_num == 6:
        return [py, "execution/generate_video_clips.py", script_path]
    elif step_num == 7:
        return [py, "execution/generate_music.py", script_path]
    elif step_num == 8:
        cmd = [py, "execution/assemble_video.py", script_path,
               "--audio-mode", audio_mode,
               "--music-volume", str(music_volume),
               "--voice-volume", str(voice_volume)]
        if no_captions:
            cmd.append("--no-captions")
        return cmd
    return []


@app.route("/api/pipeline/start", methods=["POST"])
def api_pipeline_start():
    if pipeline_state["running"]:
        return jsonify({"error": "Pipeline already running"}), 409

    data = request.json
    script_path = data.get("script_path", "")
    speed = data.get("speed", 1.0)
    audio_mode = data.get("audio_mode", "option-c")
    no_captions = data.get("no_captions", False)
    start_from = data.get("start_from", 1)
    auto_go = data.get("auto_go", False)
    music_volume = data.get("music_volume", 0.10)
    voice_volume = data.get("voice_volume", 1.5)

    if not Path(script_path).exists():
        return jsonify({"error": f"Script not found: {script_path}"}), 400

    thread = threading.Thread(
        target=run_pipeline_thread,
        args=(script_path, speed, audio_mode, no_captions, start_from,
              auto_go, music_volume, voice_volume),
        daemon=True
    )
    thread.start()

    return jsonify({"status": "started"})


@app.route("/api/pipeline/gate", methods=["POST"])
def api_pipeline_gate():
    data = request.json
    response = data.get("response", "go")  # go, skip, abort, retry
    pipeline_state["gate_response"] = response
    pipeline_state["gate_pending"] = False
    return jsonify({"status": "ok"})


@app.route("/api/pipeline/stop", methods=["POST"])
def api_pipeline_stop():
    pipeline_state["running"] = False
    pipeline_state["gate_pending"] = False
    proc = pipeline_state.get("process")
    if proc and proc.poll() is None:
        proc.terminate()
    return jsonify({"status": "stopped"})


@app.route("/api/pipeline/status", methods=["GET"])
def api_pipeline_status():
    return jsonify({
        "running": pipeline_state["running"],
        "current_step": pipeline_state["current_step"],
        "step_statuses": pipeline_state["step_statuses"],
        "gate_pending": pipeline_state["gate_pending"],
        "gate_step": pipeline_state["gate_step"],
    })


# ---------------------------------------------------------------------------
# Routes — Script Editing & Download
# ---------------------------------------------------------------------------

SCRIPT_EDIT_PROMPT = """Edit the following complete Reel Engine script JSON based on user feedback.

CURRENT SCRIPT:
{script_json}

USER'S FEEDBACK:
{feedback}

Apply the requested changes while maintaining the overall structure and all required fields.
Return ONLY the edited JSON object. No explanation."""


@app.route("/api/edit-script", methods=["POST"])
def api_edit_script():
    data = request.json
    script = data.get("script", {})
    feedback = data.get("feedback", "")

    api_key = load_env("GEMINI_API_KEY")
    if not api_key:
        return jsonify({"error": "GEMINI_API_KEY not set in .env"}), 500

    try:
        prompt = SCRIPT_EDIT_PROMPT.format(
            script_json=json.dumps(script, indent=2),
            feedback=feedback)
        raw = call_gemini(prompt, api_key, temperature=0.3,
                          max_tokens=16384, timeout=120)
        edited = extract_json_from_text(raw)
        return jsonify({"script": edited})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/download")
def api_download():
    path = request.args.get("path", "")
    resolved = Path(path).resolve()
    tmp_dir = (PROJECT_ROOT / ".tmp").resolve()
    if not str(resolved).startswith(str(tmp_dir)):
        return jsonify({"error": "Invalid path"}), 403
    if not resolved.exists():
        return jsonify({"error": "File not found"}), 404
    return send_file(str(resolved), as_attachment=True,
                     download_name=resolved.name)


# ---------------------------------------------------------------------------
# SSE (Server-Sent Events) for live updates
# ---------------------------------------------------------------------------

@app.route("/api/events")
def api_events():
    session_id = str(time.time())
    q = queue.Queue()
    log_queues[session_id] = q

    def stream():
        try:
            while True:
                try:
                    msg = q.get(timeout=30)
                    yield f"data: {msg}\n\n"
                except queue.Empty:
                    yield f"data: {json.dumps({'type': 'ping'})}\n\n"
        finally:
            log_queues.pop(session_id, None)

    return Response(stream(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"\n  Reel Engine Web UI")
    print(f"  http://localhost:5000\n")
    app.run(debug=False, port=5000, threaded=True)
