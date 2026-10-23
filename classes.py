import json, sys, urllib.request, concurrent.futures as cf, time, re
S = sys.argv[1]
comps = json.load(open(f"{S}/data/comps_clean.json"))
sel = [c for c in comps if "2026-03-01" <= c["date"] <= "2026-12-31"]
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
out = {}
t=time.time()
with cf.ThreadPoolExecutor(12) as ex:
    for cid, cl in ex.map(get, sel):
        out[cid] = cl
print("secs", round(time.time()-t))
json.dump(out, open(f"{S}/data/classes.json", "w"), ensure_ascii=False)
print("failed", sum(1 for v in out.values() if v is None), "empty", sum(1 for v in out.values() if v == []))
def isH16(n): return re.sub(r"[\s_-]", "", n.upper()) in ("H16","M16","H16A","H16K")
h16 = [c for c in sel if out.get(c["id"]) and any(isH16(x) for x in out[c["id"]])]
print("with H16:", len(h16))
json.dump(h16, open(f"{S}/data/h16_comps.json", "w"), ensure_ascii=False)
# variants of class names containing 16
from collections import Counter
cnt = Counter(x for v in out.values() if v for x in v if re.search(r"(^|\W)(H|M|P|HD|HE)?\s*-?16($|\W)", x.upper()) or "H16" in x.upper())
print(cnt.most_common(30))
