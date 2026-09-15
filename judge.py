"""Weather-Bot: THE JUDGE LANE (Sep 15 2026) -- plumbing only.

Born from the owner's question, verbatim intent: all this information
comes in and we trust the ensembles to vote -- "why don't you just
pick it?... I feel like we're trying to build another you." So Claude
now picks, ON PAPER: twice a day a Claude session reads everything
the bot knows (fresh station readings, every model's number, the
ensemble's bracket votes, live Kalshi prices, yesterday's settlement)
and records ONE bracket pick per in-window city, benched cities
included, with a stated confidence. Settlement grades it against the
ensemble's own pick on the same city-days. The question the record
answers: does a judgment layer over the same data beat the mechanical
vote? (Both prior judgment-flavored ideas -- the afternoon favorite,
the morning thermostat -- FAILED their backtests; that is exactly why
this one starts on paper.)

THE LAW (CLAUDE.md has the full section): ADVISORY / RESEARCH ONLY.
Nothing that trades, scans for money, or calibrates may ever read
judge_picks.csv or judge_results.csv. Promotion of the judge into
anything money-touching is an owner decision made on this record --
the scoreboard promotes; conviction never does.

This file is deliberately dumb: it assembles the briefing (brief),
records picks against live brackets (log), and grades by Kalshi's
settled results (grade). The JUDGMENT ITSELF never lives in code --
it happens in the Claude session that reads the briefing. No fallback
heuristic picks a bracket when the session doesn't: a missing pick is
a loud skip, never a synthesized row (honesty rules).

Usage:
  python3 judge.py brief             # the world, per city, right now
  python3 judge.py log picks.json    # record picks (validated live)
  python3 judge.py grade             # settle pending picks, standings

picks.json: [{"city": "...", "subtitle": "...", "pct": 55,
              "why": "one plain sentence"}, ...]
"""

import csv
import json
import os
import sys
from datetime import datetime, timedelta, timezone

from cities import CITY_TO_STATION, TIMEZONES, local_time
from csvio import appender

import highs

EDGES = "edges.csv"
SETTLEMENTS = "settlements.csv"
FORECASTS = "forecasts.csv"
RESEARCH_TODAY = "model_research_today.csv"
RESEARCH_NIGHT = "model_research.csv"

PICKS = "judge_picks.csv"
PICK_FIELDS = ["picked_utc", "market_date", "station", "city", "ticker",
               "subtitle", "floor", "cap", "claude_pct", "yes_ask",
               "ensemble_pick", "ens_floor", "ens_cap", "ensemble_pct",
               "why"]

RESULTS = "judge_results.csv"
RESULT_FIELDS = ["graded_utc", "market_date", "station", "city", "ticker",
                 "subtitle", "claude_pct", "yes_ask", "ensemble_pick",
                 "settled_low", "settled_high", "result",
                 "ensemble_result"]

# The judge picks only while a city's own clock reads 9:00-10:59 AM --
# the money lane's exact window, so the two picks are comparable.
WINDOW_START, WINDOW_END = 9, 11


