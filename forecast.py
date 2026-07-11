"""Weather-Bot: nightly forecast logger.
Grabs tomorrow's NWS forecast high for each settlement city and
appends it to forecasts.csv. Compare against daily_highs.csv later."""

import csv, json, os, urllib.request
from datetime import datetime, timezone

# station: (city, lat, lon)
SITES = {
    "KNYC": ("New York City", 40.7794, -73.9692),
    "KMIA": ("Miami", 25.7906, -80.3164),
    "KDEN": ("Denver", 39.8467, -104.6562),
    "KLAX": ("Los Angeles", 33.9382, -118.3866),
    "KPHL": ("Philadelphia", 39.8683, -75.2311),
    "KAUS": ("Austin", 30.1945, -97.6699),
    "KMDW": ("Chicago", 41.7842, -87.7553),
}

OUT = "forecasts.csv"
UA = {"User-Agent": "weather-bot-personal"}

def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def forecast_high(lat, lon):
    """Return (date, temp) for TOMORROW's daytime period.
    'Tomorrow' = first daytime period dated after the location's
    current local date (taken from the first period's startTime)."""
    point = get(f"https://api.weather.gov/points/{lat},{lon}")
    fc = get(point["properties"]["forecast"])
    periods = fc["properties"]["periods"]
    if not periods:
        return None, None
    today_local = periods[0]["startTime"][:10]
    for p in periods:
        if p["isDaytime"] and p["startTime"][:10] > today_local:
            return p["startTime"][:10], p["temperature"]
    return None, None

def main():
    fetched = datetime.now(timezone.utc).isoformat(timespec="seconds")
    new = not os.path.exists(OUT)
    with open(OUT, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["forecast_date", "station", "city",
                        "forecast_high_f", "fetched_utc"])
        for sid, (city, lat, lon) in SITES.items():
            try:
                d, hi = forecast_high(lat, lon)
                if d is None:
                    raise ValueError("no tomorrow daytime period found")
                w.writerow([d, sid, city, hi, fetched])
                print(f"{city}: {hi}F for {d}")
            except Exception as e:
                w.writerow(["", sid, city, "ERROR", fetched])
                print(f"{city}: failed - {e}")

if __name__ == "__main__":
    main()

