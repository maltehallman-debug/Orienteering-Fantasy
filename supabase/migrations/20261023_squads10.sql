-- Ten-runner squads (first five = A team) and five chips. Replaces public.lineups (six runners, two chips),
-- which stays in place unused. Same rules: league-mates see a squad only after its round has started,
-- and nobody can write, change or delete a squad once its round has started.
create table if not exists public.squads(
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  round int not null references public.season_rounds(round),
  squad text[] not null check (cardinality(squad) = 10),
  captain text not null,
  chip text check (chip in ('wc','tc','ax','bb','yo')),
  updated_at timestamptz not null default now(),
  primary key (user_id, round),
  check (captain = any(squad))
);
create index if not exists squads_round on public.squads(round);
alter table public.squads enable row level security;
create policy "squads read own or started in shared league" on public.squads for select to authenticated using (
  user_id = (select auth.uid())
  or (
    not public.round_open(round)
    and exists(select 1 from public.league_members a join public.league_members b on a.code = b.code
               where a.user_id = (select auth.uid()) and b.user_id = squads.user_id)
  )
);
create policy "squads write own before start" on public.squads for insert to authenticated
  with check (user_id = (select auth.uid()) and public.round_open(round));
create policy "squads change own before start" on public.squads for update to authenticated
  using (user_id = (select auth.uid()) and public.round_open(round))
  with check (user_id = (select auth.uid()) and public.round_open(round));
create policy "squads remove own before start" on public.squads for delete to authenticated
  using (user_id = (select auth.uid()) and public.round_open(round));
