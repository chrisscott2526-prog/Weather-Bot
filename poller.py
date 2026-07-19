"""Weather-Bot: NWS station poller + daily high tracker.
Every run: logs current temps AND updates each city's running
daily high (in station-local terms we use UTC date for now)."""

import csv, json, os, urllib.request
from datetime import datetime, timezone

from cities import STATIONS


LOG = "temps_log.csv"
HIGHS = "daily_highs.csv"

def fetch(station):
    url = f"https://api.weather.gov/stations/{station}/observations/latest"
    req = urllib.request.Request(url, headers={"User-Agent": "weather-bot-personal"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    c = data["properties"]["temperature"]["value"]
    if c is None:
        return None
    return round(c * 9 / 5 + 32, 1)  # C -> F

def read_highs():
    highs = {}
    if os.path.exists(HIGHS):
        with open(HIGHS) as f:
            for row in csv.DictReader(f):
                highs[(row["date"], row["station"])] = row
    return highs

def write_highs(highs):
    with open(HIGHS, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "station", "city", "high_f", "last_update_utc"])
        for (_, _), row in sorted(highs.items()):
            w.writerow([row["date"], row["station"], row["city"],
                        row["high_f"], row["last_update_utc"]])

def main():
    now = datetime.now(timezone.utc)
    stamp = now.isoformat(timespec="seconds")
    today = now.date().isoformat()
    highs = read_highs()

    new_file = not os.path.exists(LOG)
    with open(LOG, "a", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["utc_time", "station", "city", "temp_f"])
        for sid, city in STATIONS.items():
            try:
                t = fetch(sid)
            except Exception as e:
                w.writerow([stamp, sid, city, "ERROR"])
                print(f"{city}: failed - {e}")
                continue
            w.writerow([stamp, sid, city, t])
            print(f"{city}: {t}F")
            if t is None:
                continue
            key = (today, sid)
            if key not in highs or float(highs[key]["high_f"]) < t:
                highs[key] = {"date": today, "station": sid, "city": city,
                              "high_f": t, "last_update_utc": stamp}

    write_highs(highs)

if __name__ == "__main__":
    main()
