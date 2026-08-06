"""Weather-Bot: market scanner. Reads tomorrow's calibrated ensemble,
prices every open bracket on the 20 verified city series, writes
edges.csv for the trader and the dashboards.

REBUILT Aug 5 2026 -- the one-scanner merge. This file replaces BOTH
scanner.py (was live) and "scanner 2.py" (was edited but never ran).
What changed and why:

1. NO DISCOVERY. The old live scanner auto-discovered KXHIGH* series
   and matched them to cities by name -- which is how ghost series
   (KXHIGHNYD, KXHIGHOU, KXHIGHTEMPDEN) got swept in. The verified
   CITIES dict in cities.py IS the whitelist. If Kalshi adds a city,
   it gets verified by hand and added there, never auto-matched.
2. CALIBRATION APPLIED EXACTLY ONCE. forecast.py already shifts and
   scales the members at write time (calibrate_members). The old live
   scanner then computed its OWN inline bias and corrected AGAIN --
   double-correcting every probability. This scanner treats stored
   members as final. Calibration numbers appear in edges.csv for
   display only.
3. NO INVENTED SPREADS. A city with no ensemble members for the target
   date is SKIPPED, loudly. Guessed confidence is how bad NOs look good.
4. THE NO FLOOR. Never sell (bet NO on) a bracket the model itself
   gives more than MAX_NO_MODEL_PROB percent -- selling the middle of
   your own forecast is how Aug 4's NOs all died.
5. Sanity cap on edges: anything past MAX_EDGE_SANITY is printed as
   suspicious and never flagged would_bet. Real weather edges exist,
   but a 40-point edge means a broken number, not free money.

Output columns are unchanged so "trader 2.py", index.html and the
dashboards keep working:
scanned_utc, city, market, subtitle, floor, cap, yes_ask, no_ask,
model_prob_pct, edge_yes, edge_no, bias_f, spread_scale, n_members,
would_bet
"""

import base64, csv, json, math, os, re, time, urllib.request
from datetime import datetime, timezone

from cities import CITIES, SERIES_TO_CITY
from calibration import compute_calibration

OUT = "edges.csv"

MIN_EDGE = 3.0            # cents of net edge to flag a bet
MIN_MODEL_PROB = 15.0     # never BUY a bracket the model gives under this
MAX_NO_MODEL_PROB = 25.0  # never SELL a bracket the model gives over this
MIN_COST, MAX_COST = 10, 90   # ignore extreme asks entirely
MAX_EDGE_SANITY = 30.0    # bigger than this = broken number, not edge

BASE = "https://api.elections.kalshi.com"
KEY_ID = os.environ["KALSHI_API_KEY_ID"].strip()


# ---------- kalshi auth (same pattern as the rest of the repo) ----------
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


# ---------- forecast members ----------
def load_members():
    """(date, city) -> [calibrated member highs]. Latest row per pair
    wins. ERROR/blank rows from old files are skipped."""
    out = {}
    if not os.path.exists("forecasts.csv"):
        return out
    with open("forecasts.csv") as f:
        for r in csv.DictReader(f):
            d = (r.get("forecast_date") or "").strip()
            city = (r.get("city") or "").strip()
            raw = (r.get("members") or "").strip()
            if not d or not city or not raw:
                continue
            try:
                members = [float(x) for x in raw.split("|") if x]
            except ValueError:
                continue
            if members:
                out[(d, city)] = members
    return out


# ---------- brackets ----------
def parse_bracket(m):
    """(lo, hi) for a market. Strike fields first; subtitle fallback for
    tail markets, which return empty strikes (the Aug 2 Austin lesson)."""
    lo, hi = m.get("floor_strike"), m.get("cap_strike")
    lo = float(lo) if lo not in (None, "") else None
    hi = float(hi) if hi not in (None, "") else None
    if lo is not None or hi is not None:
        return lo, hi
    s = (m.get("yes_sub_title") or m.get("subtitle") or "").lower()
    s = s.replace("\u00b0", " ")
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


def prob_in_bracket(members, lo, hi):
    """Fraction of ensemble members whose high lands in the bracket.
    Kalshi brackets are inclusive whole-degree bands; a member counts
    for bracket [lo, hi] if lo - 0.5 <= member < hi + 0.5 (open-ended
    for tails)."""
    n = 0
    for v in members:
        ok_lo = (lo is None) or (v >= lo - 0.5)
        ok_hi = (hi is None) or (v < hi + 0.5)
        if ok_lo and ok_hi:
            n += 1
    return n / len(members)


def fee_cents(price_cents):
    p = price_cents / 100.0
    return math.ceil(7 * p * (1 - p))


def cents(m, field):
    v = m.get(field)
    try:
        c = float(v) * 100
        return c if c > 0 else None
    except (TypeError, ValueError):
        return None


