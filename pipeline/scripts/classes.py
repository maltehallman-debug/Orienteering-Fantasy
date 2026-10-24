import json, sys, urllib.request, concurrent.futures as cf, time, re
S = sys.argv[1]
comps = json.load(open(f"{S}/data/comps_clean.json"))
import os, datetime as dt
old = {}
try: old = json.load(open(f"{S}/data/classes.json"))
except Exception: pass
keep_before = (dt.date.today() - dt.timedelta(days=3)).isoformat()
allsel = [c for c in comps if "2026-03-01" <= c["date"] <= "2027-10-31"]
# a competition more than three days old keeps the class list it had (liveresultat is only asked about new ones)
sel = [c for c in allsel if not (c["date"] < keep_before and old.get(str(c["id"])))]
def get(c):
    url = f"https://liveresultat.orientering.se/api.php?method=getclasses&comp={c['id']}"
    for i in range(3):
        try:
            r = urllib.request.urlopen(url, timeout=25).read().decode("utf-8", "replace")
            names = re.findall(r'"className":\s*"(.*?)"\s*[,}]', r)
            return c["id"], names
        except Exception as e:
            time.sleep(1)
    return c["id"], None
out = {str(c["id"]): old[str(c["id"])] for c in allsel if c not in sel and old.get(str(c["id"]))}
t=time.time()
with cf.ThreadPoolExecutor(12) as ex:
    for cid, cl in ex.map(get, sel):
        out[cid] = cl
print("secs", round(time.time()-t))
json.dump(out, open(f"{S}/data/classes.json", "w"), ensure_ascii=False)
print("failed", sum(1 for v in out.values() if v is None), "empty", sum(1 for v in out.values() if v == []))
