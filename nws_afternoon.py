"""Weather-Bot: THE NWS 1 PM LOG (Sep 17 2026) -- RESEARCH ONLY.

The owner's ask, verbatim intent: "make sure there is a log of what
NWS would purchase -- what bracket -- at 1 o'clock in the afternoon,
or the closest refresh of temperatures closest to that time. What I'm
looking for is if NWS is more accurate, or the most accurate, later
in the day."

So this logs, once per city per day when that city's OWN clock reads
~1 PM (13:00-14:59 local, first capture wins, the local time recorded
honestly so the review knows how close to 1:00 each row really was):

  - the LIVE NWS point forecast's same-day high, fetched at log time
    through model_lab.nws_high -- the same shared code the NWS money
    lane and the Model Lab use (one source, one method);
  - the live Kalshi bracket that number lands in, matched against the
    freshest scan of today's market in edges.csv (judge.py's own
    matcher -- a number that matches no live bracket is a LOUD skip,
    never a guessed row), with the bracket's ask at that scan for
    context.

Grading is by Kalshi's own settled bracket (settlements.csv), and the
standings print the comparison the owner actually asked for: the 1 PM
number vs the NWS NIGHT-BEFORE number (model_research.csv) vs the NWS
morning same-day pull (model_research_today.csv, the ~14:12 UTC slot)
on the SAME city-days. All 20 cities, benched included -- the bench
law: paper records accrue everywhere.

THE LAW (same as the Model Lab, the Judge Lane, and every research
rider): **RESEARCH ONLY -- nothing that trades, scans for money, or
calibrates may ever read nws_afternoon_picks.csv or
nws_afternoon_results.csv.** No bet is placed and there is no pnl
column on purpose. Promoting "the 1 PM NWS number" into anything
money-touching is an owner decision made on this record -- the
scoreboard promotes; conviction never does.

Usage:
  python3 nws_afternoon.py log      # capture in-window cities (live NWS fetch)
  python3 nws_afternoon.py grade    # settle pending rows, print standings
"""

import csv
import os
import sys
from datetime import datetime, timezone

from cities import CITIES, local_time
from csvio import appender
from judge import latest_scan_today, settled_map, _f, _same_bound
from model_lab import nws_high
from nws_second_opinion import bracket_dist

import highs

PICKS = "nws_afternoon_picks.csv"
PICK_FIELDS = ["logged_utc", "local_hhmm", "market_date", "station", "city",
               "nws_f", "ticker", "subtitle", "floor", "cap", "yes_ask",
               "scan_utc"]

RESULTS = "nws_afternoon_results.csv"
RESULT_FIELDS = ["graded_utc", "market_date", "station", "city", "nws_f",
                 "subtitle", "floor", "cap", "yes_ask",
                 "settled_low", "settled_high", "result", "brackets_off"]

# Capture window on the CITY'S OWN clock: 1 PM up to 2:59 PM. The
# target is 13:0x; the tail of the window exists so a dropped cron
# slot (GitHub fired 9 of the poller's 96 once) still gets a capture,
# a little late, instead of losing the day. First capture per
# (station, market date) wins; local_hhmm records how late it was.
WINDOW_START_HOUR, WINDOW_END_HOUR = 13, 15


def _logged_keys():
    """(station, market_date) pairs already captured."""
    done = set()
    if os.path.exists(PICKS):
        with open(PICKS, newline="") as f:
            for r in csv.DictReader(f):
                done.add(((r.get("station") or "").strip(),
                          (r.get("market_date") or "").strip()))
    return done


def log(now=None):
    """One pass: capture every city currently in its 13:00-14:59
    local window that has no row yet for its own today. Missing data
    is a loud skip, never an invented row. Exits non-zero only when
    every attempted capture died on the NWS feed itself (dead-feed
    law); a pass with nothing in window is quietly green."""
    if now is None:
        now = datetime.now(timezone.utc)
    done = _logged_keys()
    scans = latest_scan_today(now)
    stamp = now.isoformat(timespec="seconds")

    attempted = feed_dead = logged = 0
    with appender(PICKS, PICK_FIELDS) as w:
        for series, (city, station, lat, lon, _) in CITIES.items():
            loc = local_time(station, now)
            if not (WINDOW_START_HOUR <= loc.hour < WINDOW_END_HOUR):
                continue
            mdate = highs.local_date(station, now)
            if (station, mdate) in done:
                continue
            attempted += 1

            try:
                val = nws_high(lat, lon, mdate)
            except Exception as e:
                print(f"SKIP {city}: NWS fetch failed -- {e}")
                feed_dead += 1
                continue
            if val is None:
                # after mid-afternoon the NWS drops today's daytime
                # period; that is the feed being honest, not dead
                print(f"SKIP {city}: NWS has no daytime period for {mdate}")
                continue

            scan = scans.get(city)
            if scan is None:
                print(f"SKIP {city}: no live scan of today's market "
                      "in edges.csv -- cannot name a bracket")
                continue
            row = None
            for r in scan["rows"]:
                lo, hi = _f(r.get("floor")), _f(r.get("cap"))
                if (lo is None or val >= lo) and (hi is None or val <= hi):
                    row = r
                    break
            if row is None:
                print(f"SKIP {city}: NWS {val}F matches no live bracket "
                      "-- refusing to guess")
                continue

            w.writerow({
                "logged_utc": stamp,
                "local_hhmm": loc.strftime("%H:%M"),
                "market_date": mdate,
                "station": station, "city": city,
                "nws_f": val,
                "ticker": (row.get("market") or "").strip(),
                "subtitle": (row.get("subtitle") or "").strip(),
                "floor": (row.get("floor") or "").strip(),
                "cap": (row.get("cap") or "").strip(),
                "yes_ask": (row.get("yes_ask") or "").strip(),
                "scan_utc": scan["scanned_utc"],
            })
            done.add((station, mdate))
            logged += 1
            print(f"logged {city}: NWS {val}F -> "
                  f"{row.get('subtitle')} (ask {row.get('yes_ask')}c, "
                  f"local {loc.strftime('%H:%M')})")

    print(f"{logged} captured, {attempted - logged} skipped")
    if attempted and feed_dead == attempted:
        print("DEAD FEED: every NWS fetch this pass failed")
        sys.exit(1)


