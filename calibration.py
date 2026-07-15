"""
calibration.py — Weather-Bot calibration (stdlib only, no pip installs needed).
Matched to forecast.py's SITES keys (KNYC, KMIA, KDEN, KLAX, KPHL, KAUS, KMDW).

Fix 1: rolling per-station bias (mean forecast - actual, last 14 days).
       Actuals come from daily_highs.csv if usable, else Open-Meteo archive.
Fix 2: ensemble spread inflation (raw GFS is underdispersive).

Fails safe: any missing file, missing column, or network error -> bias 0.0,
spread inflation still applies. Can never crash the nightly run.
"""

import csv, json, urllib.request
from datetime import date, timedelta
from statistics import median, mean

STATIONS = {
    "KNYC": (40.7794, -73.9692),
    "KMIA": (25.7906, -80.3164),
    "KDEN": (39.8467, -104.6562),
    "KLAX": (33.9382, -118.3866),
    "KPHL": (39.8683, -75.2311),
    "KAUS": (30.1945, -97.6699),
    "KMDW": (41.7842, -87.7553),
}
NAMES = {
    "KNYC": "New York City", "KMIA": "Miami", "KDEN": "Denver",
    "KLAX": "Los Angeles", "KPHL": "Philadelphia", "KAUS": "Austin",
    "KMDW": "Chicago",
}

BIAS_WINDOW_DAYS = 14
MIN_MATCHED_DAYS = 5
MAX_ABS_BIAS = 4.0
SPREAD_INFLATE = 1.30
FORECAST_LOG = "forecasts.csv"
ACTUALS_LOG = "daily_highs.csv"
UA = {"User-Agent": "weather-bot-personal"}

DATE_COLS = ("date", "target_date", "forecast_date", "day")
SITE_COLS = ("station", "site", "city", "location", "ticker")
FCST_COLS = ("forecast_high_f",)
HIGH_COLS = ("high_f", "actual_high_f", "high", "tmax_f", "temp_high_f")


def _rows(path):
    try:
        with open(path, newline="") as f:
            return list(csv.DictReader(f))
    except Exception:
        return []


def _pick(row_keys, options):
    for o in options:
        if o in row_keys:
            return o
    return None


def _iso(d):
    try:
        return date.fromisoformat(str(d).strip()[:10])
    except Exception:
        return None


def _matches(value, station):
    v = str(value).strip()
    return v.upper() == station or v == NAMES.get(station, "")


def _local_actuals(station):
    """{date: high_f} from daily_highs.csv, if columns are recognizable."""
    rows = _rows(ACTUALS_LOG)
    if not rows:
        return {}
    keys = rows[0].keys()
    dc, sc, hc = _pick(keys, DATE_COLS), _pick(keys, SITE_COLS), _pick(keys, HIGH_COLS)
    if not (dc and hc):
        return {}
    out = {}
    for r in rows:
        if sc and not _matches(r.get(sc, ""), station):
            continue
        d = _iso(r.get(dc))
        try:
            out[d] = float(r.get(hc))
        except (TypeError, ValueError):
            continue
    out.pop(None, None)
    return out


def _api_actuals(station, start, end):
    """{date: high_f} from Open-Meteo archive at the station coords."""
    lat, lon = STATIONS[station]
    url = ("https://archive-api.open-meteo.com/v1/archive"
           f"?latitude={lat}&longitude={lon}"
           f"&start_date={start}&end_date={end}"
           "&daily=temperature_2m_max&temperature_unit=fahrenheit&timezone=auto")
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.load(r).get("daily", {})
    out = {}
    for t, v in zip(d.get("time", []), d.get("temperature_2m_max", [])):
        if v is not None:
            out[_iso(t)] = float(v)
    out.pop(None, None)
    return out


def station_bias(station):
    """Rolling mean(forecast - actual) F. Positive = warm bias. 0.0 if unsure."""
    rows = _rows(FORECAST_LOG)
    if not rows:
        return 0.0
    keys = rows[0].keys()
    dc, sc, fc = _pick(keys, DATE_COLS), _pick(keys, SITE_COLS), _pick(keys, FCST_COLS)
    if not (dc and fc):
        return 0.0
    cutoff = date.today() - timedelta(days=BIAS_WINDOW_DAYS)
    fcsts = {}
    for r in rows:
        if sc and not _matches(r.get(sc, ""), station):
            continue
        d = _iso(r.get(dc))
        if d is None or d < cutoff or d >= date.today():
            continue
        try:
            fcsts[d] = float(r.get(fc))
        except (TypeError, ValueError):
            continue
    if not fcsts:
        return 0.0
    actuals = _local_actuals(station)
    matched = [(fcsts[d], actuals[d]) for d in fcsts if d in actuals]
    if len(matched) < MIN_MATCHED_DAYS:
        try:
            api = _api_actuals(station, min(fcsts), max(fcsts))
        except Exception:
            api = {}
        actuals = {**api, **actuals}
        matched = [(fcsts[d], actuals[d]) for d in fcsts if d in actuals]
    if len(matched) < MIN_MATCHED_DAYS:
        return 0.0
    b = mean(f - a for f, a in matched)
    return max(-MAX_ABS_BIAS, min(MAX_ABS_BIAS, b))


def calibrate_members(station, members):
    """
    station: SITES key, e.g. "KNYC".
    members: list of raw ensemble highs (floats or strings).
    Returns (calibrated_members, bias_applied).
    """
    try:
        m = [float(x) for x in members]
    except (TypeError, ValueError):
        return members, 0.0
    if not m:
        return members, 0.0
    try:
        bias = station_bias(station)
    except Exception:
        bias = 0.0
    m = [x - bias for x in m]
    med = median(m)
    m = [round(med + (x - med) * SPREAD_INFLATE, 1) for x in m]
    return m, bias

