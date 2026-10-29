# Eventor (eventor.orientering.se), the Swedish federation's events and entries.
# Runs in the nightly job with EVENTOR_API_KEY from a GitHub Actions secret. The key is only ever sent as a request
# header to eventor.orientering.se: it is never printed, written to a file or put into the page. Without a key this
# script does nothing and the site keeps using liveresultat alone.
#
# The key is used as little as possible: only for the coming races and who has entered them, in the game's classes.
# Results come from liveresultat alone. Every answer is cached in data/eventor (kept between runs), so a second run
# the same day, for example when an admin applies a change, asks Eventor for nothing. A normal day is about 5-15
# requests, one at a time with a pause between them.
#
# What it writes (all under pipeline/data, never committed):
#   eventor_meta.json / eventor_replaces.json  left empty (Eventor results are no longer used), old Eventor results removed
#   eventor_upcoming.json  Swedish foot-O races with D/H 16-21 classes from today to the end of the season
#   eventor_entries.json   who has entered those races (D/H 16-21 classes only)
#   eventor_weeks.json     big competitions per game week
import os, sys, json, re, time, glob, shutil, collections, datetime as dt, urllib.request, urllib.parse, urllib.error
import xml.etree.ElementTree as ET
S = sys.argv[1]
KEY = os.environ.get("EVENTOR_API_KEY", "").strip()
if not KEY:
    print("eventor: no key, skipped"); sys.exit(0)
BASE = "https://eventor.orientering.se/api/"
C = f"{S}/data/eventor"; os.makedirs(f"{C}/classes", exist_ok=True)
TODAY = dt.date.today(); RECENT = 10; AHEAD = 21
DAY = 20 * 3600   # "once a day": a cached answer younger than this is used as it is
# the race list reaches two months ahead: big competitions are judged on entries, which only exist close to the race
SEASON_END = min("2027-10-31", (TODAY + dt.timedelta(days=60)).isoformat())
FROM = (TODAY - dt.timedelta(days=RECENT)).isoformat()
PAUSE = 2.0
OFFSET = 9_000_000
REAL = re.compile(r"^([DH])(15|16|18|20|21)(E|ELIT|ELITE)?$")
def norm(n): return re.sub(r"[\s_-]", "", (n or "").upper())
def strip(t): return t.split("}", 1)[-1]
def kids(e, name): return [c for c in e if strip(c.tag) == name]
def kid(e, name):
    for c in e:
        if strip(c.tag) == name: return c
def path(e, *names):
    for n in names:
        if e is None: return None
        e = kid(e, n)
    return e
def text(e, *names):
    e = path(e, *names) if names else e
    return (e.text or "").strip() if e is not None and e.text else ""
calls = collections.Counter()
def get(p, **q):
    url = BASE + p + ("?" + urllib.parse.urlencode(q) if q else "")
    req = urllib.request.Request(url, headers={"ApiKey": KEY, "Accept": "application/xml"})
    for attempt in range(3):
        time.sleep(PAUSE)
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                calls[p.split("/")[0]] += 1; return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (400, 403, 404): calls[f"http{e.code}"] += 1; return None
            time.sleep(10 * (attempt + 1))
        except Exception:
            time.sleep(10 * (attempt + 1))
    calls["failed"] += 1; return None
def jload(p, default):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return default
def jsave(p, o): json.dump(o, open(p, "w", encoding="utf-8"), ensure_ascii=False)
def age(p): return time.time() - os.path.getmtime(p) if os.path.exists(p) else 1e12
def cached(name, p, max_age, **q):
    # the raw answer, from data/eventor when it is younger than max_age, else from Eventor (and kept)
    f = f"{C}/{name}"
    if age(f) < max_age: return open(f, "rb").read()
    raw = get(p, **q)
    if raw: open(f, "wb").write(raw)
    elif os.path.exists(f): return open(f, "rb").read()   # Eventor did not answer: the last copy will do
    return raw

# ---- Eventor results are no longer used: take out what earlier versions wrote into the shared files ----
comps = jload(f"{S}/data/comps_clean.json", []); _n0 = len(comps); comps = [c for c in comps if c["id"] < OFFSET]
classes = {k: v for k, v in jload(f"{S}/data/classes.json", {}).items() if int(k) < OFFSET}
for f in glob.glob(f"{S}/data/results/9*__*.json"):
    if int(os.path.basename(f).split("__")[0]) >= OFFSET: os.remove(f)
jsave(f"{S}/data/comps_clean.json", comps); jsave(f"{S}/data/classes.json", classes)
jsave(f"{S}/data/eventor_meta.json", {}); jsave(f"{S}/data/eventor_replaces.json", [])
shutil.rmtree(f"{C}/results", ignore_errors=True)
if os.path.exists(f"{C}/results_meta.json"): os.remove(f"{C}/results_meta.json")
if _n0 - len(comps): print("old Eventor result competitions removed", _n0 - len(comps))

