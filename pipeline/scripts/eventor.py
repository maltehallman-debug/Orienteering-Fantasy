# Eventor (eventor.orientering.se), the Swedish federation's official results, entries and events.
# Runs in the nightly job with EVENTOR_API_KEY from a GitHub Actions secret. The key is only ever sent as a request
# header to eventor.orientering.se: it is never printed, written to a file or put into the page. Without a key this
# script does nothing and the site keeps using liveresultat alone.
#
# What it writes (all under pipeline/data, never committed):
#   comps_clean.json / classes.json / results/*.json  official results in the same shape as the liveresultat files,
#                                                     one competition per race (id 9000000 + Eventor race id)
#   eventor_meta.json      per competition: Eventor event id, classification, relay, big
#   eventor_replaces.json  liveresultat competitions that Eventor has published officially (they are then dropped)
#   eventor_upcoming.json  Swedish foot-O races with D/H 16-21 classes from today to the end of the season
#   eventor_entries.json   who has entered those races (D/H 16-21 classes only)
#   eventor_weeks.json     big competitions per game week
import os, sys, json, re, time, glob, collections, datetime as dt, urllib.request, urllib.parse, urllib.error
import xml.etree.ElementTree as ET
S = sys.argv[1]
KEY = os.environ.get("EVENTOR_API_KEY", "").strip()
if not KEY:
    print("eventor: no key, skipped"); sys.exit(0)
BASE = "https://eventor.orientering.se/api/"
C = f"{S}/data/eventor"; os.makedirs(f"{C}/classes", exist_ok=True); os.makedirs(f"{C}/results", exist_ok=True)
# Kept deliberately light on Eventor's servers: one request at a time with a pause between them, results only for
# races in the last RECENT days (the season's history already comes from liveresultat), and everything cached so a
# finished race's results and class lists are fetched once and never again. A normal night is a few dozen requests.
TODAY = dt.date.today(); RECENT = 10; AHEAD = 21
# the race list reaches two months ahead: big competitions are judged on entries, which only exist close to the race
SEASON_END = min("2027-10-31", (TODAY + dt.timedelta(days=60)).isoformat())
FROM = (TODAY - dt.timedelta(days=RECENT)).isoformat()
PAUSE = 1.0
OFFSET = 9_000_000
REAL = re.compile(r"^([DH])(15|16|18|20|21)(E|ELIT|ELITE)?$")
YOUNG = re.compile(r"^[DH](10|11|12|13|14)$")   # never scored, only tells that a runner is young
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

# ---- organisations: which clubs are Swedish (refreshed monthly) ----
op = f"{C}/orgs.json"; orgs = jload(op, {})
if not orgs or time.time() - os.path.getmtime(op) > 30 * 86400:
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

# ---- events: championship, national, district and local; foot orienteering, organised by Swedish clubs, not cancelled ----
raw = get("events", fromDate=FROM, toDate=SEASON_END, classificationIds="1,2,3,4")
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
    raw = get(f"event/{eid}")
    if not raw: continue
    e = ET.fromstring(raw)
    races = [{"id": int(text(r, "EventRaceId")), "name": text(r, "Name"), "date": text(r, "RaceDate", "Date")} for r in kids(e, "EventRace")]
    events.append({"id": eid, "name": text(e, "Name"), "cls": int(text(e, "EventClassificationId") or 4), "form": e.attrib.get("eventForm", "IndSingleDay"),
                   "date": text(e, "StartDate", "Date"), "end": text(e, "FinishDate", "Date"), "races": [r for r in races if r["date"]]})
events = [e for e in events if str(e["id"]) not in DROP]
print("eventor events (Swedish, foot-O, not cancelled)", len(events), dict(collections.Counter(e["cls"] for e in events)))

