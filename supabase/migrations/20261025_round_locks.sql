-- Each live round locks the evening before its week's first big race, 20:00 Swedish time (season_rounds.locks_at;
-- round_open() already uses it, falling back to Monday 00:00). The nightly build works the times out from Eventor
-- and sends them here. Only it can: the call needs the key kept in the Vault as 'round_sync_key'. Only rounds that
-- are still open can be moved, never to a time that has passed or outside their week, so no lock is ever undone.
create or replace function public.sync_round_locks(k text, locks jsonb) returns int
language plpgsql security definer set search_path = '' as $$
declare n int := 0; x jsonb; rr int; t timestamptz;
begin
  if k is null or length(k) < 32 or k is distinct from (select decrypted_secret from vault.decrypted_secrets where name = 'round_sync_key' limit 1) then
    raise exception 'not allowed' using errcode = '42501';
  end if;
  for x in select * from jsonb_array_elements(coalesce(locks, '[]'::jsonb)) loop
    rr := (x->>'round')::int; t := (x->>'locks_at')::timestamptz;
    update public.season_rounds s set locks_at = t
      where s.round = rr and now() < coalesce(s.locks_at, s.starts_at) and t > now()
        and t > s.starts_at - interval '2 days' and t < s.starts_at + interval '7 days'
        and s.locks_at is distinct from t;
    if found then n := n + 1; end if;
  end loop;
  return n;
end $$;
revoke all on function public.sync_round_locks(text, jsonb) from public;
grant execute on function public.sync_round_locks(text, jsonb) to anon, authenticated;
