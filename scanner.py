"""Weather-Bot: Kalshi market scanner v3 (READ-ONLY).

Changes vs v2:
  1. CALIBRATION IS NOW IN THE LOOP. Learns a per-city bias and
     spread inflation from forecasts.csv vs daily_highs.csv and
     applies it to ensemble members before computing probabilities.
  2. NO-side edges. Logs edge_no and can flag would_bet = NO.
  3. Fee-aware. Edges are net of Kalshi's taker fee, so MIN_EDGE
     means real expected value, not gross.
  4. edges.csv schema changed; an old-schema file is rotated to
     edges_v1.csv automatically on first run.

Places NO orders. trader.py v3 consumes this output.
"""

import base64, csv, json, math, os, re, time, urllib.parse, urllib.request
from collections import defaultdict
from datetime import datetime, timezone, date
from statistics import mean, pstdev
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

BASE = "https://api.elections.kalshi.com"
KEY_ID = os.environ["KALSHI_API_KEY_ID"].strip()

from cities import SERIES_TO_CITY, CITY_TO_STATION

def ensembles_by_date():
    """{(city, 'YYYY-MM-DD'): [member temps]} - HEADER-AGNOSTIC.
    forecasts.csv may predate the 'members' column, so we find the
    date / city / members fields in each row by content instead of
    trusting the header. Last row wins per (city, date)."""
    os.system("git pull --rebase --quiet 2>/dev/null")
    ens = {}
    if not os.path.exists("forecasts.csv"):
        return ens
    known = set(CITY_TO_STATION)
    with open("forecasts.csv") as f:
        for row in csv.reader(f):
            d = city = members = None
            for cell in row:
                cell = (cell or "").strip()
                if d is None and re.fullmatch(r"\d{4}-\d{2}-\d{2}", cell):
                    d = cell
                elif cell in known:
                    city = cell
                elif "|" in cell:
                    try:
                        m = [float(x) for x in cell.split("|") if x]
                        if m:
                            members = m
                    except ValueError:
                        pass
            if d and city and members:
                ens[(city, d)] = members
    return ens

VERIFIED = {"KXHIGHNY", "KXHIGHMIA", "KXHIGHDEN", "KXHIGHLAX",
            "KXHIGHPHIL", "KXHIGHAUS", "KXHIGHCHI"}  # known-good 7

def _match_city(title):
    """Map a series/market title like 'Highest temperature in NYC
    today?' to one of our 20 city names."""
    t = " " + re.sub(r"[^a-z]+", " ", (title or "").lower()) + " "
    for city in CITY_TO_STATION:
        if " " + city.lower() + " " in t or city.lower() in t:
            return city
    for alias, city in (("nyc", "New York City"),
                        ("new york", "New York City"),
                        ("washington d c", "Washington DC"),
                        ("washington dc", "Washington DC"),
                        (" la ", "Los Angeles"),
                        (" sf ", "San Francisco"),
                        (" dc ", "Washington DC")):
        if alias in t:
            return city
    return None

def discover_series():
    """Find every live KXHIGH* series and map ticker -> city by the
    series TITLE, so wrong ticker guesses fix themselves. Falls back
    to the static cities.py list if the API misbehaves."""
    series = {}
    try:
        q = urllib.parse.quote("Climate and Weather")
        data = signed_get(f"/trade-api/v2/series/?category={q}")
        for s in data.get("series", []):
            tick = s.get("ticker") or ""
            if not tick.startswith("KXHIGH"):
                continue
            city = _match_city(s.get("title", ""))
            if city:
                series[tick] = city
                print(f"discovered {tick} -> {city}")
            else:
                print(f"KXHIGH series {tick} "
                      f"({s.get('title')!r}) - no city match")
    except Exception as e:
        print(f"series endpoint failed ({e})")
    # always keep the verified originals
    for tick in VERIFIED:
        series.setdefault(tick, SERIES_TO_CITY[tick])
    if len(series) <= len(VERIFIED):
        print("discovery added nothing; also trying cities.py guesses")
        for tick, city in SERIES_TO_CITY.items():
            series.setdefault(tick, city)
    return series


MIN_EDGE = 8.0            # NET edge (after fees) required, in cents
MIN_ASK, MAX_ASK = 3, 70  # price window for either side
MIN_MEMBERS = 10          # skip prob if fewer ensemble members
CAL_MIN_SAMPLES = 8       # matched days needed before we trust calibration
BIAS_CLAMP = 4.0          # max abs bias correction, deg F
SPREAD_MIN, SPREAD_MAX = 1.0, 2.0
OUT = "edges.csv"
HEADER = ["scanned_utc", "city", "market", "subtitle", "floor", "cap",
          "yes_ask", "no_ask", "model_prob_pct", "edge_yes", "edge_no",
          "would_bet", "bias_f", "spread_scale", "n_members"]


