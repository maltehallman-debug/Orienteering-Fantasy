import json, glob, collections, re, datetime as dt, math, sys, os, bisect
import numpy as np
S = sys.argv[1]
comps = {c["id"]: c for c in json.load(open(f"{S}/data/comps_clean.json"))}
MIN_FIN = 3
EXCLUDE = {36940, 36892, 40850, 37141, 37143, 40373, 40929}   # aggregates, chase duplicates, patrol, some foreign pilots, Natt-Njudung (small local night race)
# Eventor (official results, written by eventor.py when the nightly job has the key): competitions with ids from
# 9000000 are Eventor races, and the liveresultat copies of races Eventor has published are dropped
EV_OFFSET = 9_000_000
def _j(name, default):
    try: return json.load(open(f"{S}/data/{name}", encoding="utf-8"))
    except Exception: return default
EVMETA = _j("eventor_meta.json", {})
EXCLUDE |= set(_j("eventor_replaces.json", []))
# races an admin removed: an Eventor event id (all its races) or "lr:<liveresultat id>"
for o in _j("game_overrides.json", []):
    if o["kind"] == "race_remove":
        ref = str(o["ref"])
        if ref.startswith("lr:") and ref[3:].isdigit(): EXCLUDE.add(int(ref[3:]))
        elif ref.isdigit(): EXCLUDE |= {int(c) for c, m in EVMETA.items() if str(m.get("eid")) == ref}
print("eventor races", len(EVMETA), "liveresultat copies replaced", len(EXCLUDE) - 7)
SEASON_START = dt.date(2026, 5, 4)
TODAY = dt.date.today()
LAST_ROUND_START = dt.date(2027, 10, 25)   # the season runs to the end of October 2027
def norm(n): return re.sub(r"[\s_-]", "", n.upper())
def _pos(x):
    try: return int(x) > 0
    except Exception: return False
def finished(r): return r["status"] == 0 and _pos(r["result"])
def started(r): return finished(r) or r["status"] in (2, 3, 4)
def monday(d): return d - dt.timedelta(days=d.weekday())
def tier_of(c):
    if EVMETA.get(str(c["id"]), {}).get("cls") == 1: return max(1.2, _tier_name(c))   # Eventor: a championship
    return _tier_name(c)
def _tier_name(c):
    n = c["name"].lower()
    if "ungdoms-sm" in n: return 1.4
    if ("swedish league" in n or n.startswith("dm") or n.startswith("gm,") or "mästerskapen" in n
            or "unionsmatchen" in n or "jwoc" in n or "publiktävling sm" in n or "wcs spec" in n or "woc spect" in n):
        return 1.2
    return 1.0
# Only real competitions count: proper H/D15-21 classes (15 counts as 16) (plain or elite, not K/A/B/short variants),
# no other sports, no club-internal or training races, and at least two of the four age groups
# unless it is a championship (Ungdoms-SM and Unionsmatchen only have 16).
REAL = re.compile(r"^([DH])(15|16|18|20|21)(E|ELIT|ELITE)?$")
# a class name split into parts: relay legs ("H21-1"), heats ("D16-1", "D18E-2" at 25mannamedeln) or stages
PART = re.compile(r"^\s*([DH])\s*(15|16|18|20|21)\s*-?\s*(E|ELIT|ELITE)?\s*-\s*([1-9])\s*$", re.I)
# H15/D15 runners are in the game's youngest category, 16 (their races keep the real class in the label)
def cat(age): return "16" if age == "15" else age
def age_of(n):
    m = REAL.match(norm(n)) or PART.match(n)
    return cat(m.group(2)) if m else None
