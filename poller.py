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

CHANGED Aug 21 2026 (the second stale-board incident -- Vegas Aug 20,
Minneapolis Aug 21): daily_highs.csv is no longer this script's
incrementally-updated state, and NO code reads it anymore. Every
consumer (swoop_alert.py, calibration.py, autopsy.py, index.html)
now computes highs directly from temps_log.csv via highs.py -- one
source, one method. This script still WRITES daily_highs.csv, but as a
pure derived summary regenerated from temps_log.csv on every run, so it
can never drift from the raw log again. It exists only for a human to
eyeball; it is a retirement candidate.
"""

import csv, json, math, urllib.request
from datetime import datetime, timezone

from cities import STATIONS
from csvio import appender

LOG = "temps_log.csv"
HIGHS = "daily_highs.csv"

LOG_FIELDS = ["utc_time", "station", "city", "temp_f", "obs_time_utc"]
# layout before obs_time_utc was added (Aug 5 2026)
LOG_LEGACY = [["utc_time", "station", "city", "temp_f"]]

# (Local-day attribution now lives in highs.py -- one convention,
# shared by every consumer: round(longitude / 15) hours from UTC.)


def c_to_f(c):
    """Celsius -> Fahrenheit, floor to 2 decimals. NEVER round up:
    overstating the high is how a board invents a settled bracket."""
    f = c * 9.0 / 5.0 + 32.0
    return math.floor(f * 100) / 100.0


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


def write_highs():
    """Regenerate daily_highs.csv from temps_log.csv, from scratch.

    Derived summary for human eyes ONLY -- no code reads this file
    (money and display paths compute from temps_log.csv via highs.py).
    A full recompute every run means a dropped commit or race can never
    leave a stale peak behind: the raw log heals it on the next pass."""
    from highs import station_day_highs
    per_day = station_day_highs()
    with open(HIGHS, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "station", "city", "high_f",
                    "last_update_utc", "obs_time_utc"])
        for key in sorted(per_day):
            r = per_day[key]
            w.writerow([r["date"], r["station"], r["city"], r["high_f"],
                        r["peak_poll_utc"].isoformat(timespec="seconds"),
                        r["peak_obs_utc"].isoformat(timespec="seconds")])


def main():
    now = datetime.now(timezone.utc)
    stamp = now.isoformat(timespec="seconds")

    with appender(LOG, LOG_FIELDS, LOG_LEGACY) as w:
        for sid, city in STATIONS.items():
            try:
                t, obs_time = fetch(sid)
            except Exception as e:
                w.writerow({"utc_time": stamp, "station": sid, "city": city,
                            "temp_f": "ERROR", "obs_time_utc": ""})
                print(f"{city}: failed - {e}")
                continue
            w.writerow({"utc_time": stamp, "station": sid, "city": city,
                        "temp_f": t, "obs_time_utc": obs_time})
            age = ""
            try:
                ot = datetime.fromisoformat(obs_time.replace("Z", "+00:00"))
                age = f" (obs {int((now - ot).total_seconds() // 60)}m old)"
            except Exception:
                pass
            print(f"{city}: {t}F{age}")

    write_highs()


if __name__ == "__main__":
    main()

