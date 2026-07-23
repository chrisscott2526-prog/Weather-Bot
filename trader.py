"""Weather-Bot: LIVE trader. Reads latest scan from edges.csv,
buys 1 contract on top YES picks (max 5), logs to trades.csv.
HARD CAPS: 1 contract/market, 5 orders/run, ask 3-70c only.

SAFETY (v2):
  - Skips Kalshi maintenance window (~07:00 UTC daily) entirely.
  - Reconciles against REAL account positions + resting orders via API
    before placing anything (covers manual trades in same account AND
    orders that were accepted despite an error response).
  - Fails CLOSED: if the positions/orders check errors, no trades.
  - Per-city daily cap (correlated-bracket protection).
  - Sanity guard: skips "edges" where model and market disagree by
    more than SANITY_GAP points -- those are model bugs, not alpha.
"""
import base64, csv, json, os, re, time, urllib.request, urllib.error, uuid
from datetime import datetime, timezone

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

LIVE = True          # False = log picks only, place nothing
MAX_ORDERS = 5
CONTRACTS = 1
MIN_ASK, MAX_ASK = 3, 70
MAX_PER_CITY_DAY = 2          # max positions per city per market day
SANITY_GAP = 40               # skip if |model% - price¢| > this
MAINT_START, MAINT_END = (6, 45), (8, 15)   # UTC window to skip (503s)

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
    lines = [b64[i:i + 64] for i in range(0, len(b64), 64)]
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


def in_maintenance_window(now):
    """Kalshi daily maintenance ~07:00 UTC returns 503s. Don't trade into it."""
    t = (now.hour, now.minute)
    return MAINT_START <= t <= MAINT_END


def live_exposure():
    """Set of tickers with a REAL open position or resting order on the
    account -- includes the human's manual trades and any order Kalshi
    accepted even if our HTTP call errored. Raises on failure (fail closed)."""
    tickers = set()
    pos = api("GET", "/trade-api/v2/portfolio/positions?limit=200")
    for p in pos.get("market_positions", []) or []:
        if p.get("position") or p.get("total_traded"):
            tickers.add(p.get("ticker", ""))
    orders = api("GET", "/trade-api/v2/portfolio/orders?status=resting&limit=200")
    for o in orders.get("orders", []) or []:
        tickers.add(o.get("ticker", ""))
    tickers.discard("")
    return tickers


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


def city_key(ticker):
    """KXHIGHLAX-26JUL23-B85.5 -> KXHIGHLAX (series = city)."""
    return (ticker or "").split("-")[0]


def city_counts(tickers, date_code):
    """How many positions we already hold per city for this market day."""
    counts = {}
    for t in tickers:
        if date_code and date_code in t:
            counts[city_key(t)] = counts.get(city_key(t), 0) + 1
    return counts


def main():
    now = datetime.now(timezone.utc)
    stamp = now.isoformat(timespec="seconds")

    if in_maintenance_window(now):
        print(f"{stamp}: inside Kalshi maintenance window "
              f"({MAINT_START}-{MAINT_END} UTC). Skipping run.")
        return

    rows = list(csv.DictReader(open("edges.csv")))
    latest = rows[-1]["scanned_utc"]
    fresh = [r for r in rows if r["scanned_utc"] == latest
             and r["would_bet"] == "YES"]

    # tomorrow's markets = newest date code in tickers
    dates = sorted({(r["market"] or "").split("-")[1]
                    for r in fresh if r["market"]})
    date_code = dates[-1] if dates else ""
    if date_code:
        fresh = [r for r in fresh if date_code in r["market"]]

    # --- reconcile against the REAL account, not just our CSV ---
    try:
        exposure = live_exposure()
    except Exception as e:
        print(f"ABORT: could not verify account positions/orders ({e}). "
              f"Failing closed -- no trades this run.")
        return

    owned = already_bought() | exposure
    fresh = [r for r in fresh if r["market"] not in owned]

    fresh.sort(key=lambda r: float(r["edge_yes"] or 0), reverse=True)

    per_city = city_counts(owned, date_code)
    picks, skipped = [], []
    for r in fresh:
        if not r["yes_ask"]:
            continue
        price = float(r["yes_ask"])
        if not (MIN_ASK <= price <= MAX_ASK):
            continue
        model = float(r.get("model_prob_pct") or 0)
        if abs(model - price) > SANITY_GAP:
            skipped.append((r["market"], f"sanity gap model={model} ask={price}"))
            continue
        ck = city_key(r["market"])
        if per_city.get(ck, 0) >= MAX_PER_CITY_DAY:
            skipped.append((r["market"], f"city cap {ck}"))
            continue
        per_city[ck] = per_city.get(ck, 0) + 1
        picks.append(r)
        if len(picks) >= MAX_ORDERS:
            break

    for m, why in skipped:
        print(f"SKIP {m}: {why}")
    print(f"Scan {latest}: {len(picks)} orders to place "
          f"({len(owned)} markets already owned/exposed). LIVE={LIVE}")
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
