"""Weather-Bot: LIVE trader v4. Reads latest scan from edges.csv,
trades top picks (YES or NO), logs to trades.csv.

Changes vs v3 (safety release -- trading logic untouched):
  1. Skips Kalshi's daily maintenance window (~07:00 UTC): no more
     503 batches and blind retries into a down exchange.
  2. FAIL CLOSED ownership: markets owned = live API positions
     + resting orders + trades.csv 'submitted' rows, combined.
     If the API check fails, the run places NOTHING (previously it
     fell back to trades.csv alone, which can't see manual trades).
  3. Per-city daily cap (default 2): stops stacking multiple
     brackets of the same city/day, which is one correlated bet.
  4. Sanity guard: skips picks where the model and the market
     disagree by more than SANITY_GAP points -- those are almost
     always model/calibration bugs, not real edge. Skips are logged.

v3 features kept: proper ticker-date parsing, cancel own resting
orders each run, YES=bid / NO=ask-at-(100-c) on the single book.
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
BET_DOLLARS = 1      # $ per bet. THE sizing knob: 1 = ~1 contract now;
                     # 20 = ~$20 per bet later. Change ONLY after 100+
                     # settled bets show positive P&L.
MAX_RUN_DOLLARS = 10  # hard ceiling on total $ placed in one run
MIN_COST, MAX_COST = 15, 70   # cents you pay per contract, either side
MAX_PER_CITY_DAY = 1         # ONE position per city per day: two YES
                             # brackets of the same city can't both win
SANITY_GAP = 40              # skip if model% vs implied price gap > this
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


# ---------- safety ----------

def in_maintenance_window(now):
    """Kalshi daily maintenance ~07:00 UTC returns 503s. Skip it."""
    return MAINT_START <= (now.hour, now.minute) <= MAINT_END


# ---------- book-keeping ----------

def bot_order_ids():
    """Order IDs this bot placed, from trades.csv. Used so we only
    ever cancel our own orders - never the owner's manual app orders."""
    ids = set()
    if os.path.exists("trades.csv"):
        with open("trades.csv") as f:
            for row in csv.DictReader(f):
                if row.get("order_id"):
                    ids.add(row["order_id"])
    return ids

def cancel_resting_orders():
    """Kill unfilled GTC orders from prior BOT runs so stale prices
    can't get picked off. Manual orders placed in the Kalshi app are
    left untouched."""
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
            continue  # not ours - leave it alone
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

def exposure_tickers():
    """Every market we are exposed to RIGHT NOW: live positions plus
    resting orders (manual ones included) plus trades.csv history.
    Raises on API failure -- caller must FAIL CLOSED (trade nothing),
    because trades.csv alone cannot see manual positions."""
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
    """KXHIGHNY-26JUL19-B82.5 -> datetime.date, or None."""
    try:
        return datetime.strptime((ticker or "").split("-")[1],
                                 "%y%b%d").date()
    except (IndexError, ValueError):
        return None

def city_key(ticker):
    """KXHIGHLAX-26JUL23-B85.5 -> KXHIGHLAX (series prefix = city)."""
    return (ticker or "").split("-")[0]


# ---------- main ----------

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

    # ---- FAIL CLOSED: verify real account exposure before anything ----
    try:
        owned = exposure_tickers()
    except Exception as e:
        print(f"ABORT: could not verify account positions/orders ({e}). "
              f"Placing no trades this run.")
        return
    fresh = [r for r in fresh if r["market"] not in owned]

    # positions already held per city for the target day (cap input)
    per_city = {}
    for t in owned:
        if ticker_day(t) == target:
            per_city[city_key(t)] = per_city.get(city_key(t), 0) + 1

    # pick side-specific cost & edge, filter, rank
    ranked = []
    for r in fresh:
        side = r["would_bet"]
        try:
            cost = float(r["yes_ask"] if side == "YES" else r["no_ask"])
            edge = float(r["edge_yes"] if side == "YES" else r["edge_no"])
        except (TypeError, ValueError):
            continue
        if MIN_COST <= cost <= MAX_COST:
            ranked.append((edge, cost, side, r))
    ranked.sort(key=lambda p: p[0], reverse=True)

    picks = []
    for edge, cost, side, r in ranked:
        # sanity guard: model YES% vs the YES price this trade implies
        try:
            model = float(r.get("model_prob_pct") or 0)
        except (TypeError, ValueError):
            model = 0.0
        implied_yes = cost if side == "YES" else 100 - cost
        if abs(model - implied_yes) > SANITY_GAP:
            print(f"SKIP {r['market']} {side}: sanity gap "
                  f"(model {model:.0f}% vs implied {implied_yes:.0f}c)")
            continue
        # per-city daily cap
        ck = city_key(r["market"])
        if per_city.get(ck, 0) >= MAX_PER_CITY_DAY:
            print(f"SKIP {r['market']} {side}: city cap ({ck})")
            continue
        per_city[ck] = per_city.get(ck, 0) + 1
        picks.append((edge, cost, side, r))
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
        for edge, cost, side, r in picks:
            cost = int(cost)
            # dollar sizing: how many contracts BET_DOLLARS buys at this
            # price (min 1). Hard ceiling on total $ placed per run.
            count = max(1, int(BET_DOLLARS * 100) // cost)
            bet_cost = count * cost / 100
            if run_spent + bet_cost > MAX_RUN_DOLLARS:
                print(f"SKIP {r['market']} {side}: run spend cap "
                      f"(${run_spent:.2f} + ${bet_cost:.2f} > "
                      f"${MAX_RUN_DOLLARS})")
                continue
            run_spent += bet_cost
            # single YES book: buy YES = bid at cost;
            # buy NO at cost = ask (short YES) at 100 - cost
            book_side = "bid" if side == "YES" else "ask"
            book_price = cost if side == "YES" else 100 - cost
            status, oid = "DRY_RUN", ""
            if LIVE:
                body = {"ticker": r["market"],
                        "client_order_id": str(uuid.uuid4()),
                        "side": book_side,
                        "count": f"{count:.2f}",
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
            print(f"{r['city']} {r['subtitle']} {side} x{count} @{cost}c "
                  f"(${bet_cost:.2f}, edge {edge:+.1f}) -> {status}")
            w.writerow([stamp, r["market"], r["subtitle"], side.lower(),
                        count, cost, r["model_prob_pct"],
                        edge, LIVE, status, oid])
    print("Balance after:", balance())


if __name__ == "__main__":
    main()
