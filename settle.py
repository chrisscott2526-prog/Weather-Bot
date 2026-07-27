"""Weather-Bot: settlement scorekeeper. Reads trades.csv, asks Kalshi
which markets settled and how, writes results.csv with win/loss and
P&L per bet, prints the running scoreboard. Places NO trades ever.
Run daily. This file is how we know when to raise BET_DOLLARS."""

import base64, csv, json, os, re, time, urllib.request
from datetime import datetime, timezone
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

def api(path):
    req = urllib.request.Request(BASE + path, headers=sign("GET", path))
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
        return json.loads(raw) if raw else {}


def market_results():
    """ticker -> 'yes'/'no' for markets that have settled, from the
    account's settlement history (paged)."""
    results, cursor = {}, ""
    for _ in range(20):  # up to 20 pages
        path = "/trade-api/v2/portfolio/settlements?limit=100"
        if cursor:
            path += f"&cursor={cursor}"
        resp = api(path)
        for s in resp.get("settlements", []):
            t = s.get("ticker")
            mr = (s.get("market_result") or "").lower()
            if t and mr in ("yes", "no"):
                results[t] = mr
        cursor = resp.get("cursor") or ""
        if not cursor:
            break
    return results


def main():
    if not os.path.exists("trades.csv"):
        print("No trades.csv yet.")
        return
    trades = [r for r in csv.DictReader(open("trades.csv"))
              if r.get("status") == "submitted"]
    if not trades:
        print("No submitted trades to score.")
        return

    try:
        settled = market_results()
    except Exception as e:
        print(f"Could not fetch settlements ({e}). Nothing written.")
        return

    rows, total_pnl, wins, losses = [], 0.0, 0, 0
    for t in trades:
        ticker = t.get("ticker", "")
        result = settled.get(ticker)
        if not result:
            continue  # not settled yet
        side = (t.get("side") or "yes").lower()
        try:
            count = int(float(t.get("count") or 1))
            cost = int(float(t.get("limit_cents") or 0))
        except (TypeError, ValueError):
            continue
        won = (side == result)
        pnl = (count * (100 - cost) if won else -count * cost) / 100.0
        total_pnl += pnl
        wins, losses = wins + won, losses + (not won)
        rows.append({"settled_checked_utc":
                     datetime.now(timezone.utc).isoformat(timespec="seconds"),
                     "placed_utc": t.get("placed_utc", ""),
                     "ticker": ticker,
                     "subtitle": t.get("subtitle", ""),
                     "side": side, "count": count, "cost_cents": cost,
                     "model_pct": t.get("model_pct", ""),
                     "edge": t.get("edge", ""),
                     "result": result,
                     "won": "WIN" if won else "LOSS",
                     "pnl_dollars": f"{pnl:.2f}"})

    with open("results.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else
                           ["settled_checked_utc", "placed_utc", "ticker",
                            "subtitle", "side", "count", "cost_cents",
                            "model_pct", "edge", "result", "won",
                            "pnl_dollars"])
        w.writeheader()
        for r in rows:
            w.writerow(r)

    n = wins + losses
    print("=" * 46)
    print(f"SCOREBOARD  ({n} settled bets)")
    print(f"  Wins: {wins}   Losses: {losses}   "
          f"Win rate: {(wins / n * 100) if n else 0:.0f}%")
    print(f"  Total P&L: ${total_pnl:+.2f}")
    print(f"  Bets until sizing decision (100): {max(0, 100 - n)}")
    print("=" * 46)
    if n >= 100 and total_pnl > 0:
        print("MILESTONE: 100+ settled bets, positive P&L. "
              "Time to look at raising BET_DOLLARS.")
    elif n >= 100:
        print("MILESTONE: 100+ settled bets, P&L not positive. "
              "Fix the model before raising BET_DOLLARS.")


if __name__ == "__main__":
    main()
