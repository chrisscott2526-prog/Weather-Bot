"""Weather-Bot: yesterday's OFFICIAL settled high per city.

The Station Board shows two thermometers that are NOT the same product:
the METAR instrument reading (daily_highs.csv) and the settlement.
Kalshi settles on the NWS CLI Daily Climate Report, and its own
`result` field is the only thermometer that pays. This script records
what actually settled, so the board can show "Yesterday: settled X"
with the exchange as the source of record -- never the instrument.

HOW A DAY'S HIGH IS PINNED (honesty rules apply):
- A day's markets form one Kalshi event (e.g. KXHIGHCHI-26AUG19).
  Every settled bracket is a fact: YES on "74 to 75" pins the high
  inside 74-75; NO on "76 or above" removes those degrees. We start
  from every plausible integer degree and intersect the facts.
- A row is written ONLY when at least one market settled YES -- an
  anchor. Exclusions alone never invent a range, and a day with no
  usable settlement gets NO row (the board shows a dash).
- Ranges come from the market SUBTITLE ("74 deg to 75 deg"), never the
  raw strike fields: Kalshi tail markets carry off-by-one strikes
  (T74 has cap_strike=74 but means "73 or below"). Verified against
  live boards Aug 20 2026. An unparseable subtitle = that market is
  skipped loudly, not guessed.
- If a settled board contradicts itself (empty intersection), we write
  nothing and say so loudly. Never publish a made-up range.

SOURCES, in order of completeness:
1. kalshi-api: the whole event, unauthenticated (market data needs no
   key -- same as the sports card). Gives all 20 cities.
2. results-csv: our own graded bets (market_result came from the
   exchange, so it is settlement truth too), bracket ranges looked up
   from the subtitles scanner.py logged in edges.csv. Partial -- only
   cities we bet -- but real. Used only when the API path fails.
A kalshi-api row is final and never recomputed; a results-csv row is
upgraded to kalshi-api when the API answers on a later run.

DEAD-FEED RULE (the Aug 19 sports scar): if every API call fails, this
exits non-zero after writing what it can, so the run shows red instead
of publishing silence in green.

settlements.csv is rewritten in full each run (same pattern as
daily_highs.csv): one row per (date, station), header owned here.
"""

import csv, json, os, re, sys, urllib.request
from datetime import datetime, timedelta, timezone

from cities import CITIES

OUT = "settlements.csv"
FIELDS = ["date", "station", "city", "series", "low_f", "high_f",
          "n_markets", "n_settled", "source", "utc_offset_hours",
          "checked_utc"]

RESULTS = "results.csv"
EDGES = "edges.csv"
BASE = "https://api.elections.kalshi.com"
LOOKBACK_DAYS = 3          # a west-coast event can settle a day late
DEGREES = frozenset(range(-40, 141))   # every plausible official high


# ---------- bracket text -> integer range ----------
def settled_range(subtitle):
    """(lo, hi) integer degrees, inclusive; None end = unbounded.
    Returns None when the text cannot be parsed -- caller must skip
    loudly, never guess."""
    s = (subtitle or "").replace("°", " ").lower()
    nums = re.findall(r"-?\d+(?:\.\d+)?", s)
    if not nums:
        return None
    if " to " in s and len(nums) >= 2:
        return int(float(nums[0])), int(float(nums[1]))
    if "below" in s or "under" in s or "less" in s:
        return None, int(float(nums[0]))
    if "above" in s or "over" in s or "greater" in s or "higher" in s:
        return int(float(nums[0])), None
    if len(nums) == 1:
        return int(float(nums[0])), int(float(nums[0]))
    return None


def narrow(cands, rng, result):
    """Apply one settled market to the candidate-degree set."""
    lo, hi = rng
    inside = {d for d in cands
              if (lo is None or d >= lo) and (hi is None or d <= hi)}
    return inside if result == "yes" else cands - inside


def bounds(cands):
    """(low, high) of the remaining degrees; None on an unbounded end.
    min/max of the set is honest even if exclusions punched a hole in
    the middle: the true high is still inside [low, high]."""
    lo, hi = min(cands), max(cands)
    return (None if lo == min(DEGREES) else lo,
            None if hi == max(DEGREES) else hi)


# ---------- dates ----------
def event_code(date):
    """date -> Kalshi event date code, e.g. 2026-08-19 -> 26AUG19."""
    return date.strftime("%y%b%d").upper()


def local_dates_to_check(lon, now_utc):
    """The last LOOKBACK_DAYS completed calendar days at this station,
    per the longitude timezone estimate (same rule as poller.py)."""
    off = round(lon / 15.0)
    today = (now_utc + timedelta(hours=off)).date()
    return off, [today - timedelta(days=d)
                 for d in range(1, LOOKBACK_DAYS + 1)]