OTHER_SPORT = re.compile(r"mtbo|mtb-o|ol-skytte|skidorient|\bskid-?o\b|\bvtt\b|trail-?o\b|precision", re.I)
TRAINING = re.compile(r"\bkm\b|klubbmästerskap|klubbmatch|träning|^test\b|\btest \d|fasttest|testløb|ungdomsserie|u-serie|u-ringen|totalresultat", re.I)
_cl = json.load(open(f"{S}/data/classes.json"))
def clean_name(n): return re.sub(r"\s*\((lokal kopia|local copy)[^)]*\)?\s*$", "", n.strip(), flags=re.I).strip()
# Danish and Norwegian races: Swedish never writes ø or æ, and "stafet", "løb", "løp" are Danish/Norwegian words.
# (Eventor, once connected, decides this properly: only Swedish events count.)
FOREIGN = re.compile(r"[øæ]|\bstafet\b|\bløb|\bløp|bornholm|kolding|aarhus|århus|odense|aalborg|ålborg|esbjerg|silkeborg|horsens|vejle|herning|viborg|randers|roskilde|allerød|farum|tisvilde|københavn|copenhagen|danmark|denmark|oslo\b|bergen\b|trondheim|stavanger|kristiansand|drammen|lillehammer|tromsø|norge\b|norway", re.I)
def real_comp(c):
    if not c["name"].strip() or OTHER_SPORT.search(c["name"]) or TRAINING.search(c["name"]): return False
    if c["id"] < EV_OFFSET and FOREIGN.search(c["name"]): return False   # Eventor races are Swedish by their organiser
    ages = {age_of(n) for n in (_cl.get(str(c["id"])) or []) if age_of(n)}
    return len(ages) >= 2 or (len(ages) >= 1 and tier_of(c) > 1)

events = []
seen_ek = set()
parts = collections.defaultdict(dict)   # (competition, D/H, age, elite) -> {part number: result file}
for p in glob.glob(f"{S}/data/results/*.json"):
    j = json.load(open(p))
    cid = j["id"]; cn = norm(j.get("className", "H16"))
    if cid in EXCLUDE or cid not in comps: continue
    pm = PART.match(j.get("className", ""))
    if pm and real_comp(comps[cid]) and dt.date.fromisoformat(comps[cid]["date"]) < TODAY:
        parts[(cid, pm.group(1).upper(), pm.group(2), (pm.group(3) or "").upper())][int(pm.group(4))] = j
        continue
    m = REAL.match(cn)
    if not m or not real_comp(comps[cid]): continue
    ek = f"{cid}:{cn}"
    if ek in seen_ek: continue
    seen_ek.add(ek)
    c = comps[cid]
    rows = [r for r in j["rows"] if r["name"] and r["name"].strip().lower() != "vacant"]
    fin = [r for r in rows if finished(r)]
    if len(fin) < MIN_FIN: continue
    d = dt.date.fromisoformat(c["date"])
    if d >= TODAY: continue
    g, age = m.group(1), cat(m.group(2))
    # the label keeps the real class (H21 and H21E are different races in the same competition)
    events.append({"id": ek, "cid": cid, "eo": EVMETA.get(str(cid), {}).get("eid", 0), "name": f'{clean_name(c["name"])} ({cn})', "date": c["date"], "d": d, "tier": tier_of(c),
                   "g": g, "cls": g + age, "rows": rows, "fin": fin})
