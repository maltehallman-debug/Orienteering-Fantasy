# Who has entered the coming big races, from the public entry lists on eventor.se (the same list anyone sees under
# "Alla anmälda" on a race's page). Not the club API (eventor.orientering.se/api), which stays paused.
#
# Kept light: the calendar's races this game week and championship and national races next week, one request per race, and a race
# is asked again at most every other day. Only D/H 15-21 entries are kept (name, club, class); the rest is dropped at
# once. Copies in data/eventor/site_entries/<eventId>.json.
#
# Writes data/eventor_entries.json ({eid, rid, name, club, cls}), read by build_dataset.py.
# Switch: "entries" in pipeline/eventor.json (true: on).
import os, re, sys, json, time, datetime as dt, urllib.request
S = sys.argv[1]
C = f"{S}/data/eventor/site_entries"; os.makedirs(C, exist_ok=True)
OUT = f"{S}/data/eventor_entries.json"
try: CFG = json.load(open(f"{S}/eventor.json"))
except Exception: CFG = {}
TODAY = dt.date.today(); MON = TODAY - dt.timedelta(days=TODAY.weekday())
REAL = re.compile(r"^([DH])(15|16|18|20|21)(E|ELIT|ELITE)?$")
def norm(n): return re.sub(r"[\s_-]", "", (n or "").upper())
def age(p): return time.time() - os.path.getmtime(p) if os.path.exists(p) else 1e12

if not CFG.get("entries", False): print("entries: off (pipeline/eventor.json)"); sys.exit(0)
# the winter pause: after the beta round nothing is played until three weeks before the launch
BETA_END = dt.date(2026, 11, 8)
try: launch = dt.date.fromisoformat(json.load(open(f"{S}/data/eventor/launch.json"))["dates"][0])
except Exception: launch = dt.date(2027, 3, 5)
pause = BETA_END < TODAY < launch - dt.timedelta(days=21)

try: cal = json.load(open(f"{S}/data/calendar_events.json"))
except Exception: cal = []
horizon = MON + dt.timedelta(days=13)   # the end of next game week
wkend = MON + dt.timedelta(days=6)
# this game week: every race in the calendar (its big races decide the round); next week: national races and up
want = sorted({c["eo"] for c in cal if TODAY.isoformat() <= c["date"] <= horizon.isoformat()
               and (c.get("level", 9) <= 2 or c["date"] <= wkend.isoformat())})
print("entries: races asked for" if not pause else "entries: winter pause, nothing asked", want if not pause else "")

calls = 0
for eid in ([] if pause or os.environ.get("LIVE") == "1" else want):
    p = f"{C}/{eid}.json"
    if age(p) < 2 * 86400 - 3600: continue
    req = urllib.request.Request(f"https://backend.eventor.se/api/events/{eid}/entry-list",
                                 headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"})
    try:
        calls += 1
        with urllib.request.urlopen(req, timeout=60) as r: data = json.loads(r.read())
        rows = []
        for en in data.get("entries", []):
            if en.get("isRelayTeam"): continue
            for rc in en.get("raceClasses") or []:
                cls = norm(rc.get("className"))
                if REAL.match(cls):
                    rows.append({"eid": eid, "rid": rc.get("eventRaceId") or 0, "name": re.sub(r"\s+", " ", en.get("competitorName") or "").strip(),
                                 "club": en.get("organisationName") or "", "cls": cls})
        json.dump(rows, open(p, "w"), ensure_ascii=False)
        time.sleep(2)
    except Exception as e:
        print("entries:", eid, "not reached, last copy kept:", type(e).__name__)

# races that are over are dropped; the rest of the copies make up the list
out, per = [], {}
for f in os.listdir(C):
    eid = int(f.split(".")[0])
    dates = [c["date"] for c in cal if c["eo"] == eid]
    if dates and max(dates) < (TODAY - dt.timedelta(days=7)).isoformat(): os.remove(f"{C}/{f}"); continue
    rows = json.load(open(f"{C}/{f}")); out += rows; per[eid] = len(rows)
if out or not os.path.exists(OUT): json.dump(out, open(OUT, "w"), ensure_ascii=False)
print("entries: requests", calls, "- D/H 15-21 entries per race", per)
