"""
Igloo Modal studio — hosts the Flask wizard + pipeline on Modal.

Architecture:
  Next.js (igloo.video) gates access with Clerk auth and Razorpay payment,
  creates a runs row with status='draft', mints a signed HMAC token
  {run_id, user_id, exp} and redirects the browser to:

      https://<workspace>--igloo-studio.modal.run/?token=<signed>

  Modal runs one warm container hosting the Flask app (execution/web_app.py)
  via @modal.wsgi_app(). Flask verifies the token, stores {user_id, run_id}
  in flask.session, and walks the user through the theme → narration →
  character → script wizard. On "Create My Reel" it subprocesses the 9-step
  pipeline in a per-user workdir and, on success, uploads the final mp4 to
  Supabase Storage and flips the run to status='awaiting_review'. The browser
  is redirected back to igloo.video/runs/<id> where the operator picks it
  up for QC review.

  Pipeline execution is capped at IGLOO_MAX_PIPELINES (default 3) concurrent
  runs via atomic Postgres UPDATEs on runs.status. The wizard itself is
  always free. Multi-tenancy inside the single container is handled by
  web_app.py keying all state (locks, queues, workdirs) by user_id.

Deploy:
  PYTHONIOENCODING=utf-8 modal deploy infra/modal/igloo_worker.py

  Resulting URL: https://<workspace>--igloo-studio.modal.run
"""

import modal

app = modal.App("igloo")

# ---------------------------------------------------------------------------
# Image
# ---------------------------------------------------------------------------
# Pipeline deps:
#   - ffmpeg (system) for assembly
#   - flask for the wizard WSGI app
#   - PyJWT for Kling API auth
#   - supabase python client for DB + storage
#   - All other API calls in execution/ use stdlib urllib
#
# Local dirs shipped into the container:
#   - execution/       → /app/execution   (Flask app + pipeline step scripts)
#   - tools/fonts/     → /app/tools/fonts (captions font; assemble_video has
#                                          no fallback if this is missing)
#   - data/            → /app/data        (voice_calibration.json for prompt_bank)
# ---------------------------------------------------------------------------

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg")
    .pip_install(
        "flask==3.0.0",
        "pyjwt==2.8.0",
        "supabase==2.5.0",
    )
    .add_local_dir("execution", remote_path="/app/execution")
    .add_local_dir("tools/fonts", remote_path="/app/tools/fonts")
    .add_local_dir("data", remote_path="/app/data")
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
#        ELEVENLABS_VOICE_ID=...              (default voice; per-run override)
#
#   3. igloo-studio
#        IGLOO_STUDIO_SECRET=<32 bytes base64, byte-identical to Next.js side>
#        IGLOO_APP_URL=https://igloo.video
#        IGLOO_MAX_PIPELINES=3
#
# Modal injects secrets as env vars; web_app.load_env() reads os.environ first
# so no .env file is needed inside the container.
# ---------------------------------------------------------------------------

secrets = [
    modal.Secret.from_name("igloo-supabase"),
    modal.Secret.from_name("igloo-apis"),
    modal.Secret.from_name("igloo-studio"),
]


# ---------------------------------------------------------------------------
# Studio — Flask wizard + pipeline host
# ---------------------------------------------------------------------------

@app.function(
    image=image,
    secrets=secrets,
    timeout=3600,           # 1 hour — longest pipeline should finish well under this
    cpu=1.0,                # orchestrator only; heavy work is on Kling/ElevenLabs/Gemini
    memory=2048,            # 2 GB — Modal scheduling stalls on anything bigger right now
    min_containers=1,       # keep one warm so the wizard doesn't cold-start
    max_containers=1,       # single-container multi-tenant for MVP
)
@modal.concurrent(max_inputs=10)
@modal.wsgi_app()
def studio():
    """Expose execution/web_app.py as the Flask WSGI app for Modal."""
    import sys
    sys.path.insert(0, "/app/execution")
    from web_app import app as flask_app
    return flask_app
