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


def probe_kalshi():
    print()
    print("=" * 72)
    print("PART 2: KALSHI SPORTS INVENTORY (open markets, real volume)")
    print("=" * 72)

    # Series catalogue for the Sports category, if the endpoint cooperates.
    sports_series = {}
    data, err = kalshi_get("/trade-api/v2/series/?category=Sports", "series")
    if err:
        print(f"series-by-category failed ({err}); "
              f"falling back to title-only inventory")
    else:
        for s in data.get("series", []):
            sports_series[s.get("ticker", "")] = s.get("title", "")
        print(f"Kalshi lists {len(sports_series)} series under category=Sports")

    # Page through every open market and aggregate by series ticker.
    agg = {}
    cursor = ""
    pages = 0
    while pages < 40:
        path = "/trade-api/v2/markets?status=open&limit=1000"
        if cursor:
            path += f"&cursor={cursor}"
        data, err = kalshi_get(path, "markets")
        if err:
            print(f"market paging stopped: {err}")
            break
        pages += 1
        for m in data.get("markets", []):
            prefix = (m.get("ticker") or "").split("-")[0]
            a = agg.setdefault(prefix, {
                "n": 0, "vol": 0, "vol24": 0, "oi": 0, "title": ""})
            a["n"] += 1
            a["vol"] += m.get("volume") or 0
            a["vol24"] += m.get("volume_24h") or 0
            a["oi"] += m.get("open_interest") or 0
            if not a["title"]:
                a["title"] = (m.get("title") or "")[:70]
        cursor = data.get("cursor") or ""
        if not cursor:
            break
        time.sleep(0.15)
    total_mkts = sum(a["n"] for a in agg.values())
    print(f"paged {pages} page(s), {total_mkts} open markets, "
          f"{len(agg)} distinct series")
    if pages == 40 and cursor:
        print("WARNING: page cap hit -- inventory below is TRUNCATED")

    def rows_for(tickers):
        rows = [(t, agg[t]) for t in tickers if t in agg]
        return sorted(rows, key=lambda r: -r[1]["vol"])

    def show(rows, limit=None):
        print(f"  {'SERIES':<22}{'MKTS':>6}{'VOLUME':>12}{'VOL24H':>10}"
              f"{'OPENINT':>10}  EXAMPLE TITLE")
        for t, a in (rows[:limit] if limit else rows):
            title = sports_series.get(t) or a["title"]
            print(f"  {t:<22}{a['n']:>6}{a['vol']:>12,}{a['vol24']:>10,}"
                  f"{a['oi']:>10,}  {title}")

    if sports_series:
        print("\nAll category=Sports series with open markets, by volume:")
        show(rows_for(sports_series.keys()))
    else:
        print("\nTop 100 open series by volume (hand-read the titles):")
        show(sorted(agg.items(), key=lambda r: -r[1]["vol"]), limit=100)

    # Convenience view: likely-baseball series, by title words. This is a
    # READING AID for the human doing hand-verification -- nothing here is
    # ever whitelisted automatically.
    words = ("baseball", "mlb", "innings", "strikeout", "home run", "hits",
             "run scored", "total runs")
    print("\nSeries whose example title mentions baseball things:")
    hits = [(t, a) for t, a in agg.items()
            if any(w in (sports_series.get(t, "") + " " + a["title"]).lower()
                   for w in words)]
    show(sorted(hits, key=lambda r: -r[1]["vol"]))


def main():
    print("SPORTS PROBE -- read-only. No bets, no CSV writes, no card.")
    probe_odds_api()
    probe_kalshi()
    print("\nprobe complete.")


if __name__ == "__main__":
    main()
