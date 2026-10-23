#!/usr/bin/env bash
# Rebuild index.html from liveresultat.orientering.se. Run from anywhere; results are cached in pipeline/data/results.
set -euo pipefail
S="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$S")"
mkdir -p "$S/data/results" "$S/build"
curl -fsS --retry 3 -m 120 "https://liveresultat.orientering.se/api.php?method=getcompetitions" -o "$S/data/comps.json"
python3 "$S/scripts/parse_comps.py" "$S"
python3 "$S/scripts/classes.py" "$S"
python3 "$S/scripts/fetch_results.py" "$S"
python3 "$S/scripts/build_dataset.py" "$S"
python3 "$S/scripts/build_data.py" "$S"
(cd "$S" && python3 scripts/assemble.py)
cp "$S/build/index.html" "$ROOT/index.html"
