import json, glob, collections, re, datetime as dt, math, sys, os, bisect
import numpy as np
S = sys.argv[1]
comps = {c["id"]: c for c in json.load(open(f"{S}/data/comps_clean.json"))}
MIN_FIN = 3
EXCLUDE = {36940, 36892, 40850, 37141, 37143, 40373}   # aggregates, chase duplicates, patrol, some foreign pilots
SEASON_START = dt.date(2026, 5, 4)
TODAY = dt.date.today()
LAST_ROUND_START = dt.date(2026, 12, 21)
def norm(n): return re.sub(r"[\s_-]", "", n.upper())
def _pos(x):
    try: return int(x) > 0
    except Exception: return False
def finished(r): return r["status"] == 0 and _pos(r["result"])
def started(r): return finished(r) or r["status"] in (2, 3, 4)
def monday(d): return d - dt.timedelta(days=d.weekday())
def tier_of(c):
    n = c["name"].lower()
    if "ungdoms-sm" in n: return 1.4
    if ("swedish league" in n or n.startswith("dm") or n.startswith("gm,") or "mästerskapen" in n
            or "unionsmatchen" in n or "jwoc" in n or "publiktävling sm" in n or "wcs spec" in n or "woc spect" in n):
        return 1.2
    return 1.0
# Only real competitions count: proper H/D16-21 classes (plain or elite, not K/A/B/short variants),
# no other sports, no club-internal or training races, and at least two of the four age groups
# unless it is a championship (Ungdoms-SM and Unionsmatchen only have 16).
REAL = re.compile(r"^([DH])(16|18|20|21)(E|ELIT|ELITE)?$")
OTHER_SPORT = re.compile(r"mtbo|mtb-o|ol-skytte|skidorient|\bvtt\b|trail-?o\b|precision", re.I)
TRAINING = re.compile(r"\bkm\b|klubbmästerskap|klubbmatch|träning|^test\b|\btest \d|fasttest|testløb|ungdomsserie|u-serie|u-ringen|totalresultat", re.I)
_cl = json.load(open(f"{S}/data/classes.json"))
def real_comp(c):
    if not c["name"].strip() or OTHER_SPORT.search(c["name"]) or TRAINING.search(c["name"]): return False
    ages = {REAL.match(norm(n)).group(2) for n in (_cl.get(str(c["id"])) or []) if REAL.match(norm(n))}
    return len(ages) >= 2 or (len(ages) >= 1 and tier_of(c) > 1)

events = []
seen_ek = set()
for p in glob.glob(f"{S}/data/results/*.json"):
    j = json.load(open(p))
    cid = j["id"]; cn = norm(j.get("className", "H16"))
    if cid in EXCLUDE or cid not in comps: continue
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
    g, age = m.group(1), m.group(2)
    events.append({"id": ek, "cid": cid, "name": f'{c["name"].strip()} ({g}{age})', "date": c["date"], "d": d, "tier": tier_of(c),
                   "g": g, "cls": g + age, "rows": rows, "fin": fin})
events.sort(key=lambda e: (e["date"], e["id"]))
print("counted event-classes", len(events))
rkey = lambda r, e: r["name"].strip().lower() + "|" + e["g"]

# ---- strength ratings (field-adjusted log-time model), vectorised ----
keys_all = sorted({rkey(r, e) for e in events for r in e["fin"]})
kix = {k: i for i, k in enumerate(keys_all)}
ev_i, run_i, perf = [], [], []
for ei, e in enumerate(events):
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
def score_event(e):
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
    e["scores"] = score_event(e); e["n"] = len(e["fin"])

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
    return (nondist or cn.most_common())[0][0]
starts = {k: len(series[k]) for k in names}
POOL_MIN = 3
pool = sorted([k for k in names if starts[k] >= POOL_MIN], key=lambda k: (names[k].most_common(1)[0][0], k))
print("runners total", len(names), "pool", len(pool))

# ---- rounds ----
rounds = []
wk = SEASON_START; i = 0
while wk <= LAST_ROUND_START:
    ids = [e["id"] for e in events if monday(e["d"]) == wk]
    end = wk + dt.timedelta(days=6)
    rounds.append({"n": i + 1, "start": wk.isoformat(), "end": end.isoformat(), "events": ids, "final": end < TODAY})
    wk += dt.timedelta(days=7); i += 1
print("rounds", len(rounds), [len(r["events"]) for r in rounds])

# ---- prices ----
PEXP = float(os.environ.get("PEXP", "2.0"))
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
    order = sorted(ratings, key=lambda k: ratings[k])
    n = len(order)
    return {k: round(4.0 + 9.0 * ((i + 0.5) / n) ** PEXP, 1) for i, k in enumerate(order)}
price_by_round = []
for r in rounds:
    pr = prices_before(dt.date.fromisoformat(r["start"]))
    price_by_round.append({k: pr.get(k, 4.0) for k in pool})
    r["rated"] = len(pr)

hc = {int(k) for k, v in _cl.items() if v and any(REAL.match(norm(n)) for n in v)}
done_cids = {e["cid"] for e in events}
upcoming = []
for c in comps.values():
    if TODAY.isoformat() <= c["date"] <= "2026-12-31" and c["id"] in hc and c["id"] not in EXCLUDE and real_comp(c):
        upcoming.append({"id": c["id"], "name": c["name"].strip(), "date": c["date"]})
upcoming.sort(key=lambda x: (x["date"], x["id"]))
print("upcoming races", len(upcoming))
json.dump({"upcoming": upcoming, "events": [{k: v for k, v in e.items() if k not in ("rows", "fin", "d")} for e in events],
           "rounds": rounds, "pool": pool,
           "names": {k: names[k].most_common(1)[0][0] for k in pool},
           "clubs": {k: pick_club(clubs[k]) for k in pool},
           "cls": {k: clsc[k].most_common(1)[0][0] for k in pool},
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
    print(f"  {names[k].most_common(1)[0][0]:26s} {clsc[k].most_common(1)[0][0]} starts={starts[k]:2d} pts={v:6.1f}")
