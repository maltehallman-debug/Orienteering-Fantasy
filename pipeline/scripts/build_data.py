import json, sys, os, re, datetime as _dt
S = sys.argv[1]
D = json.load(open(f"{S}/data/dataset_full.json"))
events = D["events"]; pool = D["pool"]; ridx = {k: i for i, k in enumerate(pool)}
rounds = D["rounds"]
ev_round = {}
for r in rounds:
    for eid in r["events"]: ev_round[eid] = r["n"] - 1
KIND = {"F": 0, "DNF": 1, "MP": 2, "DSQ": 3}
# race points are scaled so one runner's really good week is about 10 and rounded to whole points (stored in tenths
# like everything else). A finish is always worth at least 1; a mispunch, DNF or DSQ is -1.
PSCALE = 0.11
def game_pts(s): return max(1, round(s["pts"] * PSCALE)) if s["k"] == "F" else round(s["pts"] * PSCALE)
out_events = []; res = []; evpos = {}
for i, e in enumerate(events):
    evpos[e["id"]] = i
    lr = int(m.group()) if (m := re.match(r"\d+", str(e["id"]))) else 0
    # results from Eventor link to the event in Eventor, results from liveresultat to liveresultat
    out_events.append({"name": e["name"], "date": e["date"], "tier": e["tier"], "n": e["n"], "c": e["cls"], **({"eo": e["eo"]} if e.get("eo") else {"lr": lr if lr < 9_000_000 else 0})})
    rows = []
    for k, s in e["scores"].items():
        if k not in ridx: continue
        rows.append([ridx[k], KIND[s["k"]], s.get("rank", 0), s.get("t", 0), int(round(s.get("gap", 0) * 10000)), game_pts(s) * 10, s.get("topb", 0)])
    rows.sort(key=lambda x: (x[1] != 0, x[2] if x[1] == 0 else 0, -x[5]))
    res.append(rows)
out_rounds = [{"n": r["n"], "start": r["start"], "end": r["end"], "ev": [evpos[x] for x in r["events"]], "final": 1 if r["final"] else 0,
               **({"skip": 1} if r.get("skip") else {}), **({"big": r["big"]} if r.get("big") is not None else {}),
               **({"pending": 1} if r.get("pending") else {}), **({"forced": r["forced"]} if r.get("forced") else {}),
               **({"beta": 1} if r.get("beta") else {}), **({"launch": 1} if r.get("launch") else {}), **({"wait": 1} if r.get("wait") else {}),
               **({"no": r["no"]} if r.get("no") is not None else {}), **({"pre": 1} if r.get("pre") else {}), **({"lock": r["lock"]} if r.get("lock") else {})} for r in rounds]
# prices only change with new results: rounds ahead all have today's prices, so only up to the next round is sent
_upto = next((i for i, r in enumerate(rounds) if r["start"] > _dt.date.today().isoformat()), len(rounds) - 1) + 1
prices = [[int(round(p[k] * 10)) for k in pool] for p in D["prices"][:max(1, _upto)]]
runners = [{"n": D["names"][k], "c": D["clubs"][k], "p": 1, "s": int(round(D["strength"].get(k, 0.05) * 100)), "k": D["cls"][k], "id": k} for k in pool]
# runner photos: photos.json maps a runner id ("name|H" or "name|D") to a file in data/photos, embedded so the page stays one file
import base64
_pp = f"{S}/data/photos.json"
if os.path.exists(_pp):
    _ix = {r["id"]: r for r in runners}
    # an old "name|H" key still works when exactly one runner has that name
    _legacy = {}
    for r in runners:
        n, *_, g = r["id"].split("|"); _legacy.setdefault(f"{n}|{g}", []).append(r["id"])
    for rid, fn in json.load(open(_pp, encoding="utf-8")).items():
        if rid not in _ix and len(_legacy.get(rid, [])) == 1: rid = _legacy[rid][0]
        if rid in _ix and os.path.exists(f"{S}/data/photos/{fn}"):
            _ix[rid]["ph"] = "data:image/jpeg;base64," + base64.b64encode(open(f"{S}/data/photos/{fn}", "rb").read()).decode()
        else:
            print("photo not used:", rid, fn)
ASOF = _dt.date.today().isoformat()
manual = []
_mp = f"{S}/data/manual_events.json"
# hand-entered races fill gaps on liveresultat; once Eventor's race list is in, it is the full schedule
if os.path.exists(_mp) and not any(u.get("eo") for u in D["upcoming"]):
    manual = [dict(m, id=0, manual=1) for m in json.load(open(_mp)) if m["date"] >= ASOF]
upcoming = sorted([u for u in D["upcoming"] if not any(m["date"] == u["date"] and m["name"].lower() == u["name"].lower() for m in manual)] + manual, key=lambda u: (u["date"], u["name"]))
# entries point at races in D["upcoming"]; that list is re-sorted here with manual races, so map them by identity
_old = D["upcoming"]; _pos = {id(u): i for i, u in enumerate(upcoming)}
entered = {}
for k, ixs in D.get("entered", {}).items():
    if k in ridx:
        js = sorted(_pos[id(_old[i])] for i in ixs if i < len(_old) and id(_old[i]) in _pos)
        if js: entered[str(ridx[k])] = js
LIVE_START_DATE = "2026-11-02"
live_start = next(i for i, r in enumerate(out_rounds) if r["start"] == LIVE_START_DATE)
data = {"runners": runners, "events": out_events, "rounds": out_rounds, "res": res, "prices": prices,
        "asof": ASOF, "upcoming": [dict({"name": u["name"], "date": u["date"]}, **({"lr": u["id"]} if u.get("id") else {}), **({"eo": u["eo"]} if u.get("eo") else {}), **({"big": 1} if u.get("big") else {})) for u in upcoming], "liveStart": live_start,
        # runner index -> the upcoming races (indexes into "upcoming") they have entered in Eventor
        "entered": entered,
        # set when the nightly job ran without Eventor: weeks, locks and big races are then judged from liveresultat
        **({"noEventor": 1} if D.get("noEventor") else {}),
        # the official launch: Sverigepremiären's dates (from Eventor when it has them)
        "launch": {k: v for k, v in (json.load(open(f"{S}/data/eventor/launch.json")) if os.path.exists(f"{S}/data/eventor/launch.json") else {"name": "Sverigepremiären", "dates": ["2027-03-05", "2027-03-06", "2027-03-07"], "guess": True}).items() if k in ("name", "dates", "guess")},
        # old runner keys (a joint relay club used to count as a club) -> runner index, so saved squads still load
        "alias": {a: ridx[k] for a, k in D.get("alias", {}).items() if k in ridx},
        # money is in tenths of a thousand (205 = 20.5k); ten runners, the first five are the A team and score double
        "budget": 1000, "squad": 10, "aSize": 5, "clubMax": 3, "freeTransfers": 2, "penalty": 70, "dnfPts": -30,
        # price tiers (lower bounds): gold from 17.5k (about the top 8 in a class), silver from 10k; the rest is bronze
        "tiers": [175, 100]}
json.dump(data, open(f"{S}/build/data.json", "w"), ensure_ascii=False, separators=(",", ":"))
print("runners", len(runners), "events", len(out_events), "rounds", len(out_rounds), "bytes", os.path.getsize(f"{S}/build/data.json"), "upcoming", len(upcoming))
