"""Weather-Bot: loss autopsy. Reads results.csv (the scoreboard),
trades.csv (prices, subtitles, model confidence) and daily_highs.csv
(the poller's instrument readings) and answers, for every settled bet:
where did the day's actual high land relative to the bracket we bought?

Verdicts per bet:
  WIN             settlement put the high inside our bracket
  MISS-HIGH-BY-1  the high landed exactly one bracket ABOVE our pick
  MISS-LOW-BY-1   exactly one bracket BELOW
  MISS-FAR        two or more brackets away, either direction
  UNRESOLVED      we lost but no instrument reading exists for that
                  city/day -- reported loudly, never guessed

Where the "actual high" comes from, in order of trust:
  1. Settlement. A WIN pins the high inside our bracket -- Kalshi's
     result is the only thermometer that pays.
  2. Instrument (daily_highs.csv) for losses. One physical fact does
     real work here: the poller's number is a floored running max of
     hourly readings, so the OFFICIAL high can only be equal or
     HIGHER -- never lower. So when we lost but the instrument reading
     sits inside our bracket, the official high must have escaped out
     the TOP (the CLI report catches between-hour peaks the METAR
     misses): that is scored MISS-HIGH-BY-1 with source
     "settlement+instrument".

READ-ONLY against the betting pipeline: this script writes autopsy.md
and nothing else. It changes no picks, no trades, no guards.

Run manually:  python autopsy.py
Automated:     .github/workflows/autopsy.yml after every settle sweep.
"""

import csv, math, os, re
from datetime import datetime, timezone

from cities import CITY_TO_STATION

RESULTS = "results.csv"
TRADES = "trades.csv"
HIGHS = "daily_highs.csv"
OUT = "autopsy.md"

BRACKET_WIDTH = 2          # Kalshi HIGH brackets cover 2 whole degrees
MIN_BETS_FOR_HINTS = 30    # below this, everything is a hint

TICKER_RE = re.compile(r"-(\d{2}[A-Z]{3}\d{2})-([BT])(\d+(?:\.\d+)?)$")
TAIL_RE = re.compile(r"(\d+(?:\.\d+)?)\s*°?\s*or\s+(above|below)", re.I)


def ticker_date(token):
    """'26AUG17' -> '2026-08-17' (same parse calibration.py uses)."""
    return datetime.strptime(token, "%y%b%d").date().isoformat()


def load_trade_info():
    """ticker -> (subtitle, model_pct) from the first successfully
    submitted row. ERROR/DRY_RUN rows never describe a real position."""
    info = {}
    if not os.path.exists(TRADES):
        return info
    with open(TRADES) as f:
        for r in csv.DictReader(f):
            tick = (r.get("ticker") or "").strip()
            status = (r.get("status") or "").strip().lower()
            if not tick or tick in info or status != "submitted":
                continue
            try:
                pct = float(r.get("model_pct") or "")
            except ValueError:
                pct = None
            info[tick] = ((r.get("subtitle") or "").strip(), pct)
    return info


def load_instrument_highs():
    """(date, station) -> floored METAR running high."""
    out = {}
    if not os.path.exists(HIGHS):
        return out
    with open(HIGHS) as f:
        for r in csv.DictReader(f):
            try:
                out[(r["date"], r["station"])] = float(r["high_f"])
            except (KeyError, ValueError):
                continue
    return out


def bracket_bounds(kind, num, subtitle):
    """(lo, hi) of the bracket we bought; None = open end.
    B80.5 covers highs of 80 and 81. Tail direction comes from the
    subtitle because the ticker number alone lies (Boston T74 is
    '73 or below' while San Francisco T74 is '75 or above')."""
    if kind == "B":
        return num - 0.5, num + 0.5
    m = TAIL_RE.search(subtitle)
    if not m:
        return None, None            # tail with unknown direction
    edge = float(m.group(1))
    if m.group(2).lower() == "above":
        return edge, None
    return None, edge


