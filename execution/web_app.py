"""
web_app.py — Flask web UI for the Reel Engine pipeline (multi-tenant).

Provides a browser-based interface for:
  - Step 0: Script generation (theme, topic, narration, character, full JSON)
  - Steps 1-8: Pipeline execution with live logs and SSE progress

Hosting model:
  - On Modal (production): wrapped by @modal.wsgi_app() in infra/modal/igloo_worker.py.
    Entry requires a signed studio token minted by Next.js (Clerk + Razorpay gates).
  - On localhost (dev): if IGLOO_STUDIO_SECRET is unset, falls back to a synthetic
    'dev' user/run so the existing local workflow keeps working.

Multi-tenancy:
  - All pipeline state is keyed by user_id (read from flask.session).
  - Pipelines run in /tmp/igloo/<user_id>/<slug>/ on Linux,
    PROJECT_ROOT/.tmp/igloo/<user_id>/<slug>/ on Windows.
  - Concurrent pipeline execution is capped at IGLOO_MAX_PIPELINES (default 3,
    matched to Kling's 20 concurrent generation cap).

Usage:
    py execution/web_app.py
    # Opens http://localhost:5000

"""

import base64
import hashlib
import hmac as _hmac
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path

from flask import (
    Flask, render_template, request, jsonify, Response, session,
)

# Local — shared with generate_script.py
sys.path.insert(0, str(Path(__file__).resolve().parent))
import prompt_bank as pb  # noqa: E402
from gemini_client import call_gemini  # noqa: E402
from select_voice import build_voice_profile, search_shared_voices, rank_with_gemini  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Config (env-driven, lazy where possible)
# ---------------------------------------------------------------------------

IGLOO_STUDIO_SECRET = os.environ.get("IGLOO_STUDIO_SECRET")
IGLOO_APP_URL = os.environ.get("IGLOO_APP_URL", "http://localhost:3000")
IGLOO_MAX_PIPELINES = int(os.environ.get("IGLOO_MAX_PIPELINES", "3"))

# Dev mode: no Next.js front door, no token minted, no Supabase wired up.
# Lets `python web_app.py` continue to work on the laptop.
IGLOO_DEV_MODE = not IGLOO_STUDIO_SECRET

# Per-OS workdir root. Modal containers are Linux → /tmp/igloo. Windows dev →
# repo .tmp/igloo (so existing test scripts can find intermediates).
if os.name == "nt":
    _DEFAULT_WORKDIR_ROOT = str(PROJECT_ROOT / ".tmp" / "igloo")
else:
    _DEFAULT_WORKDIR_ROOT = "/tmp/igloo"
WORKDIR_ROOT = Path(os.environ.get("IGLOO_WORKDIR_ROOT", _DEFAULT_WORKDIR_ROOT))

app = Flask(__name__)
# Flask session cookie signing key. In dev fall back to a placeholder; in prod
# the studio secret is required and is also reused as the session key.
app.secret_key = IGLOO_STUDIO_SECRET or "igloo-dev-only-not-secure"


# ---------------------------------------------------------------------------
# HMAC studio-token verification (mirrors app/src/lib/studio-token.ts)
# Format: base64url(json(payload)).base64url(hmac_sha256(payload_b64))
# ---------------------------------------------------------------------------

def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def verify_studio_token(token: str) -> dict | None:
    """Verify an HMAC-signed studio token. Returns payload dict or None."""
    if not IGLOO_STUDIO_SECRET:
        return None
    if not token or "." not in token:
        return None
    try:
        payload_b64, sig_b64 = token.split(".", 1)
    except ValueError:
        return None

    expected = _hmac.new(
        IGLOO_STUDIO_SECRET.encode("utf-8"),
        payload_b64.encode("ascii"),
        hashlib.sha256,
    ).digest()
    try:
        given = _b64url_decode(sig_b64)
    except Exception:
        return None
    if len(expected) != len(given) or not _hmac.compare_digest(expected, given):
        return None

    try:
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except Exception:
        return None

    exp = payload.get("exp")
    if not isinstance(exp, (int, float)):
        return None
    # exp is ms since epoch (matching JS Date.now())
    if time.time() * 1000 > exp:
        return None
    if not payload.get("run_id") or not payload.get("user_id"):
        return None
    return payload