# ---- split classes ----
# A relay lists each leg as its own class. The same numbered team names ("OK Linné 1") come back on every leg with a
# different runner each time, and the last leg holds the team's final place and total time. Heats and stages are
# scored like any race: heats have no team names in common, stages have the same runners in every part.
TEAMNO = re.compile(r"\s+\d{1,2}$")
RELAYNAME = re.compile(r"stafett|relay|relais|staffel|kavle|tiomila|jukola|venla|budkavle", re.I)
def _rows(j): return [r for r in j["rows"] if r["name"] and r["name"].strip().lower() != "vacant"]
for (cid, g, age, el), P in parts.items():
    c = comps[cid]; d = dt.date.fromisoformat(c["date"]); legs = sorted(P); cls = g + age + el; age = cat(age)
    relay = bool(EVMETA.get(str(cid), {}).get("relay"))
    if len(legs) >= 2 and not relay:
        a, b = _rows(P[legs[0]]), _rows(P[legs[1]])
        ca, cb = {r["club"] for r in a}, {r["club"] for r in b}
        na, nb = {r["name"].strip().lower() for r in a}, {r["name"].strip().lower() for r in b}
        numbered = sum(1 for r in a if TEAMNO.search(r["club"] or "")) / max(1, len(a))
        relay = len(ca & cb) >= .6 * max(1, min(len(ca), len(cb))) and len(na & nb) <= .2 * max(1, min(len(na), len(nb))) and (numbered >= .6 or bool(RELAYNAME.search(c["name"])))
    if not relay:
        for k in legs:
            rows = _rows(P[k]); fin = [r for r in rows if finished(r)]
            if len(fin) < MIN_FIN: continue
            events.append({"id": f"{cid}:{cls}-{k}", "cid": cid, "eo": EVMETA.get(str(cid), {}).get("eid", 0), "name": f'{clean_name(c["name"])} ({cls}-{k})', "date": c["date"], "d": d,
                           "tier": tier_of(c), "g": g, "cls": g + age, "rows": rows, "fin": fin})
        continue
    final = {r["club"]: r for r in _rows(P[legs[-1]])}
    rows = []
    for k in legs:
        for r in _rows(P[k]):
            t = final.get(r["club"])
            if not t: continue
            rows.append({"name": r["name"], "club": TEAMNO.sub("", r["club"] or ""), "team": r["club"], "leg": k, "own": r["status"],
                         "result": t["result"], "status": r["status"] if r["status"] in (2, 3, 4) else (0 if finished(t) else 2), "teamok": finished(t)})
    teams_fin = {r["team"] for r in rows if r["teamok"]}
    if len(teams_fin) < MIN_FIN: continue
    events.append({"id": f"{cid}:{cls}:relay", "cid": cid, "eo": EVMETA.get(str(cid), {}).get("eid", 0), "name": f'{clean_name(c["name"])} ({cls}, relay)', "date": c["date"], "d": d,
                   "tier": tier_of(c), "g": g, "cls": g + age, "rows": rows, "fin": [r for r in rows if r["teamok"] and finished(r)], "relay": True})
print("relays", sum(1 for e in events if e.get("relay")), "split heats/stages", sum(1 for e in events if not e.get("relay") and e["id"].count("-") and ":" in e["id"] and e["id"].split(":")[1][-2:-1] == "-"))
# some organisers publish the same race as two competitions: keep one copy per race, date and class
_best = {}
for e in events:
    k = (e["name"].lower(), e["date"])
    if k not in _best or (len(e["fin"]), -e["cid"]) > (len(_best[k]["fin"]), -_best[k]["cid"]): _best[k] = e
print("duplicate race copies dropped", len(events) - len(_best))
events = sorted(_best.values(), key=lambda e: (e["date"], e["id"]))
print("counted event-classes", len(events))
# one runner = same name, same club, same sex. Two people who share a name but run for different clubs stay apart.
# Results under a district association ("... OF"), a "förbund" or with no club go to the runner's real club when
# exactly one runner of that name has one; otherwise they stay a separate runner.
def nclub(c): return re.sub(r"\s+", " ", (c or "").strip()).lower()
NONCLUB = re.compile(r"^$|\bof$|orienteringsförbund|förbund$")
_real = collections.defaultdict(set)
for e in events:
    for r in e["rows"]:
        c = nclub(r["club"])
        if started(r) and not NONCLUB.search(c): _real[(r["name"].strip().lower(), e["g"])].add(c)
# spellings of one club ("1900 Orientering" and "Aarhus 1900 Orientering"): a name that sits whole inside the other is the same club
# A joint relay team ("IFK Lidingö SOK / Täby OK") is never a runner's club: it maps to the part the runner also
# races for on their own, and a club name never maps into a joint name.
JOINT = re.compile(r"\s*/\s*|\s+&\s+")
_canon = {}
for nk, cs in _real.items():
    for c in cs:
        if JOINT.search(c):
            own = [x for x in JOINT.split(c) if x.strip() in cs]
            if len(own) == 1: _canon[(nk, c)] = own[0].strip()
            continue
        longer = [o for o in cs if o != c and len(c) >= 6 and not JOINT.search(o) and re.search(r"(^|\s)" + re.escape(c) + r"($|\s)", o)]
        if len(longer) == 1: _canon[(nk, c)] = longer[0]
