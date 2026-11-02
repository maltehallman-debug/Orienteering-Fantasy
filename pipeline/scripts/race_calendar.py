# The public race calendar on eventor.se: which competitions are coming up, when, who organises them and at what level.
# Only what anyone sees on https://eventor.se/events (name, dates, organiser, region, distance, level, cancelled or not):
# no entries and no personal data. Asked once a week, one request, with the page's own default filter (championships,
# national, regional and international races). Kept in data/eventor/calendar.json.
#
# Writes data/calendar_events.json, read by build_dataset.py when the Eventor API is paused: the coming races and
# whether each is a championship, for the race list and the big weeks.
# Switch: "calendar" in pipeline/eventor.json (true: on).
import os, sys, json, time, datetime as dt, urllib.request
S = sys.argv[1]
C = f"{S}/data/eventor"; os.makedirs(C, exist_ok=True)
RAW = f"{C}/calendar.json"; OUT = f"{S}/data/calendar_events.json"
try: CFG = json.load(open(f"{S}/eventor.json"))
except Exception: CFG = {}
TODAY = dt.date.today()
def age(p): return time.time() - os.path.getmtime(p) if os.path.exists(p) else 1e12

raw = None
if not CFG.get("calendar", False):
    print("calendar: off (pipeline/eventor.json)")
elif age(RAW) < 6 * 86400:
    print("calendar: this week's copy reused")
else:
    mon = TODAY - dt.timedelta(days=TODAY.weekday())
    body = {"startDate": f"{mon.isoformat()}T00:00:00", "endDate": f"{(mon + dt.timedelta(days=70)).isoformat()}T23:59:59", "name": "",
            "classifications": ["Championship", "National", "Regional", "International"], "includeMyEntries": False}
    req = urllib.request.Request("https://backend.eventor.se/api/calendar/search", data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "Accept": "application/json",
                                          "User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r: data = json.loads(r.read())
        if isinstance(data, list):
            json.dump({"asof": TODAY.isoformat(), "events": data}, open(RAW, "w"), ensure_ascii=False); print("calendar: fetched", len(data), "races")
        else: print("calendar: unexpected answer, last copy kept")
    except Exception as e:
        print("calendar: not reached, last copy kept:", type(e).__name__)
try: raw = json.load(open(RAW))
except Exception: raw = None

LEVEL = {"Championship": 1, "National": 2, "Regional": 3, "International": 1}
out = []
if raw:
    for e in raw.get("events", []):
        if e.get("status") in ("Canceled", "Cancelled"): continue
        if not set(e.get("disciplines") or []) & {"Foot"}: continue
        if not any((o.get("countryId") or 752) == 752 for o in e.get("organisers") or [{}]): continue
        out.append({"eo": e.get("eventId"), "name": e.get("name", ""), "date": (e.get("startDate") or "")[:10],
                    "level": LEVEL.get(e.get("classification"), 4), "org": ", ".join(o.get("name", "") for o in e.get("organisers") or [])})
    out = [o for o in out if o["date"] and o["eo"]]
json.dump(out, open(OUT, "w"), ensure_ascii=False)
# while the API is paused the race list comes from here: the API's stale copies of it are put aside (entries are kept)
if not CFG.get("enabled", False):
    for f in ("eventor_events.json", "eventor_upcoming.json", "eventor_weeks.json"):
        if os.path.exists(f"{S}/data/{f}"): os.remove(f"{S}/data/{f}")
print("calendar races (Swedish, foot-O, not cancelled):", len(out), "from", raw.get("asof") if raw else None)
