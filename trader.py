"""Weather-Bot: LIVE trader. Reads latest scan from edges.csv,
buys 1 contract on top YES picks (max 5), logs to trades.csv.
HARD CAPS: 1 contract/market, 5 orders/run, ask 3-70c only.
Skips any market already bought (tracked in trades.csv)."""

import base64, csv, json, os, re, time, urllib.request, urllib.error, uuid
from datetime import datetime, timezone
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

LIVE = True            # False = log picks only, place nothing
MAX_ORDERS = 5
CONTRACTS = 1
MIN_ASK, MAX_ASK = 3, 70

BASE = "https://api.elections.kalshi.com"
KEY_ID = os.environ["KALSHI_API_KEY_ID"].strip()

def load_key():
    raw = os.environ["KALSHI_PRIVATE_KEY"].replace("\\n", "\n").strip()
    m = re.search(r"-----BEGIN ([A-Z ]+)-----(.*?)-----END \1-----",
                  raw, re.DOTALL)
    if not m:
        raise ValueError("No BEGIN/END block in KALSHI_PRIVATE_KEY")
    label, body = m.group(1), m.group(2)
    b64 = re.sub(r"[^A-Za-z0-9+/=]", "", body)
    lines = [b64[i:i+64] for i in range(0, len(b64), 64)]
    pem = (f"-----BEGIN {label}-----\n" + "\n".join(lines)
           + f"\n-----END {label}-----\n").encode()
    return serialization.load_pem_private_key(pem, password=None)

key = load_key()

def sign(method, path):
    ts = str(int(time.time() * 1000))
    sig = key.sign((ts + method + path.split("?")[0]).encode(),
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.DIGEST_LENGTH),
        hashes.SHA256())
    return {"KALSHI-ACCESS-KEY": KEY_ID,
            "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode(),
            "KALSHI-ACCESS-TIMESTAMP": ts,
            "User-Agent": "weather-bot-personal",
            "Content-Type": "application/json"}

def api(method, path, body=None):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(BASE + path, data=data,
                                 headers=sign(method, path), method=method)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def balance():
    try:
        return api("GET", "/trade-api/v2/portfolio/balance").get("balance")
    except Exception as e:
        return f"ERR {e}"

def already_bought():
    """Tickers we already submitted successfully, from trades.csv."""
    owned = set()
    if not os.path.exists("trades.csv"):
        return owned
    with open("trades.csv") as f:
        for row in csv.DictReader(f):
            if row.get("status") == "submitted" and row.get("ticker"):
                owned.add(row["ticker"])
    return owned

def main():
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows = list(csv.DictReader(open("edges.csv")))
    latest = rows[-1]["scanned_utc"]
    fresh = [r for r in rows if r["scanned_utc"] == latest
             and r["would_bet"] == "YES"]
    # tomorrow's markets = newest date code in tickers
    dates = sorted({(r["market"] or "").split("-")[1] for r in fresh if r["market"]})
    if dates:
        fresh = [r for r in fresh if dates[-1] in r["market"]]
    owned = already_bought()
    fresh = [r for r in fresh if r["market"] not in owned]
    fresh.sort(key=lambda r: float(r["edge_yes"] or 0), reverse=True)
    picks = [r for r in fresh
             if r["yes_ask"] and MIN_ASK <= float(r["yes_ask"]) <= MAX_ASK
             ][:MAX_ORDERS]

    print(f"Scan {latest}: {len(picks)} orders to place "
          f"({len(owned)} markets already owned). LIVE={LIVE}")
    print("Balance before:", balance())

    new = not os.path.exists("trades.csv")
    with open("trades.csv", "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["placed_utc", "ticker", "subtitle", "side",
                        "count", "limit_cents", "model_pct", "edge",
                        "live", "status", "order_id"])
        for r in picks:
            price = int(float(r["yes_ask"]))
            status, oid = "DRY_RUN", ""
            if LIVE:
                body = {"ticker": r["market"],
                        "client_order_id": str(uuid.uuid4()),
                        "side": "bid",
                        "count": f"{CONTRACTS:.2f}",
                        "price": f"{price / 100:.4f}",
                        "time_in_force": "good_till_canceled",
                        "self_trade_prevention_type": "taker_at_cross"}
                try:
                    resp = api("POST",
                               "/trade-api/v2/portfolio/events/orders",
                               body)
                    oid = resp.get("order_id", "")
                    status = "submitted" if oid else f"ODD {resp}"
                except urllib.error.HTTPError as e:
                    status = f"ERROR {e.code} {e.read().decode()[:150]}"
                except Exception as e:
                    status = f"ERROR {e}"
            print(f"{r['city']} {r['subtitle']} @{price}c -> {status}")
            w.writerow([stamp, r["market"], r["subtitle"], "yes",
                        CONTRACTS, price, r["model_prob_pct"],
                        r["edge_yes"], LIVE, status, oid])

    print("Balance after:", balance())

if __name__ == "__main__":
    main()
