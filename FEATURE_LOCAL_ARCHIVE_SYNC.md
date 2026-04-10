# Feature: Local archive sync for every reel run

**Status:** Designed, not built. Defer until Fly migration acceptance criterion #3 is green.
**Drafted:** 2026-04-09 (session 31)

---

## Goal

Every time a user creates a reel (success OR failure), automatically capture all run artifacts — reference images, scene clips, voiceover, music, final reel, scripts, timestamps, metadata — and end up with a local copy on the operator's computer. Survive Fly redeploys (which currently destroy `/tmp` and lose every intermediate).

**Why this matters:**
- Fly's `/tmp` is volatile. Every redeploy nukes all in-flight and historical run artifacts.
- Failed runs are the highest-value debugging artifacts and currently vanish on the next deploy.
- No durable record of past reel inputs/outputs for post-hoc analysis, regression testing, or recreating runs after a bug fix.
- Reference images and intermediate scene clips never make it to Supabase — only the final reel does.

---

## Architecture: two-stage decoupled sync

Direct Fly → local push is fragile (laptop sleep, dynamic IP, firewall, no 24/7 ingress). The right shape is:

**Stage A (in pipeline, runs on Fly):** archive workdir → upload tarball to Supabase Storage.
**Stage B (on local box, runs on operator schedule):** poll Supabase → pull new archives → store locally → mark as synced.

Why decoupled:
- Pipeline finishes and uploads even if laptop is off.
- Laptop pulls when it's on, hours later if needed.
- Survives Fly redeploys (no race between run finish and manual pull).
- Captures failed runs.
- Zero inbound connectivity needed on local box.

---

## Components to build

### 1. Pipeline-side: `execution/archive_run.py`

- Tarballs the entire run workdir: `/tmp/igloo/<user_id>/<run_slug>/`
- Gzips it
- Uploads to Supabase Storage bucket `archives` keyed by `<run_id>.tar.gz`
- Records the storage path back into `runs.archive_url`
- ~50-100 lines

**Wiring:** called from `web_app.py` as the **last** step of the pipeline subprocess, inside a `try/finally` so it runs even on failure. Best-effort: wrap in `try/except` so an archive upload failure does not fail the run itself.

**Optimization:** exclude `*_norm.mp4` from the tarball — they're regeneratable from `*_trimmed.mp4` and double the archive size for no information gain. Estimated tarball size after exclusion: ~50MB per run.

### 2. Supabase schema: migration `0005_add_run_archive.sql`

- Create private bucket `archives`
  - RLS: `service_role` only, no public read
  - Owner: `service_role`
- Add columns to `runs` table:
  - `archive_url TEXT NULL` — storage path for the tarball
  - `archived_at TIMESTAMPTZ NULL` — when Stage A finished
  - `archived_locally BOOLEAN DEFAULT false` — set true by Stage B after successful local pull
- ~20 lines

### 3. Local-side: `tools/pull_archives.py`

- Lives at repo root, runs on operator's laptop
- Queries Supabase: `runs WHERE archive_url IS NOT NULL AND archived_locally = false`
- For each row:
  - Generate signed URL via service_role key
  - Download tarball
  - Untar into `~/igloo_archives/<created_at>_<run_slug>_<run_id>/`
  - Mark `archived_locally = true` in Supabase
- ~80 lines
- Modes:
  - Default: one-shot pull, exit
  - `--watch`: poll every 60s, run continuously, log to terminal

### 4. Local automation (operator choice)

- **Option A — Manual:** run `python tools/pull_archives.py` whenever. Zero ops.
- **Option B — Watch mode:** `python tools/pull_archives.py --watch` in a background terminal. Recommended starting point.
- **Option C — Windows Task Scheduler:** runs every 5 min headless. Most "set and forget" but adds OS-level config. Escalate to this only if Option B is annoying.

### 5. Cleanup policy (deferred)

- Weekly cron / Supabase pg_cron job:
  - `DELETE FROM storage.objects WHERE bucket_id='archives' AND name IN (SELECT split_part(archive_url, '/', -1) FROM runs WHERE archived_locally = true AND archived_at < now() - interval '30 days')`
- Keeps cloud as a 30-day buffer; local is the durable copy.
- Don't build until storage actually gets noisy.

---

## Build sequence

1. **Phase 1 — MVP (validates upload side):**
   - `archive_run.py` + `archives` Supabase bucket
   - Wired into `web_app.py` finalize step
   - **No schema changes, no local puller.** Operator downloads manually from Supabase dashboard when needed.
   - Validates that the upload mechanic works without committing to the full local-sync stack.

2. **Phase 2 — Auto-sync (validates pull side):**
   - Migration `0005_add_run_archive.sql` (adds `archive_url`, `archived_at`, `archived_locally` columns)
   - `tools/pull_archives.py` with `--watch` mode
   - Operator runs `--watch` in a background terminal

3. **Phase 3 — Cleanup (defer until storage is noisy):**
   - pg_cron / scheduled function for Supabase-side TTL on already-synced archives

---

## Sizing & cost

Per run, current workdir contents:
- 9 reference images (~5MB)
- 9 trimmed scene clips (~25MB)
- 9 normalized scene clips (~25MB) — **excluded from tarball**, regeneratable
- Voiceover audio (~3MB)
- Music (~3MB)
- Final reel (~10MB)
- JSON/metadata (<1MB)
- **Tarball after exclusion: ~50MB compressed**

Volume math:
- 100 runs/month → 5 GB/month uploaded
- Supabase Pro: 100 GB included → 20 months of headroom
- Local 1 TB drive → ~20,000 runs

---

## Tradeoffs / things to push back on before building

- **It's real scope.** 4 new files + 1 migration + a Storage bucket + local automation. ~half a session to build, half a session to test end-to-end. Not a free addition.
- **Curated vs everything.** Decide: are reference images valuable to archive, or only the final reel + scenes + voiceover + scripts? Smaller archive = cheaper everything.
- **Supabase Storage dependency in pipeline finalize.** Wrap upload in `try/except` so a Storage outage doesn't fail the run. Archive is best-effort.
- **Simpler MVP exists.** Phase 1 alone (upload only, manual download from dashboard) is 80% of the value at 20% of the work. Strongly prefer building Phase 1 first and only committing to Phase 2 after Phase 1 has proven useful.
- **Ordering: do not start until Fly migration is green** (criterion #3 ✓). This is a feature, not a fix; the migration must land first.

---

## Open questions to answer before building

1. **Curated subset or full workdir?** Specifically: keep reference images, or only final + scenes + voiceover + scripts?
2. **Phase 1 first (manual dashboard download), or jump straight to Phase 2 (full auto-sync)?** Default: Phase 1 first.
3. **Failed runs included?** Strong recommendation: yes — failed runs are the most valuable debugging artifacts.
4. **Local archive root path?** Default `~/igloo_archives/` — confirm this is where the operator wants them.
5. **What naming convention for local folders?** Default `<created_at>_<run_slug>_<run_id>/` — sortable by time, human-readable, collision-free.

---

## Files this feature would touch

**New:**
- `execution/archive_run.py`
- `tools/pull_archives.py`
- `infra/supabase/migrations/0005_add_run_archive.sql`

**Modified:**
- `execution/web_app.py` — wire `archive_run` into pipeline finalize step (try/finally)
- `CLAUDE.md` — document the new flow under "Current state"
- Memory: add `project_local_archive_sync.md` once built

---

## When to revisit

After Fly migration acceptance criterion #3 is green AND at least 5 successful real runs have landed on Fly. At that point the migration is stable enough to add a feature on top of it.
