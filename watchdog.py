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
  SWOOP        swoop_pulse.json fresh in its 15-min band (16:00-01:59 UTC;
               the pulse, not the log -- a no-bet day writes zero log
               rows honestly, which is not a dead grader)
  SETTLEMENTS  settlements.csv checked recently         (always)

health.json is a FULL-REWRITE file (never add it to the union-merge
list in .gitattributes) and it is NOT a money input: no scanner,
trader, or grader reads it. It carries its own checked_utc so the
board can refuse to trust a stale one -- a silent watchdog shows as
an alarm on the board, never as green (the derived-file law's
fail-closed rule).

THE DAY'S MEMORY (Sep 10 2026). health.json holds only the CURRENT
second, so a morning outage vanished from the board the moment it
ended. On Sep 10 the money lane was dead from 13:19 to 17:04 UTC --
the watchdog alarmed for 3h45m -- and by the time the owner looked at
18:24 the banner read "Self-check OK" with no trace of it, while the
cards below said nothing had been bought. A self-check that forgets
is a self-check the owner cannot trust. So every pass now also
appends one row to health_log.csv (append-only, union-merged), and
health.json's "today" block is RECOMPUTED from that log each pass --
never carried forward from the previous health.json. That is the
highs.py law applied to the pulse: the displayed summary comes from
the raw log every time, so a dropped commit or a push race can never
strand a half-remembered day. Each alarm's "since" is recomputed the
same way (the start of its current unbroken run today).

THE THIRD STARTER (Sep 10 2026, owner decision). The relay had two
ways to be started -- GitHub's cron and the owner's Claude routines --
and on Sep 10 BOTH failed on the same morning: cron dropped seven
starts in a row (13:07 through 16:07) and the routines fired into
sessions blocked by an account usage limit, so the relay did not
start until 16:56 and three time zones went unbought. The watchdog
already KNEW at 13:19; it just wrote the fact down. Now it can press
the button: run with --start-money-lane and a MONEY LANE alarm also
dispatches morning.yml through the Actions API. This is a third
starter on infrastructure that survived that outage (the poller relay
polled 38 times that day, right on cadence) and it depends on neither
of the two that failed. Guardrails, all deliberate:
  - it fires ONLY on a definite dead lane (check_money_lane() False);
    an unverifiable check (None) never dispatches -- fail-closed, the
    same rule that keeps it from false-alarming;
  - only inside buying hours, because only then is the check made;
  - a cooldown and a daily cap (below), counted from relay_starts.csv,
    so a persistent outage cannot become a dispatch loop;
  - every attempt, win or lose, is logged to relay_starts.csv;
  - a failed dispatch is a note and the alarm STANDS -- the run still
    goes red. Pressing the button is a rescue, never a reason to stop
    telling the owner the lane was down.
