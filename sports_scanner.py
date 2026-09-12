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
market, shown or not), sports_results.csv (the scoreboard),
parlay_picks.csv (the parlay board's suggested combos, owner request
Sep 8 2026) and parlay_results.csv (the parlay scoreboard), plus
combo_picks.csv / combo_results.csv (THE COMBO BOARD, owner request
Sep 10 2026: cross-sector stacks -- sports favorites + weather picks
-- for the highest honest payout; see its section below).
"""

import ast
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
from datetime import date as date_cls
from datetime import datetime, timedelta, timezone
from statistics import median
from zoneinfo import ZoneInfo

from cities import CITY_TO_STATION, TIMEZONES
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
# CREDIT_RESERVE: the Odds API plan verified Aug 19 2026 is the FREE
# tier -- 500 credits/month. Featured markets cost ~2/sport/scan (~250/mo
# at 2 scans a day); prop lookups cost 3-5 per game and would drain the
# month in under a week. So: once remaining credits drop below this
# floor, prop calls stop for the run (loudly) and the card runs on
# featured markets only. Raise the plan, raise the shelf -- the guard
# reads the live header, so a bigger plan lifts it automatically.
CREDIT_RESERVE = 150

# THE PARLAY BOARD (owner request, Sep 8 2026). Same constitution,
# different question. The gap card above asks "where is Kalshi's crowd
# underpricing the sharps?" The parlay board asks the owner's question:
# "who are today's MOST LIKELY WINNERS, so I can stack them?" The
# answer comes from the SAME expert -- the de-vigged sharp consensus --
# and from nowhere else. Kalshi's price plays NO part in choosing a
# leg (the owner plays parlays at their own sportsbook; this board
# never bets, per the permanent advisory-only rule). Kalshi's job here
# is settlement truth: every leg must match a hand-verified Kalshi
# market so the board can be graded by Kalshi's own `result` field --
# a favorite we could not grade never makes the board.
#
# PARLAY_LEG_MIN_PROB: a parlay leg must be a real favorite, not a
# lean. 60% is the floor -- stacking anything weaker builds a lottery
# ticket, and the whole point is "most likely winners". (The gap
# card's 55% is a minimum LEAN for a single pick; a parlay multiplies
# its legs, so the bar is higher.)
PARLAY_LEG_MIN_PROB = 60.0
# Full-game/match moneylines ONLY (the shelves marked parlay=True):
# clean win/lose markets the books and Kalshi define identically. F5
# winners (tie risk), totals and props stay off the board -- legs must
# be simple enough to stack honestly. (Was a hardcoded 2-shelf set
# until Sep 10 2026; the owner's expansion made it a per-shelf flag,
# same rule, more leagues.)
PARLAY_MAX_LEGS = 4        # beyond 4 legs even 65% favorites hit <18%
PARLAY_LEGS_SHOWN = 6      # the ranked leg list on the card

# THE COMBO BOARD (owner request, Sep 10 2026): "build high paying
# combos from the Kalshi market, combining any sector." Same
# constitution as the parlay board, one shelf wider: the stack may mix
# SPORTS legs (the sharps' 60%+ full-game moneyline favorites -- the
# exact parlay-board pool, unchanged) with WEATHER legs (the money
# lane's own morning bracket picks). More qualifying favorites means
# taller stacks, and a taller stack of real favorites is the ONLY
# honest road to a high payout -- a payout is bought with combined
# risk, never found for free. Long-shot legs stay banned: the cheap-
# leg disease went 2W-22L under 20c and 9-21 in the old sports card,
# and no combo resurrects it.
#
# THE WEATHER LEG DUAL-EXPERT RULE (evidence, Sep 10 2026): the
# ensemble's claimed probability alone is NOT calibrated enough to
# stack -- autopsy §4: claims of 55%+ delivered ~35% across 51 settled
# bets, and even post-rebuild morning 60%+ claims ran ~50%. So a
# weather leg must be called a 60%+ favorite by BOTH experts at once:
# the ensemble (>= PARLAY_LEG_MIN_PROB % of members on the picked
# bracket) AND the market itself (a live Kalshi YES bid of >= the same
# number, in cents). The leg's stated probability is the LOWER of the
# two -- the board understates, never overstates (the Phoenix law's
# direction). Backtest on every morning-lane pick in edges.csv,
# graded against settlements.csv (Aug 21 - Sep 8 2026): legs passing
# both bars went 14W-2L (88%) while stating ~66% on average. Sixteen
# legs is a thin sample -- combo_results.csv exists to keep grading
# that rule for real, stated % vs hit rate, same as the parlay board.
#
# The laws carried over word for word: ADVISORY ONLY FOREVER (nothing
# here places, sizes, or sells a bet, and nothing that trades may ever
# read these files); the expert picks the leg (the bracket is always
# the ensemble's pick -- never a bracket picked because its price
# looks good); every leg is a hand-verified Kalshi market graded by
# Kalshi's own `result`; no dollar P&L in the results file, because no
# venue's combo payout is knowable -- the fair_payout column is what a
# no-vig book would pay, stated so the owner can see what their own
# book's price is worth. Kalshi itself sells each leg as a separate
# market -- there is no combo ticket there; buying every leg on Kalshi
# pays each leg on its own, NOT the multiplied number.
#
# Benched cities (scanner.py BENCHED_CITIES -- parsed from the source
# at run time, watchdog-style, never a mirrored copy that can drift)
# never supply a leg: a board titled "most likely winners" does not
# seat a city the scoreboard benched for losing.
COMBO_MAX_LEGS = 8         # 8 legs of 62% favorites ~ 2% / ~$46 fair --
                           # past that even a stack of favorites is
                           # pure lottery and the % rounds to zero
WEATHER_EDGES_CSV = "edges.csv"      # the weather expert's own log
WEATHER_SCANNER_SRC = "scanner.py"   # read for BENCHED_CITIES only

PICKS_CSV = "sports_picks.csv"
RESULTS_CSV = "sports_results.csv"
PARLAY_CSV = "parlay_picks.csv"
PARLAY_RESULTS_CSV = "parlay_results.csv"
PAGE = "sports.html"

PICKS_FIELDS = ["scanned_utc", "sport", "shelf", "game", "detail",
                "commence_utc", "series", "ticker", "side", "pick",
                "books_pct", "kalshi_cents", "fee_cents", "gap_cents",
                "n_books", "shown", "why"]
RESULTS_FIELDS = ["graded_utc", "sport", "shelf", "game", "detail",
                  "ticker", "side", "pick", "books_pct", "kalshi_cents",
                  "gap_cents", "market_result", "result", "pnl"]
# legs / tickers / leg_probs_pct are pipe-separated, aligned by index
# (same convention as forecasts.csv members|member_models). fair_payout
# = 1/combined_prob in dollars per $1: what a no-vig book would pay.
# No pnl column ON PURPOSE -- we cannot know what the owner's book
# pays on a parlay, and inventing a payout would violate the honesty
# rules. The scoreboard question is calibration: stated % vs hit rate.
PARLAY_FIELDS = ["scanned_utc", "parlay_id", "n_legs", "legs", "tickers",
                 "leg_probs_pct", "combined_pct", "fair_payout",
                 "last_start_utc"]
PARLAY_RESULTS_FIELDS = ["graded_utc", "parlay_id", "n_legs", "legs",
                         "tickers", "combined_pct", "legs_won",
                         "legs_lost", "legs_void", "result"]
# Combo board files: same shape as the parlay pair plus `sectors`
# (pipe-separated sector tag per leg -- MLB/NFL/WEATHER -- aligned
# with legs/tickers/leg_probs_pct). Same no-pnl law, same union-merge
# append-only law (.gitattributes).
COMBO_CSV = "combo_picks.csv"
COMBO_RESULTS_CSV = "combo_results.csv"
COMBO_FIELDS = ["scanned_utc", "combo_id", "n_legs", "sectors", "legs",
                "tickers", "leg_probs_pct", "combined_pct",
                "fair_payout", "last_start_utc"]
COMBO_RESULTS_FIELDS = ["graded_utc", "combo_id", "n_legs", "sectors",
                        "legs", "tickers", "combined_pct", "legs_won",
                        "legs_lost", "legs_void", "result"]

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
         featured=True, has_tie=False, parlay=True),
    dict(key="NFL_GAME", sport="americanfootball_nfl",
         label="NFL · MONEYLINE", kind="winner", series="KXNFLGAME",
         odds_market="h2h", featured=True, has_tie=False, parlay=True),
    # -- THE EXPANSION (owner request, Sep 10 2026): college football,
    # -- NBA, tennis -- so the card and the combo board cover the
    # -- leagues the owner plays. Verified against the live catalogue
    # -- and open markets via the expansion probe, Sep 10 2026:
    # --   KXNCAAFGAME "College Football Game", 200 open markets;
    # --   KXNBAGAME "Pro Basketball Game", 6 open (Oct 20 slate);
    # --   KXATPMATCH / KXWTAMATCH "ATP/WTA Tennis Match", 4 each
    # --     (US Open semifinals) -- tennis shelves are built at run
    # --     time from the Odds API's live tournament keys, see
    # --     tennis_shelves() below.
    # -- These series' event tickers carry DATE + teams but NO game
    # -- time (KXNBAGAME-26OCT20OKCSAS), and college/tennis codes are
    # -- variable-length -- so match="names": teams pair against
    # -- Kalshi's own market subtitles ('Oklahoma City', 'Alabama',
    # -- 'Ben Shelton') instead of a hand-kept code map. Exact rules
    # -- in match_event_by_names(); wrong or missing name = loud
    # -- UNMATCHED skip, never a wrong match -- same guarantee as the
    # -- code matcher, without 130 hand-guessed school codes.
    dict(key="NCAAF_GAME", sport="americanfootball_ncaaf",
         label="CFB · MONEYLINE", kind="winner", series="KXNCAAFGAME",
         odds_market="h2h", featured=True, has_tie=False, parlay=True,
         match="names"),
    dict(key="NBA_GAME", sport="basketball_nba",
         label="NBA · MONEYLINE", kind="winner", series="KXNBAGAME",
         odds_market="h2h", featured=True, has_tie=False, parlay=True,
         match="names"),
    # NOT included on purpose (verified but not comparable yet):
    #  KXMLBF7 -- books don't quote a first-7-innings line.
    #  KXNFL1H/KXNFL1HTOTAL -- tie handling in Kalshi's 1H rules not yet
    #    hand-read; add only after reading rules_primary via the probe.
    #  KXMLBHIT/KXMLBHR/KXMLBHRR/KXMLBHA -- batter props; add after the
    #    Odds API plan is confirmed to carry batter markets.
    #  GOLF (owner asked, Sep 10 2026 -- deliberately OFF, and here is
    #    why in plain terms): the Odds API feed carries only
    #    tournament-winner outrights for golf (no matchup lines), a
    #    pre-tournament favorite is ~20-30% -- nowhere near any pick
    #    or leg bar -- and KXGOLFTOURN had ZERO open markets at
    #    verification time, so its anatomy could not be hand-read.
    #    Golf joins only when (a) an odds source carries golf matchups
    #    the sharps actually price and (b) the Kalshi series is
    #    verified live. Anything sooner would be invented data.
]


def tennis_shelves():
    """Tennis shelves, built at run time (owner request Sep 10 2026).

    The Odds API keys tennis PER TOURNAMENT (tennis_atp_us_open, ...)
    and retires each key when the tournament ends, so a hardcoded key
    would die in a week. Instead the free /sports catalogue is read
    each scan and every active tennis_atp_*/tennis_wta_* key becomes a
    shelf. The KALSHI side stays fixed and hand-verified -- ATP maps
    to KXATPMATCH, WTA to KXWTAMATCH (verified live Sep 10 2026, US
    Open semifinals; ticker anatomy KXATPMATCH-26SEP11ZVEKHA with full
    player names in the subtitles) -- so this is not series discovery:
    the whitelist law governs Kalshi series, and both of those are
    whitelisted above by hand. Challenger-tour series (junk liquidity,
    no odds coverage) are deliberately NOT mapped."""
    if not ODDS_KEY:
        return []
    data, err = oget(f"/sports?apiKey={ODDS_KEY}", "sports catalogue")
    if err:
        print(f"!! tennis: /sports catalogue failed ({err}) -- no "
              f"tennis shelves this run")
        return []
    shelves = []
    for s in data or []:
        key = s.get("key", "")
        if not s.get("active"):
            continue
        if key.startswith("tennis_atp_"):
            series, tour = "KXATPMATCH", "ATP"
        elif key.startswith("tennis_wta_"):
            series, tour = "KXWTAMATCH", "WTA"
        else:
            continue
        shelves.append(dict(
            key=f"TENNIS_{key}", sport=key,
            label=f"TENNIS · {s.get('title', tour)}", kind="winner",
            series=series, odds_market="h2h", featured=True,
            has_tie=False, parlay=True, match="names"))
        print(f"tennis shelf: {key} -> {series} ({s.get('title', '')})")
    if not shelves:
        print("tennis: no active tour keys on the odds feed right now "
              "(between tournaments) -- tennis returns when the next "
              "tournament's lines go up")
    return shelves

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
CREDITS = {"remaining": None}   # live x-requests-remaining, for the guard


def oget(path, label):
    """Odds API GET -> (json, err). Tracks remaining quota for the guard."""
    req = urllib.request.Request(OBASE + path,
                                 headers={"User-Agent": "weather-bot-card"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            left = r.headers.get("x-requests-remaining")
            if left is not None:
                print(f"  [{label}] odds-api credits remaining: {left}")
                try:
                    CREDITS["remaining"] = float(left)
                except ValueError:
                    pass
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
    """Per-event odds for prop markets. Mutates dead_keys on plan errors
    and stops for the run when the credit budget is nearly spent."""
    keys = [k for k in market_keys if k not in dead_keys]
    if not keys:
        return None
    rem = CREDITS["remaining"]
    if rem is not None and rem < CREDIT_RESERVE:
        print(f"!! CREDIT GUARD: only {rem:.0f} odds-api credits left this "
              f"month (< {CREDIT_RESERVE}). Skipping prop lookups so the "
              f"featured card keeps running -- upgrade the Odds API plan "
              f"to lift this.")
        dead_keys.update(keys)
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


# Event tickers WITHOUT a game time: KXNCAAFGAME-26SEP19MONMALBY,
# KXNBAGAME-26OCT20OKCSAS, KXATPMATCH-26SEP11ZVEKHA (verified in the
# Sep 10 2026 expansion probe). Date + one letter block; the block's
# team/player codes are variable length, so it is never split -- the
# names in the market subtitles do the matching instead.
EVENT_DATE_RE = re.compile(r"^(\d{2})([A-Z]{3})(\d{2})[A-Z0-9]+$")


def parse_event_date(event_ticker, series):
    """KXNBAGAME-26OCT20OKCSAS -> date(2026, 10, 20) ET-calendar, or
    None. Used by the name matcher; these series carry no start time."""
    if not event_ticker.startswith(series + "-"):
        return None
    m = EVENT_DATE_RE.match(event_ticker[len(series) + 1:])
    if not m:
        return None
    yy, mon, dd = m.groups()
    if mon not in MONTHS:
        return None
    try:
        return datetime(2000 + int(yy), MONTHS[mon], int(dd)).date()
    except ValueError:
        return None


def name_matches(odds_name, kalshi_sub):
    """Does the books' name belong to Kalshi's subtitle? True only when
    the normalized subtitle IS the odds name, or is its full-word
    prefix -- 'Alabama' fits 'Alabama Crimson Tide', 'Oklahoma City'
    fits 'Oklahoma City Thunder', 'Ohio St.' fits 'Ohio State
    Buckeyes' (the one abbreviation Kalshi uses, 'St.', is expanded to
    'state' on both sides first -- verified across all 150 school
    subtitles in the Sep 10 2026 probe dump, where it is the only
    shorthand). Anything looser would be the substring-matching scar
    wearing a new hat; a name this rule can't pair is a loud
    UNMATCHED skip, and the log line is the tell for fixing it."""
    a = re.sub(r"\bst\b", "state", norm(odds_name))
    b = re.sub(r"\bst\b", "state", norm(kalshi_sub))
    if not a or not b:
        return False
    return a == b or a.startswith(b + " ")


def match_event_by_names(kalshi_events, series, game):
    """The matcher for series whose tickers carry no time and no fixed-
    width codes (college football, NBA, tennis). An event matches ONLY
    if its ticker date equals the game's ET calendar date AND each of
    the game's two sides pairs, by name_matches against the market
    subtitles, to a DIFFERENT market of that one event -- the longest
    subtitle wins when both of an event's subtitles fit (so 'Ohio St.'
    beats 'Ohio' for Ohio State). Two events matching the same game =
    ambiguous = loud skip; one team never plays twice on one date in
    these sports, so a clean match is unique. Returns (event_ticker,
    markets, {side_name: market}) or (None, None, None)."""
    want = game["commence"].astimezone(ET).date()
    found = []
    for et, mkts in kalshi_events.items():
        if parse_event_date(et, series) != want:
            continue
        assign = {}
        ok = True
        for side in (game["away"], game["home"]):
            cands = [(len(norm(m.get("yes_sub_title") or "")), m)
                     for m in mkts
                     if name_matches(side, m.get("yes_sub_title") or "")]
            if not cands:
                ok = False
                break
            cands.sort(key=lambda x: -x[0])
            assign[side] = cands[0][1]
        if ok and assign[game["away"]] is not assign[game["home"]]:
            found.append((et, mkts, assign))
    if len(found) == 1:
        return found[0]
    if len(found) > 1:
        print(f"  AMBIGUOUS {series}: {game['game']} matched "
              f"{len(found)} events on {want} -- refusing to guess")
    return None, None, None


def match_event(kalshi_events, series, sport, game):
    """The matcher. An event matches ONLY if its ticker parses cleanly,
    its team block equals AWAYCODE+HOMECODE exactly, and -- when the
    ticker carries a start time -- that time agrees with the books'
    start to within 30 minutes (doubleheader safety). NFL tickers since
    the 2026 season carry NO time (KXNFLGAME-26SEP13DALNYG -- date +
    codes, same anatomy as the names-matched series; read off the
    whale tape Sep 12 2026, the day all 8 NFL games went UNMATCHED
    while thousands of dollars traded on them). For those, the ticker
    date must equal the game's ET calendar date; an NFL team never
    plays twice on one date, so the exact-code guarantee holds without
    a clock -- the names matcher's own justification. Two date-format
    events matching one game = ambiguous = loud skip, never a guess."""
    codes = TEAM_CODES.get(sport, {})
    ac, hc = codes.get(game["away"]), codes.get(game["home"])
    if not ac or not hc:
        print(f"  UNMATCHED (no team code): {game['game']}")
        return None, None
    want = ac + hc
    best = None
    dated = []
    for et, mkts in kalshi_events.items():
        parsed = parse_event_ticker(et, series)
        if parsed:
            start_et, teams = parsed
            if teams != want:
                continue
            drift = abs((start_et - game["commence"]).total_seconds())
            if drift <= 1800 and (best is None or drift < best[0]):
                best = (drift, et, mkts)
            continue
        m = re.match(r"^\d{2}[A-Z]{3}\d{2}([A-Z0-9]+)$",
                     et[len(series) + 1:]) \
            if et.startswith(series + "-") else None
        if not m or m.group(1) != want:
            continue
        if parse_event_date(et, series) != \
                game["commence"].astimezone(ET).date():
            continue
        dated.append((et, mkts))
    if best:
        return best[1], best[2]
    if len(dated) == 1:
        return dated[0]
    if len(dated) > 1:
        print(f"  AMBIGUOUS {series}: {game['game']} matched "
              f"{len(dated)} date-format events -- refusing to guess")
    return None, None


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
    assign = None
    if shelf.get("match") == "names":
        et, mkts, assign = match_event_by_names(
            kalshi_events, shelf["series"], game)
    else:
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
    teams = {t: p for t, p in fair.items() if t != draw_key}
    pick_team = max(teams, key=teams.get)
    fair_pct = fair[pick_team] * 100
    if fair_pct < MIN_PICK_PROB:
        return                      # coin flip -- the sharps have no pick
    if assign is not None:
        # names matcher already paired each side to its own market;
        # the pick can only be one of the game's two sides
        market = assign.get(pick_team)
    else:
        codes = TEAM_CODES[shelf["sport"]]
        suffix = "-" + codes.get(pick_team, "???")
        market = next((m for m in mkts
                       if m.get("ticker", "").endswith(suffix)), None)
        if market is None:
            print(f"  UNMATCHED {shelf['key']}: no {suffix} market "
                  f"in {et}")
            return
    if market is None:
        print(f"  UNMATCHED {shelf['key']}: no market for pick "
              f"{pick_team!r} in {et}")
        return
    if (shelf.get("parlay")
            and fair_pct >= PARLAY_LEG_MIN_PROB):
        # a parlay-board candidate: the sharps' favorite, with the
        # matched Kalshi ticker that will grade it at settlement.
        # No liquidity or price gate -- the board is played at the
        # owner's own book, not on Kalshi.
        PARLAY_POOL.append({
            "pick": f"{pick_team} wins", "game": game["game"],
            "fair_pct": fair_pct, "n_books": n,
            "ticker": market.get("ticker", ""),
            "commence": game["commence"],
            "label": shelf["label"].split(" ·")[0]})
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


# -------------------------------------------- combo board: weather legs
WX_TICKER_DATE = re.compile(r"-(\d{2})([A-Z]{3})(\d{2})-")


def weather_benched_cities():
    """BENCHED_CITIES parsed from scanner.py's own source line at run
    time (the watchdog's trick for trader.py's band -- never a mirrored
    copy that can drift). FAIL-CLOSED: if the line can't be read, the
    caller must refuse ALL weather legs rather than risk seating a
    benched city on a board of 'most likely winners'."""
    try:
        src = open(WEATHER_SCANNER_SRC).read()
        m = re.search(r"^BENCHED_CITIES\s*=\s*(\{[^}]*\})", src, re.M)
        if not m:
            return None
        bench = ast.literal_eval(m.group(1))
        return set(bench) if isinstance(bench, (set, frozenset)) else None
    except (OSError, ValueError, SyntaxError):
        return None


def weather_market_date(ticker):
    """KXHIGHTLV-26SEP09-B105.5 -> date(2026, 9, 9), or None."""
    m = WX_TICKER_DATE.search(ticker or "")
    if not m:
        return None
    yy, mon, dd = m.groups()
    if mon not in MONTHS:
        return None
    try:
        return date_cls(2000 + int(yy), MONTHS[mon], int(dd))
    except ValueError:
        return None


def weather_live_bid(ticker):
    """The market expert's live number for a weather leg: Kalshi's YES
    bid in cents, unauthenticated (market data needs no key -- same as
    the rest of this file). Returns (bid_cents, err). A market that is
    no longer open, or has no readable bid, is a loud skip -- never a
    guess and never a stale morning quote presented as current."""
    data, err = kget(f"/markets/{ticker}", ticker)
    if err:
        return None, err
    m = (data or {}).get("market", {})
    status = (m.get("status") or "").lower()
    if status not in ("active", "open"):
        return None, f"market status {status or 'unknown'} -- day over"
    bid = dollars_to_cents(m, "yes_bid_dollars")
    if bid is None:
        no_ask = dollars_to_cents(m, "no_ask_dollars")
        if no_ask is not None:
            bid = 100 - no_ask       # the same number, quoted from the
                                     # other side of the book
    if bid is None or bid <= 0:
        return None, "no readable YES bid"
    return bid, None


def weather_legs():
    """TODAY's qualifying weather legs under the dual-expert rule (see
    the config block: ensemble >= PARLAY_LEG_MIN_PROB % of members on
    the picked bracket AND a live Kalshi bid >= the same bar; the leg
    states the LOWER of the two). The bracket itself is always the
    ensemble's pick straight from the money lane's own log -- morning-
    strategy edges.csv rows, latest scan per city -- never a bracket
    chosen here, and never chosen by price. No fresh morning pick for
    a city today = no leg for that city, said out loud."""
    if not os.path.exists(WEATHER_EDGES_CSV):
        print("!! combo board: edges.csv missing -- no weather legs")
        return []
    bench = weather_benched_cities()
    if bench is None:
        print("!! combo board: could not read BENCHED_CITIES from "
              f"{WEATHER_SCANNER_SRC} -- refusing ALL weather legs "
              "(fail-closed) rather than risk seating a benched city")
        return []
    today = datetime.now(timezone.utc).date()
    latest = {}                      # city -> freshest pick row today
    with open(WEATHER_EDGES_CSV) as f:
        for r in csv.DictReader(f):
            if r.get("strategy") != "morning" or r.get("pick") != "1":
                continue
            if (r.get("scanned_utc") or "")[:10] != today.isoformat():
                continue
            if weather_market_date(r.get("market")) != today:
                continue
            city = (r.get("city") or "").strip()
            if not city:
                continue
            if (city not in latest
                    or r["scanned_utc"] > latest[city]["scanned_utc"]):
                latest[city] = r
    legs = []
    for city, r in sorted(latest.items()):
        try:
            model = float(r.get("model_prob_pct") or "")
        except ValueError:
            continue
        if model < PARLAY_LEG_MIN_PROB:
            continue                 # the ensemble itself has no 60%+
                                     # opinion -- silence, not a near-miss
        if city in bench:
            print(f"  combo: {city} pick qualifies on numbers but the "
                  f"city is BENCHED by the scoreboard -- no leg")
            continue
        station = CITY_TO_STATION.get(city)
        tz = TIMEZONES.get(station) if station else None
        if not tz:
            print(f"  combo: {city} has no verified timezone -- SKIP "
                  f"(never guess a clock)")
            continue
        ticker = r.get("market") or ""
        bid, err = weather_live_bid(ticker)
        time.sleep(0.3)
        if bid is None:
            print(f"  combo: {city} {ticker}: no market quote ({err}) "
                  f"-- no leg")
            continue
        if bid < PARLAY_LEG_MIN_PROB:
            print(f"  combo: {city} pick -- ensemble {model:.0f}% but "
                  f"the live market bids only {bid:.0f}c "
                  f"(< {PARLAY_LEG_MIN_PROB:.0f}) -- the two experts "
                  f"disagree, no leg")
            continue
        stated = min(model, bid)     # understate, never overstate
        # a weather leg is "done" at the end of the city's own local
        # day; settlement lands overnight and the grader waits for it
        end_local = (datetime(today.year, today.month, today.day,
                              tzinfo=ZoneInfo(tz)) + timedelta(days=1))
        subtitle = (r.get("subtitle") or "").strip() or "picked bracket"
        legs.append({
            "pick": f"{city} high {subtitle}",
            "game": f"{city} daily high, {today.isoformat()}",
            "fair_pct": stated,
            "src": (f"ensemble {model:.0f}% of {r.get('n_members') or '?'} "
                    f"members · market bids {bid:.0f}¢"),
            "ticker": ticker,
            "commence": end_local.astimezone(timezone.utc),
            "label": "WEATHER"})
        print(f"  combo leg: {city} high {subtitle} -- stated "
              f"{stated:.0f}% (ensemble {model:.0f}%, bid {bid:.0f}c)")
    return legs


def build_combos(pool):
    """Stack the whole cross-sector pool, biggest favorites first.
    Combined probability is the plain product; one leg per game and per
    city holds by construction (scan_winner emits one favorite per
    game, weather_legs one bracket per city). Built ONLY when at least
    one weather leg made the pool -- a sports-only stack is the parlay
    board's job, and logging the same stack under two names would
    double-count the record. Weather legs in the same air mass are not
    fully independent, so the stated combined % is an approximation
    there -- said on the card, and judged by combo_results.csv."""
    seen = set()
    legs = []
    for c in sorted(pool, key=lambda c: -c["fair_pct"]):
        if not c["ticker"] or c["ticker"] in seen:
            continue
        seen.add(c["ticker"])
        legs.append(c)
    if len(legs) < 2 or not any(c["label"] == "WEATHER" for c in legs):
        return legs, []
    combos = []
    day = SCAN_STAMP[:10]
    for n in range(2, min(len(legs), COMBO_MAX_LEGS) + 1):
        top = legs[:n]
        combined = 1.0
        for c in top:
            combined *= c["fair_pct"] / 100.0
        combos.append({
            "scanned_utc": SCAN_STAMP,
            "combo_id": f"{day}-COMBO-{n}LEG",
            "n_legs": n,
            "sectors": "|".join(c["label"] for c in top),
            "legs": " | ".join(f"{c['pick']} ({c['game']})" for c in top),
            "tickers": "|".join(c["ticker"] for c in top),
            "leg_probs_pct": "|".join(f"{c['fair_pct']:.1f}" for c in top),
            "combined_pct": round(combined * 100, 1),
            "fair_payout": round(1 / combined, 2) if combined > 0 else "",
            "last_start_utc": max(c["commence"] for c in top).isoformat()})
    return legs, combos


# --------------------------------------------------------- parlay board
PARLAY_POOL = []            # candidates collected by scan_winner this run


def build_parlays(pool):
    """Rank the day's sharps favorites and stack the top ones.
    Returns (ranked_legs, parlay_rows). Combined probability is the
    plain product -- separate games are independent events, and one
    leg per game is guaranteed by construction (scan_winner emits at
    most one favorite per game per moneyline shelf)."""
    seen = set()
    legs = []
    for c in sorted(pool, key=lambda c: -c["fair_pct"]):
        if c["ticker"] in seen or not c["ticker"]:
            continue
        seen.add(c["ticker"])
        legs.append(c)
    parlays = []
    day = SCAN_STAMP[:10]
    for n in range(2, min(len(legs), PARLAY_MAX_LEGS) + 1):
        top = legs[:n]
        combined = 1.0
        for c in top:
            combined *= c["fair_pct"] / 100.0
        parlays.append({
            "scanned_utc": SCAN_STAMP,
            "parlay_id": f"{day}-{n}LEG",
            "n_legs": n,
            "legs": " | ".join(f"{c['pick']} ({c['game']})" for c in top),
            "tickers": "|".join(c["ticker"] for c in top),
            "leg_probs_pct": "|".join(f"{c['fair_pct']:.1f}" for c in top),
            "combined_pct": round(combined * 100, 1),
            "fair_payout": round(1 / combined, 2) if combined > 0 else "",
            "last_start_utc": max(c["commence"] for c in top).isoformat()})
    return legs, parlays


_SETTLE_CACHE = {}          # ticker -> market object, shared by both
                            # graders (combos reuse parlay tickers, so
                            # the cache halves the Kalshi calls)


def grade_stacks(picks_csv, results_csv, results_fields, id_col,
                 carry=(), what="parlay"):
    """Grade stacked boards (parlays AND combos) by Kalshi settlement,
    leg by leg. A stack grades only when EVERY leg's market is settled.
    Any lost leg = MISS. Void legs (cancelled games; a weather market
    Kalshi voids) drop out, the way books drop pushed legs: all
    remaining legs won = HIT; every leg void = VOID. Returns newly
    graded rows."""
    if not os.path.exists(picks_csv):
        return []
    already = set()
    if os.path.exists(results_csv):
        with open(results_csv) as f:
            for r in csv.DictReader(f):
                already.add(r["tickers"])
    pending = {}                       # tickers-key -> latest scanned row
    with open(picks_csv) as f:
        for r in csv.DictReader(f):
            k = r["tickers"]
            if k in already or not k:
                continue
            last = iso(r.get("last_start_utc", ""))
            if not last or last > datetime.now(timezone.utc) - timedelta(hours=3):
                continue               # last leg too recent to be settled
            if k not in pending or r["scanned_utc"] > pending[k]["scanned_utc"]:
                pending[k] = r
    graded = []
    for k, r in list(pending.items())[:10]:
        won = lost = void = 0
        settled = True
        for ticker in k.split("|"):
            if ticker not in _SETTLE_CACHE:
                data, err = kget(f"/markets/{ticker}", ticker)
                _SETTLE_CACHE[ticker] = (data or {}).get("market", {}) \
                    if not err else None
                time.sleep(0.3)
            m = _SETTLE_CACHE[ticker]
            if m is None:
                settled = False
                break
            status = (m.get("status") or "").lower()
            result = (m.get("result") or "").lower()
            if status not in ("settled", "finalized"):
                settled = False
                break
            if result == "yes":
                won += 1
            elif result == "no":
                lost += 1
            else:
                void += 1              # cancelled/voided: leg drops out
        if not settled:
            continue                   # next run
        if lost:
            verdict = "MISS"
        elif won:
            verdict = "HIT"
        else:
            verdict = "VOID"
        row = {"graded_utc": datetime.now(timezone.utc)
               .isoformat(timespec="seconds"),
               id_col: r[id_col], "n_legs": r["n_legs"],
               "legs": r["legs"], "tickers": k,
               "combined_pct": r["combined_pct"],
               "legs_won": won, "legs_lost": lost,
               "legs_void": void, "result": verdict}
        for c in carry:
            row[c] = r.get(c, "")
        graded.append(row)
        print(f"  graded {what} {r[id_col]}: {verdict} "
              f"({won}W-{lost}L-{void}V, stated {r['combined_pct']}%)")
    if graded:
        with appender(results_csv, results_fields) as w:
            for g in graded:
                w.writerow(g)
    return graded


def grade_parlays():
    return grade_stacks(PARLAY_CSV, PARLAY_RESULTS_CSV,
                        PARLAY_RESULTS_FIELDS, "parlay_id",
                        what="parlay")


def grade_combos():
    return grade_stacks(COMBO_CSV, COMBO_RESULTS_CSV,
                        COMBO_RESULTS_FIELDS, "combo_id",
                        carry=("sectors",), what="combo")


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


def build_parlay_html(legs, parlays, presults):
    """The parlay board section: ranked most-likely winners, then the
    stacked combos with honest combined numbers."""
    if not legs and not presults:
        return ""
    out = "<h2>The parlay board &mdash; today's most likely winners</h2>"
    if not legs:
        out += ("<div class='empty'><b>No parlay board today.</b><br>"
                "No game on the slate has a favorite the sharps make "
                f"{PARLAY_LEG_MIN_PROB:.0f}%+ likely (or its Kalshi "
                "market for grading couldn't be matched). A board built "
                "from weaker favorites would be a lottery ticket, so "
                "there isn't one.</div>")
    else:
        rows = ""
        for i, c in enumerate(legs[:PARLAY_LEGS_SHOWN], 1):
            when = c["commence"].strftime("%a %H:%M UTC")
            rows += (f"<tr><td>#{i}</td>"
                     f"<td><b>{html.escape(c['pick'])}</b><br>"
                     f"<span class='when'>{html.escape(c['label'])} · "
                     f"{html.escape(c['game'])} · {when}</span></td>"
                     f"<td><b>{c['fair_pct']:.0f}%</b></td>"
                     f"<td>{c['n_books']}</td></tr>")
        out += (f"<table><tr><th></th><th>The sharps' favorite</th>"
                f"<th>Win chance</th><th>Books</th></tr>{rows}</table>")
        for p in parlays:
            combined = float(p["combined_pct"])
            leg_lines = "".join(
                f"<div class='pick'>&#10148; <b>{html.escape(t)}</b> "
                f"<span class='when'>{q}%</span></div>"
                for t, q in zip(p["legs"].split(" | "),
                                p["leg_probs_pct"].split("|")))
            out += f"""
