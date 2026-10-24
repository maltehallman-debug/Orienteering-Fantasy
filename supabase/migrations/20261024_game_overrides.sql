-- Admin overrides for the game: races added or removed, game weeks forced on or off.
-- Everyone (and the nightly data job, with the public key) can read them; only admins can add or remove them.
create table if not exists public.game_overrides(
  id bigint generated always as identity primary key,
  kind text not null check (kind in ('race_add','race_remove','week_on','week_off')),
  ref text not null check (length(ref) between 1 and 40),
  label text check (label is null or length(label) <= 120),
  created_by uuid default auth.uid(),
  created_at timestamptz not null default now(),
  unique (kind, ref)
);
alter table public.game_overrides enable row level security;
create policy "anyone reads overrides" on public.game_overrides for select to anon, authenticated using (true);
create policy "admins add overrides" on public.game_overrides for insert to authenticated with check ((select public.is_admin()));
create policy "admins remove overrides" on public.game_overrides for delete to authenticated using ((select public.is_admin()));
grant select on public.game_overrides to anon, authenticated;
grant insert, delete on public.game_overrides to authenticated;
