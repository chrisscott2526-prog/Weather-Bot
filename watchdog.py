"""watchdog.py -- the bot's own pulse check.

THE WATCHDOG (Aug 30 2026). Every fix before this one cured the lane
that had just burned, and the owner found each new failure by squinting
at a stale board hours later. A once-a-morning "check everything" can
never catch these failures because they start AFTER the check (GitHub
dropping crons at noon looks perfectly healthy at 9 AM). So the check
runs all day instead: the poller relay calls this script every pass
(~15 min), it inspects the heartbeats that have actually burned us,
and it writes health.json for the Station Board's banner. A failing
check also makes this script exit non-zero so the relay pass flags it
and the finished run turns RED (GitHub then emails the owner -- the
dead-feed law: a problem must never scroll away green).

The heartbeats, each from the rawest source available:
  POLLER       newest poll write in temps_log.csv       (always)
  FORECAST     a same-day morning forecast row exists   (14:00-18:45 UTC)
  MONEY LANE   a morning.yml run is alive on GitHub     (13:15-18:45 UTC)
  ORDERS       no ERROR order placed today              (always)
  SWOOP        swoop_log.csv fresh in its 15-min band   (16:00-01:59 UTC)
  SETTLEMENTS  settlements.csv checked recently         (always)

health.json is a FULL-REWRITE file (never add it to the union-merge
list in .gitattributes) and it is NOT a money input: no scanner,
trader, or grader reads it. It carries its own checked_utc so the
board can refuse to trust a stale one -- a silent watchdog shows as
an alarm on the board, never as green (the derived-file law's
fail-closed rule).
"""

import csv
import io
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

from csvio import is_morning_row

HEALTH_PATH = "health.json"

# Staleness thresholds, in minutes. Generous on purpose: every one of
# these feeds runs on a 15-minute cadence when healthy, so a 45-minute
# silence means at least two missed beats -- a real outage, not jitter.
POLL_STALE_MIN = 40          # relay writes every ~15 min
SWOOP_STALE_MIN = 45         # swoop band runs every 15 min
SETTLE_STALE_MIN = 9 * 60    # settlements.py runs 4x daily
LANE_RUN_GRACE_MIN = 40      # a relay handoff gap larger than this is real


def now_utc():
    return datetime.now(timezone.utc)


def parse_ts(s):
    """ISO timestamp -> aware datetime, or None. Never guesses."""
    if not s:
        return None
    try:
        t = datetime.fromisoformat(s.strip().replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return t
    except ValueError:
        return None


def read_tail_rows(path, tail_bytes=300_000):
    """Header from the top, rows from the last tail_bytes -- columns
    read BY NAME (the header-drift law) without pulling a giant log."""
    with open(path, "rb") as f:
        header = f.readline().decode("utf-8", "replace").rstrip("\n")
        f.seek(0, 2)
        size = f.tell()
        start = max(len(header) + 1, size - tail_bytes)
        f.seek(start)
        chunk = f.read().decode("utf-8", "replace")
    lines = chunk.splitlines()
    if start > len(header) + 1 and lines:
        lines = lines[1:]  # drop the row the seek cut in half
    rdr = csv.DictReader(io.StringIO(header + "\n" + "\n".join(lines)))
    return [r for r in rdr if r]


def newest_ts(path, column, tail_bytes=300_000):
    """Newest parseable timestamp in a column, or None (file missing,
    empty, or column absent -- the caller decides how loud to be)."""
    try:
        rows = read_tail_rows(path, tail_bytes)
    except OSError:
        return None
    best = None
    for r in rows:
        t = parse_ts(r.get(column, ""))
        if t and (best is None or t > best):
            best = t
    return best


def check_money_lane(notes):
    """Is a morning.yml run alive on GitHub right now? Uses the runs
    API (GITHUB_TOKEN when the workflow provides it). Returns True
    (alive), False (dead), or None (could not verify -- note, don't
    false-alarm; an unverifiable check is a note, a dead lane is an
    alarm)."""
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        notes.append("money-lane check skipped (not running inside "
                     "GitHub Actions)")
        return None
    url = (f"https://api.github.com/repos/{repo}/actions/workflows/"
           f"morning.yml/runs?per_page=5")
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "weather-bot-watchdog",
    })
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.load(resp)
    except Exception as e:  # network/API trouble is a note, not an alarm
        notes.append(f"money-lane check could not reach the GitHub API "
                     f"({e}) -- verify morning.yml by eye")
        return None
    now = now_utc()
    for run in data.get("workflow_runs", []):
        if run.get("status") in ("queued", "in_progress"):
            return True
        t = parse_ts(run.get("updated_at", ""))
        if t and (now - t).total_seconds() < LANE_RUN_GRACE_MIN * 60:
            return True  # just finished/handing off -- give it grace
    return False


