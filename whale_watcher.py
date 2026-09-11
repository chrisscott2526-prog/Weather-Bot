"""Weather-Bot: WHALE WATCHER (owner request, Sep 11 2026).

Watches the public Kalshi trade tape on our hand-verified markets and
logs BIG EXECUTED BETS -- nothing else. Pure data collection, built to
answer the owner's question: "out of 30 college games, where is the
big money landing -- and is it early? What do they know?"

THE LAWS (agreed with the owner before a line was written):

1. ADVISORY / RESEARCH ONLY -- FOREVER unless the scoreboard promotes.
   Nothing that trades, scans for money, or calibrates may EVER read
   whale_trades.csv or whale_results.csv. This scanner places no
   orders, needs no secrets, and cannot touch the weather bot's picks
   or the sports card's picks.
2. EXECUTED TRADES ONLY. Resting orders can be placed for show and
   cancelled -- free to fake. Money that actually filled is the only
   honest signal (same spirit as the settlement-truth law).
3. HAND-VERIFIED SERIES ONLY. The watchlist below is built from
   cities.CITIES (the 20 weather series) plus the moneyline/match
   series already hand-verified for the sports card. No discovery.
4. NO INVENTED IDENTITY. Kalshi does not expose who traded, and we
   never guess. A row is a burst of big money, not a person. Fills on
   the same market+side within BURST_GAP_S seconds are summed into one
   burst (whales slice orders); that is arithmetic, not identity.
5. GRADED BY SETTLEMENT TRUTH. Every flagged burst is graded HIT/MISS
   by Kalshi's own result field once the market settles -- the
   scoreboard's only question is "does big money actually know?"
   No P&L column: we didn't bet, so inventing one would be fake data.

Thresholds (owner's call, Sep 11 2026): $250 weather, $1000 sports.
Tune later from the logged size distribution -- an owner decision.

Outputs:
  whale_trades.csv   append-only, union-merged: one row per flagged burst
  whale_results.csv  append-only, union-merged: HIT/MISS at settlement
  whales.html        the Whale Watcher board (full rewrite, sectioned
                     CFB / NFL / NBA / MLB / WEATHER / TENNIS)
"""

import csv, json, os, time, urllib.error, urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from cities import CITIES, SERIES_TO_CITY
from csvio import appender

KBASE = "https://api.elections.kalshi.com/trade-api/v2"

TRADES_CSV = "whale_trades.csv"
RESULTS_CSV = "whale_results.csv"
PAGE = "whales.html"

TRADE_FIELDS = ["seen_utc", "sector", "series", "ticker", "event",
                "bet_on", "side", "contracts", "avg_price_cents",
                "dollars", "n_fills", "first_trade_utc",
                "last_trade_utc", "close_time_utc",
                "hours_before_close", "expert_pct", "agrees"]
RESULT_FIELDS = ["graded_utc", "sector", "ticker", "bet_on", "side",
                 "dollars", "market_result", "result"]

# Owner's thresholds, Sep 11 2026. Dollars of one burst.
WEATHER_THRESHOLD = 250
SPORTS_THRESHOLD = 1000

# Fills on the same market+side count as ONE burst while gaps stay
# under this many seconds (whales slice orders to hide size).
BURST_GAP_S = 90

# How far back each scan looks. Generous on purpose: even a day of
# skipped crons loses nothing -- the tape is still there to read.
LOOKBACK_H = 26

# The board shows the freshest window; the CSV keeps all history.
BOARD_WINDOW_H = 48

# THE WATCHLIST -- hand-verified series only, grouped in the owner's
# display order. Weather comes straight from cities.py (the single
# source of truth); the sports series are the same tickers the sports
# card verified by hand (moneyline/match series -- where "big money on
# a single team" lives; props/totals are a tweak-later).
SECTORS = [
    ("CFB",     "College Football",  ["KXNCAAFGAME"],       SPORTS_THRESHOLD),
    ("NFL",     "NFL",               ["KXNFLGAME"],         SPORTS_THRESHOLD),
    ("NBA",     "NBA",               ["KXNBAGAME"],         SPORTS_THRESHOLD),
    ("MLB",     "Major League Baseball", ["KXMLBGAME"],     SPORTS_THRESHOLD),
    ("WEATHER", "Weather",           sorted(CITIES.keys()), WEATHER_THRESHOLD),
    ("TENNIS",  "Tennis",            ["KXATPMATCH", "KXWTAMATCH"],
                                                            SPORTS_THRESHOLD),
]


def now_utc():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.isoformat(timespec="seconds")


