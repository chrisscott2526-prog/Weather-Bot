"""Weather-Bot repo: SPORTS PROBE (read-only -- writes NOTHING, bets NOTHING).

This is the hand-verification tool CLAUDE.md requires before any Kalshi
series ticker is whitelisted in sports_scanner.py, and the plan-check tool
for The Odds API key. Run it from the Actions workflow with the probe
input set to true:

    gh workflow run sports.yml -f probe=true      (or the Actions web UI)

It answers two questions, in plain text in the job log:

  1. ODDS API PLAN -- which markets can the current ODDS_API_KEY actually
     pull? Featured markets (h2h / spreads / totals) are on every plan.
     Period markets (first-half, first-5-innings) and player props need a
     paid plan and the per-event endpoint. We try each one and print
     exactly what the API says, including remaining quota.

  2. KALSHI SPORTS INVENTORY -- every series with open markets right now,
     with market counts and real volume/open-interest totals, so a human
     can pick liquid prop series by reading titles, not by substring
     matching (substring matching is what produced the 9-21 edge era).

It never writes a CSV, never places an order, and never touches the card.
"""

import json
import os
import time
import urllib.error
import urllib.request
from collections import defaultdict

OBASE = "https://api.the-odds-api.com/v4"
KBASE = "https://api.elections.kalshi.com"
ODDS_KEY = os.environ["ODDS_API_KEY"].strip()

# Market keys to try per sport on the per-event endpoint. These are the
# prop shelves we care about (Kalshi's retail crowd is softest here).
MLB_PROP_MARKETS = [
    "h2h_1st_5_innings", "spreads_1st_5_innings", "totals_1st_5_innings",
    "h2h_1st_3_innings", "h2h_1st_7_innings", "totals_1st_1_innings",
    "pitcher_strikeouts", "pitcher_outs", "pitcher_record_a_win",
    "batter_home_runs", "batter_hits", "batter_total_bases",
    "batter_runs_scored", "batter_rbis",
]
NFL_PROP_MARKETS = [
    "h2h_h1", "spreads_h1", "totals_h1",
    "player_pass_tds", "player_anytime_td", "player_pass_yds",
]


