"""
Igloo Modal worker — wraps the 9-step pipeline as a serverless function.

Architecture:
  Next.js /app  ──HTTP──>  run_reel.web_url  ──spawns──>  run_reel(run_id)
                                                              │
                                                              ├─ reads runs row from Supabase
                                                              ├─ creates /tmp/igloo/<run_id>/ workdir
                                                              ├─ subprocess: run_pipeline.py --new --workdir ... --auto-go
                                                              ├─ uploads final.mp4 to Supabase Storage
                                                              └─ updates row → status=awaiting_review (or failed)

Concurrency safety:
  - Each invocation gets its own /tmp/igloo/<run_id>/ directory (UUID-isolated)
  - run_pipeline.py honors --workdir flag (added in Phase 5 pre-flight)
  - No shared mutable state between invocations

Deploy:
  modal deploy infra/modal/igloo_worker.py

Test (after seeding a runs row in Supabase):
  modal run infra/modal/igloo_worker.py::test --run-id <uuid>
"""

import modal

app = modal.App("igloo")

# ---------------------------------------------------------------------------
# Image
# ---------------------------------------------------------------------------
# Pipeline deps:
#   - ffmpeg (system) for assembly
#   - PyJWT for Kling API auth
#   - supabase python client for DB + storage
#   - All other API calls in execution/ use stdlib urllib (no requests/httpx)
# ---------------------------------------------------------------------------

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg")
    .pip_install(
        "pyjwt==2.8.0",
        "supabase==2.5.0",
        "fastapi[standard]",   # required by @modal.fastapi_endpoint (used by `trigger`)
    )
    .add_local_dir(
        "execution",
        remote_path="/app/execution",
    )
)

# ---------------------------------------------------------------------------
# Secrets
# ---------------------------------------------------------------------------
# Create these in the Modal dashboard (https://modal.com/secrets) before deploy:
#
#   1. igloo-supabase
#        SUPABASE_URL=https://qgnbeudbwfrswbnxeapf.supabase.co
#        SUPABASE_SERVICE_ROLE_KEY=<service_role JWT>
#
#   2. igloo-apis
#        GEMINI_API_KEY=...
#        KLING_ACCESS_KEY=...
#        KLING_SECRET_KEY=...
#        ELEVENLABS_API_KEY=...
#        ELEVENLABS_VOICE_ID=...              (default voice; per-run override below)
#
# The pipeline scripts read these via load_env_value() which falls back to
# os.environ when .env is missing. Modal injects secrets as env vars, so this
# Just Works™ without writing a .env file inside the container.
# ---------------------------------------------------------------------------

secrets = [
    modal.Secret.from_name("igloo-supabase"),
    modal.Secret.from_name("igloo-apis"),
]


# ---------------------------------------------------------------------------
# Helpers (defined inside Modal-imported scope so they ship with the function)
# ---------------------------------------------------------------------------

def _supabase_client():
    import os
    from supabase import create_client
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


def _find_final_mp4(workdir):
    """Pipeline writes final_reel_optionc.mp4 by default. Fall back to any final_reel*.mp4."""
    from pathlib import Path
    primary = Path(workdir) / "final_reel_optionc.mp4"
    if primary.exists():
        return primary
    candidates = sorted(Path(workdir).glob("final_reel*.mp4"))
    return candidates[0] if candidates else None


# ---------------------------------------------------------------------------
# Main worker function
# ---------------------------------------------------------------------------

