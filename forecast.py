"""Weather-Bot: nightly forecast logger (v2 - GFS ensemble).
Pulls 31-member GFS ensemble highs for tomorrow from Open-Meteo
for each settlement city, logs all members to forecasts.csv.
Column forecast_high_f = ensemble median (backward compatible).

FIXED Aug 5 2026:
- True median (averages the middle pair on an even member count;
  the old index pick was biased whenever a member dropped out).
- Failures print and SKIP -- no more "ERROR" rows with blank dates
  poisoning every downstream reader of forecasts.csv.
"""

import csv, json, os, time, urllib.request
from datetime import datetime, timezone
from statistics import median as true_median
from calibration import calibrate_members
from cities import SITES


OUT = "forecasts.csv"
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


def ensemble_highs(lat, lon):
    """Return (date_str, [member highs F]) for tomorrow, local to site."""
    url = ("https://ensemble-api.open-meteo.com/v1/ensemble"
           f"?latitude={lat}&longitude={lon}"
           "&daily=temperature_2m_max"
           "&temperature_unit=fahrenheit"
           "&models=gfs_seamless"
           "&forecast_days=3&timezone=auto")
    data = get(url)
    daily = data.get("daily", {})
    dates = daily.get("time", [])
    if len(dates) < 2:
        return None, []
    tomorrow = dates[1]
    members = []
    for key, vals in daily.items():
        if key.startswith("temperature_2m_max") and isinstance(vals, list):
            if len(vals) > 1 and vals[1] is not None:
                members.append(round(float(vals[1]), 1))
    return tomorrow, members


def main():
    fetched = datetime.now(timezone.utc).isoformat(timespec="seconds")
    new = not os.path.exists(OUT)
    with open(OUT, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["forecast_date", "station", "city",
                        "forecast_high_f", "fetched_utc", "members"])
        for sid, (city, lat, lon) in SITES.items():
            try:
                d, members = ensemble_highs(lat, lon)
                if not d or not members:
                    raise ValueError("no ensemble data returned")
                members, bias = calibrate_members(sid, members)
                med = round(true_median(members), 1)
                w.writerow([d, sid, city, med, fetched,
                            "|".join(str(m) for m in members)])
                print(f"{city}: median {med}F, "
                      f"{len(members)} members for {d}")
            except Exception as e:
                # Print and SKIP. A missing row is honest; an ERROR row
                # with a blank date is a trap for every downstream reader.
                print(f"{city}: failed - {e} (no row written)")


if __name__ == "__main__":
    main()

