"""Weather-Bot: forecast calibration.

Learns each station's forecast bias (model minus reality) from recent
history and corrects tomorrow's ensemble members before they are stored.

REBUILT Aug 5 2026 -- the honest-thermometer rewrite:

1. MEDIAN, not mean. One storm-capped day can no longer steer a city's
   correction for two weeks.
2. SETTLEMENT-PINNED ACTUALS. The bias target is what actually SETTLED
   whenever we can prove it. Any of our own bets that resolved YES pins
   the day's high inside that bracket (results.csv, B-tickers only --
   tail tickers are ambiguous). When the poller's instrument reading
   disagrees with a settled bracket, the settlement wins: it is the only
   thermometer that pays.
3. CONFIDENCE RAMP instead of the MIN_SAMPLES cliff. Less history means
   a wider spread, which means the scanner takes fewer, safer bets in
   that city -- instead of zero correction with full confidence.
4. Ignores the ERROR/blank rows old forecast.py wrote into
   forecasts.csv, and reads all CSVs by column name so added columns
   (obs_time_utc) never break it.

Interface (unchanged): forecast.py calls
    members, bias = calibrate_members(station, members)
which returns bias-shifted, spread-scaled members plus the bias used.
Run standalone to print the calibration table.
"""

import csv, os, re
from datetime import datetime, timedelta, timezone
from statistics import median

from cities import STATIONS

FORECASTS = "forecasts.csv"
HIGHS = "daily_highs.csv"
RESULTS = "results.csv"

WINDOW_DAYS = 14          # how far back to learn from
MAX_ABS_BIAS = 6.0        # sanity clamp; a "bias" beyond this is a data bug


# ---------- settlement truth ----------
def settled_windows():
    """(date, city) -> (lo, hi): a 2-degree window the day's high provably
    landed in, from our own settled bets. A market resolved YES when we
    won a YES or lost a NO. B-tickers only; T (tail) tickers are
    ambiguous about direction and are skipped."""
    out = {}
    if not os.path.exists(RESULTS):
        return out
    with open(RESULTS) as f:
        for r in csv.DictReader(f):
            act = (r.get("action") or r.get("side") or "").upper()
            res = (r.get("result") or "").upper()
            if not ((act == "YES" and res == "WIN") or
                    (act == "NO" and res == "LOSS")):
                continue
            tick = r.get("ticker", "")
            m = re.search(r"-(\d{2}[A-Z]{3}\d{2})-B(\d+(?:\.5)?)$", tick)
            if not m:
                continue
            try:
                date = datetime.strptime(
                    m.group(1), "%y%b%d").date().isoformat()
            except ValueError:
                continue
            lo = float(m.group(2)) - 0.5
            city = (r.get("city") or "").strip()
            if city:
                out[(date, city)] = (lo, lo + 1.0)
    return out


# ---------- history ----------
def load_forecast_history():
    """(date, station) -> forecast median. Skips ERROR/blank rows.
    Keeps the LAST forecast logged for a date (rerun overwrites)."""
    hist = {}
    if not os.path.exists(FORECASTS):
        return hist
    with open(FORECASTS) as f:
        for r in csv.DictReader(f):
            d = (r.get("forecast_date") or "").strip()
            sid = (r.get("station") or "").strip()
            v = (r.get("forecast_high_f") or "").strip()
            if not d or not sid or v in ("", "ERROR"):
                continue
            try:
                hist[(d, sid)] = float(v)
            except ValueError:
                continue
    return hist


def load_actuals():
    """(date, station) -> observed high from the poller (instrument
    reading -- may be corrected by settlement below)."""
    acts = {}
    if not os.path.exists(HIGHS):
        return acts
    with open(HIGHS) as f:
        for r in csv.DictReader(f):
            d = (r.get("date") or "").strip()
            sid = (r.get("station") or "").strip()
            v = (r.get("high_f") or "").strip()
            if not d or not sid or not v:
                continue
            try:
                acts[(d, sid)] = float(v)
            except ValueError:
                continue
    return acts


# ---------- the model ----------
def compute_calibration():
    """station -> (bias_f, spread_scale, n_samples).
    bias_f = median(forecast - actual): positive means the model runs hot,
    so members get shifted DOWN by bias_f. spread_scale widens the member
    spread when history is thin."""
    windows = settled_windows()
    forecasts = load_forecast_history()
    actuals = load_actuals()
    cutoff = (datetime.now(timezone.utc).date()
              - timedelta(days=WINDOW_DAYS)).isoformat()

    errors = {}   # station -> [forecast - actual]
    for (d, sid), fc in forecasts.items():
        if d < cutoff:
            continue
        act = actuals.get((d, sid))
        if act is None:
            continue
        # settlement beats the instrument when they disagree
        city = STATIONS.get(sid, "")
        win = windows.get((d, city))
        if win:
            lo, hi = win
            if not (lo - 0.25 <= act <= hi + 0.25):
                act = (lo + hi) / 2.0
        err = fc - act
        if abs(err) <= 25:          # discard corrupt joins outright
            errors.setdefault(sid, []).append(err)

    cal = {}
    for sid in STATIONS:
        errs = errors.get(sid, [])
        n = len(errs)
        if n >= 10:
            bias, scale = median(errs), 1.0
        elif n >= 5:
            bias, scale = median(errs), 1.3
        elif n >= 2:
            bias, scale = median(errs), 1.8
        else:
            bias, scale = 0.0, 2.5   # no history = wide spread = few bets
        bias = max(-MAX_ABS_BIAS, min(MAX_ABS_BIAS, bias))
        cal[sid] = (round(bias, 2), scale, n)
    return cal


_CAL_CACHE = None


def calibrate_members(station, members):
    """Shift members down by the learned bias and widen the spread by the
    confidence scale. Returns (adjusted_members, bias_used)."""
    global _CAL_CACHE
    if _CAL_CACHE is None:
        _CAL_CACHE = compute_calibration()
    bias, scale, _n = _CAL_CACHE.get(station, (0.0, 2.5, 0))
    if not members:
        return members, bias
    shifted = [m - bias for m in members]
    med = median(shifted)
    adjusted = [round(med + (m - med) * scale, 1) for m in shifted]
    return adjusted, bias


def main():
    cal = compute_calibration()
    for sid in sorted(cal, key=lambda s: STATIONS[s]):
        bias, scale, n = cal[sid]
        print(f"cal {STATIONS[sid]}: bias={bias:+.2f}F "
              f"spread x{scale:.2f} (n={n})")


if __name__ == "__main__":
    main()


