"""Weather-Bot: NWS station poller + daily high tracker.

Every run: logs current temps AND updates each city's running daily high.

FIXED Aug 5 2026 (the $60 Phoenix lesson):
1. PRECISION. NWS reports Celsius. The old code rounded the F conversion to
   one decimal, so 42.2C -> 107.96F displayed as 108.0 -- fabricating a
   degree on a bracket edge. We now keep two decimals and NEVER round up.
   The board must understate, never overstate.
2. LOCAL DATES. Daily highs were filed under the UTC date, so Phoenix
   evening heat (still 105F+ after 5pm local = next day UTC) landed on the
   wrong day. Highs are now tracked per the CITY'S OWN calendar day using a
   longitude-based timezone estimate (good to the hour, which is all a
   calendar date needs).
3. HONEST LABELING. This reads the hourly METAR instrument observation.
   Kalshi settles on the NWS CLI Daily Climate Report -- a DIFFERENT
   product that captures between-hour peaks. They usually agree; they are
   not the same number. Every consumer of daily_highs.csv must treat it as
   "instrument reading so far", never as "what will settle."
   obs_time_utc is now logged so downstream code can refuse stale data.
"""

import csv, json, math, os, urllib.request
from datetime import datetime, timezone, timedelta

from cities import STATIONS, SITES

LOG = "temps_log.csv"
HIGHS = "daily_highs.csv"

def build_offsets():
    """city -> UTC offset (hours, negative for US) from site longitude."""
    out = {}
    for station, (city, lat, lon) in SITES.items():
        out[city] = round(lon / 15.0)
    return out


CITY_OFFSET = build_offsets()


def c_to_f(c):
    """Celsius -> Fahrenheit, floor to 2 decimals. NEVER round up:
    overstating the high is how a board invents a settled bracket."""
    f = c * 9.0 / 5.0 + 32.0
    return math.floor(f * 100) / 100.0


def local_date(city, now_utc):
    off = CITY_OFFSET.get(city, 0)
    return (now_utc + timedelta(hours=off)).date().isoformat()


def fetch(station):
    """Return (temp_f, obs_time_iso) from the latest METAR observation."""
    url = f"https://api.weather.gov/stations/{station}/observations/latest"
    req = urllib.request.Request(url, headers={"User-Agent": "weather-bot-personal"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    props = data.get("properties", {})
    c = props.get("temperature", {}).get("value")
    obs_time = props.get("timestamp", "")
    if c is None:
        return None, obs_time
    return c_to_f(c), obs_time


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
        w.writerow(["date", "station", "city", "high_f",
                    "last_update_utc", "obs_time_utc"])
        for key in sorted(highs):
            row = highs[key]
            w.writerow([row["date"], row["station"], row["city"],
                        row["high_f"], row["last_update_utc"],
                        row.get("obs_time_utc", "")])


def main():
    now = datetime.now(timezone.utc)
    stamp = now.isoformat(timespec="seconds")
    highs = read_highs()

    new_file = not os.path.exists(LOG)
    with open(LOG, "a", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["utc_time", "station", "city", "temp_f",
                        "obs_time_utc"])
        for sid, city in STATIONS.items():
            try:
                t, obs_time = fetch(sid)
            except Exception as e:
                w.writerow([stamp, sid, city, "ERROR", ""])
                print(f"{city}: failed - {e}")
                continue
            w.writerow([stamp, sid, city, t, obs_time])
            age = ""
            try:
                ot = datetime.fromisoformat(obs_time.replace("Z", "+00:00"))
                age = f" (obs {int((now - ot).total_seconds() // 60)}m old)"
            except Exception:
                pass
            print(f"{city}: {t}F{age}")
            if t is None:
                continue
            day = local_date(city, now)
            key = (day, sid)
            if key not in highs or float(highs[key]["high_f"]) < t:
                highs[key] = {"date": day, "station": sid, "city": city,
                              "high_f": t, "last_update_utc": stamp,
                              "obs_time_utc": obs_time}

    write_highs(highs)


if __name__ == "__main__":
    main()

