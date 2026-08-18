"""Weather-Bot repo: SPORTS EDGE SCAN (advisor only -- places NO bets).

Compares sharp sportsbook consensus against Kalshi's FULL-GAME MONEYLINE
markets and shows the mispriced side, if any.

What it does, every run:
  1. Pulls moneyline consensus from sharp sportsbooks via The Odds API.
  2. De-vigs the books' prices into fair win probabilities.
  3. Pulls Kalshi markets from a WHITELIST of full-game moneyline series
     only -- see MONEYLINE_SERIES below. This is the whole ballgame.
  4. Computes net edge (fair% - Kalshi ask - Kalshi fee) on both sides.
  5. Logs EVERY evaluated pair to sports_picks.csv (full data, always).
  6. Grades yesterday's shown picks against final scores -> sports_results.csv.
  7. Rebuilds sports.html -- the bet-slip dashboard you read before betting.

WHY THE WHITELIST EXISTS (Aug 2 2026 -- do not undo this):
The old version matched any Kalshi series whose name contained "MLB", "NFL",
"NCAA" etc. That swept in:
  KXMLBF3          First 3 Innings Winner      (inning prop, not the game)
  KXMLBF7          First 7 Innings Winner      (inning prop, not the game)
  KXMLBSPREAD      run spread                  (not a moneyline)
  KXNEXTTEAMMLB    which team a player signs with (not a game at all)
  KXNCAAFCUSAQUAL  Conference USA football      (matched "Houston" = Astros)
It then compared those prices to full-game win probability and reported
"edges" of 20-50 cents. Those edges were never real. A true MLB moneyline
edge is 2-5c and rare. If this card ever shows you 40c again, the matcher
is broken -- not the market.

Secrets needed: KALSHI_API_KEY_ID, KALSHI_PRIVATE_KEY, ODDS_API_KEY.
"""

import base64, csv, html, json, math, os, re, time, urllib.error, urllib.request
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from statistics import median
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from csvio import appender

# ---------- config ----------
SPORTS = {  # Odds API sport key -> label
    "baseball_mlb": "MLB",
    "basketball_nba": "NBA",
    "americanfootball_nfl": "NFL",
    "americanfootball_ncaaf": "CFB",
    "basketball_ncaab": "CBB",
}

# THE WHITELIST. label -> exact Kalshi series tickers that are full-game
# moneyline markets ("who wins this game"). Nothing else is ever scanned.
# Confirmed from the live series dump on Aug 2 2026.
# To add one: run the scan, read the SERIES lines in the log, confirm the
# title says it's a whole-game winner market, then add the exact ticker.
MONEYLINE_SERIES = {
    "MLB": ["KXMLBGAME"],        # "Professional Baseball Game"
    "NFL": ["KXNFLGAME"],        # "Professional Football Game"
    "CBB": ["KXNCAAMBGAME"],     # "Men's College Basketball Men's Game"
    "NBA": [],                   # offseason Aug 2026 -- no game series seen
    "CFB": [],                   # preseason -- add KXNCAAFGAME when it opens
}

SHOW_EDGE = 2.0        # cents of net edge required to appear on the card
STRONG_EDGE = 4.0      # cents -> gets the BEST PLAY stamp treatment
MAX_EDGE = 15.0        # SANITY CAP. Bigger than this = something is wrong.
COMBO_MIN_LEG_EDGE = 5.0   # books% - kalshi% needed to qualify as combo leg
COMBO_HAIRCUT = 0.03       # Kalshi shaves ~2-3%/leg on combos (measured Aug 3)
COMBO_MAX_LEGS = 4
COMBO_MAX_TRUE = 60.0      # legs above this books% add little payout; skip
                     # Logged with shown=0 and a loud warning, never shown.