# ---------- main ----------
def main():
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    members_by = load_members()
    dates = sorted({d for d, _ in members_by})
    print(f"Ensemble dates loaded: {dates[-5:] if len(dates) > 5 else dates}")

    cal = compute_calibration()   # display only -- members are already corrected
    cal_by_city = {}
    from cities import STATIONS
    for sid, (bias, scale, n) in cal.items():
        cal_by_city[STATIONS[sid]] = (bias, scale)
        print(f"cal {STATIONS[sid]}: bias={bias:+.2f}F spread x{scale:.2f} "
              f"(n={n}) [applied at forecast time, shown for reference]")

    fields = ["scanned_utc", "city", "market", "subtitle", "floor", "cap",
              "yes_ask", "no_ask", "model_prob_pct", "edge_yes", "edge_no",
              "bias_f", "spread_scale", "n_members", "would_bet"]
    new = not os.path.exists(OUT)
    rows_written = 0
    with open(OUT, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new:
            w.writeheader()

        for series, (city, _station, _lat, _lon, _v) in CITIES.items():
            try:
                data = ksigned(f"/trade-api/v2/markets?series_ticker={series}"
                               f"&status=open&limit=200")
            except Exception as e:
                print(f"{city}: markets fetch failed ({e})")
                continue
            mkts = data.get("markets", [])
            print(f"{city}: {len(mkts)} open markets")

            for m in mkts:
                tick = m.get("ticker", "")
                dm = re.search(r"-(\d{2}[A-Z]{3}\d{2})-", tick)
                if not dm:
                    continue
                try:
                    mdate = datetime.strptime(
                        dm.group(1), "%y%b%d").date().isoformat()
                except ValueError:
                    continue
                members = members_by.get((mdate, city))
                if not members:
                    print(f"  SKIP {tick}: no ensemble members for "
                          f"{city} {mdate} - refusing to invent a spread")
                    continue

                lo, hi = parse_bracket(m)
                if lo is None and hi is None:
                    print(f"  SKIP {tick}: bracket unreadable")
                    continue

                yes_ask = cents(m, "yes_ask_dollars")
                if yes_ask is None:
                    yes_ask = cents(m, "yes_ask")
                no_ask = cents(m, "no_ask_dollars")
                if no_ask is None:
                    no_ask = cents(m, "no_ask")

                p = prob_in_bracket(members, lo, hi)
                p_pct = round(p * 100, 1)

                edge_yes = edge_no = ""
                would = ""
                if yes_ask and MIN_COST <= yes_ask <= MAX_COST:
                    ey = round(p_pct - yes_ask - fee_cents(yes_ask), 1)
                    edge_yes = ey
                    if (ey >= MIN_EDGE and p_pct >= MIN_MODEL_PROB
                            and ey <= MAX_EDGE_SANITY):
                        would = "YES"
                    elif ey > MAX_EDGE_SANITY:
                        print(f"  !! SUSPICIOUS {tick} YES edge {ey:+.1f}c "
                              f"- too big to be real, not flagged")
                if no_ask and MIN_COST <= no_ask <= MAX_COST:
                    en = round((100 - p_pct) - no_ask - fee_cents(no_ask), 1)
                    edge_no = en
                    if en >= MIN_EDGE and en <= MAX_EDGE_SANITY:
                        if p_pct > MAX_NO_MODEL_PROB:
                            print(f"  SKIP {tick} NO: model gives bracket "
                                  f"{p_pct:.0f}% (> {MAX_NO_MODEL_PROB:.0f}%)"
                                  f" - not selling our own forecast")
                        elif not would:   # one side per market, best first
                            would = "NO"
                    elif en > MAX_EDGE_SANITY:
                        print(f"  !! SUSPICIOUS {tick} NO edge {en:+.1f}c "
                              f"- too big to be real, not flagged")

                bias, scale = cal_by_city.get(city, (0.0, 2.5))
                w.writerow({"scanned_utc": stamp, "city": city,
                            "market": tick,
                            "subtitle": m.get("yes_sub_title")
                                        or m.get("subtitle") or "",
                            "floor": "" if lo is None else lo,
                            "cap": "" if hi is None else hi,
                            "yes_ask": "" if yes_ask is None
                                       else round(yes_ask, 1),
                            "no_ask": "" if no_ask is None
                                      else round(no_ask, 1),
                            "model_prob_pct": p_pct,
                            "edge_yes": edge_yes, "edge_no": edge_no,
                            "bias_f": bias, "spread_scale": scale,
                            "n_members": len(members),
                            "would_bet": would})
                rows_written += 1

    print(f"Scan complete. {rows_written} rows written.")


if __name__ == "__main__":
    main()