for nk in list(_real): _real[nk] = {_canon.get((nk, c), c) for c in _real[nk]}
def rkey(r, e):
    n, c, g = r["name"].strip().lower(), nclub(r["club"]), e["g"]
    c = _canon.get(((n, g), c), c)
    if NONCLUB.search(c) and len(_real.get((n, g), ())) == 1: c = next(iter(_real[(n, g)]))
    return f"{n}|{c}|{g}"

# ---- strength ratings (field-adjusted log-time model), vectorised ----
keys_all = sorted({rkey(r, e) for e in events for r in e["fin"]})
kix = {k: i for i, k in enumerate(keys_all)}
ev_i, run_i, perf = [], [], []
for ei, e in enumerate(events):
    if e.get("relay"): continue
    lt = np.array([np.log(int(r["result"])) for r in e["fin"]])
    m = np.median(lt)
    for r, x in zip(e["fin"], lt):
        ev_i.append(ei); run_i.append(kix[rkey(r, e)]); perf.append(-(x - m))
ev_i = np.array(ev_i); run_i = np.array(run_i); perf = np.array(perf)
nR, nE = len(keys_all), len(events)
cnt = np.bincount(run_i, minlength=nR).astype(float)
evcnt = np.bincount(ev_i, minlength=nE).astype(float)
rating = np.zeros(nR); LAMBDA = 2.0
for it in range(40):
    fm = np.bincount(ev_i, weights=rating[run_i], minlength=nE) / np.maximum(evcnt, 1)
    num = np.bincount(run_i, weights=perf + fm[ev_i], minlength=nR)
    rating = num / (cnt + LAMBDA)
# D and H never share a start list, so their rating scales are separate: percentiles are taken within each gender
gmask = {g: np.array([k.endswith("|" + g) for k in keys_all]) for g in "DH"}
pool_vals = {g: np.sort(rating[(cnt >= 3) & gmask[g]]) for g in "DH"}
def strength_pct(k):
    i = kix.get(k)
    if i is None: return 0.05
    pv = pool_vals[k[-1]]
    return float(np.searchsorted(pv, rating[i]) / max(1, len(pv)))
STR = {k: strength_pct(k) for k in keys_all}
TOP = {k for k, v in STR.items() if v >= 0.85}
def beat_w(s): return 0.1 + 1.9 * s ** 3

# ---- scoring ----
FIN, CAP_BEAT = 2.0, 35.0
def score_relay(e):
    # every runner gets the team's result: its place, the teams it beat (worth their runners' average class) and its
    # margin to the winning team as a share of the winning time, so 3 minutes behind in a 4-hour relay is close
    T = {}
    for r in e["rows"]:
        t = T.setdefault(r["team"], {"keys": [], "rows": [], "time": int(r["result"]) if _pos(r["result"]) else 0, "ok": r["teamok"]})
        t["keys"].append(rkey(r, e)); t["rows"].append(r)
    tstr = {n: sum(STR.get(k, 0.05) for k in t["keys"]) / len(t["keys"]) for n, t in T.items()}
    fin = sorted(((n, t["time"]) for n, t in T.items() if t["ok"]), key=lambda x: x[1])
    win = fin[0][1]; times = [x for _, x in fin]
    top10 = sorted((tstr[n] for n, _ in fin), reverse=True)[:10]
    qf = 0.75 + 0.75 * (sum(top10) / len(top10))
    sizef = min(1.0, 0.4 + 0.6 * (len(fin) - 3) / 17)
    out = {}
    for n, t in T.items():
        for r, key in zip(t["rows"], t["keys"]):
            if r["own"] in (2, 3, 4): out[key] = {"k": {2: "DNF", 3: "MP", 4: "DSQ"}[r["own"]], "pts": -5.0}; continue
            if not t["ok"]: out[key] = {"k": "DNF", "pts": 0.0}; continue   # a teammate did not finish: no points, no penalty
            rank = 1 + bisect.bisect_left(times, t["time"])
            beaten = [m for m, x in fin if x > t["time"]]
            wsum = sum(beat_w(tstr[m]) for m in beaten)
            gap = (t["time"] - win) / win
            speed = max(0.0, 18 - 80 * gap) * qf * sizef
            pod = {1: 12, 2: 7, 3: 4}.get(rank, 0) * qf * sizef
            raw = FIN + min(CAP_BEAT, wsum) + speed + pod
            out[key] = {"k": "F", "rank": rank, "beaten": len(beaten), "t": t["time"], "gap": round(gap, 4), "pts": round(raw * e["tier"], 1), "topb": 0}
    return out