def parse_time(v):
    """Kalshi timestamps: ISO string or epoch seconds. None on failure."""
    if v is None:
        return None
    try:
        if isinstance(v, (int, float)):
            return datetime.fromtimestamp(float(v), tz=timezone.utc)
        s = str(v).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, OSError, OverflowError):
        return None


def kget(path, label, tries=4):
    """Public (unauthenticated) Kalshi GET with 429 backoff --
    same shape as the sports card's helper."""
    req = urllib.request.Request(KBASE + path,
                                 headers={"User-Agent": "weather-bot-whales"})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r), None
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < tries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            return None, f"{label}: HTTP {e.code}"
        except Exception as e:
            return None, f"{label}: {type(e).__name__}: {e}"


def fetch_open_markets(series):
    """Open markets of one hand-verified series. None on feed failure."""
    out, cursor = [], ""
    for _ in range(6):                      # 6 pages x 200 = plenty
        path = f"/markets?series_ticker={series}&status=open&limit=200"
        if cursor:
            path += f"&cursor={cursor}"
        data, err = kget(path, series)
        if err:
            print(f"!! {series}: market fetch failed ({err})")
            return None
        out.extend(data.get("markets", []))
        cursor = data.get("cursor") or ""
        if not cursor:
            break
        time.sleep(0.3)
    return out


def fetch_trades(ticker, min_ts):
    """Executed trades for one market since min_ts (epoch s), oldest
    first. None on feed failure."""
    out, cursor = [], ""
    for _ in range(10):                     # 10 pages x 1000 = plenty
        path = f"/markets/trades?ticker={ticker}&limit=1000&min_ts={min_ts}"
        if cursor:
            path += f"&cursor={cursor}"
        data, err = kget(path, ticker)
        if err:
            print(f"!! {ticker}: trades fetch failed ({err})")
            return None
        out.extend(data.get("trades", []))
        cursor = data.get("cursor") or ""
        if not cursor:
            break
        time.sleep(0.3)
    out.sort(key=lambda t: parse_time(t.get("created_time")) or now_utc())
    return out


def market_label(sector, m):
    """Human name for what a market is about: 'Austin 99° to 100°' or
    the market title for sports ('Will Alabama beat Georgia?')."""
    sub = (m.get("yes_sub_title") or m.get("subtitle") or "").strip()
    title = (m.get("title") or "").strip()
    if sector == "WEATHER":
        city = SERIES_TO_CITY.get((m.get("ticker") or "").split("-")[0], "")
        return f"{city} {sub}".strip() or title or m.get("ticker", "")
    return sub or title or m.get("ticker", "")


def bursts_from_trades(trades):
    """Group fills on the same side into bursts (gap <= BURST_GAP_S).
    Yields dicts; caller applies the dollar threshold."""
    by_side = defaultdict(list)
    for t in trades:
        side = (t.get("taker_side") or "").lower()
        if side not in ("yes", "no"):
            continue
        price = t.get("yes_price") if side == "yes" else t.get("no_price")
        when = parse_time(t.get("created_time"))
        try:
            count = int(t.get("count"))
            price = float(price)
        except (TypeError, ValueError):
            continue
        if when is None or count <= 0 or not (0 < price < 100):
            continue
        by_side[side].append((when, count, price))
    for side, fills in by_side.items():
        fills.sort(key=lambda f: f[0])
        cur = []
        for f in fills:
            if cur and (f[0] - cur[-1][0]).total_seconds() > BURST_GAP_S:
                yield _burst(side, cur)
                cur = []
            cur.append(f)
        if cur:
            yield _burst(side, cur)


def _burst(side, fills):
    contracts = sum(c for _, c, _ in fills)
    dollars = sum(c * p for _, c, p in fills) / 100.0
    avg = sum(c * p for _, c, p in fills) / contracts
    return {"side": side, "contracts": contracts, "dollars": dollars,
            "avg_price_cents": avg, "n_fills": len(fills),
            "first": fills[0][0], "last": fills[-1][0]}


def load_logged_keys():
    """(ticker, side, first_trade_utc) of every burst already logged."""
    keys = set()
    if os.path.exists(TRADES_CSV):
        with open(TRADES_CSV) as f:
            for r in csv.DictReader(f):
                keys.add((r.get("ticker", ""), r.get("side", ""),
                          r.get("first_trade_utc", "")))
    return keys


# ---------------------------------------------------------------------
# Expert comparison -- OPPORTUNISTIC and read-only. We join against the
# freshest row our own logs already hold; a blank means "no fresh
# expert view", never a guess. Nothing here calls any paid feed.

