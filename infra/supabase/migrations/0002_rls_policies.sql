-- Igloo RLS policies for Clerk-issued JWTs
-- Run in Supabase SQL Editor after 0001_init.sql.
-- Idempotent: drops and recreates each policy.
--
-- Context:
--   We use Clerk for auth. Clerk's JWT template for Supabase puts the
--   Clerk user id in the standard `sub` claim. RLS reads it via
--   auth.jwt() ->> 'sub'.
--
--   The anon key + a Clerk-issued JWT lets the browser query Supabase
--   directly while RLS gates rows to the authenticated user.
--
--   The service_role key still bypasses all of this — server-side
--   code (Next.js API routes, Modal worker) keeps using service_role
--   for inserts, status updates, and admin reads.

-- ============================================================
-- users
--   A user can read their own row. They cannot insert/update/delete
--   directly — those happen server-side via service_role after
--   Clerk webhook (TODO: add user.created webhook in Phase 6).
-- ============================================================
drop policy if exists users_select_own on public.users;
create policy users_select_own on public.users
  for select
  using (clerk_user_id = auth.jwt() ->> 'sub');

-- ============================================================
-- runs
--   A user can read their own runs. Inserts come from /api/trigger-run
--   (server, service_role). No client writes.
-- ============================================================
drop policy if exists runs_select_own on public.runs;
create policy runs_select_own on public.runs
  for select
  using (
    user_id in (
      select id from public.users
      where clerk_user_id = auth.jwt() ->> 'sub'
    )
  );

-- ============================================================
-- credits
--   A user can read their own ledger. No client writes.
-- ============================================================
drop policy if exists credits_select_own on public.credits;
create policy credits_select_own on public.credits
  for select
  using (
    user_id in (
      select id from public.users
      where clerk_user_id = auth.jwt() ->> 'sub'
    )
  );

-- ============================================================
-- payments
--   A user can read their own payments. Webhook writes via service_role.
-- ============================================================
drop policy if exists payments_select_own on public.payments;
create policy payments_select_own on public.payments
  for select
  using (
    user_id in (
      select id from public.users
      where clerk_user_id = auth.jwt() ->> 'sub'
    )
  );

-- ============================================================
-- Notes:
--   - No INSERT/UPDATE/DELETE policies. All writes go through
--     server-side service_role. This is intentional.
--   - The user_balances view inherits the policies from the
--     underlying credits table because it is a security_invoker view
--     by default in Postgres 15+ — verify on your instance.
--   - Storage bucket 'reels' policies are NOT managed here. See
--     infra/supabase/storage_setup.md.
-- ============================================================
