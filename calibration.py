"""
calibration.py — drop-in calibration for Weather-Bot (chrisscott2526-prog/Weather-Bot)

Fixes two documented, replicated problems with raw GFS ensembles:
  1) Systematic station bias (your observed slight warm bias) —
     corrected with a rolling mean(forecast - actual) over the last
     14 matched days, actuals pulled from Open-Meteo's archive at the
     EXACT Kalshi settlement stations (Central Park, Midway, Camp
     Mabry, etc. — not "the city").
  2) Underdispersion (31 members cluster too tight, making the
     scanner overconfident on center brackets) — corrected by
     inflating member spread around the median by SPREAD_INFLATE.

No other file changes needed. scanner.py automatically inherits the
calibrated members. Bias engages once >= MIN_MATCHED_DAYS of logged
forecasts can be matched to observed highs (your week of logs means
it engages on first run).
"""

import requests
import pandas as pd
import numpy as np
from datetime import date, timedelta

# Kalshi settlement stations (NWS CLI sites). Exact coords matter —
# your $20 NYC loss was a settlement-source mismatch. These are the
# stations Kalshi actually settles on.
STATIONS = {
    "NYC":  (40.779, -73.969),   # Central Park (KNYC)
    "MIA":  (25.791, -80.316),   # Miami Intl (KMIA)
    "DEN":  (39.847, -104.656),  # Denver Intl (KDEN)
    "LAX":  (33.938, -118.389),  # Los Angeles Intl (KLAX)
    "PHIL": (39.873, -75.227),   # Philadelphia Intl (KPHL)
    "AUS":  (30.321, -97.760),   # Camp Mabry (KATT)
    "CHI":  (41.786, -87.752),   # Midway (KMDW)
}

BIAS_WINDOW_DAYS = 14      # rolling window for bias estimate
MIN_MATCHED_DAYS = 5       # minimum matched days before trusting bias
MAX_ABS_BIAS     = 4.0     # sanity clamp on correction, degrees F
SPREAD_INFLATE   = 1.30    # standard inflation for underdispersive GFS

# ---- Adjust ONLY these three lines if your log differs ----
FORECAST_LOG = "forecasts.csv"
COL_DATE, COL_CITY, COL_FCST = "date", "city", "forecast_high_f"
# -----------------------------------------------------------


def _actual_highs(city, start, end):
    """Observed daily max temps (F) from Open-Meteo archive, {date: temp}."""
    lat, lon = STATIONS[city]
    url = (
        "https://archive-api.open-meteo.com/v1/archive"
        f"?latitude={lat}&longitude={lon}"
        f"&start_date={start}&end_date={end}"
        "&daily=temperature_2m_max&temperature_unit=fahrenheit&timezone=auto"
    )
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    d = r.json().get("daily", {})
    return dict(zip(d.get("time", []), d.get("temperature_2m_max", [])))


def station_bias(city):
    """Rolling mean(forecast - actual) in F. Positive = warm bias. 0.0 if not enough data."""
    try:
        log = pd.read_csv(FORECAST_LOG)
    except FileNotFoundError:
        return 0.0
    log = log[log[COL_CITY] == city].copy()
    if log.empty:
        return 0.0
    log[COL_DATE] = pd.to_datetime(log[COL_DATE]).dt.date
    cutoff = date.today() - timedelta(days=BIAS_WINDOW_DAYS)
    log = log[(log[COL_DATE] >= cutoff) & (log[COL_DATE] < date.today())]
    if log.empty:
        return 0.0
    start, end = min(log[COL_DATE]), max(log[COL_DATE])
    try:
        actuals = _actual_highs(city, str(start), str(end))
    except Exception:
        return 0.0  # never let a network hiccup kill the nightly run
    errs = []
    for _, row in log.iterrows():
        a = actuals.get(str(row[COL_DATE]))
        if a is not None:
            errs.append(float(row[COL_FCST]) - float(a))
    if len(errs) < MIN_MATCHED_DAYS:
        return 0.0
    b = float(np.mean(errs))
    return max(-MAX_ABS_BIAS, min(MAX_ABS_BIAS, b))


def calibrate_members(city, members):
    """
    Full calibration for one city's raw ensemble members.
    Input:  list of floats (F), the 31 raw GFS members.
    Output: (calibrated_members_list, bias_applied)
    """
    m = np.asarray(members, dtype=float)
    bias = station_bias(city)
    m = m - bias                            # step 1: remove station bias
    med = float(np.median(m))
    m = med + (m - med) * SPREAD_INFLATE    # step 2: widen spread around median
    return m.round(1).tolist(), bias
