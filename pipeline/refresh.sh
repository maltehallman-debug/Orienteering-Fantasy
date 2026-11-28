#!/usr/bin/env bash
# Rebuild index.html from liveresultat.orientering.se. Run from anywhere; results are cached in pipeline/data/results.
# LIVE=1 (the quarter-hourly runs on race days): only today's races are asked for, and only from liveresultat;
# nothing is sent to eventor.se (the calendar and entries come from the saved copies) and start lists are skipped.
set -euo pipefail
S="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$S")"
mkdir -p "$S/data/results" "$S/build"
if [ "${LIVE:-}" = "1" ]; then CT=(--retry 1 -m 40); else CT=(--retry 3 -m 120); fi
if curl -fsS "${CT[@]}" "https://liveresultat.orientering.se/api.php?method=getcompetitions" -o "$S/data/comps.new.json"; then
  mv "$S/data/comps.new.json" "$S/data/comps.json"
elif [ -s "$S/data/comps.json" ]; then echo "competition list not reached, saved copy used"
else exit 1; fi
python3 "$S/scripts/parse_comps.py" "$S"
python3 "$S/scripts/classes.py" "$S"
python3 "$S/scripts/fetch_results.py" "$S"
# official results, entries and the race list from Eventor (needs EVENTOR_API_KEY; skipped without it)
python3 "$S/scripts/eventor.py" "$S"
# the public race calendar on eventor.se, once a week (see the script)
python3 "$S/scripts/race_calendar.py" "$S" || echo "calendar skipped"
python3 "$S/scripts/race_entries.py" "$S" || echo "entries skipped"
# start lists for the coming days from liveresultat (who is set to run; also used when Eventor is missing)
if [ "${LIVE:-}" != "1" ]; then python3 "$S/scripts/startlists.py" "$S" || echo "start lists skipped"; fi
# birth years and club countries from O-Ringen (not on the quarter-hourly race-day runs)
if [ "${LIVE:-}" != "1" ]; then python3 "$S/scripts/oringen_ages.py" "$S" || echo "O-Ringen skipped"; fi
python3 "$S/scripts/build_dataset.py" "$S"
# the game data as last published (the data branch): finished weeks are locked from it
rm -f "$S/data/published_game.json"
for b in "${DATA_BRANCH:-data}" data; do
  if git -C "$ROOT" fetch -q --depth 1 origin "$b" 2>/dev/null && git -C "$ROOT" show FETCH_HEAD:game.json > "$S/data/published_game.json" 2>/dev/null; then echo "published data from $b"; break; fi
  rm -f "$S/data/published_game.json"
done
python3 "$S/scripts/build_data.py" "$S"
python3 "$S/scripts/sync_locks.py" "$S"
(cd "$S" && python3 scripts/assemble.py)
cp "$S/build/index.html" "$ROOT/index.html"
