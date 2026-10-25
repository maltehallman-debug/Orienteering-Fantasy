# Sends each live round's lock time (the evening before its week's first big race) to the database, where
# round_open() uses it to close the round. Runs in the nightly job with ROUND_SYNC_KEY from a GitHub Actions secret;
# the key is only ever sent in the request body and is never printed or written out. The database only moves rounds
# that are still open, and never to a time that has passed.
import json, os, sys, urllib.request, urllib.error
S = sys.argv[1]
KEY = os.environ.get("ROUND_SYNC_KEY", "").strip()
if not KEY:
    print("round locks: no key, skipped"); sys.exit(0)
SB_URL = "https://hjpfmubvpvftxyyemltn.supabase.co"; SB_KEY = "sb_publishable_Ent2RuVrh-iKyjT1or8gOw_UFdZ74ch"   # the page's public key
D = json.load(open(f"{S}/build/data.json", encoding="utf-8"))
locks = [{"round": i, "locks_at": r["lock"]} for i, r in enumerate(D["rounds"]) if r.get("lock") and i >= D["liveStart"]]
try:
    rq = urllib.request.Request(SB_URL + "/rest/v1/rpc/sync_round_locks", data=json.dumps({"k": KEY, "locks": locks}).encode(),
                                headers={"apikey": SB_KEY, "Authorization": "Bearer " + SB_KEY, "Content-Type": "application/json"}, method="POST")
    n = json.loads(urllib.request.urlopen(rq, timeout=30).read())
    print("round locks: sent", len(locks), "changed", n)
except urllib.error.HTTPError as e:
    print("round locks: refused", e.code)
except Exception as e:
    print("round locks: failed", type(e).__name__)
