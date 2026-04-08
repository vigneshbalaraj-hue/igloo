# Supabase setup — Igloo

This is the spine of Igloo. Postgres holds users/credits/runs/payments. Storage holds the finished MP4s. Everything else (Modal pipeline, Next.js /app, Razorpay webhook) reads and writes here.

## What you do (~10 minutes)

### 1. Create the project

1. Go to https://supabase.com → sign in with **GitHub**
2. **New project**
   - Name: `igloo`
   - Database password: generate a strong one, **save it to a password manager** (you'll rarely need it but you can't recover it)
   - **Region: `ap-south-1` (Mumbai)** — closest to you and to where Modal will run, minimizes round-trip latency
   - Plan: **Free**
3. Wait ~2 minutes for provisioning

### 2. Run the migration

1. Left sidebar → **SQL Editor** → **New query**
2. Open [migrations/0001_init.sql](migrations/0001_init.sql) in this repo
3. Copy the entire file, paste into the SQL Editor
4. Click **Run** (bottom right, or Ctrl+Enter)
5. You should see: `Success. No rows returned.`
6. Verify in **Table Editor** (left sidebar) that you see 4 tables: `users`, `credits`, `payments`, `runs`

If it errors, paste the error back to me — the migration is idempotent so re-running is safe.

### 3. Create the storage bucket

Follow [storage_setup.md](storage_setup.md). ~2 minutes.

### 4. Grab the credentials

Left sidebar → **Project Settings** (gear icon) → **API**

Copy these three values and paste them back to me in chat:

| Label in dashboard | Goes into env var | Used by |
|---|---|---|
| **Project URL** | `SUPABASE_URL` | Modal + Next.js + local |
| **anon / public** key | `SUPABASE_ANON_KEY` | Next.js (browser-safe) |
| **service_role** key | `SUPABASE_SERVICE_ROLE_KEY` | **Modal + Next.js server only — NEVER ships to browser** |

⚠️ **The service_role key bypasses RLS and can read/write anything in the database.** Treat it like a root password. I'll store it in Modal secrets and Vercel environment variables (server-side only). It must never appear in any file under `landing/src/` or in any Next.js client component.

## What I'll do (after you paste the keys)

1. Add the three vars to `.env` (gitignored)
2. Wire them into Modal secrets (Phase 5)
3. Wire them into Vercel env vars (Phase 6)
4. Build the Next.js Supabase client wrapper that picks the right key per context

## Schema reference

| Table | Purpose | Key columns |
|---|---|---|
| `users` | One row per buyer | `clerk_user_id` (text, unique), `email` |
| `credits` | Append-only ledger of grants/usage | `delta` (±int), `reason`, FK to `payment_id` or `run_id` |
| `payments` | Razorpay audit trail | `razorpay_payment_id` (unique), `amount_paise`, `webhook_payload` (jsonb) |
| `runs` | Pipeline executions | `status`, `prompt`, `storage_path`, `qc_verdict` |

Convenience view `user_balances` returns `(user_id, balance)` — `balance` is `sum(credits.delta)`.

## Why no Supabase Auth

Clerk owns identity. Clerk has a much better DX for the magic-link / Google sign-in flow we want, and integrates cleanly with Next.js. Supabase here is a **database + storage**, nothing more. RLS is enabled with no policies (default deny) so the anon key is harmless if leaked — all real DB access happens server-side with the service_role key.

## Free tier limits (sanity check)

- 500 MB Postgres → fine, our schema is tiny
- 1 GB Storage → ~70–100 reels before we need lifecycle cleanup
- 5 GB egress/mo → ~300+ reel downloads
- Beta 30-user cap fits comfortably with headroom

When we approach the storage cap, see lifecycle section in [storage_setup.md](storage_setup.md).
