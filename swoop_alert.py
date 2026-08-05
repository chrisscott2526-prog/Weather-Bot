"""Weather-Bot repo: SWOOP ALERT (advisor only -- places NO bets).

Chris's edge, automated: by afternoon the official thermometer has
already written part of the answer. Daily highs only go UP. So:
  - A bracket BELOW today's observed high is DEAD for YES and
    mathematically LOCKED for NO.
  - A bracket CONTAINING the observed high is "winning if the day
    ended now" for YES.
  - A bracket ABOVE it still NEEDS HEAT.

Each run this script:
  1. Reads today's observed high per city from the poller's own logs
     (temps_log.csv / daily_highs.csv -- columns sniffed defensively).
  2. Pulls the account's open positions from Kalshi, keeps today's
     weather markets, fetches each market's bracket + live price.
  3. Grades every position: LOCKED / ON TRACK / NEEDS HEAT /
     IN DANGER / DEAD, flags SWOOP candidates, writes swoop.html
     and appends swoop_log.csv.

ALWAYS confirm on weather.gov before sizing up. Alerts are only as
fresh as the poller's last pass.
"""

import base64, csv, html, json, os, re, time, urllib.request
from datetime import datetime, timezone
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from cities import CITY_TO_STATION, SERIES_TO_CITY

BASE = "https://api.elections.kalshi.com"
KEY_ID = os.environ["KALSHI_API_KEY_ID"].strip()
PAGE = "swoop.html"
LOG = "swoop_log.csv"
SWOOP_MAX_ASK = 80    # don't flag chases above this (cents)
SWOOP_MIN_ASK = 8     # below this the market says it already lost