MIN_BOOKS = 3          # need at least this many books in consensus
MAX_HOURS_OUT = 30     # only games starting within this window
MIN_ASK, MAX_ASK = 10, 90   # ignore extreme moneylines
PICKS_CSV = "sports_picks.csv"
RESULTS_CSV = "sports_results.csv"

PICKS_FIELDS = ["scanned_utc", "sport", "game", "commence_utc", "ticker",
                "series", "action", "pick_team", "opponent", "ask_cents",
                "fair_pct", "fee_cents", "edge_cents", "n_books",
                "shown", "why"]
# layout before the series column was added mid-row (Aug 6 2026)
PICKS_LEGACY = [[c for c in PICKS_FIELDS if c != "series"]]
RESULTS_FIELDS = ["graded_utc", "sport", "game", "commence_utc", "ticker",
                  "action", "pick_team", "ask_cents", "edge_cents",
                  "winner", "result", "pnl"]
PAGE = "sports.html"

KBASE = "https://api.elections.kalshi.com"
OBASE = "https://api.the-odds-api.com/v4"
KEY_ID = os.environ["KALSHI_API_KEY_ID"].strip()
ODDS_KEY = os.environ["ODDS_API_KEY"].strip()


# ---------- kalshi auth (same as the rest of the repo) ----------
def load_key():
    raw = os.environ["KALSHI_PRIVATE_KEY"].replace("\\n", "\n").strip()
    m = re.search(r"-----BEGIN ([A-Z ]+)-----(.*?)-----END \1-----", raw, re.DOTALL)
    if not m:
        raise ValueError("No BEGIN/END block in KALSHI_PRIVATE_KEY")
    label, body = m.group(1), m.group(2)
    b64 = re.sub(r"[^A-Za-z0-9+/=]", "", body)
    lines = [b64[i:i + 64] for i in range(0, len(b64), 64)]
    pem = (f"-----BEGIN {label}-----\n" + "\n".join(lines)
           + f"\n-----END {label}-----\n").encode()
    return serialization.load_pem_private_key(pem, password=None)

key = load_key()

