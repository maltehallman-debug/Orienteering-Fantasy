-- The removal form becomes the site's contact point (as the EU Digital Services Act asks of a service with user
-- content): asking for a runner to be left out, reporting a name or picture, privacy questions and requests under
-- the GDPR, and anything else. Anyone can send one, signed in or not; only admins read and handle them.
alter table public.removal_requests add column if not exists kind text not null default 'runner';
alter table public.removal_requests drop constraint if exists removal_requests_kind_check;
alter table public.removal_requests add constraint removal_requests_kind_check check (kind in ('runner','report','privacy','rights','other'));