def score_event(e):
    if e.get("relay"): return score_relay(e)
    fin = sorted(e["fin"], key=lambda r: int(r["result"]))
    win = int(fin[0]["result"])
    fk = [(rkey(r, e), int(r["result"])) for r in fin]
    top10 = sorted((STR.get(k, 0.05) for k, _ in fk), reverse=True)[:10]
    qf = 0.75 + 0.75 * (sum(top10) / len(top10))
    sizef = min(1.0, 0.4 + 0.6 * (len(fin) - 3) / 17)
    times = [x for _, x in fk]
    out = {}
    for r in e["rows"]:
        key = rkey(r, e)
        if not started(r): continue
        if finished(r):
            t = int(r["result"])
            rank = 1 + bisect.bisect_left(times, t)
            beaten_list = [k for k, x in fk if x > t]
            wsum = sum(beat_w(STR.get(k, 0.05)) for k in beaten_list)
            topb = sum(1 for k in beaten_list if k in TOP)
            gap = (t - win) / win
            speed = max(0.0, 18 - 80 * gap) * qf * sizef
            pod = {1: 12, 2: 7, 3: 4}.get(rank, 0) * qf * sizef
            raw = FIN + min(CAP_BEAT, wsum) + speed + pod
            out[key] = {"k": "F", "rank": rank, "beaten": len(beaten_list), "t": t, "gap": round(gap, 4), "pts": round(raw * e["tier"], 1), "topb": topb}
        else:
            out[key] = {"k": {2: "DNF", 3: "MP", 4: "DSQ"}[r["status"]], "pts": -5.0}
    return out
for e in events:
    e["scores"] = score_event(e); e["n"] = len({r["team"] for r in e["fin"]}) if e.get("relay") else len(e["fin"])

# ---- runners ----
names = collections.defaultdict(collections.Counter)
clubs = collections.defaultdict(collections.Counter)
clsc = collections.defaultdict(collections.Counter)
series = collections.defaultdict(list)   # key -> [(date, pts)]
for e in events:
    for r in e["rows"]:
        if not started(r): continue
        k = rkey(r, e)
        names[k][r["name"].strip()] += 1
        clubs[k][(r["club"] or "").strip()] += 1
        clsc[k][e["cls"]] += 1
for e in events:
    for k, s in e["scores"].items(): series[k].append((e["date"], s["pts"]))
def pick_club(cn):
    nondist = [(c, n) for c, n in cn.most_common() if c and not re.search(r"\bOF$|Orienteringsförbund|^\s*$", c)]
    own = [(c, n) for c, n in nondist if not JOINT.search(c)]   # a joint relay team is not the runner's club
    return (own or nondist or cn.most_common())[0][0]
starts = {k: len(series[k]) for k in names}
POOL_MIN = 3
pool = sorted([k for k in names if starts[k] >= POOL_MIN], key=lambda k: (names[k].most_common(1)[0][0], k))
print("runners total", len(names), "pool", len(pool))

