import re, json, sys
S = sys.argv[1]
s = open(f"{S}/data/comps.json", encoding="utf-8", errors="replace").read()
pat = re.compile(r'\{"id":\s*(\d+),\s*"name":\s*"(.*?)",\s*"organizer":\s*"(.*?)",\s*"date":\s*"(\d{4}-\d{2}-\d{2})"(.*?)\}(?=,\{"id"|\s*\]|\s*$)', re.S)
comps = []
for m in pat.finditer(s):
    rest = m.group(5)
    md = re.search(r'"multidaystage":\s*(-?\d+)', rest)
    comps.append({"id": int(m.group(1)), "name": m.group(2), "organizer": m.group(3), "date": m.group(4),
                  "stage": int(md.group(1)) if md else None})
print("parsed", len(comps), "occurrences of id:", s.count('{"id"'))
json.dump(comps, open(f"{S}/data/comps_clean.json", "w"), ensure_ascii=False)
ds = sorted(c["date"] for c in comps)
print(ds[0], ds[-1])
sel = [c for c in comps if "2026-03-01" <= c["date"] <= "2026-10-23"]
print("selected", len(sel))