def _nws_reference(model_path, hour_lo=None, hour_hi=None):
    """(station, forecast_date) -> NWS number from a Model Lab file,
    freshest qualifying row. Optional fetched_utc UTC-hour band picks
    the same-day lab's morning slot out of its two daily pulls."""
    out = {}
    if not os.path.exists(model_path):
        return out
    with open(model_path, newline="") as f:
        for r in csv.DictReader(f):
            if (r.get("model") or "").strip() != "nws":
                continue
            val = _f(r.get("forecast_high_f"))
            if val is None:
                continue
            fetched = (r.get("fetched_utc") or "").strip()
            if hour_lo is not None:
                try:
                    hr = int(fetched[11:13])
                except (ValueError, IndexError):
                    continue
                if not (hour_lo <= hr < hour_hi):
                    continue
            key = ((r.get("station") or "").strip(),
                   (r.get("forecast_date") or "").strip())
            if key not in out or fetched > out[key][1]:
                out[key] = (val, fetched)
    return {k: v[0] for k, v in out.items()}


def grade(now=None):
    """Grade every ungraded capture whose market settled, then print
    the standings THREE ways on the same city-days: NWS night-before
    vs NWS morning same-day vs NWS at 1 PM -- the owner's question
    ("is NWS more accurate later in the day?") answered from the
    record, exact-bracket and within-one rates side by side."""
    if now is None:
        now = datetime.now(timezone.utc)
    if not os.path.exists(PICKS):
        print("no captures to grade yet")
        return
    done = set()
    if os.path.exists(RESULTS):
        with open(RESULTS, newline="") as f:
            for r in csv.DictReader(f):
                done.add(((r.get("station") or "").strip(),
                          (r.get("market_date") or "").strip()))
    settled = settled_map()
    stamp = now.isoformat(timespec="seconds")

    graded = pending = 0
    with open(PICKS, newline="") as f:
        picks = list(csv.DictReader(f))
    with appender(RESULTS, RESULT_FIELDS) as w:
        for p in picks:
            key = ((p.get("station") or "").strip(),
                   (p.get("market_date") or "").strip())
            if key in done:
                continue
            s = settled.get(key)
            if s is None:
                pending += 1
                continue
            lo, hi = s
            hit = (_same_bound(_f(p.get("floor")), lo)
                   and _same_bound(_f(p.get("cap")), hi))
            w.writerow({
                "graded_utc": stamp,
                "market_date": p.get("market_date"),
                "station": p.get("station"), "city": p.get("city"),
                "nws_f": p.get("nws_f"), "subtitle": p.get("subtitle"),
                "floor": p.get("floor"), "cap": p.get("cap"),
                "yes_ask": p.get("yes_ask"),
                "settled_low": "" if lo is None else lo,
                "settled_high": "" if hi is None else hi,
                "result": "HIT" if hit else "MISS",
                "brackets_off": bracket_dist(lo, hi, _f(p.get("nws_f"))),
            })
            done.add(key)
            graded += 1
    print(f"graded {graded}, pending {pending}")

    # -- the standings: night-before vs morning same-day vs 1 PM,
    #    on exactly the city-days the 1 PM log has graded --
    night = _nws_reference("model_research.csv")
    morning = _nws_reference("model_research_today.csv", 13, 17)
    rows = []
    with open(RESULTS, newline="") as f:
        for r in csv.DictReader(f):
            key = ((r.get("station") or "").strip(),
                   (r.get("market_date") or "").strip())
            s = settled.get(key)
            v = _f(r.get("nws_f"))
            if s is None or v is None:
                continue
            rows.append((key, s, v))
    if not rows:
        print("no graded city-days yet -- standings start "
              "when the first market settles")
        return

    def tally(label, values):
        pairs = [(bracket_dist(s[0], s[1], val))
                 for (_, s, _), val in values if val is not None]
        n = len(pairs)
        if not n:
            print(f"  {label:26s}: no rows on these city-days")
            return
        exact = sum(1 for d in pairs if d == 0)
        within = sum(1 for d in pairs if d <= 1)
        print(f"  {label:26s}: {exact}/{n} exact ({100.0 * exact / n:.0f}%), "
              f"{within}/{n} within one ({100.0 * within / n:.0f}%)")

    print("STANDINGS (same graded city-days, exact settled bracket):")
    tally("NWS night before", [(r, night.get(r[0])) for r in rows])
    tally("NWS morning same-day", [(r, morning.get(r[0])) for r in rows])
    tally("NWS at ~1 PM local", [(r, r[2]) for r in rows])


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "log":
        log()
    elif cmd == "grade":
        grade()
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()
