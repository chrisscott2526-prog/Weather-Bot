"""Weather-Bot: forecast calibration.

Learns each station's forecast bias (model minus reality) from recent
history and corrects tomorrow's ensemble members before they are stored.

REBUILT Aug 5 2026 -- the honest-thermometer rewrite:

1. MEDIAN, not mean. One storm-capped day can no longer steer a city's
   correction for two weeks.
2. SETTLEMENT-PINNED ACTUALS. The bias target is what actually SETTLED
   whenever we can prove it.
3. CONFIDENCE RAMP instead of the MIN_SAMPLES cliff. Less history means
   a wider spread, which means the scanner takes fewer, safer bets in
   that city -- instead of zero correction with full confidence.
4. Ignores the ERROR/blank rows old forecast.py wrote into
   forecasts.csv, and reads all CSVs by column name so added columns
   (obs_time_utc) never break it.

UPGRADED Aug 24 2026 -- learn from the official scoreboard, not our
own thermometer:

1. THE ACTUAL IS THE OFFICIAL SETTLEMENT, whenever settlements.csv has
   the day's settled bracket (settlements.py pins it from Kalshi's own
   result fields, all 20 cities, unauthenticated). The old target was
   the METAR instrument high -- which UNDERSTATES BY DESIGN (hourly
   readings, floored, and TWC's settled max catches between-hour peaks
   the METAR misses). Learning "forecast error" against an understated
   actual mis-corrected exactly the stations the autopsy flagged: Las
   Vegas ran 3.4F below the settled number while this table said the
   correction was 1.1F. Priority of actuals now: official settled
   bracket midpoint > our own settled bets pinning the instrument >
   raw instrument. (settlements.csv is a cache of Kalshi's immutable
   settlement facts, rewritten in full each run -- not the derived-
   aggregate trap of the daily_highs scar. A settled result never
   changes, so a missing row only means "fall back", never "stale".)
2. THE SPREAD IS LEARNED TOO, not just the bias. The old spread_scale
   only widened when history was thin -- with 14 days of history every
   station sat at x1.00 forever, and the raw GFS member spread is
   narrower than the real error: the scanner claimed ~50% and won 30%.
   Now each station's realized error spread (robust sigma of residuals
   after bias removal) becomes a TARGET SIGMA, and calibrate_members
   widens the member spread to match it. Members are never narrowed
   (scale floors at x1.0): we may claim less confidence than the raw
   ensemble, never more.

FIXED Aug 26 2026 -- the feedback loop:

Rows in forecasts.csv are the CALIBRATED forecast (forecast.py stores
members after the bias shift). This table used to learn "forecast
error" from those corrected rows and then apply what it learned to
the next night's RAW members as if it were the whole correction --
the correction already inside each history row was thrown away. At a
station with a stable raw bias B the applied correction stalls near
B/2 (learned error = B - correction, applied as the new correction):
San Francisco was prescribed -3.9F while its corrected forecasts
still ran +3.6F hot -- true raw bias ~7F, half-corrected forever.
Now forecast.py records bias_applied in every row, and this table
reconstructs each night's RAW error as
    (stored corrected forecast - actual) + bias_applied
so the learned bias converges to the forecast's true bias. Old rows
have no bias_applied column; they are read as 0 -- exactly the number
the old code assumed -- and age out of the 14-day window naturally.
Also: the MAX_ABS_BIAS sanity clamp now prints LOUDLY when it binds
instead of capping in silence. It was written for corrupt-join
protection, but a coastal station's real bias can reach it -- if the
same station's warning keeps appearing run after run, the bias is
real and the clamp is costing accuracy: say so to the owner instead
of raising it on vibes.

Interface (unchanged): forecast.py calls
    members, bias = calibrate_members(station, members)
which returns bias-shifted, spread-matched members plus the bias used.
compute_calibration() now returns station -> (bias_f, sigma_f, n):
the third-of-three is still n, but the middle value is the target
error sigma in DEGREES F, no longer a unitless scale. scanner.py logs
it in its own sigma_f column (edges.csv's old spread_scale column is
retired, kept only so old rows keep their meaning).
Run standalone to print the calibration table.
"""

import csv, os, re
from datetime import datetime, timedelta, timezone
from statistics import median

from cities import STATIONS
from csvio import is_morning_row
from highs import day_high_map

FORECASTS = "forecasts.csv"
RESULTS = "results.csv"
SETTLEMENTS = "settlements.csv"

WINDOW_DAYS = 14          # how far back to learn from
MAX_ABS_BIAS = 6.0        # sanity clamp; a "bias" beyond this is a data bug

