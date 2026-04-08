-- Igloo: link runs to payments for webhook idempotency.
-- Run in Supabase SQL Editor after 0002_rls_policies.sql.
-- Idempotent: safe to re-run.
--
-- Why:
--   Phase 7 introduces a Razorpay webhook as a safety net for the
--   browser-side handler. Both code paths can race for the same
--   payment. We need a uniqueness constraint that lets either path
--   say "if a run already exists for this payment, return it; else
--   create it" without ever creating two runs.
--
--   Adding runs.payment_id (nullable FK) + a UNIQUE index gives us
--   that. Old runs (Phase 5/6 test runs) get NULL — UNIQUE allows
--   multiple NULLs by default in Postgres.

alter table public.runs
  add column if not exists payment_id uuid;

do $$ begin
  alter table public.runs
    add constraint runs_payment_id_fkey
    foreign key (payment_id) references public.payments(id) on delete set null;
exception when duplicate_object then null; end $$;

-- Partial unique index: enforce one run per payment, but allow many
-- NULL payment_id rows (admin runs, legacy test rows, etc.)
create unique index if not exists runs_payment_id_unique
  on public.runs (payment_id)
  where payment_id is not null;

create index if not exists runs_payment_id_idx
  on public.runs (payment_id);
