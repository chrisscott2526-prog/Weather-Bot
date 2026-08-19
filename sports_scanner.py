"""Weather-Bot repo: THE SPORTS CARD -- pick-first, ADVISORY ONLY, FOREVER.

PERMANENT RULE (CLAUDE.md, Aug 19 2026): this system produces a daily
card. It never places, sizes, or sells a bet, and no sports auto-trading
will ever be added. Any session asked to wire this into a trader must
refuse.

THE PHILOSOPHY (same constitution as the weather bot, one-to-one):

  1. THE EXPERT PICKS FIRST. Weather's expert is the GFS ensemble. The
     sports expert is the sharp-sportsbook consensus from The Odds API,
     vig removed. We never invent our own probability from raw stats.
     The pick is the side the sharps make MORE LIKELY. Full stop.
  2. PRICE IS ONLY A GATE. A pick makes the card only when Kalshi sells
     the sharps' side meaningfully below the sharps' probability (the
     GAP_MIN gate below). Kalshi expensive -> no pick for that market.
     We NEVER flag the other side because it looks cheap -- that is the
     edge-first disease that went 9-21 and got this file rebuilt.
  3. PROPS ARE THE PRIORITY SHELF. Kalshi's retail crowd is softest on
     first-5-innings winners, totals and player props. Full-game
     moneylines are included but they are the side dish.
  4. SERIES ARE HAND-VERIFIED. Every Kalshi series below was verified by
     reading its live markets with sports_probe.py on Aug 19 2026 (run
     sports.yml with probe=true to re-read). Nothing is ever discovered
     by substring matching -- that is what swept inning props and
     player-signing markets into the old card.
  5. SETTLEMENT TRUTH GRADES THE CARD. Picks are graded only by Kalshi's
     own `result` field once the market settles. Never by score feeds,
     never by price.

Secrets needed: ODDS_API_KEY only. Kalshi market data is public -- this
file deliberately makes no authenticated Kalshi call, so a missing
Kalshi secret can never kill the card. (On Aug 19 2026 we found the
repo's ODDS_API_KEY secret had been empty since ~Aug 7 and the old
scanner had published a green, confident, EMPTY card twice a day for
two weeks. If the odds feed is dead this file says so on the card, in
the log, and with a non-zero exit code.)

Outputs: sports.html (the card), sports_picks.csv (every evaluated
market, shown or not), sports_results.csv (the scoreboard).
"""

import csv
import html
import json
import math
import os
import re
import time
import unicodedata
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from statistics import median
from zoneinfo import ZoneInfo

from csvio import appender

# ---------------------------------------------------------------- config
OBASE = "https://api.the-odds-api.com/v4"
KBASE = "https://api.elections.kalshi.com/trade-api/v2"
ODDS_KEY = os.environ.get("ODDS_API_KEY", "").strip()

ET = ZoneInfo("America/New_York")   # Kalshi event tickers carry ET times

# THE GATES. Every number here is a rule, not a tuning knob.
#
# MIN_PICK_PROB: the sharps must actually lean. A de-vigged 51% is a
# shrug, not an opinion -- carding it would be selling coin flips as
# picks. 55% is the weakest lean we call a pick (weather's analog is
# MIN_PICK_PROB=35 across 5+ brackets; a binary market needs a real
# margin over 50).
MIN_PICK_PROB = 55.0
# GAP_MIN: how much cheaper Kalshi must be than the sharps' probability,
# in cents, AFTER Kalshi's trading fee. Justification: the fee is 1-2c,
# a median-of-3+-books consensus still wobbles 1-2c, so anything under
# ~3c is noise. Real, durable retail mispricings on props run 3-8c.
# 4c net clears fee + noise with margin and is rare enough to keep the
# card short. (The old card showed 2c "edges" -- most were noise.)
GAP_MIN = 4.0
# GAP_MAX: a gap this big does not mean free money, it means bad data --
# a mismatched market, a stale quote, a scratched pitcher the books know
# about and the crowd doesn't. Same law as the trader's SANITY_GAP.
# Suppressed loudly, never shown.
GAP_MAX = 15.0
# MAX_COST: above 90c a win pays dimes and the fee eats half of it.
# Not fun, not worth a slip on the card.
MAX_COST = 90.0
# MIN_ASK_SIZE: contracts resting at the ask. Below this the "price" is
# a ghost quote you couldn't actually get filled at for a real dollar.
MIN_ASK_SIZE = 50
# MIN_BOOKS: a consensus of fewer than 3 sharp books is not a consensus.
MIN_BOOKS = 3
MAX_HOURS_OUT = 30          # only games starting inside this window
PROP_EVENT_CAP = 12         # per-event odds calls per sport per scan
                            # (props cost 1 credit per market per event;
                            #  this caps a scan at ~36 credits/sport)

PICKS_CSV = "sports_picks.csv"
RESULTS_CSV = "sports_results.csv"
PAGE = "sports.html"

PICKS_FIELDS = ["scanned_utc", "sport", "shelf", "game", "detail",
                "commence_utc", "series", "ticker", "side", "pick",
                "books_pct", "kalshi_cents", "fee_cents", "gap_cents",
                "n_books", "shown", "why"]
RESULTS_FIELDS = ["graded_utc", "sport", "shelf", "game", "detail",
                  "ticker", "side", "pick", "books_pct", "kalshi_cents",
                  "gap_cents", "market_result", "result", "pnl"]

