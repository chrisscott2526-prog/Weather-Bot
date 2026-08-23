"""One-off audit (Aug 23 2026): what does the RULES PANEL of each of our
20 city series actually name as the settlement source?

Background: the operator spotted a note in ONE market's rules saying the
market settles on data from The Weather Company (TWC), while our whole
mental model -- and CLAUDE.md -- says Kalshi settles on the NWS CLI Daily
Climate Report (the CLIPHX-style codes we verified by hand on Aug 3).
This script maps the real coverage instead of assuming either way.

It is READ-ONLY and ADVISORY: unauthenticated Kalshi market data, no
orders, no CSV writes, no changes to any money path. It prints the full
rules text (rules_primary + rules_secondary) for one market per series,
classifies each as naming TWC and/or NWS, and prints a summary table.

Honesty rules apply: a series whose rules cannot be fetched is reported
loudly and the run exits non-zero (a dead feed must never look green --
the Aug 19 scar).
"""
import json
import re
import sys
import time
import urllib.request

from cities import CITIES

BASE = "https://api.elections.kalshi.com"
UA = {"User-Agent": "weather-bot rules audit (read-only)"}


def get(url, tries=4):
    """GET JSON with the repo-standard backoff (2s, 4s, 8s, 16s)."""
    last = None
    for n in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except Exception as e:  # noqa: BLE001 - report, retry, then fail loud
            last = e
            time.sleep(2 * (2 ** n))
    raise RuntimeError(f"GET failed after {tries} tries: {url}: {last}")


def market_for(series):
    """One representative market per series: prefer an open one (the
    rules traders see today), else the most recent of any status."""
    for extra in ("&status=open", ""):
        data = get(f"{BASE}/trade-api/v2/markets?series_ticker={series}"
                   f"&limit=3{extra}")
        markets = data.get("markets") or []
        if markets:
            return markets[0]
    return None


def classify(text):
    twc = bool(re.search(r"the\s+weather\s+company|weather\.com|\bTWC\b|\bIBM\b",
                         text, re.I))
    nws = bool(re.search(r"national\s+weather\s+service|\bNWS\b"
                         r"|climatological|daily\s+climate", text, re.I))
    cli_codes = sorted(set(re.findall(r"\bCLI[A-Z]{2,4}\b", text)))
    return twc, nws, cli_codes


def main():
    rows = []
    failures = []
    for series, (city, station, _lat, _lon, _v) in CITIES.items():
        try:
            m = market_for(series)
        except RuntimeError as e:
            print(f"FETCH FAILED  {series} ({city}): {e}")
            failures.append(series)
            continue
        if m is None:
            print(f"NO MARKETS    {series} ({city}): API returned none")
            failures.append(series)
            continue

        primary = m.get("rules_primary") or ""
        secondary = m.get("rules_secondary") or ""
        twc, nws, cli_codes = classify(primary + " " + secondary)
        rows.append((series, city, station, m.get("ticker"),
                     m.get("status"), twc, nws, cli_codes))

        print("=" * 72)
        print(f"{series}  {city}  (our station: {station})")
        print(f"market: {m.get('ticker')}  status: {m.get('status')}")
        print("--- rules_primary ---")
        print(primary or "(empty)")
        print("--- rules_secondary ---")
        print(secondary or "(empty)")
        time.sleep(0.5)  # pace unauth requests, same as settlements.py

    print("=" * 72)
    print("SUMMARY  (source named in the rules text)")
    print(f"{'series':13} {'city':15} {'station':8} "
          f"{'TWC':4} {'NWS':4} cli_codes")
    for series, city, station, _t, _s, twc, nws, cli in rows:
        print(f"{series:13} {city:15} {station:8} "
              f"{'YES' if twc else '-':4} {'YES' if nws else '-':4} "
              f"{','.join(cli) or '-'}")

    if failures:
        print(f"\nAUDIT INCOMPLETE: {len(failures)} series unreadable: "
              f"{', '.join(failures)}")
        sys.exit(1)
    print(f"\nAudit complete: all {len(rows)} series read.")


if __name__ == "__main__":
    main()