def classify(row, tinfo, highs):
    """One graded bet -> dict with verdict, actual-high source, etc."""
    tick = row["ticker"]
    m = TICKER_RE.search(tick)
    out = {"ticker": tick, "city": (row.get("city") or "").strip(),
           "cost": row.get("cost_cents", ""), "result": row["result"],
           "pnl": row.get("pnl", ""), "date": "?", "bracket": "?",
           "verdict": "UNRESOLVED", "source": "-", "direction": None,
           "model_pct": None}
    if not m:
        print(f"SKIP {tick}: ticker does not parse -- cannot autopsy")
        return out
    out["date"] = ticker_date(m.group(1))
    subtitle, model_pct = tinfo.get(tick, ("", None))
    out["model_pct"] = model_pct
    lo, hi = bracket_bounds(m.group(2), float(m.group(3)), subtitle)
    if lo is None and hi is None:
        print(f"SKIP {tick}: tail bracket with no subtitle on file")
        return out
    out["bracket"] = subtitle or f"{lo:g}-{hi:g}"

    if row["result"] == "WIN":
        out.update(verdict="WIN", source="settlement")
        return out

    # A loss: locate the high with the instrument reading.
    station = CITY_TO_STATION.get(out["city"], "")
    reading = highs.get((out["date"], station))
    if reading is None:
        print(f"UNRESOLVED {out['city']} {out['date']}: lost, but no "
              f"instrument reading on file for {station or '???'}")
        return out
    h = math.floor(reading + 0.5)    # nearest whole degree, like the CLI

    if hi is not None and h > hi:
        n, out["direction"] = math.ceil((h - hi) / BRACKET_WIDTH), "high"
    elif lo is not None and h < lo:
        n, out["direction"] = math.ceil((lo - h) / BRACKET_WIDTH), "low"
    else:
        # Instrument says in-bracket, settlement says NO. The floored
        # instrument max can only understate, so the official high
        # escaped out the top.
        n, out["direction"] = 1, "high"
        out.update(verdict="MISS-HIGH-BY-1", source="settlement+instrument")
        return out

    out["source"] = "instrument"
    if n == 1:
        out["verdict"] = f"MISS-{out['direction'].upper()}-BY-1"
    else:
        out["verdict"] = "MISS-FAR"
    return out


# ---------- report helpers ----------
def pct(part, whole):
    return f"{100.0 * part / whole:.0f}%" if whole else "-"


def tally(bets):
    t = {"n": len(bets), "win": 0, "hi1": 0, "lo1": 0,
         "far": 0, "unres": 0, "far_hi": 0, "far_lo": 0}
    for b in bets:
        v = b["verdict"]
        if v == "WIN":
            t["win"] += 1
        elif v == "MISS-HIGH-BY-1":
            t["hi1"] += 1
        elif v == "MISS-LOW-BY-1":
            t["lo1"] += 1
        elif v == "MISS-FAR":
            t["far"] += 1
            t["far_hi" if b["direction"] == "high" else "far_lo"] += 1
        else:
            t["unres"] += 1
    return t


