"""Weather-Bot: market scanner -- PICK-FIRST edition.

Chris's rule, Aug 6 2026, replacing edge-ranking for good:

  1. PICK THE BRACKET. For each city, the ensemble votes: the bracket
     with the most member votes is the pick. Full stop. Price plays no
     part in choosing it.
  2. DON'T OVERPAY. If the pick's price is inside the band, flag the
     buy. If it's too expensive (or suspiciously cheap), NO BUY for
     that city that day. No substitutes, no falling back to a cheaper
     neighbor -- that discount-shopping is exactly what a week of
     babysitting proved wrong: the cheap second-favorite loses, and
     rolling out of it at 2pm pays a sell loss, a premium re-entry,
     and two fees to end up where a clean first buy would have been.

Why the old edge rule died: it bought whichever bracket had the
biggest (model% - price - fee), which systematically chose the
SECOND-most-likely bracket at a discount over the most-likely at fair
price. Right neighborhood, wrong house, over and over. The model's
job is the bracket. The price is only a gate.

Edge numbers are still COMPUTED and LOGGED for every bracket -- they
decide nothing. They exist so results.csv can grade the old rule's
hypothetical picks against this rule's real ones (edge_pick column).

KEPT GUARDS (not edge-hunting -- seatbelts, all paid for in losses):
  - Cost band MIN_PICK_COST..MAX_PICK_COST: never pay 96c to win 4,
    never buy a pick the market prices near zero.
  - MIN_PICK_PROB: if even the top bracket is a weak favorite, the
    day is genuinely uncertain -- no bet beats a coin flip.
  - No ensemble members = SKIP, loudly. Never invent confidence.
  - Whitelist only (cities.py). No discovery, no ghost series.
  - Calibration applied exactly once, at forecast time. Reported
    here for display only.

Output columns unchanged plus two new ones (pick, edge_pick) so
trader.py and the dashboards keep working. would_bet is YES on the
picked bracket when the price gate passes, else empty. The NO side is
no longer traded by this scanner at all. One city, one pick, one buy
or no buy.
"""

import base64, csv, json, math, os, re, time, urllib.request
from datetime import datetime, timezone

from cities import CITIES, STATIONS
from calibration import compute_calibration
from csvio import appender

OUT = "edges.csv"
FIELDS = ["scanned_utc", "city", "market", "subtitle", "floor", "cap",
          "yes_ask", "no_ask", "model_prob_pct", "edge_yes", "edge_no",
          "bias_f", "spread_scale", "n_members", "pick", "edge_pick",
          "would_bet"]

# ---- THE TWO RULES' NUMBERS ----
MAX_PICK_COST = 68.0   # past this, no buy for that city today
MIN_PICK_COST = 8.0    # under this the market is screaming we're wrong
MIN_PICK_PROB = 35.0   # top bracket weaker than this = day too uncertain

BASE = "https://api.elections.kalshi.com"
KEY_ID = os.environ["KALSHI_API_KEY_ID"].strip()


# ---------- kalshi auth (same pattern repo-wide) ----------
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
    tail markets, which return empty strikes."""
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
    """Fraction of ensemble members landing in the bracket. A member
    counts for [lo, hi] if lo - 0.5 <= member < hi + 0.5 (open-ended
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

    cal = compute_calibration()   # display only
    cal_by_city = {}
    for sid, (bias, scale, n) in cal.items():
        cal_by_city[STATIONS[sid]] = (bias, scale)
        print(f"cal {STATIONS[sid]}: bias={bias:+.2f}F spread x{scale:.2f} "
              f"(n={n}) [applied at forecast time]")

    rows_written = 0
    buys = 0
    with appender(OUT, FIELDS) as w:
        for series, (city, _station, _lat, _lon, _v) in CITIES.items():
            try:
                data = ksigned(f"/trade-api/v2/markets?series_ticker={series}"
                               f"&status=open&limit=200")
            except Exception as e:
                print(f"{city}: markets fetch failed ({e})")
                continue
            mkts = data.get("markets", [])
            print(f"{city}: {len(mkts)} open markets")

            by_date = {}
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
                by_date.setdefault(mdate, []).append(m)

            for mdate, board in sorted(by_date.items()):
                members = members_by.get((mdate, city))
                if not members:
                    print(f"  SKIP {city} {mdate}: no ensemble members "
                          f"- refusing to invent a spread")
                    continue

                # RULE 1: pick the bracket -- most member votes wins
                scored = []
                for m in board:
                    lo, hi = parse_bracket(m)
                    if lo is None and hi is None:
                        continue
                    p = prob_in_bracket(members, lo, hi)
                    scored.append((p, m, lo, hi))
                if not scored:
                    continue
                scored.sort(key=lambda x: -x[0])
                top_p, top_m = scored[0][0], scored[0][1]
                pick_tick = top_m.get("ticker", "")

                # old rule's hypothetical, logged for the scoreboard
                edge_pick = ""
                best_e = None
                for p, m, lo, hi in scored:
                    ask = cents(m, "yes_ask_dollars") or cents(m, "yes_ask")
                    if not ask:
                        continue
                    e = p * 100 - ask - fee_cents(ask)
                    if best_e is None or e > best_e:
                        best_e, edge_pick = e, m.get("ticker", "")

                for p, m, lo, hi in scored:
                    tick = m.get("ticker", "")
                    yes_ask = cents(m, "yes_ask_dollars") or \
                        cents(m, "yes_ask")
                    no_ask = cents(m, "no_ask_dollars") or \
                        cents(m, "no_ask")
                    p_pct = round(p * 100, 1)
                    ey = en = ""
                    if yes_ask:
                        ey = round(p_pct - yes_ask - fee_cents(yes_ask), 1)
                    if no_ask:
                        en = round((100 - p_pct) - no_ask
                                   - fee_cents(no_ask), 1)

                    would = ""
                    is_pick = (tick == pick_tick)
                    if is_pick:
                        pct = round(top_p * 100, 1)
                        if pct < MIN_PICK_PROB:
                            print(f"  NO BUY {city} {mdate}: top bracket "
                                  f"only {pct:.0f}% - day too uncertain")
                        elif not yes_ask:
                            print(f"  NO BUY {city} {mdate}: pick {tick} "
                                  f"has no ask price")
                        elif yes_ask > MAX_PICK_COST:
                            print(f"  NO BUY {city} {mdate}: pick {tick} "
                                  f"costs {yes_ask:.0f}c (> "
                                  f"{MAX_PICK_COST:.0f}c cap) - moving on")
                        elif yes_ask < MIN_PICK_COST:
                            print(f"  NO BUY {city} {mdate}: pick {tick} "
                                  f"at {yes_ask:.0f}c - market says we're "
                                  f"wrong, believe it")
                        else:
                            would = "YES"
                            buys += 1
                            print(f"  BUY {city} {mdate}: {tick} "
                                  f"({pct:.0f}% of members) @ "
                                  f"{yes_ask:.0f}c")

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
                                "edge_yes": ey, "edge_no": en,
                                "bias_f": bias, "spread_scale": scale,
                                "n_members": len(members),
                                "pick": "1" if is_pick else "",
                                "edge_pick": "1" if tick == edge_pick
                                             else "",
                                "would_bet": would})
                    rows_written += 1

    print(f"Scan complete. {rows_written} rows, {buys} buys flagged.")


if __name__ == "__main__":
    main()
