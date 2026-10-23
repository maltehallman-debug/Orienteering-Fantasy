import json, sys, os, re, datetime as _dt
from datetime import date as dt_date
S = sys.argv[1]
D = json.load(open(f"{S}/data/dataset_full.json"))
events = D["events"]; pool = D["pool"]; ridx = {k: i for i, k in enumerate(pool)}
rounds = D["rounds"]
ev_round = {}
for r in rounds:
    for eid in r["events"]: ev_round[eid] = r["n"] - 1
KIND = {"F": 0, "DNF": 1, "MP": 2, "DSQ": 3}
# race points are scaled so a good week is about 100 and rounded to whole points (stored in tenths like everything else)
PSCALE = 0.32
out_events = []; res = []; evpos = {}
for i, e in enumerate(events):
    evpos[e["id"]] = i
    out_events.append({"name": e["name"], "date": e["date"], "tier": e["tier"], "n": e["n"], "c": e["cls"], "lr": int(m.group()) if (m := re.match(r"\d+", str(e["id"]))) else 0})
    rows = []
    for k, s in e["scores"].items():
        if k not in ridx: continue
        rows.append([ridx[k], KIND[s["k"]], s.get("rank", 0), s.get("t", 0), int(round(s.get("gap", 0) * 10000)), int(round(s["pts"] * PSCALE)) * 10, s.get("topb", 0)])
    rows.sort(key=lambda x: (x[1] != 0, x[2] if x[1] == 0 else 0, -x[5]))
    res.append(rows)
from zoneinfo import ZoneInfo
_STO = ZoneInfo("Europe/Stockholm")
def lock_at(start):  # Wednesday 20:00 Swedish time before a round that starts on Thursday
    d = dt_date.fromisoformat(start) - _dt.timedelta(days=1)
    return _dt.datetime(d.year, d.month, d.day, 20, 0, tzinfo=_STO).isoformat()
out_rounds = [{"n": r["n"], "start": r["start"], "end": r["end"], "lock": lock_at(r["start"]), "ev": [evpos[x] for x in r["events"]], "final": 1 if r["final"] else 0} for r in rounds]
prices = [[int(round(p[k] * 10)) for k in pool] for p in D["prices"]]
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
if os.path.exists(_mp):
    manual = [dict(m, id=0, manual=1) for m in json.load(open(_mp)) if m["date"] >= ASOF]
upcoming = sorted([u for u in D["upcoming"] if not any(m["date"] == u["date"] and m["name"].lower() == u["name"].lower() for m in manual)] + manual, key=lambda u: (u["date"], u["name"]))
LIVE_START_DATE = "2026-11-05"  # first live round: Thursday 5 to Wednesday 11 November, locks Wednesday 4 November 20:00
live_start = next(i for i, r in enumerate(out_rounds) if r["start"] == LIVE_START_DATE)
data = {"runners": runners, "events": out_events, "rounds": out_rounds, "res": res, "prices": prices,
        "asof": ASOF, "upcoming": [dict({"name": u["name"], "date": u["date"]}, **({"lr": u["id"]} if u.get("id") else {})) for u in upcoming], "liveStart": live_start,
        # money is in tenths of a thousand (205 = 20.5k); ten runners, the first five are the A team and score double
        "budget": 1000, "squad": 10, "aSize": 5, "clubMax": 3, "freeTransfers": 3, "penalty": 40, "dnfPts": -30,
        # price tiers (lower bounds): gold from 17.5k (about the top 8 in a class), silver from 10k; the rest is bronze
        "tiers": [175, 100]}
json.dump(data, open(f"{S}/build/data.json", "w"), ensure_ascii=False, separators=(",", ":"))
print("runners", len(runners), "events", len(out_events), "rounds", len(out_rounds), "bytes", os.path.getsize(f"{S}/build/data.json"), "upcoming", len(upcoming))