def weather_expert(ticker, since):
    """(model_prob_pct, was_our_pick) from the freshest edges.csv row
    for this market, or (None, None)."""
    if not os.path.exists("edges.csv"):
        return None, None
    best = None
    with open("edges.csv") as f:
        for r in csv.DictReader(f):
            if r.get("market") != ticker:
                continue
            when = parse_time(r.get("scanned_utc"))
            if when is None or when < since:
                continue
            if best is None or when > best[0]:
                best = (when, r)
    if best is None:
        return None, None
    r = best[1]
    try:
        pct = float(r.get("model_prob_pct"))
    except (TypeError, ValueError):
        return None, None
    return pct, bool((r.get("pick") or "").strip())


def sports_expert(ticker, side, since):
    """De-vigged sharps %, for the whale's side, from the freshest
    sports_picks.csv row for this market, or None."""
    if not os.path.exists("sports_picks.csv"):
        return None
    best = None
    with open("sports_picks.csv") as f:
        for r in csv.DictReader(f):
            if r.get("ticker") != ticker:
                continue
            when = parse_time(r.get("scanned_utc"))
            if when is None or when < since:
                continue
            if best is None or when > best[0]:
                best = (when, r)
    if best is None:
        return None
    r = best[1]
    try:
        pct = float(r.get("books_pct"))
    except (TypeError, ValueError):
        return None
    row_side = (r.get("side") or "yes").strip().lower()
    return pct if side == row_side else round(100 - pct, 1)


# ---------------------------------------------------------------------
# Grading -- settlement truth only, same law as settle.py.

def load_flags():
    if not os.path.exists(TRADES_CSV):
        return []
    with open(TRADES_CSV) as f:
        return list(csv.DictReader(f))


def load_graded_keys():
    done = set()
    if os.path.exists(RESULTS_CSV):
        with open(RESULTS_CSV) as f:
            for r in csv.DictReader(f):
                done.add((r.get("ticker", ""), r.get("side", ""),
                          r.get("dollars", "")))
    return done


def grade_flags():
    """Ask Kalshi how flagged markets settled; write HIT/MISS rows."""
    graded = load_graded_keys()
    pending = defaultdict(list)
    horizon = now_utc() - timedelta(days=7)
    for r in load_flags():
        key = (r.get("ticker", ""), r.get("side", ""), r.get("dollars", ""))
        seen = parse_time(r.get("seen_utc"))
        if key in graded or seen is None or seen < horizon:
            continue
        pending[r["ticker"]].append(r)
    if not pending:
        print("grade: nothing pending")
        return
    stamp = iso(now_utc())
    wrote = 0
    with appender(RESULTS_CSV, RESULT_FIELDS) as w:
        for ticker, rows in pending.items():
            data, err = kget(f"/markets/{ticker}", ticker)
            if err:
                print(f"!! grade {ticker}: {err}")
                continue
            m = data.get("market", {})
            status = (m.get("status") or "").lower()
            result = (m.get("result") or "").lower()
            if status not in ("settled", "finalized") or \
                    result not in ("yes", "no"):
                continue                    # not settled yet -- next run
            for r in rows:
                won = (result == (r.get("side") or "").lower())
                w.writerow({"graded_utc": stamp,
                            "sector": r.get("sector", ""),
                            "ticker": ticker,
                            "bet_on": r.get("bet_on", ""),
                            "side": r.get("side", ""),
                            "dollars": r.get("dollars", ""),
                            "market_result": result.upper(),
                            "result": "HIT" if won else "MISS"})
                wrote += 1
            time.sleep(0.3)
    print(f"grade: wrote {wrote} settled whale results")


# ---------------------------------------------------------------------