# ---------- auth (unchanged) ----------

def load_key():
    raw = os.environ["KALSHI_PRIVATE_KEY"].replace("\\n", "\n").strip()
    m = re.search(r"-----BEGIN ([A-Z ]+)-----(.*?)-----END \1-----",
                  raw, re.DOTALL)
    if not m:
        raise ValueError("No BEGIN/END block found in KALSHI_PRIVATE_KEY")
    label, body = m.group(1), m.group(2)
    b64 = re.sub(r"[^A-Za-z0-9+/=]", "", body)
    lines = [b64[i:i + 64] for i in range(0, len(b64), 64)]
    pem = (f"-----BEGIN {label}-----\n" + "\n".join(lines)
           + f"\n-----END {label}-----\n").encode()
    return serialization.load_pem_private_key(pem, password=None)

key = load_key()

def signed_get(path):
    ts = str(int(time.time() * 1000))
    sig = key.sign((ts + "GET" + path.split("?")[0]).encode(),
                   padding.PSS(mgf=padding.MGF1(hashes.SHA256()),
                               salt_length=padding.PSS.DIGEST_LENGTH),
                   hashes.SHA256())
    req = urllib.request.Request(BASE + path, headers={
        "KALSHI-ACCESS-KEY": KEY_ID,
        "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode(),
        "KALSHI-ACCESS-TIMESTAMP": ts,
        "User-Agent": "weather-bot-personal",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


# ---------- helpers ----------

def cents(m, field):
    v = m.get(field)
    if v in (None, ""):
        return None
    try:
        c = float(v) * 100
    except (TypeError, ValueError):
        return None
    return c if c > 0 else None

def taker_fee_cents(price_cents):
    """Kalshi trading fee per contract: ceil(0.07 * P * (1-P)) dollars."""
    p = price_cents / 100.0
    return math.ceil(7 * p * (1 - p))

def ticker_date(ticker):
    """KXHIGHPHIL-26JUL10-T93 -> '2026-07-10', or None."""
    try:
        code = (ticker or "").split("-")[1]
        return datetime.strptime(code, "%y%b%d").date().isoformat()
    except (IndexError, ValueError):
        return None

def _iso_day(s):
    """Normalize a date-ish string to YYYY-MM-DD, else None."""
    s = (s or "").strip()[:10]
    try:
        return datetime.strptime(s, "%Y-%m-%d").date().isoformat()
    except ValueError:
        return None

def _find_col(fieldnames, *cands):
    for c in cands:
        for f in (fieldnames or []):
            if c in f.lower():
                return f
    return None


# ---------- data loading ----------

def actual_highs():
    """{(city, 'YYYY-MM-DD'): actual_high_f} from daily_highs.csv.
    Column names are sniffed so this works with your existing file."""
    if not os.path.exists("daily_highs.csv"):
        return {}
    with open("daily_highs.csv") as f:
        rd = csv.DictReader(f)
        city_c = _find_col(rd.fieldnames, "city")
        date_c = _find_col(rd.fieldnames, "date", "day")
        high_c = _find_col(rd.fieldnames, "high", "actual", "temp")
        if not (city_c and date_c and high_c):
            print("CALIBRATION OFF: couldn't identify columns in "
                  f"daily_highs.csv (found {rd.fieldnames})")
            return {}
        out = {}
        for row in rd:
            d = _iso_day(row.get(date_c))
            try:
                t = float(row.get(high_c))
            except (TypeError, ValueError):
                continue
            if d:
                out[(row.get(city_c), d)] = t
        return out


# ---------- calibration ----------

def build_calibration(ens, actuals, cities):
    """Per-city (bias_f, spread_scale) from matched history.
    bias   = mean(actual - ensemble_mean), clamped.
    spread = stdev of z-scores (actual vs ensemble), clamped >= 1
             (ensembles are underdispersive; never shrink them)."""
    errs, zs = defaultdict(list), defaultdict(list)
    today = date.today().isoformat()
    for (city, d), members in ens.items():
        if d >= today or (city, d) not in actuals:
            continue
        mu = mean(members)
        sd = pstdev(members)
        e = actuals[(city, d)] - mu
        errs[city].append(e)
        if sd > 0.1:
            zs[city].append(e / sd)
    cal = {}
    for city in cities:
        bias, scale = 0.0, 1.0
        if len(errs[city]) >= CAL_MIN_SAMPLES:
            bias = max(-BIAS_CLAMP, min(BIAS_CLAMP, mean(errs[city])))
            if len(zs[city]) >= CAL_MIN_SAMPLES:
                scale = max(SPREAD_MIN, min(SPREAD_MAX, pstdev(zs[city]) or 1.0))
        cal[city] = (round(bias, 2), round(scale, 2))
        print(f"cal {city}: bias={cal[city][0]:+.2f}F "
              f"spread x{cal[city][1]:.2f} (n={len(errs[city])})")
    return cal

def bracket_prob(members, floor_s, cap_s, bias, scale):
    """Fraction of calibrated members inside (floor-0.5, cap+0.5]."""
    mu = mean(members)
    adj = [mu + bias + scale * (t - mu) for t in members]
    lo = float(floor_s) - 0.5 if floor_s not in (None, "") else -999.0
    hi = float(cap_s) + 0.5 if cap_s not in (None, "") else 999.0
    return sum(1 for t in adj if lo <= t <= hi) / len(adj)


# ---------- output ----------

def rotate_old_schema():
    """If edges.csv exists with the old header, move it aside once."""
    if not os.path.exists(OUT):
        return
    with open(OUT) as f:
        first = f.readline().strip().split(",")
    if first != HEADER:
        dst = "edges_v1.csv"
        if os.path.exists(dst):
            dst = f"edges_v1_{int(time.time())}.csv"
        os.rename(OUT, dst)
        print(f"Rotated old-schema {OUT} -> {dst}")


def main():
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    series_map = discover_series()
    print(f"Trading {len(series_map)} city series")
    ens = ensembles_by_date()
    print("Ensemble dates loaded:", sorted({k[1] for k in ens}))
    cal = build_calibration(ens, actual_highs(),
                            sorted(set(series_map.values())))

    rotate_old_schema()
    new = not os.path.exists(OUT)
    with open(OUT, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(HEADER)
        for series, city in series_map.items():
            try:
                data = signed_get(f"/trade-api/v2/markets?series_ticker="
                                  f"{series}&status=open&limit=100")
            except Exception as e:
                print(f"{city} ({series}): FAILED - {e}")
                w.writerow([stamp, city, series, f"FETCH ERROR {e}"]
                           + [""] * (len(HEADER) - 4))
                continue
            mkts = data.get("markets", [])
            print(f"{city}: {len(mkts)} open markets")
            bias, scale = cal.get(city, (0.0, 1.0))
            for m in mkts:
                ticker = m.get("ticker")
                mdate = ticker_date(ticker)
                members = ens.get((city, mdate)) if mdate else None
                floor_s, cap_s = m.get("floor_strike"), m.get("cap_strike")
                yes_ask = cents(m, "yes_ask_dollars")
                no_ask = cents(m, "no_ask_dollars")

                prob = edge_y = edge_n = None
                if members and len(members) >= MIN_MEMBERS:
                    prob = bracket_prob(members, floor_s, cap_s,
                                        bias, scale) * 100
                    if yes_ask:
                        edge_y = round(prob - yes_ask
                                       - taker_fee_cents(yes_ask), 1)
                    if no_ask:
                        edge_n = round((100 - prob) - no_ask
                                       - taker_fee_cents(no_ask), 1)

                def ok(ask):
                    return ask and MIN_ASK <= ask <= MAX_ASK
                bet = ""
                best_y = edge_y if (edge_y is not None and ok(yes_ask)
                                    and edge_y >= MIN_EDGE) else None
                best_n = edge_n if (edge_n is not None and ok(no_ask)
                                    and edge_n >= MIN_EDGE) else None
                if best_y is not None and (best_n is None or best_y >= best_n):
                    bet = "YES"
                elif best_n is not None:
                    bet = "NO"

                w.writerow([stamp, city, ticker,
                            m.get("yes_sub_title") or m.get("subtitle", ""),
                            floor_s, cap_s,
                            round(yes_ask, 1) if yes_ask else "",
                            round(no_ask, 1) if no_ask else "",
                            round(prob, 1) if prob is not None else "",
                            edge_y if edge_y is not None else "",
                            edge_n if edge_n is not None else "",
                            bet, bias, scale,
                            len(members) if members else 0])
    print("Scan complete.")


if __name__ == "__main__":
    main()