# THE SHELVES. Each maps ONE hand-verified Kalshi series to ONE Odds API
# market key. kind decides the matching logic. Verified against live
# markets via sports_probe.py, Aug 19 2026 -- to add a shelf, run the
# probe, read the series' real markets and rules, then add it here BY
# EXACT TICKER. featured=True markets ride the cheap bulk /odds call
# (works on every Odds API plan); the rest need the per-event endpoint
# (paid plans -- the scanner finds out at runtime and says so).
SHELVES = [
    # -- the priority shelf: props ---------------------------------------
    dict(key="MLB_F5", sport="baseball_mlb", label="MLB · FIRST 5",
         kind="winner", series="KXMLBF5", odds_market="h2h_1st_5_innings",
         featured=False, has_tie=True),
    dict(key="MLB_F5_TOTAL", sport="baseball_mlb", label="MLB · F5 TOTAL",
         kind="total", series="KXMLBF5TOTAL",
         odds_market="totals_1st_5_innings", featured=False),
    dict(key="MLB_KS", sport="baseball_mlb", label="MLB · STRIKEOUTS",
         kind="pitcher_prop", series="KXMLBKS",
         odds_market="pitcher_strikeouts", featured=False),
    dict(key="MLB_TOTAL", sport="baseball_mlb", label="MLB · TOTAL RUNS",
         kind="total", series="KXMLBTOTAL", odds_market="totals",
         featured=True),
    dict(key="NFL_TOTAL", sport="americanfootball_nfl",
         label="NFL · TOTAL POINTS", kind="total", series="KXNFLTOTAL",
         odds_market="totals", featured=True),
    # -- the side dish: full-game moneylines -----------------------------
    dict(key="MLB_GAME", sport="baseball_mlb", label="MLB · MONEYLINE",
         kind="winner", series="KXMLBGAME", odds_market="h2h",
         featured=True, has_tie=False),
    dict(key="NFL_GAME", sport="americanfootball_nfl",
         label="NFL · MONEYLINE", kind="winner", series="KXNFLGAME",
         odds_market="h2h", featured=True, has_tie=False),
    # NOT included on purpose (verified but not comparable yet):
    #  KXMLBF7 -- books don't quote a first-7-innings line.
    #  KXNFL1H/KXNFL1HTOTAL -- tie handling in Kalshi's 1H rules not yet
    #    hand-read; add only after reading rules_primary via the probe.
    #  KXMLBHIT/KXMLBHR/KXMLBHRR/KXMLBHA -- batter props; add after the
    #    Odds API plan is confirmed to carry batter markets.
]

# Kalshi's team codes as they appear INSIDE event tickers, keyed by the
# Odds API's full team name. Matching is EXACT: an event ticker must end
# with AWAYCODE+HOMECODE and the market ticker with -CODE. A wrong or
# missing code can only ever cause a loud SKIP, never a wrong match.
# Codes marked (v) were verified against live tickers Aug 19 2026; the
# rest are Kalshi's standard abbreviations -- if one never matches, the
# UNMATCHED log line is the tell, fix it there.
MLB_CODES = {
    "Arizona Diamondbacks": "AZ",      # (v)
    "Athletics": "ATH",                # (v)
    "Oakland Athletics": "ATH",        # Odds API legacy name
    "Atlanta Braves": "ATL",
    "Baltimore Orioles": "BAL",
    "Boston Red Sox": "BOS",
    "Chicago Cubs": "CHC",             # (v)
    "Chicago White Sox": "CWS",        # (v)
    "Cincinnati Reds": "CIN",          # (v)
    "Cleveland Guardians": "CLE",
    "Colorado Rockies": "COL",
    "Detroit Tigers": "DET",
    "Houston Astros": "HOU",
    "Kansas City Royals": "KC",        # (v)
    "Los Angeles Angels": "LAA",
    "Los Angeles Dodgers": "LAD",      # (v)
    "Miami Marlins": "MIA",
    "Milwaukee Brewers": "MIL",
    "Minnesota Twins": "MIN",
    "New York Mets": "NYM",
    "New York Yankees": "NYY",         # (v)
    "Philadelphia Phillies": "PHI",
    "Pittsburgh Pirates": "PIT",       # (v)
    "San Diego Padres": "SD",          # (v)
    "San Francisco Giants": "SF",
    "Seattle Mariners": "SEA",         # (v)
    "St. Louis Cardinals": "STL",
    "Tampa Bay Rays": "TB",
    "Texas Rangers": "TEX",
    "Toronto Blue Jays": "TOR",        # (v)
    "Washington Nationals": "WSH",
}
# NFL codes all verified against the live KXNFLWINS-* series list.
NFL_CODES = {
    "Arizona Cardinals": "ARI", "Atlanta Falcons": "ATL",
    "Baltimore Ravens": "BAL", "Buffalo Bills": "BUF",
    "Carolina Panthers": "CAR", "Chicago Bears": "CHI",
    "Cincinnati Bengals": "CIN", "Cleveland Browns": "CLE",
    "Dallas Cowboys": "DAL", "Denver Broncos": "DEN",
    "Detroit Lions": "DET", "Green Bay Packers": "GB",
    "Houston Texans": "HOU", "Indianapolis Colts": "IND",
    "Jacksonville Jaguars": "JAC", "Kansas City Chiefs": "KC",
    "Las Vegas Raiders": "LV", "Los Angeles Chargers": "LAC",
    "Los Angeles Rams": "LA", "Miami Dolphins": "MIA",
    "Minnesota Vikings": "MIN", "New England Patriots": "NE",
    "New Orleans Saints": "NO", "New York Giants": "NYG",
    "New York Jets": "NYJ", "Philadelphia Eagles": "PHI",
    "Pittsburgh Steelers": "PIT", "San Francisco 49ers": "SF",
    "Seattle Seahawks": "SEA", "Tampa Bay Buccaneers": "TB",
    "Tennessee Titans": "TEN", "Washington Commanders": "WAS",
}
TEAM_CODES = {"baseball_mlb": MLB_CODES, "americanfootball_nfl": NFL_CODES}