# ---------- source 1: the whole event from Kalshi ----------
def fetch_event(series, code):
    url = (f"{BASE}/trade-api/v2/markets?event_ticker={series}-{code}"
           f"&limit=200")
    req = urllib.request.Request(
        url, headers={"User-Agent": "weather-bot-personal"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r).get("markets", [])


def pin_from_event(markets, label):
    """(low, high, n_markets, n_settled) or None if nothing anchors."""
    cands, anchored, n_settled = set(DEGREES), False, 0
    for m in markets:
        status = (m.get("status") or "").lower()
        result = (m.get("result") or "").lower()
        if status not in ("settled", "finalized") or \
                result not in ("yes", "no"):
            continue
        rng = settled_range(m.get("yes_sub_title") or m.get("subtitle"))
        if rng is None:
            print(f"  {label}: cannot parse bracket "
                  f"'{m.get('yes_sub_title')}' ({m.get('ticker')}) "
                  f"- skipping that market")
            continue
        n_settled += 1
        cands = narrow(cands, rng, result)
        if result == "yes":
            anchored = True
    if not anchored:
        return None
    if not cands:
        print(f"  {label}: settled brackets CONTRADICT each other "
              f"- refusing to publish a range")
        return None
    lo, hi = bounds(cands)
    return lo, hi, len(markets), n_settled


# ---------- source 2: our own graded bets ----------
def load_edge_subtitles():
    """ticker -> subtitle, from every market scanner.py ever logged."""
    subs = {}
    if not os.path.exists(EDGES):
        return subs
    with open(EDGES) as f:
        for r in csv.DictReader(f):
            t = (r.get("market") or "").strip()
            s = (r.get("subtitle") or "").strip()
            if t and s:
                subs[t] = s
    return subs


def ticker_date(ticker):
    m = re.search(r"-(\d{2}[A-Z]{3}\d{2})-", ticker or "")
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%y%b%d").date()
    except ValueError:
        return None


def pins_from_results():
    """(date_iso, series) -> (low, high, n_markets, n_settled), built
    from results.csv market_result values (exchange truth) with ranges
    from the subtitles logged in edges.csv."""
    if not os.path.exists(RESULTS):
        return {}
    subs = load_edge_subtitles()
    facts = {}   # (date_iso, series) -> {ticker: (range, result)}
    with open(RESULTS) as f:
        for r in csv.DictReader(f):
            tick = (r.get("ticker") or "").strip()
            res = (r.get("market_result") or "").lower()
            date = ticker_date(tick)
            series = tick.split("-")[0].upper()
            if not date or series not in CITIES or \
                    res not in ("yes", "no"):
                continue
            rng = settled_range(subs.get(tick))
            if rng is None:
                print(f"  results.csv {tick}: no parseable subtitle in "
                      f"edges.csv - skipping that market")
                continue
            facts.setdefault((date.isoformat(), series), {})[tick] = \
                (rng, res)
    out = {}
    for key, mkts in facts.items():
        cands, anchored = set(DEGREES), False
        for rng, res in mkts.values():
            cands = narrow(cands, rng, res)
            if res == "yes":
                anchored = True
        if not anchored or not cands:
            continue
        lo, hi = bounds(cands)
        out[key] = (lo, hi, len(mkts), len(mkts))
    return out


# ---------- the file ----------
def read_existing():
    rows = {}
    if not os.path.exists(OUT):
        return rows
    with open(OUT) as f:
        for r in csv.DictReader(f):
            if r.get("date") and r.get("station"):
                rows[(r["date"], r["station"])] = \
                    {k: (r.get(k) or "") for k in FIELDS}
    return rows


def write_all(rows):
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for key in sorted(rows):
            w.writerow(rows[key])


def main():
    now = datetime.now(timezone.utc)
    stamp = now.isoformat(timespec="seconds")
    rows = read_existing()
    fallback = None          # built lazily, only if the API fails
    api_tried = api_ok = wrote = 0

    for series, (city, station, _lat, lon, _v) in CITIES.items():
        off, dates = local_dates_to_check(lon, now)
        for date in dates:
            iso = date.isoformat()
            key = (iso, station)
            if rows.get(key, {}).get("source") == "kalshi-api":
                continue     # settlement is final; never recomputed
            label = f"{city} {iso}"
            pin, source = None, ""
            api_tried += 1
            try:
                markets = fetch_event(series, event_code(date))
                api_ok += 1
                pin = pin_from_event(markets, label)
                source = "kalshi-api"
                if pin is None:
                    print(f"  {label}: event not settled yet "
                          f"({len(markets)} markets) - will retry")
            except Exception as e:
                print(f"  {label}: API fetch failed ({e}) "
                      f"- trying results.csv")
                if fallback is None:
                    fallback = pins_from_results()
                pin = fallback.get((iso, series))
                source = "results-csv"
            if pin is None:
                continue
            lo, hi, n_markets, n_settled = pin
            row = {"date": iso, "station": station, "city": city,
                   "series": series,
                   "low_f": "" if lo is None else lo,
                   "high_f": "" if hi is None else hi,
                   "n_markets": n_markets, "n_settled": n_settled,
                   "source": source, "utc_offset_hours": off,
                   "checked_utc": stamp}
            old = rows.get(key)
            if old and all(str(old.get(k, "")) == str(row[k])
                           for k in FIELDS if k != "checked_utc"):
                continue   # nothing new -- don't churn checked_utc
            rows[key] = row
            wrote += 1
            shown = (f"{lo}-{hi}" if lo is not None and hi is not None
                     else f"<= {hi}" if lo is None else f">= {lo}")
            print(f"{label}: settled {shown} F "
                  f"({n_settled}/{n_markets} markets, {source})")

    write_all(rows)
    print(f"{wrote} settlement row(s) written/updated, "
          f"{len(rows)} total in {OUT}")

    if api_tried and not api_ok:
        # Aug 19 scar: a dead feed must fail loudly, never publish
        # silence in green.
        print(f"DEAD FEED: all {api_tried} Kalshi API calls failed")
        sys.exit(2)


if __name__ == "__main__":
    main()
