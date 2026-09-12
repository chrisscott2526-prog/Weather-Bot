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

PER-MODEL BIAS (Sep 12 2026) -- one thermostat cannot fix two rooms:

The pool is two models (GFS 31 members, ECMWF 51), and at several
stations they carry OPPOSITE biases -- at New Orleans raw ECMWF ran
~5F cold while raw GFS ran hot. The single per-station bias is
learned from the pooled median, which ECMWF dominates 51:31, so the
correction that fixed ECMWF shoved every GFS member ~3.5F further
UP: on Sep 12 all 31 GFS members landed in "95 or above" (39% of the
pool voting for a bracket the NWS forecast, yesterday's settlement,
and the market all called wrong). The median stayed honest while the
top BRACKET became a phantom cluster -- the two-humped-pool disease.
The gates (MIN_PICK_PROB, the price band) blocked the buys; the
votes themselves were broken.

The fix: each member is now shifted by ITS OWN MODEL's learned bias
(per station), measured from the member_models tags forecasts.csv
has carried since Aug 31 2026. A model needs MIN_MODEL_N nights of
tagged, settled history at a station to earn its own number;
otherwise its members fall back to the pooled per-station bias
(exactly the old behavior). The pooled bias and target sigma are
still learned as before -- they remain the fallback and the display
number -- and the spread widening is unchanged (it now engages more
often, honestly, because de-splitting the pool shrinks its raw
sigma).

bias_applied in forecasts.csv grows up with it: when tags are
usable the writer stores the EXACT per-model corrections as
    pool:-3.46|gfs:-0.85|ecmwf:-5.52
where each number is (raw median - stored median) for that slice --
pool for the whole row, one tag per model. Exact means exact: it is
measured after the spread widening, so reconstruction never has to
guess the widening scale. Old scalar rows keep their old meaning
(one shift for everyone) and their per-model reconstruction is
approximate only by the old widening displacement, which ages out
of the window with them.

Interface: forecast.py calls
    members, bias = calibrate_members(station, members, tags)
which returns bias-shifted, spread-matched members plus the
bias_applied value to store (a scalar when tags are unusable, the
tagged string above when they are). compute_calibration() still
returns station -> (bias_f, sigma_f, n) -- the POOLED table, the
shape scanner.py displays -- plus the sources dict, unchanged.
compute_calibration_full() adds the per-model table on top.
Run standalone to print both tables.
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
MIN_MODEL_N = 4           # tagged settled nights a model needs at a
                          # station before it earns its OWN bias there;
                          # under that, its members use the pooled bias

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
def parse_applied(raw):
    """bias_applied field -> (pool_applied, {model: applied}) or
    (None, None) when unparseable.

    Scalar (pre-Sep-12 rows): one shift for everyone -- the pool value
    and every model's value are that number.
    Tagged 'pool:-3.4|gfs:-0.9|ecmwf:-5.5' (Sep 12 2026): the exact
    correction subtracted from each slice's median, widening included,
    so adding it back recovers the raw median with no guesswork."""
    raw = (raw or "").strip()
    if not raw:
        return 0.0, {}
    if ":" not in raw:
        try:
            return float(raw), {}
        except ValueError:
            return None, None
    pool, per = None, {}
    try:
        for part in raw.split("|"):
            k, v = part.split(":", 1)
            k = k.strip()
            v = float(v)
            if k == "pool":
                pool = v
            else:
                per[k] = v
    except ValueError:
        return None, None
    if pool is None:
        # a tagged value without its pool entry is a malformed write
        return None, None
    return pool, per


def model_medians(members_raw, tags_raw):
    """{model: median of its stored members} from the row's pipe fields.
    Empty when tags are absent or misaligned -- never guessed."""
    if not members_raw or not tags_raw:
        return {}
    try:
        vals = [float(x) for x in members_raw.split("|") if x != ""]
    except ValueError:
        return {}
    tags = [t for t in tags_raw.split("|") if t != ""]
    if not vals or len(vals) != len(tags):
        return {}
    by = {}
    for v, t in zip(vals, tags):
        by.setdefault(t, []).append(v)
    return {t: median(vs) for t, vs in by.items()}


