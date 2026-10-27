# Start lists from liveresultat.orientering.se: who is set to run the races of the coming days in D/H 16-21.
# Organisers put their start list on liveresultat before the race (often the day before), and the runners show up
# there without a time yet (status 9 or 10). That is the only open source of "who is running" besides Eventor, so it
# fills in when the Eventor key is missing, and adds races Eventor does not know about when it is there.
# Writes data/lr_startlists.json: {liveresultat id: [{"name", "club", "cls"}]}. Kept light: only races in the next
# DAYS days, a few requests at a time.
import json, sys, re, time, urllib.request, urllib.parse, concurrent.futures as cf, datetime as dt
S = sys.argv[1]
DAYS = 10
comps = {c["id"]: c for c in json.load(open(f"{S}/data/comps_clean.json"))}
classes = json.load(open(f"{S}/data/classes.json"))
def norm(n): return re.sub(r"[\s_-]", "", n.upper())
PAT = re.compile(r"^[DH](15|16|18|20|21)(E|ELIT|ELITE)?$")
today = dt.date.today(); last = (today + dt.timedelta(days=DAYS)).isoformat()
jobs = [(int(cid), n) for cid, names in classes.items() for n in (names or [])
        if today.isoformat() <= comps.get(int(cid), {}).get("date", "0") <= last and PAT.match(norm(n))]
print("start list jobs", len(jobs))
def get(job):
    cid, cn = job
    url = f"https://liveresultat.orientering.se/api.php?method=getclassresults&comp={cid}&class={urllib.parse.quote(cn)}&unformattedTimes=true"
    for _ in range(3):
        try:
            j = json.loads(urllib.request.urlopen(url, timeout=30).read().decode("utf-8", "replace"))
            return cid, [{"name": r.get("name"), "club": r.get("club"), "cls": norm(cn)[:3]} for r in j.get("results", []) if r.get("name")]
        except Exception:
            time.sleep(1.5)
    return cid, None
out = {}
with cf.ThreadPoolExecutor(4) as ex:
    for cid, rows in ex.map(get, jobs):
        if rows: out.setdefault(str(cid), []).extend(rows)
json.dump(out, open(f"{S}/data/lr_startlists.json", "w"), ensure_ascii=False)
print("races with a start list", len(out), "runners", sum(len(v) for v in out.values()))
