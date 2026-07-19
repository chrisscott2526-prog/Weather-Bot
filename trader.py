"""Weather-Bot: LIVE trader v3. Reads latest scan from edges.csv,
trades top picks (YES or NO), logs to trades.csv.

Changes vs v2:
  1. DATE FIX: ticker dates parsed properly (v2 sorted "26AUG01"
     before "26JUL19" alphabetically -> wrong day at month ends).
  2. Cancels resting unfilled orders at the start of each run, so
     stale bids can't sit on the book after the forecast moves.
  3. Ownership from real Kalshi positions (API), with trades.csv
     as a fallback, instead of trusting "submitted" == owned.
  4. NO-side orders: a NO buy at price c is placed as an "ask" on
     the single YES book at (100 - c) cents.

HARD CAPS unchanged: 1 contract/market, 5 orders/run, cost 3-70c.
Run once with LIVE = False after upgrading to sanity-check output.
"""

import base64, csv, json, os, re, time, urllib.request, urllib.error, uuid
from datetime import datetime, timezone
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

LIVE = True          # False = log picks only, place nothing
TRADE_NO = True      # set False to keep old YES-only behavior
MAX_ORDERS = 5
CONTRACTS = 1
MIN_COST, MAX_COST = 3, 70   # cents you pay per contract, either side
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
        raw = r.read()
        return json.loads(raw) if raw else {}

def balance():
    try:
        return api("GET", "/trade-api/v2/portfolio/balance").get("balance")
    except Exception as e:
        return f"ERR {e}"


# ---------- book-keeping ----------

def cancel_resting_orders():
    """Kill unfilled GTC orders from prior runs so stale prices
    can't get picked off after the forecast moves."""
    try:
        resp = api("GET", "/trade-api/v2/portfolio/orders?status=resting")
    except Exception as e:
        print(f"cancel: couldn't list resting orders ({e})")
        return
    for o in resp.get("orders", []):
        oid = o.get("order_id")
        if not oid:
            continue
        for path in (f"/trade-api/v2/portfolio/events/orders/{oid}",
                     f"/trade-api/v2/portfolio/orders/{oid}"):
            try:
                api("DELETE", path)
                print(f"cancelled resting {o.get('ticker')} ({oid[:8]})")
                break
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    continue          # try legacy path
                print(f"cancel {oid[:8]}: HTTP {e.code}")
                break
            except Exception as e:
                print(f"cancel {oid[:8]}: {e}")
                break

def owned_tickers():
    """Markets we actually hold, from live positions; fall back to
    trades.csv 'submitted' rows if the API call fails."""
    try:
        resp = api("GET", "/trade-api/v2/portfolio/positions")
        return {p["ticker"] for p in resp.get("market_positions", [])
                if p.get("ticker") and float(p.get("position") or 0) != 0}
    except Exception as e:
        print(f"positions unavailable ({e}); falling back to trades.csv")
    owned = set()
    if os.path.exists("trades.csv"):
        with open("trades.csv") as f:
            for row in csv.DictReader(f):
                if row.get("status") == "submitted" and row.get("ticker"):
                    owned.add(row["ticker"])
    return owned

def ticker_day(ticker):
    """KXHIGHNY-26JUL19-B82.5 -> datetime.date, or None."""
    try:
        return datetime.strptime((ticker or "").split("-")[1],
                                 "%y%b%d").date()
    except (IndexError, ValueError):
        return None


# ---------- main ----------

def main():
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if not os.path.exists("edges.csv"):
        print("No edges.csv yet - run scanner first.")
        return
    rows = list(csv.DictReader(open("edges.csv")))
    if not rows:
        print("edges.csv is empty.")
        return
    latest = rows[-1]["scanned_utc"]
    fresh = [r for r in rows if r["scanned_utc"] == latest
             and r.get("would_bet") in
             (("YES", "NO") if TRADE_NO else ("YES",))]

    # target the most distant open date (usually tomorrow),
    # comparing REAL dates, not alphabetical ticker strings
    dated = [(ticker_day(r["market"]), r) for r in fresh]
    dated = [(d, r) for d, r in dated if d]
    if not dated:
        print(f"Scan {latest}: no dated picks.")
        return
    target = max(d for d, _ in dated)
    fresh = [r for d, r in dated if d == target]

    owned = owned_tickers()
    fresh = [r for r in fresh if r["market"] not in owned]

    # pick side-specific cost & edge, filter, rank
    picks = []
    for r in fresh:
        side = r["would_bet"]
        try:
            cost = float(r["yes_ask"] if side == "YES" else r["no_ask"])
            edge = float(r["edge_yes"] if side == "YES" else r["edge_no"])
        except (TypeError, ValueError):
            continue
        if MIN_COST <= cost <= MAX_COST:
            picks.append((edge, cost, side, r))
    picks.sort(key=lambda p: p[0], reverse=True)
    picks = picks[:MAX_ORDERS]

    print(f"Scan {latest} -> {target}: {len(picks)} orders "
          f"({len(owned)} markets owned). LIVE={LIVE}")
    if LIVE:
        cancel_resting_orders()
    print("Balance before:", balance())

    new = not os.path.exists("trades.csv")
    with open("trades.csv", "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["placed_utc", "ticker", "subtitle", "side",
                        "count", "limit_cents", "model_pct", "edge",
                        "live", "status", "order_id"])
        for edge, cost, side, r in picks:
            cost = int(cost)
            # single YES book: buy YES = bid at cost;
            # buy NO at cost = ask (short YES) at 100 - cost
            book_side = "bid" if side == "YES" else "ask"
            book_price = cost if side == "YES" else 100 - cost
            status, oid = "DRY_RUN", ""
            if LIVE:
                body = {"ticker": r["market"],
                        "client_order_id": str(uuid.uuid4()),
                        "side": book_side,
                        "count": f"{CONTRACTS:.2f}",
                        "price": f"{book_price / 100:.4f}",
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
            print(f"{r['city']} {r['subtitle']} {side} @{cost}c "
                  f"(edge {edge:+.1f}) -> {status}")
            w.writerow([stamp, r["market"], r["subtitle"], side.lower(),
                        CONTRACTS, cost, r["model_prob_pct"],
                        edge, LIVE, status, oid])
    print("Balance after:", balance())


if __name__ == "__main__":
    main()