<div class="slip"><div class="punch"></div>
<div class="stamp gap">{p['n_legs']} LEGS</div>
<div class="slipbody">
<span class="tag">PARLAY</span><span class="when">stack of the top {p['n_legs']}</span>
{leg_lines}
<div class="nums"><span>Honest chance all hit: <b>{combined:.0f}%</b></span>
<span>Fair payout <b>${p['fair_payout']} per $1</b></span></div>
<div class="why">If your sportsbook pays less than ${p['fair_payout']}
on a $1 stake for this exact combo, the difference is the parlay tax.
These are the day's most likely winners &mdash; and this stack still
misses {100 - combined:.0f} times out of 100. Size accordingly.</div>
</div></div>"""
    if presults:
        hits = sum(1 for r in presults if r["result"] == "HIT")
        misses = sum(1 for r in presults if r["result"] == "MISS")
        prows = ""
        for r in list(reversed(presults))[:12]:
            cls = {"HIT": "W", "MISS": "L"}.get(r["result"], "V")
            prows += (f"<tr><td>{html.escape(r['parlay_id'])}</td>"
                      f"<td>{html.escape(r['legs'])}</td>"
                      f"<td>{float(r['combined_pct']):.0f}%</td>"
                      f"<td class='{cls}'>{r['result']}</td></tr>")
        out += (f"<h2>Parlay record: {hits} hit, {misses} missed "
                f"(graded by Kalshi settlement)</h2>"
                f"<table><tr><th>Parlay</th><th>Legs</th>"
                f"<th>Stated chance</th><th>Result</th></tr>{prows}</table>")
    return out


def build_combo_html(combo_legs, combos, cresults):
    """THE COMBO BOARD section: the cross-sector stack ladder. Shown
    biggest payout first because that is the owner's question -- with
    the honest chance printed just as large, because the two are the
    same number upside down."""
    if not combo_legs and not cresults:
        return ""
    out = ("<h2>The combo board &mdash; cross-sector stacks, "
           "highest payout first</h2>")
    n_wx = sum(1 for c in combo_legs if c["label"] == "WEATHER")
    if not combos:
        if len(combo_legs) < 2:
            why = ("Fewer than two qualifying favorites across all "
                   "sectors right now.")
        elif n_wx == 0:
            why = ("No weather leg qualifies right now &mdash; today's "
                   "strongest bracket pick did not clear the dual-expert "
                   f"bar (ensemble AND live market both "
                   f"{PARLAY_LEG_MIN_PROB:.0f}%+), so the only honest "
                   "stacks today are the sports parlays above.")
        else:
            why = "Not enough qualifying favorites to stack."
        out += (f"<div class='empty'><b>No combos this scan.</b><br>"
                f"{why} A combo built from weaker legs would be a "
                f"lottery ticket wearing a suit, so there isn't "
                f"one.</div>")
    else:
        rows = ""
        for i, c in enumerate(combo_legs, 1):
            when = c["commence"].strftime("%a %H:%M UTC")
            done = ("settles overnight" if c["label"] == "WEATHER"
                    else when)
            rows += (f"<tr><td>#{i}</td>"
                     f"<td><span class='tag'>{html.escape(c['label'])}"
                     f"</span></td>"
                     f"<td><b>{html.escape(c['pick'])}</b><br>"
                     f"<span class='when'>{html.escape(c['game'])} · "
                     f"{done}</span></td>"
                     f"<td><b>{c['fair_pct']:.0f}%</b><br>"
                     f"<span class='when'>{html.escape(c['src'])}"
                     f"</span></td></tr>")
        out += (f"<table><tr><th></th><th>Sector</th>"
                f"<th>The favorite</th><th>Win chance (why)</th></tr>"
                f"{rows}</table>")
        for j, p in enumerate(reversed(combos)):
            combined = float(p["combined_pct"])
            stamp = ("top" if j == 0 else "gap")
            label = ("MAX PAYOUT" if j == 0 else f"{p['n_legs']} LEGS")
            leg_lines = "".join(
                f"<div class='pick'>&#10148; <b>{html.escape(t)}</b> "
                f"<span class='when'>{q}% · {html.escape(s)}</span></div>"
                for t, q, s in zip(p["legs"].split(" | "),
                                   p["leg_probs_pct"].split("|"),
                                   p["sectors"].split("|")))
            out += f"""