# ---- classes per event: which have D/H 16-21 classes. Only for races in the last RECENT days and the next AHEAD days
# (results and entries are only needed there). Cached: a past event's classes are never fetched again, an upcoming
# event's at most every third day. ----
def classes_of(ev):
    # class names, plus "_n": everyone entered in the event (all classes), which decides whether it is a big competition.
    # Refetched while the event is ahead (at most every third day) and once more after it, for the final count.
    p = f"{C}/classes/{ev['id']}.json"; old = jload(p, None)
    upcoming = ev["end"] >= TODAY.isoformat()
    age = time.time() - os.path.getmtime(p) if old is not None else 1e12
    stale = old is None or "_eb" not in old or (upcoming and age > 3 * 86400) or (not upcoming and old.get("_final") is None)
    if not stale: return old
    raw = get("eventclasses", eventId=ev["id"], includeEntryBreakdown="true")   # numberOfEntries is only sent with the breakdown
    if raw is None: return old or {}
    out = {}; n = 0
    for c in ET.fromstring(raw):
        if strip(c.tag) != "EventClass": continue
        out[text(c, "EventClassId")] = text(c, "ClassShortName") or text(c, "Name")
        try: n += int(c.attrib.get("numberOfEntries", 0))
        except ValueError: pass
    out["_n"] = n; out["_eb"] = 1
    if not upcoming: out["_final"] = 1
    jsave(p, out); return out
near = [e for e in events if e["date"] <= (TODAY + dt.timedelta(days=AHEAD)).isoformat() or e["id"] in ADD]
cl = {e["id"]: classes_of(e) for e in near}
def cnames(eid): return [v for k, v in cl.get(eid, {}).items() if not k.startswith("_")]
def youth_ages(ev): return {REAL.match(norm(n)).group(2).replace("15", "16") for n in cnames(ev["id"]) if REAL.match(norm(n))}
yev = [e for e in near if youth_ages(e)]
print("eventor events with D/H 16-21 classes", len(yev))

# ---- results (IOF XML 3.0), parsed into the liveresultat row shape ----
STATUS = {"OK": 0, "DidNotStart": 1, "DidNotFinish": 2, "MissingPunch": 3, "Disqualified": 4, "OverTime": 2, "SportingWithdrawal": 2}
def hund(s):
    try: return str(int(round(float(s) * 100)))
    except Exception: return ""
def pname(p):
    n = path(p, "Name"); given = " ".join(text(g) for g in kids(n, "Given")) if n is not None else ""
    return re.sub(r"\s+", " ", f"{given} {text(n, 'Family')}").strip()
def club(e): o = path(e, "Organisation"); return (text(o, "ShortName") or text(o, "Name")) if o is not None else ""
def parse_results(raw):
    root = ET.fromstring(raw); ev = path(root, "Event"); races = {}
    for r in kids(ev, "Race"):
        rid = text(r, "Extensions", "EventRaceId")
        races[text(r, "RaceNumber") or "1"] = {"id": int(rid) if rid else None, "name": text(r, "Name"), "date": text(r, "StartTime", "Date")}
    out = collections.defaultdict(dict)   # race number -> class -> rows
    for cr in kids(root, "ClassResult"):
        cn = text(cr, "Class", "ShortName") or text(cr, "Class", "Name")
        if not (REAL.match(norm(cn)) or YOUNG.match(norm(cn))): continue
        cn = norm(cn)
        teams = kids(cr, "TeamResult")
        if teams:
            legs = collections.defaultdict(lambda: collections.defaultdict(list))   # race -> leg -> rows
            for t in teams:
                tname = text(t, "Name") or club(t)
                mem = []
                for m in kids(t, "TeamMemberResult"):
                    for res in kids(m, "Result"):
                        mem.append((res.attrib.get("raceNumber", "1"), int(text(res, "Leg") or 0), m, res))
                last = {}
                for rn, leg, m, res in mem:
                    if leg and leg >= last.get(rn, (0,))[0]: last[rn] = (leg, res)
                for rn, leg, m, res in mem:
                    if not leg: continue
                    own = STATUS.get(text(res, "Status"))
                    if own is None: continue
                    row = {"place": text(res, "Position"), "name": pname(path(m, "Person")), "club": tname, "result": hund(text(res, "Time")),
                           "status": own, "timeplus": hund(text(res, "TimeBehind")), "progress": 100}
                    if last.get(rn, (None, None))[1] is res:   # the last leg holds the team's final time and status
                        ov = path(res, "OverallResult")
                        if ov is not None:
                            row.update(result=hund(text(ov, "Time")), status=STATUS.get(text(ov, "Status"), own), place=text(ov, "Position"), timeplus=hund(text(ov, "TimeBehind")))
                    legs[rn][leg].append(row)
            for rn, L in legs.items():
                for leg, rows in L.items(): out[rn][f"{cn}-{leg}"] = rows
            continue
        for pr in kids(cr, "PersonResult"):
            for res in kids(pr, "Result"):
                st = STATUS.get(text(res, "Status"))
                if st is None: continue                      # not run yet, not competing, cancelled
                out[res.attrib.get("raceNumber", "1")].setdefault(cn, []).append(
                    {"place": text(res, "Position"), "name": pname(path(pr, "Person")), "club": club(pr), "result": hund(text(res, "Time")),
                     "status": st, "timeplus": hund(text(res, "TimeBehind")), "progress": 100})
    return races, out
