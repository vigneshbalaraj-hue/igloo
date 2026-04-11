-- Post-reel feedback: 5-star rating + optional text comment.
-- One feedback per run (unique index on run_id).
-- All writes go through service_role; RLS only needed for SELECT.

create table public.run_feedback (
  id          uuid primary key default gen_random_uuid(),
  run_id      uuid not null references public.runs(id) on delete cascade,
  user_id     uuid not null references public.users(id) on delete cascade,
  rating      smallint not null check (rating >= 1 and rating <= 5),
  comment     text,
  created_at  timestamptz not null default now()
);

create unique index run_feedback_run_id_uniq on public.run_feedback (run_id);
create index run_feedback_created_at_idx on public.run_feedback (created_at desc);

alter table public.run_feedback enable row level security;

create policy run_feedback_select_own on public.run_feedback
  for select using (
    user_id in (
      select id from public.users
      where clerk_user_id = auth.jwt() ->> 'sub'
    )
  );