# ---------------------------------------------------------------------------
# Per-user state (replaces the old singleton pipeline_state)
# ---------------------------------------------------------------------------

_pipeline_states: dict[str, dict] = {}
_log_queues: dict[str, dict[str, queue.Queue]] = {}
_state_locks: dict[str, threading.Lock] = {}
_global_lock = threading.Lock()


def _default_state() -> dict:
    return {
        "running": False,
        "queue_status": None,        # None | 'queued' | 'running'
        "current_step": None,
        "script_path": None,
        "logs": [],
        "step_statuses": {},
        "gate_pending": False,
        "gate_step": None,
        "gate_response": None,
        "process": None,
        "run_id": None,
    }


def get_state(user_id: str) -> dict:
    with _global_lock:
        if user_id not in _pipeline_states:
            _pipeline_states[user_id] = _default_state()
            _state_locks[user_id] = threading.Lock()
            _log_queues[user_id] = {}
        return _pipeline_states[user_id]


def get_state_lock(user_id: str) -> threading.Lock:
    with _global_lock:
        return _state_locks.setdefault(user_id, threading.Lock())


def get_user_queues(user_id: str) -> dict[str, queue.Queue]:
    with _global_lock:
        return _log_queues.setdefault(user_id, {})


def broadcast_event(user_id: str, event_type: str, data: dict):
    """Push an SSE event to all of one user's connected clients."""
    msg = json.dumps({"type": event_type, **data})
    for q in list(get_user_queues(user_id).values()):
        q.put(msg)


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def current_user_id() -> str | None:
    sess = session.get("igloo")
    return sess.get("user_id") if sess else None


def current_run_id() -> str | None:
    sess = session.get("igloo")
    return sess.get("run_id") if sess else None


def _ensure_dev_session():
    """In dev mode, transparently inject a synthetic session if missing."""
    if IGLOO_DEV_MODE and not session.get("igloo"):
        session["igloo"] = {"user_id": "dev", "run_id": "dev-run"}