# ---- organisations: which clubs are Swedish (refreshed every three months) ----
op = f"{C}/orgs.json"; orgs = jload(op, {})
if not orgs or age(op) > 90 * 86400:
    raw = get("organisations")
    if raw:
        orgs = {}
        for o in ET.fromstring(raw):
            if strip(o.tag) != "Organisation": continue
            cid = next((a.attrib.get("value") for a in o.iter() if strip(a.tag) == "CountryId"), "")
            orgs[text(o, "OrganisationId")] = cid
        jsave(op, orgs)
print("eventor organisations", len(orgs))

# ---- admin overrides (set on the site by admins): races added or removed, game weeks forced on or off ----
SB_URL = "https://hjpfmubvpvftxyyemltn.supabase.co"; SB_KEY = "sb_publishable_Ent2RuVrh-iKyjT1or8gOw_UFdZ74ch"   # the page's public key
try:
    _rq = urllib.request.Request(SB_URL + "/rest/v1/game_overrides?select=kind,ref", headers={"apikey": SB_KEY, "Authorization": "Bearer " + SB_KEY})
    OVR = json.loads(urllib.request.urlopen(_rq, timeout=30).read())
except Exception:
    OVR = jload(f"{S}/data/game_overrides.json", [])
jsave(f"{S}/data/game_overrides.json", OVR)
ADD = {int(o["ref"]) for o in OVR if o["kind"] == "race_add" and str(o["ref"]).isdigit()}
DROP = {str(o["ref"]) for o in OVR if o["kind"] == "race_remove"}
print("admin overrides", len(OVR))

# ---- the official launch: Sverigepremiären, the season's first big weekend. The event list above only reaches two
# months ahead, so it is looked up on its own, in the first months of the coming year. Once found it is checked again
# only every second week ----
try:
    _yr = TODAY.year + (1 if TODAY.month >= 4 else 0)
    _lp = f"{C}/launch.json"; _old = jload(_lp, {})
    _known = any(d.startswith(str(_yr)) for d in _old.get("dates", []))
    _raw = None if _known and age(_lp) < 14 * 86400 else cached("launch_events.xml", "events", 7 * 86400,
                                                                 fromDate=f"{_yr}-01-15", toDate=f"{_yr}-04-30", classificationIds="1,2,3,4")
    if _raw is None and _known: raise StopIteration
    _hits = []
    for e in (ET.fromstring(_raw) if _raw else []):
        if strip(e.tag) != "Event" or not re.search(r"sverigepremi", text(e, "Name") or "", re.I) or text(e, "EventStatusId") == "10": continue
        _ds = [text(r, "RaceDate", "Date") for r in kids(e, "EventRace")] or [text(e, "StartDate", "Date")]
        _hits.append({"eid": int(text(e, "EventId")), "name": text(e, "Name"), "dates": sorted(d for d in _ds if d)})
    if _hits:
        _dates = sorted(d for h in _hits for d in h["dates"])
        jsave(f"{C}/launch.json", {"name": "Sverigepremiären", "dates": _dates, "events": _hits})
        print("launch: Sverigepremiären", _dates[0], "to", _dates[-1], [h["name"] for h in _hits])
    else:
        print("launch: no Sverigepremiären found in", _yr, "- keeping", jload(f"{C}/launch.json", {}).get("dates"))
except StopIteration:
    print("launch: known", _old["dates"][0], "(not asked again yet)")
except Exception as ex:
    print("launch: lookup failed", type(ex).__name__)

# ---- the winter pause: after the beta round the game waits for the launch. Nothing is played then, so no entries
# or class lists are needed and the race list is only looked at once a week, until three weeks before the launch ----
BETA_END = dt.date(2026, 11, 8)
_ld = jload(f"{C}/launch.json", {}).get("dates") or ["2027-03-05"]
PAUSE_WINTER = BETA_END < TODAY < dt.date.fromisoformat(_ld[0]) - dt.timedelta(days=21)
if PAUSE_WINTER: print("winter pause until", _ld[0], "- race list weekly, no entries or class lists")

