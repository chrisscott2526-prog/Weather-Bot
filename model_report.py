"""Weather-Bot: THE MODEL LAB's scoreboard (Aug 31 2026).

Grades every forecast model we log -- the two that vote real money
(gfs, ecmwf, via forecasts.csv's member_models tags), the pooled
median the money actually used (pool), and the research passengers in
model_research.csv (icon, nws) -- against the OFFICIAL settled number
for each city and day, and writes the standings to model_report.md.

The actual is the settled bracket midpoint from settlements.csv
(both-bounds rows only) -- the same truth calibration and the city
standings trust, and the reason this report can exist at all: it is
a cache of Kalshi's immutable settlement facts.

Night-lane rows only (csvio.is_morning_row must be False), so every
model is graded on the same job: last night's call about today,
made at the same time of night. Morning refreshes answer an easier
question and would flatter whichever file logged more of them.

Apples-to-apples caveat, stated plainly: gfs/ecmwf members in
forecasts.csv are stored AFTER calibration (both models get the same
bias shift and spread widening, so their heads-up comparison is
fair), while icon and nws rows are raw model output. A calibrated
model carries an advantage the raw passengers don't get -- so a
passenger that merely TIES the incumbents here is doing well, and
one that beats them is shouting. The per-model bias column shows
what a calibration could remove.

Display/analysis ONLY: model_report.md is a full-rewrite derived
file that NO code reads (same standing as autopsy.md). NEVER add it
to the union-merge list. Nothing that trades, scans, or calibrates
reads this script's output. Promotion of any model into the voting
pool is an owner decision made on this report's evidence.

Usage:  python model_report.py          # writes + prints model_report.md
"""

import csv, os
from statistics import median
from cities import STATIONS
from csvio import is_morning_row

FORECASTS = "forecasts.csv"
RESEARCH = "model_research.csv"
SETTLEMENTS = "settlements.csv"
OUT = "model_report.md"
POOL_TAG = "pool"


def load_actuals():
    """(date, station) -> settled bracket midpoint F. Both-bounds rows
    only: an open-ended tail has no honest midpoint."""
    out = {}
    if not os.path.exists(SETTLEMENTS):
        return out
    with open(SETTLEMENTS, newline="") as f:
        for r in csv.DictReader(f):
            lo, hi = (r.get("low_f") or "").strip(), (r.get("high_f") or "").strip()
            if not lo or not hi:
                continue
            try:
                out[(r["date"], r["station"])] = (float(lo) + float(hi)) / 2
            except (ValueError, KeyError):
                continue
    return out


def night_forecasts():
    """(date, station, model) -> forecast high F, night rows only,
    last row wins on a re-run. Splits tagged members per model and
    always includes the pooled median the money used."""
    out = {}
    if not os.path.exists(FORECASTS):
        return out
    with open(FORECASTS, newline="") as f:
        for r in csv.DictReader(f):
            d, sid = (r.get("forecast_date") or "").strip(), (r.get("station") or "").strip()
            if not d or not sid or is_morning_row(d, r.get("fetched_utc") or ""):
                continue
            try:
                out[(d, sid, POOL_TAG)] = float(r.get("forecast_high_f"))
            except (TypeError, ValueError):
                continue
            raw_m = (r.get("members") or "").strip()
            raw_t = (r.get("member_models") or "").strip()
            if not raw_m or not raw_t:
                continue
            members = raw_m.split("|")
            tags = raw_t.split("|")
            if len(members) != len(tags):
                continue   # never grade mislabeled members
            per = {}
            for m, t in zip(members, tags):
                try:
                    per.setdefault(t, []).append(float(m))
                except ValueError:
                    continue
            for t, vals in per.items():
                if vals:
                    out[(d, sid, t)] = round(median(vals), 1)
    return out


def research_forecasts():
    """(date, station, model) -> forecast high F from the research
    log, night rows only, last row wins."""
    out = {}
    if not os.path.exists(RESEARCH):
        return out
    with open(RESEARCH, newline="") as f:
        for r in csv.DictReader(f):
            d, sid = (r.get("forecast_date") or "").strip(), (r.get("station") or "").strip()
            tag = (r.get("model") or "").strip()
            if not d or not sid or not tag:
                continue
            if is_morning_row(d, r.get("fetched_utc") or ""):
                continue
            try:
                out[(d, sid, tag)] = float(r.get("forecast_high_f"))
            except (TypeError, ValueError):
                continue
    return out


def grade():
    """city -> model -> (n, median |error|, median signed error)."""
    actuals = load_actuals()
    forecasts = {**research_forecasts(), **night_forecasts()}
    errs = {}
    for (d, sid, tag), fc in forecasts.items():
        act = actuals.get((d, sid))
        if act is None:
            continue
        city = STATIONS.get(sid, sid)
        errs.setdefault(city, {}).setdefault(tag, []).append(fc - act)
    table = {}
    for city, models in errs.items():
        table[city] = {
            tag: (len(e), median(abs(x) for x in e), median(e))
            for tag, e in models.items()}
    return table


def render(table):
    tags = sorted({t for m in table.values() for t in m},
                  key=lambda t: (t != POOL_TAG, t))
    lines = [
        "# Model report -- who forecasts each city best",
        "",
        "Median miss (degrees F) between each model's night-before",
        "forecast and the officially settled number, per city; the",
        "signed lean in brackets (+ runs hot, - runs cold). `pool` is",
        "the calibrated GFS+ECMWF median the money actually used;",
        "`gfs`/`ecmwf` are its two voters graded separately (also",
        "calibrated); `icon`/`nws` are raw research passengers riding",
        "along -- a passenger that ties the calibrated incumbents is",
        "doing well. Small n means luck still speaks louder than",
        "skill. RESEARCH ONLY: no trading or calibration code reads",
        "this file, and promotion of any model into the vote is an",
        "owner decision. Regenerated in full by model_report.py.",
        "",
        "| city | " + " | ".join(tags) + " |",
        "|---|" + "---|" * len(tags),
    ]
    for city in sorted(table):
        cells = []
        for t in tags:
            v = table[city].get(t)
            cells.append(f"{v[1]:.1f} ({v[2]:+.1f}) n={v[0]}" if v else "-")
        lines.append(f"| {city} | " + " | ".join(cells) + " |")

    lines += ["", "## Overall (all cities pooled)", ""]
    return lines


def main():
    table = grade()
    if not table:
        print("model report: nothing gradeable yet (no settled days "
              "overlap the logged forecasts) -- writing the empty truth")
    lines = render(table)

    # overall standings need the raw errors, not per-city medians
    actuals = load_actuals()
    forecasts = {**research_forecasts(), **night_forecasts()}
    allerrs = {}
    for (d, sid, tag), fc in forecasts.items():
        act = actuals.get((d, sid))
        if act is not None:
            allerrs.setdefault(tag, []).append(fc - act)
    for tag in sorted(allerrs, key=lambda t: median(abs(x) for x in allerrs[t])):
        e = allerrs[tag]
        lines.append(f"- **{tag}**: median miss "
                     f"{median(abs(x) for x in e):.2f}F, lean "
                     f"{median(e):+.2f}F, n={len(e)}")
    lines.append("")

    with open(OUT, "w") as f:
        f.write("\n".join(lines))
    print("\n".join(lines))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
