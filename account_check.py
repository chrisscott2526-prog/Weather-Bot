"""Weather-Bot: READ-ONLY account check. Answers one question in plain
English: WHERE IS THE MONEY?

Born Sep 11 2026: the morning lane's San Antonio order (92 cents)
bounced with "insufficient balance" while the owner's Kalshi app
showed $20+. Those two facts can both be true at once, because the
number on the app's home screen is the whole portfolio -- cash PLUS
money already sitting inside open positions PLUS money held hostage
by unfilled resting orders. A new order can only spend the CASH
part. This script prints all three buckets so nobody has to guess
again.

Places nothing, cancels nothing, changes nothing. Needs the same two
secrets the trader uses (KALSHI_API_KEY_ID, KALSHI_PRIVATE_KEY).
Run it from the Actions tab: "Account check (read-only)" -> Run
workflow. Any dead API call exits non-zero (the dead-feed law).
"""

import base64, csv, json, os, re, sys, time, urllib.request, urllib.error
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

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


def api(method, path):
    req = urllib.request.Request(BASE + path, headers=sign(method, path),
                                 method=method)
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
        return json.loads(raw) if raw else {}


def paged(path, list_key):
    """Follow Kalshi's cursor pagination until the list runs out."""
    out, cursor = [], ""
    for _ in range(50):
        sep = "&" if "?" in path else "?"
        resp = api("GET", path + (f"{sep}cursor={cursor}" if cursor else ""))
        out.extend(resp.get(list_key) or [])
        cursor = resp.get("cursor") or ""
        if not cursor:
            break
    return out


def bot_order_ids():
    ids = set()
    if os.path.exists("trades.csv"):
        with open("trades.csv") as f:
            for row in csv.DictReader(f):
                if row.get("order_id"):
                    ids.add(row["order_id"])
    return ids


def cents(v):
    # int(float(...)) because Kalshi sometimes serializes counts as
    # "2.0" -- plain int() throws on that and a position would
    # silently read as zero (seen Sep 11 2026: the first run printed
    # "0 markets" while the swoop board, reading the same API, was
    # correctly grading 1 open position).
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def main():
    print("KALSHI ACCOUNT CHECK -- read-only, places nothing, "
          "cancels nothing\n")

    # Bucket 1: cash a new order could actually spend.
    bal = api("GET", "/trade-api/v2/portfolio/balance")
    cash = cents(bal.get("balance"))
    print(f"1) AVAILABLE CASH (what a new order can spend): "
          f"${cash / 100:.2f}")

    # Bucket 2: money held hostage by unfilled resting orders.
    orders = paged("/trade-api/v2/portfolio/orders?status=resting",
                   "orders")
    ours = bot_order_ids()
    held = 0
    lines = []
    for o in orders:
        rem = cents(o.get("remaining_count"))
        side = (o.get("side") or "?").lower()
        price = cents(o.get("yes_price") if side == "yes"
                      else o.get("no_price"))
        hold = rem * price
        held += hold
        who = ("the bot's" if o.get("order_id") in ours
               else "NOT the bot's (placed by hand?)")
        lines.append(f"     {o.get('ticker', '?')}: {side.upper()} "
                     f"x{rem} @ {price}c = ${hold / 100:.2f} -- {who}")
    print(f"\n2) HELD BY RESTING (unfilled) ORDERS: ${held / 100:.2f} "
          f"across {len(orders)} order(s)")
    for ln in lines:
        print(ln)

    # Bucket 3: money already inside open positions. Same query the
    # swoop board uses (limit=200), so the two can never disagree by
    # pagination.
    mpos = paged("/trade-api/v2/portfolio/positions?limit=200",
                 "market_positions")
    open_pos = [p for p in mpos if cents(p.get("position")) != 0]
    at_risk = 0
    print(f"\n3) INSIDE OPEN POSITIONS (money already spent on "
          f"contracts that haven't settled): {len(open_pos)} market(s) "
          f"open, {len(mpos)} row(s) returned in all")
    for p in open_pos:
        exp = cents(p.get("market_exposure"))
        at_risk += exp
        print(f"     {p.get('ticker', '?')}: {cents(p.get('position'))} "
              f"contract(s), ${exp / 100:.2f} riding on it")
    print(f"   Total riding: ${at_risk / 100:.2f}")

    total = cash + held + at_risk
    print("\n" + "-" * 60)
    print(f"ADDS UP TO ROUGHLY ${total / 100:.2f} -- this is about the "
          f"number the Kalshi app shows on its home screen.")
    print(f"But the bot's $1 bets can only spend bucket 1. With "
          f"${cash / 100:.2f} available, a ~$1 order "
          f"{'FAILS' if cash < 100 else 'fits'}.")
    if cash < 100:
        print("\nTO FIX: free up cash. Either deposit, or (if bucket 2 "
              "shows hand-placed resting orders) cancel them in the "
              "app, or wait for open positions to settle and pay out.")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as e:
        print(f"ERROR: Kalshi API said {e.code}: "
              f"{e.read().decode()[:200]}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: account check failed: {e}", file=sys.stderr)
        sys.exit(1)
