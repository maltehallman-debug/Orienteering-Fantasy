"""Birth years and club countries from O-Ringen's public results (resultat.oringen.se).

O-Ringen lists every runner's birth year and their club's country. That settles two things the other result lists
cannot: a junior's exact age class (D16 is 15 and 16, so only the 16-year-olds move up at new year) and whether a club
is outside Sweden. One request per stage and year, for the game's classes only; finished years are kept and never
asked for again, this year's copy is refreshed at most once a week.
Writes data/oringen_people.json: [{"n": name, "g": "D"/"H", "c": club, "b": birth year, "cc": club country, "y": year}]
"""
import json, os, re, sys, time, urllib.request, datetime as dt

S = sys.argv[1]
C = f"{S}/data/oringen"; os.makedirs(C, exist_ok=True)
API = "https://resultat.oringen.se/api"
UA = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
YEARS = range(dt.date.today().year - 5, dt.date.today().year + 1)
# the classes worth reading: youth classes with single years (10-16), juniors and seniors; not motion or open classes
WANT = re.compile(r"^[DH](1[0-9]|2[01])(\s|$|-)")

def get(url):
    for k in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r: return json.load(r)
        except Exception as e:
            err = e; time.sleep(2 + 3 * k)
    print("oringen: not reached", url, err); return None

people = []
for y in YEARS:
    path = f"{C}/{y}.json"
    fresh = os.path.exists(path) and (y < dt.date.today().year or time.time() - os.path.getmtime(path) < 7 * 86400)
    if fresh:
        rows = json.load(open(path))
    else:
        ev = get(f"{API}/events/slugs/{y}")
        if not ev or not ev.get("c"): print("oringen: no event for", y); continue
        cls = [c for c in ev["c"] if WANT.match(c.get("n", ""))]
        rows, seen = [], set()
        for race in sorted(ev.get("r", []), key=lambda r: r.get("rn", 0))[:2]:   # the first two stages cover nearly everyone
            ids = [str(c["i"]) for c in cls if any(cr.get("r") == race["i"] for cr in c.get("r", []))]
            for i in range(0, len(ids), 25):
                res = get(f"{API}/races/{race['i']}/classes/results/json?classIds={','.join(ids[i:i + 25])}") or []
                cname = {c["i"]: c["n"] for c in cls}
                for x in res:
                    p, o = x.get("p") or {}, x.get("o") or {}
                    n = f"{p.get('f', '')} {p.get('l', '')}".strip(); b = p.get("b")
                    cn = cname.get((x.get("c") or {}).get("i"), "")
                    if not n or not b or not cn: continue
                    key = (n.lower(), cn[0], o.get("n", ""))
                    if key in seen: continue
                    seen.add(key); rows.append({"n": n, "g": cn[0], "c": o.get("n", ""), "b": int(b), "cc": o.get("c", ""), "cl": cn, "y": y})
                time.sleep(1)
        if rows: json.dump(rows, open(path, "w"), ensure_ascii=False)
    people += rows
    print("oringen", y, len(rows), "runners")
json.dump(people, open(f"{S}/data/oringen_people.json", "w"), ensure_ascii=False)
print("oringen people", len(people))