# ---- rounds ----
# A live game week needs at least two big competitions. A big competition has at least 100 competitors (everyone
# entered, all classes, from Eventor) and a good field: at least 5 of the game's top runners (top 15% by class
# rating) entered or racing in D/H 16-21. Admins can add or remove races and force a week on or off. A week is
# decided when it starts (from the data on its Monday morning) and then kept; until then it is shown as provisional.
LIVE_START = dt.date(2026, 11, 2)
EVINFO = _j("eventor_events.json", None)
OVR = _j("game_overrides.json", [])
WEEK_ON = {o["ref"] for o in OVR if o["kind"] == "week_on"}; WEEK_OFF = {o["ref"] for o in OVR if o["kind"] == "week_off"}
BIG_N, BIG_TOP = 100, 5
EVWEEKS = None; EVBIG = {}
if EVINFO is not None:
    top_in = collections.defaultdict(set)
    for en in _j("eventor_entries.json", []):
        k = rkey({"name": en["name"], "club": en["club"]}, {"g": en["cls"][0]})
        if k in TOP: top_in[en["eid"]].add(k)
    for e in events:
        eid = EVMETA.get(str(e["cid"]), {}).get("eid")
        if eid: top_in[eid] |= {rkey(r, e) for r in e["fin"]} & TOP
    weeks_now = collections.defaultdict(set)
    for ev in EVINFO:
        big = ev.get("forced") or ((ev.get("n") or 0) >= BIG_N and len(top_in.get(ev["eid"], ())) >= BIG_TOP)
        EVBIG[ev["eid"]] = {"big": bool(big), "n": ev.get("n"), "top": len(top_in.get(ev["eid"], ()))}
        if big:
            for d in ev["dates"]: weeks_now[monday(dt.date.fromisoformat(d)).isoformat()].add(ev["eid"])
    # a week that has started keeps what it was decided as
    fp = f"{S}/data/eventor/weeks_final.json"; final = _j("eventor/weeks_final.json", {})
    EVWEEKS = {}
    wk = SEASON_START
    while wk <= LAST_ROUND_START:
        k = wk.isoformat(); wk_started = wk <= TODAY
        if wk_started and k in final: EVWEEKS[k] = final[k]
        else:
            EVWEEKS[k] = {"big": len(weeks_now.get(k, ())), "final": wk_started}
            if wk_started: final[k] = EVWEEKS[k]
        wk += dt.timedelta(days=7)
    os.makedirs(os.path.dirname(fp), exist_ok=True); json.dump(final, open(fp, "w"))
    print("races ahead (name, date, competitors, top runners entered):", [(ev["name"], ev["dates"][0], EVBIG[ev["eid"]]["n"], EVBIG[ev["eid"]]["top"]) for ev in sorted(EVINFO, key=lambda x: x["dates"][0]) if ev["dates"] and ev["dates"][0] >= TODAY.isoformat()])
    print("big competitions:", sorted(((ev["name"], ev["dates"][0], EVBIG[ev["eid"]]["n"], EVBIG[ev["eid"]]["top"]) for ev in EVINFO if EVBIG[ev["eid"]]["big"]), key=lambda x: x[1]))
rounds = []
wk = SEASON_START; i = 0
while wk <= LAST_ROUND_START:
    ids = [e["id"] for e in events if monday(e["d"]) == wk]
    end = wk + dt.timedelta(days=6)
    w = EVWEEKS.get(wk.isoformat()) if EVWEEKS is not None else None
    big = w["big"] if w else None; decided = bool(w and w["final"])
    k = wk.isoformat()
    skip = wk >= LIVE_START and (k in WEEK_OFF or (k not in WEEK_ON and w is not None and decided and big < 2))
    pending = wk >= LIVE_START and w is not None and not decided and k not in WEEK_ON and k not in WEEK_OFF
    rounds.append({"n": i + 1, "start": k, "end": end.isoformat(), "events": [] if skip else ids, "final": end < TODAY, "big": big, "skip": skip,
                   "pending": pending, "forced": "on" if k in WEEK_ON else "off" if k in WEEK_OFF else None})
    wk += dt.timedelta(days=7); i += 1
print("rounds", len(rounds), [len(r["events"]) for r in rounds])
print("skipped live weeks", [r["start"] for r in rounds if r.get("skip")], "big per live week", [(r["start"], r["big"]) for r in rounds if r["start"] >= LIVE_START.isoformat()])

# ---- prices ----
PTAU, PBETA = float(os.environ.get("PTAU", "37.6")), float(os.environ.get("PBETA", "0.816"))
# ---- each runner's class: the youngest one they really race in ----
# You can race up an age class but never down, so the youngest class someone races in is their class (the most common
# one put juniors who often run H21 into H21). A class counts when it is at least 2 starts or a third of them. Anyone
# seen in an H10-H14 class is young and goes in the game's youngest class, 16.
YOUNG = re.compile(r"^[DH](10|11|12|13|14)$")
# (name, sex) -> {club: the oldest they can be this year}. A runner in H12 in 2026 is at most 12 that year, 13 in 2027.
_young = collections.defaultdict(dict)
for p in glob.glob(f"{S}/data/results/*.json"):
    j = json.load(open(p)); cn = norm(j.get("className", ""))
    if not YOUNG.match(cn): continue
    yr = int((comps.get(j.get("id"), {}).get("date") or str(TODAY.year))[:4]); bound = int(cn[1:]) + TODAY.year - yr
    for r in j.get("rows", []):
        if r.get("name") and started(r):   # raced (an entry alone is not enough: some camps list everyone in any class)
            c = nclub(r.get("club")); d = _young[(r["name"].strip().lower(), cn[0])]
            for x in {c} | {x.strip() for x in JOINT.split(c)}: d[x] = min(d.get(x, 99), bound)