def results_of(ev):
    # a race's results are fetched each night for its first 4 days (corrections come in), then never again
    p = f"{C}/results/{ev['id']}.json"
    fresh = ev["end"] >= (TODAY - dt.timedelta(days=4)).isoformat()
    old = jload(p, None) if os.path.exists(p) else None
    if old and old.get("v") != 3: fresh = True; os.utime(p, (0, 0))   # cached before H15/D15 counted: read once more
    if os.path.exists(p) and not fresh: return old
    if os.path.exists(p) and time.time() - os.path.getmtime(p) < 20 * 3600: return jload(p, None)
    raw = get("results/event/iofxml", eventId=ev["id"], includeSplitTimes="false")
    if raw is None: return jload(p, None)
    try: races, out = parse_results(raw)
    except ET.ParseError: return jload(p, None)
    o = {"races": races, "classes": out, "v": 3}; jsave(p, o); return o
past = [e for e in yev if e["date"] and e["date"] < TODAY.isoformat()]
R = {e["id"]: results_of(e) for e in past}
# races fetched on earlier nights stay in the cache and keep counting after they drop out of the window
for f in glob.glob(f"{C}/results/*.json"):
    eid = int(os.path.basename(f)[:-5])
    if eid not in R:
        o = jload(f, None); m = jload(f"{C}/results_meta.json", {}).get(str(eid))
        if o and m: past.append(m); R[eid] = results_of(m) if o.get("v") != 3 and "end" in m else o
_rm = jload(f"{C}/results_meta.json", {}); _rm.update({str(e["id"]): e for e in past if R.get(e["id"])}); jsave(f"{C}/results_meta.json", _rm)

# ---- into the shared data files ----
comps = jload(f"{S}/data/comps_clean.json", []); comps = [c for c in comps if c["id"] < OFFSET]
classes = {k: v for k, v in jload(f"{S}/data/classes.json", {}).items() if int(k) < OFFSET}
for f in glob.glob(f"{S}/data/results/9*__*.json"):
    if int(os.path.basename(f).split("__")[0]) >= OFFSET: os.remove(f)
