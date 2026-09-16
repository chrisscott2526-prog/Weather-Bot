"""THE NWS SECOND-OPINION TEST (Sep 16, 2026) — RESEARCH ONLY.

The owner's hypothesis, in their words: the local weatherman (the NWS
point forecast for our exact stations) is dead on or one bracket away
almost every day. If the ensemble's pick sits 2+ brackets from that
number, the pick deserves no trust.

This script grades that hypothesis from data the repo already stores —
no new feeds, no API calls, re-runnable by any session at any time:

  edges.csv              the morning-lane pick (last morning scan per
                         city-day, bracket parsed from the SUBTITLE —
                         the Sep 12 tail-strike law)
  model_research.csv     the NWS night-before point forecast per
                         station (Model Lab passenger, since Sep 1)
  settlements.csv        the official settled bracket (Kalshi truth)
  results.csv            the real morning-lane bets

RESEARCH ONLY — nothing that trades, scans for money, or calibrates
may ever read this script's output. Turning the "NWS within one
bracket" rule into a money gate is an owner decision made on this
record at the October review, never before. First run's verdict is
recorded in CLAUDE.md ("THE NWS SECOND-OPINION TEST").
"""
import csv
import math
import os
import re
from collections import defaultdict

REPO = os.path.dirname(os.path.abspath(__file__))

MONTHS = {m: i + 1 for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
     "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"])}


def ticker_date(ticker):
    """KXHIGHPHIL-26SEP14-B76.5 -> 2026-09-14 (the market's own date)."""
    m = re.search(r"-(\d{2})([A-Z]{3})(\d{2})-", ticker)
    if not m:
        return None
    return "20%s-%02d-%02d" % (m.group(1), MONTHS[m.group(2)], int(m.group(3)))


def parse_subtitle(sub):
    """Inclusive (lo, hi) degree bounds from the market subtitle.
    None = unbounded tail side. Subtitle-first is the law (Sep 12)."""
    sub = sub.replace("°", "")
    m = re.match(r"\s*(-?\d+)\s*to\s*(-?\d+)", sub)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = re.match(r"\s*(-?\d+)\s*or\s*below", sub)
    if m:
        return None, float(m.group(1))
    m = re.match(r"\s*(-?\d+)\s*or\s*above", sub)
    if m:
        return float(m.group(1)), None
    return "?", "?"


def bracket_dist(lo, hi, x):
    """How many 2-degree brackets the number x sits from bracket [lo,hi].
    0 = inside, 1 = the neighboring bracket, 2+ = the veto zone."""
    if lo is not None and x < lo:
        d = lo - x
    elif hi is not None and x > hi:
        d = x - hi
    else:
        return 0
    return math.ceil(d / 2.0)


def main():
    import sys
    sys.path.insert(0, REPO)
    from cities import CITIES  # single source of truth for the 20 cities
    city2station = {v[0]: v[1] for v in CITIES.values()}

    # NWS night-before number per (station, market date)
    nws = {}
    with open(os.path.join(REPO, "model_research.csv")) as f:
        for r in csv.DictReader(f):
            if r["model"] == "nws" and r["forecast_high_f"]:
                nws[(r["station"], r["forecast_date"])] = float(r["forecast_high_f"])

    # Official settled bracket per (station, date)
    settled = {}
    with open(os.path.join(REPO, "settlements.csv")) as f:
        for r in csv.DictReader(f):
            lo = float(r["low_f"]) if r["low_f"] else None
            hi = float(r["high_f"]) if r["high_f"] else None
            settled[(r["station"], r["date"])] = (lo, hi)

    # Last morning-lane pick per (city, market date)
    picks = {}
    with open(os.path.join(REPO, "edges.csv")) as f:
        for r in csv.DictReader(f):
            if r["strategy"] != "morning" or r["pick"] != "1":
                continue
            mdate = ticker_date(r["market"])
            if not mdate:
                continue
            key = (r["city"], mdate)
            if key not in picks or r["scanned_utc"] > picks[key][0]:
                lo, hi = parse_subtitle(r["subtitle"])
                if lo == "?":
                    continue
                picks[key] = (r["scanned_utc"], lo, hi)

    # ---- Test 1: is the owner right about the NWS forecast itself? ----
    dist_count = defaultdict(int)
    n = 0
    for (st, d), val in nws.items():
        if (st, d) not in settled:
            continue
        lo, hi = settled[(st, d)]
        dist_count[bracket_dist(lo, hi, val)] += 1
        n += 1
    print("=== TEST 1: NWS night-before number vs the OFFICIAL settled bracket ===")
    print("graded city-days: %d" % n)
    for d in sorted(dist_count):
        lab = {0: "exact bracket", 1: "one bracket off"}.get(d, "%d brackets off" % d)
        print("  %-18s: %4d  (%.0f%%)" % (lab, dist_count[d], 100.0 * dist_count[d] / n))
    within = dist_count[0] + dist_count[1]
    print("  within one bracket: %d (%.0f%%)" % (within, 100.0 * within / n))

    # ---- Test 2: pick accuracy split by distance to the NWS number ----
    print("\n=== TEST 2: morning pick exact-bracket rate, by distance to NWS ===")
    rows = []
    for (city, mdate), (ts, lo, hi) in picks.items():
        st = city2station.get(city)
        if not st or (st, mdate) not in nws or (st, mdate) not in settled:
            continue
        slo, shi = settled[(st, mdate)]
        hit = (lo == slo and hi == shi)
        rows.append((city, mdate, lo, hi, nws[(st, mdate)], slo, shi, hit,
                     min(bracket_dist(lo, hi, nws[(st, mdate)]), 2)))
    for d, lab in [(0, "NWS inside the pick bracket"),
                   (1, "NWS one bracket away"),
                   (2, "NWS 2+ brackets away (the veto zone)")]:
        sub = [r for r in rows if r[8] == d]
        h = sum(r[7] for r in sub)
        if sub:
            print("  %-38s: %dW-%dL  (%.0f%% exact)"
                  % (lab, h, len(sub) - h, 100.0 * h / len(sub)))

    # ---- Test 3: what the veto would have done to the real bets ----
    print("\n=== TEST 3: real morning-lane bets on days an NWS number exists ===")
    kept = [0, 0, 0.0]
    blocked = [0, 0, 0.0]
    with open(os.path.join(REPO, "results.csv")) as f:
        for r in csv.DictReader(f):
            if (r["strategy"] or "night") != "morning":
                continue
            mdate = ticker_date(r["ticker"])
            st = city2station.get(r["city"])
            if not mdate or not st or (st, mdate) not in nws:
                continue
            m = re.search(r"-B(-?[\d.]+)$", r["ticker"])
            if m:
                mid = float(m.group(1))
                lo, hi = mid - 0.5, mid + 0.5
            else:
                pk = picks.get((r["city"], mdate))
                if not pk:
                    continue
                lo, hi = pk[1], pk[2]
            d = bracket_dist(lo, hi, nws[(st, mdate)])
            tgt = kept if d <= 1 else blocked
            tgt[0] += (r["result"] == "WIN")
            tgt[1] += 1
            tgt[2] += float(r["pnl"] or 0)
    for lab, b in [("veto KEEPS  (NWS within one bracket)", kept),
                   ("veto BLOCKS (NWS 2+ brackets away)", blocked)]:
        if b[1]:
            print("  %-36s: %dW-%dL, pnl $%+.2f" % (lab, b[0], b[1] - b[0], b[2]))
        else:
            print("  %-36s: no bets" % lab)


if __name__ == "__main__":
    main()
