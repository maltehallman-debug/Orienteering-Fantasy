# One-off probe of the Eventor API: prints the SHAPE of what comes back (tag paths, counts, a few public values like
# event names and dates). Never prints the key, and never prints anything under a Person element.
import os, sys, urllib.request, urllib.parse, collections, datetime as dt, xml.etree.ElementTree as ET
KEY = os.environ.get("EVENTOR_API_KEY", "").strip()
if not KEY: print("no key in the environment"); sys.exit(1)
BASE = "https://eventor.orientering.se/api/"
def get(path, **q):
    url = BASE + path + ("?" + urllib.parse.urlencode(q) if q else "")
    req = urllib.request.Request(url, headers={"ApiKey": KEY, "Accept": "application/xml"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r: body = r.read()
        print(f"\n== {path} {q} -> {r.status}, {len(body)} bytes")
        return ET.fromstring(body)
    except urllib.error.HTTPError as e:
        print(f"\n== {path} {q} -> HTTP {e.code}"); return None
    except Exception as e:
        print(f"\n== {path} {q} -> {type(e).__name__}"); return None
def strip(t): return t.split("}", 1)[-1]
SHOW = {"Name", "ShortName", "Date", "Clock", "EventClassificationId", "EventStatusId", "DisciplineId", "EventId", "EventRaceId",
        "Time", "TimeBehind", "TimeDiff", "Position", "ResultPosition", "Status", "CompetitorStatus", "Leg", "ClassShortName",
        "StartDate", "FinishDate", "OrganisationId", "CountryId", "Alpha3", "EventClassId", "ClassTypeId", "Id", "StartTime", "FinishTime", "LegOrder", "BibNumber"}
def dump(root, maxpaths=90):
    if root is None: return
    cnt = collections.Counter(); attrs = collections.defaultdict(set); ex = {}
    def walk(e, path, inperson):
        tag = strip(e.tag); p = path + "/" + tag; cnt[p] += 1
        person = inperson or tag in ("Person", "PersonName")
        for a, v in e.attrib.items(): attrs[p].add(f"{strip(a)}={v[:25]}" if not person else strip(a))
        txt = (e.text or "").strip()
        if txt and tag in SHOW and not person and p not in ex: ex[p] = txt[:60]
        for c in e: walk(c, p, person)
    walk(root, "", False)
    for p, n in list(cnt.items())[:maxpaths]:
        a = sorted(attrs[p])[:6]
        print(f"  {n:5d} {p}" + (f"  @{a}" if a else "") + (f"  e.g. {ex[p]!r}" if p in ex else ""))
    if len(cnt) > maxpaths: print(f"  ... {len(cnt) - maxpaths} more paths")
def kids(e, name): return [c for c in e if strip(c.tag) == name]
def find(e, name):
    for c in e.iter():
        if strip(c.tag) == name: return c
def txt(e, name):
    f = find(e, name); return (f.text or "").strip() if f is not None and f.text else ""

dump(get("organisation/apiKey"))
today = dt.date.today()
ev = get("events", fromDate="2026-08-01", toDate=(today + dt.timedelta(days=21)).isoformat(), classificationIds="1,2,3,4")
dump(ev, 70)
evs = [e for e in ev if strip(e.tag) == "Event"] if ev is not None else []
print("events:", len(evs))
byc = collections.Counter((txt(e, "EventClassificationId"), e.attrib.get("eventForm", "?"), txt(e, "DisciplineId")) for e in evs)
print("by classification / form / discipline:", byc.most_common(20))
def date_of(e):
    s = find(e, "StartDate"); return txt(s, "Date") if s is not None else ""
past = [e for e in evs if date_of(e) and date_of(e) < today.isoformat()]
fut = [e for e in evs if date_of(e) and date_of(e) >= today.isoformat()]
for e in past[-6:] + fut[:6]: print("  ", date_of(e), txt(e, "EventClassificationId"), e.attrib.get("eventForm"), txt(e, "EventId"), txt(e, "Name"))
def pick(lst, cond):
    for e in reversed(lst):
        if cond(e): return e
ind = pick(past, lambda e: txt(e, "EventClassificationId") in ("1", "2") and "Ind" in e.attrib.get("eventForm", "") and "Multi" not in e.attrib.get("eventForm", ""))
rel = pick(past, lambda e: "Relay" in e.attrib.get("eventForm", ""))
mul = pick(past, lambda e: "Multi" in e.attrib.get("eventForm", ""))
for label, e in (("INDIVIDUAL", ind), ("RELAY", rel), ("MULTIDAY", mul)):
    if e is None: print("no", label); continue
    print(f"\n#### {label}: {date_of(e)} {txt(e, 'Name')}")
    r = get("results/event/iofxml", eventId=txt(e, "EventId"), includeSplitTimes="false")
    dump(r, 60)
    if r is not None:
        cls = [txt(c, "ShortName") or txt(c, "Name") for c in r.iter() if strip(c.tag) == "Class"]
        print("  classes:", cls[:40])
up = next((e for e in fut if txt(e, "EventClassificationId") in ("1", "2", "3")), fut[0] if fut else None)
if up is not None:
    print(f"\n#### UPCOMING: {date_of(up)} {txt(up, 'Name')}")
    dump(get("entries", eventIds=txt(up, "EventId"), includePersonElement="true", includeOrganisationElement="true", includeEventElement="false"), 50)
    dump(get("eventclasses", eventId=txt(up, "EventId")), 30)
