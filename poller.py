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

# THE OVERNIGHT PEAK LOG (Sep 14 2026) -- the official 6-hour max
# temperatures the synoptic observations carry, logged for the
# floor-at-official-max backtest. RESEARCH ONLY (CLAUDE.md law).
SIXHR_LOG = "sixhr_max_log.csv"
SIXHR_FIELDS = ["utc_time", "station", "city", "max6_f", "obs_time_utc"]

# (Local-day attribution now lives in highs.py -- one convention,
# shared by every consumer: round(longitude / 15) hours from UTC.)


def c_to_f(c):
    """Celsius -> Fahrenheit, floor to 2 decimals. NEVER round up:
    overstating the high is how a board invents a settled bracket."""
    f = c * 9.0 / 5.0 + 32.0
    return math.floor(f * 100) / 100.0


def fetch(station):
    """Return (temp_f, obs_time_iso, max6_f) from the latest METAR
    observation. max6_f is the station's OFFICIAL 6-hour maximum
    (populated only on the 00/06/12/18 UTC synoptic observations,
    None otherwise) -- the between-hour peak our hourly sampling
    misses and the number TWC's settled max is built from. Same API
    payload we already fetch; no extra call. Floored like every
    temperature here, never rounded up."""
    url = f"https://api.weather.gov/stations/{station}/observations/latest"
    req = urllib.request.Request(url, headers={"User-Agent": "weather-bot-personal"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    props = data.get("properties", {})
    c = props.get("temperature", {}).get("value")
    obs_time = props.get("timestamp", "")
    m6 = props.get("maxTemperatureLast6Hours", {}).get("value")
    max6_f = c_to_f(m6) if isinstance(m6, (int, float)) else None
    if c is None:
        return None, obs_time, max6_f
    return c_to_f(c), obs_time, max6_f


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

    six = []   # (station, city, max6_f, obs_time) research rows
    with appender(LOG, LOG_FIELDS, LOG_LEGACY) as w:
        for sid, city in STATIONS.items():
            try:
                t, obs_time, max6 = fetch(sid)
            except Exception as e:
                w.writerow({"utc_time": stamp, "station": sid, "city": city,
                            "temp_f": "ERROR", "obs_time_utc": ""})
                print(f"{city}: failed - {e}")
                continue
            w.writerow({"utc_time": stamp, "station": sid, "city": city,
                        "temp_f": t, "obs_time_utc": obs_time})
            if max6 is not None:
                six.append((sid, city, max6, obs_time))
            age = ""
            try:
                ot = datetime.fromisoformat(obs_time.replace("Z", "+00:00"))
                age = f" (obs {int((now - ot).total_seconds() // 60)}m old)"
            except Exception:
                pass
            m6txt = f" [6h max {max6}F]" if max6 is not None else ""
            print(f"{city}: {t}F{age}{m6txt}")

    # THE OVERNIGHT PEAK LOG (Sep 14 2026, research only). The
    # Philadelphia $10: the deciding overnight peak happened BETWEEN
    # hourly readings, the official 6-hour max in the same API payload
    # knew it, and nothing read that field. Log it here so the "floor
    # at the official 6-hour max" idea can be backtested against real
    # rows before it is allowed anywhere near the money floor -- the
    # walk-forward standard the morning thermostat set. RESEARCH LOG
    # ONLY: nothing that trades, scans for money, or calibrates may
    # read this file until a backtest and an owner decision promote
    # it (CLAUDE.md has the law). Dedupe by (station, obs_time): the
    # same synoptic observation stays "latest" for up to an hour of
    # passes.
    if six:
        seen = set()
        try:
            with open(SIXHR_LOG) as f:
                for row in csv.DictReader(f):
                    seen.add((row.get("station"), row.get("obs_time_utc")))
        except OSError:
            pass
        fresh = [r for r in six if (r[0], r[3]) not in seen]
        if fresh:
            with appender(SIXHR_LOG, SIXHR_FIELDS) as w:
                for sid, city, max6, obs_time in fresh:
                    w.writerow({"utc_time": stamp, "station": sid,
                                "city": city, "max6_f": max6,
                                "obs_time_utc": obs_time})

    write_highs()


if __name__ == "__main__":
    main()

