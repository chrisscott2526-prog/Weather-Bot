"""Weather-Bot: nightly forecast logger (v2 - GFS ensemble).
Pulls 31-member GFS ensemble highs for tomorrow from Open-Meteo
for each settlement city, logs all members to forecasts.csv.
Column forecast_high_f = ensemble median (backward compatible).

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
"""

import csv, json, os, sys, time, urllib.request
from datetime import datetime, timezone
from statistics import median as true_median
from calibration import calibrate_members
from cities import SITES
from csvio import appender


OUT = "forecasts.csv"
FIELDS = ["forecast_date", "station", "city", "forecast_high_f",
          "fetched_utc", "members"]
# layout before ensemble members were logged (Aug 5 2026)
LEGACY = [[c for c in FIELDS if c != "members"]]
UA = {"User-Agent": "weather-bot-personal"}


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


def ensemble_highs(lat, lon, day_index=1):
    """Return (date_str, [member highs F]) local to site.
    day_index 1 = tomorrow (the nightly default), 0 = today (the
    morning refresh). Open-Meteo's daily arrays start at today."""
    url = ("https://ensemble-api.open-meteo.com/v1/ensemble"
           f"?latitude={lat}&longitude={lon}"
           "&daily=temperature_2m_max"
           "&temperature_unit=fahrenheit"
           "&models=gfs_seamless"
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


def main():
    today_mode = "--today" in sys.argv
    day_index = 0 if today_mode else 1
    print("MORNING refresh: fetching TODAY's ensemble highs"
          if today_mode else "Nightly run: fetching TOMORROW's ensemble highs")
    fetched = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with appender(OUT, FIELDS, LEGACY) as w:
        for sid, (city, lat, lon) in SITES.items():
            try:
                d, members = ensemble_highs(lat, lon, day_index)
                if not d or not members:
                    raise ValueError("no ensemble data returned")
                members, bias = calibrate_members(sid, members)
                med = round(true_median(members), 1)
                w.writerow({"forecast_date": d, "station": sid,
                            "city": city, "forecast_high_f": med,
                            "fetched_utc": fetched,
                            "members": "|".join(str(m) for m in members)})
                print(f"{city}: median {med}F, "
                      f"{len(members)} members for {d}")
            except Exception as e:
                # Print and SKIP. A missing row is honest; an ERROR row
                # with a blank date is a trap for every downstream reader.
                print(f"{city}: failed - {e} (no row written)")


if __name__ == "__main__":
    main()

