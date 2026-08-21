"""Weather-Bot: THE one way a daily high is computed.

Born Aug 21 2026, after the second stale-board incident (Vegas Aug 20,
Minneapolis Aug 21). Both times a DERIVED file (daily_highs.csv) was
shown on a money-relevant board while the RAW readings in temps_log.csv
already knew better. The law that came out of it: any number displayed
or graded on a money path comes straight from the rawest, freshest
source available — the raw poll log — and every surface showing the
same quantity computes it the same way, from the same file.

So this module reads temps_log.csv (the raw METAR readings, appended by
poller.py every 15 minutes) and computes daily highs on the fly. It is
imported by:

  swoop_alert.py   grades open positions against highs_today()
  calibration.py   learns forecast bias from station_day_highs()
  autopsy.py       classifies losses with station_day_highs()
  poller.py        regenerates daily_highs.csv from station_day_highs()
                   (that file is now a derived, human-readable summary
                   only — NO code reads it; retirement candidate)

index.html (the Station Board) implements the SAME method in browser
JavaScript — same file, same day attribution, same offsets. If you
change the rules here, change them there in the same commit.

The rules:

1. A reading belongs to the CITY'S OWN calendar day (the $60 Phoenix
   lesson), estimated as round(longitude / 15) hours from UTC — the
   same convention poller.py and swoop_alert.py always used.
2. The day is judged by the OBSERVATION time (obs_time_utc), falling
   back to the poll time for legacy rows that predate obs_time_utc.
   (The old daily_highs.csv filed by poll time, which let a 23:45-local
   reading from *yesterday* seed *today's* high — that is how
   Minneapolis opened Aug 21 with a phantom 73.4° from the night
   before.)
3. The high is the plain maximum of the day's logged readings. The
   readings were already floored, never rounded up, by poller.c_to_f —
   no further rounding here. ERROR/blank rows are skipped.
4. Freshness is the age of the station's LATEST valid reading of the
   day — how current our knowledge is — not the age of the peak. A high
   is a floor that never expires; what goes stale is knowing where the
   temperature is NOW. (The old file carried the peak's own timestamp,
   so a quiet afternoon made a perfectly-current board look 10 hours
   stale — 592-738 minute "ages" in swoop_log.csv on Aug 21 — while a
   just-built page could show a fresh age on an hour-old number.)
"""

import csv
import os
from datetime import datetime, timedelta, timezone

from cities import SITES

TEMPS_LOG = "temps_log.csv"

# station -> UTC offset in hours (longitude estimate, good to the hour,
# which is all a calendar date needs). Same convention as poller.py.
STATION_OFFSET = {station: round(lon / 15.0)
                  for station, (_city, _lat, lon) in SITES.items()}
STATION_CITY = {station: city
                for station, (city, _lat, _lon) in SITES.items()}


def _parse_utc(s):
    """ISO timestamp -> aware UTC datetime, or None."""
    s = (s or "").strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def readings(path=TEMPS_LOG):
    """Yield (station, city, temp_f, obs_dt, poll_dt) for every valid
    reading in temps_log.csv. ERROR and unparseable rows are skipped —
    they are logged failures, not temperatures. obs_dt falls back to
    poll_dt for legacy rows (pre Aug 5 2026) with no obs_time_utc."""
    if not os.path.exists(path):
        return
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            station = (row.get("station") or "").strip()
            if station not in STATION_OFFSET:
                continue
            try:
                t = float((row.get("temp_f") or "").strip())
            except ValueError:
                continue          # ERROR / blank -> skip, never invent
            poll_dt = _parse_utc(row.get("utc_time"))
            obs_dt = _parse_utc(row.get("obs_time_utc")) or poll_dt
            if obs_dt is None:
                continue          # no usable timestamp -> refuse the row
            yield (station, STATION_CITY[station], t, obs_dt, poll_dt)


def local_date(station, dt_utc):
    """The station's own calendar date for a UTC moment."""
    off = STATION_OFFSET[station]
    return (dt_utc + timedelta(hours=off)).date().isoformat()


def station_day_highs(path=TEMPS_LOG):
    """(local_date, station) -> row dict with the day's running high:

        {date, station, city, high_f,
         peak_obs_utc, peak_poll_utc,     when the high was set
         latest_obs_utc, latest_poll_utc} freshest reading of that day

    Computed from scratch on every call — no incremental state to race,
    drop a peak, or drift from the raw log."""
    out = {}
    for station, city, t, obs_dt, poll_dt in readings(path):
        day = local_date(station, obs_dt)
        key = (day, station)
        rec = out.get(key)
        if rec is None:
            rec = out[key] = {
                "date": day, "station": station, "city": city,
                "high_f": t, "peak_obs_utc": obs_dt,
                "peak_poll_utc": poll_dt,
                "latest_obs_utc": obs_dt, "latest_poll_utc": poll_dt,
            }
        else:
            if t > rec["high_f"]:
                rec["high_f"] = t
                rec["peak_obs_utc"] = obs_dt
                rec["peak_poll_utc"] = poll_dt
            if obs_dt > rec["latest_obs_utc"]:
                rec["latest_obs_utc"] = obs_dt
                rec["latest_poll_utc"] = poll_dt
    return out


def day_high_map(path=TEMPS_LOG):
    """(local_date, station) -> high_f. The drop-in shape
    calibration.py and autopsy.py used to read from daily_highs.csv."""
    return {key: rec["high_f"]
            for key, rec in station_day_highs(path).items()}


def highs_today(now=None, path=TEMPS_LOG):
    """city -> (high_so_far_today, age_min) for each city's CURRENT
    local day. age_min is the age in whole minutes of the station's
    latest valid reading today (None never happens for a present city —
    a city with no reading today is simply absent, and the caller must
    skip it loudly, never guess)."""
    if now is None:
        now = datetime.now(timezone.utc)
    per_day = station_day_highs(path)
    out = {}
    for station, city in STATION_CITY.items():
        today = local_date(station, now)
        rec = per_day.get((today, station))
        if rec is None:
            continue
        age = int((now - rec["latest_obs_utc"]).total_seconds() // 60)
        out[city] = (rec["high_f"], max(0, age))
    return out
