-- An admin can mark a manager's name or team name as not allowed. Until the manager chooses a new, allowed one,
-- others see "Manager" and the game asks them for a new name. Only admins (or the database itself) set the flag;
-- a manager clears it only by changing what was flagged.
alter table public.profiles add column if not exists name_flag text check (name_flag is null or name_flag in ('name','team','both'));

create or replace function public.profiles_name_guard() returns trigger language plpgsql set search_path = '' as $$
declare adm boolean := coalesce(public.is_admin(), false) or current_user in ('postgres', 'service_role', 'supabase_admin');
begin
  if tg_op = 'INSERT' then
    if not public.name_ok(new.name) then new.name := 'Manager'; end if;
    if not public.name_ok(new.team) then new.team := null; end if;
    new.name_flag := null;
    return new;
  end if;
  if new.name is distinct from old.name and not public.name_ok(new.name) then
    raise exception 'name not allowed' using errcode = '22023';
  end if;
  if new.team is distinct from old.team and not public.name_ok(new.team) then
    raise exception 'team name not allowed' using errcode = '22023';
  end if;
  if not adm and new.name_flag is distinct from old.name_flag then
    if new.name_flag is not null then raise exception 'only admins flag names' using errcode = '42501'; end if;
    if old.name_flag in ('name','both') and new.name is not distinct from old.name then raise exception 'choose a new name' using errcode = '22023'; end if;
    if old.name_flag in ('team','both') and new.team is not distinct from old.team then raise exception 'choose a new team name' using errcode = '22023'; end if;
  end if;
  return new;
end $$;