LOCK_MAX_ASK = 95     # locked-win flag only if price still below this
SWOOP_EARLIEST_UTC = 20   # no gold tags before ~4pm ET / 1pm PT --
                          # a morning reading inside a bracket means
                          # nothing; the day is still heating.


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
    req = urllib.request.Request(BASE + path, headers={
        "KALSHI-ACCESS-KEY": KEY_ID,
        "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode(),
        "KALSHI-ACCESS-TIMESTAMP": ts,
        "User-Agent": "weather-bot-personal"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


# ---------- observed highs from the poller's own logs ----------
def _col(fields, *cands):
    for c in cands:
        for f in (fields or []):
            if c in f.lower():
                return f
    return None

def observed_highs():
    """{city: high_so_far_today} from daily_highs.csv + temps_log.csv."""
    today = datetime.now(timezone.utc).date().isoformat()
    highs = {}
    for fname in ("daily_highs.csv", "temps_log.csv"):
        if not os.path.exists(fname):
            continue
        with open(fname) as f:
            rd = csv.DictReader(f)
            city_c = _col(rd.fieldnames, "city", "station")
            date_c = _col(rd.fieldnames, "date", "time", "utc", "stamp")
            temp_c = _col(rd.fieldnames, "high", "temp")
            if not (city_c and date_c and temp_c):
                print(f"{fname}: couldn't identify columns {rd.fieldnames}")
                continue
            for row in rd:
                if today not in (row.get(date_c) or ""):
                    continue
                try:
                    t = float(row.get(temp_c))
                except (TypeError, ValueError):
                    continue
                c = row.get(city_c)
                if c and (c not in highs or t > highs[c]):
                    highs[c] = t
    return highs

def match_city(title, ticker=""):
    """Prefer the ticker's series prefix -- Kalshi omits the city from the
    title on the newer KXHIGHT* markets. Fall back to the title text."""
    series = (ticker or "").split("-")[0].upper()
    if series in SERIES_TO_CITY:
        return SERIES_TO_CITY[series]
    t = " " + re.sub(r"[^a-z]+", " ", (title or "").lower()) + " "
    for city in CITY_TO_STATION:
        if city.lower() in t:
            return city
    for alias, city in (("nyc", "New York City"), ("new york", "New York City"),
                        ("washington dc", "Washington DC"),
                        (" la ", "Los Angeles"), (" sf ", "San Francisco"),
                        (" dc ", "Washington DC")):
        if alias in t:
            return city
    return None



# ---------- grade one position ----------

def parse_bracket(sub):
    """Read (lo, hi) from a Kalshi subtitle: '88° to 89°',
    '98° or below', '99° or above'. (None, None) if unreadable."""
    s = (sub or "").lower().replace("\u00b0", " ")
    nums = re.findall(r"-?\d+(?:\.\d+)?", s)
    if not nums:
        return None, None
    if " to " in s and len(nums) >= 2:
        return float(nums[0]), float(nums[1])
    if "below" in s or "under" in s or "less" in s:
        return None, float(nums[0])
    if "above" in s or "over" in s or "greater" in s or "higher" in s:
        return float(nums[0]), None
    return None, None


def grade(side, lo, hi, obs):
    """Return (status, note). Daily highs only rise: obs is a floor on
    the final high. lo/hi may be None for tail markets."""
    lo = float(lo) if lo not in (None, "") else None
    hi = float(hi) if hi not in (None, "") else None
    if lo is None and hi is None:
        return "UNKNOWN", ("Bracket could not be read from this market. "
                           "NOT graded - check weather.gov yourself.")
    above = hi is not None and obs > hi + 0.5
    below = lo is not None and obs < lo - 0.5
    inside = not above and not below
    if side == "yes":
        if above:
            return "DEAD", "Thermometer already blew past this bracket."
        if hi is None and lo is not None and obs >= lo - 0.5:
            return "LOCKED", (f"High already hit {obs:.0f}\u00b0 - at/above the "
                              f"{lo:.0f}\u00b0 line. This YES cannot lose.")
        if inside:
            if lo is None:
                return "AT RISK", (f"Observed high {obs:.0f}\u00b0 is under the "
                                   f"{hi:.0f}\u00b0 cap, but highs only rise - "
                                   "this can still climb out and die. Never a "
                                   "swoop; there is no safe side on an "
                                   "'or below' bracket.")
            return "ON TRACK", (f"Observed high {obs:.0f}\u00b0 is inside the "
                                "bracket. Wins if the heat stops here - "
                                "watch for late overshoot.")

        need = (lo - obs) if lo is not None else 0
        return "NEEDS HEAT", f"Needs about {need:.0f}\u00b0 more warming to enter."
    else:  # no side
        if above:
            return "LOCKED", (f"High already {obs:.0f}\u00b0, past {hi:.0f}\u00b0. "
                              "This NO is mathematically won.")
        if hi is None and lo is not None and obs >= lo - 0.5:
            return "DEAD", "Threshold already reached - this NO is done."
        if inside:
            return "IN DANGER", (f"Observed high {obs:.0f}\u00b0 is sitting in "
                                 "the bracket. NO needs more heat to "
                                 "escape upward.")
        return "ON TRACK", (f"High {obs:.0f}\u00b0 is below the bracket. NO wins "
                            "unless the day climbs into it.")



# ---------- page ----------
CSS = """
*{margin:0;padding:0;box-sizing:border-box}
body{background:#101418;color:#e8e4da;font:16px/1.5 -apple-system,system-ui,sans-serif}
.wrap{max-width:640px;margin:0 auto;padding:20px 14px 60px}
h1{font:700 30px/1.1 "Barlow Condensed",Impact,sans-serif;letter-spacing:.04em;
text-transform:uppercase;color:#f3b53c;margin-bottom:4px}
.sub{color:#93a1ad;font-size:13px;margin-bottom:20px}
.card{background:#1a2027;border:1px solid #2a323b;border-radius:8px;
padding:14px 16px;margin-bottom:12px;border-left:5px solid #2a323b}
.card.LOCKED{border-left-color:#28a06c}.card.SWOOP{border-left-color:#f3b53c}
.card.ONTRACK{border-left-color:#3f7fbf}.card.INDANGER{border-left-color:#c2542f}
.card.ATRISK{border-left-color:#c2542f}
.ATRISK .badge{background:#c2542f}


.card.DEAD{border-left-color:#5c6670;opacity:.65}
.top{display:flex;justify-content:space-between;align-items:baseline}
.city{font:600 19px/1 "Barlow Condensed",sans-serif}
.badge{font:700 12px/1 sans-serif;letter-spacing:.1em;padding:4px 8px;
border-radius:3px;background:#2a323b}
.LOCKED .badge{background:#28a06c;color:#08130d}
.SWOOP .badge{background:#f3b53c;color:#191203}
.INDANGER .badge{background:#c2542f}
.det{font-size:13px;color:#93a1ad;margin:6px 0}
.det b{color:#e8e4da}
.note{font-size:14px;border-top:1px solid #2a323b;padding-top:8px;margin-top:8px}
.empty{border:1px dashed #2a323b;border-radius:8px;padding:24px;text-align:center;color:#93a1ad}
.foot{margin-top:22px;font-size:12.5px;color:#93a1ad;line-height:1.6}
"""

def build_page(cards, note):
    now = datetime.now(timezone.utc).strftime("%a %b %d, %H:%M UTC")
    body = ""
    order = {"SWOOP": 0, "LOCKED": 1, "AT RISK": 2, "IN DANGER": 3,
             "ON TRACK": 4, "NEEDS HEAT": 5, "DEAD": 6}

    for c in sorted(cards, key=lambda c: order.get(c["flag"], 9)):
        cls = c["flag"].replace(" ", "")
        body += f"""
<div class="card {cls}"><div class="top">
<span class="city">{html.escape(c['city'])} — {html.escape(c['side'].upper())} {html.escape(c['bracket'])}</span>
<span class="badge">{html.escape(c['flag'])}</span></div>
<div class="det">Observed high so far: <b>{c['obs']:.0f}°</b> &nbsp;|&nbsp;
Market now: <b>{c['ask']}</b> &nbsp;|&nbsp; Your side value rising: <b>{c['dir']}</b></div>
<div class="note">{html.escape(c['note'])}</div></div>"""
    if not body:
        body = ("<div class='empty'>No open same-day weather positions to "
                "grade right now. The board refreshes each scheduled pass.</div>")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Swoop Alert</title>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body><div class="wrap">
<h1>Swoop Alert</h1>
<div class="sub">Thermometer vs. market on the bot's open positions —
checked {now}. {html.escape(note)}</div>
{body}
<div class="foot"><b>Read it like this:</b> daily highs only rise, so a
bracket the thermometer has passed is settled physics, not opinion.
<b>SWOOP</b> = the reading already agrees with the bot's side and the
market is still selling it under {SWOOP_MAX_ASK}c. <b>LOCKED</b> = the
outcome is mathematically decided. Always eyeball the station on
weather.gov before sizing up — this page is only as fresh as the last
poll. Chase nothing above {SWOOP_MAX_ASK}c; the meat is gone.</div>
</div></body></html>"""


def main():
    now = datetime.now(timezone.utc)
    stamp = now.isoformat(timespec="seconds")
    today_code = now.strftime("%y%b%d").upper()
    note = ""
    highs = observed_highs()
    print(f"observed highs for {len(highs)} cities")

    try:
        raw = []
        cursor = ""
        for _ in range(25):                     # turn every page
            path = "/trade-api/v2/portfolio/positions?limit=200"
            if cursor:
                path += f"&cursor={cursor}"
            resp = ksigned(path)
            raw += resp.get("market_positions", [])
            cursor = resp.get("cursor") or ""
            if not cursor:
                break
        def qty_of(p):
            for f in ("position_fp", "position", "quantity", "contracts",
                      "total_position"):
                try:
                    v = float(p.get(f) or 0)
                except (TypeError, ValueError):
                    v = 0
                if v != 0:
                    return v
            return 0.0
        positions = [p for p in raw if p.get("ticker") and qty_of(p) != 0]
        print(f"positions API: {len(raw)} rows total, "
              f"{len(positions)} currently open")
        if raw and not positions:
            print("DEBUG sample row:", json.dumps(raw[0])[:400])
    except Exception as e:
        positions, note = [], f"Positions unavailable this pass ({e})."
    print(f"{len(positions)} open positions")

    cards, rows = [], []
    for p in positions:
        tick = p["ticker"]
        print(f"  SEEN {tick}")

        if "KXHIGH" not in tick or today_code not in tick:
            continue
        side = "yes"
        for f in ("position_fp", "position", "quantity", "contracts",
                  "total_position"):
            try:
                v = float(p.get(f) or 0)
            except (TypeError, ValueError):
                v = 0
            if v != 0:
                side = "yes" if v > 0 else "no"
                break
        try:
            m = ksigned(f"/trade-api/v2/markets/{tick}").get("market", {})
        except Exception as e:
            print(f"{tick}: market fetch failed ({e})")
            continue
        
 
        city = match_city(m.get("title", ""), tick)
        if not city or city not in highs: 
            continue
        obs = highs[city]
        lo, hi = m.get("floor_strike"), m.get("cap_strike")
        sub = m.get("yes_sub_title") or m.get("subtitle") or ""
        if lo in (None, "") and hi in (None, ""):
            lo, hi = parse_bracket(sub)
        print(f"  {tick}: sub={sub!r} lo={lo} hi={hi} obs={obs}")

        status, gnote = grade(side, lo, hi, obs)
        try:
            yes_ask = float(m.get("yes_ask_dollars") or 0) * 100
        except (TypeError, ValueError):
            yes_ask = 0
        my_price = yes_ask if side == "yes" else (100 - yes_ask if yes_ask else 0)
        flag = status
        if status == "ON TRACK" and side == "yes" and SWOOP_MIN_ASK <= my_price <= SWOOP_MAX_ASK:

            if now.hour >= SWOOP_EARLIEST_UTC:
                flag, gnote = "SWOOP", (gnote + " Market still under "
                                        f"{SWOOP_MAX_ASK}c — this is the "
                                        "swoop window.")
            else:
                gnote += (" TOO EARLY to swoop — the day is still heating "
                          "and can climb past this bracket. Check the "
                          "afternoon passes.")
        if status == "LOCKED" and 0 < my_price <= LOCK_MAX_ASK:
            gnote += f" Market still pricing it at {my_price:.0f}c."
        bracket = (m.get("yes_sub_title") or m.get("subtitle") or
                   f"{lo}-{hi}").strip()
        cards.append({"city": city, "side": side, "bracket": bracket,
                      "obs": obs, "flag": flag, "note": gnote,
                      "ask": f"{my_price:.0f}c" if my_price else "n/a",
                      "dir": "your side" if side == "yes" else "NO side"})
        rows.append({"checked_utc": stamp, "ticker": tick, "city": city,
                     "side": side, "bracket": bracket, "observed_high": obs,
                     "market_cents": round(my_price, 1), "status": flag})
        print(f"{city} {side.upper()} {bracket}: {flag} (obs {obs:.0f}°)")

    if rows:
        new = not os.path.exists(LOG)
        with open(LOG, "a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            if new:
                w.writeheader()
            for r in rows:
                w.writerow(r)
    with open(PAGE, "w") as f:
        f.write(build_page(cards, note))
    print(f"wrote {PAGE}")


if __name__ == "__main__":
    main()



