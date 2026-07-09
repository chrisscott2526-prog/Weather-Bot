"""Weather-Bot: Kalshi market scanner (READ-ONLY).
Authenticates with Kalshi, pulls high-temp markets for our cities,
compares prices to our NWS forecast, logs edges to edges.csv.
Places NO orders."""

import base64, csv, json, math, os, time, urllib.request
from datetime import datetime, timezone
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

BASE = "https://api.elections.kalshi.com"
KEY_ID = os.environ["KALSHI_API_KEY_ID"]
PRIV_PEM = os.environ["KALSHI_PRIVATE_KEY"].encode()

# Kalshi series tickers for daily high temp, per city
SERIES = {
    "KXHIGHNY":   "New York City",
    "KXHIGHMIA":  "Miami",
    "KXHIGHDEN":  "Denver",
    "KXHIGHLAX":  "Los Angeles",
    "KXHIGHPHIL": "Philadelphia",
    "KXHIGHAUS":  "Austin",
    "KXHIGHCHI":  "Chicago",
}

SIGMA = 3.0  # assumed forecast error (deg F) until calibration says better
OUT = "edges.csv"

key = serialization.load_pem_private_key(PRIV_PEM, password=None)

def signed_get(path):
    ts = str(int(time.time() * 1000))
    msg = ts + "GET" + path.split("?")[0]
    sig = key.sign(
        msg.encode(),
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.DIGEST_LENGTH),
        hashes.SHA256(),
    )
    req = urllib.request.Request(BASE + path, headers={
        "KALSHI-ACCESS-KEY": KEY_ID,
        "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode(),
        "KALSHI-ACCESS-TIMESTAMP": ts,
        "User-Agent": "weather-bot-personal",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def norm_cdf(x, mu, sd):
    return 0.5 * (1 + math.erf((x - mu) / (sd * math.sqrt(2))))

def bracket_prob(fc, floor_s, cap_s):
    lo = norm_cdf(floor_s - 0.5, fc, SIGMA) if floor_s is not None else 0.0
    hi = norm_cdf(cap_s + 0.5, fc, SIGMA) if cap_s is not None else 1.0
    return max(0.0, hi - lo)

def latest_forecasts():
    fcs = {}
    if not os.path.exists("forecasts.csv"):
        return fcs
    with open("forecasts.csv") as f:
        for row in csv.DictReader(f):
            if row["forecast_high_f"] not in ("", "ERROR"):
                fcs[row["city"]] = float(row["forecast_high_f"])
    return fcs  # last row per city wins

def main():
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    fcs = latest_forecasts()
    print("Forecasts loaded:", fcs)

    new = not os.path.exists(OUT)
    with open(OUT, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["scanned_utc", "city", "market", "subtitle",
                        "floor", "cap", "yes_ask", "no_ask",
                        "model_prob_pct", "edge_yes", "would_bet"])
        for series, city in SERIES.items():
            fc = fcs.get(city)
            try:
                data = signed_get(
                    f"/trade-api/v2/markets?series_ticker={series}"
                    f"&status=open&limit=100")
            except Exception as e:
                print(f"{city} ({series}): FAILED - {e}")
                w.writerow([stamp, city, series, f"FETCH ERROR {e}",
                            "", "", "", "", "", "", ""])
                continue
            mkts = data.get("markets", [])
            print(f"{city}: {len(mkts)} open markets")
            for m in mkts:
                floor_s = m.get("floor_strike")
                cap_s = m.get("cap_strike")
                yes_ask = m.get("yes_ask")
                no_ask = m.get("no_ask")
                prob = (bracket_prob(fc, floor_s, cap_s) * 100
                        if fc is not None else None)
                edge = (round(prob - yes_ask, 1)
                        if prob is not None and yes_ask else None)
                bet = ("YES" if edge is not None and edge >= 10
                       and yes_ask and 3 <= yes_ask <= 70 else "")
                w.writerow([stamp, city, m.get("ticker"),
                            m.get("subtitle") or m.get("yes_sub_title", ""),
                            floor_s, cap_s, yes_ask, no_ask,
                            round(prob, 1) if prob is not None else "",
                            edge if edge is not None else "", bet])

if __name__ == "__main__":
    main()
