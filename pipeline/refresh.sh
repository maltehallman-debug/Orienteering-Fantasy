#!/usr/bin/env bash
# Rebuild index.html from liveresultat.orientering.se. Run from anywhere; results are cached in pipeline/data/results.
# LIVE=1 (the quarter-hourly runs on race days): only today's races are asked for, and only from liveresultat;
# nothing is sent to eventor.se (the calendar and entries come from the saved copies) and start lists are skipped.
set -euo pipefail
S="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$S")"
mkdir -p "$S/data/results" "$S/build"
curl -fsS --retry 3 -m 120 "https://liveresultat.orientering.se/api.php?method=getcompetitions" -o "$S/data/comps.json"
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
python3 "$S/scripts/build_dataset.py" "$S"
python3 "$S/scripts/build_data.py" "$S"
python3 "$S/scripts/sync_locks.py" "$S"
(cd "$S" && python3 scripts/assemble.py)
cp "$S/build/index.html" "$ROOT/index.html"
