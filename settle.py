"""Weather-Bot: settlement grader. Reads trades.csv, asks Kalshi how each
market actually settled, writes graded rows to results.csv.

AUDITED + FIXED Aug 6 2026:
- results.csv now ALWAYS carries city + action + result + ticker, because
  calibration.py reads settled bets to pin the day's true high (the
  settlement is the only thermometer that pays). Missing city fields
  previously made those rows useless to calibration.
- Only grades markets whose Kalshi status is settled -- no more guessing
  from price. The result field comes from the exchange, nowhere else.
- Rows already graded are never re-graded (idempotent on re-run).
- Defensive column reads: works with old and new trades.csv layouts.
"""

import base64, csv, json, os, re, time, urllib.request
from datetime import datetime, timezone

from cities import SERIES_TO_CITY
from csvio import appender

TRADES = "trades.csv"
RESULTS = "results.csv"
FIELDS = ["graded_utc", "ticker", "city", "action", "cost_cents",
          "count", "market_result", "result", "pnl"]

BASE = "https://api.elections.kalshi.com"
KEY_ID = os.environ["KALSHI_API_KEY_ID"].strip()

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


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


def ksigned(path):
    ts = str(int(time.time() * 1000))
    sig = key.sign((ts + "GET" + path.split("?")[0]).encode(),
                   padding.PSS(mgf=padding.MGF1(hashes.SHA256()),
                               salt_length=padding.PSS.DIGEST_LENGTH),
                   hashes.SHA256())
    req = urllib.request.Request(BASE + path, headers={
        "KALSHI-ACCESS-KEY": KEY_ID,
        "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode(),
        "KALSHI-ACCESS-TIMESTAMP": ts,
        "User-Agent": "weather-bot-personal"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def city_from_ticker(ticker):
    series = (ticker or "").split("-")[0].upper()
    return SERIES_TO_CITY.get(series, "")


def load_graded():
    """Set of (ticker, action) already in results.csv."""
    done = set()
    if os.path.exists(RESULTS):
        with open(RESULTS) as f:
            for r in csv.DictReader(f):
                act = (r.get("action") or r.get("side") or "").upper()
                done.add((r.get("ticker", ""), act))
    return done


def load_trades():
    """Ungraded submitted trades from trades.csv, defensively read."""
    out = []
    if not os.path.exists(TRADES):
        return out
    with open(TRADES) as f:
        for r in csv.DictReader(f):
            tick = (r.get("ticker") or r.get("market") or "").strip()
            if not tick:
                continue
            act = (r.get("action") or r.get("side") or "").upper()
            if act not in ("YES", "NO"):
                continue
            # trades.csv names this column limit_cents (the price the
            # order was placed at). It was missing from this chain, so
            # every graded bet scored with cost 0: wins paid a full 100c
            # and losses cost nothing. Real money, fictional scoreboard.
            cost = (r.get("cost_cents") or r.get("price_cents")
                    or r.get("limit_cents") or r.get("cost") or "")
            qty = r.get("count") or r.get("qty") or r.get("contracts") or "1"
            out.append({"ticker": tick, "action": act,
                        "cost_cents": cost, "count": qty,
                        "city": (r.get("city") or "").strip()
                                or city_from_ticker(tick)})
    return out


def main():
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    graded = load_graded()
    trades = load_trades()
    pending = [t for t in trades
               if (t["ticker"], t["action"]) not in graded]
    print(f"{len(trades)} trades on file, {len(pending)} not yet graded")

    wrote = 0
    with appender(RESULTS, FIELDS) as w:
        seen_this_run = set()
        for t in pending:
            k = (t["ticker"], t["action"])
            if k in seen_this_run:
                continue
            seen_this_run.add(k)
            try:
                data = ksigned(f"/trade-api/v2/markets/{t['ticker']}")
            except Exception as e:
                print(f"{t['ticker']}: fetch failed ({e})")
                continue
            m = data.get("market", {})
            status = (m.get("status") or "").lower()
            result = (m.get("result") or "").lower()
            if status not in ("settled", "finalized") or result not in \
                    ("yes", "no"):
                continue   # not settled yet -- next run
            won = (result == t["action"].lower())
            try:
                cost = float(t["cost_cents"])
            except (TypeError, ValueError):
                cost = 0.0
            try:
                n = float(t["count"])
            except (TypeError, ValueError):
                n = 1.0
            pnl = round(((100 - cost) if won else -cost) * n / 100.0, 2)
            pnl = pnl + 0.0        # normalise -0.0 -> 0.0
            w.writerow({"graded_utc": stamp, "ticker": t["ticker"],
                        "city": t["city"], "action": t["action"],
                        "cost_cents": t["cost_cents"], "count": t["count"],
                        "market_result": result.upper(),
                        "result": "WIN" if won else "LOSS",
                        "pnl": pnl})
            wrote += 1
            print(f"{t['city'] or t['ticker']} {t['action']} "
                  f"@ {t['cost_cents']}c -> {result.upper()} "
                  f"= {'WIN' if won else 'LOSS'} ({pnl:+.2f})")
    print(f"graded {wrote} newly settled bets")


if __name__ == "__main__":
    main()
