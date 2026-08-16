"""Weather-Bot: LIVE trader. Reads latest scan from edges.csv, buys the
scanner's picked brackets (YES only), logs to trades.csv.

FIXED Aug 6 2026 -- pick-first alignment:
  1. MIN_COST/MAX_COST corrected to 8/68, matching scanner.py's gate
     exactly. (Was 15/10 -- an impossible range that silently placed
     ZERO trades no matter what the scanner picked. This was the bug
     behind days of "nothing is buying.")
  2. TRADE_NO removed. The pick-first scanner never bets against a
     bracket -- only for the one it picked. Nothing left to flip.
  3. No more edge-based ranking. The scanner already chose the
     bracket; the trader just executes it. Picks are taken in the
     order they were written, not re-sorted by any price math.

Everything else unchanged: maintenance-window skip, FAIL CLOSED
ownership check, per-city daily cap, sanity guard against a model/
price gap, unverified-city skip, $1 sizing until 100+ settled bets.
HARD CAPS: 1 contract/market by default, 5 orders/run, $10/run.
"""

import base64, csv, json, os, re, time, urllib.request, urllib.error, uuid
from datetime import datetime, timezone
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cities import UNVERIFIED

LIVE = True          # False = log picks only, place nothing
MAX_ORDERS = 5
BET_DOLLARS = 1      # $ per bet. Change ONLY after 100+ settled bets
                     # show positive P&L.
MAX_RUN_DOLLARS = 10  # hard ceiling on total $ placed in one run
MIN_COST, MAX_COST = 8, 68   # matches scanner.py's MIN/MAX_PICK_COST
MAX_PER_CITY_DAY = 1         # one position per city per day
SANITY_GAP = 60             # skip if model% vs implied price gap > this
SKIP_UNVERIFIED = True
MAINT_START, MAINT_END = (6, 45), (8, 15)  # UTC window to skip (Kalshi 503s)
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


def in_maintenance_window(now):
    return MAINT_START <= (now.hour, now.minute) <= MAINT_END


def bot_order_ids():
    ids = set()
    if os.path.exists("trades.csv"):
        with open("trades.csv") as f:
            for row in csv.DictReader(f):
                if row.get("order_id"):
                    ids.add(row["order_id"])
    return ids

def cancel_resting_orders():
    mine = bot_order_ids()
    if not mine:
        return
    try:
        resp = api("GET", "/trade-api/v2/portfolio/orders?status=resting")
    except Exception as e:
        print(f"cancel: couldn't list resting orders ({e})")
        return
    for o in resp.get("orders", []):
        oid = o.get("order_id")
        if not oid or oid not in mine:
            continue
        for path in (f"/trade-api/v2/portfolio/events/orders/{oid}",
                     f"/trade-api/v2/portfolio/orders/{oid}"):
            try:
                api("DELETE", path)
                print(f"cancelled resting {o.get('ticker')} ({oid[:8]})")
                break
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    continue
                print(f"cancel {oid[:8]}: HTTP {e.code}")
                break
            except Exception as e:
                print(f"cancel {oid[:8]}: {e}")
                break

def exposure_tickers():
    tickers = set()
    resp = api("GET", "/trade-api/v2/portfolio/positions")
    for p in resp.get("market_positions", []):
        if p.get("ticker") and float(p.get("position") or 0) != 0:
            tickers.add(p["ticker"])
    resp = api("GET", "/trade-api/v2/portfolio/orders?status=resting")
    for o in resp.get("orders", []):
        if o.get("ticker"):
            tickers.add(o["ticker"])
    if os.path.exists("trades.csv"):
        with open("trades.csv") as f:
            for row in csv.DictReader(f):
                if row.get("status") == "submitted" and row.get("ticker"):
                    tickers.add(row["ticker"])
    return tickers

def ticker_day(ticker):
    try:
        return datetime.strptime((ticker or "").split("-")[1],
                                 "%y%b%d").date()
    except (IndexError, ValueError):
        return None

def city_key(ticker):
    return (ticker or "").split("-")[0]