def scan():
    """One pass over the watchlist. Returns new flag rows (also written
    to the CSV). Raises SystemExit(1) if the whole feed is dead."""
    stamp = iso(now_utc())
    since = now_utc() - timedelta(hours=LOOKBACK_H)
    min_ts = int(since.timestamp())
    logged = load_logged_keys()
    new_rows, series_ok, series_dead = [], 0, 0

    for sector, _label, series_list, threshold in SECTORS:
        # a burst can't reach $T on fewer than ~T contracts (price<$1),
        # so skip markets whose LIFETIME volume can't contain one
        min_volume = threshold
        for series in series_list:
            markets = fetch_open_markets(series)
            if markets is None:
                series_dead += 1
                continue
            series_ok += 1
            for m in markets:
                ticker = m.get("ticker") or ""
                try:
                    vol = int(m.get("volume") or 0)
                except (TypeError, ValueError):
                    vol = 0
                if not ticker or vol < min_volume:
                    continue
                trades = fetch_trades(ticker, min_ts)
                if trades is None:
                    continue
                close = parse_time(m.get("close_time"))
                for b in bursts_from_trades(trades):
                    if b["dollars"] < threshold:
                        continue
                    key = (ticker, b["side"], iso(b["first"]))
                    if key in logged:
                        continue
                    logged.add(key)
                    hours_before = ""
                    if close is not None:
                        hours_before = round(
                            (close - b["first"]).total_seconds() / 3600, 1)
                    expert, agrees = "", ""
                    if sector == "WEATHER":
                        pct, was_pick = weather_expert(ticker, since)
                        if pct is not None:
                            expert = pct if b["side"] == "yes" \
                                else round(100 - pct, 1)
                            agrees = "yes" if (b["side"] == "yes"
                                               and was_pick) else "no"
                    else:
                        pct = sports_expert(ticker, b["side"], since)
                        if pct is not None:
                            expert = pct
                            agrees = "yes" if pct >= 50 else "no"
                    new_rows.append({
                        "seen_utc": stamp, "sector": sector,
                        "series": series, "ticker": ticker,
                        "event": m.get("event_ticker") or "",
                        "bet_on": market_label(sector, m),
                        "side": b["side"],
                        "contracts": b["contracts"],
                        "avg_price_cents": round(b["avg_price_cents"], 1),
                        "dollars": round(b["dollars"], 2),
                        "n_fills": b["n_fills"],
                        "first_trade_utc": iso(b["first"]),
                        "last_trade_utc": iso(b["last"]),
                        "close_time_utc": iso(close) if close else "",
                        "hours_before_close": hours_before,
                        "expert_pct": expert, "agrees": agrees})
                time.sleep(0.2)

    if series_ok == 0:
        # dead-feed law: a dead tape must never scroll away green
        print("!! WHALE WATCHER: every series fetch failed -- feed dead")
        raise SystemExit(1)
    if series_dead:
        print(f"note: {series_dead} series fetch(es) failed this pass; "
              f"{series_ok} succeeded")
    if new_rows:
        with appender(TRADES_CSV, TRADE_FIELDS) as w:
            for r in new_rows:
                w.writerow(r)
    print(f"scan: {len(new_rows)} new whale burst(s) flagged")
    return new_rows


# ---------------------------------------------------------------------
# THE BOARD. Full rewrite each run; shows the last BOARD_WINDOW_H hours
# plus the all-time scoreboard. All times render on the VIEWER'S clock
# (data-utc + JS), ages recompute live (data-built) -- the same honesty
# pattern as the swoop board.