# ---- events: championship, national, district and local; foot orienteering, organised by Swedish clubs, not cancelled ----
raw = cached("events.xml", "events", 7 * 86400 if PAUSE_WINTER else 2 * DAY + 4 * 3600, fromDate=FROM, toDate=SEASON_END, classificationIds="1,2,3,4")
if not raw: print("eventor: event list unavailable, skipped"); sys.exit(0)
events = []
for e in ET.fromstring(raw):
    if strip(e.tag) != "Event": continue
    if text(e, "DisciplineId") != "1" or text(e, "EventStatusId") == "10": continue
    _org = path(e, "Organiser"); org_ids = [text(o) for o in kids(_org if _org is not None else e, "OrganisationId")]
    if not org_ids or any(orgs.get(o, "752") != "752" for o in org_ids): continue
    races = [{"id": int(text(r, "EventRaceId")), "name": text(r, "Name"), "date": text(r, "RaceDate", "Date")} for r in kids(e, "EventRace")]
    events.append({"id": int(text(e, "EventId")), "name": text(e, "Name"), "cls": int(text(e, "EventClassificationId") or 4),
                   "form": e.attrib.get("eventForm", "IndSingleDay"), "date": text(e, "StartDate", "Date"), "end": text(e, "FinishDate", "Date"),
                   "races": [r for r in races if r["date"]]})
# races an admin added are taken whatever their classification or date
for eid in ADD - {e["id"] for e in events}:
    raw = cached(f"event_{eid}.xml", f"event/{eid}", 7 * 86400)
    if not raw: continue
    e = ET.fromstring(raw)
    races = [{"id": int(text(r, "EventRaceId")), "name": text(r, "Name"), "date": text(r, "RaceDate", "Date")} for r in kids(e, "EventRace")]
    events.append({"id": eid, "name": text(e, "Name"), "cls": int(text(e, "EventClassificationId") or 4), "form": e.attrib.get("eventForm", "IndSingleDay"),
                   "date": text(e, "StartDate", "Date"), "end": text(e, "FinishDate", "Date"), "races": [r for r in races if r["date"]]})
events = [e for e in events if str(e["id"]) not in DROP]
print("eventor events (Swedish, foot-O, not cancelled)", len(events), dict(collections.Counter(e["cls"] for e in events)))

# ---- classes per event: which have D/H 16-21 classes, and their ids (entries are asked for those classes only).
# Only for races in the next AHEAD days, once per race and once more in its last four days. ----
def classes_of(ev):
    # class names and ids. Asked once per race, and once more in its last four days in case classes were added late
    p = f"{C}/classes/{ev['id']}.json"; old = jload(p, None)
    if ev["end"] < TODAY.isoformat() or PAUSE_WINTER: return old
    soon = ev["date"] <= (TODAY + dt.timedelta(days=4)).isoformat()
    if old is not None and "_eb" in old and (not soon or old.get("_late")): return old
    raw = get("eventclasses", eventId=ev["id"], includeEntryBreakdown="true")   # numberOfEntries is only sent with the breakdown
    if raw is None: return old or {}
    out = {}; n = 0
    for c in ET.fromstring(raw):
        if strip(c.tag) != "EventClass": continue
        out[text(c, "EventClassId")] = text(c, "ClassShortName") or text(c, "Name")
        try: n += int(c.attrib.get("numberOfEntries", 0))
        except ValueError: pass
    out["_n"] = n; out["_eb"] = 1
    if soon: out["_late"] = 1
    jsave(p, out); return out
near = [e for e in events if e["date"] <= (TODAY + dt.timedelta(days=AHEAD)).isoformat() or e["id"] in ADD]
cl = {e["id"]: c for e in near if (c := classes_of(e)) is not None}
def cnames(eid): return [v for k, v in cl.get(eid, {}).items() if not k.startswith("_")]
def youth_ages(ev): return {REAL.match(norm(n)).group(2).replace("15", "16") for n in cnames(ev["id"]) if REAL.match(norm(n))}
yev = [e for e in near if youth_ages(e)]
print("eventor events with D/H 16-21 classes", len(yev))

BIGNAME = re.compile(r"helg utan älg|novembertävling", re.I)
def big(ev): return ev["cls"] in (1, 2) or bool(BIGNAME.search(ev["name"]))

# ---- upcoming races and big competitions per game week ----
def monday(d): return d - dt.timedelta(days=d.weekday())
up = []
far = [e for e in events if e["date"] > (TODAY + dt.timedelta(days=AHEAD)).isoformat() and big(e)]
for ev in yev + far:
    for r in ev["races"]:
        if TODAY.isoformat() <= r["date"] <= SEASON_END:
            multi = len(ev["races"]) > 1
            up.append({"eid": ev["id"], "rid": r["id"], "name": ev["name"] + (f", {r['name']}" if multi and r["name"] and r["name"].lower() not in ev["name"].lower() else ""),
                       "date": r["date"], "cls": ev["cls"], "big": big(ev), "ages": len(youth_ages(ev)) if ev["id"] in cl else 4})
