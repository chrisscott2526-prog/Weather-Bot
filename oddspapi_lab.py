"""Weather-Bot: THE ODDSPAPI LAB (Sep 15 2026) -- research-only
side-by-side of two odds feeds, built the day the owner supplied the
free-tier ODDSPAPI_KEY (the OddsPapi conversation, Sep 14-15 2026).

THE QUESTION: is OddsPapi's sharp consensus (Pinnacle-led) better
calibrated than The Odds API consensus the sports card already uses?
The leg lab (leg_research.csv) logs every parlay-shelf favorite with
The Odds API's de-vigged number and grades it by Kalshi settlement.
This lab logs ODDSPAPI's de-vigged number FOR THE SAME PICKS, so the
October review can join the two on the ticker and ask which expert's
stated % matched reality. If OddsPapi wins, swapping the advisory
card's feed is a normal change argued from this record.

THE LAW (same as every research lane): oddspapi_research.csv is a
RESEARCH LOG ONLY. Nothing that boards, trades, scans for money, or
calibrates may EVER read it. No board changes while this runs.

Verified live before this was coded (oddspapi_probe.yml runs 1-4,
Sep 15 2026 -- every constant below cites those logs):
- base https://api.oddspapi.io/v4, auth apiKey query param
- tournaments: NFL=31, MLB=109 (run 4)
- FULL-GAME moneyline markets, period "result", playerProp false
  (run 4 dictionary dump): american-football marketId 141
  (outcomes 141="1", 142="2"), baseball marketId 131 (131/132)
  [basketball 111 (111/112) and tennis 121 (121/122) recorded for
  the day those sports join]
- outcome "1" = participant1, "2" = participant2 (dictionary);
  fixture objects carry participant1Name/participant2Name (run 2)
- bulk endpoint: odds-by-tournaments?tournamentIds=X&bookmaker=slug,
  EXACTLY ONE bookmaker per call, ~1 req/sec rate limit with 429 +
  retryMs (runs 3-4)
- free tier serves pinnacle (694KB NFL payload incl. limits) and 3et
  (160KB); singbet has no NFL (run 4). Books are HAND-WHITELISTED
  here -- the sports whitelist law, never discovery. cloneOf books
  never join (round 1: clones would double-count a consensus).

COST, stated plainly: per scan = 1 fixtures call + 2 book calls per
league with games that day; NFL+MLB worst case 6 requests/day at one
scan/day ~= 180/month against the free tier's ~250. The paid plan is
the owner's lever IF the early record earns wider coverage -- never
before.

Honesty rules: a pick that can't be matched to exactly one OddsPapi
fixture is a LOUD skip, never a guessed match; a book with no active
two-sided moneyline contributes nothing (no invented consensus, no
guessed vig); zero rows written when fresh picks existed = non-zero
exit (dead-feed law). Missing/empty key = immediate RED (the Aug 19
2026 empty-secret scar).

Usage:  python oddspapi_lab.py            # normal scan
        python oddspapi_lab.py --out F    # write elsewhere (testing)
"""

import csv, json, os, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
from statistics import median as true_median
from csvio import appender

OUT_DEFAULT = "oddspapi_research.csv"
FIELDS = ["scanned_utc", "sport", "game", "pick", "ticker",
          "commence_utc", "oddspapi_pct", "n_books",
          "oddspapi_low_pct", "oddspapi_high_pct",
          "theoddsapi_pct", "kalshi_bid_cents", "boarded"]

LEG_FILE = "leg_research.csv"

BASE = "https://api.oddspapi.io/v4"
KEY = os.environ.get("ODDSPAPI_KEY", "").strip()

# Hand-verified constants -- probe runs 1-4, Sep 15 2026 (see header).
TOURNAMENTS = {"NFL": 31, "MLB": 109}      # leg-lab sport tag -> id
MONEYLINE = {"NFL": ("141", "141", "142"),  # marketId, outcome "1", "2"
             "MLB": ("131", "131", "132")}
SHARP_BOOKS = ["pinnacle", "3et"]  # hand-whitelisted; pinnacle is THE
                                   # sharp; 3et verified live; no clones
RATE_SLEEP = 1.5   # the bulk endpoint 429s under ~1 req/sec (probe 3)
MAX_LEG_AGE_H = 24  # only picks from the last day's scans
FIXTURE_TIME_SLACK_MIN = 45  # name-pair must also agree on start time


