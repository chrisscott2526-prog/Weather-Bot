"""Weather-Bot: OddsPapi probe (read-only) -- ROUND 4, the last one
before the lane (Sep 15 2026).

ANSWERED so far (runs 1-3, Sep 15 2026 -- full notes in each run's
log and the CLAUDE.md session record):
- auth apiKey param; base https://api.oddspapi.io/v4
- sports: basketball=11, tennis=12, baseball=13, american-football=14
- NFL tournamentId=31; fixtures carry names/Abbr/startTime/hasOdds
  and honor from/to date filters (unfiltered = 844 rows of history)
- odds?fixtureId works; markets keyed by NUMERIC ids; /v4/markets is
  the dictionary (33,115 entries) and carries marketType -- the
  2-way winner-incl-overtime type is tagged "moneyline"
- BULK: odds-by-tournaments?tournamentIds=X&bookmaker=<slug> -- ONE
  bookmaker per call, ~1 req/sec rate limit (429 with retryMs)

ROUND 4 questions (the lane's last unknowns):
1. The moneyline marketIds for american-football (14) and baseball
   (13) from the dictionary, with their outcome ids.
2. MLB's tournamentId (tournaments?sportId=13).
3. Does the FREE subscription serve sharp books through the bulk
   endpoint -- pinnacle, and a second sharp (singbet / 3et)?

Honesty rules unchanged: no key or URL in output; empty-secret scar
check first; a handful of requests, ~1.2s apart for the rate limit.
"""

import json, os, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone

KEY = os.environ.get("ODDSPAPI_KEY", "").strip()
if not KEY:
    sys.exit("ODDSPAPI_KEY is MISSING or EMPTY -- refusing to probe "
             "(the Aug 19 2026 empty-secret scar).")

BASE = "https://api.oddspapi.io/v4"


def get(path, **params):
    params["apiKey"] = KEY
    url = f"{BASE}/{path}?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers={"User-Agent":
                                     "weather-bot-research-probe"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8", "replace"))
        except Exception:
            body = "<unparseable body>"
        return e.code, body
    except Exception as e:
        return None, f"<request failed: {e}>"


def main():
    # 1. Moneyline dictionary entries for our sports (one request).
    st, markets = get("markets")
    if st != 200 or not isinstance(markets, list):
        sys.exit(f"markets fetch failed: HTTP {st} {str(markets)[:300]}")
    for sid, name in ((14, "american-football"), (13, "baseball"),
                      (11, "basketball"), (12, "tennis")):
        ml = [m for m in markets
              if m.get("sportId") == sid
              and m.get("marketType") == "moneyline"
              and not m.get("playerProp")]
        print("=" * 55)
        print(f"{name} (sportId {sid}): {len(ml)} moneyline markets:")
        print(json.dumps(ml, indent=1)[:2500])

    # 2. MLB tournament id.
    time.sleep(1.2)
    st, tours = get("tournaments", sportId=13)
    if st == 200 and isinstance(tours, list):
        mlb = [t for t in tours
               if "MLB" in str(t.get("tournamentName", "")).upper()
               or t.get("tournamentSlug") == "mlb"]
        print("=" * 55)
        print(f"baseball tournaments: {len(tours)}; MLB-matching:")
        print(json.dumps(mlb[:5], indent=1)[:1500])
    else:
        print("=" * 55)
        print(f"tournaments?sportId=13 -> HTTP {st}: {str(tours)[:400]}")

    # 3. Sharp books through the bulk endpoint on the free tier.
    for slug in ("pinnacle", "singbet", "3et"):
        time.sleep(1.5)
        st, bulk = get("odds-by-tournaments", tournamentIds=31,
                       bookmaker=slug)
        text = json.dumps(bulk) if not isinstance(bulk, str) else bulk
        print("=" * 55)
        print(f"odds-by-tournaments NFL bookmaker={slug} -> HTTP {st}; "
              f"{len(text)} chars")
        if st == 200:
            if isinstance(bulk, list):
                print(f"list of {len(bulk)} fixtures; first, truncated:")
                print(json.dumps(bulk[0], indent=1)[:2000] if bulk
                      else "[]")
            else:
                print(text[:2000])
        else:
            print(text[:600])

    print("=" * 55)
    print("Round 4 done (read-only; ~6 requests).")


if __name__ == "__main__":
    main()
