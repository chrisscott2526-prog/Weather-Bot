"""Weather-Bot: THE MODEL LAB (Aug 31 2026) -- research-only logger
for OUTSIDE candidate forecast models.

WHY THIS EXISTS (owner decision, Aug 31 2026): before any new model
is allowed to vote with real money, it rides along as a passenger and
builds a public record. This script logs, nightly, what each candidate
model predicted for tomorrow's high at every settlement station.
model_report.py later grades those predictions against the official
settled numbers, per city -- the same forecast-vs-settlement test that
ranked our cities. Whatever proves it shrinks the miss gets promoted
into forecast.py's voting pool BY THE OWNER, on that evidence.
The scoreboard promotes; conviction never does.

THE LAW: model_research.csv is a RESEARCH LOG ONLY. Nothing that
trades, scans, or calibrates may EVER read it -- same law as
afternoon_forecasts.csv. Pointing scanner.py or calibration.py at it
would poison the race and the bias table.

Candidates logged (add or drop in CANDIDATES / include_nws only):
- icon  -- the German weather service's global ensemble (~40 members),
           via the same Open-Meteo ensemble API forecast.py uses.
           Generally rated the #3 global model behind ECMWF and GFS.
- nws   -- the National Weather Service's own published point forecast
           for the station (informed by NOAA's National Blend of
           Models), via api.weather.gov. A single number, not an
           ensemble -- logged as one expert opinion.

Honesty rules, inherited from forecast.py:
- Failures print and SKIP; a missing row is honest, an invented one
  never is. No placeholder temperatures, ever.
- DEAD-FEED LAW: if a candidate model returns ZERO rows across all 20
  cities, this script exits non-zero so the workflow turns RED (the
  Aug 19 2026 empty-secret scar: a dead feed must never scroll away
  green). Partial failures just print.

Usage:
    python model_lab.py                 # tomorrow's highs (nightly)
    python model_lab.py --today         # today's highs (research only)
    python model_lab.py --out FILE      # write elsewhere (testing)
"""

import csv, json, sys, time, urllib.request
from datetime import datetime, timedelta, timezone
from statistics import median as true_median
from cities import SITES, local_time
from csvio import appender

OUT_DEFAULT = "model_research.csv"
FIELDS = ["forecast_date", "station", "city", "model",
          "forecast_high_f", "n_members", "members", "fetched_utc"]
UA = {"User-Agent": "weather-bot-personal (aquatechpower@gmail.com)"}

# Open-Meteo ensemble candidates: api_name -> short tag stored in the
# model column. Same API and parsing as forecast.py's MODELS.
CANDIDATES = {"icon_seamless": "icon"}
NWS_TAG = "nws"


def get(url, tries=3):
    """Same transient-failure retry as forecast.py."""
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


def ensemble_highs(lat, lon, model, day_index):
    """(date_str, [member highs F]) for one Open-Meteo ensemble model,
    local to the site. Mirrors forecast.model_highs."""
    url = ("https://ensemble-api.open-meteo.com/v1/ensemble"
           f"?latitude={lat}&longitude={lon}"
           "&daily=temperature_2m_max"
           "&temperature_unit=fahrenheit"
           f"&models={model}"
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


def nws_high(lat, lon, target_date):
    """The NWS public forecast's daytime high (F) for target_date at
    this point, or None. Two calls: the /points lookup names this
    location's forecast URL, then the forecast's daytime period for
    the target date carries the high. Whole degrees F by design --
    that is genuinely all the NWS forecast publishes."""
    pt = get(f"https://api.weather.gov/points/{lat:.4f},{lon:.4f}")
    fc_url = (pt.get("properties") or {}).get("forecast")
    if not fc_url:
        raise ValueError("points lookup returned no forecast URL")
    fc = get(fc_url)
    for period in (fc.get("properties") or {}).get("periods", []):
        if not period.get("isDaytime"):
            continue
        if str(period.get("startTime", ""))[:10] != target_date:
            continue
        if str(period.get("temperatureUnit", "F")).upper() != "F":
            raise ValueError("unexpected temperature unit "
                             f"{period.get('temperatureUnit')}")
        t = period.get("temperature")
        if t is None:
            return None
        return float(t)
    return None   # no daytime period for that date (e.g. --today at night)


def out_path_from_argv():
    if "--out" in sys.argv:
        path = sys.argv[sys.argv.index("--out") + 1].strip()
        if not path or path.startswith("-"):
            raise SystemExit("--out needs a filename")
        return path
    return OUT_DEFAULT


def main():
    today_mode = "--today" in sys.argv
    day_index = 0 if today_mode else 1
    out = out_path_from_argv()
    print("MODEL LAB (research only): fetching "
          + ("TODAY's" if today_mode else "TOMORROW's")
          + f" candidate-model highs -> {out}")
    fetched = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows_per_model = {tag: 0 for tag in CANDIDATES.values()}
    rows_per_model[NWS_TAG] = 0

    with appender(out, FIELDS) as w:
        for sid, (city, lat, lon) in SITES.items():
            # The target calendar day on the CITY'S OWN clock (IANA
            # zones, DST-correct -- the same hand-verified clock the
            # buy window trusts). The ensemble API answers with the
            # same local-day attribution (timezone=auto), and the
            # cross-check below refuses any row where they disagree.
            target = (local_time(sid, datetime.now(timezone.utc))
                      + timedelta(days=day_index)).date().isoformat()

            # --- Open-Meteo ensemble candidates ---
            for api_name, tag in CANDIDATES.items():
                try:
                    d, members = ensemble_highs(lat, lon, api_name,
                                                day_index)
                    if not d or not members:
                        raise ValueError("no ensemble data returned")
                    if d != target:
                        raise ValueError(f"returned date {d}, expected "
                                         f"{target} on {city}'s clock")
                    med = round(true_median(members), 1)
                    w.writerow({
                        "forecast_date": d, "station": sid, "city": city,
                        "model": tag, "forecast_high_f": med,
                        "n_members": len(members),
                        "members": "|".join(str(m) for m in members),
                        "fetched_utc": fetched})
                    rows_per_model[tag] += 1
                    print(f"{city}: {tag} median {med}F "
                          f"({len(members)} members) for {d}")
                except Exception as e:
                    print(f"{city}: {tag} failed - {e} (no row written)")

            # --- NWS public point forecast ---
            try:
                t = nws_high(lat, lon, target)
                if t is None:
                    raise ValueError("no daytime forecast period for "
                                     f"{target}")
                w.writerow({
                    "forecast_date": target, "station": sid, "city": city,
                    "model": NWS_TAG, "forecast_high_f": t,
                    "n_members": "", "members": "",
                    "fetched_utc": fetched})
                rows_per_model[NWS_TAG] += 1
                print(f"{city}: nws forecast {t}F for {d}")
            except Exception as e:
                print(f"{city}: nws failed - {e} (no row written)")

    dead = [tag for tag, n in rows_per_model.items() if n == 0]
    print("Model lab done:", ", ".join(
        f"{tag}={n} rows" for tag, n in rows_per_model.items()))
    if dead:
        print(f"DEAD FEED: {', '.join(dead)} produced ZERO rows across "
              "all cities -- failing loudly (the Aug 19 2026 scar: a "
              "dead feed must never look green).")
        sys.exit(1)


if __name__ == "__main__":
    main()