def require_auth(fn):
    """API decorator: 401 if no session, except in dev mode where it self-heals."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user_id():
            if IGLOO_DEV_MODE:
                _ensure_dev_session()
            else:
                return jsonify({"error": "unauthorized"}), 401
        return fn(*args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# Workdir helpers
# ---------------------------------------------------------------------------

def user_workdir(user_id: str, slug: str) -> Path:
    return WORKDIR_ROOT / user_id / slug


# ---------------------------------------------------------------------------
# Supabase client (lazy, optional in dev)
# ---------------------------------------------------------------------------

_sb_client = None


def supabase_client():
    """Return cached Supabase client, or None if not configured (dev mode)."""
    global _sb_client
    if _sb_client is not None:
        return _sb_client
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        return None
    try:
        from supabase import create_client
    except ImportError:
        return None
    _sb_client = create_client(url, key)
    return _sb_client


# ---------------------------------------------------------------------------
# Pipeline-slot queue (Policy 2: cap concurrent pipelines, wizard is free)
# ---------------------------------------------------------------------------

def _sweep_orphan_queued():
    """Fail queued runs older than 4 hours (orphaned after Fly restart). Cheap, race-safe."""
    sb = supabase_client()
    if sb is None:
        return
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=4)).isoformat()
        sb.table("runs").update({
            "status": "failed",
            "rejection_reason": "queue_timeout",
        }).eq("status", "queued").lt("created_at", cutoff).execute()
    except Exception:
        pass


class SlotAcquireError(Exception):
    """Raised when a run can never acquire a slot — missing row or wrong status."""


def try_acquire_slot(run_id: str) -> bool:
    """
    Atomically promote a draft/queued run to 'running' if a slot is available.
    Returns True if acquired, False if all slots are full.
    Raises SlotAcquireError if the run row is missing or in a non-acquirable
    state (failed/delivered/etc) — those are unrecoverable, not "wait longer".

    Note: count + update is not a single SQL transaction, so a sub-millisecond
    race window exists where N+1 pipelines could briefly start. Acceptable for
    MVP — Kling cap is 20 generations, default IGLOO_MAX_PIPELINES=3 ≈ 18.
    """
    sb = supabase_client()
    if sb is None:
        return True  # dev mode: always acquire

    _sweep_orphan_queued()

    # Check the run actually exists and is in an acquirable state. Without
    # this, a stale token pointing at a 'failed' row would loop forever in
    # the queue UI because the UPDATE below would silently match 0 rows.
    try:
        row = sb.table("runs").select("status").eq("id", run_id).maybe_single().execute().data
    except Exception as e:
        raise SlotAcquireError(f"run lookup failed: {e}") from e
    if row is None:
        raise SlotAcquireError(f"run {run_id} not found in database")
    if row["status"] not in ("draft", "queued"):
        raise SlotAcquireError(f"run {run_id} is in status {row['status']!r}, not acquirable")

    try:
        running = sb.table("runs").select("id", count="exact") \
            .eq("status", "running").execute()
        running_count = running.count or 0
    except Exception:
        return False

    if running_count >= IGLOO_MAX_PIPELINES:
        return False

    try:
        result = sb.table("runs").update({
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", run_id).in_("status", ["draft", "queued"]).execute()
    except Exception:
        return False

    return bool(result.data)


def mark_run_queued(run_id: str):
    sb = supabase_client()
    if sb is None:
        return
    try:
        sb.table("runs").update({"status": "queued"}) \
            .eq("id", run_id).in_("status", ["draft"]).execute()
    except Exception:
        pass


def queue_position(run_id: str) -> int:
    """Return how many runs are ahead of this one in the queue (0 = next up)."""
    sb = supabase_client()
    if sb is None:
        return 0
    try:
        row = sb.table("runs").select("created_at") \
            .eq("id", run_id).single().execute().data
        if not row:
            return 0
        ahead = sb.table("runs").select("id", count="exact") \
            .eq("status", "queued").lt("created_at", row["created_at"]).execute()
        return ahead.count or 0
    except Exception:
        return 0


def upload_final_to_supabase(run_id: str, final_path: Path) -> tuple[bool, str | None]:
    sb = supabase_client()
    if sb is None:
        return False, "supabase not configured"
    storage_key = f"{run_id}/final.mp4"
    try:
        with open(final_path, "rb") as f:
            sb.storage.from_("reels").upload(
                path=storage_key,
                file=f.read(),
                file_options={"content-type": "video/mp4", "upsert": "true"},
            )
        sb.table("runs").update({
            "status": "awaiting_review",
            "storage_path": f"reels/{storage_key}",
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "qc_notes": None,
            "rejection_reason": None,
        }).eq("id", run_id).execute()
        return True, None
    except Exception as e:
        return False, str(e)


def mark_run_failed(run_id: str, reason: str, qc_notes: str | None = None):
    sb = supabase_client()
    if sb is None:
        return
    try:
        sb.table("runs").update({
            "status": "failed",
            "rejection_reason": reason[:1000],
            "qc_notes": (qc_notes or "")[-2000:],
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", run_id).execute()
    except Exception:
        pass

    # Auto-refund: give the customer their credit back on pipeline failure.
    try:
        row = sb.table("runs").select("user_id") \
            .eq("id", run_id).single().execute().data
        if row and row.get("user_id"):
            sb.table("credits").insert({
                "user_id": row["user_id"],
                "delta": 1,
                "reason": "refund",
                "run_id": run_id,
                "note": f"auto-refund: {reason[:200]}",
            }).execute()
    except Exception:
        pass


def fetch_run_prompt(run_id: str) -> str | None:
    """Pre-fill the wizard's topic field from the runs.prompt set at payment time."""
    sb = supabase_client()
    if sb is None:
        return None
    try:
        row = sb.table("runs").select("prompt") \
            .eq("id", run_id).single().execute().data
        return row.get("prompt") if row else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Gemini helpers (reused from generate_script.py)
# ---------------------------------------------------------------------------

def load_env(key: str) -> str | None:
    # Prefer real env (Modal injects secrets here), fall back to .env file for dev.
    val = os.environ.get(key)
    if val:
        return val
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return None
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith(f"{key}="):
                v = line.split("=", 1)[1].strip().strip('"').strip("'")
                if v and not v.startswith("<"):
                    return v
    return None


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
- "image_prompt": Photorealistic Imagen prompt with camera specs (e.g., "shot on Sony A7IV, 50mm f/1.8, shallow depth of field"), lighting. MUST include "looking directly at camera, direct eye contact". NO abstract emotional cues.
- "voice": object with "gender" (must be "male" or "female"), "accent", "tone"

