-- Runner photos submitted by the runner (or a parent), shown after an admin approves them.

create table if not exists public.app_admins(
  user_id uuid primary key references auth.users(id) on delete cascade
);
alter table public.app_admins enable row level security;
create policy "admins read self" on public.app_admins for select to authenticated using (user_id = (select auth.uid()));

create or replace function public.is_admin() returns boolean
language sql stable security invoker set search_path = '' as $$
  select exists(select 1 from public.app_admins where user_id = (select auth.uid()))
$$;
revoke execute on function public.is_admin() from public, anon;
grant execute on function public.is_admin() to authenticated;

create table if not exists public.photo_submissions(
  id uuid primary key default gen_random_uuid(),
  runner_id text not null check (char_length(runner_id) between 3 and 80 and runner_id ~ '\|[HD]$'),
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  path text not null unique,
  status text not null default 'pending' check (status in ('pending','approved','rejected')),
  relation text not null check (relation in ('self','guardian','admin')),
  consent boolean not null check (consent),
  created_at timestamptz not null default now(),
  reviewed_at timestamptz
);
create index if not exists photo_submissions_runner_approved on public.photo_submissions(runner_id) where status = 'approved';
create index if not exists photo_submissions_user on public.photo_submissions(user_id);
alter table public.photo_submissions enable row level security;

create policy "photos read approved (anon)" on public.photo_submissions for select to anon
  using (status = 'approved');
create policy "photos read" on public.photo_submissions for select to authenticated
  using (status = 'approved' or user_id = (select auth.uid()) or (select public.is_admin()));
create policy "photos submit own" on public.photo_submissions for insert to authenticated
  with check (
    user_id = (select auth.uid())
    and status = 'pending'
    and path like (select auth.uid())::text || '/%'
    and (relation <> 'admin' or (select public.is_admin()))
  );
-- at most 5 photos waiting per person (a trigger: a subquery in the policy would recurse into this table's own policies)
create or replace function public.photo_pending_limit() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if (select count(*) from public.photo_submissions where user_id = new.user_id and status = 'pending') >= 5 then
    raise exception 'Too many photos waiting for approval' using errcode = 'P0001';
  end if;
  return new;
end $$;
revoke execute on function public.photo_pending_limit() from public, anon, authenticated;
create trigger photo_pending_limit before insert on public.photo_submissions for each row execute function public.photo_pending_limit();
create policy "photos review (admin)" on public.photo_submissions for update to authenticated
  using ((select public.is_admin())) with check ((select public.is_admin()));
create policy "photos withdraw own or admin" on public.photo_submissions for delete to authenticated
  using (user_id = (select auth.uid()) or (select public.is_admin()));

-- public bucket: approved images load for everyone; uploads only into your own folder, small JPEGs only
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('runner-photos', 'runner-photos', true, 400000, array['image/jpeg'])
on conflict (id) do update set public = excluded.public, file_size_limit = excluded.file_size_limit, allowed_mime_types = excluded.allowed_mime_types;

create policy "runner photos upload own folder" on storage.objects for insert to authenticated
  with check (bucket_id = 'runner-photos' and (storage.foldername(name))[1] = (select auth.uid())::text);
create policy "runner photos delete own or admin" on storage.objects for delete to authenticated
  using (bucket_id = 'runner-photos' and ((storage.foldername(name))[1] = (select auth.uid())::text or (select public.is_admin())));