up.sort(key=lambda u: (u["date"], u["name"]))
jsave(f"{S}/data/eventor_upcoming.json", up)
evinfo = [{"eid": e["id"], "name": e["name"], "cls": e["cls"], "dates": [r["date"] for r in e["races"]], "n": cl.get(e["id"], {}).get("_n"),
           "forced": e["id"] in ADD} for e in events if e["id"] in cl or e["id"] in ADD]
jsave(f"{S}/data/eventor_events.json", evinfo)
weeks = collections.defaultdict(set)
for ev in events:
    if big(ev) and (ev["id"] not in cl or youth_ages(ev)):
        for r in ev["races"]: weeks[monday(dt.date.fromisoformat(r["date"])).isoformat()].add(ev["id"])
# for deciding the rule: every week ahead, how many events of each kind (1 championship, 2 national, 3 district, 4 local)
_kinds = collections.defaultdict(collections.Counter)
for ev in events:
    for r in ev["races"]:
        if r["date"] >= TODAY.isoformat(): _kinds[monday(dt.date.fromisoformat(r["date"])).isoformat()][ev["cls"]] += 1
print("events per week ahead by classification:", {k: dict(sorted(v.items())) for k, v in sorted(_kinds.items())})
# a week that has started keeps the count it had (the event list only reaches back RECENT days)
wk = {k: len(v) for k, v in weeks.items()}
for k, v in jload(f"{C}/weeks.json", {}).items():
    if k < monday(TODAY).isoformat(): wk[k] = v
jsave(f"{C}/weeks.json", wk); jsave(f"{S}/data/eventor_weeks.json", dict(sorted(wk.items())))
print("upcoming races", len(up), "big competitions per week ahead:", {k: len(v) for k, v in sorted(weeks.items()) if k >= monday(TODAY).isoformat()})

# ---- entries for the races in this game week and the next: who is running ----
# this game week and all of the next one (on a Saturday, the coming game week starts in two days)
horizon = (monday(TODAY) + dt.timedelta(days=20)).isoformat()
want = sorted({u["eid"] for u in up if u["date"] <= horizon})
# only the game's classes are asked for (D/H 15-21): the ids come from the class lists above, so Eventor sends no one
# else. Asked once a day; a second run the same day reads the copy from data/eventor.
cids = {e: sorted(k for k, v in cl.get(e, {}).items() if not k.startswith("_") and REAL.match(norm(v))) for e in want}
want = [e for e in want if cids[e]]
ep = f"{C}/entries.json"; ec = jload(ep, {})
if PAUSE_WINTER: entries = []; print("entries: winter pause, not asked")
elif ec.get("want") == want and age(ep) < DAY: entries = ec["entries"]; print("entries: today's copy reused")
else:
    entries = []; got = True
    for i in range(0, len(want), 20):
        ids = want[i:i + 20]
        raw = get("entries", eventIds=",".join(map(str, ids)), eventClassIds=",".join(c for e in ids for c in cids[e]),
                  includePersonElement="true", includeOrganisationElement="true", includeEventElement="false")
        if not raw: got = False; continue
        for en in ET.fromstring(raw):
            if strip(en.tag) != "Entry": continue
            eid = int(text(en, "EventId") or 0); ecid = text(en, "EntryClass", "EventClassId")
            cn = str(cl.get(eid, {}).get(ecid, ""))
            if not REAL.match(norm(cn)): continue
            comp = path(en, "Competitor"); per = path(comp, "Person")
            if per is None: continue
            pn = path(per, "PersonName")
            given = " ".join(text(g) for g in kids(pn, "Given")) if pn is not None else ""
            o = path(comp, "Organisation")
            entries.append({"eid": eid, "rid": int(text(en, "EventRaceId") or 0), "name": re.sub(r"\s+", " ", f"{given} {text(pn, 'Family')}").strip(),
                            "club": (text(o, "ShortName") or text(o, "Name")) if o is not None else "", "cls": norm(cn)})
    if got: jsave(ep, {"want": want, "entries": entries})
    elif not entries: entries = ec.get("entries", [])   # Eventor did not answer: yesterday's list will do
jsave(f"{S}/data/eventor_entries.json", entries)
# Eventor's class list often reports no entry counts; the field size is then the entries in the game's classes ("ny")
_ny = collections.Counter(e["eid"] for e in entries)
for e in evinfo: e["ny"] = _ny.get(e["eid"], 0)
jsave(f"{S}/data/eventor_events.json", evinfo)
print("entries per event:", dict(collections.Counter(e["eid"] for e in entries)), "competitors per event:", {e: cl.get(e, {}).get("_n") for e in want})
print("entries in D/H 15-21 for", len(want), "events:", len(entries))
print("eventor calls", dict(calls))
