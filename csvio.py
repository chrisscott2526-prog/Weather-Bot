"""Weather-Bot: header-safe CSV appending.

THE BUG THIS EXISTS TO KILL (found in the Aug 18 2026 audit):

Every logger in this repo used the same pattern --

    new = not os.path.exists(OUT)
    w = csv.writer(f)
    if new:
        w.writerow([...header...])

-- which writes the header EXACTLY ONCE, on the day the file is born.
Add a column to the writer six weeks later and the header on disk is
never updated. The file keeps growing with rows that are one column
wider than the header claims, and nothing raises: csv.DictReader maps
by POSITION, so every column after the insertion point silently shifts
one place left. A team name lands in ask_cents. An age in minutes lands
in market_cents. Readers do not crash, they just quietly read the wrong
column forever.

Four files had drifted this way (temps_log, swoop_log, sports_picks,
forecasts) and it had already switched sports grading off entirely.

The fix: writers declare their columns, and align() makes the file on
disk match that declaration before a single row is appended.

Cost: align() reads only the first line when the header is already
correct, which is the case on every run after the first. A full rewrite
happens only on the run where columns actually changed -- which is
exactly when a rewrite is the point.
"""

import csv
import os
from contextlib import contextmanager


# ---------------------------------------------------------------------
# forecasts.csv row semantics, shared by scanner.py and calibration.py
# (it lives here and not in forecast.py only because forecast.py
# imports calibration.py, and calibration.py needs this too -- putting
# it there would make a circle).

MORNING_FETCH_START_HOUR = 6   # UTC


def is_morning_row(forecast_date, fetched_utc):
    """True if a forecasts.csv row came from the same-day MORNING
    refresh (forecast.py --today) rather than the night-before pull.

    The naive rule -- "fetched on its own forecast date" -- is a trap
    the real data exposed: the 23:00 UTC nightly cron sometimes slips
    past UTC midnight, stamping fetched_utc 00:xx-04:xx on the SAME
    date it forecasts. Those are still night-before forecasts (it is
    evening, local, in every one of our cities). So a row counts as
    morning only when it is BOTH same-UTC-day-or-later AND fetched
    between 06:00 and 22:59 UTC: the morning refresh runs ~13:45,
    while nightly runs and their past-midnight stragglers land
    23:00-05:59. Rows with no fetched_utc are old nightly rows."""
    d = (forecast_date or "").strip()
    f = (fetched_utc or "").strip()
    if not d or not f or f[:10] < d:
        return False
    try:
        hour = int(f[11:13])
    except (ValueError, IndexError):
        return False
    return MORNING_FETCH_START_HOUR <= hour < 23


def read_header(path):
    """First row of the file, or None if missing/empty."""
    if not os.path.exists(path):
        return None
    with open(path, newline="") as f:
        for row in csv.reader(f):
            return row
    return None


def align(path, fields, legacy=(), force=False):
    """Ensure path's header is exactly `fields`, migrating existing rows.

    `legacy` is a sequence of older column layouts this file may already
    contain. Each existing row is interpreted against whichever layout
    (current or legacy) has the same width, then re-emitted in `fields`
    order -- so a column added in the middle moves the old values back
    where they belong instead of leaving them shifted.

    Returns (changed, n_rows, n_unmapped). Rows whose width matches no
    known layout are padded/truncated positionally and counted in
    n_unmapped so the caller can say so out loud rather than pretend.

    By default a correct header short-circuits the whole thing after one
    line of I/O, which is what keeps this cheap enough to run on every
    poll. Pass force=True to also normalise row widths and drop blank
    lines -- worth it for a one-off repair, too expensive per run.
    """
    header = read_header(path)
    if header is None:
        return False, 0, 0
    if header == list(fields) and not force:
        return False, 0, 0          # the fast path: nothing to do

    layouts = {len(fields): list(fields)}
    for lay in legacy:
        layouts.setdefault(len(lay), list(lay))
    layouts.setdefault(len(header), list(header))

    out, unmapped = [], 0
    with open(path, newline="") as f:
        rows = list(csv.reader(f))
    for i, row in enumerate(rows):
        if i == 0 or not any(cell.strip() for cell in row):
            continue                # drop the stale header and blank lines
        lay = layouts.get(len(row))
        if lay is None:
            unmapped += 1
            vals = (row + [""] * len(fields))[:len(fields)]
            out.append(dict(zip(fields, vals)))
            continue
        rec = dict(zip(lay, row))
        out.append({k: rec.get(k, "") for k in fields})

    if force and header == list(fields):
        with open(path, newline="") as f:
            before = list(csv.reader(f))
        if len(before) - 1 == len(out) and all(
                len(r) == len(fields) for r in before[1:]):
            return False, 0, 0      # already conforming, nothing to rewrite

    tmp = path + ".tmp"
    with open(tmp, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(fields), extrasaction="ignore")
        w.writeheader()
        for rec in out:
            w.writerow(rec)
    os.replace(tmp, path)
    return True, len(out), unmapped


@contextmanager
def appender(path, fields, legacy=(), verbose=True):
    """Append rows to `path` with a guaranteed-correct header.

    Yields a csv.DictWriter. Creates the file with a header if missing,
    and realigns it first if its columns have drifted from `fields`.
    """
    changed, n, unmapped = align(path, fields, legacy)
    if changed and verbose:
        msg = f"{path}: header realigned to {len(fields)} columns ({n} rows)"
        if unmapped:
            msg += f" -- {unmapped} row(s) matched no known layout"
        print(msg)
    new = not os.path.exists(path) or read_header(path) is None
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(fields), extrasaction="ignore")
        if new:
            w.writeheader()
        yield w