CRITICAL: voice.gender MUST match the visual gender of the person described in image_prompt. If image_prompt describes a woman/female, voice.gender MUST be "female". If image_prompt describes a man/male, voice.gender MUST be "male". Never mismatch.

Make characters diverse and authentic to the content.
Return ONLY a JSON array of 3 objects. No explanation."""


CHARACTER_CUSTOM_PROMPT = """Generate a full anchor character object from this description.

USER'S DESCRIPTION: {description}
REEL TOPIC: {topic}

Return JSON with:
- "description": expanded detailed description
- "image_prompt": photorealistic Imagen prompt with camera specs, lighting. MUST include "looking directly at camera, direct eye contact". NO abstract cues.
- "voice": object with "gender" (must be "male" or "female"), "accent", "tone"

CRITICAL: voice.gender MUST match the visual gender of the person described in image_prompt. If image_prompt describes a woman/female, voice.gender MUST be "female". If image_prompt describes a man/male, voice.gender MUST be "male". Never mismatch.

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
Anchor image_prompt MUST include "looking directly at camera, direct eye contact" — the anchor is speaking to the viewer.
Anchor video prompts: minimal to not override lip-sync.

Return ONLY the JSON object. No explanation."""


# ---------------------------------------------------------------------------
# Routes — Health check
# ---------------------------------------------------------------------------
# Unauthenticated, no session touch, no DB call. Used by Fly.io machine
# health checks (fly.toml [[http_service.checks]]). The "/" route below
# returns 401 for unauthenticated requests, which Fly would treat as
# unhealthy — so health checks must hit /healthz instead.

@app.route("/healthz")
def healthz():
    return {"ok": True, "service": "igloo-studio"}, 200


# ---------------------------------------------------------------------------
# Routes — Pages
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """
    Entry point. In production, requires a signed studio token via ?token=<t>.
    In dev (no IGLOO_STUDIO_SECRET set), allows direct access with synthetic
    session.
    """
    token = request.args.get("token")
    if token:
        payload = verify_studio_token(token)
        if not payload:
            return _render_token_error("Your studio link is invalid or expired."), 401
        session["igloo"] = {
            "user_id": payload["user_id"],
            "run_id": payload["run_id"],
        }
    elif IGLOO_DEV_MODE:
        _ensure_dev_session()
    elif not current_user_id():
        return _render_token_error("This studio requires a valid access link from igloo.video."), 401

    # Pre-fill topic from runs.prompt if available
    prefill_topic = ""
    run_id = current_run_id()
    if run_id and run_id != "dev-run":
        prefill_topic = fetch_run_prompt(run_id) or ""

    return render_template(
        "index.html",
        igloo_app_url=IGLOO_APP_URL,
        prefill_topic=prefill_topic,
        run_id=run_id or "",
    )


def _render_token_error(message: str) -> str:
    return (
        "<!doctype html><html><body style='font-family:sans-serif;"
        "max-width:480px;margin:80px auto;text-align:center;color:#222'>"
        f"<h1>Studio access</h1><p>{message}</p>"
        f"<p><a href='{IGLOO_APP_URL}'>Return to Igloo</a></p>"
        "</body></html>"
    )


# ---------------------------------------------------------------------------
# Routes — Script Generation API
# ---------------------------------------------------------------------------

@app.route("/api/generate-narration", methods=["POST"])
@require_auth
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
            raw = call_gemini(retry_prompt, api_key, temperature=0.5)
            scenes = extract_json_from_text(raw)
            scenes, retry_repair_log = pb.repair_scenes(scenes)
            failures = pb.validate_scenes(scenes, duration, voice_id=voice_id)

        # Hard ceiling breach after retry = reject outright
        if failures and any("HARD CEILING" in f for f in failures):
            return jsonify({
                "error": "Script exceeds the hard duration ceiling even after retry. "
                         "Please try a shorter duration or simpler topic.",
                "validation_failures": failures,
            }), 422

        return jsonify({
            "scenes": scenes,
            "niche": resolved_niche,
            "validation_warnings": failures or None,
            "repair_log": (repair_log + retry_repair_log) or None,
        })
    except Exception as e:
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        return jsonify({"error": f"{type(e).__name__}: {e}"}), 500


@app.route("/api/edit-narration", methods=["POST"])
@require_auth
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
@require_auth
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
@require_auth
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


@app.route("/api/select-voice", methods=["POST"])
@require_auth
def api_select_voice():
    data = request.json
    character = data.get("character", {})

    elevenlabs_key = load_env("ELEVENLABS_API_KEY")
    gemini_key = load_env("GEMINI_API_KEY")
    if not elevenlabs_key:
        return jsonify({"error": "ELEVENLABS_API_KEY not set"}), 500
    if not gemini_key:
        return jsonify({"error": "GEMINI_API_KEY not set"}), 500

    # Build a mock script structure that build_voice_profile expects
    mock_script = {"anchor_character": character}
    try:
        profile = build_voice_profile(mock_script)
        voices = search_shared_voices(elevenlabs_key, profile)
        if not voices:
            return jsonify({"candidates": [], "profile": profile})

        # Build candidate dicts for Gemini ranking (same shape download_previews returns)
        candidates = []
        for v in voices:
            if not v.get("preview_url"):
                continue
            candidates.append({
                "voice_id": v["voice_id"],
                "name": v.get("name", ""),
                "description": v.get("description", ""),
                "category": v.get("category", ""),
                "labels": v.get("labels", {}),
                "preview_url": v["preview_url"],
                "cloned_by_count": v.get("cloned_by_count", 0),
                "liked_by_count": v.get("liked_by_count", 0),
            })

        ranked = rank_with_gemini(candidates, profile, gemini_key, top_n=3)
        return jsonify({"candidates": ranked, "profile": profile})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/assemble-script", methods=["POST"])
@require_auth
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
@require_auth
def api_save_script():
    data = request.json
    topic = data.get("topic", "")
    script_json = data.get("script", {})

    user_id = current_user_id()
    slug = slugify(topic)
    output_dir = user_workdir(user_id, slug)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{slug}_script.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(script_json, f, indent=2, ensure_ascii=False)

    # If voice was pre-selected in the wizard, propagate to env so
    # generate_voiceover.py picks it up when pipeline starts from step 2.
    voice_id = (script_json.get("anchor_character", {})
                .get("voice", {}).get("elevenlabs_voice_id"))
    if voice_id:
        os.environ["ELEVENLABS_VOICE_ID"] = voice_id

    return jsonify({
        "path": str(output_path),
        "relative": str(output_path.relative_to(WORKDIR_ROOT.parent))
                    if WORKDIR_ROOT.parent in output_path.parents
                    else str(output_path),
    })


# ---------------------------------------------------------------------------
# Routes — Pipeline Execution API
# ---------------------------------------------------------------------------

@app.route("/api/list-scripts", methods=["GET"])
@require_auth
def api_list_scripts():
    """List the current user's script JSON files."""
    user_id = current_user_id()
    user_root = WORKDIR_ROOT / user_id
    scripts = []
    if user_root.exists():
        for script_file in user_root.glob("*/*_script.json"):
            try:
                with open(script_file) as f:
                    data = json.load(f)
                scripts.append({
                    "path": str(script_file),
                    "relative": str(script_file),
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


def run_pipeline_thread(user_id: str, run_id: str, script_path: str,
                        speed: float, audio_mode: str,
                        no_captions: bool, start_from: int,
                        auto_go: bool = False,
                        music_volume: float = 0.10,
                        voice_volume: float = 1.5):
    """Run pipeline steps sequentially in a background thread for one user."""
    state = get_state(user_id)
    state["running"] = True
    state["queue_status"] = "running"
    state["script_path"] = script_path
    state["run_id"] = run_id
    state["logs"] = []
    state["step_statuses"] = {i: "pending" for i in range(1, 9)}
    state["gate_pending"] = False

    steps_to_run = list(range(max(1, start_from), 9))

    # Mark steps before start_from as skipped
    for i in range(1, start_from):
        state["step_statuses"][i] = "skipped"
        broadcast_event(user_id, "step_status",
                        {"step": i, "status": "skipped", "reason": "Before start step"})

    # Track cumulative time for progress estimation
    elapsed_total = 0
    pipeline_failed_reason: str | None = None
    pipeline_failed_logs: str | None = None

    try:
        for step_num in steps_to_run:
            if not state["running"]:
                break

            step_name = STEP_NAMES[step_num]
            state["current_step"] = step_num
            state["step_statuses"][step_num] = "running"
            broadcast_event(user_id, "step_status",
                            {"step": step_num, "status": "running", "name": step_name})

            # Broadcast cinematic phase + progress
            remaining_est = sum(STEP_TIME_ESTIMATES[s] for s in range(step_num, 9))
            completed_est = sum(STEP_TIME_ESTIMATES[s] for s in range(1, step_num))
            progress_pct = round((completed_est / TOTAL_ESTIMATED) * 100) if TOTAL_ESTIMATED > 0 else 0
            broadcast_event(user_id, "phase", {
                "step": step_num,
                "message": CINEMATIC_PHASES.get(step_num, step_name),
                "remaining_seconds": remaining_est,
                "progress": progress_pct,
            })

            # Build command
            cmd = _build_step_cmd(step_num, script_path, speed, audio_mode,
                                  no_captions, music_volume, voice_volume)
            broadcast_event(user_id, "log", {"text": f"$ {' '.join(cmd)}", "level": "cmd"})

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
                state["process"] = proc

                for line in proc.stdout:
                    line = line.rstrip('\n')
                    state["logs"].append(line)
                    broadcast_event(user_id, "log", {"text": line, "level": "info"})

                proc.wait()
                elapsed = time.time() - step_start
                elapsed_total += elapsed

                if proc.returncode != 0:
                    state["step_statuses"][step_num] = "failed"
                    broadcast_event(user_id, "step_status", {
                        "step": step_num, "status": "failed",
                        "name": step_name, "elapsed": round(elapsed, 1),
                        "error": f"Exit code {proc.returncode}"
                    })
                    pipeline_failed_reason = f"step {step_num} ({step_name}) exited {proc.returncode}"
                    pipeline_failed_logs = "\n".join(state["logs"][-50:])

                    if auto_go:
                        broadcast_event(user_id, "pipeline_error", {
                            "step": step_num,
                            "error": pipeline_failed_reason,
                        })
                        break
                    else:
                        # Wait for user decision (retry/skip/abort)
                        state["gate_pending"] = True
                        state["gate_step"] = step_num
                        broadcast_event(user_id, "gate", {
                            "step": step_num, "name": step_name,
                            "type": "error",
                            "message": f"Step {step_num} ({step_name}) failed with exit code {proc.returncode}"
                        })
                        while state["gate_pending"] and state["running"]:
                            time.sleep(0.2)

                        gate_response = state.get("gate_response", "abort")
                        if gate_response == "abort":
                            break
                        elif gate_response == "skip":
                            state["step_statuses"][step_num] = "skipped"
                            pipeline_failed_reason = None
                            continue
                        elif gate_response == "retry":
                            pipeline_failed_reason = None
                            continue
                else:
                    state["step_statuses"][step_num] = "completed"
                    broadcast_event(user_id, "step_status", {
                        "step": step_num, "status": "completed",
                        "name": step_name, "elapsed": round(elapsed, 1)
                    })

            except Exception as e:
                state["step_statuses"][step_num] = "failed"
                broadcast_event(user_id, "step_status", {
                    "step": step_num, "status": "failed",
                    "name": step_name, "error": str(e)
                })
                pipeline_failed_reason = f"step {step_num} crashed: {e}"
                pipeline_failed_logs = "\n".join(state["logs"][-50:])
                if auto_go:
                    broadcast_event(user_id, "pipeline_error", {
                        "step": step_num, "error": str(e)
                    })
                break

            # Gate: wait for user GO between steps (only in manual mode)
            if not auto_go and step_num < 8 and state["running"]:
                next_step = step_num + 1
                if next_step <= 8:
                    state["gate_pending"] = True
                    state["gate_step"] = step_num
                    broadcast_event(user_id, "gate", {
                        "step": step_num, "name": step_name,
                        "type": "approval",
                        "next_step": next_step, "next_name": STEP_NAMES[next_step],
                        "message": f"Step {step_num} ({step_name}) completed. Proceed to Step {next_step} ({STEP_NAMES[next_step]})?"
                    })
                    while state["gate_pending"] and state["running"]:
                        time.sleep(0.2)

                    gate_response = state.get("gate_response", "go")
                    if gate_response == "abort":
                        break
                    elif gate_response == "skip":
                        if next_step <= 8:
                            state["step_statuses"][next_step] = "skipped"
                            broadcast_event(user_id, "step_status",
                                            {"step": next_step, "status": "skipped", "reason": "Skipped by user"})
                            steps_to_run = [s for s in steps_to_run if s != next_step]

        # Determine success and find output file
        all_ok = all(
            state["step_statuses"].get(s) in ("completed", "skipped")
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
        broadcast_event(user_id, "phase", {
            "step": 8, "message": "Done.",
            "remaining_seconds": 0, "progress": 100,
        })

        redirect_url = None
        if all_ok and download_path and run_id and run_id != "dev-run":
            ok, err = upload_final_to_supabase(run_id, Path(download_path))
            if ok:
                redirect_url = f"{IGLOO_APP_URL}/runs/{run_id}"
            else:
                mark_run_failed(run_id, f"storage upload failed: {err}",
                                "\n".join(state["logs"][-50:]))
                broadcast_event(user_id, "pipeline_error", {
                    "step": 8,
                    "error": f"Upload to Igloo failed: {err}",
                })
                all_ok = False
        elif not all_ok and run_id and run_id != "dev-run":
            mark_run_failed(
                run_id,
                pipeline_failed_reason or "pipeline aborted",
                pipeline_failed_logs,
            )

        broadcast_event(user_id, "pipeline_done", {
            "statuses": state["step_statuses"],
            "success": all_ok,
            "download_path": download_path,
            "redirect_url": redirect_url,
        })

    finally:
        state["running"] = False
        state["queue_status"] = None
        state["current_step"] = None
        state["process"] = None


def _build_step_cmd(step_num: int, script_path: str,
                    speed: float, audio_mode: str, no_captions: bool,
                    music_volume: float = 0.10,
                    voice_volume: float = 1.5) -> list[str]:
    py = sys.executable
    if step_num == 1:
        return [py, "execution/select_voice.py", script_path, "--auto"]
    elif step_num == 2:
        # Voice is always generated at 1.0x. The pacing speedup is applied
        # at step 8 via assemble_video --final-speed (pitch-preserving).
        return [py, "execution/generate_voiceover.py", script_path]
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
               "--final-speed", str(speed),
               "--music-volume", str(music_volume),
               "--voice-volume", str(voice_volume)]
        if no_captions:
            cmd.append("--no-captions")
        return cmd
    return []


@app.route("/api/pipeline/start", methods=["POST"])
@require_auth
def api_pipeline_start():
    user_id = current_user_id()
    run_id = current_run_id()
    state = get_state(user_id)

    if state["running"]:
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

    # Try to claim a pipeline slot. If full, mark queued and let the client poll.
    try:
        acquired = try_acquire_slot(run_id)
    except SlotAcquireError as e:
        return jsonify({"error": f"run not acquirable: {e}"}), 409
    if not acquired:
        mark_run_queued(run_id)
        state["queue_status"] = "queued"
        state["script_path"] = script_path
        # Stash launch params so queue-status can spawn the thread later.
        state["pending_launch"] = {
            "script_path": script_path,
            "speed": speed,
            "audio_mode": audio_mode,
            "no_captions": no_captions,
            "start_from": start_from,
            "auto_go": auto_go,
            "music_volume": music_volume,
            "voice_volume": voice_volume,
        }
        return jsonify({
            "status": "queued",
            "queue_position": queue_position(run_id),
        })

    state.pop("pending_launch", None)
    thread = threading.Thread(
        target=run_pipeline_thread,
        args=(user_id, run_id, script_path, speed, audio_mode, no_captions,
              start_from, auto_go, music_volume, voice_volume),
        daemon=True
    )
    thread.start()

    return jsonify({"status": "started"})


@app.route("/api/pipeline/queue-status", methods=["GET"])
@require_auth
def api_pipeline_queue_status():
    """Polled by the client every ~5s while queued. Re-attempts slot acquire."""
    user_id = current_user_id()
    run_id = current_run_id()
    state = get_state(user_id)

    if state["running"]:
        return jsonify({"status": "running", "acquired": True})

    if state.get("queue_status") != "queued":
        return jsonify({"status": "idle", "acquired": False})

    # Try to promote
    try:
        promoted = try_acquire_slot(run_id)
    except SlotAcquireError as e:
        state["queue_status"] = None
        state.pop("pending_launch", None)
        return jsonify({"status": "error", "error": str(e)}), 409
    if promoted:
        launch = state.get("pending_launch") or {}
        state.pop("pending_launch", None)
        if not launch:
            return jsonify({"status": "error", "error": "missing launch params"}), 500
        thread = threading.Thread(
            target=run_pipeline_thread,
            args=(user_id, run_id,
                  launch["script_path"], launch["speed"], launch["audio_mode"],
                  launch["no_captions"], launch["start_from"], launch["auto_go"],
                  launch["music_volume"], launch["voice_volume"]),
            daemon=True
        )
        thread.start()
        return jsonify({"status": "running", "acquired": True})

    return jsonify({
        "status": "queued",
        "acquired": False,
        "queue_position": queue_position(run_id),
    })


@app.route("/api/pipeline/gate", methods=["POST"])
@require_auth
def api_pipeline_gate():
    user_id = current_user_id()
    state = get_state(user_id)
    data = request.json
    response = data.get("response", "go")  # go, skip, abort, retry
    state["gate_response"] = response
    state["gate_pending"] = False
    return jsonify({"status": "ok"})


@app.route("/api/pipeline/stop", methods=["POST"])
@require_auth
def api_pipeline_stop():
    user_id = current_user_id()
    state = get_state(user_id)
    state["running"] = False
    state["gate_pending"] = False
    proc = state.get("process")
    if proc and proc.poll() is None:
        proc.terminate()
    return jsonify({"status": "stopped"})


@app.route("/api/pipeline/status", methods=["GET"])
@require_auth
def api_pipeline_status():
    user_id = current_user_id()
    state = get_state(user_id)
    return jsonify({
        "running": state["running"],
        "queue_status": state.get("queue_status"),
        "current_step": state["current_step"],
        "step_statuses": state["step_statuses"],
        "gate_pending": state["gate_pending"],
        "gate_step": state["gate_step"],
    })


# ---------------------------------------------------------------------------
# Routes — Script Editing
# ---------------------------------------------------------------------------

SCRIPT_EDIT_PROMPT = """Edit the following complete Reel Engine script JSON based on user feedback.

CURRENT SCRIPT:
{script_json}

USER'S FEEDBACK:
{feedback}

Apply the requested changes while maintaining the overall structure and all required fields.
Return ONLY the edited JSON object. No explanation."""


@app.route("/api/edit-script", methods=["POST"])
@require_auth
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


# /api/download removed — final MP4 is uploaded to Supabase Storage on
# pipeline completion and served via the Next.js admin → deliver flow.


# ---------------------------------------------------------------------------
# SSE (Server-Sent Events) for live updates
# ---------------------------------------------------------------------------

@app.route("/api/events")
@require_auth
def api_events():
    user_id = current_user_id()
    user_queues = get_user_queues(user_id)
    session_id = str(time.time())
    q = queue.Queue()
    user_queues[session_id] = q

    def stream():
        try:
            while True:
                try:
                    msg = q.get(timeout=30)
                    yield f"data: {msg}\n\n"
                except queue.Empty:
                    yield f"data: {json.dumps({'type': 'ping'})}\n\n"
        finally:
            user_queues.pop(session_id, None)

    return Response(stream(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"\n  Reel Engine Web UI")
    print(f"  http://localhost:5000")
    print(f"  dev_mode={IGLOO_DEV_MODE}, max_pipelines={IGLOO_MAX_PIPELINES}\n")
    app.run(debug=False, port=5000, threaded=True)