def ksigned(path):
    ts = str(int(time.time() * 1000))
    sig = key.sign((ts + "GET" + path.split("?")[0]).encode(),
                   padding.PSS(mgf=padding.MGF1(hashes.SHA256()),
                               salt_length=padding.PSS.DIGEST_LENGTH),
                   hashes.SHA256())
    req = urllib.request.Request(KBASE + path, headers={
        "KALSHI-ACCESS-KEY": KEY_ID,
        "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode(),
        "KALSHI-ACCESS-TIMESTAMP": ts,
        "User-Agent": "weather-bot-personal"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def oget(path):
    with urllib.request.urlopen(OBASE + path, timeout=30) as r:
        remain = r.headers.get("x-requests-remaining")
        if remain:
            print(f"  odds-api credits left: {remain}")
        return json.load(r)


# ---------- helpers ----------
def cents(m, field):
    v = m.get(field)
    try:
        c = float(v) * 100
        return c if c > 0 else None
    except (TypeError, ValueError):
        return None

def fee_cents(price_cents):
    p = price_cents / 100.0
    return math.ceil(7 * p * (1 - p))

def nickname(team):
    """'Atlanta Braves' -> 'braves'. Returns '' for empty/odd input."""
    words = re.sub(r"[^a-z0-9 ]", "", (team or "").lower()).split()
    return words[-1] if words else ""

def iso(ts):
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


# ---------- 1-2: books consensus ----------
def fetch_consensus():
    """[{sport, game, home, away, commence, fair: {team: prob}, n_books}]"""
    out = []
    for skey, label in SPORTS.items():
        if not MONEYLINE_SERIES.get(label):
            print(f"{label}: no moneyline series whitelisted, skipping")
            continue
        try:
            events = oget(f"/sports/{skey}/odds?regions=us&markets=h2h"
                          f"&oddsFormat=decimal&apiKey={ODDS_KEY}")
        except urllib.error.HTTPError as e:
            print(f"{label}: odds fetch failed HTTP {e.code} (off-season?)")
            continue
        except Exception as e:
            print(f"{label}: odds fetch failed ({e})")
            continue
        now = datetime.now(timezone.utc)
        for ev in events:
            start = iso(ev.get("commence_time", ""))
            if not start or start < now or start > now + timedelta(hours=MAX_HOURS_OUT):
                continue
            home, away = ev.get("home_team"), ev.get("away_team")
            if not home or not away:
                continue
            probs = defaultdict(list)
            for bk in ev.get("bookmakers", []):
                for mkt in bk.get("markets", []):
                    if mkt.get("key") != "h2h":
                        continue
                    o = {oc["name"]: oc["price"] for oc in mkt.get("outcomes", [])
                         if oc.get("price")}
                    if home in o and away in o and o[home] > 1 and o[away] > 1:
                        probs[home].append(1 / o[home])
                        probs[away].append(1 / o[away])
            n = min(len(probs.get(home, [])), len(probs.get(away, [])))
            if n < MIN_BOOKS:
                continue
            ph, pa = median(probs[home]), median(probs[away])
            tot = ph + pa                      # de-vig: normalize the pair
            out.append({"sport": label, "home": home, "away": away,
                        "game": f"{away} @ {home}",
                        "commence": start,
                        "fair": {home: ph / tot, away: pa / tot},
                        "n_books": n})
    return out


# ---------- 3: kalshi moneyline markets (WHITELIST ONLY) ----------
def fetch_kalshi_moneylines():
    """{label: [market dicts]} -- only from whitelisted full-game series."""
    by_sport = {}
    for label, tickers in MONEYLINE_SERIES.items():
        mkts = []
        for st in tickers:
            try:
                data = ksigned(f"/trade-api/v2/markets?series_ticker={st}"
                               f"&status=open&limit=200")
            except Exception as e:
                print(f"  {st}: markets fetch failed ({e})")
                continue
            for m in data.get("markets", []):
                text = " ".join(str(m.get(k) or "") for k in
                                ("title", "subtitle", "yes_sub_title")).lower()
                mkts.append({"ticker": m.get("ticker", ""), "text": text,
                             "series": st,
                             "yes_hint": (m.get("yes_sub_title") or "").lower(),
                             "yes_ask": cents(m, "yes_ask_dollars"),
                             "no_ask": cents(m, "no_ask_dollars")})
        if tickers:
            print(f"kalshi {label}: {len(mkts)} open moneyline markets "
                  f"from {tickers}")
        by_sport[label] = mkts
    return by_sport


def team_keys(team):
    """'San Diego Padres' -> {'padres', 'san diego'}: nickname + city."""
    words = re.sub(r"[^a-z0-9 ]", "", (team or "").lower()).split()
    if not words:
        return set()
    keys = {words[-1]}
    if len(words) > 1:
        keys.add(" ".join(words[:-1]))
    return keys


def match_market(game, mkts):
    """Find the Kalshi market for this game and which team YES means.
    BOTH teams must be named in the market text. There is deliberately no
    single-team fallback -- that is what matched Sam Houston State to the
    Houston Astros. If we cannot confirm both teams, we do not bet."""
    hk, ak = team_keys(game["home"]), team_keys(game["away"])
    if not hk or not ak:
        return None, None
    for m in mkts:
        h_hit = any(k in m["text"] for k in hk)
        a_hit = any(k in m["text"] for k in ak)
        if not (h_hit and a_hit):
            continue
        if any(k in m["yes_hint"] for k in hk) and \
           not any(k in m["yes_hint"] for k in ak):
            return m, game["home"]
        if any(k in m["yes_hint"] for k in ak) and \
           not any(k in m["yes_hint"] for k in hk):
            return m, game["away"]
        mm = re.search(r"will the ([a-z0-9 .]+?) (beat|win)", m["text"])
        if mm:
            who = team_keys(mm.group(1))
            if who & hk:
                return m, game["home"]
            if who & ak:
                return m, game["away"]
    return None, None


# ---------- 6: grade past picks ----------
def grade(picks_rows):
    already = set()
    if os.path.exists(RESULTS_CSV):
        with open(RESULTS_CSV) as f:
            for r in csv.DictReader(f):
                already.add((r["ticker"], r["action"], r["commence_utc"]))
    pending = {}
    for r in picks_rows:
        if r.get("shown") != "1":
            continue
        k = (r["ticker"], r["action"], r["commence_utc"])
        if k in already:
            continue
        st = iso(r["commence_utc"])
        if st and st < datetime.now(timezone.utc) - timedelta(hours=4):
            pending[k] = r          # latest row wins
    if not pending:
        return []
    sports_needed = {r["sport"] for r in pending.values()}
    winners = {}                    # (sport, frozenset(nicknames)) -> winner
    label_to_key = {v: k for k, v in SPORTS.items()}
    for label in sports_needed:
        if label not in label_to_key:
            continue
        try:
            scores = oget(f"/sports/{label_to_key[label]}/scores?daysFrom=2"
                          f"&apiKey={ODDS_KEY}")
        except Exception as e:
            print(f"grade {label}: scores fetch failed ({e})")
            continue
        for g in scores:
            if not g.get("completed"):
                continue
            sc = {s["name"]: float(s["score"]) for s in (g.get("scores") or [])
                  if s.get("score") is not None}
            if len(sc) == 2:
                w = max(sc, key=sc.get)
                keyset = frozenset(nickname(t) for t in sc)
                winners[(label, keyset)] = w
    graded = []
    for (ticker, action, commence), r in pending.items():
        keyset = frozenset({nickname(r["pick_team"]), nickname(r["opponent"])})
        w = winners.get((r["sport"], keyset))
        if not w:
            continue
        pick_won = (nickname(w) == nickname(r["pick_team"])) == (action == "YES")
        ask = float(r["ask_cents"]); fee = float(r["fee_cents"])
        pnl = round(((100 - ask - fee) if pick_won else -(ask + fee)) / 100, 2)
        graded.append({"graded_utc": datetime.now(timezone.utc)
                       .isoformat(timespec="seconds"),
                       "sport": r["sport"], "game": r["game"],
                       "commence_utc": commence, "ticker": ticker,
                       "action": action, "pick_team": r["pick_team"],
                       "ask_cents": ask, "edge_cents": r["edge_cents"],
                       "winner": w,
                       "result": "WIN" if pick_won else "LOSS", "pnl": pnl})
    if graded:
        with appender(RESULTS_CSV, RESULTS_FIELDS) as w:
            for g in graded:
                w.writerow(g)
    return graded

# ---------- 6.5: combo legs ----------
def combo_legs(rows):
    """Rows where books beat Kalshi's price by COMBO_MIN_LEG_EDGE+ points.
    One leg per game (best side). Raw gap, not fee-adjusted edge."""
    best_by_game = {}
    for r in rows:
        try:
            fair = float(r["fair_pct"])
            ask = float(r["ask_cents"])
        except (KeyError, TypeError, ValueError):
            continue
        gap = fair - ask
        if gap < COMBO_MIN_LEG_EDGE or fair > COMBO_MAX_TRUE + 20:
            continue
        g = r["game"]
        if g not in best_by_game or gap > best_by_game[g]["gap"]:
            best_by_game[g] = {**r, "gap": round(gap, 1)}
    legs = sorted(best_by_game.values(), key=lambda r: -r["gap"])
    return legs

def combo_math(legs):
    """True hit prob and approx Kalshi quote for the top 2..N legs."""
    out = []
    for n in range(2, min(COMBO_MAX_LEGS, len(legs)) + 1):
        pick = legs[:n]
        p_true, p_k = 1.0, 1.0
        for l in pick:
            p_true *= float(l["fair_pct"]) / 100.0
            p_k *= float(l["ask_cents"]) / 100.0 / (1 - COMBO_HAIRCUT)
        x = (1 / p_k) if p_k else 0
        out.append({"n": n, "teams": [l["pick_team"] for l in pick],
                    "true_pct": round(p_true * 100, 1),
                    "ten_pays": round(10 * x, 2),
                    "ev": round(p_true * x, 2)})
    return out

# ---------- 7: the dashboard ----------
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
.nums{display:flex;gap:18px;font-size:13px;color:var(--dim);
margin:8px 0 10px;font-variant-numeric:tabular-nums}
.nums b{color:var(--ink)}
.why{font-size:14px;border-top:1px solid var(--line);padding-top:10px}
.stamp{position:absolute;right:12px;top:12px;
font:700 15px/1 "Barlow Condensed",sans-serif;letter-spacing:.1em;
border:2.5px solid;border-radius:4px;padding:6px 9px;
transform:rotate(6deg);text-transform:uppercase}
.stamp.edge{color:var(--felt);border-color:var(--felt)}
.stamp.best{color:var(--gold);border-color:var(--gold)}
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
.foot{margin-top:26px;font-size:12.5px;color:var(--dim);line-height:1.6}
@media (prefers-reduced-motion:no-preference){
.slip{transition:transform .12s}.slip:hover{transform:translateY(-2px)}}
"""

def build_page(shown, results, note, all_rows):
    now = datetime.now(timezone.utc).strftime("%a %b %d, %H:%M UTC")
    wins = sum(1 for r in results if r["result"] == "WIN")
    losses = sum(1 for r in results if r["result"] == "LOSS")
    pnl = sum(float(r["pnl"]) for r in results)
    slips = ""
    best = max((float(p["edge_cents"]) for p in shown), default=0)
    for p in shown:
        e = float(p["edge_cents"])
        stamp = ("best" if e >= STRONG_EDGE and e == best else "edge")
        label = ("BEST PLAY" if stamp == "best" else f"+{e:.1f}c EDGE")
        start = iso(p["commence_utc"])
        when = start.strftime("%a %H:%M UTC") if start else ""
        side = ("to WIN" if p["action"] == "YES" else "NOT to win (buy NO)")
        slips += f"""
<div class="slip"><div class="punch"></div>
<div class="stamp {stamp}">{label}</div>
<div class="slipbody">
<span class="tag">{html.escape(p['sport'])}</span><span class="when">{when}</span>
<div class="match">{html.escape(p['game'])}</div>
<div class="pick">Bet <b>{html.escape(p['pick_team'])} {side}</b>
on Kalshi at <b>{float(p['ask_cents']):.0f}c</b></div>
<div class="nums"><span>Books say <b>{float(p['fair_pct']):.0f}%</b></span>
<span>Kalshi charges <b>{float(p['ask_cents']):.0f}c</b></span>
<span>Fee <b>{float(p['fee_cents']):.0f}c</b></span>
<span>Net edge <b>+{e:.1f}c</b></span></div>
<div class="why">{html.escape(p['why'])}</div>
</div></div>"""
    if not slips:
        slips = ("<div class='empty'><b>No edges on today's board.</b><br>"
                 "The books and the Kalshi crowd agree on every full-game "
                 "moneyline we can match. Moneylines are efficient, so this "
                 "is the normal result. When there's nothing mispriced, the "
                 "best bet is no bet.</div>")
    rows = ""
    for r in list(reversed(results))[:15]:
        rows += (f"<tr><td>{html.escape(r['sport'])}</td>"
                 f"<td>{html.escape(r['pick_team'])} "
                 f"({html.escape(r['action'])})</td>"
                 f"<td class='{r['result'][0]}'>{r['result']}</td>"
                 f"<td>{'+' if float(r['pnl'])>=0 else ''}{float(r['pnl']):.2f}</td></tr>")
    legs = combo_legs(all_rows)
    combo = ""
    if len(legs) >= 2:
        lines = ""
        for l in legs:
            lines += (f"<tr><td>{html.escape(l['pick_team'])}</td>"
                      f"<td>{html.escape(l['game'])}</td>"
                      f"<td>{float(l['fair_pct']):.0f}%</td>"
                      f"<td>{float(l['ask_cents']):.0f}c</td>"
                      f"<td>+{l['gap']:.1f}</td></tr>")
        maths = ""
        for c in combo_math(legs):
  
            maths += (f"<tr><td>{c['n']}-leg</td>"
                      f"<td>{html.escape(' + '.join(c['teams']))}</td>"
                      f"<td>{c['true_pct']:.0f}%</td>"
                      f"<td>${c['ten_pays']:.2f}</td>"
                      f"<td>{c['ev']:.2f}x</td></tr>")
        combo = (f"<h2>Combo legs (books beat Kalshi by "
                 f"{COMBO_MIN_LEG_EDGE:.0f}+ pts)</h2><table>"
                 f"<tr><th>Team</th><th>Game</th><th>Books</th>"
                 f"<th>Kalshi</th><th>Gap</th></tr>{lines}</table>"
                 f"<h2>If you combine the top legs</h2><table>"
                 f"<tr><th>Size</th><th>Legs</th><th>True odds</th>"
                 f"<th>$10 pays ~</th><th>EV</th></tr>{maths}</table>"
                 f"<div class='foot'>Build it yourself in Kalshi's COMBO "
                 f"screen with these exact legs. True odds is the books' "
                 f"honest chance every leg hits. EV above 1.00x means the "
                 f"payout beats the odds. Kalshi's quote will differ "
                 f"slightly. Combos lose most days by design - never bet "
                 f"more than the fun is worth.</div>")
     
    hist = (f"<h2>Recent results (graded automatically)</h2><table>"
            f"<tr><th>Sport</th><th>Pick</th><th>Result</th><th>P&L $</th></tr>"
            f"{rows}</table>") if rows else ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>The Daily Card - Sports Edges</title>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=Inter:wght@400;600&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body>
<header><div class="inner">
<h1>The Daily <span>Card</span></h1>
<div class="rec"><div><b>{wins}-{losses}</b>record</div>
<div><b>{'+' if pnl>=0 else ''}{pnl:.2f}</b>P&L ($1 slips)</div>
<div><b>{len(shown)}</b>plays today</div></div>
<div class="upd">Scanned {now} - picks are suggestions, you place the bets.
{html.escape(note)}</div>
</div></header>
<div class="wrap">
<h2>Today's plays</h2>
{slips}
{combo}
{hist}






<div class="foot"><b>How to read a slip:</b> "Books say" is the de-vigged
consensus win probability from US sportsbooks (the sharpest public forecast
that exists). "Net edge" is that probability minus Kalshi's price minus
Kalshi's trading fee - the estimated profit per $1 contract if the books are
right. Only FULL-GAME moneyline markets are scanned; inning props, spreads
and player-movement markets are excluded on purpose. Slips under
+{SHOW_EDGE:.0f}c never make the card, and anything claiming more than
+{MAX_EDGE:.0f}c is treated as a bug and suppressed. The record above is
scored at $1 per slip. Every evaluated game is logged to sports_picks.csv,
shown or not, and every shown play is graded against final scores in
sports_results.csv.</div>
</div></body></html>"""


# ---------- main ----------
def main():
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    note = ""
    games = fetch_consensus()
    print(f"books: {len(games)} upcoming games with {MIN_BOOKS}+ book consensus")
    by_sport = fetch_kalshi_moneylines()
    if not any(by_sport.values()):
        note = "Kalshi moneyline markets unavailable this scan."

    shown = []
    todays_rows = []

    matched = 0
    suppressed = 0
    with appender(PICKS_CSV, PICKS_FIELDS, PICKS_LEGACY) as w:
        for g in games:
            mkts = by_sport.get(g["sport"], [])
            m, yes_team = match_market(g, mkts)
            if not m:
                print(f"no market matched: {g['game']}")
                continue
            matched += 1
            other = g["away"] if yes_team == g["home"] else g["home"]
            fair_yes = g["fair"][yes_team] * 100
            for action, team, opp, ask, fair in (
                    ("YES", yes_team, other, m["yes_ask"], fair_yes),
                    ("NO", other, yes_team, m["no_ask"], 100 - fair_yes)):
                if not ask or not (MIN_ASK <= ask <= MAX_ASK):
                    continue
                fee = fee_cents(ask)
                edge = round(fair - ask - fee, 1)
                too_big = edge > MAX_EDGE
                is_shown = (SHOW_EDGE <= edge <= MAX_EDGE)
                if too_big:
                    suppressed += 1
                    print(f"  !! SUPPRESSED {m['ticker']} {action} {team}: "
                          f"edge {edge:+.1f}c exceeds MAX_EDGE {MAX_EDGE}c. "
                          f"A real moneyline edge is never this big -- check "
                          f"the matcher before trusting this.")
                if edge >= 0:
                    why = (f"{g['n_books']} sportsbooks make {team} "
                           f"{fair:.0f}% to win this one, but the Kalshi "
                           f"crowd is only charging {ask:.0f}c. After the "
                           f"{fee:.0f}c fee that's {edge:+.1f}c of edge per "
                           f"contract - the books like this side more than "
                           f"the crowd does.")
                else:
                    why = (f"{g['n_books']} sportsbooks make {team} "
                           f"{fair:.0f}% to win this one and Kalshi charges "
                           f"{ask:.0f}c. After the {fee:.0f}c fee that's "
                           f"{edge:+.1f}c - no edge on this side.")
                if too_big:
                    why = ("SUPPRESSED: computed edge is implausibly large "
                           "for a moneyline, which means the market may be "
                           "mismatched. Not a play.")
                row = {"scanned_utc": stamp, "sport": g["sport"],
                       "game": g["game"],
                       "commence_utc": g["commence"].isoformat(),
                       "ticker": m["ticker"], "series": m["series"],
                       "action": action, "pick_team": team, "opponent": opp,
                       "ask_cents": round(ask, 1),
                       "fair_pct": round(fair, 1), "fee_cents": fee,
                       "edge_cents": edge, "n_books": g["n_books"],
                       "shown": "1" if is_shown else "0", "why": why}
                w.writerow(row)
                todays_rows.append(row)
       
                if is_shown:
                    shown.append(row)
    shown.sort(key=lambda r: -float(r["edge_cents"]))
    print(f"matched {matched} of {len(games)} games to moneyline markets")
    if suppressed:
        print(f"SUPPRESSED {suppressed} implausible edges (>{MAX_EDGE}c)")
    print(f"{len(shown)} plays make the card")
    if games and matched == 0:
        print("DEBUG - sample market texts from whitelisted series:")
        for label, mkts in by_sport.items():
            for m in mkts[:3]:
                print(f"  [{label}] ticker={m['ticker']!r} "
                      f"text={m['text'][:110]!r} yes_hint={m['yes_hint']!r}")

    all_picks = list(csv.DictReader(open(PICKS_CSV))) \
        if os.path.exists(PICKS_CSV) else []
    graded = grade(all_picks)
    print(f"graded {len(graded)} finished picks")
    results = list(csv.DictReader(open(RESULTS_CSV))) \
        if os.path.exists(RESULTS_CSV) else []

    with open(PAGE, "w") as f:
        f.write(build_page(shown, results, note, todays_rows))
    print(f"wrote {PAGE}")


if __name__ == "__main__":
    main()

 
