-- Each manager can name their team and set a profile picture; league-mates see both.
alter table public.profiles add column if not exists team text check (team is null or char_length(team) between 1 and 30);
alter table public.profiles add column if not exists avatar text check (avatar is null or (char_length(avatar) < 120 and avatar like id::text || '/%' and avatar ~ '\.jpg$'));

-- public bucket for profile pictures: small JPEGs, each user only writes in their own folder
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('avatars', 'avatars', true, 300000, array['image/jpeg'])
on conflict (id) do update set public = excluded.public, file_size_limit = excluded.file_size_limit, allowed_mime_types = excluded.allowed_mime_types;

create policy "avatars upload own folder" on storage.objects for insert to authenticated
  with check (bucket_id = 'avatars' and (storage.foldername(name))[1] = (select auth.uid())::text);
create policy "avatars delete own" on storage.objects for delete to authenticated
  using (bucket_id = 'avatars' and (storage.foldername(name))[1] = (select auth.uid())::text);