AGES = ["16", "18", "20", "21"]
def youth_bound(k):
    # the oldest a runner seen in a youth class can be this year (None when never seen in one)
    n, g = k.split("|")[0], k.rsplit("|", 1)[1]
    yc = _young.get((n, g)) or {}
    b = [yc[c] for c in {nclub(c) for c in clubs[k]} | {k.split("|")[1]} if c in yc]
    return min(b) if b else None
# Runners under 15 are not in the game, nor anyone an admin has hidden (a runner or parent asked to be left out)
HIDE = {o["ref"] for o in OVR if o["kind"] == "runner_hide"}
_under = {k for k in pool if (youth_bound(k) or 99) <= 14}
pool = [k for k in pool if k not in _under and k not in HIDE]
print("left out: under 15", len(_under), sorted(names[k].most_common(1)[0][0] for k in _under)[:15], "hidden by an admin", len(HIDE))
def class_of(k):
    g = k.rsplit("|", 1)[1]
    if youth_bound(k) is not None: return g + "16"
    cc = clsc[k]; tot = sum(cc.values())
    for a in AGES:
        x = cc.get(g + a, 0)
        if x >= 2 or (x and x * 3 >= tot): return g + a
    return cc.most_common(1)[0][0]
CLS = {k: class_of(k) for k in pool}
# saved squads name runners by key; keys made from a joint relay club before it stopped counting as a club still work
ALIAS = {}
for k in pool:
    n, g = k.split("|")[0], k.rsplit("|", 1)[1]
    for c in clubs[k]:
        if JOINT.search(c or ""): ALIAS.setdefault(f"{n}|{nclub(c)}|{g}", k)
for (n, g), cs in _real.items():
    for c in cs:
        if JOINT.search(c) and f"{n}|{c}|{g}" not in pool:
            for part in JOINT.split(c):
                k = f"{n}|{part.strip()}|{g}"
                if k in pool: ALIAS.setdefault(f"{n}|{c}|{g}", k); break
ALIAS = {a: k for a, k in ALIAS.items() if a not in pool}
print("old keys kept as aliases", len(ALIAS))
_moved = [(names[k].most_common(1)[0][0], clsc[k].most_common(1)[0][0], CLS[k]) for k in pool if CLS[k] != clsc[k].most_common(1)[0][0]]
print("runners in a younger class than their most common one", len(_moved), _moved[:12], "seen in youth classes", len(_young))
W0, DECAY = 2.0, 0.9
allpts = [s["pts"] for e in events for s in e["scores"].values()]
league_mean = sum(allpts) / len(allpts)
ser_sorted = {k: sorted(series[k]) for k in pool}
ser_dates = {k: [d for d, _ in ser_sorted[k]] for k in pool}
def prices_before(cutoff):
    cs = cutoff.isoformat()
    ratings = {}
    gm = [s["pts"] for e in events if e["date"] < cs for s in e["scores"].values()]
    m0 = sum(gm) / len(gm) if gm else league_mean
    for k in pool:
        n = bisect.bisect_left(ser_dates[k], cs)
        if not n: continue
        num = den = 0.0
        for age, (_, p) in enumerate(reversed(ser_sorted[k][:n])):
            w = DECAY ** age; num += w * p; den += w
        ratings[k] = (num + W0 * m0) / (den + W0)
    # prices in thousands, set within each class (H16, D21, ...): the best runner 22k, three from 20k,
    # about 17.5k for 8th, 14.5k for 15th, 11k for 30th, 7k for 60th, then down to 2.5-3k for the rest
    out = {}
    for c in {CLS[k] for k in ratings}:
        order = sorted((k for k in ratings if CLS[k] == c), key=lambda k: -ratings[k])
        for i, k in enumerate(order): out[k] = round(2.5 + 19.5 * math.exp(-(i / PTAU) ** PBETA), 1)
    return out
