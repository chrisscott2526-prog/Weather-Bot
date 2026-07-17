"""Weather-Bot: Kalshi market scanner (READ-ONLY, v2 ensemble).
Authenticates with Kalshi, pulls high-temp markets for our cities,
computes bracket probability by counting GFS ensemble members,
logs edges to edges.csv. Places NO orders."""

import base64, csv, json, math, os, re, time, urllib.request
from datetime import datetime, timezone
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

BASE = "https://api.elections.kalshi.com"
KEY_ID = os.environ["KALSHI_API_KEY_ID"].strip()

def load_key():
    """Rebuild a clean PEM no matter how the paste mangled it."""
    raw = os.environ["KALSHI_PRIVATE_KEY"]
    raw = raw.replace("\\n", "\n").strip()
    m = re.search(r"-----BEGIN ([A-Z ]+)-----(.*?)-----END \1-----",
                  raw, re.DOTALL)
    if not m:
        raise ValueError("No BEGIN/END block found in KALSHI_PRIVATE_KEY")
    label, body = m.group(1), m.group(2)
    b64 = re.sub(r"[^A-Za-z0-9+/=]", "", body)
    lines = [b64[i:i+64] for i in range(0, len(b64), 64)]
    pem = (f"-----BEGIN {label}-----\n" + "\n".join(lines)
           + f"\n-----END {label}-----\n").encode()
    return serialization.load_pem_private_key(pem, password=None)

key = load_key()

SERIES = {
    "KXHIGHNY":   "New York City",
    "KXHIGHMIA":  "Miami",
    "KXHIGHDEN":  "Denver",
    "KXHIGHLAX":  "Los Angeles",
    "KXHIGHPHIL": "Philadelphia",
    "KXHIGHAUS":  "Austin",
    "KXHIGHCHI":  "Chicago",
}

MIN_EDGE = 8.0
OUT = "edges.csv"

def cents(m, field):
    """Read a *_dollars string field, return cents as float, or None."""
    v = m.get(field)
    if v in (None, ""):
        return None
    try:
        c = float(v) * 100
    except (TypeError, ValueError):
        return None
    return c if c > 0 else None

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

def ensembles_by_date():
    """Return {(city, 'YYYY-MM-DD'): [member temps]} from the most
    recent fetch for each city+date."""
    # Sync fix: this job can check out the repo seconds BEFORE the
    # nightly forecast commit lands (cron race). Pull the freshest
    # commit so tonight's members are always available. Fails safe:
    # if the pull errors, we just use the checkout copy as before.
    os.system("git pull --rebase --quiet 2>/dev/null")
    ens = {}
    if not os.path.exists("forecasts.csv"):
        return ens
    with open("forecasts.csv") as f:
        for row in csv.DictReader(f):
            mstr = row.get("members") or ""
            if (row.get("forecast_high_f") or "") not in ("", "ERROR") and mstr:
                members = [float(x) for x in mstr.split("|") if x]
                if members:
                    ens[(row["city"], row["forecast_date"])] = members
    return ens

def bracket_prob(members, floor_s, cap_s):
    """Fraction of ensemble members inside (floor, cap]."""
    lo = float(floor_s) - 0.5 if floor_s is not None else -999.0
    hi = float(cap_s) + 0.5 if cap_s is not None else 999.0
    n = sum(1 for t in members if lo <= t <= hi)
    return n / len(members)

def ticker_date(ticker):
    """KXHIGHPHIL-26JUL10-T93 -> '2026-07-10', or None if unparseable."""
    try:
        code = (ticker or "").split("-")[1]
        return datetime.strptime(code, "%y%b%d").date().isoformat()
    except (IndexError, ValueError):
        return None

def main():
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    ens = ensembles_by_date()
    print("Ensemble dates loaded:", sorted({k[1] for k in ens}))

    new = not os.path.exists(OUT)
    with open(OUT, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["scanned_utc", "city", "market", "subtitle",
                        "floor", "cap", "yes_ask", "no_ask",
                        "model_prob_pct", "edge_yes", "would_bet"])
        for series, city in SERIES.items():
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
                ticker = m.get("ticker")
                mdate = ticker_date(ticker)
                members = ens.get((city, mdate)) if mdate else None
                floor_s = m.get("floor_strike")
                cap_s = m.get("cap_strike")
                yes_ask = cents(m, "yes_ask_dollars")
                no_ask = cents(m, "no_ask_dollars")
                prob = (bracket_prob(members, floor_s, cap_s) * 100
                        if members else None)
                edge = (round(prob - yes_ask, 1)
                        if prob is not None and yes_ask else None)
                bet = ("YES" if edge is not None and edge >= MIN_EDGE
                       and yes_ask and 3 <= yes_ask <= 70 else "")
                w.writerow([stamp, city, ticker,
                            m.get("yes_sub_title") or m.get("subtitle", ""),
                            floor_s, cap_s,
                            round(yes_ask, 1) if yes_ask else "",
                            round(no_ask, 1) if no_ask else "",
                            round(prob, 1) if prob is not None else "",
                            edge if edge is not None else "", bet])
    print("Scan complete.")

if __name__ == "__main__":
    main()