Extra starts are harmless by the relay's own design: they queue in the
morning-money-relay concurrency group and stand down in seconds, or
take over if the running relay died. The 9-11 window gate and the
fail-closed exposure check make repeated passes safe, as always.
"""

import argparse
import csv
import io
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

from csvio import is_morning_row

HEALTH_PATH = "health.json"
HEALTH_LOG_PATH = "health_log.csv"
HEALTH_LOG_HEADER = ["checked_utc", "ok", "alarms", "notes"]
RELAY_STARTS_PATH = "relay_starts.csv"
RELAY_STARTS_HEADER = ["dispatched_utc", "workflow", "result", "detail"]

# Staleness thresholds, in minutes. Generous on purpose: every one of
# these feeds runs on a 15-minute cadence when healthy, so a 45-minute
# silence means at least two missed beats -- a real outage, not jitter.
POLL_STALE_MIN = 40          # relay writes every ~15 min
SWOOP_STALE_MIN = 45         # swoop band runs every 15 min
SETTLE_STALE_MIN = 9 * 60    # settlements.py runs 4x daily
LANE_RUN_GRACE_MIN = 40      # a relay handoff gap larger than this is real

# --start-money-lane limits. The relay itself makes extra starts
# harmless, so these exist to stop a RUNAWAY (a broken API, a token
# that cannot dispatch) from hammering the Actions queue all day --
# not to ration rescues. One start every 20 min covers the whole
# 13:15-18:45 buying window inside the daily cap with room to spare.
RELAY_START_COOLDOWN_MIN = 20
MAX_RELAY_STARTS_PER_DAY = 6


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


def append_log_row(path, header, row):
    """Append one row to an append-only CSV, writing the header first
    if the file is missing or empty. Columns are written BY NAME in
    header order (the header-drift law). Returns True on success; a
    logging failure must never take the watchdog down, so callers
    treat False as a note."""
    try:
        need_header = (not os.path.exists(path)
                       or os.path.getsize(path) == 0)
        with open(path, "a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=header)
            if need_header:
                w.writeheader()
            w.writerow({k: row.get(k, "") for k in header})
        return True
    except OSError:
        return False


def todays_pulse_history(now, tail_bytes=200_000):
    """Recompute today's alarm history from health_log.csv -- the raw
    log, every pass, never carried forward from the last health.json
    (the highs.py law). Returns (since_by_code, today_block):

      since_by_code  code -> start of its CURRENT unbroken run today,
                     so a re-alarm after a clean spell dates from the
                     re-alarm, not from this morning.
      today_block    what the board shows once the alarm has cleared:
                     every code seen today with first/last time and
                     how many passes it fired.

    Union merge can interleave rows at the tail, so rows are sorted by
    timestamp before they are read as a sequence."""
    today = now.strftime("%Y-%m-%d")
    try:
        rows = read_tail_rows(HEALTH_LOG_PATH, tail_bytes)
    except OSError:
        return {}, {"date": today, "passes": 0, "alarms": []}

    seq = []
    for r in rows:
        t = parse_ts(r.get("checked_utc", ""))
        if t is None or t.strftime("%Y-%m-%d") != today:
            continue
        codes = [c for c in (r.get("alarms") or "").split("|") if c]
        seq.append((t, codes))
    seq.sort(key=lambda x: x[0])

    seen = {}
    for t, codes in seq:
        for c in codes:
            e = seen.setdefault(c, {"code": c, "first_utc": None,
                                    "last_utc": None, "passes": 0})
            if e["first_utc"] is None:
                e["first_utc"] = t.isoformat(timespec="seconds")
            e["last_utc"] = t.isoformat(timespec="seconds")
            e["passes"] += 1

    # start of each code's current unbroken run: walk backwards from
    # the newest pass while the code is still present
    since = {}
    if seq:
        for c in seq[-1][1]:
            start = seq[-1][0]
            for t, codes in reversed(seq[:-1]):
                if c not in codes:
                    break
                start = t
            since[c] = start.isoformat(timespec="seconds")

    today_block = {
        "date": today,
        "passes": len(seq),
        "alarms": sorted(seen.values(), key=lambda e: e["first_utc"]),
    }
    return since, today_block


def relay_starts_today(now):
    """Dispatches this script already made today, newest first. A log
    that cannot be read counts as 'unknown' and blocks the dispatch --
    fail-closed: never press a button we cannot count."""
    today = now.strftime("%Y-%m-%d")
    if not os.path.exists(RELAY_STARTS_PATH):
        return []
    try:
        rows = read_tail_rows(RELAY_STARTS_PATH, 100_000)
    except OSError:
        return None
    out = []
    for r in rows:
        t = parse_ts(r.get("dispatched_utc", ""))
        if t and t.strftime("%Y-%m-%d") == today:
            out.append((t, r))
    out.sort(key=lambda x: x[0], reverse=True)
    return out


def start_money_lane(now, notes):
    """Press Run on morning.yml -- the third starter (see the module
    docstring). Called ONLY when the money-lane check came back a
    definite False during buying hours. Returns True if GitHub
    accepted the dispatch. Every outcome is appended to
    relay_starts.csv, including the ones we decline to make, so the
    owner can see the rescue attempts as plainly as the alarms."""
    repo = os.environ.get("GITHUB_REPOSITORY")
    token = os.environ.get("GITHUB_TOKEN")
    if not repo or not token:
        notes.append("money-lane auto-start skipped (no GITHUB_REPOSITORY"
                     "/GITHUB_TOKEN -- not inside GitHub Actions)")
        return False

    prior = relay_starts_today(now)
    if prior is None:
        notes.append(f"money-lane auto-start skipped ({RELAY_STARTS_PATH} "
                     f"unreadable, so today's starts cannot be counted)")
        return False
    # The CAP counts only starts GitHub accepted: it answers "how many
    # times have we already rescued this lane today", and hitting it
    # means the relay keeps dying for a reason a restart cannot fix.
    ok_prior = [(t, r) for t, r in prior if r.get("result") == "dispatched"]
    if len(ok_prior) >= MAX_RELAY_STARTS_PER_DAY:
        notes.append(f"money-lane auto-start skipped -- already started "
                     f"the relay {len(ok_prior)} times today (cap "
                     f"{MAX_RELAY_STARTS_PER_DAY}). Something is killing "
                     f"the relay: press Run by hand and look at the run "
                     f"log.")
        return False
    # The COOLDOWN counts EVERY attempt, failures included. A dispatch
    # that keeps failing (a token without actions: write, say) is not
    # a reason to retry it every 15 minutes for five hours -- that
    # floods the API and the log with the same message. It retries on
    # the same 20-minute rhythm as a successful rescue, and each row
    # carries the fix, so the owner sees the cause once and often
    # enough rather than 22 times.
    if prior:
        age = (now - prior[0][0]).total_seconds() / 60
        if age < RELAY_START_COOLDOWN_MIN:
            notes.append(f"money-lane auto-start held -- last attempt "
                         f"was {age:.0f} min ago (cooldown "
                         f"{RELAY_START_COOLDOWN_MIN} min)")
            return False

    url = (f"https://api.github.com/repos/{repo}/actions/workflows/"
           f"morning.yml/dispatches")
    body = json.dumps({"ref": "main"}).encode()
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "weather-bot-watchdog",
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            code = resp.status
        result, detail = "dispatched", f"HTTP {code}"
        notes.append("money-lane auto-start: pressed Run on morning.yml "
                     "(the relay was not running during buying hours)")
        ok = True
    except urllib.error.HTTPError as e:
        hint = ""
        if e.code in (403, 404):
            hint = (" -- poll.yml needs 'actions: write' permission for "
                    "this, or press Run on morning.yml by hand")
        result, detail = "failed", f"HTTP {e.code}{hint}"
        notes.append(f"money-lane auto-start FAILED ({detail})")
        ok = False
    except Exception as e:
        result, detail = "failed", str(e)[:200]
        notes.append(f"money-lane auto-start FAILED ({detail})")
        ok = False

    if not append_log_row(RELAY_STARTS_PATH, RELAY_STARTS_HEADER, {
        "dispatched_utc": now.isoformat(timespec="seconds"),
        "workflow": "morning.yml",
        "result": result,
        "detail": detail,
    }):
        notes.append(f"could not append to {RELAY_STARTS_PATH}")
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "--start-money-lane", action="store_true",
        help="if the money lane is definitely dead during buying hours, "
             "dispatch morning.yml (the third starter). Off by default: "
             "the watchdog stays read-only unless a caller opts in.")
    args = ap.parse_args(argv)

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
            # THE THIRD STARTER: don't just write it down -- press the
            # button. The alarm stands either way (see the docstring):
            # a rescued day is still a day the two scheduled starters
            # failed, and the owner must be told that.
            if args.start_money_lane:
                start_money_lane(now, notes)

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

    # -- SWOOP: inside its 15-minute band the grader must be ALIVE. ---
    # -- The pulse file (swoop_pulse.json, written by swoop_alert.py --
    # -- every run, positions or not) is the heartbeat; the log alone -
    # -- cannot tell "grader dead" from "nothing to grade" -- on a ----
    # -- no-bet day it honestly writes zero rows, and on Sep 1 2026 ---
    # -- that false-alarmed SWOOP BOARD STALE all evening. The log ----
    # -- check remains only as the fallback for a repo where the ------
    # -- pulse has never been written (day zero / forks). -------------
    if now.hour >= 16 or now.hour < 2:
        if os.path.exists("swoop_pulse.json"):
            try:
                with open("swoop_pulse.json") as f:
                    t = parse_ts(json.load(f).get("checked_utc", ""))
            except (OSError, ValueError):
                t = None
            if t is None:
                alarm("SWOOP", "SWOOP PULSE UNREADABLE -- "
                      "swoop_pulse.json exists but carries no valid "
                      "timestamp, so the grader cannot prove it is "
                      "alive. Press Run on swoop.yml.")
            else:
                age = (now - t).total_seconds() / 60
                if age > SWOOP_STALE_MIN:
                    alarm("SWOOP", f"SWOOP GRADER DEAD -- it last ran "
                          f"{age:.0f} min ago (limit {SWOOP_STALE_MIN}) "
                          f"during its 15-minute band. Any open "
                          f"positions are being graded on old readings. "
                          f"Press Run on swoop.yml.")
        else:
            t = newest_ts("swoop_log.csv", "checked_utc")
            if t is not None:
                age = (now - t).total_seconds() / 60
                if age > SWOOP_STALE_MIN:
                    alarm("SWOOP", f"SWOOP BOARD STALE -- last graded "
                          f"{age:.0f} min ago (limit {SWOOP_STALE_MIN}) "
                          f"during its 15-minute band. Open positions "
                          f"are being graded on old readings. Press Run "
                          f"on swoop.yml.")

    # -- SETTLEMENTS: the official-results feed (4x daily) ------------
    t = newest_ts("settlements.csv", "checked_utc", tail_bytes=100_000)
    if t is not None:
        age = (now - t).total_seconds() / 60
        if age > SETTLE_STALE_MIN:
            alarm("SETTLE", f"SETTLEMENTS STALE -- last checked "
                  f"{age / 60:.1f} h ago. Yesterday lines and the "
                  f"calibration's actuals are running behind. Press "
                  f"Run on settlements.yml.")

    # -- THE DAY'S MEMORY: record this pass in the append-only log, --
    # -- then recompute both the "since" times and today's history ---
    # -- FROM that log. Nothing is carried forward from the previous -
    # -- health.json, so a dropped commit or a push race can never ---
    # -- strand a half-remembered day (the highs.py law). -------------
    if not append_log_row(HEALTH_LOG_PATH, HEALTH_LOG_HEADER, {
        "checked_utc": now.isoformat(timespec="seconds"),
        "ok": "yes" if not alarms else "no",
        "alarms": "|".join(a["code"] for a in alarms),
        "notes": "|".join(notes),
    }):
        notes.append(f"could not append to {HEALTH_LOG_PATH} -- today's "
                     f"history on the board will be short by this pass")

    since, today_block = todays_pulse_history(now)
    for a in alarms:
        a["since"] = since.get(a["code"]) or now.isoformat(timespec="seconds")

    health = {
        "checked_utc": now.isoformat(timespec="seconds"),
        "ok": not alarms,
        "alarms": alarms,
        "notes": notes,
        "today": today_block,
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
    earlier = today_block.get("alarms") or []
    if earlier:
        # Clear NOW is not the same as clear TODAY. Say so in the run
        # log too, not only on the board -- a rescued outage that
        # leaves no trace anywhere is the failure this fix exists for.
        recap = ", ".join(f"{e['code']} ({e['first_utc'][11:16]}-"
                          f"{e['last_utc'][11:16]} UTC, {e['passes']}x)"
                          for e in earlier)
        print(f"watchdog: all pulses OK at {now.strftime('%H:%M')} UTC "
              f"({len(notes)} note(s)) -- but EARLIER TODAY: {recap}")
        return
    print(f"watchdog: all pulses OK at {now.strftime('%H:%M')} UTC "
          f"({len(notes)} note(s))")


if __name__ == "__main__":
    main()