BIGNAME = re.compile(r"helg utan älg|novembertävling", re.I)
def big(ev): return ev["cls"] in (1, 2) or bool(BIGNAME.search(ev["name"]))
meta = {}; written = 0; ev_fin = {}
for ev in past:
    o = R.get(ev["id"])
    if not o or not o.get("classes"): continue
    multi = len(o["races"]) > 1
    for rn, cls in o["classes"].items():
        race = o["races"].get(rn) or {}
        rid = race.get("id") or (ev["races"][0]["id"] if ev["races"] else None)
        date = race.get("date") or ev["date"]
        if not rid or not date or date >= TODAY.isoformat(): continue
        cid = OFFSET + rid
        name = ev["name"] + (f", {race['name']}" if multi and race.get("name") and race["name"].lower() not in ev["name"].lower() else "")
        comps.append({"id": cid, "name": name, "organizer": "", "date": date, "stage": int(rn) if multi else None})
        classes[str(cid)] = sorted(cls)
        meta[str(cid)] = {"eid": ev["id"], "cls": ev["cls"], "relay": "Relay" in ev["form"], "big": big(ev)}
        fin = set()
        for cn, rows in cls.items():
            jsave(f"{S}/data/results/{cid}__{norm(cn)}.json", {"id": cid, "className": cn, "rows": rows}); written += 1
            fin |= {r["name"].strip().lower() for r in rows if r["status"] == 0 and r["result"]}
        ev_fin[cid] = (date, fin)
jsave(f"{S}/data/comps_clean.json", comps); jsave(f"{S}/data/classes.json", classes); jsave(f"{S}/data/eventor_meta.json", meta)
print("eventor races with results", len(ev_fin), "class files", written)

# ---- the same race on liveresultat: Eventor's official copy replaces it (matched by date and the runners who finished) ----
lr_by_date = collections.defaultdict(list)
for c in comps:
    if c["id"] < OFFSET: lr_by_date[c["date"]].append(c["id"])
lr_fin = {}
def lr_names(cid):
    if cid not in lr_fin:
        s = set()
        for f in glob.glob(f"{S}/data/results/{cid}__*.json") + glob.glob(f"{S}/data/results/{cid}.json"):
            for r in jload(f, {}).get("rows", []):
                if r.get("status") == 0 and r.get("name"): s.add(r["name"].strip().lower())
        lr_fin[cid] = s
    return lr_fin[cid]
replaces = set()
for cid, (date, fin) in ev_fin.items():
    for lid in lr_by_date.get(date, []):
        ln = lr_names(lid)
        if len(fin) >= 3 and len(ln) >= 3 and len(fin & ln) >= .5 * min(len(fin), len(ln)): replaces.add(lid)
jsave(f"{S}/data/eventor_replaces.json", sorted(replaces))
print("liveresultat competitions replaced by Eventor", len(replaces))

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
entries = []; allent = collections.Counter()
for i in range(0, len(want), 15):
    ids = want[i:i + 15]
    raw = get("entries", eventIds=",".join(map(str, ids)), includePersonElement="true", includeOrganisationElement="true", includeEventElement="false")
    if not raw: continue
    for en in ET.fromstring(raw):
        if strip(en.tag) != "Entry": continue
        eid = int(text(en, "EventId") or 0); ecid = text(en, "EntryClass", "EventClassId"); allent[eid] += 1
        cn = str(cl.get(eid, {}).get(ecid, ""))
        if not REAL.match(norm(cn)): continue
        comp = path(en, "Competitor"); per = path(comp, "Person")
        if per is None: continue
        pn = path(per, "PersonName")
        given = " ".join(text(g) for g in kids(pn, "Given")) if pn is not None else ""
        o = path(comp, "Organisation")
        entries.append({"eid": eid, "rid": int(text(en, "EventRaceId") or 0), "name": re.sub(r"\s+", " ", f"{given} {text(pn, 'Family')}").strip(),
                        "club": (text(o, "ShortName") or text(o, "Name")) if o is not None else "", "cls": norm(cn)})
jsave(f"{S}/data/eventor_entries.json", entries)
# the entry list counts everyone entered (all classes), so it also gives the size of the field when the class list does not
for e in evinfo:
    if allent.get(e["eid"], 0) > (e["n"] or 0): e["n"] = allent[e["eid"]]
jsave(f"{S}/data/eventor_events.json", evinfo)
print("entries per event:", dict(collections.Counter(e["eid"] for e in entries)), "all classes:", dict(allent), "classes known for:", {e: cl.get(e, {}).get("_n") for e in want})
print("entries in D/H 16-21 for", len(want), "events:", len(entries))
print("eventor calls", dict(calls))
