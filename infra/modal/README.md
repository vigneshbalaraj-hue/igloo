# Modal worker — Igloo

Wraps the 9-step pipeline in [execution/](../../execution/) as a serverless function. Each invocation runs in an isolated `/tmp/igloo/<run_id>/` workdir, uploads the final MP4 to Supabase Storage, and updates the `runs` row.

## Files

- [igloo_worker.py](igloo_worker.py) — the Modal app with `run_reel`, `trigger` (web endpoint), and `test` (local entrypoint)

## What you do (~5 minutes)

### 1. Install Modal CLI (if not already)

```bash
pip install modal
modal token new
```

This opens a browser to link your Modal account.

### 2. Create the two secrets

Modal dashboard → **Secrets** → **Create new secret** → **Custom**

**Secret 1: `igloo-supabase`**

| Key | Value |
|---|---|
| `SUPABASE_URL` | `https://qgnbeudbwfrswbnxeapf.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | (the long JWT starting with `eyJ...` from `.env`) |

**Secret 2: `igloo-apis`**

Copy these straight from your local [.env](../../.env):

| Key | Value |
|---|---|
| `GEMINI_API_KEY` | from `.env` |
| `KLING_ACCESS_KEY` | from `.env` |
| `KLING_SECRET_KEY` | from `.env` |
| `ELEVENLABS_API_KEY` | from `.env` |
| `ELEVENLABS_VOICE_ID` | from `.env` (default voice; per-run voice override comes from `runs.voice_id`) |

### 3. Deploy

From the repo root:

```bash
modal deploy infra/modal/igloo_worker.py
```

You should see:

```
✓ Created objects.
├── 🔨 Created mount...
├── 🔨 Created function run_reel.
└── 🔨 Created web function trigger => https://<your-workspace>--igloo-trigger.modal.run
```

**Save that `trigger` URL** — Phase 6 (Next.js) will POST `{"run_id": "<uuid>"}` to it.

### 4. Test (without paying for a real run yet)

We don't want to burn API credits testing. Two options:

**A. Test the wiring only** — manually insert a fake run row, watch the worker fail at the script generation step in a controlled way:

```sql
-- In Supabase SQL Editor
insert into public.users (clerk_user_id, email)
values ('test_clerk_id', 'test@igloo.video')
returning id;
-- copy the returned uuid as <user_uuid>

insert into public.runs (user_id, prompt, status, params)
values ('<user_uuid>', 'modal wiring test', 'queued', '{"theme": "Test", "duration": 10}'::jsonb)
returning id;
-- copy the returned uuid as <run_uuid>
```

Then:

```bash
modal run infra/modal/igloo_worker.py::test --run-id <run_uuid>
```

Watch the logs in the Modal dashboard. If the worker:
- ✅ Connects to Supabase, marks the row `running`, creates the workdir, invokes the pipeline → **wiring works**, even if the pipeline itself fails on the cheap first step.
- ❌ Errors before reaching the pipeline → fix the wiring (usually a missing secret or a typo in env var names).

**B. Full end-to-end test** — defer to **Phase 9**, where we'll do the ₹420 charge test that triggers a real pipeline run.

## Cost notes

- **Modal deploy itself**: free
- **Idle worker**: $0 (serverless, scales to zero)
- **Per-run cost**: ~$0.05–0.20 of Modal compute (CPU + memory + 1h cap is generous, real runs finish in ~10–15 min). Pipeline API costs (Gemini + Kling + ElevenLabs) are separate, on the order of $1–2 per reel based on s17 estimates.
- The 30-user beta will burn ~$30–60 in Modal compute total. Negligible vs revenue.

## Concurrency

- Each invocation gets a UUID-isolated workdir → no collisions
- Modal scales horizontally → if 5 users buy at once, 5 workers spawn in parallel
- Cold start: ~30s (image build is cached, so it's mostly container boot + dep load). The s17 gotcha says we should warm the function before announcing — Phase 10 will add a `keep_warm=1` flag if needed.

## Updating the pipeline

Bug fixes to anything under [execution/](../../execution/) just need a redeploy:

```bash
modal deploy infra/modal/igloo_worker.py
```

The image rebuild will pick up the new files via `add_local_dir`. No DB changes, no downtime, no user-visible disruption — next invocation uses the new code.