def _f(s):
    """CSV cell -> float or None (blank = unbounded tail bound)."""
    s = (s or "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _same_bound(a, b):
    """Two bracket bounds match: both blank tails, or equal degrees."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return abs(a - b) < 0.51


def market_date_from_ticker(ticker):
    """KXHIGHTLV-26SEP15-B96.5 -> 2026-09-15. None if unparseable --
    a pick whose date can't be pinned is refused, never guessed."""
    parts = (ticker or "").split("-")
    if len(parts) < 3:
        return None
    try:
        return datetime.strptime(parts[1], "%y%b%d").date().isoformat()
    except ValueError:
        return None


def latest_scan_today(now=None):
    """city -> list of that city's edges.csv rows from its FRESHEST
    scan batch whose market date is the city's own today. Old scans
    and other days' markets never leak in."""
    if now is None:
        now = datetime.now(timezone.utc)
    best = {}      # city -> (scanned_utc, market_date, [rows])
    if not os.path.exists(EDGES):
        return {}
    cutoff = (now - timedelta(hours=20)).isoformat()
    with open(EDGES, newline="") as f:
        for row in csv.DictReader(f):
            ts = (row.get("scanned_utc") or "").strip()
            if ts < cutoff:
                continue
            city = (row.get("city") or "").strip()
            station = CITY_TO_STATION.get(city)
            if station is None:
                continue
            mdate = market_date_from_ticker(row.get("market"))
            today = highs.local_date(station, now)
            if mdate != today:
                continue
            cur = best.get(city)
            if cur is None or ts > cur[0]:
                best[city] = (ts, mdate, [row])
            elif ts == cur[0]:
                cur[2].append(row)
    return {c: {"scanned_utc": v[0], "market_date": v[1], "rows": v[2]}
            for c, v in best.items()}


def settled_map():
    """(station, date) -> (low_f, high_f) from settlements.csv --
    Kalshi's own settled winning bracket, the only judge that pays."""
    out = {}
    if not os.path.exists(SETTLEMENTS):
        return out
    with open(SETTLEMENTS, newline="") as f:
        for row in csv.DictReader(f):
            key = ((row.get("station") or "").strip(),
                   (row.get("date") or "").strip())
            out[key] = (_f(row.get("low_f")), _f(row.get("high_f")))
    return out


def _research_numbers(path, station_dates):
    """(station -> {model: forecast_high_f}) for the given
    station -> local-date map, freshest row per model."""
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            st = (row.get("station") or "").strip()
            if station_dates.get(st) != (row.get("forecast_date") or "").strip():
                continue
            model = (row.get("model") or "").strip()
            fh = _f(row.get("forecast_high_f"))
            if not model or fh is None:
                continue
            rec = out.setdefault(st, {})
            prev = rec.get(model)
            fetched = (row.get("fetched_utc") or "").strip()
            if prev is None or fetched > prev[1]:
                rec[model] = (fh, fetched)
    return {st: {m: v[0] for m, v in rec.items()}
            for st, rec in out.items()}


def brief(now=None):
    """Print the world, one block per city. Cities inside their own
    9:00-10:59 AM window are marked IN WINDOW -- the judge picks only
    those. Missing data prints as missing, never invented."""
    if now is None:
        now = datetime.now(timezone.utc)
    scans = latest_scan_today(now)
    latest = highs.latest_readings(now)
    hi_today = highs.highs_today(now)
    settled = settled_map()

    station_dates = {st: highs.local_date(st, now)
                     for st in TIMEZONES}
    same_day = _research_numbers(RESEARCH_TODAY, station_dates)
    nightly = _research_numbers(RESEARCH_NIGHT, station_dates)

    print(f"JUDGE BRIEFING  {now.isoformat(timespec='seconds')}")
    print("Pick ONLY cities marked IN WINDOW. One bracket each, from")
    print("the LIVE BRACKETS list verbatim. Skipping a city (too")
    print("uncertain, stale data) is always allowed and always loud.\n")

    for city, station in sorted(CITY_TO_STATION.items()):
        loc = local_time(station, now)
        in_win = WINDOW_START <= loc.hour < WINDOW_END
        tag = "IN WINDOW" if in_win else "out of window"
        print(f"== {city} ({station})  local {loc.strftime('%H:%M')}  [{tag}]")

        lt = latest.get(city)
        ht = hi_today.get(city)
        if lt and ht:
            print(f"   now: {lt[0]}F ({lt[1]}m old)   "
                  f"high so far: {ht[0]}F")
        else:
            print("   no station reading yet today")

        yday = highs.local_date(
            station, now - timedelta(days=1))
        s = settled.get((station, yday))
        if s:
            lo = "" if s[0] is None else int(s[0])
            hi = "" if s[1] is None else int(s[1])
            print(f"   yesterday settled: {lo}-{hi}F")

        models = {}
        models.update(nightly.get(station, {}))
        models.update({f"{m} (same-day)": v
                       for m, v in same_day.get(station, {}).items()})
        if models:
            txt = "  ".join(f"{m}:{v}" for m, v in sorted(models.items()))
            print(f"   models: {txt}")

        scan = scans.get(city)
        if not scan:
            print("   NO LIVE SCAN for today's market -> cannot pick\n")
            continue
        print(f"   live brackets (scan {scan['scanned_utc']}):")
        rows = sorted(scan["rows"],
                      key=lambda r: _f(r.get("floor")) if _f(r.get("floor"))
                      is not None else -999.0)
        for r in rows:
            mark = "  <- ensemble pick" if (r.get("pick") or "").strip() else ""
            print(f"     {r.get('subtitle','?'):18s} ask {r.get('yes_ask'):>5s}c"
                  f"  members {r.get('model_prob_pct'):>5s}%{mark}")
        print()


def log_picks(path, now=None):
    """Validate and record the session's picks. A pick must name a
    LIVE bracket from today's freshest scan -- anything else is a
    loud refusal, never a guessed row."""
    if now is None:
        now = datetime.now(timezone.utc)
    with open(path) as f:
        picks = json.load(f)
    scans = latest_scan_today(now)
    stamp = now.isoformat(timespec="seconds")

    logged = 0
    with appender(PICKS, PICK_FIELDS) as w:
        for p in picks:
            city = (p.get("city") or "").strip()
            subtitle = (p.get("subtitle") or "").strip()
            station = CITY_TO_STATION.get(city)
            scan = scans.get(city)
            if station is None or scan is None:
                print(f"REFUSED: {city!r} -- no live scan for today")
                continue
            row = next((r for r in scan["rows"]
                        if (r.get("subtitle") or "").strip() == subtitle),
                       None)
            if row is None:
                print(f"REFUSED: {city}: {subtitle!r} is not a live bracket")
                continue
            loc = local_time(station, now)
            if not (WINDOW_START <= loc.hour < WINDOW_END):
                print(f"REFUSED: {city} -- outside its 9-11 AM window "
                      f"(local {loc.strftime('%H:%M')})")
                continue
            ens = next((r for r in scan["rows"]
                        if (r.get("pick") or "").strip()), None)
            w.writerow({
                "picked_utc": stamp,
                "market_date": scan["market_date"],
                "station": station, "city": city,
                "ticker": (row.get("market") or "").strip(),
                "subtitle": subtitle,
                "floor": (row.get("floor") or "").strip(),
                "cap": (row.get("cap") or "").strip(),
                "claude_pct": p.get("pct", ""),
                "yes_ask": (row.get("yes_ask") or "").strip(),
                "ensemble_pick": (ens.get("subtitle") or "").strip() if ens else "",
                "ens_floor": (ens.get("floor") or "").strip() if ens else "",
                "ens_cap": (ens.get("cap") or "").strip() if ens else "",
                "ensemble_pct": (ens.get("model_prob_pct") or "").strip() if ens else "",
                "why": (p.get("why") or "").strip(),
            })
            logged += 1
            print(f"logged: {city} -> {subtitle} ({p.get('pct','?')}%)")
    print(f"{logged} pick(s) logged")


def grade(now=None):
    """Grade every ungraded pick whose market has settled, then print
    the running standings: Claude vs the ensemble, same city-days."""
    if now is None:
        now = datetime.now(timezone.utc)
    if not os.path.exists(PICKS):
        print("no picks to grade")
        return
    done = set()
    if os.path.exists(RESULTS):
        with open(RESULTS, newline="") as f:
            for row in csv.DictReader(f):
                done.add((row.get("station"), row.get("market_date"),
                          row.get("ticker")))
    settled = settled_map()
    stamp = now.isoformat(timespec="seconds")

    graded = pending = 0
    with open(PICKS, newline="") as f:
        picks = list(csv.DictReader(f))
    with appender(RESULTS, RESULT_FIELDS) as w:
        for p in picks:
            key = (p.get("station"), p.get("market_date"), p.get("ticker"))
            if key in done:
                continue
            s = settled.get((p.get("station"), p.get("market_date")))
            if s is None:
                pending += 1
                continue
            lo, hi = s
            hit = (_same_bound(_f(p.get("floor")), lo)
                   and _same_bound(_f(p.get("cap")), hi))
            ens_res = ""
            if (p.get("ensemble_pick") or "").strip():
                ens_hit = (_same_bound(_f(p.get("ens_floor")), lo)
                           and _same_bound(_f(p.get("ens_cap")), hi))
                ens_res = "HIT" if ens_hit else "MISS"
            w.writerow({
                "graded_utc": stamp,
                "market_date": p.get("market_date"),
                "station": p.get("station"), "city": p.get("city"),
                "ticker": p.get("ticker"), "subtitle": p.get("subtitle"),
                "claude_pct": p.get("claude_pct"),
                "yes_ask": p.get("yes_ask"),
                "ensemble_pick": p.get("ensemble_pick"),
                "settled_low": "" if lo is None else lo,
                "settled_high": "" if hi is None else hi,
                "result": "HIT" if hit else "MISS",
                "ensemble_result": ens_res,
            })
            done.add(key)
            graded += 1
    print(f"graded {graded}, pending {pending}")

    # standings from the full results file
    cw = cl = ew = el = 0
    if os.path.exists(RESULTS):
        with open(RESULTS, newline="") as f:
            for row in csv.DictReader(f):
                if row.get("result") == "HIT":
                    cw += 1
                elif row.get("result") == "MISS":
                    cl += 1
                if row.get("ensemble_result") == "HIT":
                    ew += 1
                elif row.get("ensemble_result") == "MISS":
                    el += 1
    print(f"STANDINGS  claude {cw}W-{cl}L   ensemble (same days) {ew}W-{el}L")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "brief":
        brief()
    elif cmd == "log" and len(sys.argv) > 2:
        log_picks(sys.argv[2])
    elif cmd == "grade":
        grade()
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()