<div class="slip"><div class="punch"></div>
<div class="stamp {stamp}">{label}</div>
<div class="slipbody">
<span class="tag">COMBO</span><span class="when">the top {p['n_legs']} favorites, all sectors</span>
{leg_lines}
<div class="nums"><span>Fair payout <b>${p['fair_payout']} per $1</b></span>
<span>Honest chance all hit: <b>{combined:.1f}%</b></span></div>
<div class="why">${p['fair_payout']} per $1 is what a no-vig book would
pay this exact stack &mdash; and it misses about
{100 - combined:.0f} times out of 100. The payout isn't found, it's
bought with combined risk. Kalshi has no combo ticket: buying each leg
there pays each leg on its own, never this multiplied number.</div>
</div></div>"""
    if cresults:
        hits = sum(1 for r in cresults if r["result"] == "HIT")
        misses = sum(1 for r in cresults if r["result"] == "MISS")
        crows = ""
        for r in list(reversed(cresults))[:12]:
            cls = {"HIT": "W", "MISS": "L"}.get(r["result"], "V")
            crows += (f"<tr><td>{html.escape(r['combo_id'])}</td>"
                      f"<td>{html.escape(r['legs'])}</td>"
                      f"<td>{float(r['combined_pct']):.1f}%</td>"
                      f"<td class='{cls}'>{r['result']}</td></tr>")
        out += (f"<h2>Combo record: {hits} hit, {misses} missed "
                f"(graded by Kalshi settlement)</h2>"
                f"<table><tr><th>Combo</th><th>Legs</th>"
                f"<th>Stated chance</th><th>Result</th></tr>{crows}"
                f"</table>")
    return out


def build_page(shown, results, feed_dead, parlay_legs, parlays, presults,
               combo_legs, combos, cresults):
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
{build_parlay_html(parlay_legs, parlays, presults)}
{build_combo_html(combo_legs, combos, cresults)}
{hist}
<div class="foot"><b>How this card works, in one breath:</b> the sharpest
sportsbooks in the world publish their opinion as prices; we strip out
their commission to get an honest probability, then check what Kalshi's
crowd charges for the same thing. When the crowd sells the sharps' pick
at least {GAP_MIN:.0f}¢ under the sharps' own number (after Kalshi's
fee), it makes the card. We never pick against the sharps, never chase
a "cheap" longshot, and anything over +{GAP_MAX:.0f}¢ is treated as bad
data and suppressed. Props (first-5-innings, totals, strikeouts) are the
main event -- moneylines tag along. The card covers MLB, NFL, college
football, the NBA (once its games are inside the scan window) and
tour-level tennis; golf is deliberately absent because the odds feed
carries only tournament-winner longshots for it -- no matchup lines
means no honest pick, so none is invented. Sharps must lean at least
{MIN_PICK_PROB:.0f}% -- coin flips don't get picks. Every market we
evaluate is logged to sports_picks.csv, shown or not, and every shown
pick is graded by Kalshi's own settlement in sports_results.csv. The
record above is the only reason to trust (or ignore) this card.
<br><br><b>The parlay board</b> answers a different question: not
"what's mispriced" but "who are today's most likely winners". Legs are
the sharps' strongest full-game or full-match favorites, from any
league on the card ({PARLAY_LEG_MIN_PROB:.0f}%+
after removing the books' commission), Kalshi's price plays no part in
choosing them, and each leg must match a hand-verified Kalshi market so
the board can be graded by Kalshi's own settlement &mdash; hit or miss,
in parlay_results.csv. The stated combined chance is the honest
multiplied probability; there's no dollar score on purpose, because
every sportsbook pays parlays differently. This board, like everything
here, never bets. You do (or don't).
<br><br><b>The combo board</b> is the parlay board with every sector
of this operation invited: the sharps' strongest game favorites plus
the weather bot's own strongest bracket picks, stacked tallest-payout
first. A weather leg has to pass TWO experts at once &mdash; the
ensemble must put {PARLAY_LEG_MIN_PROB:.0f}%+ of its members on the
bracket AND Kalshi's live market must bid {PARLAY_LEG_MIN_PROB:.0f}¢+
for it &mdash; because the record shows the ensemble alone runs
overconfident; the leg then states the LOWER of the two numbers, so
the board understates on purpose. Cities benched by the scoreboard
never supply a leg. One honest wrinkle: weather picks in the same air
mass can win or lose together, so a stack heavy on nearby cities is
riskier than the multiplied number implies &mdash; the combo record
above is the judge of that, stated chance vs hit rate. And the plain
truth about "high paying": the payout and the chance are the same
number upside down &mdash; the only honest way to a bigger payout is
stacking MORE real favorites, never reaching for longer shots. This
board never bets, same permanent rule as everything on this page.</div>
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
    all_shelves = list(SHELVES)
    if not feed_dead:
        all_shelves += tennis_shelves()   # tournament keys are live-
                                          # discovered; Kalshi side fixed
    for s in all_shelves:
        shelves_by_sport[s["sport"]].append(s)

    sports_ok = 0
    series_cache = {}     # series -> fetched events; KXATPMATCH backs
                          # every concurrent ATP tournament shelf, so
                          # fetch each series once per run
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
                if s["series"] not in series_cache:
                    series_cache[s["series"]] = \
                        fetch_kalshi_series(s["series"])
                    time.sleep(0.4)
                ev = series_cache[s["series"]]
                if ev is not None:
                    kalshi[s["key"]] = ev
                    print(f"  kalshi {s['series']}: {len(ev)} open events")
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

    parlay_legs, parlays = build_parlays(PARLAY_POOL)
    if parlays:
        with appender(PARLAY_CSV, PARLAY_FIELDS) as w:
            for p in parlays:
                w.writerow(p)
    print(f"parlay board: {len(parlay_legs)} qualifying favorites, "
          f"{len(parlays)} stacked combos")

    # THE COMBO BOARD: the parlay pool plus the weather sector's
    # dual-expert legs. Weather legs need no odds key, so a dead odds
    # feed leaves the weather side of the board standing (and the red
    # dead-feed banner still flies).
    wx_legs = weather_legs()
    combo_pool = ([dict(c, src=f"{c['n_books']} sharp books")
                   for c in PARLAY_POOL] + wx_legs)
    combo_legs, combos = build_combos(combo_pool)
    if combos:
        with appender(COMBO_CSV, COMBO_FIELDS) as w:
            for p in combos:
                w.writerow(p)
    print(f"combo board: {len(combo_legs)} favorites across sectors "
          f"({len(wx_legs)} weather), {len(combos)} stacked combos")

    graded = grade()
    print(f"graded {len(graded)} settled picks")
    pgraded = grade_parlays()
    print(f"graded {len(pgraded)} settled parlays")
    cgraded = grade_combos()
    print(f"graded {len(cgraded)} settled combos")
    results = list(csv.DictReader(open(RESULTS_CSV))) \
        if os.path.exists(RESULTS_CSV) else []
    presults = list(csv.DictReader(open(PARLAY_RESULTS_CSV))) \
        if os.path.exists(PARLAY_RESULTS_CSV) else []
    cresults = list(csv.DictReader(open(COMBO_RESULTS_CSV))) \
        if os.path.exists(COMBO_RESULTS_CSV) else []

    with open(PAGE, "w") as f:
        f.write(build_page(shown, results, feed_dead,
                           parlay_legs, parlays, presults,
                           combo_legs, combos, cresults))
    print(f"wrote {PAGE}")

    if feed_dead:
        raise SystemExit(3)        # red run = someone looks. The card and
                                   # scoreboard were still written first.


if __name__ == "__main__":
    main()