def main():
    now = now_utc()
    today = now.strftime("%Y-%m-%d")
    alarms = []
    notes = []

    def alarm(code, msg):
        alarms.append({"code": code, "msg": msg})

    # -- POLLER: is the raw temps feed being written at all? ----------
    t = newest_ts("temps_log.csv", "utc_time")
    if t is None:
        alarm("POLLER", "temps_log.csv is missing or unreadable -- "
              "no thermometer data at all. Press Run on poll.yml.")
    else:
        age = (now - t).total_seconds() / 60
        if age > POLL_STALE_MIN:
            alarm("POLLER", f"POLLER STALE -- last poll wrote "
                  f"{age:.0f} min ago (limit {POLL_STALE_MIN}). Every "
                  f"reading below is at least that old. Press Run on "
                  f"poll.yml.")

    # -- FORECAST: after the buying day starts, a same-day morning ----
    # -- forecast row must exist (no fresh row = the lane is scanning -
    # -- nothing, per the SKIP-loudly law) ----------------------------
    if 14 * 60 <= now.hour * 60 + now.minute <= 18 * 60 + 45:
        try:
            rows = read_tail_rows("forecasts.csv")
            fresh = any(r.get("forecast_date") == today
                        and is_morning_row(r.get("forecast_date", ""),
                                           r.get("fetched_utc", ""))
                        for r in rows)
        except OSError:
            fresh = False
        if not fresh:
            alarm("FORECAST", "NO SAME-DAY FORECAST -- the buying day "
                  "is underway but no morning forecast row exists for "
                  "today, so every scan is skipping every city. Press "
                  "Run on morning.yml.")

    # -- MONEY LANE: during buying hours a morning.yml relay must be --
    # -- alive on GitHub (the Aug 29 disease: every cron dropped and --
    # -- nothing was even trying to buy) ------------------------------
    if 13 * 60 + 15 <= now.hour * 60 + now.minute <= 18 * 60 + 45:
        alive = check_money_lane(notes)
        if alive is False:
            alarm("MONEYLANE", "MONEY LANE NOT RUNNING -- no morning.yml "
                  "run is alive during buying hours. Cities are hitting "
                  "their 9-11 AM windows with nobody buying. Press Run "
                  "on morning.yml.")

    # -- ORDERS: an order that errored today (usually an empty --------
    # -- wallet). morning.yml reds its own run; this keeps the alarm --
    # -- on the board until the day ends ------------------------------
    try:
        bad = [r for r in read_tail_rows("trades.csv")
               if (r.get("placed_utc", "").startswith(today)
                   and "ERROR" in (r.get("status") or "").upper())]
    except OSError:
        bad = []
        notes.append("trades.csv unreadable -- order check skipped")
    if bad:
        alarm("ORDERS", f"ORDER FAILED today ({len(bad)}) -- the bot "
              f"had a pick and could not pay for it. Likely an empty "
              f"wallet: fund the Kalshi account.")

    # -- BAND: no order ever leaves the owner's price band. The band --
    # -- is read from trader.py's own source line (never a mirrored ---
    # -- copy that can drift), so this alarm is judged by the exact ---
    # -- numbers the trader enforces. BAND_SINCE_UTC: judge only ------
    # -- orders placed after the current band took effect -- move it --
    # -- in the same commit as any band change, or the day's earlier --
    # -- (then-legal) orders retro-alarm all evening (seen live on ----
    # -- Aug 30 when 40 -> 45 flagged that morning's 43-44c buys) -----
    BAND_SINCE_UTC = "2026-08-30T23:00:00"   # the 45-60 tightening
    try:
        import re
        src = open("trader.py").read()
        m = re.search(r"^MIN_COST\s*,\s*MAX_COST\s*=\s*(\d+)\s*,\s*(\d+)",
                      src, re.M)
        lo, hi = int(m.group(1)), int(m.group(2))
        out = [r for r in read_tail_rows("trades.csv")
               if r.get("placed_utc", "").startswith(today)
               and r.get("placed_utc", "") >= BAND_SINCE_UTC
               and (r.get("limit_cents") or "").isdigit()
               and not lo <= int(r["limit_cents"]) <= hi]
        if out:
            alarm("BAND", f"ORDER OUTSIDE THE {lo}-{hi}c BAND today "
                  f"({len(out)}) -- this must be impossible. Stop the "
                  f"bot and audit trader.py before the next buy.")
    except (OSError, AttributeError):
        notes.append("band check skipped (could not read trader.py's "
                     "MIN_COST/MAX_COST line)")

    # -- SWOOP: inside its 15-minute band the advisor board must be ---
    # -- fresh (positions are graded there in their riskiest hours) ---
    if now.hour >= 16 or now.hour < 2:
        t = newest_ts("swoop_log.csv", "checked_utc")
        if t is not None:
            age = (now - t).total_seconds() / 60
            if age > SWOOP_STALE_MIN:
                alarm("SWOOP", f"SWOOP BOARD STALE -- last graded "
                      f"{age:.0f} min ago (limit {SWOOP_STALE_MIN}) "
                      f"during its 15-minute band. Open positions are "
                      f"being graded on old readings. Press Run on "
                      f"swoop.yml.")

    # -- SETTLEMENTS: the official-results feed (4x daily) ------------
    t = newest_ts("settlements.csv", "checked_utc", tail_bytes=100_000)
    if t is not None:
        age = (now - t).total_seconds() / 60
        if age > SETTLE_STALE_MIN:
            alarm("SETTLE", f"SETTLEMENTS STALE -- last checked "
                  f"{age / 60:.1f} h ago. Yesterday lines and the "
                  f"calibration's actuals are running behind. Press "
                  f"Run on settlements.yml.")

    # -- keep each alarm's first-seen time across passes --------------
    prev = {}
    try:
        with open(HEALTH_PATH) as f:
            for a in json.load(f).get("alarms", []):
                prev[a.get("code")] = a.get("since")
    except (OSError, ValueError):
        pass
    for a in alarms:
        a["since"] = prev.get(a["code"]) or now.isoformat(timespec="seconds")

    health = {
        "checked_utc": now.isoformat(timespec="seconds"),
        "ok": not alarms,
        "alarms": alarms,
        "notes": notes,
    }
    with open(HEALTH_PATH, "w") as f:
        json.dump(health, f, indent=1)
        f.write("\n")

    for n in notes:
        print(f"watchdog note: {n}")
    if alarms:
        for a in alarms:
            print(f"WATCHDOG ALARM [{a['code']}] since {a['since']}: "
                  f"{a['msg']}")
        sys.exit(2)
    print(f"watchdog: all pulses OK at {now.strftime('%H:%M')} UTC "
          f"({len(notes)} note(s))")


if __name__ == "__main__":
    main()
