-- Getting ready to open the game to the public.

-- 1. Runners (or their parents) can ask to be taken out of the game. Anyone can send a request, signed in or not;
--    only admins can read and handle them.
create table if not exists public.removal_requests (
  id bigserial primary key,
  runner text not null check (char_length(runner) between 2 and 120),
  message text check (message is null or char_length(message) <= 1000),
  contact text check (contact is null or char_length(contact) <= 200),
  created_at timestamptz not null default now(),
  handled boolean not null default false
);
alter table public.removal_requests enable row level security;
create policy "anyone asks to be removed" on public.removal_requests for insert to anon, authenticated with check (handled = false);
create policy "admins read removal requests" on public.removal_requests for select to authenticated using ((select public.is_admin()));
create policy "admins handle removal requests" on public.removal_requests for update to authenticated using ((select public.is_admin())) with check ((select public.is_admin()));
create policy "admins delete removal requests" on public.removal_requests for delete to authenticated using ((select public.is_admin()));

-- 2. An admin can hide a runner from the game (the nightly build leaves them out). Runner keys can be long.
alter table public.game_overrides drop constraint if exists game_overrides_kind_check;
alter table public.game_overrides add constraint game_overrides_kind_check check (kind = any (array['race_add','race_remove','week_on','week_off','runner_hide']));
alter table public.game_overrides drop constraint if exists game_overrides_ref_check;
alter table public.game_overrides add constraint game_overrides_ref_check check (length(ref) between 1 and 120);

-- 3. Names everyone can see: no slurs or crude words. Checked here, so it holds whatever the page does.
--    Letters are compared after lower-casing and undoing common look-alike digits; short words only at a word start.
create or replace function public.name_ok(t text) returns boolean language sql immutable set search_path = '' as $$
  select t is null or not (
    translate(lower(t), '013457@$', 'oieastas') ~ '(fitta|fittor|knull|fuck|cunt|nigg|whore|slut|pussy|penis|vagina|porn|våldt|hitler|nazi|bitch)'
    or translate(lower(t), '013457@$', 'oieastas') ~ '(^|[^a-zåäö])(kuk|snopp|hora|horor|bög|rape|cock|porr|neger|balle|slyn)'
  )
$$;
create or replace function public.profiles_name_guard() returns trigger language plpgsql set search_path = '' as $$
begin
  -- a new account never fails over its name (sign-up must work): it becomes "Manager" instead
  if tg_op = 'INSERT' then
    if not public.name_ok(new.name) then new.name := 'Manager'; end if;
    if not public.name_ok(new.team) then new.team := null; end if;
    return new;
  end if;
  if new.name is distinct from old.name and not public.name_ok(new.name) then
    raise exception 'name not allowed' using errcode = '22023';
  end if;
  if new.team is distinct from old.team and not public.name_ok(new.team) then
    raise exception 'team name not allowed' using errcode = '22023';
  end if;
  return new;
end $$;
drop trigger if exists profiles_name_guard on public.profiles;
create trigger profiles_name_guard before insert or update on public.profiles for each row execute function public.profiles_name_guard();

-- 4. Admins can rename a manager or clear a team name that breaks the rules.
create policy "profiles moderate (admin)" on public.profiles for update to authenticated using ((select public.is_admin())) with check ((select public.is_admin()));
