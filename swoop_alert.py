"""Weather-Bot repo: SWOOP ALERT (advisor only -- places NO bets).

Grades every open weather position against the thermometer and writes
swoop.html + swoop_log.csv.

AUDITED + REBUILT Aug 6 2026 -- the $60 Phoenix rules, all enforced:

1. FRESHNESS GATE. Every reading carries the observation's own age.
   A reading older than 60 minutes can NEVER produce a SWOOP tag --
   it degrades to VERIFY with "check weather.gov yourself." A number
   that looks current but isn't is how the $60 was lost.
2. PRICE CONTRADICTION KILL. If the board thinks a position is a
   SWOOP but the market prices that side under 40c, the market is
   saying the day is going the other way -- the tag is suppressed and
   the card says so. When the board and the money disagree, the money
   has better information.
3. NO SWOOP ON "OR BELOW". A YES cap-only bracket has no safe side:
   highs only rise, so it can always still climb out. AT RISK at best.
4. Past the cap on a YES cap-only = DEAD immediately (96.8 on a
   "96 or below" is over -- no rounding mercy, no hope text).
5. Removed "Your side value rising" -- it was a label wearing a
   measurement's clothes.
6. Cities come from the ticker via SERIES_TO_CITY (Kalshi omits city
   names from newer market titles); title matching is the fallback.
7. OVERSHOOT RISK (Aug 19 2026). A YES bracket whose cap the
   thermometer is within OVERSHOOT_GAP_F degrees of, during the
   station's local heating hours (~10am-6pm, longitude estimate --
   same convention as poller.py), gets a loud warning: highs only
   rise, so a winning-looking card can still get blown past. The
   card shows the gap to the cap, the reading's age, and what the
   side currently fetches on the market (the YES bid). The warning
   outranks a SWOOP tag -- a warning beats an invitation. A STALE
   reading near the cap is MORE dangerous, not less (the true temp
   may already be past the cap), so staleness never suppresses this
   tag. Advisory only: this board never trades or sells.

ALWAYS confirm on weather.gov before sizing up. This board is an
advisor. The Daily Climate Report is the judge.
"""

import base64, csv, html, json, os, re, time, urllib.request
from datetime import datetime, timedelta, timezone

from cities import CITY_TO_STATION, SERIES_TO_CITY, SITES
from csvio import appender

BASE = "https://api.elections.kalshi.com"
KEY_ID = os.environ["KALSHI_API_KEY_ID"].strip()
PAGE = "swoop.html"
LOG = "swoop_log.csv"
LOG_FIELDS = ["checked_utc", "ticker", "city", "side", "bracket",
              "observed_high", "obs_age_min", "market_cents", "status"]
# layout before obs_age_min was added mid-row (Aug 6 2026)
LOG_LEGACY = [["checked_utc", "ticker", "city", "side", "bracket",
               "observed_high", "market_cents", "status"]]
SWOOP_MAX_ASK = 80       # don't flag chases above this (cents)
SWOOP_MIN_ASK = 8        # below this the market says it already lost
LOCK_MAX_ASK = 95        # locked-win flag only if price still below this
SWOOP_EARLIEST_UTC = 20  # no gold tags before ~4pm ET / 1pm PT
MAX_OBS_AGE_MIN = 60     # readings older than this can never SWOOP
PRICE_CONTRADICTION = 40 # a "winning" side priced under this kills the tag
OVERSHOOT_GAP_F = 2.0    # obs within this many deg of a YES cap = risk
HEAT_START_LOCAL = 10    # station-local heating hours: 10am up to (but
HEAT_END_LOCAL = 18      # not including) 6pm, via the longitude estimate

# city -> UTC offset in hours (longitude estimate, same convention as
# poller.py -- good to about an hour, which is all a rough heating
# window needs)
CITY_OFFSET = {city: round(lon / 15.0)
               for _st, (city, _lat, lon) in SITES.items()}


def local_hour(city, now_utc):
    """The station's approximate local hour (0-23), or None if the
    city is unknown."""
    off = CITY_OFFSET.get(city)
    if off is None:
        return None
    return (now_utc + timedelta(hours=off)).hour


# ---------- kalshi auth ----------
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