def http_json(url, label):
    """GET url, print quota headers, return (json, None) or (None, errtext)."""
    req = urllib.request.Request(url, headers={"User-Agent": "weather-bot-probe"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            used = r.headers.get("x-requests-used")
            left = r.headers.get("x-requests-remaining")
            if left is not None:
                print(f"    [{label}] odds-api quota: used={used} remaining={left}")
            return json.load(r), None
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", "replace")[:500]
        except Exception:
            body = "(no body)"
        return None, f"HTTP {e.code}: {body}"
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def odds_url(path, **params):
    params["apiKey"] = ODDS_KEY
    q = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{OBASE}{path}?{q}"


def summarize_event_odds(ev, requested):
    """Which of the requested market keys did any bookmaker return?"""
    seen = defaultdict(set)          # market key -> set of book keys
    outcomes = defaultdict(int)      # market key -> total outcome rows
    for bk in ev.get("bookmakers", []):
        for m in bk.get("markets", []):
            seen[m.get("key", "?")].add(bk.get("key", "?"))
            outcomes[m.get("key", "?")] += len(m.get("outcomes", []))
    for mk in requested:
        if mk in seen:
            print(f"    OK   {mk:<24} {len(seen[mk])} book(s), "
                  f"{outcomes[mk]} outcome rows")
        else:
            print(f"    none {mk:<24} no book returned it (not offered on "
                  f"this game, or not on this plan -- see per-key test)")


def probe_event_markets(sport_key, markets):
    """Try the per-event additional-markets endpoint for one upcoming game."""
    events, err = http_json(odds_url(f"/sports/{sport_key}/events"), "events")
    if err:
        print(f"  events list failed: {err}")
        return
    if not events:
        print("  no upcoming events -- cannot probe per-event markets today")
        return
    ev = events[0]
    print(f"  probing event: {ev.get('away_team')} @ {ev.get('home_team')} "
          f"({ev.get('commence_time')})")
    # One batched call first (cheapest happy path)...
    batch = ",".join(markets)
    data, err = http_json(
        odds_url(f"/sports/{sport_key}/events/{ev['id']}/odds",
                 regions="us", markets=batch, oddsFormat="decimal"),
        "event-odds batch")
    if data is not None:
        print("  batched per-event call SUCCEEDED. Markets returned:")
        summarize_event_odds(data, markets)
        return
    print(f"  batched per-event call failed: {err}")
    # ...then one-by-one so the log names exactly which keys the plan
    # rejects and which merely have no offers today.
    print("  retrying each market key individually:")
    for mk in markets:
        data, err = http_json(
            odds_url(f"/sports/{sport_key}/events/{ev['id']}/odds",
                     regions="us", markets=mk, oddsFormat="decimal"),
            f"event-odds {mk}")
        if err:
            print(f"    FAIL {mk:<24} {err}")
        else:
            summarize_event_odds(data, [mk])
        time.sleep(0.3)


def probe_odds_api():
    print("=" * 72)
    print("PART 1: WHAT THE ODDS API KEY CAN PULL")
    print("=" * 72)

    sports, err = http_json(odds_url("/sports"), "sports list")
    if err:
        print(f"/sports failed -- key may be dead: {err}")
        return
    active = [s for s in sports if s.get("active")]
    print(f"\nActive sports on the feed right now: {len(active)}")
    for s in active:
        if s.get("group") in ("Baseball", "American Football", "Basketball",
                              "Ice Hockey"):
            print(f"  {s['key']:<28} {s.get('title', '')}")

    print("\n-- Featured markets (h2h,spreads,totals) on baseball_mlb --")
    data, err = http_json(
        odds_url("/sports/baseball_mlb/odds",
                 regions="us", markets="h2h,spreads,totals",
                 oddsFormat="decimal"),
        "featured mlb")
    if err:
        print(f"  featured call failed: {err}")
    else:
        n_books = {len(ev.get("bookmakers", [])) for ev in data}
        print(f"  {len(data)} MLB games returned, "
              f"books per game: {sorted(n_books) if n_books else '[]'}")
        mkeys = set()
        for ev in data:
            for bk in ev.get("bookmakers", []):
                for m in bk.get("markets", []):
                    mkeys.add(m.get("key"))
        print(f"  market keys present: {sorted(mkeys)}")

    print("\n-- Per-event MLB prop/period markets --")
    probe_event_markets("baseball_mlb", MLB_PROP_MARKETS)

    print("\n-- Per-event NFL prop/period markets (preseason) --")
    probe_event_markets("americanfootball_nfl", NFL_PROP_MARKETS)


def kalshi_get(path, label):
    req = urllib.request.Request(KBASE + path,
                                 headers={"User-Agent": "weather-bot-probe"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r), None
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", "replace")[:300]
        except Exception:
            body = "(no body)"
        return None, f"{label}: HTTP {e.code}: {body}"
    except Exception as e:
        return None, f"{label}: {type(e).__name__}: {e}"


# Leagues we might ever card. The tag is matched against SERIES TICKERS
# from Kalshi's own category=Sports catalogue purely to shortlist which
# series get a volume lookup -- a READING AID for hand-verification.
# Nothing from this list is ever whitelisted automatically.
LEAGUE_TAGS = ("MLB", "NFL", "NBA", "WNBA", "NHL", "NCAA", "UFC", "PGA",
               "ATP", "WTA", "F1", "NASCAR", "EPL", "MLS", "SERIEA",
               "LALIGA", "BUNDES", "UCL", "TENNIS", "SOCCER", "CFB", "CBB")
MAX_SERIES_LOOKUPS = 90


def probe_kalshi():
    print()
    print("=" * 72)
    print("PART 2: KALSHI SPORTS INVENTORY (open markets, real volume)")
    print("=" * 72)

    data, err = kalshi_get("/trade-api/v2/series/?category=Sports", "series")
    if err:
        print(f"series catalogue failed ({err}) -- cannot inventory")
        return
    catalogue = {(s.get("ticker") or ""): (s.get("title") or "")
                 for s in data.get("series", [])}
    print(f"Kalshi lists {len(catalogue)} series under category=Sports")

    short = {t: title for t, title in catalogue.items()
             if any(tag in t.upper() for tag in LEAGUE_TAGS)}
    print(f"{len(short)} of them carry a league tag "
          f"({', '.join(LEAGUE_TAGS)})")
    # MLB first (it's the season), then NFL, then the rest alphabetically.
    def league_rank(t):
        u = t.upper()
        return (0 if "MLB" in u else 1 if "NFL" in u else 2, t)
    ordered = sorted(short, key=league_rank)
    if len(ordered) > MAX_SERIES_LOOKUPS:
        print(f"capping volume lookups at {MAX_SERIES_LOOKUPS} series -- "
              f"{len(ordered) - MAX_SERIES_LOOKUPS} tagged series skipped "
              f"(list below shows which)")
    lookups, skipped = ordered[:MAX_SERIES_LOOKUPS], ordered[MAX_SERIES_LOOKUPS:]

    rows = []
    samples = {}
    for t in lookups:
        data, err = kalshi_get(
            f"/trade-api/v2/markets?series_ticker={t}&status=open&limit=200",
            t)
        if err:
            print(f"  {t}: {err}")
            continue
        mkts = data.get("markets", [])
        if not mkts:
            continue
        rows.append({
            "t": t, "n": len(mkts),
            "vol": sum(m.get("volume") or 0 for m in mkts),
            "vol24": sum(m.get("volume_24h") or 0 for m in mkts),
            "oi": sum(m.get("open_interest") or 0 for m in mkts),
        })
        samples[t] = mkts
        time.sleep(0.12)

    rows.sort(key=lambda r: -r["vol24"])
    print(f"\n{len(rows)} tagged series have open markets right now. "
          f"By 24h volume:")
    print(f"  {'SERIES':<26}{'MKTS':>6}{'VOL24H':>10}{'VOLUME':>12}"
          f"{'OPENINT':>10}  TITLE")
    for r in rows:
        print(f"  {r['t']:<26}{r['n']:>6}{r['vol24']:>10,}{r['vol']:>12,}"
              f"{r['oi']:>10,}  {catalogue.get(r['t'], '')[:60]}")

    print("\nSample open markets from the top series (ticker anatomy for "
          "the matcher):")
    for r in rows[:12]:
        t = r["t"]
        mkts = sorted(samples[t], key=lambda m: -(m.get("volume_24h") or 0))
        print(f"  -- {t}: {catalogue.get(t, '')}")
        for m in mkts[:3]:
            print(f"     {m.get('ticker', '')}")
            print(f"       title={m.get('title', '')!r} "
                  f"yes_sub={m.get('yes_sub_title', '')!r}")
            print(f"       yes_ask={m.get('yes_ask')} no_ask={m.get('no_ask')} "
                  f"vol24={m.get('volume_24h')} oi={m.get('open_interest')} "
                  f"close={m.get('close_time', '')}")

    if skipped:
        print("\nTagged series skipped by the lookup cap (titles only):")
        for t in skipped:
            print(f"  {t:<26} {catalogue.get(t, '')[:70]}")


def main():
    print("SPORTS PROBE -- read-only. No bets, no CSV writes, no card.")
    probe_odds_api()
    probe_kalshi()
    print("\nprobe complete.")


if __name__ == "__main__":
    main()
