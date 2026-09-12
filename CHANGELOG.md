# CHANGELOG

- 2026-09-12 (night): THE TAIL-STRIKE FIX (owner catch). The owner
  read the Austin card — top bracket "98° or below" at 31.7% under a
  101.2° median — and said something was wrong with the temperature.
  It was an off-by-one on the money path: Kalshi tail markets carry
  EXCLUSIVE strikes ("98° or below" has cap_strike=99), which
  settlements.py documented Aug 20 2026 but scanner.py still trusted
  raw (its subtitle fallback had gone dead when Kalshi started
  filling tail strikes). Every tail bracket over-counted a full
  degree of members, double-counted against the neighboring bracket:
  Austin's honest tail count was 20.7%, not 31.7%; "107° or above"
  showed 20.7% against an honest 9.8%. parse_bracket is now
  subtitle-first with a corrected strike fallback; edges.csv floor/
  cap log inclusive degrees from today. Gates held throughout — no
  money moved on phantom votes. Same commit, display only: when GFS
  and ECMWF medians split ≥3°F, the card's WHY line now says so with
  both numbers (Austin that morning: GFS ~106°, ECMWF ~100° — ECMWF,
  NWS and ICON were right, the station peaked ~100°), and explains
  that a split pool can honestly put the biggest single group in a
  wide edge bracket away from the median. Full write-up in CLAUDE.md.

- 2026-09-12 (night): THE WALLET LINE (owner request). The owner
  moved the cash to a sportsbook because nothing on the board showed
  the account's spendable money; the day's San Francisco buy then
  bounced on "insufficient balance" — accurate, but too late to
  help. trader.py now writes balance.json (spendable cash +
  checked_utc) on every trading pass and the end-of-day sweep;
  account_check.py writes the fuller three-bucket picture and
  account.yml commits it, so the Run button refreshes the board
  after funding. The Station Board shows the number with its checked
  time, red under $1 with "fund the account or the bot buys
  nothing", and explains that the Kalshi app's home number includes
  money a new bet cannot spend. Display only: no money code reads
  balance.json, and it never joins the union-merge list.

- 2026-09-12: PER-MODEL BIAS — the two-humped-pool fix (owner
  decision). The owner caught New Orleans claiming 39% of members on
  "95° or above" against a 90.7° median and a 89–90° settlement the
  day before, and NYC picking a 1¢ bracket — the gates blocked every
  buy, but the votes were broken. Cause: the single per-station bias
  is learned from the pooled median, which ECMWF dominates 51:31, so
  at stations where the two models lean OPPOSITE ways (New Orleans:
  ECMWF ~4.4°F cold, GFS hot) the correction that fixed ECMWF shoved
  all 31 GFS members into a phantom extreme bracket. Fix:
  calibration learns a bias per (station, model) from the
  member_models tags (≥4 tagged settled nights, else that model
  falls back to the pooled bias) and calibrate_members shifts each
  member by its own model's number; bias_applied becomes the exact
  tagged record `pool:…|gfs:…|ecmwf:…` when tags are usable (scalar
  fallback and old rows unchanged). Replayed on the sick morning:
  New Orleans' "95° or above" fell 35% → 1% and the pool became one
  honest hump at 89–92. Widening, gates, sizing, scanner display —
  all untouched. Full write-up in CLAUDE.md.

- 2026-09-12 (evening): WHALE BOARD NAMES THE BET TYPE (owner
  request) — every Whale Watcher card now carries a chip saying what
  KIND of bet the whale made: MONEYLINE, SPREAD with the number,
  TOTAL with the line, or PROP (a prop card shows the full market
  question, since its subtitle alone — "Seth Lugo: 9+" — names the
  line but not the ask). Parsed structured-first so wording can't
  fool it: the series ticker and Kalshi's own floor_strike field
  decide before any title text; a market fitting no known shape is a
  PROP, never a guessed moneyline. whale_trades.csv grew a bet_type
  column (align() migrates the old rows; a blank sports row reads as
  MONEYLINE by construction — only winner/match series were ever
  watched — and weather rows stay blank on purpose, a bracket isn't
  a sports bet type). The board now shows ONE line per team + side +
  bet type — same-window bursts on the same market+side sum into one
  line ("26 bursts (3,969 fills)") so a moneyline whale and a spread
  whale on the same team can never share a line and a sliced whale
  no longer floods a sector; the CSV keeps every burst separately
  and grading is untouched. Research-only law unchanged.

- 2026-09-12 (evening): NFL COULD NEVER MATCH — KXNFLGAME's 2026-season
  event tickers carry date + team codes but NO game time
  (KXNFLGAME-26SEP13DALNYG, read off the whale tape the day the fixed
  whale watcher lit up), while the code matcher demanded an MLB-style
  4-digit start time in the ticker. Every NFL game since the season
  started went UNMATCHED — zero NFL_GAME rows ever logged — so no NFL
  favorite could reach the card, the parlay board, or the combos.
  Fix: match_event accepts the no-time format with the exact-code
  guarantee intact (block must equal AWAYCODE+HOMECODE, ticker date
  must equal the game's ET date; an NFL team never plays twice on one
  date — the names matcher's own justification; two candidates =
  loud refusal). MLB's timed matching and 30-minute doubleheader
  drift check are untouched, verified by regression test.

- 2026-09-12 (later): WHALE WATCHER WAS BLIND SINCE BIRTH — the owner
  called it ("hard to believe no one has bet a grand on football"),
  and they were right: Kalshi's 2026 field migration renamed the
  numbers the scanner read (volume → volume_fp fixed-point string,
  yes/no_price → *_price_dollars, count → count_fp), so every market
  parsed as volume 0, not one trade tape was ever read, and every
  run finished green in ~1.5 seconds having scanned nothing —
  whale_trades.csv was never even created. Proven from the Sep 10
  probe's raw market dump (no old fields present) and the Kalshi API
  docs. Fix: new field names first with old names kept as fallback
  (the scanner.py pattern), units normalized to cents, fractional
  contracts handled, a belt-and-suspenders time filter on the tape,
  and a new dead-feed tripwire: 50+ open markets with ZERO passing
  even the $250 weather volume bar turns the run RED — that exact
  silence was green for a full CFB Friday night. whale_watcher.py +
  CHANGELOG, one commit.

- 2026-09-12: SETTLEMENTS FALSE ALARM FIXED (the swoop_pulse lesson,
  applied) — the watchdog judged the settlements feed by checked_utc
  in settlements.csv, but that timestamp moves only when Kalshi
  actually finalizes a new settlement (the don't-churn rule). On
  Sep 11-12 the exchange sat ~20 h without finalizing any of the 20
  cities' events while settlements.yml ran green every 2 hours, and
  the board showed a red SETTLEMENTS STALE alarm that no Run press
  could clear (the owner pressed it; nothing happened — correctly).
  Cure: settlements.py now writes settlements_pulse.json every run
  (the job's heartbeat, full rewrite, display-only, never
  union-merged), and the watchdog alarms on a dead PULSE, not a quiet
  CSV; a healthy job with a >30 h quiet CSV is a plain-English note
  ("Kalshi hasn't settled yet"), never an alarm. The old CSV check
  survives as the day-zero fallback. settlements.py + watchdog.py +
  CLAUDE.md, one commit.

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