# ------------------------------------------------------------- fetchers
def oget(path, label):
    """Odds API GET -> (json, err). Prints remaining quota when present."""
    req = urllib.request.Request(OBASE + path,
                                 headers={"User-Agent": "weather-bot-card"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            left = r.headers.get("x-requests-remaining")
            if left is not None:
                print(f"  [{label}] odds-api credits remaining: {left}")
            return json.load(r), None
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", "replace")[:200]
        except Exception:
            body = ""
        return None, f"HTTP {e.code} {body}"
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def kget(path, label, tries=4):
    """Public (unauthenticated) Kalshi GET with 429 backoff."""
    req = urllib.request.Request(KBASE + path,
                                 headers={"User-Agent": "weather-bot-card"})
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


def dollars_to_cents(m, field):
    try:
        c = float(m.get(field)) * 100
        return c if c > 0 else None
    except (TypeError, ValueError):
        return None


def fee_cents(price_cents):
    """Kalshi taker fee per contract: ceil(7% * p * (1-p)), in cents."""
    p = price_cents / 100.0
    return math.ceil(7 * p * (1 - p))


def norm(name):
    """Normalize a person/team name for exact comparison across feeds."""
    s = unicodedata.normalize("NFKD", name or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


def iso(ts):
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


# ------------------------------------------------- sharps consensus side
def devig_pair(over_probs, under_probs):
    """Median implied prob per side across books, then normalize the pair."""
    if not over_probs or not under_probs:
        return None
    po, pu = median(over_probs), median(under_probs)
    tot = po + pu
    return (po / tot, pu / tot) if tot > 0 else None


def consensus_h2h(ev, market_key):
    """De-vigged win probs for one event's h2h-style market.
    Returns ({outcome_name: prob}, n_books) or (None, 0). Handles 2-way
    and 3-way (Draw) books identically: all quoted outcomes normalized."""
    per_book = []
    for bk in ev.get("bookmakers", []):
        for mkt in bk.get("markets", []):
            if mkt.get("key") != market_key:
                continue
            probs = {}
            ok = True
            for oc in mkt.get("outcomes", []):
                try:
                    price = float(oc["price"])
                except (KeyError, TypeError, ValueError):
                    ok = False
                    break
                if price <= 1:
                    ok = False
                    break
                probs[oc["name"]] = 1 / price
            if ok and len(probs) >= 2:
                per_book.append(probs)
    if len(per_book) < MIN_BOOKS:
        return None, len(per_book)
    names = set(per_book[0])
    if any(set(b) != names for b in per_book):
        # books disagree on the outcome set (2-way vs 3-way) -- use only
        # the majority shape rather than mixing incomparable prices
        shapes = defaultdict(list)
        for b in per_book:
            shapes[frozenset(b)].append(b)
        per_book = max(shapes.values(), key=len)
        names = set(per_book[0])
        if len(per_book) < MIN_BOOKS:
            return None, len(per_book)
    med = {n: median(b[n] for b in per_book) for n in names}
    tot = sum(med.values())
    return {n: p / tot for n, p in med.items()}, len(per_book)


def consensus_lines(ev, market_key):
    """De-vigged over/under probs per (participant, point).
    Returns {(norm_name_or_'', point): (p_over, p_under, n_books)}."""
    raw = defaultdict(lambda: ([], []))       # key -> (over probs, under probs)
    for bk in ev.get("bookmakers", []):
        for mkt in bk.get("markets", []):
            if mkt.get("key") != market_key:
                continue
            sides = defaultdict(dict)
            for oc in mkt.get("outcomes", []):
                try:
                    price = float(oc["price"])
                    point = float(oc["point"])
                except (KeyError, TypeError, ValueError):
                    continue
                if price <= 1:
                    continue
                who = norm(oc.get("description", ""))
                sides[(who, point)][oc.get("name", "").lower()] = 1 / price
            for k, s in sides.items():
                if "over" in s and "under" in s:
                    raw[k][0].append(s["over"])
                    raw[k][1].append(s["under"])
    out = {}
    for k, (ov, un) in raw.items():
        n = min(len(ov), len(un))
        if n < MIN_BOOKS:
            continue
        pair = devig_pair(ov, un)
        if pair:
            out[k] = (pair[0], pair[1], n)
    return out


def fetch_sharp_games(sport, featured_keys):
    """Bulk /odds call: every upcoming game with featured-market consensus."""
    markets = ",".join(featured_keys)
    data, err = oget(f"/sports/{sport}/odds?regions=us&markets={markets}"
                     f"&oddsFormat=decimal&apiKey={ODDS_KEY}",
                     f"{sport} featured")
    if err:
        print(f"!! {sport}: featured odds fetch FAILED ({err})")
        return None
    now = datetime.now(timezone.utc)
    games = []
    for ev in data:
        start = iso(ev.get("commence_time", ""))
        home, away = ev.get("home_team"), ev.get("away_team")
        if (not start or not home or not away
                or start < now or start > now + timedelta(hours=MAX_HOURS_OUT)):
            continue
        games.append({"id": ev.get("id"), "sport": sport, "home": home,
                      "away": away, "game": f"{away} @ {home}",
                      "commence": start, "raw": ev})
    return games


def fetch_event_props(sport, game, market_keys, dead_keys):
    """Per-event odds for prop markets. Mutates dead_keys on plan errors."""
    keys = [k for k in market_keys if k not in dead_keys]
    if not keys:
        return None
    data, err = oget(f"/sports/{sport}/events/{game['id']}/odds"
                     f"?regions=us&markets={','.join(keys)}"
                     f"&oddsFormat=decimal&apiKey={ODDS_KEY}",
                     f"{sport} props")
    if data is not None:
        return data
    if err and ("HTTP 401" in err or "HTTP 422" in err):
        # The plan doesn't carry these markets. Say so once, loudly, and
        # stop burning credits on them this run.
        print(f"!! {sport}: per-event markets {keys} REJECTED by the Odds "
              f"API ({err}). These shelves are OFF until the plan carries "
              f"them -- run the probe after upgrading the key.")
        dead_keys.update(keys)
    else:
        print(f"!! {sport} {game['game']}: prop fetch failed ({err})")
    return None


# --------------------------------------------------------- kalshi side
EVENT_RE = re.compile(r"^(\d{2})([A-Z]{3})(\d{2})(\d{4})([A-Z0-9]+)$")
MONTHS = {m: i + 1 for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
     "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"])}


def parse_event_ticker(event_ticker, series):
    """KXMLBF5-26AUG191940ATHKC -> (start datetime ET, 'ATHKC') or None."""
    if not event_ticker.startswith(series + "-"):
        return None
    m = EVENT_RE.match(event_ticker[len(series) + 1:])
    if not m:
        return None
    yy, mon, dd, hhmm, teams = m.groups()
    if mon not in MONTHS:
        return None
    try:
        start = datetime(2000 + int(yy), MONTHS[mon], int(dd),
                         int(hhmm[:2]), int(hhmm[2:]), tzinfo=ET)
    except ValueError:
        return None
    return start, teams


def fetch_kalshi_series(series):
    """All open markets of one hand-verified series, grouped by event."""
    events = defaultdict(list)
    cursor = ""
    for _ in range(6):                      # 6 pages x 200 = plenty
        path = f"/markets?series_ticker={series}&status=open&limit=200"
        if cursor:
            path += f"&cursor={cursor}"
        data, err = kget(path, series)
        if err:
            print(f"!! {series}: kalshi fetch failed ({err})")
            return None
        for m in data.get("markets", []):
            events[m.get("event_ticker", "")].append(m)
        cursor = data.get("cursor") or ""
        if not cursor:
            break
        time.sleep(0.4)
    return events


def match_event(kalshi_events, series, sport, game):
    """The matcher. An event matches ONLY if its ticker parses cleanly,
    its team block equals AWAYCODE+HOMECODE exactly, and its start time
    agrees with the books' start to within 30 minutes (doubleheader
    safety). Anything less is a SKIP, never a guess."""
    codes = TEAM_CODES.get(sport, {})
    ac, hc = codes.get(game["away"]), codes.get(game["home"])
    if not ac or not hc:
        print(f"  UNMATCHED (no team code): {game['game']}")
        return None, None
    want = ac + hc
    best = None
    for et, mkts in kalshi_events.items():
        parsed = parse_event_ticker(et, series)
        if not parsed:
            continue
        start_et, teams = parsed
        if teams != want:
            continue
        drift = abs((start_et - game["commence"]).total_seconds())
        if drift <= 1800 and (best is None or drift < best[0]):
            best = (drift, et, mkts)
    if not best:
        return None, None
    return best[1], best[2]


# ---------------------------------------------------------- the shelves
def liquid_ask(m, side):
    """(price_cents, fee) for buying `side` of market m, or None if the
    quote is missing, oversized, or a ghost."""
    price = dollars_to_cents(m, f"{side}_ask_dollars")
    if price is None or price > MAX_COST:
        return None
    # size resting at that ask: buying NO fills against the YES bid,
    # so the NO ask's size is yes_bid_size_fp (verified in the probe's
    # raw dump: yes_bid 0.27 <-> no_ask 0.73 on the same market)
    size_field = "yes_ask_size_fp" if side == "yes" else "yes_bid_size_fp"
    try:
        size = float(m.get(size_field) or 0)
    except (TypeError, ValueError):
        size = 0
    if size < MIN_ASK_SIZE:
        return None
    return price, fee_cents(price)


def evaluate(shelf, game, fair_pct, n_books, market, side, pick_text,
             detail, rows):
    """Apply the gates to one (pick, market) pair and log the row."""
    quote = liquid_ask(market, side)
    if quote is None:
        return None
    price, fee = quote
    gap = round(fair_pct - price - fee, 1)
    suppressed = gap > GAP_MAX
    shown = (GAP_MIN <= gap <= GAP_MAX)
    if suppressed:
        why = (f"SUPPRESSED: the sharps say {fair_pct:.0f}% but Kalshi "
               f"charges {price:.0f}c -- a {gap:+.1f}c gap is too good to "
               f"be true and usually means bad data (scratch, mismatch, "
               f"stale quote). Not a play.")
        print(f"  !! SUPPRESSED {market.get('ticker', '')}: gap {gap:+.1f}c "
              f"> {GAP_MAX}c")
    elif shown:
        why = (f"{n_books} sharp books make this {fair_pct:.0f}% likely; "
               f"Kalshi sells it for {price:.0f}c. After the {fee:.0f}c fee "
               f"you're getting the sharps' opinion at a {gap:.0f}c "
               f"discount.")
    elif gap >= 0:
        why = (f"Sharps {fair_pct:.0f}%, Kalshi {price:.0f}c, fee "
               f"{fee:.0f}c: only {gap:+.1f}c of daylight -- not enough to "
               f"card (needs {GAP_MIN:.0f}c+).")
    else:
        why = (f"Sharps {fair_pct:.0f}%, Kalshi {price:.0f}c + {fee:.0f}c "
               f"fee: the crowd already charges more than the sharps' "
               f"number. No pick.")
    row = {"scanned_utc": SCAN_STAMP, "sport": shelf["label"].split(" ·")[0],
           "shelf": shelf["key"], "game": game["game"], "detail": detail,
           "commence_utc": game["commence"].isoformat(),
           "series": shelf["series"], "ticker": market.get("ticker", ""),
           "side": side.upper(), "pick": pick_text,
           "books_pct": round(fair_pct, 1), "kalshi_cents": round(price, 1),
           "fee_cents": fee, "gap_cents": gap, "n_books": n_books,
           "shown": "1" if shown else "0", "why": why}
    rows.append(row)
    return row if shown else None


def scan_winner(shelf, game, kalshi_events, rows):
    fair, n = consensus_h2h(game["raw"], shelf["odds_market"])
    if not fair:
        return
    et, mkts = match_event(kalshi_events, shelf["series"],
                           shelf["sport"], game)
    if not mkts:
        print(f"  UNMATCHED {shelf['key']}: {game['game']}")
        return
    has_tie = any(m.get("ticker", "").endswith("-TIE") for m in mkts)
    draw_key = next((k for k in fair if norm(k) in ("draw", "tie")), None)
    if has_tie and not draw_key:
        # Books priced this 2-way (tie = push); Kalshi settles a tie as a
        # LOSS for both team markets. Those probabilities are not the
        # same thing -- comparing them would invent data. Skip loudly.
        print(f"  SKIP {shelf['key']} {game['game']}: Kalshi has a TIE "
              f"market but the books quote 2-way (tie=push) -- "
              f"incomparable")
        return
    codes = TEAM_CODES[shelf["sport"]]
    teams = {t: p for t, p in fair.items() if t != draw_key}
    pick_team = max(teams, key=teams.get)
    fair_pct = fair[pick_team] * 100
    if fair_pct < MIN_PICK_PROB:
        return                      # coin flip -- the sharps have no pick
    suffix = "-" + codes.get(pick_team, "???")
    market = next((m for m in mkts
                   if m.get("ticker", "").endswith(suffix)), None)
    if market is None:
        print(f"  UNMATCHED {shelf['key']}: no {suffix} market in {et}")
        return
    what = ("wins the first 5 innings" if shelf["key"] == "MLB_F5"
            else "wins")
    evaluate(shelf, game, fair_pct, n, market, "yes",
             f"{pick_team} {what}", "", rows)


def scan_total(shelf, game, kalshi_events, rows):
    lines = consensus_lines(game["raw"], shelf["odds_market"])
    lines = {k: v for k, v in lines.items() if k[0] == ""}   # game totals
    if not lines:
        return
    et, mkts = match_event(kalshi_events, shelf["series"],
                           shelf["sport"], game)
    if not mkts:
        return
    unit = "runs" if shelf["sport"] == "baseball_mlb" else "points"
    span = ("in the first 5 innings" if shelf["key"] == "MLB_F5_TOTAL"
            else "in the game")
    for m in mkts:
        strike = m.get("floor_strike")
        if strike is None or float(strike) != float(strike) // 1 + 0.5:
            continue    # only half-point strikes: books can push on
                        # integer lines, Kalshi can't -- incomparable
        hit = lines.get(("", float(strike)))
        if not hit:
            continue    # books don't quote this exact line
        p_over, p_under, n = hit
        if p_over >= p_under:
            side, fair_pct = "yes", p_over * 100
            pick = f"Over {strike} {unit} {span}"
        else:
            side, fair_pct = "no", p_under * 100
            pick = f"Under {strike} {unit} {span}"
        if fair_pct < MIN_PICK_PROB:
            continue
        evaluate(shelf, game, fair_pct, n, m, side, pick,
                 f"line {strike}", rows)


def scan_pitcher_prop(shelf, game, kalshi_events, rows):
    lines = consensus_lines(game["raw"], shelf["odds_market"])
    lines = {k: v for k, v in lines.items() if k[0]}         # per player
    if not lines:
        return
    et, mkts = match_event(kalshi_events, shelf["series"],
                           shelf["sport"], game)
    if not mkts:
        return
    for m in mkts:
        strike = m.get("floor_strike")
        sub = m.get("yes_sub_title") or ""       # "Seth Lugo: 9+"
        player = norm(sub.split(":")[0]) if ":" in sub else ""
        if strike is None or not player:
            continue
        if float(strike) != float(strike) // 1 + 0.5:
            continue
        hit = lines.get((player, float(strike)))
        if not hit:
            continue
        p_over, p_under, n = hit
        name = sub.split(":")[0].strip()
        need = int(float(strike) + 0.5)
        if p_over >= p_under:
            side, fair_pct = "yes", p_over * 100
            pick = f"{name} strikes out {need}+"
        else:
            side, fair_pct = "no", p_under * 100
            pick = f"{name} stays under {need} strikeouts"
        if fair_pct < MIN_PICK_PROB:
            continue
        evaluate(shelf, game, fair_pct, n, m, side, pick,
                 f"{name} K line {strike}", rows)


# ------------------------------------------------------------- grading
def grade():
    """Grade shown picks against Kalshi's own settlement. Nothing else
    counts. Returns newly graded rows."""
    if not os.path.exists(PICKS_CSV):
        return []
    already = set()
    if os.path.exists(RESULTS_CSV):
        with open(RESULTS_CSV) as f:
            for r in csv.DictReader(f):
                already.add((r["ticker"], r["side"]))
    pending = {}
    with open(PICKS_CSV) as f:
        for r in csv.DictReader(f):
            if r.get("shown") != "1":
                continue
            k = (r["ticker"], r["side"])
            if k in already:
                continue
            st = iso(r.get("commence_utc", ""))
            if st and st < datetime.now(timezone.utc) - timedelta(hours=2):
                pending[k] = r                    # latest scan wins
    graded = []
    for (ticker, side), r in list(pending.items())[:40]:
        data, err = kget(f"/markets/{ticker}", ticker)
        if err:
            print(f"  grade {ticker}: {err}")
            continue
        m = data.get("market", {})
        status = (m.get("status") or "").lower()
        result = (m.get("result") or "").lower()
        if status not in ("settled", "finalized"):
            continue                              # next run
        if result in ("yes", "no"):
            won = (result == side.lower())
            cost = float(r["kalshi_cents"])
            fee = float(r["fee_cents"])
            pnl = round(((100 - cost - fee) if won else -(cost + fee)) / 100,
                        2)
            verdict = "WIN" if won else "LOSS"
        else:
            # scratched pitcher / cancelled game: Kalshi resolves to a
            # fair price, not yes/no. Record it, count it as a push.
            pnl, verdict = 0.0, "VOID"
        graded.append({"graded_utc": datetime.now(timezone.utc)
                       .isoformat(timespec="seconds"),
                       "sport": r["sport"], "shelf": r["shelf"],
                       "game": r["game"], "detail": r["detail"],
                       "ticker": ticker, "side": side, "pick": r["pick"],
                       "books_pct": r["books_pct"],
                       "kalshi_cents": r["kalshi_cents"],
                       "gap_cents": r["gap_cents"],
                       "market_result": result.upper() or status.upper(),
                       "result": verdict, "pnl": pnl})
        print(f"  graded {ticker} {side}: {verdict} ({pnl:+.2f})")
        time.sleep(0.3)
    if graded:
        with appender(RESULTS_CSV, RESULTS_FIELDS) as w:
            for g in graded:
                w.writerow(g)
    return graded


# ------------------------------------------------------------- the card
CSS = """
*{margin:0;padding:0;box-sizing:border-box}
:root{--felt:#14532d;--felt2:#0e3d21;--paper:#fbf8f1;--ink:#1d2733;
--dim:#6b7280;--gold:#b8860b;--red:#b3392f;--line:#d8d2c4}
body{background:#e9e4d8;color:var(--ink);
font:16px/1.5 "Inter",-apple-system,system-ui,sans-serif}
.wrap{max-width:680px;margin:0 auto;padding:0 14px 60px}
header{background:linear-gradient(180deg,var(--felt),var(--felt2));
color:#f3efe4;padding:26px 18px 20px;border-bottom:6px double var(--gold)}
header .inner{max-width:680px;margin:0 auto}
h1{font:700 34px/1 "Barlow Condensed",Impact,sans-serif;
letter-spacing:.04em;text-transform:uppercase}
h1 span{color:#e8c766}
.rec{display:flex;gap:22px;margin-top:12px;font-size:14px}
.rec b{font:600 22px/1 "Barlow Condensed",sans-serif;display:block}
.upd{margin-top:8px;font-size:12px;opacity:.75}
.dead{background:var(--red);color:#fff;padding:12px 16px;border-radius:6px;
margin:18px 0 0;font-size:14px;font-weight:600}
h2{font:600 15px/1 "Barlow Condensed",sans-serif;letter-spacing:.18em;
text-transform:uppercase;color:var(--dim);margin:28px 2px 12px}
.slip{background:var(--paper);border:1px solid var(--line);border-radius:6px;
margin-bottom:16px;position:relative;overflow:hidden;
box-shadow:0 1px 3px rgba(29,39,51,.12)}
.slip::before{content:"";position:absolute;top:0;bottom:0;left:52px;
border-left:2px dashed var(--line)}
.punch{position:absolute;left:18px;top:50%;width:16px;height:16px;
transform:translateY(-50%);border-radius:50%;background:#e9e4d8;
border:1px solid var(--line)}
.slipbody{padding:16px 16px 14px 72px}
.tag{display:inline-block;font:600 12px/1 "Barlow Condensed",sans-serif;
letter-spacing:.14em;background:var(--ink);color:#fff;
padding:4px 8px;border-radius:3px;margin-right:8px}
.when{font-size:12px;color:var(--dim)}
.match{font:600 21px/1.25 "Barlow Condensed",sans-serif;margin:8px 0 2px}
.pick{font-size:15px;margin:6px 0}
.pick b{color:var(--felt)}
.nums{display:flex;flex-wrap:wrap;gap:14px;font-size:13px;color:var(--dim);
margin:8px 0 10px;font-variant-numeric:tabular-nums}
.nums b{color:var(--ink)}
.why{font-size:14px;border-top:1px solid var(--line);padding-top:10px}
.stamp{position:absolute;right:12px;top:12px;
font:700 15px/1 "Barlow Condensed",sans-serif;letter-spacing:.1em;
border:2.5px solid;border-radius:4px;padding:6px 9px;
transform:rotate(6deg);text-transform:uppercase}
.stamp.gap{color:var(--felt);border-color:var(--felt)}
.stamp.top{color:var(--gold);border-color:var(--gold)}
.empty{background:var(--paper);border:1px dashed var(--line);border-radius:6px;
padding:26px 20px;text-align:center;color:var(--dim);font-size:15px}
.empty b{color:var(--ink)}
table{width:100%;border-collapse:collapse;background:var(--paper);
border:1px solid var(--line);border-radius:6px;overflow:hidden;font-size:13px}
th,td{padding:8px 10px;text-align:left;border-bottom:1px solid var(--line)}
th{font:600 12px/1 "Barlow Condensed",sans-serif;letter-spacing:.12em;
text-transform:uppercase;color:var(--dim)}
tr:last-child td{border-bottom:none}
.W{color:var(--felt);font-weight:600}.L{color:var(--red);font-weight:600}
.V{color:var(--dim);font-weight:600}
.foot{margin-top:26px;font-size:12.5px;color:var(--dim);line-height:1.6}
@media (prefers-reduced-motion:no-preference){
.slip{transition:transform .12s}.slip:hover{transform:translateY(-2px)}}
"""


def side_words(p):
    if p["side"] == "YES":
        return f"tap <b>Yes</b> at <b>{float(p['kalshi_cents']):.0f}¢</b>"
    return (f"tap <b>No</b> at <b>{float(p['kalshi_cents']):.0f}¢</b> "
            f"(that IS the sharps' side of this market)")


def build_page(shown, results, feed_dead):
    now = datetime.now(timezone.utc).strftime("%a %b %d, %H:%M UTC")
    wins = sum(1 for r in results if r["result"] == "WIN")
    losses = sum(1 for r in results if r["result"] == "LOSS")
    pnl = sum(float(r["pnl"]) for r in results)
    dead = ""
    if feed_dead:
        dead = ("<div class='dead'>THE ODDS FEED IS DOWN, so today's card "
                "is empty -- no picks can exist without the sharps. "
                "(Fix: re-add the ODDS_API_KEY secret in GitHub → Settings "
                "→ Secrets → Actions.) The scoreboard below is still "
                "real.</div>")
    slips = ""
    for i, p in enumerate(shown):
        gap = float(p["gap_cents"])
        stamp = "top" if i == 0 and len(shown) > 1 else "gap"
        label = "TOP PICK" if stamp == "top" else f"+{gap:.0f}¢ GAP"
        start = iso(p["commence_utc"])
        when = start.strftime("%a %H:%M UTC") if start else ""
        slips += f"""
<div class="slip"><div class="punch"></div>
<div class="stamp {stamp}">{label}</div>
<div class="slipbody">
<span class="tag">{html.escape(p['shelf'].replace('_', ' '))}</span><span class="when">{when}</span>
<div class="match">{html.escape(p['game'])}</div>
<div class="pick">The sharps' pick: <b>{html.escape(p['pick'])}</b>.
On Kalshi ({html.escape(p['ticker'])}), {side_words(p)}.</div>
<div class="nums"><span>Sharps say <b>{float(p['books_pct']):.0f}%</b></span>
<span>Kalshi charges <b>{float(p['kalshi_cents']):.0f}¢</b></span>
<span>Fee <b>{float(p['fee_cents']):.0f}¢</b></span>
<span>Gap <b>+{gap:.1f}¢</b></span>
<span>{html.escape(str(p['n_books']))} books</span></div>
<div class="why">{html.escape(p['why'])}</div>
</div></div>"""
    if not slips and not feed_dead:
        slips = ("<div class='empty'><b>No picks today.</b><br>"
                 "Everywhere the sharps lean, Kalshi's crowd already "
                 "charges full price. That's the normal result -- the gap "
                 "this card waits for is rare on purpose. When there's "
                 "nothing mispriced, the best bet is no bet.</div>")
    rows = ""
    for r in list(reversed(results))[:20]:
        rows += (f"<tr><td>{html.escape(r['shelf'].replace('_', ' '))}</td>"
                 f"<td>{html.escape(r['pick'])}</td>"
                 f"<td class='{r['result'][0]}'>{r['result']}</td>"
                 f"<td>{'+' if float(r['pnl']) >= 0 else ''}"
                 f"{float(r['pnl']):.2f}</td></tr>")
    hist = (f"<h2>The card's record (graded by Kalshi settlement)</h2>"
            f"<table><tr><th>Shelf</th><th>Pick</th><th>Result</th>"
            f"<th>P&L $</th></tr>{rows}</table>") if rows else (
            "<h2>The card's record</h2><div class='empty'>Fresh scoreboard "
            "-- the pick-first card started Aug 19, 2026 and grades itself "
            "from day one. Every shown pick lands here as a WIN or LOSS at "
            "$1 a slip, settled by Kalshi itself. Give it a few weeks "
            "before trusting it with real beer money.</div>")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>The Daily Card - Sharps vs. Kalshi</title>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=Inter:wght@400;600&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body>
<header><div class="inner">
<h1>The Daily <span>Card</span></h1>
<div class="rec"><div><b>{wins}-{losses}</b>record</div>
<div><b>{'+' if pnl >= 0 else ''}{pnl:.2f}</b>P&L ($1 slips)</div>
<div><b>{len(shown)}</b>picks today</div></div>
<div class="upd">Scanned {now}. This card is advice between friends, not a
robot with your wallet -- it never bets. You do (or don't).</div>
{dead}
</div></header>
<div class="wrap">
<h2>Today's picks, biggest gap first</h2>
{slips}
{hist}
<div class="foot"><b>How this card works, in one breath:</b> the sharpest
sportsbooks in the world publish their opinion as prices; we strip out
their commission to get an honest probability, then check what Kalshi's
crowd charges for the same thing. When the crowd sells the sharps' pick
at least {GAP_MIN:.0f}¢ under the sharps' own number (after Kalshi's
fee), it makes the card. We never pick against the sharps, never chase
a "cheap" longshot, and anything over +{GAP_MAX:.0f}¢ is treated as bad
data and suppressed. Props (first-5-innings, totals, strikeouts) are the
main event -- moneylines tag along. Sharps must lean at least
{MIN_PICK_PROB:.0f}% -- coin flips don't get picks. Every market we
evaluate is logged to sports_picks.csv, shown or not, and every shown
pick is graded by Kalshi's own settlement in sports_results.csv. The
record above is the only reason to trust (or ignore) this card.</div>
</div></body></html>"""


# ----------------------------------------------------------------- main
SCAN_STAMP = datetime.now(timezone.utc).isoformat(timespec="seconds")


def main():
    feed_dead = False
    rows = []                       # every evaluated row this scan
    if not ODDS_KEY:
        print("!! ODDS_API_KEY is EMPTY. No sharps, no card. "
              "Re-add the secret in GitHub → Settings → Secrets → Actions.")
        feed_dead = True

    shelves_by_sport = defaultdict(list)
    for s in SHELVES:
        shelves_by_sport[s["sport"]].append(s)

    sports_ok = 0
    if not feed_dead:
        for sport, shelves in shelves_by_sport.items():
            featured = sorted({s["odds_market"] for s in shelves
                               if s["featured"]})
            prop_keys = sorted({s["odds_market"] for s in shelves
                                if not s["featured"]})
            games = fetch_sharp_games(sport, featured)
            if games is None:
                continue            # printed loudly inside; featured
                                    # markets work on every plan, so a
                                    # failure here is key/feed trouble
            sports_ok += 1
            print(f"{sport}: {len(games)} upcoming games from the books")
            kalshi = {}
            for s in shelves:
                ev = fetch_kalshi_series(s["series"])
                if ev is not None:
                    kalshi[s["key"]] = ev
                    print(f"  kalshi {s['series']}: {len(ev)} open events")
                time.sleep(0.4)
            dead_keys = set()
            games.sort(key=lambda g: g["commence"])
            for gi, game in enumerate(games):
                if prop_keys and gi < PROP_EVENT_CAP:
                    props = fetch_event_props(sport, game, prop_keys,
                                              dead_keys)
                    if props:
                        # merge prop bookmakers into the featured payload
                        game["raw"].setdefault("bookmakers", [])
                        have = {b.get("key") for b in game["raw"]["bookmakers"]}
                        for bk in props.get("bookmakers", []):
                            if bk.get("key") in have:
                                for b in game["raw"]["bookmakers"]:
                                    if b.get("key") == bk.get("key"):
                                        b.setdefault("markets", []).extend(
                                            bk.get("markets", []))
                            else:
                                game["raw"]["bookmakers"].append(bk)
                    time.sleep(0.2)
                for s in shelves:
                    if s["key"] not in kalshi:
                        continue
                    if not s["featured"] and s["odds_market"] in dead_keys:
                        continue
                    scanner = {"winner": scan_winner, "total": scan_total,
                               "pitcher_prop": scan_pitcher_prop}[s["kind"]]
                    scanner(s, game, kalshi[s["key"]], rows)

    if not feed_dead and sports_ok == 0:
        feed_dead = True            # every league's fetch failed: the
                                    # key is dead or the feed is down

    shown = sorted([r for r in rows if r["shown"] == "1"],
                   key=lambda r: -float(r["gap_cents"]))
    if rows:
        with appender(PICKS_CSV, PICKS_FIELDS) as w:
            for r in rows:
                w.writerow(r)
    print(f"evaluated {len(rows)} sharp-vs-Kalshi pairs, "
          f"{len(shown)} make the card")

    graded = grade()
    print(f"graded {len(graded)} settled picks")
    results = list(csv.DictReader(open(RESULTS_CSV))) \
        if os.path.exists(RESULTS_CSV) else []

    with open(PAGE, "w") as f:
        f.write(build_page(shown, results, feed_dead))
    print(f"wrote {PAGE}")

    if feed_dead:
        raise SystemExit(3)        # red run = someone looks. The card and
                                   # scoreboard were still written first.


if __name__ == "__main__":
    main()