def main():
    now = datetime.now(timezone.utc)
    stamp = now.isoformat(timespec="seconds")

    if in_maintenance_window(now):
        print(f"{stamp}: inside Kalshi maintenance window "
              f"({MAINT_START}-{MAINT_END} UTC). Skipping run.")
        return

    if not os.path.exists("edges.csv"):
        print("No edges.csv yet - run scanner first.")
        return
    rows = list(csv.DictReader(open("edges.csv")))
    if not rows:
        print("edges.csv is empty.")
        return
    latest = rows[-1]["scanned_utc"]
    fresh = [r for r in rows if r["scanned_utc"] == latest
             and r.get("would_bet") == "YES"]

    dated = [(ticker_day(r["market"]), r) for r in fresh]
    dated = [(d, r) for d, r in dated if d]
    if not dated:
        print(f"Scan {latest}: no dated picks.")
        return
    target = max(d for d, _ in dated)
    fresh = [r for d, r in dated if d == target]

    if SKIP_UNVERIFIED:
        before = len(fresh)
        blocked = sorted({r.get("city", "") for r in fresh
                          if r.get("city", "") in UNVERIFIED})
        fresh = [r for r in fresh if r.get("city", "") not in UNVERIFIED]
        if blocked:
            print(f"SKIP_UNVERIFIED: dropped {before - len(fresh)} picks "
                  f"from unverified cities: {', '.join(blocked)}")

    try:
        owned = exposure_tickers()
    except Exception as e:
        print(f"ABORT: could not verify account positions/orders ({e}). "
              f"Placing no trades this run.")
        return
    fresh = [r for r in fresh if r["market"] not in owned]

    per_city = {}
    for t in owned:
        if ticker_day(t) == target:
            per_city[city_key(t)] = per_city.get(city_key(t), 0) + 1

    # filter to the cost band only -- no ranking, no edge math.
    # order is simply the order the scanner wrote them in.
    candidates = []
    for r in fresh:
        try:
            cost = float(r["yes_ask"])
        except (TypeError, ValueError):
            continue
        if MIN_COST <= cost <= MAX_COST:
            candidates.append((cost, r))

    picks = []
    for cost, r in candidates:
        try:
            model = float(r.get("model_prob_pct") or 0)
        except (TypeError, ValueError):
            model = 0.0
        if abs(model - cost) > SANITY_GAP:
            print(f"SKIP {r['market']}: sanity gap "
                  f"(model {model:.0f}% vs price {cost:.0f}c)")
            continue
        ck = city_key(r["market"])
        if per_city.get(ck, 0) >= MAX_PER_CITY_DAY:
            print(f"SKIP {r['market']}: city cap ({ck})")
            continue
        per_city[ck] = per_city.get(ck, 0) + 1
        picks.append((cost, r))
        if len(picks) >= MAX_ORDERS:
            break

    print(f"Scan {latest} -> {target}: {len(picks)} orders "
          f"({len(owned)} markets owned/exposed). LIVE={LIVE}")
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
        run_spent = 0.0
        for cost, r in picks:
            cost = int(cost)
            count = max(1, int(BET_DOLLARS * 100) // cost)
            bet_cost = count * cost / 100
            if run_spent + bet_cost > MAX_RUN_DOLLARS:
                print(f"SKIP {r['market']}: run spend cap "
                      f"(${run_spent:.2f} + ${bet_cost:.2f} > "
                      f"${MAX_RUN_DOLLARS})")
                continue
            run_spent += bet_cost
            status, oid = "DRY_RUN", ""
            if LIVE:
                body = {"ticker": r["market"],
                        "client_order_id": str(uuid.uuid4()),
                        "side": "bid",
                        "count": f"{count:.2f}",
                        "price": f"{cost / 100:.4f}",
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
            print(f"{r['city']} {r['subtitle']} YES x{count} @{cost}c "
                  f"(${bet_cost:.2f}) -> {status}")
            w.writerow([stamp, r["market"], r["subtitle"], "yes",
                        count, cost, r["model_prob_pct"], "",
                        LIVE, status, oid])
    print("Balance after:", balance())


if __name__ == "__main__":
    main()
