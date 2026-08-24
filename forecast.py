"""Weather-Bot: nightly forecast logger (v3 - multi-model ensemble).
Pulls the GFS (31-member) AND ECMWF (51-member) ensembles for tomorrow
from Open-Meteo for each settlement city, pools all members, and logs
them to forecasts.csv. Column forecast_high_f = pooled ensemble median
(backward compatible).

FIXED Aug 5 2026:
- True median (averages the middle pair on an even member count;
  the old index pick was biased whenever a member dropped out).
- Failures print and SKIP -- no more "ERROR" rows with blank dates
  poisoning every downstream reader of forecasts.csv.

MORNING MODE (Aug 20 2026, the night-vs-morning race):
    python forecast.py --today
pulls TODAY's highs (local to each site) instead of tomorrow's, with
the same calibration and the same forecasts.csv columns. A morning row
is told apart from a night row by its timestamps (csvio.is_morning_row:
same-UTC-day AND fetched 06:00-22:59 UTC -- the hour window matters
because a delayed nightly cron can slip past UTC midnight and stamp
the same date). scanner.py and calibration.py rely on that split --
morning picks must use morning members, night picks and bias learning
must use night members. No new column needed, so the header is
unchanged.

MULTI-MODEL POOL (Aug 24 2026): one GFS model claimed ~50% and won 30%
-- a single ensemble is both less accurate and tighter than the real
error. ECMWF's ensemble is the stronger model for surface temperature,
and a pooled 80+ member vote is finer-grained than 31. Rules:
- One API call PER MODEL, parsed identically. A model that dies or
  returns a mismatched date is reported LOUDLY and the others carry
  on; the city is skipped only when NO model delivers (the Aug 19
  dead-feed scar: partial feeds must show in the log, never vanish
  into a silent pooled call).
- Calibration is still applied exactly once, to the POOLED members,
  right here. The per-station bias/spread table (calibration.py)
  learns from the pooled median it stored -- one pipeline, one
  correction, same as before.

AFTERNOON GRADING LOG (Aug 24 2026):
    python forecast.py --today --out afternoon_forecasts.csv
Same fetch, same calibration, same columns -- different FILE. The
afternoon workflow logs a late same-day forecast so the scoreboard
can eventually measure how much accuracy each extra hour of freshness
buys. NOTHING trades from that file: scanner.py and calibration.py
read only forecasts.csv, and rows written elsewhere can never leak
into a scan or the bias table. Keep it that way: nothing that trades
or calibrates may ever read an --out file.
"""

import csv, json, os, sys, time, urllib.request
from datetime import datetime, timezone
from statistics import median as true_median
from calibration import calibrate_members
from cities import SITES
from csvio import appender

OUT_DEFAULT = "forecasts.csv"
FIELDS = ["forecast_date", "station", "city", "forecast_high_f",
          "fetched_utc", "members"]
# layout before ensemble members were logged (Aug 5 2026)
LEGACY = [[c for c in FIELDS if c != "members"]]
UA = {"User-Agent": "weather-bot-personal"}

# The pool. gfs_seamless = 31 members (30 perturbed + control),
# ecmwf_ifs025 = 51. ECMWF outvotes GFS ~5:3 in the pool -- accepted
# on purpose: it is the stronger surface-temperature model. Add or
# drop models HERE only; the fetch loop treats them all alike.
MODELS = ["gfs_seamless", "ecmwf_ifs025"]


def get(url, tries=3):
    """Retry on transient network failures. Dallas has been timing out on
    the SSL handshake nightly since ~Aug 1 -- one dropped connection should
    not cost a whole city's forecast."""
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception as e:
            last = e
            if attempt < tries - 1:
                print(f"    retry {attempt + 1}/{tries - 1} after: {e}")
                time.sleep(3)
    raise last


def model_highs(lat, lon, model, day_index=1):
    """Return (date_str, [member highs F]) local to site, for ONE model.
    day_index 1 = tomorrow (the nightly default), 0 = today (the
    morning refresh). Open-Meteo's daily arrays start at today.
    One call per model keeps the response keys identical to the
    single-model layout, whatever the model."""
    url = ("https://ensemble-api.open-meteo.com/v1/ensemble"
           f"?latitude={lat}&longitude={lon}"
           "&daily=temperature_2m_max"
           "&temperature_unit=fahrenheit"
           f"&models={model}"
           "&forecast_days=3&timezone=auto")
    data = get(url)
    daily = data.get("daily", {})
    dates = daily.get("time", [])
    if len(dates) <= day_index:
        return None, []
    target = dates[day_index]
    members = []
    for key, vals in daily.items():
        if key.startswith("temperature_2m_max") and isinstance(vals, list):
            if len(vals) > day_index and vals[day_index] is not None:
                members.append(round(float(vals[day_index]), 1))
    return target, members


def pooled_highs(city, lat, lon, day_index):
    """(date, pooled members) across MODELS. A model that fails or
    disagrees on the target date is reported and dropped; the pool is
    whatever honestly arrived. No models at all -> (None, [])."""
    target, pool = None, []
    for model in MODELS:
        try:
            d, members = model_highs(lat, lon, model, day_index)
            if not d or not members:
                raise ValueError("no ensemble data returned")
        except Exception as e:
            print(f"  {city}: {model} FAILED ({e}) -- pooling without it")
            continue
        if target is None:
            target = d
        elif d != target:
            print(f"  {city}: {model} returned date {d}, expected "
                  f"{target} -- dropping that model this run")
            continue
        pool.extend(members)
        print(f"  {city}: {model} contributed {len(members)} members")
    return target, pool


def out_path_from_argv():
    if "--out" in sys.argv:
        path = sys.argv[sys.argv.index("--out") + 1].strip()
        if not path or path.startswith("-"):
            raise SystemExit("--out needs a filename")
        return path
    return OUT_DEFAULT


def main():
    today_mode = "--today" in sys.argv
    day_index = 0 if today_mode else 1
    out = out_path_from_argv()
    print("MORNING refresh: fetching TODAY's ensemble highs"
          if today_mode else "Nightly run: fetching TOMORROW's ensemble highs")
    print(f"Models: {', '.join(MODELS)} -> {out}")
    fetched = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with appender(out, FIELDS, LEGACY) as w:
        for sid, (city, lat, lon) in SITES.items():
            try:
                d, members = pooled_highs(city, lat, lon, day_index)
                if not d or not members:
                    raise ValueError("no model delivered any members")
                members, bias = calibrate_members(sid, members)
                med = round(true_median(members), 1)
                w.writerow({"forecast_date": d, "station": sid,
                            "city": city, "forecast_high_f": med,
                            "fetched_utc": fetched,
                            "members": "|".join(str(m) for m in members)})
                print(f"{city}: median {med}F, "
                      f"{len(members)} pooled members for {d}")
            except Exception as e:
                # Print and SKIP. A missing row is honest; an ERROR row
                # with a blank date is a trap for every downstream reader.
                print(f"{city}: failed - {e} (no row written)")


if __name__ == "__main__":
    main()