def sector_scoreboard():
    board = defaultdict(lambda: [0, 0])
    if os.path.exists(RESULTS_CSV):
        with open(RESULTS_CSV) as f:
            for r in csv.DictReader(f):
                s = r.get("sector", "")
                if r.get("result") == "HIT":
                    board[s][0] += 1
                elif r.get("result") == "MISS":
                    board[s][1] += 1
    return board


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def build_page(rows_all):
    now = now_utc()
    cutoff = now - timedelta(hours=BOARD_WINDOW_H)
    recent = []
    for r in rows_all:
        seen = parse_time(r.get("first_trade_utc")) or \
            parse_time(r.get("seen_utc"))
        if seen and seen >= cutoff:
            r = dict(r)
            r["_when"] = seen
            recent.append(r)
    by_sector = defaultdict(list)
    for r in recent:
        by_sector[r.get("sector", "")].append(r)
    score = sector_scoreboard()
    built_ms = int(now.timestamp() * 1000)

    css = """
    body{background:#0b1220;color:#dbe4f0;font:15px/1.45 -apple-system,
      'Segoe UI',Roboto,sans-serif;margin:0;padding:14px 10px 40px}
    .wrap{max-width:760px;margin:0 auto}
    h1{font-size:22px;margin:4px 0 2px}
    .meta{color:#7d8aa0;font-size:12px;margin-bottom:10px}
    .law{background:#121b2e;border:1px solid #23324d;border-radius:10px;
      padding:8px 12px;font-size:12.5px;color:#9fb0c8;margin-bottom:14px}
    .sec{margin:18px 0 6px;font-size:16px;font-weight:700;
      letter-spacing:.4px;color:#e8eefc;border-bottom:1px solid #23324d;
      padding-bottom:4px}
    .sec .tally{float:right;font-size:12px;font-weight:400;color:#7d8aa0}
    .card{background:#121b2e;border:1px solid #23324d;border-radius:12px;
      padding:10px 12px;margin:8px 0}
    .row1{display:flex;justify-content:space-between;gap:8px;
      align-items:baseline;flex-wrap:wrap}
    .bet{font-weight:700;font-size:15.5px}
    .no .bet::after{content:" (bet AGAINST)";color:#f0a45c;
      font-weight:400;font-size:12px}
    .dollars{font-weight:800;font-size:17px;color:#7fd8a4;
      white-space:nowrap}
    .detail{color:#9fb0c8;font-size:12.5px;margin-top:3px}
    .expert{font-size:12.5px;margin-top:3px}
    .agree{color:#7fd8a4}.disagree{color:#f0a45c}
    .empty{color:#5d6a80;font-size:13px;padding:6px 2px 2px}
    .old{color:#ff8f8f}
    """

    parts = [f"<title>Whale Watcher</title><style>{css}</style>",
             '<div class="wrap">',
             "<h1>\U0001F40B Whale Watcher</h1>",
             f'<div class="meta"><span class="age" data-built="{built_ms}">'
             "just built</span> &middot; big executed bets on our "
             "hand-verified markets, last "
             f"{BOARD_WINDOW_H}h &middot; whale bar: "
             f"${WEATHER_THRESHOLD}+ weather, ${SPORTS_THRESHOLD}+ "
             "sports</div>",
             '<div class="law">Research only &mdash; this board places '
             "no bets and never touches the weather bot or the daily "
             "card. Kalshi does not reveal who traded; each line is a "
             "burst of filled orders, not a person. Every line is "
             "graded later by Kalshi's own settled result "
             "(HIT/MISS).</div>"]

    for sector, label, _series, _thr in SECTORS:
        h, ms = score.get(sector, [0, 0])
        tally = f"record {h}&ndash;{ms}" if (h or ms) else "no grades yet"
        parts.append(f'<div class="sec">{esc(label)}'
                     f'<span class="tally">{tally}</span></div>')
        rows = sorted(by_sector.get(sector, []),
                      key=lambda r: float(r.get("dollars") or 0),
                      reverse=True)
        if not rows:
            parts.append('<div class="empty">No whale-sized bets in '
                         f"the last {BOARD_WINDOW_H} hours.</div>")
            continue
        for r in rows:
            side = (r.get("side") or "yes").lower()
            when_ms = int(r["_when"].timestamp() * 1000)
            fills = int(float(r.get("n_fills") or 1))
            burst = "1 fill" if fills == 1 else f"{fills} fills"
            hrs = r.get("hours_before_close")
            early = f" &middot; {hrs}h before close" if hrs else ""
            try:
                price = f"{float(r.get('avg_price_cents')):.0f}&cent;"
            except (TypeError, ValueError):
                price = "?"
            expert_html = ""
            ep = r.get("expert_pct")
            if ep not in ("", None):
                who = ("our ensemble" if r.get("sector") == "WEATHER"
                       else "the sharps")
                cls = "agree" if r.get("agrees") == "yes" else "disagree"
                verdict = ("agrees with" if r.get("agrees") == "yes"
                           else "fights")
                expert_html = (f'<div class="expert {cls}">'
                               f"{verdict} {who} ({ep}% on this side)"
                               "</div>")
            parts.append(
                f'<div class="card {"no" if side == "no" else ""}">'
                '<div class="row1">'
                f'<span class="bet">{esc(r.get("bet_on", ""))}</span>'
                f'<span class="dollars">${float(r.get("dollars") or 0):,.0f}'
                "</span></div>"
                f'<div class="detail">{int(float(r.get("contracts") or 0)):,}'
                f" contracts @ {price} avg &middot; {burst} &middot; "
                f'<span data-utc="{when_ms}">&hellip;</span>{early}</div>'
                f"{expert_html}</div>")

    parts.append("""</div><script>
    function whaleTick(){
      var now=Date.now();
      document.querySelectorAll('[data-utc]').forEach(function(el){
        var d=new Date(+el.dataset.utc);
        el.textContent=d.toLocaleString([],{weekday:'short',hour:'numeric',
          minute:'2-digit'});});
      document.querySelectorAll('[data-built]').forEach(function(el){
        var m=Math.max(0,Math.floor((now-+el.dataset.built)/60000));
        el.textContent=m<1?'built just now':'built '+m+'m ago';
        el.classList.toggle('old',m>180);});
    }
    whaleTick();setInterval(whaleTick,30000);
    </script>""")
    with open(PAGE, "w") as f:
        f.write("\n".join(parts))
    print(f"board: wrote {PAGE} ({len(recent)} burst(s) shown)")


def main():
    grade_flags()
    scan()
    build_page(load_flags())


if __name__ == "__main__":
    main()
