# Igloo studio — Fly.io image.
#
# Replaces infra/modal/igloo_worker.py. Same Flask app (execution/web_app.py),
# same secrets, same pipeline scripts. Only the host changes.
#
# Build context = repo root. Build with:
#   docker build -t igloo-studio:test .
#
# Run locally with:
#   docker run --rm -p 8080:8080 -e IGLOO_STUDIO_SECRET=test igloo-studio:test
#
# See .tmp/fly_migration_impact.md §4.1 for the spec this implements.

FROM python:3.11-slim

# System deps:
#   - ffmpeg: assemble_video.py shells out to ffmpeg/ffprobe (Linux binary,
#     not the Windows .exe in tools/ — those are dev-only).
#   - ca-certificates: for HTTPS to Supabase, Gemini, Kling, ElevenLabs.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps — versions match infra/modal/igloo_worker.py exactly so we
# inherit Modal's "known good" dependency set. gunicorn is added because
# Fly doesn't have Modal's @modal.wsgi_app() wrapper.
RUN pip install --no-cache-dir \
        flask==3.0.0 \
        pyjwt==2.8.0 \
        supabase==2.5.0 \
        gunicorn==21.2.0

# Code — same three dirs Modal ships:
#   - execution/   : Flask app (web_app.py) + 9 pipeline step scripts + prompt_bank
#   - tools/fonts/ : caption font (assemble_video has no fallback if missing)
#   - data/        : voice_calibration.json for prompt_bank
# We deliberately do NOT copy tools/ffmpeg.exe / ffprobe.exe — those are
# Windows binaries for local dev; the container uses the apt-installed
# Linux ffmpeg above.
COPY execution/   /app/execution/
COPY tools/fonts/ /app/tools/fonts/
COPY data/        /app/data/

ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8
ENV PROJECT_ROOT=/app
ENV IGLOO_WORKDIR_ROOT=/tmp/igloo

EXPOSE 8080

# gunicorn config (see impact doc §3.3):
#   --workers 1     : single process. web_app.py holds per-user pipeline
#                     state in module-level dicts; multiple workers = split
#                     state = broken SSE. NEVER raise this.
#   --threads 16    : I/O-bound concurrency, parity with Modal's
#                     @modal.concurrent(max_inputs=10).
#   --timeout 0     : pipelines run 5–10 minutes; default 30s would kill
#                     a worker mid-pipeline.
#   --graceful-timeout 30 : let in-flight requests finish on SIGTERM.
#   --chdir /app/execution : so gunicorn can resolve `web_app:app`.
#                     Pipeline subprocesses still run with cwd=PROJECT_ROOT
#                     (=/app) per web_app.py:986, so this chdir does NOT
#                     affect their `python execution/<step>.py` calls.
CMD ["gunicorn", \
     "--workers", "1", \
     "--threads", "16", \
     "--timeout", "0", \
     "--graceful-timeout", "30", \
     "--bind", "0.0.0.0:8080", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--chdir", "/app/execution", \
     "web_app:app"]
