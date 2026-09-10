# CHANGELOG

- 2026-09-10 (later): THE LEAGUE EXPANSION — the sports card and the
  combo/parlay pools now cover college football (KXNCAAFGAME) and the
  NBA (KXNBAGAME), plus tour-level tennis via run-time tournament keys
  (KXATPMATCH/KXWTAMATCH) — all three hand-verified against live
  markets by two probe runs the same day. New name-based event
  matcher for series whose tickers carry no game time; unmatched
  names skip loudly, never mismatch. Golf deliberately OFF (no
  matchup odds on the feed, KXGOLFTOURN empty at verification).
  Stated cost: the free Odds API tier (106/500 credits left) will run
  dry under the wider card — owner decides on the upgrade; a dry key
  fails RED, never silently. Weather money lane untouched.

- 2026-09-10: THE COMBO BOARD (owner request: "high paying combos,
  combining any sector") — cross-sector stack ladder on the sports
  card: the parlay board's sharps favorites + weather legs from the
  money lane's own morning picks, up to 8 legs, highest fair payout
  first. Weather legs pass a dual-expert rule (ensemble ≥60% of
  members AND live Kalshi bid ≥60¢, the LOWER number stated —
  backtest 14W-2L while stating ~66%); benched cities excluded
  fail-closed. New combo_picks.csv / combo_results.csv (union-
  merged, HIT/MISS by Kalshi settlement, no pnl column — same laws
  as the parlay pair). ADVISORY ONLY, permanent rule unchanged.
  sports_scanner.py + CLAUDE.md + .gitattributes, one commit.

- 2026-08-30 (evening): END-OF-DAY SWEEP — trader.py --sweep-resting +
  morning.yml runs it when the buying day ends; closes the unfilled-
  resting-order hole (stale fills + phantom scoreboard rows). Audit
  also confirmed: window stays 9-11 AM (later hours show no edge and
  no in-band inventory), band stays 45-60c (review Sep 11), and all six
  checkable insufficient-balance orders would have won (funding note to
  owner).

- 2026-08-30: THE CITY BENCH — Oklahoma City (0W-7L) and Dallas (1W-9L)
  benched from real-money buys on scoreboard evidence; still scanned and
  logged on paper. scanner.py + index.html mirror, one commit. Review
  ~Sep 11 with the band trial.

- 2026-08-30: Added STATUS.md, DECISIONS.md, CHANGELOG.md (documentation
  only — no code or trading logic changed).