# Spread targets, all in degrees F. MIN_SIGMA: a settled bracket is 2F
# wide, so the actual is only known to ~half a bracket -- claiming a
# tighter error than 1F would be inventing precision. DEFAULT_SIGMA:
# no history at all = very wide = few bets (the old x2.5 ramp rung).
MIN_SIGMA = 1.0
MAX_SIGMA = 6.0
DEFAULT_SIGMA = 4.0
MIN_RAW_SIGMA = 0.3       # guard against a near-zero raw member spread
# (No separate cap on the widening ratio: the scaling is
# self-normalizing -- the adjusted spread lands AT sigma_f, which is
# itself capped at MAX_SIGMA -- and real raw spreads of 0.5F with
# realized errors of 2-4F legitimately need x4-x8.)


# ---------- settlement truth ----------
def settlement_actuals():
    """(date, station) -> (lo_f, hi_f): the OFFICIAL settled range from
    settlements.csv -- Kalshi's own result fields, pinned by
    settlements.py for all 20 cities. A None end = unbounded tail.
    This is the thermometer that pays; it outranks the instrument."""
    out = {}
    if not os.path.exists(SETTLEMENTS):
        return out
    with open(SETTLEMENTS) as f:
        for r in csv.DictReader(f):
            d = (r.get("date") or "").strip()
            sid = (r.get("station") or "").strip()
            if not d or not sid:
                continue
            lo = (r.get("low_f") or "").strip()
            hi = (r.get("high_f") or "").strip()
            try:
                lo_v = float(lo) if lo else None
                hi_v = float(hi) if hi else None
            except ValueError:
                continue
            if lo_v is None and hi_v is None:
                continue
            out[(d, sid)] = (lo_v, hi_v)
    return out


def settled_windows():
    """(date, city) -> (lo, hi): a 2-degree window the day's high provably
    landed in, from our own settled bets. A market resolved YES when we
    won a YES or lost a NO. B-tickers only; T (tail) tickers are
    ambiguous about direction and are skipped. Fallback only -- used
    when settlements.csv has no row for the day."""
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
    """(date, station) -> (forecast median, bias_applied). Skips
    ERROR/blank rows. Keeps the LAST forecast logged for a date
    (rerun overwrites).

    bias_applied (Aug 26 2026) is the correction forecast.py already
    subtracted from that row's members before storing it. Adding it
    back turns the stored corrected forecast into the RAW forecast, so
    the bias table measures the raw model's error -- the feedback-loop
    fix. Rows from before the column existed read as 0.0, which is
    exactly what the old code assumed; they age out of the window.

    NIGHT ROWS ONLY (Aug 20 2026): this bias table corrects the
    night-before forecast, and it feeds BOTH strategies -- so it must
    keep measuring the night forecast's error, not the (easier)
    same-day error. Morning-refresh rows (told apart by timestamp via
    csvio.is_morning_row) are skipped here; nightly rows -- including
    runs that slipped past UTC midnight -- are kept."""
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
            if is_morning_row(d, r.get("fetched_utc")):
                continue   # same-day morning refresh: not this table's job
            b = (r.get("bias_applied") or "").strip()
            try:
                hist[(d, sid)] = (float(v), float(b) if b else 0.0)
            except ValueError:
                continue
    return hist


def load_actuals():
    """(date, station) -> observed high (instrument reading -- outranked
    by settlement wherever settlement exists). Computed directly from
    the raw temps_log.csv by highs.py -- the single source of truth for
    daily highs since Aug 21 2026; the derived daily_highs.csv lagged
    its raw source in two money-relevant incidents and is no longer
    read."""
    return day_high_map()


def resolve_actual(d, sid, official, instrument, windows):
    """The day's high for (date, station), in order of trust:
    1. Official settled bracket, both bounds known -> its midpoint.
    2. Official settled TAIL (one bound) -> the instrument reading
       clamped into the proven range; no instrument reading = skip
       (never guess how far past the bound the high ran).
    3. Our own settled bet pinning the day -> instrument overridden
       into that 2-degree window (the pre-Aug-24 rule, kept as
       fallback for days settlements.csv is missing).
    4. Raw instrument reading.
    Returns (actual, source) or (None, None)."""
    off = official.get((d, sid))
    inst = instrument.get((d, sid))
    if off:
        lo, hi = off
        if lo is not None and hi is not None:
            return (lo + hi) / 2.0, "settlement"
        if inst is not None:
            if lo is not None:
                return max(inst, lo), "settlement-tail"
            return min(inst, hi), "settlement-tail"
        return None, None
    if inst is None:
        return None, None
    city = STATIONS.get(sid, "")
    win = windows.get((d, city))
    if win:
        lo, hi = win
        if not (lo - 0.25 <= inst <= hi + 0.25):
            return (lo + hi) / 2.0, "own-bet"
    return inst, "instrument"