def get(path, **params):
    """One API call; never prints the key or the URL. Raises on
    transport failure after 3 tries; 429 waits and retries."""
    params["apiKey"] = KEY
    url = f"{BASE}/{path}?" + urllib.parse.urlencode(params)
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent":
                                         "weather-bot-research"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            if e.code == 429:
                try:
                    wait = json.loads(body)["error"]["retryMs"] / 1000.0
                except Exception:
                    wait = 2.0
                time.sleep(min(wait + 0.5, 10))
                last = e
                continue
            raise RuntimeError(f"HTTP {e.code} on /{path}: {body[:200]}")
        except Exception as e:
            last = e
            if attempt < 2:
                print(f"    retry {attempt + 1}/2 after: {e}")
                time.sleep(3)
    raise RuntimeError(f"/{path} failed after retries: {last}")


def norm(name):
    """Team-name normalizer for exact-pair matching. Deliberately
    conservative: lowercase, collapse spaces, drop periods -- no
    fuzzy matching (a wrong match is worse than a loud skip)."""
    return " ".join(str(name).replace(".", " ").lower().split())


def fresh_legs():
    """Latest leg-lab row per ticker: NFL/MLB, scanned within
    MAX_LEG_AGE_H, game not yet started."""
    now = datetime.now(timezone.utc)
    legs = {}
    try:
        with open(LEG_FILE, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                sport = (r.get("sport") or "").strip()
                if sport not in TOURNAMENTS:
                    continue
                try:
                    scanned = datetime.fromisoformat(r["scanned_utc"])
                    commence = datetime.fromisoformat(r["commence_utc"])
                except Exception:
                    continue
                if (now - scanned) > timedelta(hours=MAX_LEG_AGE_H):
                    continue
                if commence <= now:
                    continue
                legs[r["ticker"]] = r   # later rows overwrite = latest
    except FileNotFoundError:
        print(f"{LEG_FILE} not found -- nothing to compare against.")
    return list(legs.values())


def devig_two_way(book_odds, sport):
    """(p1, p2) de-vigged from one book's full-game moneyline, or
    None. Requires BOTH sides present, active, decimal price > 1.01
    -- a one-sided or suspended line contributes nothing."""
    mkt_id, out1, out2 = MONEYLINE[sport]
    markets = (book_odds or {}).get("markets") or {}
    m = markets.get(mkt_id)
    if not m or not m.get("marketActive"):
        return None
    prices = {}
    for out_id, entry in (m.get("outcomes") or {}).items():
        player0 = ((entry or {}).get("players") or {}).get("0") or {}
        if not player0.get("active"):
            continue
        p = player0.get("price")
        if p is None or float(p) <= 1.01:
            continue
        prices[str(out_id)] = float(p)
    if out1 not in prices or out2 not in prices:
        return None
    inv1, inv2 = 1.0 / prices[out1], 1.0 / prices[out2]
    total = inv1 + inv2
    if total <= 0:
        return None
    return inv1 / total * 100.0, inv2 / total * 100.0


def main():
    if not KEY:
        sys.exit("ODDSPAPI_KEY is MISSING or EMPTY -- the dead-feed "
                 "law says fail loudly (the Aug 19 2026 scar).")
    out = OUT_DEFAULT
    if "--out" in sys.argv:
        out = sys.argv[sys.argv.index("--out") + 1].strip()
        if not out or out.startswith("-"):
            raise SystemExit("--out needs a filename")

    legs = fresh_legs()
    sports_needed = sorted({r["sport"] for r in legs})
    print(f"ODDSPAPI LAB (research only): {len(legs)} fresh leg-lab "
          f"picks to price ({', '.join(sports_needed) or 'none'})")
    if not legs:
        print("No fresh NFL/MLB picks in the leg lab -- an honest "
              "quiet day, nothing fetched, nothing written.")
        return

    now = datetime.now(timezone.utc)
    scanned = now.isoformat(timespec="seconds")

    # One fixtures call + one bulk call per whitelisted book, per
    # league actually needed today. ~1.5s spacing for the rate limit.
    fixtures = {}       # sport -> list of fixture dicts (names, times)
    book_odds = {}      # sport -> book -> {fixtureId: bookmaker block}
    for sport in sports_needed:
        tid = TOURNAMENTS[sport]
        frm = (now - timedelta(days=1)).date().isoformat()
        to = (now + timedelta(days=2)).date().isoformat()
        fixtures[sport] = get("fixtures", tournamentId=tid,
                              **{"from": frm, "to": to})
        print(f"{sport}: {len(fixtures[sport])} fixtures {frm}..{to}")
        book_odds[sport] = {}
        for book in SHARP_BOOKS:
            time.sleep(RATE_SLEEP)
            try:
                bulk = get("odds-by-tournaments", tournamentIds=tid,
                           bookmaker=book)
            except RuntimeError as e:
                # A sharp with no line today prints and contributes
                # nothing -- never a fake number (their 404 is
                # FIXTURE_NOT_FOUND, probe run 4).
                print(f"{sport}: {book} unavailable - {e}")
                continue
            by_id = {}
            for fx in bulk if isinstance(bulk, list) else []:
                blocks = (fx.get("bookmakerOdds") or {})
                if book in blocks:
                    by_id[fx.get("fixtureId")] = blocks[book]
            book_odds[sport][book] = by_id
            print(f"{sport}: {book} priced {len(by_id)} fixtures")

    rows = 0
    with appender(out, FIELDS) as w:
        for leg in legs:
            sport, game = leg["sport"], leg["game"]
            # leg-lab game format is "Away @ Home" (The Odds API
            # names); match the UNORDERED name pair + start time.
            if " @ " not in game:
                print(f"SKIP (unparseable game): {game}")
                continue
            away, home = (norm(p) for p in game.split(" @ ", 1))
            try:
                commence = datetime.fromisoformat(leg["commence_utc"])
            except Exception:
                print(f"SKIP (bad commence_utc): {game}")
                continue
            matches = []
            for fx in fixtures.get(sport, []):
                p1 = norm(fx.get("participant1Name"))
                p2 = norm(fx.get("participant2Name"))
                if {p1, p2} != {away, home}:
                    continue
                try:
                    start = datetime.fromisoformat(
                        str(fx.get("startTime")).replace("Z", "+00:00"))
                except Exception:
                    continue
                if abs((start - commence).total_seconds()) \
                        <= FIXTURE_TIME_SLACK_MIN * 60:
                    matches.append((fx, p1))
            if len(matches) != 1:
                print(f"UNMATCHED ({len(matches)} candidates): {game} "
                      f"@ {leg['commence_utc']} -- loud skip, never a "
                      "guessed match")
                continue
            fx, p1 = matches[0]
            fid = fx.get("fixtureId")

            # The pick is "<Team> wins" (leg-lab format); map it to
            # outcome "1" (participant1) or "2".
            pick_team = norm(leg["pick"].rsplit(" wins", 1)[0])
            if pick_team == p1:
                side = 0
            elif pick_team == norm(fx.get("participant2Name")):
                side = 1
            else:
                print(f"SKIP (pick name mismatch): {leg['pick']} vs "
                      f"{fx.get('participant1Name')}/"
                      f"{fx.get('participant2Name')}")
                continue

            pcts = []
            for book in SHARP_BOOKS:
                block = book_odds.get(sport, {}).get(book, {}).get(fid)
                dv = devig_two_way(block, sport)
                if dv:
                    pcts.append(dv[side])
            if not pcts:
                print(f"NO SHARP LINE: {game} ({leg['pick']}) -- no "
                      "row (a missing number is honest)")
                continue

            w.writerow({
                "scanned_utc": scanned, "sport": sport, "game": game,
                "pick": leg["pick"], "ticker": leg["ticker"],
                "commence_utc": leg["commence_utc"],
                "oddspapi_pct": round(true_median(pcts), 1),
                "n_books": len(pcts),
                "oddspapi_low_pct": round(min(pcts), 1),
                "oddspapi_high_pct": round(max(pcts), 1),
                "theoddsapi_pct": leg.get("books_pct", ""),
                "kalshi_bid_cents": leg.get("kalshi_bid_cents", ""),
                "boarded": leg.get("boarded", "")})
            rows += 1
            print(f"{game}: {leg['pick']} -- OddsPapi "
                  f"{round(true_median(pcts), 1)}% ({len(pcts)} books) "
                  f"vs The Odds API {leg.get('books_pct', '?')}%")

    print(f"OddsPapi lab done: {rows} rows -> {out}")
    if rows == 0:
        print("DEAD FEED? Fresh picks existed but ZERO were priced -- "
              "failing loudly (the Aug 19 2026 scar: a dead feed must "
              "never look green). Check the UNMATCHED/NO-LINE lines "
              "above; if names or markets drifted, re-run the probe.")
        sys.exit(1)


if __name__ == "__main__":
    main()
