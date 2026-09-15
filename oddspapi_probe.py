"""Weather-Bot: OddsPapi probe (read-only) -- ROUND 3 (Sep 15 2026).

Discovery only, the sports_probe / modellab_probe pattern: printed
truncated live responses teach the API's real shapes before any lane
is coded. Runs inside oddspapi_probe.yml on GitHub's runners (the
repo's sessions cannot reach oddspapi.io from their sandbox).

ANSWERED by rounds 1-2 (logs in runs 1-2, Sep 15 2026):
- auth: apiKey query param against https://api.oddspapi.io/v4
- sports: american-football=14, basketball=11, tennis=12, baseball=13
- bookmakers list carries cloneOf (clone books must not double-count
  in any consensus); account shows the subscription
- NFL tournamentId=31; fixtures carry full participant names, Abbr,
  startTime, statusName, hasOdds -- but an unfiltered
  fixtures?tournamentId=31 returns 844 rows back to 2024, so date
  filters are mandatory
- odds?fixtureId=... works: per-bookmaker -> markets (NUMERIC ids) ->
  outcomes -> players -> decimal price + priceAmerican + mainLine
- BULK EXISTS: odds-by-tournaments wants tournamentIds (plural,
  comma-separated) -- one call per league instead of per fixture

ROUND 3 questions:
1. The MARKET DICTIONARY -- which numeric marketId is the full-game
   moneyline (and which outcome id is which side)?
2. odds-by-tournaments?tournamentIds=31 -- response shape and rough
   size, and whether a bookmakers filter param narrows it.
3. fixtures with from/to date filters -- confirmed working?

Honesty rules: never prints the key or full URLs; fails RED on a
missing/empty key (the Aug 19 2026 empty-secret scar). Costs a
handful of requests per press.
"""

import json, os, sys, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone

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


def show(label, status, body, limit=2500):
    print("=" * 55)
    text = json.dumps(body) if not isinstance(body, str) else body
    size = len(text)
    print(f"{label} -> HTTP {status} ({size} chars)")
    print(text[:limit] + ("..." if size > limit else ""))


def main():
    # 1. The market dictionary -- try the plausible spellings; error
    # shapes are answers too.
    for attempt in (("markets", {}), ("markets", {"sportId": 14}),
                    ("market-types", {}), ("outcomes", {"sportId": 14})):
        path, params = attempt
        st, body = get(path, **params)
        label = f"{path}?{urllib.parse.urlencode(params)}" if params else path
        # American-football moneyline hunt: if it IS a list, show any
        # entries mentioning moneyline/winner/1x2 rather than raw head
        if st == 200 and isinstance(body, list):
            hits = [m for m in body
                    if any(k in json.dumps(m).lower()
                           for k in ("moneyline", "money line", "winner",
                                     "1x2", "match odds"))]
            print("=" * 55)
            print(f"{label} -> HTTP 200; {len(body)} entries; "
                  f"{len(hits)} mention moneyline/winner/1x2; "
                  "first 6 such:")
            print(json.dumps(hits[:6], indent=1)[:3000])
            print("...and the first 3 raw entries for shape:")
            print(json.dumps(body[:3], indent=1)[:1500])
            break
        else:
            show(label, st, body, limit=600)

    # 2. Bulk odds for the NFL -- shape + rough size; then again with
    # a guessed bookmakers filter to see if the response narrows.
    st, bulk = get("odds-by-tournaments", tournamentIds=31)
    if st == 200:
        text = json.dumps(bulk)
        print("=" * 55)
        print(f"odds-by-tournaments?tournamentIds=31 -> HTTP 200; "
              f"{len(text)} chars total")
        if isinstance(bulk, list):
            print(f"list of {len(bulk)} entries; first entry, truncated:")
            print(json.dumps(bulk[0], indent=1)[:2500] if bulk else "[]")
        elif isinstance(bulk, dict):
            print(f"dict with keys: {list(bulk.keys())[:20]}")
            print(text[:2500])
    else:
        show("odds-by-tournaments?tournamentIds=31", st, bulk)

    st, body = get("odds-by-tournaments", tournamentIds=31,
                   bookmakers="pinnacle")
    text = json.dumps(body) if not isinstance(body, str) else body
    print("=" * 55)
    print(f"odds-by-tournaments + bookmakers=pinnacle -> HTTP {st}; "
          f"{len(text)} chars (filter honored if much smaller)")
    print(text[:1200])

    # 3. fixtures with date filters -- the lane must never pull 844
    # rows of history.
    today = datetime.now(timezone.utc).date()
    st, fx = get("fixtures", tournamentId=31,
                 **{"from": today.isoformat(),
                    "to": (today + timedelta(days=3)).isoformat()})
    if st == 200 and isinstance(fx, list):
        print("=" * 55)
        print(f"fixtures?tournamentId=31&from={today}&to=+3d -> "
              f"HTTP 200; {len(fx)} fixtures:")
        for f in fx[:10]:
            print(f"  {f.get('startTime')}  "
                  f"{f.get('participant1Name')} vs "
                  f"{f.get('participant2Name')}  hasOdds="
                  f"{f.get('hasOdds')}  id={f.get('fixtureId')}")
    else:
        show("fixtures with from/to", st, fx)

    print("=" * 55)
    print("Round 3 done (read-only; a handful of requests).")


if __name__ == "__main__":
    main()