def build_report(bets):
    lines = []
    say = lines.append
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    n = len(bets)
    say(f"# Loss autopsy — {stamp}")
    say("")
    say(f"{n} settled bet{'s' if n != 1 else ''} on the scoreboard. "
        f"Where did the day's real high land, relative to what we bought?")
    say("")

    # -- every bet, one line each --
    say("## Every settled bet")
    say("")
    say("| Date | City | Bracket bought | Price | Verdict | High located by |")
    say("|---|---|---|---|---|---|")
    for b in sorted(bets, key=lambda b: (b["date"], b["city"])):
        say(f"| {b['date']} | {b['city']} | {b['bracket']} "
            f"| {b['cost']}¢ | {b['verdict']} | {b['source']} |")
    say("")

    # -- 1. overall --
    t = tally(bets)
    say("## 1. Overall")
    say("")
    say(f"- Wins: **{t['win']} of {n}** ({pct(t['win'], n)})")
    say(f"- Missed by exactly one bracket: **{t['hi1'] + t['lo1']}** "
        f"({pct(t['hi1'] + t['lo1'], n)}) — {t['hi1']} high, {t['lo1']} low")
    say(f"- Missed far (2+ brackets): **{t['far']}** ({pct(t['far'], n)})"
        + (f" — {t['far_hi']} high, {t['far_lo']} low" if t["far"] else ""))
    if t["unres"]:
        say(f"- Unresolved (no data to locate the high): **{t['unres']}**")
    say("")

    # -- 2. per-city --
    say("## 2. Per city")
    say("")
    say("| City | Bets | Wins | 1 off, high | 1 off, low | Far | Model said | Flags |")
    say("|---|---|---|---|---|---|---|---|")
    cities = {}
    for b in bets:
        cities.setdefault(b["city"] or "???", []).append(b)
    flags_fired = False
    for city in sorted(cities):
        cb = cities[city]
        ct = tally(cb)
        highs_n = ct["hi1"] + ct["far_hi"]
        lows_n = ct["lo1"] + ct["far_lo"]
        pcts = [b["model_pct"] for b in cb if b["model_pct"] is not None]
        claimed = sum(pcts) / len(pcts) if pcts else None
        flags = []
        directional = highs_n + lows_n
        if directional >= 2 and (highs_n == 0 or lows_n == 0):
            lean = "hot" if highs_n else "cold"
            flags.append(f"every miss leans one way — station may run "
                         f"{lean} vs our model (calibration should be "
                         f"eating this)")
        if (ct["n"] >= 3 and claimed is not None
                and ct["win"] / ct["n"] < claimed / 100.0 / 2):
            flags.append("winning less than half what the model claims "
                         "— bench candidate")
        if flags:
            flags_fired = True
        model_txt = f"{claimed:.0f}%" if claimed is not None else "-"
        say(f"| {city} | {ct['n']} | {ct['win']} | {ct['hi1']} | {ct['lo1']} "
            f"| {ct['far']} | {model_txt} | {'; '.join(flags) or '-'} |")
    say("")
    if not flags_fired:
        say("No city has enough settled bets yet for a flag to mean "
            "anything (flags need repeated misses in one direction, or "
            "3+ bets underperforming the model by half).")
    if "New York City" not in cities:
        say("KNYC (Central Park) remains the standing bench suspect from "
            "the roadmap, but it has no settled bets on this scoreboard "
            "yet — nothing to judge it on so far.")
    say("")

    # -- 3. price vs outcome --
    say("## 3. What the market charged vs how we did")
    say("")
    say("| Price band | Bets | Wins | Win rate |")
    say("|---|---|---|---|")
    bands = [("under 15¢", lambda c: c < 15),
             ("15–35¢", lambda c: 15 <= c <= 35),
             ("over 35¢", lambda c: c > 35)]
    band_stats = []
    for label, fits in bands:
        bb = []
        for b in bets:
            try:
                if fits(float(b["cost"])):
                    bb.append(b)
            except ValueError:
                continue
        wins = sum(1 for b in bb if b["verdict"] == "WIN")
        band_stats.append((label, len(bb), wins))
        say(f"| {label} | {len(bb)} | {wins} | {pct(wins, len(bb))} |")
    say("")
    say("The question this table exists to answer: when the market "
        "prices our pick cheap (under 15¢), is it right and are we "
        "wrong? If the cheap band keeps losing while the mid band "
        "holds up, that is the case for raising MIN_PICK_COST.")
    say("")

    # -- 4. what this means --
    say("## 4. What this means (plain English)")
    say("")
    one_off = t["hi1"] + t["lo1"]
    losses = n - t["win"] - t["unres"]
    if one_off:
        say(f"- {one_off} of {losses} losses missed by exactly ONE "
            "bracket. Plain English: on those days the forecast found "
            "the right neighborhood and knocked on the wrong door. "
            "That pattern points at small per-station bias — the "
            "calibration's job — not at a broken strategy.")
    if t["far"]:
        say(f"- But {t['far']} of {losses} losses landed 2+ brackets "
            "away. Far misses are worse news than near misses: on "
            "those days the model wasn't even in the right "
            "neighborhood.")
    if t["hi1"] + t["far_hi"] > (t["lo1"] + t["far_lo"]) + 1:
        say("- Misses lean HIGH overall: real days ran hotter than the "
            "brackets we bought. Watch whether calibration pulls this "
            "back as it learns.")
    elif t["lo1"] + t["far_lo"] > (t["hi1"] + t["far_hi"]) + 1:
        say("- Misses lean LOW overall: real days ran cooler than the "
            "brackets we bought. Watch whether calibration pulls this "
            "back as it learns.")
    else:
        say("- Misses are split between high and low — no overall "
            "drift in one direction yet.")
    cheap = band_stats[0]
    if cheap[1] >= 3 and cheap[2] == 0:
        say(f"- The cheap band (under 15¢) is 0 for {cheap[1]}. The "
            "market priced those picks against us and was right every "
            "time — evidence toward raising MIN_PICK_COST.")
    elif cheap[1]:
        say(f"- Under-15¢ picks: {cheap[2]} win(s) in {cheap[1]} bet(s). "
            "Not enough of them yet to judge the cheap-pick rule.")
    else:
        say("- No settled bets under 15¢ yet, so the cheap-pick "
            "question is still open.")
    say("")
    say(f"**The honest caveat:** with fewer than ~{MIN_BETS_FOR_HINTS} "
        f"settled bets ({n} so far), every pattern above is a HINT, not "
        f"a conclusion. {n} coin flips can look like a trend. Per the "
        "roadmap: the scoreboard promotes, conviction never does — no "
        "rule changes, no benchings, no sizing moves on this sample.")
    say("")
    say("*Sources: `settlement` = Kalshi's own result pinned the high; "
        "`instrument` = the poller's floored METAR running max; "
        "`settlement+instrument` = the instrument read inside our "
        "bracket but Kalshi settled NO, and since the instrument can "
        "only understate, the official high must have escaped out the "
        "top. Note the instrument understates by design, so a rare "
        "loss scored `low` could in truth have overshot instead.*")
    return "\n".join(lines) + "\n"


def main():
    if not os.path.exists(RESULTS):
        print("No results.csv -- nothing to autopsy.")
        return
    tinfo = load_trade_info()
    highs = load_instrument_highs()
    bets = []
    with open(RESULTS) as f:
        for r in csv.DictReader(f):
            act = (r.get("action") or r.get("side") or "").upper()
            if act != "YES":
                if act:
                    print(f"SKIP {r.get('ticker')}: {act} bet -- the "
                          "book is YES-only, refusing to guess")
                continue
            if (r.get("result") or "").upper() not in ("WIN", "LOSS"):
                continue
            bets.append(classify(r, tinfo, highs))
    if not bets:
        print("Scoreboard is empty -- nothing to autopsy yet.")
        return
    report = build_report(bets)
    print(report)
    with open(OUT, "w") as f:
        f.write(report)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
