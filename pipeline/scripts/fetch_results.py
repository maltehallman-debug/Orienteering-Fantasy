import json, sys, urllib.request, urllib.parse, concurrent.futures as cf, time, re, os, datetime as dt
S = sys.argv[1]
comps = {c["id"]: c for c in json.load(open(f"{S}/data/comps_clean.json"))}
classes = json.load(open(f"{S}/data/classes.json"))
def norm(n): return re.sub(r"[\s_-]", "", n.upper())
PAT = re.compile(r"^[DH](15|16|18|20|21)(E|ELIT|A|B|K|KORT|L|LÅNG|LANG|ELITE)?$")
# split classes: relay legs ("H21-1", "H21-2", ...), heats ("D16-1", "D16-2" at 25mannamedeln) and stages
PART = re.compile(r"^\s*[DH]\s*(15|16|18|20|21)\s*-?\s*(E|ELIT|ELITE)?\s*-\s*[1-9]\s*$", re.I)
jobs = []
TODAY = dt.date.today().isoformat()
FRESH = (dt.date.today() - dt.timedelta(days=3)).isoformat()   # results this recent may still change, so refetch them
for cid, names in classes.items():
    if comps.get(int(cid), {}).get("date", "9999") > TODAY: continue
    for n in names or []:
        if PAT.match(norm(n)) or PART.match(n):
            jobs.append((int(cid), n))
print("jobs", len(jobs))
def get(job):
    cid, cn = job
    path = f"{S}/data/results/{cid}__{norm(cn)}.json"
    if os.path.exists(path) and comps[cid]["date"] < FRESH: return cid, "cached"
    if norm(cn) == "H16" and os.path.exists(f"{S}/data/results/{cid}.json"): return cid, "cached"
    url = f"https://liveresultat.orientering.se/api.php?method=getclassresults&comp={cid}&class={urllib.parse.quote(cn)}&unformattedTimes=true"
    for i in range(3):
        try:
            raw = urllib.request.urlopen(url, timeout=40).read().decode("utf-8", "replace")
            j = json.loads(raw)
            rows = [{"place": r.get("place"), "name": r.get("name"), "club": r.get("club"), "result": r.get("result"),
                     "status": r.get("status"), "timeplus": r.get("timeplus"), "progress": r.get("progress")} for r in j.get("results", [])]
            json.dump({"id": cid, "className": cn, "rows": rows}, open(path, "w"), ensure_ascii=False)
            return cid, len(rows)
        except Exception as e:
            err = str(e)[:80]; time.sleep(1.5)
    return cid, "ERR " + err
t = time.time(); res = {}
with cf.ThreadPoolExecutor(24) as ex:
    for job, (cid, r) in zip(jobs, ex.map(get, jobs)): res[job] = r
print("secs", round(time.time()-t))
errs = {k: v for k, v in res.items() if isinstance(v, str) and v.startswith("ERR")}
print("errors", len(errs), list(errs.items())[:5])
print("nonempty", sum(1 for v in res.values() if isinstance(v, int) and v > 0))
