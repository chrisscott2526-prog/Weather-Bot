"""Weather-Bot: OddsPapi probe (read-only, Sep 15 2026).

Discovery only -- prints truncated live responses from OddsPapi's v4
API so the research lane is built against real shapes, never a
guessed contract (the sports_probe / modellab_probe pattern). Runs
inside oddspapi_probe.yml on GitHub's runners; the repo's sessions
cannot reach oddspapi.io from their sandbox.

Chain probed: sports -> tournaments(NFL) -> fixtures -> odds for one
real fixture, plus the bulk odds-by-tournament endpoint if one
exists (bulk matters: the free tier is request-capped, and one call
per fixture burns it fast).

Honesty rules: never prints the key or full request URLs; fails RED
on a missing/empty key (the Aug 19 2026 empty-secret scar). Costs a
handful of requests per press -- read-only, no files written.
"""

import json, os, sys, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone

KEY = os.environ.get("ODDSPAPI_KEY", "").strip()
if not KEY:
    sys.exit("ODDSPAPI_KEY is MISSING or EMPTY -- refusing to probe "
             "(the Aug 19 2026 empty-secret scar).")

BASE = "https://api.oddspapi.io/v4"


def get(path, **params):
    """(status, parsed-or-text). Never prints the URL (it carries the
    key)."""
    params["apiKey"] = KEY
    url = f"{BASE}/{path}?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers={"User-Agent":
                                     "weather-bot-research-probe"})
        with urllib.request.urlopen(req, timeout=30) as r:
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
    print(f"{label} -> HTTP {status}")
    text = json.dumps(body) if not isinstance(body, str) else body
    print(text[:limit] + ("..." if len(text) > limit else ""))


def main():
    # 1. NFL tournaments (american-football = sportId 14, probe run 1)
    st, tours = get("tournaments", sportId=14)
    show("tournaments?sportId=14", st, tours)
    nfl_id = None
    if st == 200 and isinstance(tours, list):
        for t in tours:
            name = str(t.get("tournamentName") or t.get("name") or "")
            if name.strip().upper() == "NFL" or "NFL" in name.upper():
                nfl_id = t.get("tournamentId") or t.get("id")
                print(f"--> matched NFL tournament: {name!r} id={nfl_id}")
                break
    if nfl_id is None:
        sys.exit("Could not find an NFL tournament -- read the dump "
                 "above and adjust the probe.")

    # 2. Fixtures for that tournament (shape: ids, participants, times)
    st, fx = get("fixtures", tournamentId=nfl_id)
    if isinstance(fx, list):
        print("=" * 55)
        print(f"fixtures?tournamentId={nfl_id} -> HTTP {st}; "
              f"{len(fx)} fixtures; first two in full:")
        print(json.dumps(fx[:2], indent=1)[:3000])
    else:
        show(f"fixtures?tournamentId={nfl_id}", st, fx)
        sys.exit("Fixtures response was not a list -- read and adjust.")

    # Pick the next upcoming fixture for the odds probe
    now = datetime.now(timezone.utc).isoformat()
    upcoming = [f for f in fx
                if str(f.get("startTime") or f.get("startDate") or "")
                >= now]
    target = (upcoming or fx)[0]
    fid = target.get("fixtureId") or target.get("id")
    print(f"--> odds probe fixture: id={fid}")

    # 3. Odds for one real fixture -- the payload the lane will parse
    st, odds = get("odds", fixtureId=fid)
    show(f"odds?fixtureId={fid}", st, odds, limit=4000)

    # 4. Bulk endpoint hunt -- one call per fixture would eat the
    # request-capped free tier; a per-tournament bulk call changes
    # the lane's whole cost model. Try the documented-sounding names.
    for path in ("odds-by-tournaments", "odds-by-tournament"):
        st, body = get(path, tournamentId=nfl_id)
        show(f"{path}?tournamentId={nfl_id}", st, body, limit=1200)

    print("=" * 55)
    print("Probe done (read-only; a handful of requests).")


if __name__ == "__main__":
    main()
