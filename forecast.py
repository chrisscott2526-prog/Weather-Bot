"""Weather-Bot: nightly forecast logger (v2 - GFS ensemble).
Pulls 31-member GFS ensemble highs for tomorrow from Open-Meteo
for each settlement city, logs all members to forecasts.csv.
Column forecast_high_f = ensemble median (backward compatible)."""

import csv, json, os, urllib.request
from datetime import datetime, timezone, timedelta
from calibration import calibrate_members
from cities import SITES


OUT = "forecasts.csv"
UA = {"User-Agent": "weather-bot-personal"}

def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)

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
                srt = sorted(members)
                median = srt[len(srt) // 2]
                w.writerow([d, sid, city, median, fetched,
                            "|".join(str(m) for m in members)])
                print(f"{city}: median {median}F, "
                      f"{len(members)} members for {d}")
            except Exception as e:
                w.writerow(["", sid, city, "ERROR", fetched, ""])
                print(f"{city}: failed - {e}")

if __name__ == "__main__":
    main()
