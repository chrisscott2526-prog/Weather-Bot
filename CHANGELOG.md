# CHANGELOG

- 2026-09-17: THE NWS 1 PM LOG (owner request: "a log of what NWS
  would purchase — what bracket — at 1 o'clock in the afternoon...
  is NWS more accurate later in the day?"). New nws_afternoon.py +
  nwsafternoon.yml: once per city per day, in each city's own
  13:00–14:59 local window, log the live NWS same-day number
  (model_lab.nws_high, shared code) and the live Kalshi bracket it
  lands in (judge.py's matcher — unmatched = loud skip, never a
  guess), then grade by settlement with brackets_off distance. The
  grade printout compares night-before vs morning-same-day vs 1 PM
  NWS on the same graded city-days. New nws_afternoon_picks.csv /
  nws_afternoon_results.csv (union-merged, no pnl). RESEARCH ONLY —
  nothing that trades, scans, or calibrates reads them; no secrets.
  nws_afternoon.py + nwsafternoon.yml + .gitattributes + CLAUDE.md,
  one commit; sandbox-verified (window selection, bracket matching
  incl. tails, dedupe, dead-feed red exit, grading + idempotence).
  Same morning (owner's sharpened ask: "that handful that it is
  correct on late in the day and still has a good price — may not
  be the seven"): each capture also fetches the bracket's LIVE
  Kalshi ask at capture time (live_ask, unauth single-market read,
  settlements.py's 429-paced pattern; blank + note on a dead call,
  capture stands), and the grade printout adds the per-city table
  (hit rate, median capture-time ask) and the ask-bucket record.

- 2026-09-15: SPORTS CARD: EARLY LINES + DK COLUMN + SCHEDULE FIX
  (owner report: card stale all day; wants NFL days early + payout
  comparison vs their books). sports.yml 2 → 4 cron slots + a sports
  tripwire in the poller relay (dispatch when the card is ~5h stale
  in 13:35-23:30 UTC). NFL fetch window 30h → 78h (credit-free) with
  a new EARLY LINES card section (sharps' 70%+ favorites 30-78h out,
  DK price + current Kalshi ask); early games feed NO board or gap
  card and skip prop calls; leg lab logs them (hours_to_start grades
  early-vs-late). DraftKings' own American odds now print on parlay
  legs, the props menu, and the early section — same payload, zero
  extra credits, display only. Polymarket/PrizePicks staged pending
  probe verification. sports_scanner.py + sports.yml + poll.yml +
  CLAUDE.md, one commit; sandbox-verified.

- 2026-09-15: THE JUDGE LANE (owner request: "why don't you just
  pick it... I feel like we're trying to build another you"). Claude
  itself now picks brackets ON PAPER: a claude.ai routine fires a
  fresh session at 14:30 + 16:30 UTC daily; each fire grades pending
  picks, reads the full briefing (judge.py brief: fresh reading,
  high so far, yesterday's settlement, every model's number, live
  brackets + the ensemble's pick), judges one bracket per in-window
  city (benched included, skips always allowed and loud), logs
  validated picks to judge_picks.csv, grades by settlements into
  judge_results.csv — judge vs ensemble on the same city-days.
  judge.py is dumb plumbing; the judgment lives only in the session.
  ADVISORY/PAPER ONLY: nothing that trades, scans, or calibrates may
  read the judge CSVs; promotion is an owner decision on the record.
  DST note: shift fires to 15:30/17:30 UTC when daylight saving ends
  Nov 1 2026. judge.py + CLAUDE.md + .gitattributes, one commit.

- 2026-09-15: THE SUB-HOURLY FEED TEST (owner-approved side test).
  The poller now also logs each station's FULL observation feed
  (hourly METARs + between-hour SPECI specials) from the same
  api.weather.gov endpoint, list form, to a new research-only CSV
  `obs_feed_log.csv` — deduped by (station, obs_time), floored,
  per-station failures print and skip, union-merged. Born from a
  writeup the owner shared; its two factual errors are corrected in
  CLAUDE.md (settlement judge is TWC per the Aug 23 audit, and its
  KORD/KDAL examples are the wrong stations for our markets). The
  test: do our stations file temperature-bearing specials our
  15-minute /latest poll misses, and would they have raised the
  day's running max when it mattered (the Philadelphia $10 shape)?
  NOTHING on the money path reads it — promotion into temps_log/
  the reality floor needs a walk-forward backtest and an owner
  decision, same bar as the 6-hour-max log. poller.py + CLAUDE.md +
  .gitattributes, one commit.

- 2026-09-14 (late night): THE EVERY-SPORT PROPS WIDENING + THE DIAL
  (owner requests). Four pieces, one commit: (1) THE DIAL -- the
  props menu now shows a SAFE column beside each player's strong
  bar: the deepest bar he's a 90%+ favorite to clear
  (PROPS_SAFE_PROB), the owner's dial-it-back-for-safety habit
  printed as a measured number. (2) Pitcher strikeouts join the
  props pool/menu under the same OVER-only 70 floor (the shelf was
  already scanned; only the pool append is new). (3) Player props
  join the COMBO board, with the one-leg-per-game law made explicit
  across pools (combo_sports_legs: a team's moneyline and its own
  QB's yards never share a stack). (4) CFB + NBA prop verification
  staged in the probe (odds keys + KXNCAAF*/KXNBA* live inventory);
  NBA verifies when October's prop markets open. MLB BATTER props
  stay OFF on recorded evidence: Kalshi's series are rich but the
  odds feed returned 1 book for batter markets (run 117) and one
  book is not a consensus -- recheck by probe near game time.
  Advisory-only law unchanged everywhere.

- 2026-09-14 (night, follow-up): THE PROPS MENU (owner request). The
  card now lists EVERY qualifying player prop, grouped by game --
  the player's name, the DEEPEST bar he's still a 70%+ favorite to
  clear, and the sharps' % -- so the owner can pick freely at their
  own book, including several props from one game. The
  one-leg-per-game law was only ever about the card's own stacks
  (their multiplied number must stay honest); the menu says the
  same-game-parlay caveat once, plainly. Display only: no new data,
  no new files, no gate changes. sports_scanner.py + CLAUDE.md.

- 2026-09-14 (night): THE PROPS LADDER (owner request). A player-prop
  version of the parlay board: four NFL prop shelves verified live
  the same day via three probe runs (KXNFLPASSYDS / KXNFLREC /
  KXNFLRECYDS / KXNFLRSHYDS -- anatomy identical to KXMLBKS -- and
  the odds plan's base + _alternate player markets, 6 sharp books,
  alternate points landing exactly on Kalshi's strikes). The sharps
  price every leg (never a homemade stats model); over-only
  alternate ladders are de-vigged by each book's own measured
  main-line overround, never a guessed haircut; the ladder takes ONE
  prop leg per game, strongest only, because same-game props move
  together and stacking them (like the app's own slips do) wears a
  multiplied number that isn't real. Floor 70 (the quality
  tightening), rungs 2-4, OVER legs only, ids <day>-PROPS<n>, rows
  in parlay_picks.csv, graded by Kalshi settlement via grade_stacks
  unchanged. Prop shelves also feed the gap card through the normal
  gates -- props were always the constitution's priority shelf.
  Cost stated: ~2,000-2,500 odds credits/month worst case on the
  20K plan. ADVISORY ONLY, permanent rule unchanged.
  sports_scanner.py + sports_probe.py + CLAUDE.md, three commits
  (probe evidence first, then the build).

- 2026-09-14 (later): THE LEG LAB (owner question -> evidence-first
  build, the Model Lab pattern). The owner's question: "you can't
  tell who wins just from the market's percent -- an 80%er can lose
  and a 60%er can win. What else could we look at, and in what
  scenario would a 60% team still belong?" Nobody can call WHICH
  favorite loses, but the QUALITY of a favorite's number might be
  measurable -- so every parlay-shelf favorite from 55% up (below
  the 70 board floor on purpose, so the banned bands keep building
  a paper record) now logs the signals already in hand at scan
  time: the sharp books' own low/high numbers for the pick (do the
  experts agree with each other), the live Kalshi YES bid (the
  weather legs' dual-expert pattern applied to sports, logged not
  gated), and hours-to-start (freshness -- the day-of lesson,
  measured for sports). Graded per leg by Kalshi settlement into
  leg_research_results.csv, WIN/LOSS/VOID, no pnl. No new feeds, no
  extra API calls, ZERO change to any board or card. RESEARCH ONLY
  (Model Lab law): nothing that boards or trades may ever read it.
  Promoting any signal into a gate -- including re-admitting a 60%er
  that passes every signal -- is an owner decision made on ~100+
  graded legs. sports_scanner.py + CLAUDE.md + .gitattributes, one
  commit.

- 2026-09-14: THE QUALITY TIGHTENING (owner decision). Nothing under
  a 70% win chance boards on the parlay or combo ladders anymore:
  PARLAY_LEG_MIN_PROB 60 -> 70 and PARLAY_BOOST_FLOOR 65 -> 70, one
  commit (sports_scanner.py + CLAUDE.md; the card text reads the
  constants so it updates itself). The owner's words after the
  Chargers weekend: the boards are "full of 60%ers... it's not about
  quantity it's about quality." Evidence recorded honestly both
  ways in CLAUDE.md: the banned 60-69% bands were 11W-3L at leg
  level and the Chargers leg that sank the weekend was stated at
  80% -- the floor buys concentration, not upset protection; what
  the record did convict is stack depth (5+ leg rungs 0W-5L), which
  a 70 floor thins naturally. The weather dual-expert bar rides the
  same constant and is now 70/70 (backtest through Sep 14: 6W-1L on
  7 legs, vs 20W-2L on 22 legs at 60/60). Both results CSVs keep
  grading stated % vs hit rate; reviewing the floor is an owner
  decision on that record.

- 2026-09-13: BOOSTER STACKS on the parlay board (owner decision).
  The owner typed the whole locks ladder into their book and watched
  the payout barely move -- two 95% legs multiply to 90%, $1.09
  fair, "no money in them" -- while the record showed 2-leg locks
  hitting and 4-leg rungs barely ever. The board now builds two
  ladders from the same sharps pool: the LOCKS ladder (unchanged)
  and BOOSTER stacks -- the strongest 90%+ lock anchoring the
  strongest 65-89% favorites, up to 6 legs (~$2-5 fair). The 65%
  floor is the owner's boundary on the caliber of shots, picked from
  the 60/65/70 options with the math for each: every booster is
  still the sharps' clear favorite; an underdog never boards at any
  payout (the 9-21 edge-first disease wearing a parlay slip). Rungs
  short of qualifying legs don't exist -- never padded. Same CSVs,
  same settlement grading (ids <day>-BOOST<n>), pool floor and combo
  board untouched. Injury feeds discussed and deliberately deferred
  by the owner pending investigation.

- 2026-09-13: WHALE STANDINGS on whales.html (owner request --
  "what do we do with that data after today?"). The burst log never
  resets; every burst grades at settlement forever. The board now
  opens with per-sector standings: burst record, the matched-dollar
  test ($1-for-$1 at the whale's own price -- the honest number,
  since hit rate flatters favorites: CFB's first days ran 64% hits
  yet -1.0% matched), and the record split by how early the money
  landed (3-days-early CFB money opened 2-5 -- early is not smart so
  far; the $3.8M Oklahoma split proved big money sits on BOTH sides
  and the $2.0M YES side lost). Computed from the two whale CSVs at
  board build, research-only law unchanged.

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