# ---------- the model ----------
def compute_calibration():
    """station -> (bias_f, sigma_f, n_samples).
    bias_f = median(RAW forecast - actual): positive means the model
    runs hot, so members get shifted DOWN by bias_f. The raw forecast
    is reconstructed per row as stored (corrected) forecast +
    bias_applied -- the feedback-loop fix of Aug 26 2026; old rows
    without bias_applied contribute their corrected error unchanged.
    sigma_f = the TARGET error spread in degrees F: a robust sigma
    (1.4826 x median absolute deviation) of the residual errors after
    the bias is removed, floored by the confidence ramp when history
    is thin. calibrate_members widens the member spread to match it."""
    windows = settled_windows()
    official = settlement_actuals()
    forecasts = load_forecast_history()
    instrument = load_actuals()
    cutoff = (datetime.now(timezone.utc).date()
              - timedelta(days=WINDOW_DAYS)).isoformat()

    errors = {}    # station -> [raw forecast - actual]
    sources = {}   # how each actual was located, for the honest printout
    for (d, sid), (fc, applied) in forecasts.items():
        if d < cutoff:
            continue
        act, src = resolve_actual(d, sid, official, instrument, windows)
        if act is None:
            continue
        err = (fc - act) + applied     # undo the row's own correction
        if abs(err) <= 25:          # discard corrupt joins outright
            errors.setdefault(sid, []).append(err)
            sources[src] = sources.get(src, 0) + 1

    cal = {}
    for sid in STATIONS:
        errs = errors.get(sid, [])
        n = len(errs)
        if n < 2:
            # no usable history: no correction, maximum humility
            cal[sid] = (0.0, DEFAULT_SIGMA, n)
            continue
        bias = median(errs)
        resid = [e - bias for e in errs]
        sigma = 1.4826 * median(abs(r) for r in resid)
        if n >= 10:
            floor = MIN_SIGMA
        elif n >= 5:
            floor = 2.0            # thin history = stay wide
        else:
            floor = 3.0
        sigma = max(floor, min(MAX_SIGMA, sigma))
        if abs(bias) > MAX_ABS_BIAS:
            # The clamp exists to stop corrupt joins, but a real coastal
            # bias can hit it too. Capping in silence would hide exactly
            # the station that needs the most correction -- say so.
            print(f"WARNING {STATIONS.get(sid, sid)}: learned bias "
                  f"{bias:+.2f}F exceeds the +/-{MAX_ABS_BIAS:.0f}F "
                  f"sanity clamp -- applying {MAX_ABS_BIAS:.0f}F. If "
                  f"this repeats daily the bias is real, not a data "
                  f"bug, and the clamp is costing accuracy.")
        bias = max(-MAX_ABS_BIAS, min(MAX_ABS_BIAS, bias))
        cal[sid] = (round(bias, 2), round(sigma, 2), n)
    return cal, sources


_CAL_CACHE = None


def _cal_table():
    global _CAL_CACHE
    if _CAL_CACHE is None:
        _CAL_CACHE = compute_calibration()[0]
    return _CAL_CACHE


def calibrate_members(station, members):
    """Shift members down by the learned bias, then widen their spread
    (around the median) until it matches the station's realized error
    sigma. Members are never narrowed: scale floors at x1.0 -- we may
    claim less confidence than the raw ensemble, never more.
    Returns (adjusted_members, bias_used)."""
    bias, sigma_t, _n = _cal_table().get(station, (0.0, DEFAULT_SIGMA, 0))
    if not members:
        return members, bias
    shifted = [m - bias for m in members]
    med = median(shifted)
    raw_sigma = (sum((m - med) ** 2 for m in shifted)
                 / len(shifted)) ** 0.5
    scale = max(1.0, sigma_t / max(raw_sigma, MIN_RAW_SIGMA))
    adjusted = [round(med + (m - med) * scale, 1) for m in shifted]
    return adjusted, bias


def main():
    cal, sources = compute_calibration()
    for sid in sorted(cal, key=lambda s: STATIONS[s]):
        bias, sigma, n = cal[sid]
        print(f"cal {STATIONS[sid]}: bias={bias:+.2f}F "
              f"target sigma={sigma:.2f}F (n={n})")
    total = sum(sources.values())
    if total:
        parts = ", ".join(f"{k}={v}" for k, v in sorted(sources.items()))
        print(f"actuals located by: {parts} ({total} samples; "
              f"settlement outranks the instrument wherever it exists)")


if __name__ == "__main__":
    main()
