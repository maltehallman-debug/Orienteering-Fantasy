-- Tips from signed-in managers: bugs, ideas or anything else. Each manager writes only as themselves;
-- only admins read and mark them done. The browser and page are kept so a bug can be reproduced.
create table if not exists public.feedback (
  id bigint generated always as identity primary key,
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  kind text not null check (kind in ('bug','idea','other')),
  message text not null check (length(message) between 3 and 4000),
  context text check (context is null or length(context) <= 500),
  handled boolean not null default false,
  created_at timestamptz not null default now()
);
alter table public.feedback enable row level security;
drop policy if exists "managers send feedback" on public.feedback;
create policy "managers send feedback" on public.feedback for insert to authenticated
  with check (user_id = (select auth.uid()) and handled = false);
drop policy if exists "admins read feedback" on public.feedback;
create policy "admins read feedback" on public.feedback for select to authenticated using ((select public.is_admin()));
drop policy if exists "admins handle feedback" on public.feedback;
create policy "admins handle feedback" on public.feedback for update to authenticated using ((select public.is_admin())) with check ((select public.is_admin()));
drop policy if exists "admins delete feedback" on public.feedback;
create policy "admins delete feedback" on public.feedback for delete to authenticated using ((select public.is_admin()));
create index if not exists feedback_open on public.feedback (created_at) where not handled;