def load_key():
    raw = os.environ["KALSHI_PRIVATE_KEY"].replace("\\n", "\n").strip()
    m = re.search(r"-----BEGIN ([A-Z ]+)-----(.*?)-----END \1-----",
                  raw, re.DOTALL)
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


# ---------- observed highs (with age) ----------
def latest_reading_ages(now):
    """city -> minutes since the station's newest successful reading in
    temps_log.csv. This is the SAME age the Station Board (index.html)
    shows. The daily high's own timestamp is NOT freshness: it marks when
    the day's peak was set, which is hours old by every afternoon even
    when the station reported minutes ago (the 162m-vs-41m bug, fixed
    Aug 21 2026). A fresh latest reading is what proves the observed high
    is still the running maximum."""
    ages = {}
    if not os.path.exists("temps_log.csv"):
        return ages
    with open("temps_log.csv") as f:
        for row in csv.DictReader(f):
            city = (row.get("city") or "").strip()
            v = (row.get("temp_f") or "").strip()
            if not city or not v or v == "ERROR":
                continue
            # file is append-ordered, so the last good row per city wins
            ot = (row.get("obs_time_utc") or row.get("utc_time") or "")
            try:
                dt = datetime.fromisoformat(ot.replace("Z", "+00:00"))
                ages[city] = int((now - dt).total_seconds() // 60)
            except (ValueError, TypeError):
                continue
    return ages


def observed_highs():
    """city -> (high_so_far_today, obs_age_minutes or None).

    The HIGH comes from daily_highs.csv. The AGE comes from the latest
    reading in temps_log.csv (see latest_reading_ages) -- never from the
    high's own timestamp. Falls back to the high row's timestamps only
    when the station has no readable row in temps_log.csv."""
    now = datetime.now(timezone.utc)
    reading_age = latest_reading_ages(now)
    highs = {}
    if not os.path.exists("daily_highs.csv"):
        return highs
    with open("daily_highs.csv") as f:
        for row in csv.DictReader(f):
            city = (row.get("city") or "").strip()
            d = (row.get("date") or "").strip()
            v = (row.get("high_f") or "").strip()
            if not city or not v:
                continue
            # keep today's row per the file's own (local) date; the file
            # holds one row per (date, station) so latest date wins
            try:
                t = float(v)
            except ValueError:
                continue
            prev = highs.get(city)
            if prev is None or d >= prev[2]:
                age = reading_age.get(city)
                if age is None:
                    ot = (row.get("obs_time_utc") or
                          row.get("last_update_utc") or "")
                    try:
                        dt = datetime.fromisoformat(
                            ot.replace("Z", "+00:00"))
                        age = int((now - dt).total_seconds() // 60)
                    except (ValueError, TypeError):
                        pass
                highs[city] = (t, age, d)
    return {c: (t, a) for c, (t, a, _d) in highs.items()}


def match_city(title, ticker=""):
    """Prefer the ticker's series prefix -- Kalshi omits the city from
    newer market titles. Title text is the fallback."""
    series = (ticker or "").split("-")[0].upper()
    if series in SERIES_TO_CITY:
        return SERIES_TO_CITY[series]
    t = " " + re.sub(r"[^a-z]+", " ", (title or "").lower()) + " "
    for city in CITY_TO_STATION:
        if city.lower() in t:
            return city
    for alias, city in (("nyc", "New York City"),
                        ("new york", "New York City"),
                        ("washington dc", "Washington DC"),
                        (" la ", "Los Angeles"),
                        (" sf ", "San Francisco"),
                        (" dc ", "Washington DC")):
        if alias in t:
            return city
    return None


# ---------- brackets ----------
def parse_bracket(sub):
    """(lo, hi) from a Kalshi subtitle: '88° to 89°', '98° or below',
    '99° or above'. (None, None) if unreadable."""
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


# ---------- grade one position ----------
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
            return "LOCKED", (f"High already hit {obs:.1f}\u00b0 - at/above "
                              f"the {lo:.0f}\u00b0 line. This YES cannot "
                              f"lose.")
        if inside:
            if lo is None:
                # cap-only "X or below": there is no safe side, ever.
                # (Past the cap is caught by `above` -> DEAD before here.)
                edge_txt = (" ONE TICK FROM DEAD." if obs >= hi - 0.5
                            else "")
                return "AT RISK", (f"Observed high {obs:.1f}\u00b0 is under "
                                   f"the {hi:.0f}\u00b0 cap, but highs only "
                                   f"rise - this can still climb out and "
                                   f"die. Never a swoop; there is no safe "
                                   f"side on an 'or below' bracket."
                                   + edge_txt)
            return "ON TRACK", (f"Observed high {obs:.1f}\u00b0 is inside "
                                f"the bracket. Wins if the heat stops here "
                                f"- watch for late overshoot.")
        need = (lo - obs) if lo is not None else 0
        return "NEEDS HEAT", (f"Needs about {need:.0f}\u00b0 more warming "
                              f"to enter.")
    else:  # no side
        if above:
            return "LOCKED", (f"High already {obs:.1f}\u00b0, past "
                              f"{hi:.0f}\u00b0. This NO is mathematically "
                              f"won.")
        if hi is None and lo is not None and obs >= lo - 0.5:
            return "DEAD", "Threshold already reached - this NO is done."
        if inside:
            return "IN DANGER", (f"Observed high {obs:.1f}\u00b0 is sitting "
                                 f"in the bracket. NO needs more heat to "
                                 f"escape upward.")
        return "ON TRACK", (f"High {obs:.1f}\u00b0 is below the bracket. "
                            f"NO wins unless the day climbs into it.")


# ---------- overshoot risk ----------
def overshoot_check(status, side, hi, obs, age, loc_hr, fetch_cents):
    """OVERSHOOT RISK gate for a graded YES position. Returns
    (flag, extra_note) -- extra_note is None when the tag does not
    apply and the caller should leave the card alone.

    Fires when a winning-looking YES card (ON TRACK or AT RISK) sits
    within OVERSHOOT_GAP_F degrees of its bracket cap during the
    station's local heating hours. Highs only rise, so the gap can
    only shrink. A stale or unknown-age reading makes it WORSE (the
    true temp may already be past the cap), so staleness never
    suppresses this warning. Advisory only -- alerts, never trades."""
    if side != "yes" or hi is None:
        return status, None
    if status not in ("ON TRACK", "AT RISK"):
        return status, None
    if loc_hr is None or not (HEAT_START_LOCAL <= loc_hr < HEAT_END_LOCAL):
        return status, None
    gap = float(hi) - obs
    if gap > OVERSHOOT_GAP_F:
        return status, None
    if gap > 0:
        gap_txt = (f"Observed high {obs:.1f}\u00b0 is only {gap:.1f}\u00b0 "
                   f"under the {hi:.0f}\u00b0 cap")
    else:
        gap_txt = (f"Instrument already reads {obs:.1f}\u00b0 - at or past "
                   f"the {hi:.0f}\u00b0 cap itself")
    age_txt = "of unknown age" if age is None else f"{age}m old"
    fetch_txt = f"{fetch_cents:.0f}c" if fetch_cents else "n/a"
    note = (f"{gap_txt}, and it is the heat of the day "
            f"(~{loc_hr}:00 local). Highs only rise - one more push "
            f"blows past this bracket. Reading is {age_txt}. Our side "
            f"currently fetches {fetch_txt} on the market.")
    if age is None or age > MAX_OBS_AGE_MIN:
        note += (" WARNING: that reading is STALE - the true temp may "
                 "already be past the cap. Check weather.gov NOW.")
    note += " Advisory only - this board never sells for you."
    return "OVERSHOOT RISK", note


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
.card.OVERSHOOTRISK{border-left-color:#e0483e}
.card.VERIFY{border-left-color:#8a6aa8}
.card.DEAD{border-left-color:#5c6670;opacity:.65}
.top{display:flex;justify-content:space-between;align-items:baseline}
.city{font:600 19px/1 "Barlow Condensed",sans-serif}
.badge{font:700 12px/1 sans-serif;letter-spacing:.1em;padding:4px 8px;
border-radius:3px;background:#2a323b}
.LOCKED .badge{background:#28a06c;color:#08130d}
.SWOOP .badge{background:#f3b53c;color:#191203}
.INDANGER .badge{background:#c2542f}
.ATRISK .badge{background:#c2542f}
.OVERSHOOTRISK .badge{background:#e0483e;color:#1a0505}
.VERIFY .badge{background:#8a6aa8}
.det{font-size:13px;color:#93a1ad;margin:6px 0}
.det b{color:#e8e4da}
.age{font-size:12px;color:#93a1ad}
.age.old{color:#c2542f;font-weight:600}
.note{font-size:14px;border-top:1px solid #2a323b;padding-top:8px;margin-top:8px}
.empty{border:1px dashed #2a323b;border-radius:8px;padding:24px;text-align:center;color:#93a1ad}
.foot{margin-top:22px;font-size:12.5px;color:#93a1ad;line-height:1.6}
"""


def build_page(cards, note, counts):
    now = datetime.now(timezone.utc).strftime("%a %b %d, %H:%M UTC")
    body = ""
    order = {"OVERSHOOT RISK": 0, "SWOOP": 1, "LOCKED": 2, "AT RISK": 3,
             "IN DANGER": 4, "VERIFY": 5, "ON TRACK": 6, "NEEDS HEAT": 7,
             "UNKNOWN": 8, "DEAD": 9}
    for c in sorted(cards, key=lambda c: order.get(c["flag"], 9)):
        cls = c["flag"].replace(" ", "")
        age_txt = ""
        if c["age"] is not None:
            old = " old" if c["age"] > MAX_OBS_AGE_MIN else ""
            age_txt = (f' &nbsp;|&nbsp; <span class="age{old}">reading '
                       f'{c["age"]}m old</span>')
        body += f"""
<div class="card {cls}"><div class="top">
<span class="city">{html.escape(c['city'])} &mdash; {html.escape(c['side'].upper())} {html.escape(c['bracket'])}</span>
<span class="badge">{html.escape(c['flag'])}</span></div>
<div class="det">Observed high so far: <b>{c['obs']:.1f}&deg;</b>{age_txt}
 &nbsp;|&nbsp; Market now: <b>{c['ask']}</b></div>
<div class="note">{html.escape(c['note'])}</div></div>"""
    if not body:
        body = ("<div class='empty'>No open same-day weather positions to "
                "grade right now. The board refreshes each scheduled "
                "pass.</div>")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Swoop Alert</title>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body><div class="wrap">
<h1>Swoop Alert</h1>
<div class="sub">Thermometer vs. market on the bot's open positions -
checked {now}. Graded {counts[0]} of {counts[1]} open weather positions.
{html.escape(note)}</div>
{body}
<div class="foot"><b>Read it like this:</b> daily highs only rise, so a
bracket the thermometer has passed is settled physics, not opinion.
<b>SWOOP</b> = the reading already agrees with the bot's side, the
reading is FRESH (under {MAX_OBS_AGE_MIN}m old), and the market still
sells it under {SWOOP_MAX_ASK}c. A stale reading or a price that
disagrees kills the tag. <b>AT RISK</b> = an 'or below' bracket that can
still climb out - never a swoop. <b>OVERSHOOT RISK</b> = the observed
high is within {OVERSHOOT_GAP_F:.0f}&deg; of a YES bracket's cap during
the station's heating hours (~10am-6pm local) - a winning-looking card
that one more push of heat kills. The card shows the gap to the cap,
the reading's age, and what the side currently fetches; a stale reading
makes it MORE urgent, not less. This board only warns - it never sells
for you. Always eyeball the station on
weather.gov before sizing up; this page is only as fresh as the last
poll. Chase nothing above {SWOOP_MAX_ASK}c; the meat is gone.</div>
</div></body></html>"""


# ---------- main ----------
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
        for _ in range(25):
            path = "/trade-api/v2/portfolio/positions?limit=200"
            if cursor:
                path += f"&cursor={cursor}"
            resp = ksigned(path)
            raw += resp.get("market_positions", [])
            cursor = resp.get("cursor") or ""
            if not cursor:
                break

        def qty_of(p):
            for fld in ("position_fp", "position", "quantity", "contracts",
                        "total_position"):
                try:
                    v = float(p.get(fld) or 0)
                except (TypeError, ValueError):
                    v = 0
                if v != 0:
                    return v
            return 0.0
        positions = [p for p in raw if p.get("ticker") and qty_of(p) != 0]
        print(f"positions API: {len(raw)} rows total, "
              f"{len(positions)} currently open")
    except Exception as e:
        positions, note = [], f"Positions unavailable this pass ({e})."
    print(f"{len(positions)} open positions")

    cards, rows = [], []
    weather_open = 0
    for p in positions:
        tick = p["ticker"]
        print(f"  SEEN {tick}")
        if "KXHIGH" not in tick or today_code not in tick:
            continue
        weather_open += 1
        side = "yes"
        for fld in ("position_fp", "position", "quantity", "contracts",
                    "total_position"):
            try:
                v = float(p.get(fld) or 0)
            except (TypeError, ValueError):
                v = 0
            if v != 0:
                side = "yes" if v > 0 else "no"
                break
        try:
            m = ksigned(f"/trade-api/v2/markets/{tick}").get("market", {})
        except Exception as e:
            print(f"  {tick}: market fetch failed ({e})")
            continue
        city = match_city(m.get("title", ""), tick)
        if not city or city not in highs:
            print(f"  {tick}: no city/obs match - NOT graded")
            continue
        obs, age = highs[city]
        sub = m.get("yes_sub_title") or m.get("subtitle") or ""
        lo, hi = parse_bracket(sub)
        print(f"  {tick}: sub={sub!r} lo={lo} hi={hi} obs={obs} "
              f"age={age}m")
        status, gnote = grade(side, lo, hi, obs)
        try:
            yes_ask = float(m.get("yes_ask_dollars") or 0) * 100
        except (TypeError, ValueError):
            yes_ask = 0
        try:
            yes_bid = float(m.get("yes_bid_dollars") or 0) * 100
        except (TypeError, ValueError):
            yes_bid = 0
        my_price = yes_ask if side == "yes" else \
            (100 - yes_ask if yes_ask else 0)
        flag = status

        # OVERSHOOT RISK outranks everything below: a warning beats an
        # invitation. Fetch price = the YES bid (what selling would
        # actually get, honestly quoted -- overshoot only fires on YES).
        oflag, onote = overshoot_check(status, side, hi, obs, age,
                                       local_hour(city, now), yes_bid)
        if onote is not None:
            flag = oflag
            gnote += " " + onote
        # SWOOP gate: fresh reading, right hour, sane price, and the
        # market must not contradict us.
        elif status == "ON TRACK" and side == "yes" and \
                SWOOP_MIN_ASK <= my_price <= SWOOP_MAX_ASK:
            if age is None or age > MAX_OBS_AGE_MIN:
                flag = "VERIFY"
                gnote += (f" Reading is "
                          f"{'unknown age' if age is None else str(age)+'m old'}"
                          f" - too old to trust for a swoop. Check "
                          f"weather.gov before any money moves.")
            elif my_price < PRICE_CONTRADICTION:
                gnote += (f" Market prices this side at only "
                          f"{my_price:.0f}c - the money says the day is "
                          f"going the other way. No swoop tag.")
            elif now.hour >= SWOOP_EARLIEST_UTC:
                flag = "SWOOP"
                gnote += (f" Market still under {SWOOP_MAX_ASK}c and the "
                          f"reading is {age}m fresh - this is the swoop "
                          f"window. Confirm on weather.gov first.")
            else:
                gnote += (" TOO EARLY to swoop - the day is still heating "
                          "and can climb past this bracket. Check the "
                          "afternoon passes.")
        if status == "LOCKED" and 0 < my_price <= LOCK_MAX_ASK:
            gnote += f" Market still pricing it at {my_price:.0f}c."

        bracket = (m.get("yes_sub_title") or m.get("subtitle")
                   or f"{lo}-{hi}").strip()
        cards.append({"city": city, "side": side, "bracket": bracket,
                      "obs": obs, "age": age, "flag": flag, "note": gnote,
                      "ask": f"{my_price:.0f}c" if my_price else "n/a"})
        rows.append({"checked_utc": stamp, "ticker": tick, "city": city,
                     "side": side, "bracket": bracket,
                     "observed_high": obs, "obs_age_min": age,
                     "market_cents": round(my_price, 1), "status": flag})
        print(f"{city} {side.upper()} {bracket}: {flag} (obs {obs:.1f}\u00b0)")

    if rows:
        with appender(LOG, LOG_FIELDS, LOG_LEGACY) as w:
            for r in rows:
                w.writerow(r)
    with open(PAGE, "w") as f:
        f.write(build_page(cards, note, (len(cards), weather_open)))
    print(f"graded {len(cards)} of {weather_open} open weather positions")
    print(f"wrote {PAGE}")


if __name__ == "__main__":
    main()