def load_forecast_history():
    """(date, station) -> (forecast median, pool bias_applied,
    {model: (stored median, applied)}). Skips ERROR/blank rows. Keeps
    the LAST forecast logged for a date (rerun overwrites).

    bias_applied (Aug 26 2026) is the correction forecast.py already
    subtracted from that row before storing it. Adding it back turns
    the stored corrected forecast into the RAW forecast, so the bias
    table measures the raw model's error -- the feedback-loop fix.
    Rows from before the column existed read as 0.0, which is exactly
    what the old code assumed; they age out of the window. Since
    Sep 12 2026 the field carries per-model corrections too (see
    parse_applied); on older scalar rows every model shares the one
    number.

    The per-model dict is filled only when the row's member_models
    tags are present and aligned (Aug 31 2026 onward) -- a row
    without honest tags contributes to the pooled table only.

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
            pool_applied, per_applied = parse_applied(r.get("bias_applied"))
            if pool_applied is None:
                continue
            try:
                fc = float(v)
            except ValueError:
                continue
            meds = model_medians(r.get("members"), r.get("member_models"))
            per = {}
            for mdl, mm in meds.items():
                per[mdl] = (mm, per_applied.get(mdl, pool_applied))
            hist[(d, sid)] = (fc, pool_applied, per)
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
def _clamped(bias, label):
    """MAX_ABS_BIAS with the loud warning -- shared by both tables."""
    if abs(bias) > MAX_ABS_BIAS:
        # The clamp exists to stop corrupt joins, but a real coastal
        # bias can hit it too. Capping in silence would hide exactly
        # the station that needs the most correction -- say so.
        print(f"WARNING {label}: learned bias "
              f"{bias:+.2f}F exceeds the +/-{MAX_ABS_BIAS:.0f}F "
              f"sanity clamp -- applying {MAX_ABS_BIAS:.0f}F. If "
              f"this repeats daily the bias is real, not a data "
              f"bug, and the clamp is costing accuracy.")
    return max(-MAX_ABS_BIAS, min(MAX_ABS_BIAS, bias))


def compute_calibration_full():
    """(pooled table, per-model table, sources).
    pooled: station -> (bias_f, sigma_f, n_samples) -- exactly the old
    compute_calibration output, learned from the pooled median exactly
    as before. It stays the fallback for untagged members and models
    with thin history, and the number scanner.py displays.
    per-model: station -> {model: (bias_f, n)} for models with at
    least MIN_MODEL_N tagged settled nights at that station. bias_f =
    median(that model's RAW median - actual): positive means the model
    runs hot there, so its members get shifted DOWN by bias_f.
    sigma_f = the TARGET error spread in degrees F: a robust sigma
    (1.4826 x median absolute deviation) of the pooled residuals after
    the pooled bias is removed, floored by the confidence ramp when
    history is thin. calibrate_members widens the member spread to
    match it."""
    windows = settled_windows()
    official = settlement_actuals()
    forecasts = load_forecast_history()
    instrument = load_actuals()
    cutoff = (datetime.now(timezone.utc).date()
              - timedelta(days=WINDOW_DAYS)).isoformat()

    errors = {}    # station -> [raw pooled forecast - actual]
    merrors = {}   # (station, model) -> [raw model median - actual]
    sources = {}   # how each actual was located, for the honest printout
    for (d, sid), (fc, applied, per) in forecasts.items():
        if d < cutoff:
            continue
        act, src = resolve_actual(d, sid, official, instrument, windows)
        if act is None:
            continue
        err = (fc - act) + applied     # undo the row's own correction
        if abs(err) <= 25:          # discard corrupt joins outright
            errors.setdefault(sid, []).append(err)
            sources[src] = sources.get(src, 0) + 1
        for mdl, (mm, m_applied) in per.items():
            m_err = (mm - act) + m_applied
            if abs(m_err) <= 25:
                merrors.setdefault((sid, mdl), []).append(m_err)

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
        bias = _clamped(bias, STATIONS.get(sid, sid))
        cal[sid] = (round(bias, 2), round(sigma, 2), n)

    mcal = {}
    for (sid, mdl), errs in merrors.items():
        n = len(errs)
        if n < MIN_MODEL_N:
            continue   # too thin to split: those members use the pool
        bias = _clamped(median(errs),
                        f"{STATIONS.get(sid, sid)} [{mdl}]")
        mcal.setdefault(sid, {})[mdl] = (round(bias, 2), n)
    return cal, mcal, sources


def compute_calibration():
    """station -> (bias_f, sigma_f, n_samples), plus sources -- the
    POOLED table in its historical shape (scanner.py displays it).
    The per-model table lives in compute_calibration_full()."""
    cal, _mcal, sources = compute_calibration_full()
    return cal, sources


_CAL_CACHE = None


def _cal_tables():
    global _CAL_CACHE
    if _CAL_CACHE is None:
        cal, mcal, _src = compute_calibration_full()
        _CAL_CACHE = (cal, mcal)
    return _CAL_CACHE


def calibrate_members(station, members, tags=None):
    """Shift each member down by its own model's learned bias (per-model
    table; the pooled station bias for untagged members and models
    with thin history), then widen the pool's spread (around the
    median) until it matches the station's realized error sigma.
    Members are never narrowed: scale floors at x1.0 -- we may claim
    less confidence than the raw ensemble, never more. Member ORDER is
    preserved so the member_models tags stay honest.

    Returns (adjusted_members, bias_applied_value): a scalar when tags
    are missing or misaligned (the pre-Sep-12 behavior), else the
    exact tagged record 'pool:...|gfs:...|ecmwf:...' where each number
    is (raw median - stored median) for that slice, widening included
    -- what parse_applied inverts with no guesswork."""
    cal, mcal = _cal_tables()
    bias, sigma_t, _n = cal.get(station, (0.0, DEFAULT_SIGMA, 0))
    if not members:
        return members, bias
    per = mcal.get(station, {})
    tags_ok = bool(tags) and len(tags) == len(members)
    if tags_ok:
        shifts = [per.get(t, (bias,))[0] for t in tags]
    else:
        shifts = [bias] * len(members)
    shifted = [m - s for m, s in zip(members, shifts)]
    med = median(shifted)
    raw_sigma = (sum((m - med) ** 2 for m in shifted)
                 / len(shifted)) ** 0.5
    scale = max(1.0, sigma_t / max(raw_sigma, MIN_RAW_SIGMA))
    adjusted = [round(med + (m - med) * scale, 1) for m in shifted]
    if not tags_ok:
        return adjusted, bias
    parts = [f"pool:{median(members) - median(adjusted):.2f}"]
    seen = []
    for t in tags:
        if t not in seen:
            seen.append(t)
    for t in seen:
        raw_mm = median(m for m, tg in zip(members, tags) if tg == t)
        sto_mm = median(a for a, tg in zip(adjusted, tags) if tg == t)
        parts.append(f"{t}:{raw_mm - sto_mm:.2f}")
    return adjusted, "|".join(parts)


def main():
    cal, mcal, sources = compute_calibration_full()
    for sid in sorted(cal, key=lambda s: STATIONS[s]):
        bias, sigma, n = cal[sid]
        per = mcal.get(sid, {})
        extra = "".join(
            f"  {mdl}={b:+.2f}F(n={mn})"
            for mdl, (b, mn) in sorted(per.items()))
        print(f"cal {STATIONS[sid]}: bias={bias:+.2f}F "
              f"target sigma={sigma:.2f}F (n={n}){extra}")
    total = sum(sources.values())
    if total:
        parts = ", ".join(f"{k}={v}" for k, v in sorted(sources.items()))
        print(f"actuals located by: {parts} ({total} samples; "
              f"settlement outranks the instrument wherever it exists)")


if __name__ == "__main__":
    main()
