-- Published squads for the live season, one per manager per round.
-- League-mates see a squad only after the round has started; nobody can change it after that.

create table if not exists public.season_rounds(
  round int primary key check (round between 0 and 60),
  starts_on date not null,
  starts_at timestamptz generated always as ((starts_on::timestamp) at time zone 'Europe/Stockholm') stored
);
alter table public.season_rounds enable row level security;
create policy "rounds read" on public.season_rounds for select to anon, authenticated using (true);
insert into public.season_rounds(round, starts_on) values
  (0,'2026-05-04'),
  (1,'2026-05-11'),
  (2,'2026-05-18'),
  (3,'2026-05-25'),
  (4,'2026-06-01'),
  (5,'2026-06-08'),
  (6,'2026-06-15'),
  (7,'2026-06-22'),
  (8,'2026-06-29'),
  (9,'2026-07-06'),
  (10,'2026-07-13'),
  (11,'2026-07-20'),
  (12,'2026-07-27'),
  (13,'2026-08-03'),
  (14,'2026-08-10'),
  (15,'2026-08-17'),
  (16,'2026-08-24'),
  (17,'2026-08-31'),
  (18,'2026-09-07'),
  (19,'2026-09-14'),
  (20,'2026-09-21'),
  (21,'2026-09-28'),
  (22,'2026-10-05'),
  (23,'2026-10-12'),
  (24,'2026-10-19'),
  (25,'2026-10-26'),
  (26,'2026-11-02'),
  (27,'2026-11-09'),
  (28,'2026-11-16'),
  (29,'2026-11-23'),
  (30,'2026-11-30'),
  (31,'2026-12-07'),
  (32,'2026-12-14'),
  (33,'2026-12-21')
on conflict (round) do update set starts_on = excluded.starts_on;

create table if not exists public.lineups(
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  round int not null references public.season_rounds(round),
  squad text[] not null check (cardinality(squad) = 6),
  captain text not null,
  chip text check (chip in ('wc','tc')),
  updated_at timestamptz not null default now(),
  primary key (user_id, round),
  check (captain = any(squad))
);
create index if not exists lineups_round on public.lineups(round);
alter table public.lineups enable row level security;

create or replace function public.round_open(r int) returns boolean
language sql stable security invoker set search_path = '' as $$
  select exists(select 1 from public.season_rounds s where s.round = r and now() < s.starts_at)
$$;

create policy "lineups read own or started in shared league" on public.lineups for select to authenticated using (
  user_id = (select auth.uid())
  or (
    not public.round_open(round)
    and exists(select 1 from public.league_members a join public.league_members b on a.code = b.code
               where a.user_id = (select auth.uid()) and b.user_id = lineups.user_id)
  )
);
create policy "lineups write own before start" on public.lineups for insert to authenticated
  with check (user_id = (select auth.uid()) and public.round_open(round));
create policy "lineups change own before start" on public.lineups for update to authenticated
  using (user_id = (select auth.uid()) and public.round_open(round))
  with check (user_id = (select auth.uid()) and public.round_open(round));
create policy "lineups remove own before start" on public.lineups for delete to authenticated
  using (user_id = (select auth.uid()) and public.round_open(round));