@app.function(
    image=image,
    secrets=secrets,
    timeout=3600,           # 1 hour hard cap per run
    cpu=2.0,
    memory=4096,
    retries=0,              # We handle failure ourselves via Supabase status
)
def run_reel(run_id: str) -> dict:
    """
    Execute the full 9-step pipeline for a single Supabase runs row.

    Args:
        run_id: UUID of the row in public.runs

    Returns:
        {"ok": bool, "run_id": str, "storage_path": str | None, "error": str | None}
    """
    import os
    import shutil
    import subprocess
    from datetime import datetime, timezone
    from pathlib import Path

    sb = _supabase_client()

    # ----- 1. Fetch the run row -----
    try:
        row = sb.table("runs").select("*").eq("id", run_id).single().execute().data
    except Exception as e:
        return {"ok": False, "run_id": run_id, "error": f"fetch failed: {e}"}

    if not row:
        return {"ok": False, "run_id": run_id, "error": "run not found"}

    if row["status"] not in ("queued", "failed"):
        # Idempotency guard — don't re-run something that's already running/delivered
        return {
            "ok": False,
            "run_id": run_id,
            "error": f"row status is '{row['status']}', expected 'queued'",
        }

    # ----- 2. Mark running -----
    sb.table("runs").update({
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", run_id).execute()

    # ----- 3. Create isolated workdir -----
    workdir = Path(f"/tmp/igloo/{run_id}")
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    # ----- 4. Build env for the subprocess -----
    # Pass through all API keys + the per-run voice override
    env = os.environ.copy()
    env["IGLOO_WORKDIR"] = str(workdir)
    if row.get("voice_id"):
        env["ELEVENLABS_VOICE_ID"] = row["voice_id"]

    # ----- 5. Run the pipeline -----
    params = row.get("params") or {}
    theme = params.get("theme") or "General"
    topic = row["prompt"]
    duration = str(params.get("duration") or 40)

    cmd = [
        "python", "/app/execution/run_pipeline.py",
        "--new",
        "--theme", theme,
        "--topic", topic,
        "--workdir", str(workdir),
        "--auto-go",
    ]
    if params.get("script_text"):
        cmd.extend(["--script-text", params["script_text"]])
    if params.get("speed"):
        cmd.extend(["--speed", str(params["speed"])])

    print(f"[run_reel] {run_id}: {' '.join(cmd)}")

    try:
        proc = subprocess.run(
            cmd,
            cwd="/app",
            env=env,
            capture_output=True,
            text=True,
            timeout=3500,
        )
    except subprocess.TimeoutExpired:
        sb.table("runs").update({
            "status": "failed",
            "rejection_reason": "pipeline timeout (>3500s)",
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", run_id).execute()
        return {"ok": False, "run_id": run_id, "error": "timeout"}

    if proc.returncode != 0:
        sb.table("runs").update({
            "status": "failed",
            "rejection_reason": f"pipeline exited {proc.returncode}",
            "qc_notes": (proc.stderr or "")[-2000:],
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", run_id).execute()
        return {
            "ok": False,
            "run_id": run_id,
            "error": f"pipeline exit {proc.returncode}",
            "stderr_tail": (proc.stderr or "")[-500:],
        }

    # ----- 6. Locate the final mp4 -----
    final = _find_final_mp4(workdir)
    if not final:
        sb.table("runs").update({
            "status": "failed",
            "rejection_reason": "no final_reel*.mp4 produced",
            "qc_notes": (proc.stdout or "")[-2000:],
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", run_id).execute()
        return {"ok": False, "run_id": run_id, "error": "no output mp4"}

    # ----- 7. Upload to Supabase Storage -----
    storage_key = f"{run_id}/final.mp4"
    try:
        with open(final, "rb") as f:
            sb.storage.from_("reels").upload(
                path=storage_key,
                file=f.read(),
                file_options={
                    "content-type": "video/mp4",
                    "upsert": "true",
                },
            )
    except Exception as e:
        sb.table("runs").update({
            "status": "failed",
            "rejection_reason": f"storage upload failed: {e}",
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", run_id).execute()
        return {"ok": False, "run_id": run_id, "error": f"upload failed: {e}"}

    # ----- 8. Mark awaiting_review -----
    sb.table("runs").update({
        "status": "awaiting_review",
        "storage_path": f"reels/{storage_key}",
        "duration_seconds": float(duration),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        # Clear any stale error fields from previous failed attempts (retries)
        "qc_notes": None,
        "rejection_reason": None,
    }).eq("id", run_id).execute()

    print(f"[run_reel] {run_id}: ✅ uploaded to reels/{storage_key}")

    return {
        "ok": True,
        "run_id": run_id,
        "storage_path": f"reels/{storage_key}",
    }


# ---------------------------------------------------------------------------
# Web endpoint — Phase 6 (Next.js webhook handler) will POST to this URL
# ---------------------------------------------------------------------------

@app.function(image=image, secrets=secrets)
@modal.fastapi_endpoint(method="POST")
def trigger(item: dict):
    """
    POST { "run_id": "<uuid>" } → spawns run_reel and returns immediately.
    The actual pipeline runs async; clients poll Supabase for status.
    """
    run_id = item.get("run_id")
    if not run_id:
        return {"ok": False, "error": "missing run_id"}
    call = run_reel.spawn(run_id)
    return {"ok": True, "run_id": run_id, "modal_call_id": call.object_id}


# ---------------------------------------------------------------------------
# Local entrypoint for manual testing
# ---------------------------------------------------------------------------

@app.local_entrypoint()
def test(run_id: str):
    """
    Manually trigger a run for testing:
        modal run infra/modal/igloo_worker.py::test --run-id <uuid>
    """
    print(f"Triggering run_reel({run_id}) on Modal...")
    result = run_reel.remote(run_id)
    print(f"Result: {result}")
