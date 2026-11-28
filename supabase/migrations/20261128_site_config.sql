-- Admin dashboard: site configuration with a draft and a published version, a version history, and admin statistics.
-- Anyone may read the published configuration (the public site applies it). Only admins (public.is_admin()) may read the
-- draft, save it, publish it or restore an older version. Security lives here, in row level security, not in the page.

create table if not exists public.site_config (
  id int primary key default 1 check (id = 1),
  draft jsonb not null default '{}'::jsonb,
  published jsonb not null default '{}'::jsonb,
  draft_updated_at timestamptz,
  draft_updated_by uuid,
  published_at timestamptz,
  published_by uuid
);
insert into public.site_config (id) values (1) on conflict (id) do nothing;

create table if not exists public.site_config_history (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  author uuid default auth.uid(),
  action text not null check (action in ('publish', 'restore')),
  note text check (char_length(note) <= 300),
  config jsonb not null
);

alter table public.site_config enable row level security;
alter table public.site_config_history enable row level security;

drop policy if exists "admins read config" on public.site_config;
create policy "admins read config" on public.site_config for select to authenticated using (public.is_admin());
drop policy if exists "admins write config" on public.site_config;
create policy "admins write config" on public.site_config for update to authenticated using (public.is_admin()) with check (public.is_admin());
drop policy if exists "admins read history" on public.site_config_history;
create policy "admins read history" on public.site_config_history for select to authenticated using (public.is_admin());
drop policy if exists "admins add history" on public.site_config_history;
create policy "admins add history" on public.site_config_history for insert to authenticated with check (public.is_admin());

grant select, update on public.site_config to authenticated;
grant select, insert on public.site_config_history to authenticated;

-- the published configuration, for everyone (the public site calls this)
create or replace function public.get_site_config()
returns jsonb language sql stable security definer set search_path = '' as $$
  select coalesce((select published from public.site_config where id = 1), '{}'::jsonb)
$$;
grant execute on function public.get_site_config() to anon, authenticated;

-- publish the draft: copy it to published and keep a version
create or replace function public.publish_site_config(p_note text default null)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare c jsonb;
begin
  if not public.is_admin() then raise exception 'not allowed'; end if;
  select draft into c from public.site_config where id = 1;
  update public.site_config set published = c, published_at = now(), published_by = auth.uid() where id = 1;
  insert into public.site_config_history (action, note, config) values ('publish', left(p_note, 300), c);
  return c;
end $$;
grant execute on function public.publish_site_config(text) to authenticated;

-- restore an older version: it becomes both the draft and the published configuration
create or replace function public.restore_site_config(p_id bigint)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare c jsonb;
begin
  if not public.is_admin() then raise exception 'not allowed'; end if;
  select config into c from public.site_config_history where id = p_id;
  if c is null then raise exception 'no such version'; end if;
  update public.site_config set draft = c, published = c, draft_updated_at = now(), draft_updated_by = auth.uid(),
    published_at = now(), published_by = auth.uid() where id = 1;
  insert into public.site_config_history (action, note, config) values ('restore', 'Återställd från version ' || p_id, c);
  return c;
end $$;
grant execute on function public.restore_site_config(bigint) to authenticated;

-- numbers for the dashboard, admins only
create or replace function public.admin_stats()
returns jsonb language plpgsql stable security definer set search_path = '' as $$
begin
  if not public.is_admin() then raise exception 'not allowed'; end if;
  return jsonb_build_object(
    'users', (select count(*) from auth.users),
    'users_7d', (select count(*) from auth.users where created_at > now() - interval '7 days'),
    'profiles', (select count(*) from public.profiles),
    'squads', (select count(distinct user_id) from public.squads),
    'leagues', (select count(*) from public.leagues),
    'news', (select count(*) from public.news),
    'removal_open', (select count(*) from public.removal_requests where not coalesce(handled, false)),
    'feedback_open', (select count(*) from public.feedback where not coalesce(handled, false)),
    'photos_pending', (select count(*) from public.photo_submissions where status = 'pending'),
    'closed_beta', (select enabled from public.app_flags where name = 'closed_beta')
  );
end $$;
grant execute on function public.admin_stats() to authenticated;

-- the draft, history and admin functions are not for anonymous visitors at all
revoke all on public.site_config, public.site_config_history from anon;
revoke execute on function public.admin_stats(), public.publish_site_config(text), public.restore_site_config(bigint) from anon, public;
grant execute on function public.admin_stats(), public.publish_site_config(text), public.restore_site_config(bigint) to authenticated;
