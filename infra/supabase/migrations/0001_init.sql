-- Igloo initial schema
-- Run in Supabase SQL Editor as one shot.
-- Idempotent: safe to re-run.

-- ============================================================
-- Extensions
-- ============================================================
create extension if not exists "pgcrypto";   -- gen_random_uuid()

-- ============================================================
-- users
--   One row per buyer. Identified by Clerk user id (text).
--   We do NOT use Supabase Auth — Clerk owns identity.
-- ============================================================
create table if not exists public.users (
  id              uuid primary key default gen_random_uuid(),
  clerk_user_id   text unique not null,
  email           text unique not null,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);

create index if not exists users_clerk_user_id_idx on public.users (clerk_user_id);
create index if not exists users_email_idx          on public.users (email);

-- ============================================================
-- credits
--   Ledger of credit grants and usage.
--   delta > 0 = grant (from a payment), delta < 0 = consumption (a run).
--   Balance is sum(delta) for a user. We avoid a "balance" column to
--   keep this append-only and auditable.
-- ============================================================
create table if not exists public.credits (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid not null references public.users(id) on delete cascade,
  delta        integer not null,
  reason       text not null check (reason in ('payment', 'run', 'refund', 'admin_grant', 'admin_revoke')),
  payment_id   uuid,         -- nullable; FK added after payments table
  run_id       uuid,         -- nullable; FK added after runs table
  note         text,
  created_at   timestamptz not null default now()
);

create index if not exists credits_user_id_idx     on public.credits (user_id);
create index if not exists credits_created_at_idx  on public.credits (created_at desc);

-- Convenience view: current balance per user
create or replace view public.user_balances as
  select user_id, coalesce(sum(delta), 0)::int as balance
  from public.credits
  group by user_id;

-- ============================================================
-- payments
--   Razorpay payment audit trail. One row per webhook receipt.
-- ============================================================
create table if not exists public.payments (
  id                       uuid primary key default gen_random_uuid(),
  user_id                  uuid not null references public.users(id) on delete restrict,
  razorpay_payment_id      text unique not null,
  razorpay_order_id        text,
  razorpay_signature       text,
  amount_paise             integer not null,            -- ₹420 = 42000 paise
  currency                 text not null default 'INR',
  status                   text not null check (status in ('created', 'authorized', 'captured', 'failed', 'refunded')),
  credits_granted          integer not null default 0,
  webhook_event            text,                        -- e.g. 'payment.captured'
  webhook_payload          jsonb,                       -- full Razorpay event for audit
  created_at               timestamptz not null default now(),
  updated_at               timestamptz not null default now()
);

create index if not exists payments_user_id_idx              on public.payments (user_id);
create index if not exists payments_razorpay_payment_id_idx  on public.payments (razorpay_payment_id);
create index if not exists payments_status_idx               on public.payments (status);
create index if not exists payments_created_at_idx           on public.payments (created_at desc);

-- ============================================================
-- runs
--   One row per pipeline execution. Tracks status, inputs, outputs.
-- ============================================================
create table if not exists public.runs (
  id                  uuid primary key default gen_random_uuid(),
  user_id             uuid not null references public.users(id) on delete cascade,
  status              text not null default 'queued'
                      check (status in ('queued', 'running', 'awaiting_review', 'delivered', 'rejected', 'failed')),

  -- Inputs
  prompt              text not null,
  script              text,
  voice_id            text,
  params              jsonb,                  -- pipeline params snapshot

  -- Outputs
  storage_path        text,                   -- e.g. 'reels/<run_id>/final.mp4'
  duration_seconds    numeric(6,2),
  qc_verdict          text check (qc_verdict in ('pass', 'fail', 'manual_review')),
  qc_notes            text,
  rejection_reason    text,                   -- set if status = rejected/failed

  -- Cost tracking
  modal_cost_usd      numeric(8,4),
  api_cost_usd        numeric(8,4),

  -- Timestamps
  created_at          timestamptz not null default now(),
  started_at          timestamptz,
  finished_at         timestamptz,
  delivered_at        timestamptz
);

create index if not exists runs_user_id_idx     on public.runs (user_id);
create index if not exists runs_status_idx      on public.runs (status);
create index if not exists runs_created_at_idx  on public.runs (created_at desc);

-- ============================================================
-- Add deferred FKs on credits
-- ============================================================
do $$ begin
  alter table public.credits
    add constraint credits_payment_id_fkey
    foreign key (payment_id) references public.payments(id) on delete set null;
exception when duplicate_object then null; end $$;

do $$ begin
  alter table public.credits
    add constraint credits_run_id_fkey
    foreign key (run_id) references public.runs(id) on delete set null;
exception when duplicate_object then null; end $$;

-- ============================================================
-- updated_at triggers
-- ============================================================
create or replace function public.set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end $$;

drop trigger if exists users_set_updated_at on public.users;
create trigger users_set_updated_at
  before update on public.users
  for each row execute function public.set_updated_at();

drop trigger if exists payments_set_updated_at on public.payments;
create trigger payments_set_updated_at
  before update on public.payments
  for each row execute function public.set_updated_at();

-- ============================================================
-- Row Level Security
--   Clerk does not issue Supabase JWTs by default, so we will
--   talk to Postgres from the server (Modal + Next.js API routes)
--   using the SERVICE_ROLE key, which BYPASSES RLS.
--
--   We still enable RLS so that:
--     1. The anon key is safe even if leaked
--     2. Future direct-from-browser queries (if we add them) are
--        denied by default
--
--   No policies are added — default deny is the goal.
-- ============================================================
alter table public.users    enable row level security;
alter table public.credits  enable row level security;
alter table public.payments enable row level security;
alter table public.runs     enable row level security;

-- ============================================================
-- Done.
-- After running this:
--   1. Storage > create bucket 'reels' > Private
--   2. Settings > API > copy URL + anon key + service_role key
-- ============================================================
