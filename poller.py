"""Weather-Bot: NWS station poller.
Pulls current temps from Kalshi settlement stations, keeps a running
daily high, and appends everything to a CSV log in the repo."""

import csv, json, os, urllib.request
from datetime import datetime, timezone

STATIONS = {
    "KNYC": "New York City",
    "KMIA": "Miami",
    "KDEN": "Denver",
    "KLAX": "Los Angeles",
    "KPHL": "Philadelphia",
    "KAUS": "Austin",
    "KMDW": "Chicago",
}

LOG = "temps_log.csv"

def fetch(station):
    url = f"https://api.weather.gov/stations/{station}/observations/latest"
    req = urllib.request.Request(url, headers={"User-Agent": "weather-bot-personal"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    c = data["properties"]["temperature"]["value"]
    if c is None:
        return None
    return round(c * 9 / 5 + 32, 1)  # C -> F

def main():
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    new_file = not os.path.exists(LOG)
    with open(LOG, "a", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["utc_time", "station", "city", "temp_f"])
        for sid, city in STATIONS.items():
            try:
                t = fetch(sid)
                w.writerow([now, sid, city, t])
                print(f"{city} ({sid}): {t}F")
            except Exception as e:
                w.writerow([now, sid, city, "ERROR"])
                print(f"{city} ({sid}): failed - {e}")

if __name__ == "__main__":
    main()
