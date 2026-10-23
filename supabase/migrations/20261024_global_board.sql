-- Global leaderboard: once a round has started (its squads are locked), every signed-in player may read
-- everyone's squad for it, so every client can compute the same global table. Open rounds stay private.
create policy "squads read started (everyone)" on public.squads for select to authenticated
  using (not public.round_open(round));
