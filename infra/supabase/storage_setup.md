# Supabase Storage setup — `reels` bucket

The pipeline writes finished MP4s here. Next.js hands users **signed URLs** that expire, so the bucket stays private.

## 1. Create the bucket

Supabase dashboard → **Storage** → **New bucket**

| Field | Value |
|---|---|
| Name | `reels` |
| Public bucket | **OFF** (private) |
| File size limit | `50 MB` (free-plan max; a 60s reel is ~10–20 MB so this is fine) |
| Allowed MIME types | `video/mp4` |

Click **Create bucket**.

## 2. Folder layout

The pipeline (Phase 5, Modal wrapper) will upload to:

```
reels/
  <run_id>/
    final.mp4          ← the deliverable
    thumbnail.jpg      ← optional poster frame
```

`<run_id>` is the `runs.id` UUID from Postgres. One folder per run keeps cleanup trivial (delete the folder, the row's `storage_path` becomes a tombstone).

## 3. Access pattern

| Who | How | Why |
|---|---|---|
| **Modal pipeline** | service_role key, direct upload | Server-side, trusted |
| **Next.js /app** | service_role key, generates signed URL (1h expiry) | Server-side API route, never ships key to browser |
| **Browser** | downloads via signed URL | URL expires, no persistent access |
| **Anon key** | ❌ no access | RLS + bucket privacy block it |

## 4. Lifecycle (defer to Phase 10+)

When we hit ~70 stored reels, add a daily cron that:
1. Finds runs where `delivered_at < now() - interval '30 days'`
2. Deletes the folder `reels/<run_id>/`
3. Sets `runs.storage_path = null` (keep the row for history)

This keeps us on the 1 GB free tier indefinitely. Not needed for the 30-user beta.

## 5. Verify

After creating the bucket, in **Storage → reels**:
- Try uploading a small test file via the dashboard
- Confirm it appears
- Delete it
- Done. Bucket is ready for the pipeline.