price_by_round = []
for r in rounds:
    pr = prices_before(dt.date.fromisoformat(r["start"]))
    price_by_round.append({k: pr.get(k, 2.5) for k in pool})
    r["rated"] = len(pr)

hc = {int(k) for k, v in _cl.items() if v and any(age_of(n) for n in v)}
done_cids = {e["cid"] for e in events}
upcoming = []
for c in comps.values():
    if TODAY.isoformat() <= c["date"] <= "2027-10-31" and c["id"] in hc and c["id"] not in EXCLUDE and real_comp(c):
        upcoming.append({"id": c["id"], "name": clean_name(c["name"]), "date": c["date"]})
upcoming.sort(key=lambda x: (x["date"], x["id"]))
_seen = set(); upcoming = [u for u in upcoming if not ((u["name"].lower(), u["date"]) in _seen or _seen.add((u["name"].lower(), u["date"])))]
EVUP = _j("eventor_upcoming.json", None)
if EVUP is not None:
    upcoming = [{"id": 0, "eo": u["eid"], "name": clean_name(u["name"]), "date": u["date"], "big": 1 if EVBIG.get(u["eid"], {}).get("big") else 0}
                for u in EVUP if (u["ages"] >= 2 or u["cls"] == 1) and not TRAINING.search(u["name"]) and not OTHER_SPORT.search(u["name"])]
    _seen = set(); upcoming = [u for u in upcoming if not ((u["name"].lower(), u["date"]) in _seen or _seen.add((u["name"].lower(), u["date"])))]
print("upcoming races", len(upcoming))
# entries (Eventor): which pool runners have entered which upcoming race, matched like results (name, club, sex)
entered = collections.defaultdict(list)
_upix = {}
for i, u in enumerate(upcoming):
    if u.get("eo"): _upix.setdefault(u["eo"], []).append(i)
pset0 = set(pool)
# Eventor's club name is not always the one in the result lists ("IFK Göteborg" / "IFK Göteborg Orientering"),
# so a name and sex that fit exactly one runner in the pool is enough
_byname = collections.defaultdict(list)
for k in pool: _byname[(k.split("|")[0], k.rsplit("|", 1)[1])].append(k)
_miss = []
for en in _j("eventor_entries.json", []):
    k = rkey({"name": en["name"], "club": en["club"]}, {"g": en["cls"][0]})
    if k not in pset0:
        c = _byname.get((en["name"].strip().lower(), en["cls"][0]), [])
        if len(c) != 1: _miss.append((en["name"], en["club"], en["cls"])); continue
        k = c[0]
    for i in _upix.get(en["eid"], []):
        if i not in entered[k]: entered[k].append(i)
print("pool runners with entries", len(entered), "entries not matched to a pool runner", len(_miss), _miss[:15])
json.dump({"entered": entered, "upcoming": upcoming, "events": [{k: v for k, v in e.items() if k not in ("rows", "fin", "d")} for e in events],
           "rounds": rounds, "pool": pool,
           "names": {k: names[k].most_common(1)[0][0] for k in pool},
           "clubs": {k: pick_club(clubs[k]) for k in pool},
           "cls": CLS, "alias": ALIAS,
           "starts": {k: starts[k] for k in pool}, "strength": {k: round(STR.get(k, 0.05), 3) for k in pool},
           "prices": price_by_round}, open(f"{S}/data/dataset_full.json", "w"), ensure_ascii=False)
pset = set(pool)
tot = collections.Counter()
for r in rounds:
    for eid in r["events"]:
        e = next(x for x in events if x["id"] == eid)
        for k, s in e["scores"].items():
            if k in pset: tot[k] += s["pts"]
print("league mean pts/start", round(league_mean, 2))
for k, v in tot.most_common(10):
    print(f"  {names[k].most_common(1)[0][0]:26s} {CLS[k]} starts={starts[k]:2d} pts={v:6.1f}")
