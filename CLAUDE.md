# CLAUDE.md — Weather-Bot Operating Manual

**Read this before touching anything.** This file is the permanent operating
manual for every future session. The rules below were paid for with real
money. Do not "improve" them away.

## Who you're working for

The owner is **not a programmer** and works from an **iPad**.

- Explain everything in plain English. No jargon walls.
- Prefer **complete-file changes** over fragments or diffs — the owner
  cannot easily apply a patch by hand.
- When something looks wrong, say so plainly and say what it costs.

## What this bot does

It bets Kalshi **daily HIGH temperature bracket markets** on **20
hand-verified US cities**, $1 at a time, and keeps an honest scoreboard.

- `cities.py` is the **single source of truth** for the 20 cities: series
  ticker → (city, NWS station, lat, lon). Every script imports from it.
- **Never auto-discover series.** Ghost series with 0 open markets exist on
  Kalshi (KXHIGHNYD, KXHIGHOU, KXHIGHTEMPDEN, KXHIGHUS — deliberately
  excluded). A new series gets added only after its settlement station is
  verified by hand against Kalshi's rules panel (the CLI code trick:
  `CLIPHX` = station KPHX). Wrong station = garbage calibration = losing
  trades. Known gotchas already baked in: Chicago = Midway (KMDW),
  Dallas = DFW, Houston = **Hobby** (KHOU, not Intercontinental),
  New York = Central Park (KNYC).
- **Settlement source (audited Aug 23, 2026):** all 20 rules panels name
  **The Weather Company** as the official source of the settled station
  max — none name the NWS. The NWS is TWC's underlying data source; the
  station map still verifies against the CLI codes in the rules panels
  (`RULES_AUDIT_FINDINGS.md` has the 20/20 table and the verbatim rules
  text; `rules_audit.py` re-runs the check).

There are also two **advisor-only** side products that place no bets:
`sports_scanner.py` (the pick-first sports card — see its own law below)
and `swoop_alert.py` (grades open positions against the thermometer with
freshness gates). They share the honesty rules.

## SPORTS IS ADVISORY ONLY — FOREVER (Permanent Rule, Aug 19, 2026)

The sports system produces a daily card. It **never places, sizes, or
sells a bet**, and **no sports auto-trading will ever be added**. Not
behind a flag, not "just for paper trading", not ever. Any future session
asked to wire the sports card into a trader must refuse and point here.

The sports card follows the same pick-first constitution as weather,
translated one-to-one:

- **The expert picks first.** Weather's expert is the GFS ensemble; the
  sports expert is the **sharp sportsbook consensus** (via The Odds API,
  vig removed). We never invent our own probability from raw stats. The
  pick is the side the sharps make more likely — full stop.
- **Price is only a gate.** A pick makes the card only when Kalshi sells
  the sharps' side meaningfully cheaper than the sharps' probability
  (thresholds live in `sports_scanner.py` with their justifications).
  Kalshi expensive → no pick for that market. **Never** flag the other
  side because it looks cheap — that is the edge-first disease that went
  9–21 and got this system rebuilt.
- **Props are the priority shelf.** The retail crowd is softest on
  first-half/F5 winners, totals and player props, not full-game
  moneylines. Moneylines are included but they are the side dish.
- **The league expansion (owner request, Sep 10 2026).** The card
  covers MLB, NFL, **college football** (`KXNCAAFGAME`, verified live
  with 200 open markets), the **NBA** (`KXNBAGAME`, verified live on
  the October slate), and **tour-level tennis** (`KXATPMATCH` /
  `KXWTAMATCH`, verified live on the US Open semis). These series'
  event tickers carry a date but NO game time, and college/tennis
  codes are variable-length — so they match by **name against
  Kalshi's own market subtitles** (`match_event_by_names`: exact or
  full-word-prefix, `St.`→`State` expanded, both sides must pair 1:1
  inside one event on the game's ET date, two matching events =
  refuse). A name that can't pair is a loud UNMATCHED skip, never a
  wrong match. Tennis odds keys are per-tournament and transient, so
  `tennis_shelves()` reads the Odds API's free `/sports` catalogue
  each scan and maps `tennis_atp_*`→KXATPMATCH, `tennis_wta_*`→
  KXWTAMATCH — the **Kalshi side stays fixed and hand-verified**, so
  this is not series discovery. **Golf is deliberately OFF**: the
  odds feed carries only tournament-winner outrights (favorites
  ~20–30%, below every bar), and `KXGOLFTOURN` had zero open markets
  to verify — golf joins only when a matchup-odds source exists AND
  the series is verified live. **The cost, said plainly:** the free
  Odds API tier is 500 credits/month and was at 106 remaining when
  this shipped; the wider card burns ~8/scan (~480/month at 2
  scans/day), so the free key will run dry — the card then fails RED
  (dead-feed law), never silently. Upgrading the Odds API plan is the
  owner's lever. **And it played out exactly that way (Sep 13 2026):**
  the free key hit OUT_OF_USAGE_CREDITS, the card failed RED as
  designed, and the owner pulled the lever — upgraded to the paid
  **20,000-credits/month** plan (~$30/mo) and replaced the
  `ODDS_API_KEY` secret in GitHub the same day. Probe verified live:
  `used=0 remaining=20000`, props included. No code changed for the
  rotation — the workflows read the secret by NAME, so a new key
  saved under the same name links itself through everything. At ~8
  credits/scan the new plan has ~40× headroom, so `CREDIT_RESERVE`
  in `sports_scanner.py` should never bind; if the CREDIT GUARD
  message ever prints again, check the plan's renewal (and the
  empty-secret scar below) first.
- **Series are hand-verified, never substring-matched.** Every Kalshi
  series ticker the scanner reads is whitelisted by hand after a human
  reads the series title. `sports_probe.py` (run `sports.yml` with
  `probe=true`) prints the live inventory to read from. Substring
  matching is what swept inning props and player-signing markets into
  the old moneyline card.
- **Settlement truth grades the card.** Picks are graded only by
  Kalshi's own `result` field once the market settles — never by score
  feeds, never by guessing from price. Same law as `settle.py`.
- The scoreboard (`sports_results.csv`) exists to answer exactly one
  question: **is this card worth listening to?** It was wiped on
  Aug 19, 2026 when the strategy changed — old edge-era rows graded a
  dead rule and would poison the new record.
- **The parlay board (owner request, Sep 8 2026)** is a second section
  on the same card answering a different question: not "what's
  mispriced" but "who are today's most likely winners, so the owner
  can stack them at their own sportsbook". Its laws: legs are the
  sharps' strongest **full-game/full-match moneyline favorites only**,
  from any league on the card — the shelves marked `parlay=True`
  (`PARLAY_LEG_MIN_PROB = 70`%+ de-vigged since Sep 14 2026, the
  quality tightening below; 60 from Sep 8–14 — F5/totals stay off,
  and props stay off the MONEYLINE ladders; the separate PROPS
  ladder, Sep 14 2026 below, carries player props under its own
  one-leg-per-game law; legs must be simple enough to stack
  honestly); **Kalshi's price
  plays no part in choosing a leg**, but every leg must match a
  hand-verified Kalshi market so the board is graded by Kalshi's own
  `result` (a favorite that can't be graded never makes the board);
  the combined chance is the plain product of the legs (one leg per
  game by construction, so independence holds) and the card states it
  plus the fair no-vig payout; **`parlay_results.csv` records
  HIT/MISS only, never a dollar P&L** — we cannot know what the
  owner's book pays a parlay, and inventing a payout would violate
  the honesty rules. The scoreboard question is calibration: stated
  combined % vs actual hit rate. The board never bets — the permanent
  advisory-only rule covers it word for word.
  **The booster stacks (owner decision, Sep 12 2026).** The owner
  typed the locks ladder into their own book and watched the payout
  barely move (two 95% legs = 90% combined = $1.09 fair — "no money
  in them"), while the graded record showed 2-leg locks hitting and
  4-leg rungs barely ever. So the board builds TWO ladders from the
  same sharps pool: the **LOCKS ladder** (top favorites top-down,
  unchanged) and the **BOOSTER stacks** — the strongest 90%+ lock as
  anchor plus the strongest **70–89%** favorites, up to 6 legs
  (`PARLAY_BOOST_FLOOR = 70` since Sep 14 2026; 65 was the owner's
  Sep 12 call from the 60/65/70 options — the quality tightening
  raised it with the pool floor, so the two floors now coincide).
  Every booster is still the sharps' CLEAR FAVORITE to win its game
  — a leg the sharps call an underdog never boards, at any payout
  (the 9–21 edge-first disease wearing a parlay slip). A rung short
  of qualifying legs doesn't exist; never pad with a weaker leg.
  Grading is unchanged: same CSVs, same HIT/MISS-by-settlement, ids
  `<day>-BOOST<n>`, and the calibration question (stated % vs hit
  rate) now judges both ladders.
  **THE QUALITY TIGHTENING (owner decision, Sep 14 2026).** The
  owner's words after the Sep 13–14 weekend card: the boards are
  "full of 60%ers", one lost leg (the Chargers) sat on every stack
  and sank them all, and "it's not about quantity it's about
  quality" — nothing under 70% boards anymore, anywhere.
  `PARLAY_LEG_MIN_PROB` 60 → 70 and `PARLAY_BOOST_FLOOR` 65 → 70,
  one commit. The evidence at decision time, stated honestly both
  ways: leg-level grading (outcomes pinned from the graded stacks)
  had the 60–64% band at 5W–2L and 65–69% at 6W–1L — the bands being
  banned were not the proven killers, and the Chargers leg itself
  was stated at 80%, above the new bar (an 80% favorite loses one
  time in five; no floor stops that). What the record DID convict is
  depth: 5+ leg parlay rungs went 0W–5L and 4-leg rungs 6W–8L, and a
  70 floor thins the pool so deep rungs mostly stop existing — the
  concentration the owner asked for. The dual-expert weather bar
  rides the same constant, so it moved to 70/70: rerunning the
  backtest through Sep 14 at 70/70 gave 6W–1L on 7 qualifying legs
  (vs 20W–2L on 22 legs at 60/60) — far fewer legs, each stronger.
  Both results CSVs keep grading stated % vs hit rate; reviewing the
  70 floor against that record is an owner decision, like every gate.
  **THE PROPS LADDER (owner request, Sep 14 2026).** The owner saw
  Kalshi's own app promoting pre-built player-prop slips (Herbert
  150+ passing yards, Kelce 3+ receptions...) and asked for a props
  version of the parlay board — betting on players, whose records
  exist, instead of only team moneylines. Built the same day, fully
  inside the constitution, after live probe verification (sports.yml
  runs 117–119, log evidence in the shelf comments): four NFL
  player-prop shelves — `KXNFLPASSYDS` (37 open), `KXNFLREC` (156),
  `KXNFLRECYDS` (195), `KXNFLRSHYDS` (84), anatomy identical to
  KXMLBKS (`'Bo Nix: 160+'`, floor_strike 159.5) — matched to the
  Odds API player markets the paid plan verifiably carries (base
  keys = each player's two-sided main line, `_alternate` keys = the
  over-only ladders whose points land exactly on Kalshi's strikes;
  6 sharp books each). The laws: **the sharps price every leg** — we
  never build a probability from a player's raw stats (the books
  already price Tom Brady's whole history plus this week's injury
  report; a homemade stats model is the edge-first disease with
  extra steps); alternate-ladder vig is removed with each book's own
  MEASURED main-line overround (`consensus_player_points` — never a
  guessed haircut, and a book with no two-sided line for the player
  contributes nothing); **ONE prop leg per game, strongest only** —
  same-game props rise and fall together (a QB's yards and his
  receiver's catches are the same drives), so the app-style
  ten-legs-one-game slip wears a multiplied number that isn't real,
  and this board refuses to stack two legs from one game — that is
  what keeps the plain product honest; floor `PARLAY_LEG_MIN_PROB`
  (70, the quality tightening), rungs 2–4, OVER legs only, ids
  `<day>-PROPS<n>`; rows ride `parlay_picks.csv` and grade through
  `grade_stacks` by Kalshi settlement, unchanged. The prop shelves
  also feed the gap card through the standard `evaluate()` gates
  (props were always the constitution's priority shelf — the NFL
  finally has verified series for them). Cost, stated plainly: 8
  prop keys × up to 12 NFL events × 2 scans/day on slate days ≈
  2,000–2,500 credits/month worst case against the 20K plan.
  **The props menu (owner request, same day):** the card also lists
  EVERY qualifying prop, grouped by game — player's name, the
  deepest bar he's still a floor-clearing favorite to beat, the
  sharps' % — so the owner can pick freely at their own book,
  several from one game included (`build_props_menu_html`). The
  one-leg-per-game law governs only the card's own STACKS (their
  multiplied number must stay honest); it was never a limit on what
  the owner may bet, and the menu prints the same-game caveat once,
  plainly. **The dial (owner request, same night):** each menu line
  also shows a SAFE column — the deepest bar the player is a
  `PROPS_SAFE_PROB` (90%)+ favorite to clear — the owner's own habit
  of dialing a Kalshi prop ladder down a few rungs for safety,
  printed as a measured number. Display only; no gate changed.
  **The every-sport widening (owner request, same night):** pitcher
  strikeouts (the original prop shelf) now join the props pool/menu
  under the same OVER-only 70 floor; MLB **batter** props stay OFF
  on recorded evidence — Kalshi's series are rich (KXMLBHIT 85 open,
  KXMLBHRR 125) but the odds feed returned only **1 book** for
  batter hits/total-bases/RBIs (probe run 117) and one book is not a
  consensus (`MIN_BOOKS = 3`); recheck by probe, since book coverage
  can improve near game time. CFB and NBA player props are staged in
  the probe (odds keys + KXNCAAF*/KXNBA* inventory, `inventory_
  prefix`) — verdicts recorded from probe run 122, Sep 14 2026:
  **CFB player props do not exist on either side** (Kalshi has no
  KXNCAAF player-prop series — only team-level ones, all 0 open —
  and the odds feed returned zero CFB player markets), off until
  BOTH appear; **NBA is fully staged** — Kalshi already lists
  KXNBAPTS / KXNBAREB / KXNBAAST / KXNBA3PT plus the combo stats
  (all 0 open, season not started) and the odds feed already prices
  the Oct 20 opener's props (2 books, thickening expected near
  tip-off) — run the probe when October's markets OPEN and the
  shelves join same-day; each joins only after live two-sided
  verification, per the whitelist law. ADVISORY ONLY — the permanent
  rule covers it word for word.
- **The combo board (owner request, Sep 10 2026)** is the parlay
  board with every sector invited: one cross-sector stack ladder on
  the same card, mixing the sharps' favorites — full-game moneylines
  AND, since Sep 14 2026 (owner request), player props, with **ONE
  sports leg per game chosen across both pools**
  (`combo_sports_legs`: a team's moneyline and its own QB's yards
  are the same game's fortunes and never share a stack — the
  explicit form of the independence law that held by construction
  when the pool was moneylines only; 70%+ since the quality
  tightening, 60%+ before) — with **weather legs** — the money
  lane's own morning bracket picks. Its laws: a weather leg must pass the **dual-expert rule**
  — the ensemble puts ≥`PARLAY_LEG_MIN_PROB`% of members on the
  picked bracket AND Kalshi's **live** market bids at least the same
  number in cents (70/70 since Sep 14 2026; 60/60 before) — and
  states the **lower** of the two numbers (the ensemble's claim alone
  is proven overconfident: autopsy §4 had 55%+ claims delivering
  ~35%; the dual-bar backtest over Aug 21–Sep 8 at the original
  60/60 bar went **14W–2L (88%) while stating ~66%** — understate,
  never overstate). The bracket is
  always the ensemble's pick (pick-first law — never a bracket chosen
  for its price); benched cities never supply a leg (`BENCHED_CITIES`
  parsed from `scanner.py`'s source at run time, watchdog-style,
  fail-closed: unreadable = no weather legs at all); combos are built
  only when ≥1 weather leg qualifies (a sports-only stack is the
  parlay board's job — never log the same stack under two names); max
  8 legs; the only road to a higher payout is MORE real favorites,
  never longer shots. `combo_picks.csv`/`combo_results.csv` mirror
  the parlay pair plus a `sectors` column — same **no-pnl law** (no
  venue's combo payout is knowable; `fair_payout` = 1/combined prob
  is what a no-vig book would pay), same HIT/MISS-by-Kalshi-
  settlement grading (void legs drop out), same union-merge. Stated
  caveats, printed on the card: Kalshi itself has **no combo ticket**
  (buying each leg there pays each leg on its own, never the
  multiplied number), and weather legs in one air mass are not fully
  independent, so the plain product is an approximation the combo
  record must keep honest. Adding any OTHER sector (politics, econ,
  anything without a calibrated expert and a hand-verified series)
  is an owner decision that needs both of those first — Kalshi's own
  price is not an expert that can earn a stated edge, and no series
  ever joins by discovery. ADVISORY ONLY — the permanent rule covers
  it word for word; nothing that trades may ever read these files.

## THE STRATEGY IS PICK-FIRST (Law of Aug 6, 2026)

1. **Pick the bracket.** For each city and market date, the ensemble
   (GFS + ECMWF pooled since Aug 24 2026, ~82 members) votes: the
   bracket containing the **most ensemble members** is the pick.
   Full stop. Price plays **no part** in choosing it.
2. **Price is only a gate.** If the pick's YES ask is inside
   `MIN_PICK_COST..MAX_PICK_COST` (**45¢–54¢ since Sep 11 2026 — the
   cap trim, decided at the Sep 11 band review, see the trial section;
   45–60¢ Aug 30–Sep 11 — the accuracy tightening; 40¢–60¢ Aug 28–30;
   the floor history: 8¢ → 15¢ on Aug 24 2026 — see the accuracy
   rebuild — → 20¢ on Aug 28 2026 ("no long shots") → 40¢ that
   evening → 45¢ on Aug 30).
   Then buy is flagged.
   Outside the band → **NO BUY for that city that day. No substitutes.**
   Never fall back to a cheaper neighboring bracket — a week of babysitting
   proved the discounted second-favorite loses, and rolling out of it costs
   a sell loss, a premium re-entry, and two fees.
3. **Never rank by edge.** The old edge-ranking rule systematically bought
   the second-most-likely bracket at a discount. Right neighborhood, wrong
   house, over and over. Edge numbers are still *computed and logged* in
   `edges.csv` (`edge_yes`, `edge_no`, `edge_pick`) so the scoreboard can
   grade the old rule's hypothetical picks against the real ones — they
   **decide nothing**.
4. **Never bet NO.** The scanner and trader are YES-only. `TRADE_NO` was
   removed from the trader on purpose.
5. Additional seatbelts in `scanner.py` (paid for in losses — keep them):
   - `MIN_PICK_PROB = 40`: if even the top bracket has under 40% of
     members, the day is too uncertain — no bet. (35 from day one
     until Aug 30 2026 — the accuracy tightening, see its section.)
   - Under `MIN_PICK_COST` (40¢ during the band trial): the market is
     screaming we're wrong — believe it, don't "value-buy". (Floor
     raised 8¢ → 15¢ on Aug 24 2026: under-15¢ picks settled
     **0-for-10**. Raised 15¢ → 20¢ on Aug 28 2026: every settled bet
     under 20¢ stood **2 wins to 22 losses**. The owner's words: not
     interested in long shots — skip the bet instead. Raised again to
     40¢, with the cap trimmed 68¢ → 60¢, that same evening — the
     two-week band trial, see its own section.)
   - No ensemble members for a (date, city) → **SKIP loudly**.

## THE DAY-OF SWITCH (Aug 26, 2026) — OWNER DECISION

**Money moves only on the day of the bet, in each city's own
9:00–10:59 AM local window.** The owner called the race early, on
the standings (night: 29% wins, −33¢ per $1 over 105 settled bets;
morning/day-of: 62% wins, +87¢ per $1 over 13) plus weeks of watching
night-before picks fight the morning's own thermometer readings. Made
as an explicit owner decree with the sample size stated plainly — 13
day-of settles is early evidence, not proof, so the per-strategy
scoreboard keeps running and this decision is re-checkable against it.

How it works now:
- `trader.yml` (the night-before buyer) is **benched**: no schedule,
  manual dispatch only. Re-arming it is an owner decision.
- `morning.yml` is the only money lane. It is scheduled **every 30
  minutes, 13:07–18:37 UTC** (the Clock Fix, Aug 28 2026 — see its
  own section below; it was three single-shot runs before, and
  GitHub's unreliable cron kept missing whole coasts). Each run does,
  in one job: fresh station poll → window preflight → fresh same-day
  forecast → `scanner.py --strategy morning --window 9-11` →
  `trader.py --strategy morning --keep-resting` → commit → a step
  that turns the run RED if any order errored.
- The `--window 9-11` gate (scanner) buys a city only when its **local
  civil clock** reads 9:00–10:59 AM (`cities.TIMEZONES` +
  `cities.local_time`, IANA zones, DST-correct, hand-verified; never
  use settlements.csv's solar `utc_offset_hours` for this). By then
  the settlement station has reported 3–4 hourly morning readings
  (stations report ~10 minutes before each hour) and the same-job
  ensemble refresh has digested them. The dense schedule gives every
  city ~4 in-window chances, summer and winter (verified against IANA
  tzdata for both solstices); the fail-closed exposure check makes
  every repeat pass harmless. **The promise to the owner:** each city
  is bought — or loudly skipped with a reason on the Station Board —
  within about half an hour of 9:00 AM its own time.
- **Night forecasts and night scans still run.** Calibration learns
  from night forecast rows, and night `would_bet` rows keep a paper
  record — so the bench itself stays gradeable, and un-benching (or
  deeper changes) can be argued from settled evidence.

## THE RACE: NIGHT vs MORNING (Aug 20, 2026)

Two strategies run the same pick-first rules against the same markets,
and the scoreboard decides which one earns the money. **(Since the
Day-of Switch above, only the morning lane trades; the night lane
races on paper.)**

- **NIGHT** (the original): picks from the 23:00 UTC night-before
  forecast, bought at night-before prices. Everything that existed
  before Aug 20, 2026 is night — old CSV rows were backfilled
  `strategy=night`, and every reader treats a blank tag as night.
- **MORNING**: `morning.yml` (daily ~13:45 UTC, one job so the steps
  cannot run out of order) refreshes TODAY's ensemble
  (`forecast.py --today`), scans with `scanner.py --strategy morning`,
  trades with `trader.py --strategy morning --keep-resting`.

The laws of the race:

- **Same gates, both lanes.** MIN/MAX_PICK_COST, MIN_PICK_PROB, the
  sanity gap, the whitelist, the $1 sizing law — identical. Never
  loosen a gate for one strategy.
- **Forecast rows are told apart by timestamps, not a new column.**
  `csvio.is_morning_row` is the one true classifier: morning = fetched
  on its own `forecast_date` between 06:00–22:59 UTC. (Not just
  "same date" — a delayed nightly cron slips past UTC midnight and
  stamps the same date; the real file has dozens of those, and they
  are night rows.) Night scans load only night rows, morning scans
  only morning rows (no fresh morning row = SKIP, loudly).
  Calibration learns bias from night rows only — it corrects the
  night-before forecast and feeds both lanes; letting same-day rows
  in would quietly redefine "forecast error".
- **No double exposure.** One position per city per day TOTAL, both
  strategies combined — the trader's existing fail-closed exposure
  check + `MAX_PER_CITY_DAY=1` enforce it. A city the night strategy
  already owns today is off limits to the morning strategy. Night
  wins ties (it runs first).
- **Each trader executes only its own strategy's rows** (the
  `--strategy` filter), and the morning trader never cancels resting
  orders (`--keep-resting`) — the cancel-and-reprice sweep belongs to
  the night runs that placed them. (Since Aug 30 2026 evening the
  buying day ENDS with `trader.py --sweep-resting` — see the broom
  note in THE EXECUTION RELAY. --keep-resting still holds during the
  day.)
- **The tag flows everywhere:** edges.csv → trades.csv → results.csv,
  read by autopsy.py. The race's finish line is autopsy.md's
  night-vs-morning table: **profit per $1 risked, after fees**. Per
  the roadmap, the scoreboard promotes — neither lane gains sizing or
  loses gates without settled results.

## SIZING LAW

**$1 per bet** (`BET_DOLLARS = 1` in `trader.py`) until **100+ settled bets
in `results.csv` show positive P&L**. No exceptions, no matter how good a
pick looks. A pick that "can't lose" still gets $1.

Trader hard caps, all enforced in `trader.py` — do not loosen:
- `MAX_ORDERS = 5` orders per run, `MAX_RUN_DOLLARS = 10` per run.
- `MAX_PER_CITY_DAY = 1` position per city per day (counts existing
  positions and resting orders via the FAIL-CLOSED exposure check — if the
  account can't be read, **no trades are placed that run**).
- `MIN_COST, MAX_COST = 45, 54` — must always equal the scanner's gate.
  (Cap 60 → 54 on Sep 11 2026 at the band review, with the scanner's
  in one commit, as they always must.)
  (They were once 15/10, an impossible range that silently placed zero
  trades for days. Floor raised 8 → 15 on Aug 24 2026, 15 → 20 on
  Aug 28 2026, then the 40–60 band trial that evening, each time with
  the scanner's — the two moved in one commit, as they always must.)
- `SANITY_GAP = 60`: skip if model% and price disagree by more than 60
  points — that gap means bad data, not free money.
- Kalshi maintenance window 06:45–08:15 UTC is skipped (the API 503s).
- Contracts per bet = `max(1, 100 // cost_cents)` — i.e. roughly $1 spent
  whatever the price.

## HONESTY RULES

- **Never invent data.** No fake spreads, no guessed confidence, no
  placeholder temperatures. A missing forecast or observation means
  **SKIP, loudly** (print why), never a made-up row.
- Every temperature reading carries its **observation timestamp**
  (`obs_time_utc`). Downstream code must be able to refuse stale data;
  `swoop_alert.py` refuses readings older than 60 minutes for SWOOP tags.
- Daily highs are the **hourly METAR instrument reading so far** —
  Kalshi settles on **The Weather Company's reported station max**
  (per the rules panels, all 20 series, audited Aug 23 2026). TWC
  builds its number from the same NWS station observations, catches
  between-hour peaks our hourly reading misses, and warns of its own
  rounding/conversion differences. The two usually agree; they are not
  the same number. Our METAR boards are honest approximations and must
  never be presented as "what will settle."
- **Daily highs are computed, never stored** (Aug 21, 2026). `highs.py`
  computes them straight from `temps_log.csv` on every call, and every
  consumer (swoop board, Station Board, calibration, autopsy) goes
  through it — one source, one method. `daily_highs.csv` still exists
  but only as a derived summary the poller regenerates for human eyes;
  **no code reads it** (retirement candidate). See the scar below.
- **Settlement truth outranks any thermometer.** Kalshi's own `result`
  field is the only thermometer that pays. `settle.py` grades only markets
  Kalshi says are settled/finalized; `calibration.py` overrides the
  instrument reading whenever one of our own settled bets proves the high
  landed in a different bracket.
- Failures print and skip. An "ERROR" row with a blank date is a trap for
  every downstream reader (this exact trap poisoned `forecasts.csv` once).
- **A finished day's high is never answered from repo CSVs alone.** When
  asked what a day's high WAS (past tense, day complete), the poller's
  running max is a **floor, not the final** — it only samples hourly
  METARs, and the number that settles is TWC's station max (see the
  settlement-source audit above). The best fetchable public check is
  the NWS **CLI Daily Climate Report** for that station (published
  ~5:30 PM local) or weather.gov's station page; fetch it live if
  network access allows. If it can't be fetched, say plainly: "our
  last logged reading was X at [time], but the official high may be
  higher — check weather.gov." Never present the logged running max as
  the day's final high after the day ends.

## HISTORY — THE SCARS (do not repeat these)

- **The $60 Phoenix lesson (Aug 5, 2026).** Rounding invented a degree:
  42.2 °C → 107.96 °F displayed as 108.0 on a bracket edge. The poller now
  **floors to two decimals and never rounds up** (`c_to_f` in `poller.py`).
  The board must understate, never overstate. Also from the same audit:
  daily highs are filed under the **city's own calendar day** (longitude
  timezone estimate), not the UTC date.
- **CSV header drift caused repeated silent failures.** Whenever a data
  file is wiped or a writer changes columns, the header must be updated
  **in the same commit** as the writer change. Readers should read by
  column name and tolerate old layouts (`settle.py` and `calibration.py`
  do this deliberately).
- **Workflow rules** (`.github/workflows/*.yml`), all learned the hard way:
  - `git add -A` — never single-file `git add` (it silently drops sibling
    files the script also wrote).
  - Push via a **real retry loop** — pull-rebase, back off, try again,
    up to 4 times (see `poll.yml` or `settlements.yml` for the pattern) —
    15-minute polling means pushes race. The old one-liner fallback
    (`git push || (... git rebase --abort ...)`) was a trap: under the
    step's `bash -e`, `git rebase --abort` fails when no rebase is in
    progress and kills the recovery before it recovers. It lost a
    39-row settlements commit (Aug 20 2026) and turned the Aug 28 2026
    autopsy run red; all workflows now carry the loop.
  - Every job must carry `timeout-minutes`.
- **Sports whitelist (Aug 2, 2026).** Substring matching on series names
  swept in inning props and player-signing markets and reported fantasy
  40¢ "edges". Real moneyline edges are 2–5¢ and rare. Whitelist only.
- **Derived data lagging its raw source — twice (Vegas Aug 20,
  Minneapolis Aug 21, 2026).** The swoop board graded real positions
  from `daily_highs.csv`, a derived snapshot, while the raw readings in
  `temps_log.csv` already knew better: Vegas sat on 105.8° through a
  107.6° climb toward a 109° settlement; Minneapolis showed 77.0° while
  the Station Board showed 80.6° at the same moment. Three separate rots
  were found in the derived file: (1) its "age" was the timestamp of the
  *peak*, so a quiet afternoon made a current board look 10 hours stale
  (592–738-minute "ages" in `swoop_log.csv`) while a stale page could
  wear a fresh age; (2) rows before Aug 5 were filed under **UTC** dates
  — the regeneration found 63 wrong historical rows plus an entire
  missing day (Jul 18), including Phoenix's Aug-4 evening 107.6° filed
  under Aug 5 — the $60 incident's own residue; (3) as incremental
  state, one dropped commit or push race lost a peak **forever**.
  **THE LAW: any number displayed or graded on a money path comes from
  the rawest, freshest source available, and any two surfaces showing
  the same quantity must compute it from the same source, the same
  way.** Hence `highs.py`: highs are recomputed from `temps_log.csv` on
  every call (obs-time day attribution, freshness = age of the latest
  reading), `index.html` mirrors the same rule in JS, and
  `daily_highs.csv` is write-only human-readable output. Never
  reintroduce a stored derived file into a money or display path.

## HOW THE PIECES FIT (data flow)

```
forecast.py  (nightly 23:00 UTC)  GFS (31) + ECMWF (51) ensembles via
     |                            Open-Meteo, one call per model,
     |                            pooled (~82 members), calibrated
     |                            per-station -> forecasts.csv
     |                            (forecast.yml has its OWN concurrency
     |                            group since Sep 10 2026: in the shared
     |                            repo-writes line its queued run was
     |                            displaced-and-cancelled by newer jobs
     |                            5 nights of 7 -- same fix, same
     |                            reason as poll.yml and morning.yml)
     v
scanner.py   (9x daily + after forecast)  Kalshi open markets + ensemble
     |                            votes -> picks + gates -> edges.csv
     v
trader.py    (BENCHED from schedule Aug 26 2026 -- runs only inside
     |                            morning.yml or by manual dispatch)
     |                            latest scan's would_bet=YES rows,
     |                            $1 each -> Kalshi orders -> trades.csv
     v
settle.py    (daily 12:20 UTC)    asks Kalshi how each market settled
     |                            -> results.csv  (THE scoreboard)
     v
calibration.py  learns per-station bias AND error spread from NIGHT
                forecasts vs actuals — and, since Sep 12 2026, a
                separate bias PER MODEL per station (the two-humped-
                pool fix, see its own section): each member is
                shifted by its own model's bias, pooled bias as the
                fallback. The actual, in order of trust
                (Aug 24 2026): official settled bracket from
                settlements.csv > our own settled bets pinning the
                instrument > raw instrument (which understates by
                design — the old target, and the reason Vegas was
                mis-corrected by 2°F). Feeds back into forecast.py
                (both the nightly and --today pulls): members are
                bias-shifted, then widened to the station's realized
                error sigma — never narrowed.

morning.yml  (ALL-DAY RELAY:      THE ONLY MONEY LANE since Aug 26
              first trigger to    2026 (the Day-of Switch; schedule
              land starts one     densified Aug 28 2026 the Clock Fix;
              job that passes     relay since Aug 30 2026, the
              every 30 min at     Execution Relay -- see its section)
              :07/:37 until       each pass:
              18:45 UTC)          poller.py -> window preflight ->
                                  forecast.py --today ->
                                  scanner.py --strategy morning
                                             --window 9-11 ->
                                  trader.py --strategy morning
                                            --keep-resting ->
                                  commit -> RED finish if any pass
                                  failed or an order errored
                                  (same files, strategy=morning rows;
                                  each city bought only while its own
                                  clock reads 9:00-10:59 AM; passes
                                  with no city in window poll temps
                                  only, skip the Kalshi steps and log
                                  nothing; starters: 12 cron slots
                                  13:07-18:37 UTC + Claude routines
                                  12:50 and 16:05 UTC + the Run
                                  button -- extras queue and stand
                                  down, or take over if the running
                                  relay died)

afternoon.yml (daily 19:30 UTC)   forecast.py --today
                                    --out afternoon_forecasts.csv
                                  RESEARCH LOG ONLY: measures how much
                                  accuracy later-in-the-day forecasts
                                  buy. Separate file so nothing can
                                  leak into a scan, a trade, or the
                                  bias table. No Kalshi secrets, no
                                  trading step, ever.

poller.py    (ALL-DAY RELAY since  NWS METAR temps -> temps_log.csv
              Aug 30 2026: one
              job polls + pushes
              every 15 min at
              :04/:19/:34/:49,
              re-chained by 96
              daily cron starters;
              also piggybacked
              inside morning.yml +
              swoop.yml runs)
                                  (the RAW source of truth for highs);
                                  also regenerates daily_highs.csv from
                                  it -- a derived summary NO code reads
highs.py     (library, no cron)   THE one way a daily high is computed:
                                  temps_log.csv -> per-station local-day
                                  highs + freshness. Used by swoop_alert,
                                  calibration, autopsy, poller; mirrored
                                  in JS by index.html
settlements.py (12x daily, every  Kalshi settled result fields (unauth)
              2h at :23 -- off-
              peak minute, Sep 10
              2026: the old 4 slots
              sat on :00 and were
              skipped nightly)
                                  -> settlements.csv: the OFFICIAL high
                                  range each city's markets paid on;
                                  feeds the board's "Yesterday" line
                                  AND (Aug 24 2026) the actuals that
                                  calibration and autopsy learn from
swoop_alert.py (every 15 min      advisor board -> swoop.html, swoop_log.csv,
              13:00-01:59 UTC,    swoop_pulse.json (its heartbeat)
              2-hourly rest --    (polls its own fresh temps first;
              band start 16 -> 13
              Sep 14 2026, the
              sell-signal fixes)
                                  grades each position on its CITY'S
                                  local day, so West Coast evenings
                                  stay on the board)
sports_scanner.py (2x daily)      sharps consensus (MLB/NFL/CFB/NBA/
                                  tennis) vs Kalshi props ->
                                  sports.html card, sports_picks.csv;
                                  grades by Kalshi settlement ->
                                  sports_results.csv. ADVISORY ONLY.
sports_probe.py  (on demand)      read-only inventory: what the Odds API
                                  plan carries + Kalshi's live sports
                                  series. Run sports.yml with probe=true.
whale_watcher.py (every 2h inside Kalshi public trade tape on the
              the poller relay
              since Sep 11 2026;
              whales.yml cron +
              Run button = backup)
                                  hand-verified series -> big executed
                                  bets ($250+ weather / $1000+ sports,
                                  fill-bursts, 26h lookback) ->
                                  whale_trades.csv + whales.html board
                                  (CFB/NFL/NBA/MLB/Weather/Tennis);
                                  graded by Kalshi settlement ->
                                  whale_results.csv. RESEARCH ONLY --
                                  no money code may ever read it.
index.html                        static dashboard reading the CSVs
```

All state is CSVs committed to `main` by the workflows. There is no
database. Secrets live in GitHub Actions: `KALSHI_API_KEY_ID`,
`KALSHI_PRIVATE_KEY`, `ODDS_API_KEY` (the sports card needs only
`ODDS_API_KEY`; it reads Kalshi market data unauthenticated on purpose).

**Scar (Aug 19, 2026): a secret can silently go EMPTY.** From ~Aug 7 the
repo's `ODDS_API_KEY` secret was empty; every odds call 401'd and the old
sports card published "no edges today" twice a day, green, for two weeks
(sports.yml runs Aug 7–16 also failed outright while the Kalshi secrets
were missing). Rules that came out of it: a dead feed must show on the
card itself, in the log, AND as a non-zero exit; and an empty secret in
a workflow log looks like `ODDS_API_KEY:` with nothing after the colon —
check that line first when a feed dies.

### CSV contracts (writer owns the header)

| File | Writer | Header |
|---|---|---|
| `forecasts.csv` | `forecast.py` | `forecast_date,station,city,forecast_high_f,fetched_utc,members,bias_applied,member_models` (members pipe-separated, already calibrated, pooled across GFS+ECMWF since Aug 24 2026; bias_applied added Aug 26 2026 = the correction already subtracted from that row's members, so calibration can reconstruct the raw error — blank on old rows, read as 0; since Sep 12 2026 it is the tagged record `pool:-3.46\|gfs:-0.85\|ecmwf:-4.40` whenever member_models is usable — per slice, exactly (raw median − stored median), widening included, so `calibration.parse_applied` inverts it with no guesswork — and stays a plain scalar on the no-tags fallback path (old scalar rows keep their old one-shift-for-everyone meaning); member_models added Aug 31 2026 = one tag per member, pipe-separated, aligned with members (`gfs`/`ecmwf`), so the Model Lab can grade each voter separately — blank on old rows and whenever alignment can't be guaranteed; a morning `--today` row is fetched on its own forecast_date between 06:00–22:59 UTC — `csvio.is_morning_row` is the one true classifier, there is no extra column. The hour window exists because a delayed nightly cron slips past UTC midnight and stamps the same date; those rows are still night) |
| `afternoon_forecasts.csv` | `forecast.py --today --out afternoon_forecasts.csv` (afternoon.yml, 19:30 UTC) | same header as `forecasts.csv` (RESEARCH LOG ONLY, added Aug 24 2026 — measures the value of forecast freshness; **no trading or calibration code reads it**, and it must stay that way: pointing scanner/calibration at it would poison the race and the bias table) |
| `temps_log.csv` | `poller.py` | `utc_time,station,city,temp_f,obs_time_utc` |
| `daily_highs.csv` | `poller.py` (full rewrite each run, regenerated from `temps_log.csv` via `highs.py`) | `date,station,city,high_f,last_update_utc,obs_time_utc` (last_update/obs_time = poll/observation time of the day's peak; derived human-readable summary ONLY — since Aug 21 2026 **no code reads it**; retirement candidate) |
| `settlements.csv` | `settlements.py` (full rewrite each run) | `date,station,city,series,low_f,high_f,n_markets,n_settled,source,utc_offset_hours,checked_utc` (blank low/high = unbounded tail; row exists only when a market settled YES — exclusions alone never make a row) |
| `edges.csv` | `scanner.py` | `scanned_utc,city,market,subtitle,floor,cap,yes_ask,no_ask,model_prob_pct,edge_yes,edge_no,bias_f,spread_scale,sigma_f,n_members,pick,edge_pick,would_bet,strategy` (strategy added Aug 20 2026, old rows backfilled `night`; sigma_f added Aug 24 2026 = the calibration's learned target error spread in °F — it replaces the old unitless spread_scale ratio, whose column stays so old rows keep meaning; new rows leave spread_scale blank, the two numbers must never share a column; floor/cap are INCLUSIVE degree bounds since Sep 12 2026 — the tail-strike fix: tail rows before that date carry Kalshi's exclusive strike (T99 → cap 99 meaning "98 or below") and an inflated tail `model_prob_pct`, see the fix's section) |
| `trades.csv` | `trader.py` | `placed_utc,ticker,subtitle,side,count,limit_cents,model_pct,edge,live,status,order_id,strategy` (strategy added Aug 20 2026, old rows backfilled `night`) |
| `results.csv` | `settle.py` | `graded_utc,ticker,city,action,cost_cents,count,fee_cents,market_result,result,pnl,strategy` (fee_cents added Aug 18, strategy Aug 20 2026; old rows backfilled `night`; readers treat a blank strategy as night) |
| `sports_picks.csv` | `sports_scanner.py` | `scanned_utc,sport,shelf,game,detail,commence_utc,series,ticker,side,pick,books_pct,kalshi_cents,fee_cents,gap_cents,n_books,shown,why` (wiped + new header Aug 19, 2026 — edge-era rows graded a dead rule) |
| `sports_results.csv` | `sports_scanner.py` | `graded_utc,sport,shelf,game,detail,ticker,side,pick,books_pct,kalshi_cents,gap_cents,market_result,result,pnl` (wiped same commit) |
| `parlay_picks.csv` | `sports_scanner.py` | `scanned_utc,parlay_id,n_legs,legs,tickers,leg_probs_pct,combined_pct,fair_payout,last_start_utc` (the parlay board, Sep 8 2026; legs/tickers/leg_probs_pct pipe-separated and index-aligned; fair_payout = 1/combined_prob in $ per $1; append-only, union-merged; ADVISORY ONLY — nothing that trades may ever read it) |
| `parlay_results.csv` | `sports_scanner.py` | `graded_utc,parlay_id,n_legs,legs,tickers,combined_pct,legs_won,legs_lost,legs_void,result` (result HIT/MISS/VOID by Kalshi settlement per leg — any lost leg = MISS, void legs drop out like a book's pushed legs; **no pnl column on purpose**: a book's parlay payout is unknowable, so the scoreboard grades calibration — stated % vs hit rate) |
| `combo_picks.csv` | `sports_scanner.py` | `scanned_utc,combo_id,n_legs,sectors,legs,tickers,leg_probs_pct,combined_pct,fair_payout,last_start_utc` (THE COMBO BOARD, Sep 10 2026 — cross-sector stacks: parlay-board sports legs + dual-expert weather legs; sectors/legs/tickers/leg_probs_pct pipe-separated and index-aligned, sectors ∈ MLB/NFL/CFB/NBA/TENNIS/WEATHER; a weather leg's stated prob = min(ensemble member share, live Kalshi YES bid); append-only, union-merged; ADVISORY ONLY — nothing that trades may ever read it) |
| `combo_results.csv` | `sports_scanner.py` | `graded_utc,combo_id,n_legs,sectors,legs,tickers,combined_pct,legs_won,legs_lost,legs_void,result` (HIT/MISS/VOID by Kalshi settlement per leg, void legs drop out, **no pnl column on purpose** — same laws as `parlay_results.csv`; the scoreboard question is calibration of the cross-sector product, which the card admits is approximate when weather legs share an air mass) |
| `health.json` | `watchdog.py` (full rewrite each relay pass) | JSON: `checked_utc, ok, alarms[{code,since,msg}], notes` (added Aug 30 2026 — the watchdog's pulse report for the Station Board banner; display/alerting ONLY, no money code reads it, NEVER union-merge it) |
| `swoop_pulse.json` | `swoop_alert.py` (full rewrite each run) | JSON: `checked_utc, open_weather_positions, graded, note` (added Sep 1 2026 — the grader's heartbeat, written every run even with zero open positions, so the watchdog can tell "grader dead" from "nothing to grade"; a no-bet day writes zero `swoop_log.csv` rows honestly and used to false-alarm. Display/alerting ONLY, no money code reads it, NEVER union-merge it) |
| `balance.json` | `trader.py` (every trading pass + end-of-day sweep: cash bucket) and `account_check.py` (Run button: all buckets) — full rewrite each write | JSON: `checked_utc, cash_cents, source, note` (+ `held_cents, riding_cents, n_resting, n_open` when written by account_check) (THE WALLET LINE, Sep 12 2026 — the Station Board's spendable-cash display, red under $1; display/alerting ONLY, no money code reads it, NEVER union-merge it; a dead balance call leaves the old file, whose own checked_utc shows the staleness) |
| `settlements_pulse.json` | `settlements.py` (full rewrite each run) | JSON: `checked_utc, api_tried, api_ok, rows_written, rows_total, note` (added Sep 12 2026 — the settlements job’s heartbeat, written every run even when nothing new settled, so the watchdog can tell "job dead" from "Kalshi slow to finalize"; checked_utc in settlements.csv moves only when a settlement pins, and on Sep 11–12 2026 that false-alarmed SETTLEMENTS STALE for ~20 h at a healthy job — the swoop_pulse lesson applied. Display/alerting ONLY, no money code reads it, NEVER union-merge it) |
| `model_research.csv` | `model_lab.py` (forecast.yml, nightly after the money forecast) | `forecast_date,station,city,model,forecast_high_f,n_members,members,fetched_utc` (THE MODEL LAB, Aug 31 2026 — candidate models riding as research passengers: `icon` = the German global ensemble, `nws` = the NWS public point forecast, and since Sep 14 2026 (owner request) `hrrr` = NOAA's hourly-refreshed ~3 km US short-range model via Open-Meteo's free forecast API (models=gfs_hrrr, a single deterministic number like nws; its short horizon can honestly miss a nightly for-tomorrow row), and since Sep 15 2026 (the widen-the-field pass, under the owner's run-every-test mandate) `nbm` = NOAA's National Blend of Models (ncep_nbm_conus — NOAA's own per-station statistical blend of all major models, the product NWS forecasters start from), `ukmo` = the UK Met Office global model (ukmo_seamless), and `gem` = the Canadian global ensemble (~21 members, ensemble API) — all three verified live 20/20 cities by `modellab_probe.yml` (probe run 1, Sep 15 2026) before riding; the probe is the read-only Run button for vetting any future candidate (its header documents the after-dark nws=0 quirk: red at that hour means read the per-city log, not necessarily a dead feed) — all raw and uncalibrated. RESEARCH LOG ONLY, same law as afternoon_forecasts.csv: **no trading or calibration code may ever read it**; union-merged append-only) |
| `model_research_today.csv` | `model_lab.py --today --out model_research_today.csv` (samedaylab.yml, 14:12 + 19:42 UTC) | same header as `model_research.csv` (THE SAME-DAY LAB, Sep 14 2026 — the candidates' SAME-DAY numbers, one pull in the buy-window hours and one in the afternoon, so the October review can judge same-day skill (HRRR's whole reason for existing) on a real record instead of nightly-horizon rows; separate file on purpose so the nightly standings in model_report.md never mix horizons. RESEARCH LOG ONLY, same law as its parent: **nothing that trades, scans for money, or calibrates may ever read it**; union-merged append-only) |
| `whale_trades.csv` | `whale_watcher.py` (whales.yml, every 2h at :37) | `seen_utc,sector,series,ticker,event,bet_on,bet_type,side,contracts,avg_price_cents,dollars,n_fills,first_trade_utc,last_trade_utc,close_time_utc,hours_before_close,expert_pct,agrees` (THE WHALE WATCHER, Sep 11 2026 — big executed bets from Kalshi's public tape on hand-verified series only; a row is a fill-burst, never a person; sector ∈ CFB/NFL/NBA/MLB/WEATHER/TENNIS; expert_pct = ensemble % (weather, from edges.csv) or sharps' de-vigged % (sports, from sports_picks.csv) for the whale's side, blank when no fresh row; bet_type added Sep 12 2026 = MONEYLINE / SPREAD n / TOTAL n / PROP, parsed structured-first (series ticker + Kalshi's floor_strike, then title text; a PROP's bet_on carries the full market question) — blank on rows older than the column, which readers treat as MONEYLINE for sports (only winner/match series were ever watched) and as blank-on-purpose for weather (a bracket is not a sports bet type); the board shows one line per team+side+bet type, summing same-window bursts, while the CSV keeps every burst; append-only, union-merged; **RESEARCH ONLY — nothing that trades, scans, or calibrates may ever read it**) |
| `whale_results.csv` | `whale_watcher.py` | `graded_utc,sector,ticker,bet_on,side,dollars,market_result,result` (HIT/MISS by Kalshi's own settled result; **no pnl column on purpose** — no bet was placed, a dollar figure would be invented data; the scoreboard question is "does big money actually know?", per sector and per timing; append-only, union-merged; same research-only law) |
| `leg_research.csv` | `sports_scanner.py` | `scanned_utc,sport,game,pick,ticker,commence_utc,hours_to_start,books_pct,n_books,books_low_pct,books_high_pct,kalshi_bid_cents,boarded` (THE LEG LAB, Sep 14 2026 — born from the owner's question "an 80%er can lose and a 60%er can win; what else could we look at?": every parlay-shelf sharps favorite from 55% up (deliberately below the 70 board floor, so the banned bands keep building a paper record) logs the quality signals already in hand at scan time — books_low/high = each sharp book's own de-vigged number for the pick, min/max, "do the experts agree with each other"; kalshi_bid_cents = the live Kalshi YES bid, the same second expert the weather dual-expert rule uses, blank when unquoted, never guessed; hours_to_start = number freshness; boarded = whether it cleared the board floor. No new feeds, no extra API calls, no effect on any board. RESEARCH LOG ONLY, same law as the Model Lab: **nothing that boards, trades, scans for money, or calibrates may ever read it**; append-only, union-merged) |
| `leg_research_results.csv` | `sports_scanner.py` | `graded_utc,sport,ticker,pick,books_pct,books_low_pct,books_high_pct,kalshi_bid_cents,hours_to_start,boarded,market_result,result` (WIN/LOSS/VOID per leg by Kalshi's own settled result, one row per ticker from its latest scan row; **no pnl column on purpose** — no bet was placed. The scoreboard question, verbatim from the owner: in what scenario does a 60% team still belong on the board? Slice at ~100+ graded legs: tight-books-agreement vs loose, Kalshi-confirms vs Kalshi-doubts, fresh number vs stale. Promoting any signal into a board gate is an owner decision made on this record — the scoreboard promotes; conviction never does; append-only, union-merged; same research-only law) |
| `sixhr_max_log.csv` | `poller.py` | `utc_time,station,city,max6_f,obs_time_utc` (THE OVERNIGHT PEAK LOG, Sep 14 2026 — the station's OFFICIAL 6-hour maximum temperature from the 00/06/12/18 UTC synoptic observations, read from the same API payload the poller already fetches (no extra call), floored like every temperature, deduped by (station, obs_time). Born from the Philadelphia $10: the deciding overnight peak happened BETWEEN hourly readings, this field knew it, and nothing read it. **RESEARCH LOG ONLY — nothing that trades, scans for money, or calibrates may read it** until a walk-forward backtest (the morning-thermostat standard) proves that flooring the vote at the official 6-hour max flips misses to wins, and an owner decision promotes it; append-only, union-merged) |
| `model_report.md` | `model_report.py` (autopsy.yml, full rewrite each run) | per-city, per-model median miss vs the settled number: `pool`/`gfs`/`ecmwf` from forecasts.csv (calibrated; member_models splits the voters) and the research passengers from model_research.csv. Derived human-readable output ONLY — no code reads it, NEVER union-merge it. Promotion of a model into the vote is an owner decision made on this evidence |

Calibration is applied **exactly once**, at forecast time
(`calibrate_members` inside `forecast.py`) — both the bias shift and
the spread widening. The scanner only reports the calibration table
for display — never re-apply either.

## THE ACCURACY REBUILD (Aug 24, 2026)

Ninety-three settled bets said the same four things; all four were
fixed in one commit, on the owner's explicit call:

1. **Calibration now learns from the official settlement, not our own
   thermometer.** The old "actual" was the METAR instrument high,
   which understates by design (hourly, floored, misses between-hour
   peaks TWC's settled max catches). Learning bias against an
   understated actual mis-corrected exactly the cities the autopsy
   flagged — Las Vegas ran 3.4°F below the settled number while the
   table prescribed 1.1°F. `calibration.resolve_actual` order of
   trust: settled bracket midpoint from `settlements.csv` > our own
   settled bets pinning the instrument > raw instrument. (Why reading
   `settlements.csv` here doesn't violate the derived-file law: it is
   a cache of Kalshi's **immutable** settlement facts, rewritten in
   full each run — a settled result never changes, so a missing row
   only ever means "fall back", never "stale". The daily_highs rot
   was incremental state over *changing* raw data; this is neither.)
2. **The spread is learned, not assumed.** The scanner claimed ~50%
   average confidence and won 30% (autopsy §4 has the table: the 65%+
   claims won 19%). Root cause: raw ensemble spread (~1.4°F median)
   is narrower than realized forecast error (~2–4°F), and the old
   spread_scale only widened on thin history — at n≥10 every station
   sat at ×1.00 forever. Now each station's robust residual sigma is
   a **target**, and `calibrate_members` widens members to match it.
   Members are never narrowed (scale floors at ×1.0): we may claim
   less confidence than the raw ensemble, never more. Expect FEWER
   flagged buys — honest probabilities fail MIN_PICK_PROB more often.
   That is the fix working, not a bug.
3. **The ensemble is a two-model pool.** GFS (31) + ECMWF (51)
   members, one Open-Meteo call per model so a dead model prints
   loudly and the other carries on (dead-feed scar applies); the city
   is skipped only when no model delivers. ECMWF outvotes GFS ~5:3 on
   purpose — it is the stronger surface-temperature model.
4. **MIN_PICK_COST raised 8¢ → 15¢** (scanner + trader in the same
   commit, bands identical as always). Scoreboard evidence: under-15¢
   picks settled 0-for-10 — the market was right every time.

Also in the rebuild: autopsy.py locates losses with the official
settled range (both-bounds rows in `settlements.csv`) before falling
back to the instrument, and its §4 reliability table (claimed % vs
delivered %) is the permanent monitor for fix #2 — if the claimed-vs-
won gap doesn't shrink as post-rebuild bets settle, say so loudly.
And `afternoon.yml` logs a 19:30 UTC same-day forecast to
`afternoon_forecasts.csv` (research only, nothing trades from it) to
measure what forecast freshness is worth before the race promotes
anything.

## THE FEEDBACK FIX (Aug 26, 2026)

The calibration graded its own corrected homework. `forecasts.csv`
stores the forecast AFTER the bias shift, and `calibration.py` learned
"forecast error" from those corrected rows — then applied what it
learned to the next night's raw members as the WHOLE correction,
throwing away the correction already inside every history row. At a
station with a stable raw bias B, the applied correction stalls near
B/2 (learned = B − applied, applied anew each night). Found the day
San Francisco bet "80° or above" off a calibrated 80.6°F forecast
while the market screamed mid-70s: the table prescribed −3.9°F while
SF's corrected forecasts still ran +3.6°F hot — true raw bias ~7°F,
half-corrected forever. SF settled bets were 0-for-3, all warm-side;
Las Vegas had the same disease cold-side (−3.0°F leftover).

The fix, one commit: `forecast.py` records `bias_applied` in every
row, and `calibration.py` reconstructs each night's raw error as
(corrected forecast − actual) + bias_applied before learning. Old
rows read as bias_applied 0 (the old assumption) and age out of the
14-day window — expect the table to take up to two weeks to fully
converge, biases roughly doubling at the worst stations. The
`MAX_ABS_BIAS` ±6°F clamp now WARNS in the log when it binds instead
of capping silently: it exists for corrupt joins, but SF's real bias
can reach it — if the same station warns daily, the bias is real, and
raising the clamp is an owner decision on that evidence, never a
silent edit. The monitor for this fix is the same as the rebuild's:
autopsy §4 claimed-vs-delivered, plus the leftover biases in the
calibration printout collapsing toward zero.

## THE CLOCK + BOARDS FIX (Aug 28, 2026) — OWNER AUDIT

The owner's complaint, in their words: after the Day-of Switch they
could never tell whether the bot was going to buy today or whether
they were "waiting too late"; the swoop and station boards kept
looking wrong; and long shots kept getting bought. The audit found
one root cause under most of it: **GitHub's cron scheduler is
best-effort and was dropping most of this repo's runs.** Evidence,
Aug 28: the 15-minute poller fired ~11 times in 24 hours instead of
96 (boards graded on 75–80-minute-old readings); NONE of morning.yml's
three scheduled runs fired — every buy that day was the owner pressing
Run by hand from the iPad. On Aug 27 the 14:30 run fired at 15:37,
after the East Coast window had closed. Fixes, all in one commit:

1. **The money lane got redundancy, not hope.** morning.yml runs every
   30 minutes 13:07–18:37 UTC (off-peak minutes — GitHub drops the
   crowded :00/:15/:30/:45 slots far more often). Every city gets ~4
   chances inside its own 9:00–10:59 AM window; a preflight step skips
   the Kalshi work when no city is in window; the window gate and the
   fail-closed exposure check make repeats harmless. Never thin this
   schedule back to single-shot runs — one dropped cron = a coast
   unbought. (Aug 30 2026: the slots stayed but stopped being
   single-shot runs — each is now a redundant starter of one all-day
   relay job. See THE EXECUTION RELAY below.)
2. **Every run that needs fresh temperatures brings its own.**
   morning.yml and swoop.yml run poller.py as their first step, so the
   reality floor and the swoop grades never depend on poll.yml's cron
   having fired. poll.yml itself moved to minutes 4/19/34/49.
3. **A failed order turns the run red.** On Aug 24 and Aug 26 every
   order died on "insufficient balance" and the runs stayed GREEN (the
   dead-feed scar again). morning.yml now greps the trader log after
   committing and fails loudly; the Station Board card shows the same
   failure in red with "fund the account" in plain English.
4. **The day-of reality floor** (scanner.py, morning scans only): a
   FRESH station reading (≤60 min) is a hard floor on the day's final
   high — ensemble members below it are physically impossible and get
   raised to it before the vote, so the pick can never be a bracket
   the thermometer already killed. A stale reading applies no floor
   (never correct with old data). The METAR reading understates by
   design, so flooring at it can only be honest.
5. **The swoop board grades on each city's own day and clock.** The
   old UTC-date filter dropped every West Coast position from the
   board after ~5pm Pacific (UTC had rolled over) — their riskiest
   hours; and the "too early to swoop" gate was one UTC hour (4pm ET
   but 1pm PT). Both are per-city local now, and the 15-minute swoop
   band extends to 01:59 UTC to cover Pacific evenings.
6. **The Station Board is the owner's answer to "did it buy and
   why".** Each card now carries a money box: BOUGHT (bracket, price,
   time on the viewer's clock, plus WHY — the ensemble vote share,
   member count, forecast median, and how today's forecast compares
   with what settled yesterday), or the exact rule that said no, or
   the buy window shown on the viewer's clock while waiting, or a red
   box for failed orders / dropped runs. All times on the page use
   the VIEWER'S browser clock (it used to hardcode Chicago and call
   it "your time"). The board reads trades.csv and tails of
   edges.csv/forecasts.csv straight from the raw logs — no new
   derived files. The JS mirrors of the money gates
   (MIN/MAX_PICK_COST, MIN_PICK_PROB, the window hours), the
   series→station map, and the timezone map MUST move in the same
   commit as their Python sources — same law as the highs mirror.

## THE EXECUTION RELAY (Aug 30, 2026) — OWNER DECISION

The Clock Fix's dense schedule still trusted GitHub to fire enough of
its 12 slots each day. It didn't: on Aug 29 only two fired on their
own — the first at 17:03 UTC, after the East Coast window had already
closed — and every East Coast and Central buy that day happened
because the owner pressed Run by hand. A schedule of single-shot runs
loses a coast every time GitHub drops a slot. The owner asked for
execution that does not need a babysitter. The fix keeps the pipeline
and every gate exactly as they were and changes only who keeps the
clock:

- **morning.yml is a relay, not a single shot.** The FIRST trigger
  that lands — any of the 12 cron slots (kept as redundant starters),
  a Claude routine, or the owner's Run button — starts ONE job that
  runs a full buying pass (poll → fresh --today forecast → scan
  --window 9-11 → trade --keep-resting → commit) every 30 minutes at
  :07/:37 until 18:45 UTC, then exits. One lucky trigger covers the
  whole day instead of 1/12th of it.
- **Extra triggers are harmless and are the fail-over.** They queue
  in the morning-money-relay concurrency group behind the running
  relay and stand down in seconds when their turn comes — unless the
  relay's runner died mid-day, in which case the queued run takes
  over the rest of the day. GitHub keeps only the newest queued run
  and cancels older queued ones; those "cancelled" entries in the
  Actions list are normal, not failures. The window gate and the
  fail-closed exposure check make repeated passes safe, as always.
- **Two Claude routines back up GitHub's cron.** They live in the
  owner's claude.ai account (not in this repo — you will not find
  them in the workflows): daily at 12:50 UTC one starts the relay
  whether or not any GitHub cron fires; at 16:05 UTC a watchdog
  checks a relay is actually running and starts one if the morning's
  died. Each only presses Run on morning.yml — no code, no trades,
  no gate decisions ever live in the routines.
- **morning.yml LEFT the shared repo-writes concurrency group** — a
  six-hour holder of that lock would freeze the poller, swoop, and
  settlement jobs all afternoon. Racing pushes are handled by the
  existing retry loops plus a new .gitattributes rule: the
  append-only CSVs (temps, forecasts, edges, trades, results, swoop
  and sports logs) merge by UNION, so when two jobs append at once
  both sides' rows survive (the Aug 20 lost-settlements scar, fixed
  at the root). NEVER union a full-rewrite file (settlements.csv,
  daily_highs.csv, the HTML pages, autopsy.md) — union would
  interleave two complete rewrites into garbage.
- **The day ends with a broom (added Aug 30 2026, evening audit).**
  When the relay reaches 18:45 UTC — or a starter lands after it —
  it runs `trader.py --sweep-resting`: cancel this bot's own
  still-resting orders and mark provably-unfilled ones "cancelled"
  in trades.csv. Found by audit before it cost money: with the night
  cancel runs benched, nothing cleaned up unfilled morning orders, so
  one could (a) fill hours after its pick's information went stale —
  exactly when the market turns against it — and (b) keep its
  "submitted" status, which settle.py grades at settlement as a real
  bet that never existed, poisoning results.csv. The sweep touches
  ONLY order_ids recorded in trades.csv (the owner's own manual
  Kalshi orders are invisible to it) and un-marks a row only when
  Kalshi's order object proves zero fills — both guarantees live in
  `cancel_resting_orders()`. A failed sweep turns the run red.
- **A failed pass warns and the next pass retries; any failed pass
  turns the finished run red.** Same honesty rule as ever: a problem
  may not scroll away green. An insufficient-balance order no longer
  kills the rest of the day's passes — it flags red at the finish
  while later passes keep buying the cities that can still be bought.
- **The poller is the relay's tripwire (Sep 2, 2026).** Sep 1 exposed
  the gap this closes: none of morning.yml's 12 cron slots fired
  before 17:16 UTC and neither Claude routine wake executed on time
  (a cold session's wakes can queue instead of running), so the East,
  Central and Mountain windows went unbought — while the poller relay
  fired 23 times straight through the money window and its watchdog
  could only alarm. Now every poll pass during 12:45–18:15 UTC checks
  whether a morning.yml run is queued or in progress and STARTS one if
  not (its own GITHUB_TOKEN via workflow_dispatch — the one event
  GitHub lets a workflow trigger in another; extra starts queue and
  stand down, so false positives cost nothing). Layer order is now:
  poller tripwire (primary, GitHub-native, ~15-min reaction) → the 12
  cron slots → the Claude routines (backup) → the watchdog alarm and
  the owner's Run button (last resort). The watchdog's MONEYLANE alarm
  stays: if it ever fires now, the tripwire itself is broken — say so.

## THE POLLER RELAY (Aug 30, 2026)

The Clock Fix moved poll.yml to off-peak minutes and still trusted
GitHub to fire the slots. On Aug 30 the 15-minute poller fired **9
times instead of 96**; every board sat on 1–2-hour-old readings all
afternoon, and the owner watched Phoenix's card say "high so far
100.4°" while Kalshi priced 106–107° at 93% — the market knew, the
board didn't. (The board's red "136 min ago" age was the only honest
part of that card.) Same disease, same cure as morning.yml:
**poll.yml is now a relay.** The first trigger that lands (any of the
96 cron slots, kept as redundant starters, or the Run button) starts
one job that polls and pushes every 15 minutes at :04/:19/:34/:49
until it nears GitHub's 6-hour job ceiling, then exits and a queued
starter takes over — the relay re-chains itself around the clock.
Like morning.yml it left the shared repo-writes concurrency lock
(its own `poll-relay` group; a six-hour lock holder would freeze
swoop/settlements/scans), pushes through the real retry loop with
union-merge protecting the appends, and turns the finished run RED
if any pass failed. Queued runs showing "cancelled" in the Actions
list are normal — GitHub keeps only the newest starter. Never thin
this back to single-shot runs: the repo's runner minutes are free
(public repo) and one dropped cron = a stale board on a money day.

Since later that same day the relay also carries the **swoop board**:
swoop_alert.py runs inside the pass on swoop's own rhythm (every pass
in the 16:00–01:59 UTC heat-of-day band, 2-hourly otherwise — same
hours its old crons kept), because swoop.yml's cron starved the board
3 hours during Pacific risk hours on Aug 30. swoop.yml keeps its
schedule as a redundant backup and its Run button for manual passes;
racing pushes are the same solved problem as everywhere else.

Since Sep 11 2026 the relay also carries the **whale watcher** (owner
request, the day it shipped): whale_watcher.py runs inside the pass
every 2 hours (the :34 pass of odd UTC hours — the old odd-hours-at-
:37 cadence), because on its first day GitHub fired only 1 of
whales.yml's 5 cron slots. whales.yml keeps its schedule as a
redundant backup and its Run button, exactly like swoop.yml. Safe by
construction: the scan needs no secrets, the 26h lookback + dedupe
mean overlapping runs log nothing twice, and the whale CSVs
union-merge.

## THE WATCHDOG (Aug 30, 2026)

Born from the owner's exact words: "every single solitary time I ask
for a check, everything checks out great, and then something breaks
anyway." They were right, and the reason is structural: **a
once-a-morning check can never catch failures that start after the
check.** Every infrastructure failure this repo has eaten (dropped
poller crons, the money lane never firing, the empty ODDS_API_KEY,
insufficient-balance orders) *began* while everything was green and
was *found* hours later by the owner squinting at a stale board. The
owner was the monitoring system. That is backwards.

So the check runs all day instead: `watchdog.py` runs inside every
poller-relay pass (~15 min) and checks the pulses that have actually
burned us, each against its rawest source:

- **POLLER** — newest write in `temps_log.csv` under 40 min old.
- **FORECAST** (14:00–18:45 UTC) — a same-day morning row exists in
  `forecasts.csv` (via `csvio.is_morning_row`, the one true
  classifier).
- **MONEY LANE** (13:15–18:45 UTC) — a morning.yml run is alive on
  GitHub right now (queued/in-progress, or finished under 40 min ago),
  checked via the Actions API. An unreachable API is a logged note,
  never a false alarm.
- **ORDERS** — no trade placed today has ERROR status.
- **BAND** — no trade placed today priced outside the band, judged
  against trader.py's own MIN_COST/MAX_COST source line (parsed at
  run time, never a mirrored copy that can drift). Firing means
  something impossible happened: stop and audit before the next buy.
- **SWOOP** (16:00–01:59 UTC) — `swoop_pulse.json` written under 45
  min ago inside its 15-minute band. The pulse, NOT the log (fixed
  Sep 1 2026): `swoop_log.csv` only gets rows when a position was
  graded, so a no-bet day writes zero rows for honest reasons and the
  old log-based check cried SWOOP BOARD STALE all evening at a
  healthy board — exactly the alarm-the-owner-learns-to-ignore this
  section warns against. The log check survives only as the fallback
  when the pulse file has never been written (day zero / forks).
- **SETTLEMENTS** — `settlements_pulse.json` written within 9 hours.
  The pulse, NOT the CSV (fixed Sep 12 2026): `checked_utc` in
  `settlements.csv` moves only when Kalshi finalizes a new
  settlement (the don't-churn rule), so on a night the exchange is
  slow — Sep 11–12 2026, all 20 events unfinalized ~20 h — the old
  CSV check cried SETTLEMENTS STALE at a job that had run green
  four times, with a "Press Run" message no Run press could clear.
  Same disease and same cure as the SWOOP fix above. The CSV check
  survives only as the fallback when the pulse has never been
  written (day zero / forks); a fresh pulse with a >30 h quiet CSV
  is a NOTE ("Kalshi hasn't settled yet"), never an alarm.

An alarm does two things: the relay pass flags it and the finished
run turns **RED** (GitHub then emails the owner — the dead-feed law),
and `health.json` carries it to the **Station Board banner**, which
names the problem and the button to press in plain English, within
~15 minutes of the failure starting. Alarms keep their first-seen
time (`since`) across passes.

`health.json` contracts: writer is `watchdog.py`, FULL-REWRITE every
pass — **never** add it to the union-merge list; **no money code
reads it** (not scanner, trader, settle, or calibration — it is
display/alerting only, so it does not violate the derived-file law).
The board's display is **fail-closed**: a `health.json` older than
25 minutes shows a red "SELF-CHECK SILENT" banner — a dead watchdog
must never look green. A *missing* file just hides the banner (day
zero / forks). Thresholds are generous (≥2 missed beats) on purpose:
an alarm the owner learns to ignore is worse than none.

What the watchdog can NOT do, said plainly to the owner when it
shipped: it cannot see a failure before it happens, and it cannot
make a 55%-win-rate strategy stop having losing days. It shrinks
discovery time from "when the owner happens to look" to ~15 minutes.
That is the whole promise.

## THE ACCURACY TIGHTENING (Aug 30, 2026) — OWNER DECISION

The owner's words after losing 3 of 4 on Aug 30 (having added their
own money on top of the bot's $1 bets): fewer bets, more accuracy.
The full gate sweep across all 146 settled bets said the same two
things:

- **Floor 45¢, cap 60¢**: the ≥45¢ half of the band ran 29W–15L
  (66%), +28¢/$1, vs 58% and +15¢ for the full 40–60. The 45–49¢
  pocket remains the best price region ever recorded (12W–4L).
- **MIN_PICK_PROB 35 → 40**: drops the weakest-agreement picks.

Both changed in one commit (scanner + trader + the Station Board JS
mirror, as the law requires). Caveats stated plainly when the owner
chose: the slices are thin, and the morning-lane-only slice mildly
preferred the old 40¢ floor (16 bets — too few to overrule the full
record). Expect roughly a bet a day less. Reviewed ~Sep 11 together
with the band trial, off settled results — edges.csv still logs
every bracket regardless, so the review can compare what these gates
bought against what the old ones would have.

## THE CITY BENCH (Aug 30, 2026) — OWNER MANDATE

The owner's words, verbatim intent: "anything that can be done to
bring the wins up and the losses down. I don't care what we gotta
do." The roadmap already said how: bench cities on scoreboard
evidence. The full per-city slice of all 146 settled bets found two
cities that lose under EVERY rule set — not just under the dead
cheap-bet and night-lane rules, but inside the current 45–60¢ band
and in the morning lane too:

- **Oklahoma City: 0W–7L** overall (0–2 inside 45–60¢, 0–2 morning).
- **Dallas: 1W–9L** overall (0–2 inside 45–60¢, 0–3 morning).
- Together: **1W–16L, −$10.57** — half the account's entire net loss.

`BENCHED_CITIES` in `scanner.py` (mirrored as `BENCHED_STATIONS` in
`index.html` — same-commit law) forces `would_bet` off for them. A
benched city is still polled, forecast, scanned, and fully logged to
`edges.csv` (pick, prices, everything), so its paper record keeps
accruing and the bench itself stays gradeable. The Station Board card
says "Benched" with the record, in plain English.

**On watch, NOT benched** — their ugly totals came almost entirely
from the already-banned cheap night bets, and their current-rules
records are too thin to convict: **Denver** (1W–7L, but its one
morning bet won), **Washington DC** (1W–7L, 1–1 in-band), **San
Francisco** (0W–4L, all cheap night bets; its known forecast bias is
mid-repair per the Feedback Fix), **Austin** (2W–6L, 0–3 in-band but
1–1 morning). Benching them would punish the cities for the dead
rules' crimes.

**Review ~Sep 11, 2026, together with the band trial and the accuracy
tightening**, off settled results: re-slice every city, un-bench or
extend the bench on the paper record, and convict or clear the watch
list. Un-benching is an owner decision; so is adding a third city.

## THE 40–60 BAND TRIAL (Aug 28, 2026) — OWNER DECISION, TWO WEEKS

The owner asked for the full scoreboard sliced by price, then chose
the band. The evidence (all 132 settled bets at the time):

- Under 20¢: **2W–22L** (−$1.07/$1 under 15¢). 20–24¢: 2W–12L.
  35–39¢: 2W–9L. 60–68¢: **3W–7L, −55¢/$1** — both tails lose.
- **40–60¢: 28W–23L (55%), +11¢ per $1 risked — the only profitable
  region.** The 45–49¢ pocket alone: 12W–4L (75%), +56¢/$1.
- Floor scenarios: ≥40¢ was the first floor ever profitable (+3¢/$1);
  ≥45¢ made +14¢/$1; trimming the cap to 60¢ beat keeping 68¢.

The owner's reasoning, recorded: by the time the day-of bot buys
(9–11 AM city time), a 40–60¢ price means the market genuinely agrees
with the pick and it still pays — they had been noticing the same
thing watching the buys.

Terms of the trial, set when it started:

- `MIN_PICK_COST/MIN_COST = 40`, `MAX_PICK_COST/MAX_COST = 60`,
  scanner + trader + the Station Board JS mirror, one commit.
- **Runs two weeks: Aug 28 → ~Sep 11, 2026.** Then the owner decides
  — keep, widen, or revert to 20–68 — off the settled results, not
  vibes.
- Both known caveats were on the table when the owner chose: the
  per-band slices are thin (10–16 bets each), and most of the record
  is the benched night lane — the morning lane (16 settled: 10W–6L,
  +68¢/$1) had NOT shown the cheap-bet disease (its 20–39¢ bets were
  4W–2L). The trial knowingly trades those possible wins away for the
  proven band; that trade-off is what the review judges.
- **How to grade it:** edges.csv keeps logging every bracket with
  prices, picks, and `would_bet` regardless of the band, so the
  review can compare what 40–60 actually bought against what 20–68
  would have bought on the same days. Expect FEWER buys per day
  during the trial — that is the band working, not a bug.

**THE SEP 11 REVIEW — OWNER DECISION.** Real money in the trial
window (Aug 31–Sep 10): 24 settled bets, 11W–13L, −$2.53 (−16¢/$1).
The paper counterfactuals, graded against official settlements under
identical simulation rules: every alternative lost MORE — skipped
20–44¢ picks 9W–28L (−20¢/$1), skipped 61–68¢ picks 7W–7L (−24¢/$1),
and the picks the prob-40 bar dropped went 10W–25L (−47¢/$1). The
bad fortnight was a forecast problem (a run of too-cool picks during
the Feedback Fix's stated convergence window), not a band problem.
Decisions, recorded: **keep the 45¢ floor and the prob-40 bar; trim
the cap 60¢ → 54¢** (55–60¢ ran 3W–6L, −45¢/$1 in the trial, and the
high side has lost in every era — 60–68¢ was 3W–7L historically;
stated caveat: the trial slice is 9 bets). Two-week trial, **review
~Sep 25** off settled results. **The bench holds** (OKC in-band paper
1W–2L, Dallas 2W–2L — far too thin to overturn 1W–16L); the watch
list stands, with San Francisco 2W–0L real-money in the trial — the
Feedback Fix repair looking real.

## THE MODEL LAB (Aug 31, 2026) — OWNER DECISION

The owner asked whether other forecast models could sharpen the pick,
and chose the evidence-first build: no new model votes with money on
day one — candidates ride along as passengers and build a public
record, and the scoreboard decides who gets promoted. Three pieces,
all shipped in one commit:

1. **The voters are now labeled.** `forecasts.csv` grew a
   `member_models` column: one tag per ensemble member (`gfs`/
   `ecmwf`), pipe-separated, aligned with `members`. The vote is
   UNCHANGED — the pick still comes from the pooled members exactly
   as before — but the scoreboard can finally grade each voter
   separately, per city (until now the pool was unlabeled, so
   GFS-vs-ECMWF skill could never be measured from history; old rows
   stay blank forever). `calibrate_members` preserves member order,
   which is what keeps the tags honest; `forecast.py` refuses to
   write tags if the counts ever disagree.
2. **Research passengers log nightly** (`model_lab.py` inside
   forecast.yml, right after the money forecast): `icon` — the German
   global ensemble (~40 members, generally rated #3 behind ECMWF and
   GFS) — and `nws` — the National Weather Service's own published
   point forecast for each station; joined by `hrrr` (Sep 14 2026)
   and, in the widen-the-field pass (Sep 15 2026, the owner's
   run-every-test mandate, all probe-verified live 20/20 first),
   `nbm` / `ukmo` / `gem` — full detail in the model_research.csv
   contract row above. Raw, uncalibrated, written to
   `model_research.csv`. **THE LAW: research log only, same as
   afternoon_forecasts.csv — nothing that trades, scans, or
   calibrates may ever read it.** A passenger feed that dies
   completely turns the run RED after the money forecast has safely
   committed (dead-feed scar); partial failures print and skip.
   **Scar (Sep 13–14, 2026): a passenger that HANGS is not a
   passenger that dies.** continue-on-error protected the commit
   from a research feed that failed — but slow ICON/NWS calls pushed
   the job into its own 5-minute timeout two nights running, GitHub
   killed it mid-research-step, and the commit step after it never
   ran: the already-fetched money forecast was thrown away both
   nights (found by the watchdog session; no bets were affected —
   the buy clock fetches its own same-day forecast — but calibration
   lost two nights of learning). The fix (Sep 14, one commit):
   forecast.yml now **commits the money forecast immediately after
   fetching it**, BEFORE the research step — making the section's
   promise above literally true in the step order — the job timeout
   went 5 → 15 minutes, and the research step carries its own
   8-minute leash so a hung feed becomes a loud step failure (red
   flag fires, dead-feed law) instead of taking the job down. Never
   put any step between "Fetch forecasts" and its commit.
3. **`model_report.py` writes the standings** (`model_report.md`,
   regenerated by autopsy.yml after each settlement pass): per city
   and per model, the median miss against the officially settled
   number — the same test that ranked the cities. Stated caveat baked
   into the report: gfs/ecmwf/pool are graded on calibrated members
   while the passengers are raw, so a passenger that merely ties the
   incumbents is doing well.

What this is for, in order: (a) per-city model weighting — bench the
*model* that's bad in a city, not just the city — argued from the
report once each model has ~30+ graded nights; (b) promoting icon or
nws into the voting pool if the record says they earn it; (c) HRRR
as a same-day morning-lane signal — no longer deferred as a LOGGER
(Sep 14 2026, owner request: `hrrr` rides as a passenger via
Open-Meteo's free API, so the record starts now); its promotion
into the same-day morning vote remains the October question, judged
on this record. The paid option researched the same day, recorded
for whenever the evidence calls for it: The Weather Company's own
data API (the settlement source itself) is the only purchase that
would tell us something free feeds can't — the judge's own numbers;
buy it only if the settlement-vs-instrument gap still costs money
after the free fixes (the 6-hour-max log) are graded. **Every one of those is an owner decision made
on the report's evidence. The scoreboard promotes; conviction never
does — no model joins, leaves, or changes weight in the vote without
it.**

## THE PER-MODEL BIAS FIX (Sep 12, 2026) — OWNER DECISION

Found the morning the owner caught the board "running wild": New
Orleans' card claimed 39% of members on "95° or above" while its own
median said 90.7°, yesterday settled 89–90°, and NYC's pick was
priced at 1¢. The gates (MIN_PICK_PROB, the price band) blocked
every one of those buys — the discipline held — but the votes
themselves were broken, and the owner called it before any money
moved.

Root cause, proven from the stored rows: **one thermostat cannot fix
two rooms.** The pool is two models with, at many stations, OPPOSITE
biases (that morning at New Orleans: raw ECMWF ~4.4°F cold, raw GFS
slightly hot). The single per-station bias is learned from the
pooled median, which ECMWF dominates 51:31 — so the +3.5°F shift
that fixed ECMWF at New Orleans pushed all 31 already-hot GFS
members into "95° or above": a phantom cluster wearing 38% of the
vote (31/82), one point under the prob bar. NYC was the same disease
mirrored (shift-down overcooling ECMWF into a 1¢ bracket). The
Feedback Fix's converged (larger, correct-on-the-median) biases plus
an unusually wide GFS-ECMWF split that week made it blow up; the
median stayed honest throughout while the top BRACKET lied — the
two-humped-pool disease.

The fix, one commit (this is exactly what member_models was built
for): `calibrate_members` now takes the tags and shifts each member
by ITS OWN MODEL's learned bias — `compute_calibration_full()` in
calibration.py learns bias per (station, model) from tagged night
rows, needing `MIN_MODEL_N = 4` settled tagged nights before a model
earns its own number; under that, and for untagged members, the
pooled per-station bias applies (the old behavior, unchanged as
fallback and as scanner.py's display number). Replaying the sick
New Orleans morning through the fix: the phantom "95° or above"
falls 35% → 1% and the pool becomes one hump centered 89–92, where
the NWS forecast, the market, and the settlement all sat.

The plumbing law that rode along: `bias_applied` in forecasts.csv is
the tagged record `pool:-3.46|gfs:-0.85|ecmwf:-4.40` whenever tags
are usable — each number is exactly (raw median − stored median) for
that slice, measured AFTER the spread widening, so
`calibration.parse_applied` reconstructs raw errors with no
guesswork (the Feedback Fix's reconstruction now holds per model).
Scalar on the fallback path and on all old rows, which keep their
one-shift-for-everyone meaning. Spread widening itself is untouched
— and now engages more often, honestly, because de-splitting the
pool shrinks its raw sigma.

Stated caveats, recorded at ship time: per-model history was 7
tagged settled nights per city (thin — but the mechanism being
corrected is arithmetic, not a streak, and the fallback is the
exact old behavior); and per-model reconstruction from PRE-fix
scalar rows is approximate by the old widening displacement, which
ages out of the 14-day window. Watch the same monitors as the
rebuild: autopsy §4 claimed-vs-delivered, and the calibration
printout's per-model biases converging. NYC-GFS and LA-ECMWF hit
the ±6°F clamp with the warning printing loudly — if that repeats
daily the bias is real, and raising the clamp is an owner decision,
never a silent edit.

## THE TAIL-STRIKE FIX (Sep 12, 2026) — OWNER CATCH

The owner read the Austin card — "98° or below" as the top bracket at
31.7% of members, under a forecast median of 101.2° — and said
something is wrong with the temperature. They were right, and the
find was an off-by-one ON THE MONEY PATH:

- **Kalshi's tail markets carry EXCLUSIVE strike fields.** "98° or
  below" has `cap_strike=99`; "107° or above" has `floor_strike=106`.
  Middle brackets ("103° to 104°") carry inclusive 103/104.
  settlements.py verified and documented exactly this on Aug 20 2026
  ("ranges come from the market SUBTITLE, never the raw strike
  fields") — but scanner.py kept trusting the strikes. Its comment
  claimed tails "return empty strikes"; Kalshi had since started
  filling them, which silently switched the scanner onto the wrong
  path and made its correct subtitle fallback dead code.
- **Effect: every tail bracket over-counted a full degree of ensemble
  members**, and that boundary degree voted TWICE (it also counts in
  the adjacent middle bracket, so a card's bracket percentages could
  sum past 100%). On the day it was caught, Austin's "98° or below"
  showed 26 of 82 members (31.7%) when the honest count was 17
  (20.7%) — nine members forecasting a 99° high were voting for "98
  or below". "107° or above" showed 20.7% against an honest 9.8%.
  New Orleans' phantom "95° or above" cluster (the per-model bias
  fix's trigger, same day) was inflated by the same degree.
- **The fix:** scanner.py's `parse_bracket` now parses the SUBTITLE
  first (the same law settlements.py has followed since Aug 20) and
  falls back to strikes only for an unreadable subtitle, converting a
  one-sided strike to its inclusive degree (cap 99 → hi 98, floor
  106 → lo 107). Middle brackets were always right and are unchanged.
  edges.csv's floor/cap columns therefore log INCLUSIVE degree bounds
  on all rows from Sep 12 2026 on; tail rows before that carry the
  raw exclusive strike (and inflated `model_prob_pct` on tail
  brackets — remember it when grading history).
- Nothing else parsed strikes: swoop_alert.py and settlements.py both
  parse subtitles (correct all along); settle.py grades only Kalshi's
  own `result`. The gates held throughout — MIN_PICK_PROB kept the
  phantom votes from ever buying — but the votes themselves, the
  combo board's weather-leg shares, and the whale board's expert_pct
  all read cleaner from here on.

The card also learned to explain itself (same commit, display only):
when GFS and ECMWF medians pull ≥3°F apart, the money box's WHY line
says the forecast is split and names both numbers — a split pool
scatters the vote, so the biggest single group can honestly sit in a
wide edge bracket away from the median (Austin that morning: GFS
~106°, ECMWF ~100°, ECMWF/NWS/ICON right, GFS ~5° hot). That is a
real disagreement stated plainly, not a bug — and the 40% bar is
what keeps money out of such days.

## THE WALLET LINE (Sep 12, 2026) — OWNER REQUEST

The owner moved the account's cash to their sportsbook one morning
because nothing on the board said how much spendable money the bot
had — then the day's buy bounced on "insufficient balance" (the
banner was accurate; the information came too late). The Kalshi
app's home number is the whole portfolio; only the CASH bucket can
buy (the Sep 11 account_check lesson). So the money is now ON the
Station Board:

- `balance.json` — writers: `trader.py` (every trading pass and the
  end-of-day sweep: cash bucket) and `account_check.py` (the
  "Account check (read-only)" Run button: all three buckets — cash,
  held-by-resting, riding-in-positions; account.yml now commits it).
  JSON: `checked_utc, cash_cents, source, note` (+ `held_cents,
  riding_cents, n_resting, n_open` from account_check). FULL REWRITE
  each write — **never union-merge it**; display/alerting ONLY — **no
  money code reads it** (the trader's own decisions never touch it;
  its fail-closed exposure check still asks the API directly). A dead
  balance call leaves the old file in place: its own checked_utc
  shows the staleness honestly.
- The board shows spendable cash with its checked time, red when it
  can't cover a $1 bet ("fund the account or the bot buys nothing"),
  plus the locked buckets when known, and a press-Run hint when the
  snapshot is over 20 hours old. The number is only as fresh as the
  last trader pass or Account-check run — the board says so rather
  than pretending to be live.

## THE WHALE WATCHER (Sep 11, 2026) — OWNER REQUEST

The owner's question, in their words: out of 30 college games on a
Saturday, where is the big money landing on a single team — and is it
way early? What do they know that we don't? `whale_watcher.py` reads
the **public Kalshi trade tape** on our hand-verified markets only
(the 20 weather series from `cities.py` + the sports card's verified
moneyline/match series: KXNCAAFGAME, KXNFLGAME, KXNBAGAME, KXMLBGAME,
KXATPMATCH, KXWTAMATCH — no discovery, ever) and logs big **executed**
bets to `whale_trades.csv`. The board is `whales.html`, sectioned in
the owner's order: CFB / NFL / NBA / MLB / Weather / Tennis.

The laws, agreed before it was built:

- **RESEARCH ONLY — nothing that trades, scans for money, or
  calibrates may EVER read `whale_trades.csv` or `whale_results.csv`.**
  Same law as afternoon_forecasts.csv and the Model Lab. It places no
  orders, needs no secrets, and must never influence the weather
  bot's picks or the daily card's picks. Promotion to influencing
  anything is an owner decision made on the scoreboard, never before.
- **Executed trades only, never resting orders** — a resting wall can
  be placed for show and cancelled for free; filled money is the only
  honest signal.
- **No invented identity.** Kalshi never reveals who traded and we
  never guess. A row is a *burst* — fills on the same market+side
  with gaps under 90 seconds, summed, because whales slice orders —
  not a person. That is arithmetic, not identity.
- **Thresholds (owner's call): $250+ weather, $1000+ sports** per
  burst. Tuning them later from the logged size distribution is an
  owner decision.
- **Graded by settlement truth**: every burst becomes HIT/MISS in
  `whale_results.csv` by Kalshi's own `result` field, and the board
  shows each sector's running record. **No P&L column on purpose** —
  we placed no bet, so a dollar figure would be invented data.
- **The standings (owner request, Sep 12 2026)** answer "what do we
  do with this data after today": the log never resets (bursts
  accumulate and grade forever), and whales.html now opens with a
  per-sector standings section — burst-level record, the
  **matched-dollar test** (matching every graded burst $1-for-$1 at
  the whale's own price — hit rate alone flatters whales: CFB's
  first days ran 64% hits and −1.0% matched), and the record split
  by **how early the money landed** (first days: 3-days-early CFB
  money went 2–5 — early ≠ smart so far). Computed on the board from
  the two whale CSVs, no new files, no dollar invented. Following
  whales anywhere is an owner decision these standings would have to
  earn first — the scoreboard promotes; conviction never does.
- **Expert cross-check is opportunistic and read-only**: a weather
  burst is compared against the freshest `edges.csv` scan (our
  ensemble %), a sports burst against the freshest `sports_picks.csv`
  row (the sharps' de-vigged %) — blank when no fresh row exists,
  never guessed, and no paid feed is ever called.
- Each scan looks back 26 hours and dedupes against what's already
  logged, so skipped crons lose nothing. A fully dead Kalshi feed
  exits RED (dead-feed law). Low-volume markets that could not
  possibly contain a whale are skipped to keep scans cheap.
- **The scan rides the poller relay** (owner request, Sep 11 2026 —
  the day it shipped, after GitHub fired only 1 of its first 5 cron
  slots): whale_watcher.py runs inside poll.yml's relay pass every 2
  hours, on the same cadence whales.yml's cron kept. whales.yml stays
  as a redundant backup starter and the owner's Run button — the
  swoop.yml pattern exactly.

## THE HANDFUL MANDATE (Sep 14, 2026) — OWNER DECISION

The owner's words, after reading the first per-model, per-city
standings in `model_report.md`: "I'd rather have five awesome ones
than 20 OK ones... I always knew it was gonna be down to just a
handful." And on which cities survive: "I don't care which ones they
are — I only wanna keep the ones the ensembles are accurate on."
Recorded here so the review that executes it runs the way the owner
decided, whichever session runs it:

- **THE BIG CUT REVIEW runs when the tagged per-model records reach
  ~30 graded nights per city** — the bar the Model Lab set. The owner
  said "30 days" (~Oct 14); at the pace graded nights were actually
  accruing when this was written (n=4–7 per model per city on Sep 14,
  tags since Aug 31 — settlement lag plus the two hung forecast
  nights, since fixed, cost real nights), the count more likely
  arrives **mid-to-late October**. Run it when the COUNT arrives, not
  the calendar — a cut made on n=15 is vibes wearing a spreadsheet.
- **The cut is aggressive by mandate.** Slice `results.csv` per city
  and `model_report.md` per model, and: bench every city where no
  model is provably accurate (the owner is explicitly fine with
  benching HALF the map or more — quality over coverage, no city has
  a right to a daily bet); bench the bad MODEL per city where one
  voter drags the pick (the Minneapolis-GFS pattern); and put
  promoting `icon`/`nws` into the vote on the same table, same
  evidence. Fewer, better bets is the point — the owner pre-accepted
  the smaller daily card.
- **The mechanism is the existing bench, nothing new**: a benched
  city keeps being polled, forecast, scanned, and logged to
  edges.csv, so its paper record keeps accruing and it can earn its
  way back — exactly the OKC/Dallas machinery. Per-city model
  benching needs a small scanner change when the review lands
  (weight or drop one model's members per station in the vote);
  build it AT the review, on the evidence, not before.
- The final keep/cut list is the owner's call at the review, off the
  settled record — the scoreboard promotes; conviction never does.
  This section pre-authorizes the review's direction and appetite,
  not a specific list.

**PHASE 1 EXECUTED — THE HANDFUL CUT (Sep 14 2026, same day, owner
order).** The owner didn't wait for the per-MODEL record to run the
per-CITY half of the cut, because the per-city evidence already
existed at twice the sample: the ensemble's DAY-OF PICK graded
against official settlements over ~21–22 scanned days per city (433
picks from edges.csv, bought or not — money gates played no part;
blind chance among ~6 brackets ≈ 17%). The owner's framing,
recorded: the city was never the problem, the "manager" (the
ensemble in that city) is — so keep the 10 cities the manager is
best at, bench the rest. `BENCHED_CITIES` grew from 2 to 11:
the bottom 10 by pick accuracy (Washington DC 29%, Philadelphia
29%, Phoenix 27%, Dallas 27%, Austin 27%, Boston 24%, Chicago 23%,
Houston 18%, Seattle 14%, New Orleans 14% — the bottom three are
all water cities, where global models are weakest) plus Oklahoma
City, which ranked #5 on picks but keeps its own Aug 30 bench
(0W–7L real money) until the owner lifts it by name. Active nine:
San Antonio 55%, Minneapolis 45%, Atlanta 43%, NYC 38%, LA 36%,
Las Vegas 36%, Miami 33%, Denver 33%, San Francisco 32% (SF's
caveat, stated: only 32% land even NEXT DOOR — when its pick
misses, it misses big; a October cut candidate). All benched
cities keep full paper records, as the bench law requires. The
October review (phase 2) still does the per-model work — benching
a model inside a city, promoting icon/nws — and re-judges this
city list with the thicker record, both directions.

## THE MORNING THERMOSTAT — TESTED AND REJECTED (Sep 14, 2026)

The near-miss autopsy of the pick report card found a real-looking
cold lean: at ten cities the morning pick's one-bracket misses fell
overwhelmingly on the cold side (NYC and Atlanta: 8 of 8 cold; OKC
6 of 6; Seattle 10 of 11) — while the calibration, trained on NIGHT
forecast errors and bolted onto the morning lane, was already
pushing warm at most of them. The proposed fix was a morning-lane
thermostat: a second per-station bias learned from morning rows vs
settlements, applied only to `--today` forecasts.

**The walk-forward backtest said NO, and it was not shipped.** Over
468 stored morning city-days (every shift learned only from days
before it, both arms re-voted identically): full strength 150 → 145
hits; every gentler variant (half-shift, strong-evidence-only,
21-day window) gained at most +6 of 468 overall while LOSING ground
on the active nine cities (81 → 79/80), where the money is. The
lean is real in the misses but a trailing shift chases day-to-day
noise as hard as it corrects lean — the existing calibration plus
the day-of reality floor already eat what is eatable. The scoreboard
refused the promotion; conviction did not override it. Do not
re-ship this idea on the same hunch — re-test it only when the
per-model corrections or a genuinely different estimator (e.g. HRRR
same-day guidance, the Model Lab's deferred item) change the
picture. The backtest lives in the session record of Sep 14 2026;
the method (walk-forward on stored morning members, re-voted over
edges.csv bracket sets, graded by settlements) is the required
standard for any future forecast-correction proposal.

## THE AFTERNOON-LEADER TEST (Sep 14, 2026) — TESTED, NO EDGE

The owner's musing, mid-afternoon with Kalshi open: by ~2:30 PM the
winning bracket is obvious, a 65–70¢ favorite still pays ~40%, and
"I can pick five winners every single day just by looking at it."
Tested the same day against our own logs before anything was built —
the exact play, no gates: for each city-day, take the edges.csv scan
nearest 2:30 PM that city's LOCAL time (±90 min), buy the bracket
with the highest YES ask (the market's favorite, price no object),
grade by settlements.csv, Kalshi fees included. 341 graded city-days,
Aug 17 – Sep 12 2026.

**The record said no edge:**

- All afternoon favorites: **232W–109L (68%), −11¢ per $1** after fees.
- By ask price: under 50¢ (uncertain days) 9%, −87¢/$1 — the killer.
  50–60¢: 59%, +5¢/$1. 60–70¢: 70%, +5¢/$1. 70–80¢: 70%, **−8¢/$1**.
  80–90¢: 85%, −1¢/$1. 90¢+: **96% wins and still −1¢/$1** — the fee
  eats the whole payout. Picking winners and making money are
  different questions; late prices are roughly calibrated, so you pay
  for exactly the certainty the thermometer shows, minus fees.
- The +5¢ pocket (50–70¢, 136 bets) is thin noise, nowhere near the
  morning 45–54¢ band's evidence, and one band away from −8¢.
- "Five winners every day": no day in the record swept. Typical days
  the 2:30 favorites lost 3–6 of 20 cities (Aug 18: 9 of 20 lost);
  best stretch 14/15. At $1 that's tuition; at $50 a leg it's a bad
  afternoon every few days.

No afternoon lane was built and nothing in the money path changed.
Building one is an owner money-path decision this record argues
against; any future proposal must beat this same test (afternoon
scan rows re-graded against settlements, fees in) on newer data,
not the feeling that late picks look easy. The reason the feeling
is real but unpayable, stated once: by 2:30 PM the market has read
the same thermometer we poll — the information advantage is gone
and only the fee remains.

**THE OWNER'S REBUTTAL AND THE FORWARD TEST (same day, hours
later).** The owner pushed back: skip the 90¢ers — the play is $50
on every ~73¢ favorite as late in the day as possible. Deeper
slicing found that pocket DID make paper money in the stored month:
each city-day's LAST scan between 1:00–4:59 PM local, $50 on the
favorite when it cost 65–80¢, went **64W–14L (82%), +$495 over 20
days (+13¢/$1 after fees, +10¢ with 2¢ slippage)**. Stated honestly
both ways: the result is FRAGILE — the same rule read one scan
earlier drops to 73% wins and break-even, the 75–80¢ third of the
band lost −7¢/$1 on its own, and the shiny 65–69¢ pocket (23W–2L,
+35¢/$1) is only 25 bets. Fragility under small shifts is the
signature of a data-mined band, so **nothing ships on this slice**.
Instead the rule is pre-registered here and judged OUT OF SAMPLE:
edges.csv already logs everything needed for all 20 cities (the
bench law), so no code was added. Rule, frozen Sep 14 2026: last
scan 13:00–16:59 city-local on the market's own date → the bracket
with the highest YES ask → paper $50 when that ask is 65–80¢
inclusive → grade by settlements.csv, Kalshi fees in. Judge on
data AFTER Sep 14 only (~4 qualifying city-days/day → ~100 by the
October review). If the out-of-sample record holds ≥ +10¢/$1, an
afternoon advisory lane is worth proposing; anything more is an
owner money-path decision then, never before. And the honest scale,
said plainly: even the friendly in-sample slice averaged ~$25/day
at $50 stakes with a −$120 worst day — real if it survives, but not
"a couple hundred every day."

**THE AFTERNOON ENSEMBLE REPLAY (same day, third round) — the
owner's real question answered from stored data.** The owner asked
to log, for two weeks, which bracket the ENSEMBLE MEMBERS would
pick late in the afternoon — benched cities included — because "the
bot is just plumbing, it's the ensemble members," and surely they
wouldn't pick a 10¢ bracket that late. No waiting was needed:
`afternoon_forecasts.csv` has logged a fresh same-day ensemble
fetch (~19:30–23 UTC, calibrated, all 20 cities) every day since
Aug 25 — so the replay ran the full machinery on stored rows: fresh
afternoon members + the day-of reality floor from `temps_log.csv`,
voted over that day's live bracket sets from `edges.csv`, graded by
`settlements.csv`. 240 city-days, Aug 25 – Sep 13. The verdict,
both halves stated:

- **The owner is right that the members sharpen late.** Afternoon
  pick exact-bracket accuracy: **47%**, vs **23%** for the morning
  pick on the SAME city-days. Benched cities: 41% afternoon vs ~15%
  morning — the fresh look helps them most. The medians run close
  (typically within 1–2°F of the settled number).
- **And they still picked the dead bracket half the time.** 120 of
  240 afternoon picks were brackets the live market priced at 15¢
  or less — and those went **0-for-120**. When the late-day model
  disagreed with a market that was reading the actual thermometer,
  the market was right every single time. The other half of the
  picks agreed with the market and cost 90¢+ (99% win rate, no pay
  after fees). $1 on every pick priced 5–85¢: 4W–8L, −60¢/$1.
  Close-on-temperature loses the bracket game: brackets are 2°F
  wide, forecast error late in the day is still ~2°F, and the sigma
  widening (an honesty feature that rides `--today` fetches too)
  scatters the vote — tail brackets collect the scattered members,
  which is exactly how a fresh forecast picks a 1¢ tail.
- **No afternoon ensemble lane, and nothing to build**: the data
  the owner asked to collect is ALREADY collected daily and forever
  (afternoon_forecasts + edges + settlements + temps), so this
  replay is re-runnable by any session at any time — re-grade it at
  the October review with double the days. The right future
  candidate for genuine afternoon skill is a same-day short-range
  model, i.e. the `hrrr` passenger the Model Lab added Sep 14 — an
  un-widened hourly-refresh model is a different estimator, which
  is what the morning-thermostat rejection says re-tests need.

## THE ENSEMBLE VERDICT AND THE SAME-DAY LAB (Sep 14, 2026, night) — OWNER DECISION

The owner's words after the afternoon ensemble replay, recorded so
future sessions know exactly where trust stands: the global
ensembles have now been graded at night (29% wins, benched), in the
morning (better, still modest), and late afternoon (picking 1¢ dead
brackets half the time) — "they're absolutely worthless... you can
never adjust them, you can never train them... nothing could happen
that could make me trust them again," and HRRR "may be what we
need." Two owner decisions came out of it, plus one honesty note:

- **Nothing changes on the money path right now** — the owner's own
  call ("we're not changing anything right now, that's too wild").
  The morning lane keeps running exactly as configured on the active
  nine. The counterpoint stays on the record, as honesty requires:
  the morning lane on the active-nine cities stands 23W–9L, +53¢/$1
  settled — the one slice of ensemble output that has ever made
  money — and the ensembles beat blind chance in every window (47%
  afternoon vs ~17% blind), so "bet against them" would lose worse,
  and NO-betting stays banned regardless. Distrust is recorded;
  the scoreboard, not the mood, decides the replacement.
- **The October review is now also a REPLACEMENT review.** The owner
  pre-declares the appetite: if a candidate (HRRR first) proves
  materially better on the records, replacing the global ensembles
  in the vote is on the table — same evidence bar as every
  promotion, owner decides on the numbers.
- **THE SAME-DAY LAB shipped the same night** (samedaylab.yml →
  `model_research_today.csv`, contract in the table): the nightly
  Model Lab only logs HRRR's for-TOMORROW guess, which is not the
  question — so the lab now logs the candidates' TODAY numbers twice
  a day (14:12 UTC, inside the buy-window hours, and 19:42 UTC,
  afternoon), all 20 cities, benched included. By the October review
  that is ~35+ same-day city-days per slot to grade against
  settlements with the replay method. Research only, dead-feed law,
  no secrets, nothing on the money path reads it. First run
  verified green same night: 20 cities × hrrr/nws/icon, 60 same-day
  rows.

**THE NWS PREVIEW (same night, recorded early on purpose).** Graded
on the nights already stored (Aug 31 – Sep 13, 7 nights/city): the
NWS point forecast's night-before number lands in the EXACT settled
bracket **33% vs the money pool's 28%** — and in the benched cities
**34% vs 24%**: the government forecast is best precisely where the
ensembles are worst (DC, Minneapolis, San Antonio, Las Vegas each
5-of-7). Median miss agrees (nws 1.50°F beats pool 1.60°F overall,
and it is raw while the pool is calibrated). Stated caveat: n=7
nights per city — a preview, not a verdict. The October review now
has three candidates building records on both horizons (nightly +
the same-day lab): hrrr, nws, icon. Promotion or replacement stays
an owner decision on those records.

## THE SELL-SIGNAL FIXES (Sep 14, 2026) — OWNER INCIDENT

Context every future session must know: **the owner mirrors the
bot's picks with their own much larger money, and uses the swoop
board as the sell trigger.** The bot's $1 ledger understates what a
board defect costs by an order of magnitude — the owner reported
roughly $4,000 of personal losses mirroring seven months of picks.
Treat every advisory-board latency or wording bug as a money bug.

The incident (Sep 14): Philadelphia's 76–77° bracket was bought at
9:10 AM ET. The day's high — 77.0° — had been BANKED at 2:15 AM
ahead of a cold front; by mid-morning the station read 71.6° and
falling. The overshoot card still wore the heating-afternoon words
("heat of the day, one more push blows past this bracket"), and the
owner, reading it through a stale home-screen copy two hours after
the buy, sold into a 33¢ market. Two defects, both fixed in one
commit:

1. **The morning blind spot.** The swoop board's dense 15-minute
   band started at 16:00 UTC — two-plus hours after the first 13:00
   UTC buys (Philadelphia that day: bought 13:10, first graded
   15:04). The band now starts at **13:00 UTC** (poll.yml relay
   condition + swoop.yml backup crons, moved together).
2. **The banked-high fix.** `highs.latest_readings()` (new, same
   pass and raw source as `highs_today` so the two can never
   disagree) gives every card the station's freshest reading, shown
   as "Now: X°". When that reading sits `BANKED_DROP_F` (1.5°F) or
   more under the day's high, the overshoot card says the true shape
   of the day — "that high is BANKED... this wins if the heat stays
   away; it dies only if the afternoon climbs back past the cap" —
   instead of the live-climb words. The tag itself stays OVERSHOOT
   RISK (a second warm-up is a real risk); only the story changed.
   The freshness laws are untouched. Note the iPad gotcha, told to
   the owner: a home-screen bookmark serves a frozen copy — the
   "built X m ago" label turning red is the tell; refresh in Safari.

3. **THE HOME-SCREEN SELF-HEAL (same day, second incident).**
   "Refresh in Safari" was an explanation, not a fix, and the same
   frozen home-screen copy cost the owner again within hours: the
   cached swoop page didn't even list the city being sold, and the
   sell signal reached them two hours late through Safari. The
   frozen copy is Apple's cache, not a bot failure — but the boards
   are the owner's money surfaces, so the pages now heal themselves:
   - `swoop.html` (fully pre-built, so a frozen copy can only heal
     by replacing itself): on open, on every return to the
     foreground, and every 2 minutes, it fetches
     `swoop_pulse.json?t=<now>` with `cache:'no-store'` (unique
     query + no-store beats every cache layer including the CDN
     edge); if the live board is 3+ minutes newer than the loaded
     copy's embedded `BUILD_MS`, it jumps to
     `swoop.html?fresh=<now>` — a cache-busting URL of itself. The
     pulse and the page ship in the same commit, so after healing
     the two agree and the check goes quiet — no reload loop.
   - `index.html` was already safe on data (all fetches are
     `?t=`-busted no-store on a 2-minute timer) but could sit up to
     2 minutes stale at the exact moment of reopening; it now
     reloads its data the INSTANT the page returns to the
     foreground (visibilitychange + pageshow).
   The same self-heal pattern is the template for sports.html and
   whales.html if their staleness ever bites (they rebuild 2x daily
   / 2-hourly, so the window is smaller); rolling it out there is a
   display-only change any session may make.

## THE CARD EXPLAINS THE FLOOR (Sep 14, 2026) — OWNER CATCH

The owner cross-checked three Station Board cards' pick brackets
against their own forecast medians and asked how they could disagree
(Philadelphia: vote 76–77, median 77.6; DC: 57.3% on 78–79, median
79.5; LA: 29.3% on "83 or above", median 81.1). All three are honest
mechanics, verified against the raw rows that day, and the card now
states them instead of looking broken — the split-note lineage
continued. Explanation priority in the WHY line (one line fires,
never a lecture): **overtaken** (the station has since read past the
pick's cap — the pick is from an earlier scan and the day outran it;
DC's exact shape) > **the floor** (the vote runs AFTER the day-of
reality floor, so members below a fresh observed high are raised to
it and stack the vote in the thermometer's own bracket, while the
displayed median is the raw pre-floor forecast; Philadelphia's exact
shape — the banked 77.0 pulled the vote to 76–77) > **the model
split** (Sep 12, unchanged) > generic spread. Display only; no gate
or vote changed. The deeper lesson, recorded: when two numbers on
one card come from different pipeline stages, the card must say so
— that gap is exactly where the owner loses trust.

## ROADMAP — how this grows

Flat $1 stakes are **temporary tuition**. The record in `results.csv`,
sliced **per-city and per-strategy**, decides everything:

- Cities with proven bad hit rates get **benched**. Prime suspect:
  **KNYC Central Park** (sheltered station, runs cool). Bench on evidence
  from the scoreboard, not on vibes.
- Sizing eventually concentrates into the strategies and cities the record
  proves accurate (the `pick` vs `edge_pick` columns exist so pick-first
  can be graded against the old edge rule on the same days).
- **The scoreboard promotes; conviction never does.** No sizing change, no
  city change, no strategy change without settled results backing it.

## Working rules for future sessions

- Before changing any writer, grep for every reader of that CSV and keep
  the header, writer, and readers in sync **in one commit**.
- Never weaken a guard because it "blocks trades" — most guards exist
  because a missing guard once lost money. Find out why it's blocking.
- Keep the scanner's and trader's cost bands identical.
- Test reasoning against the actual CSVs in the repo; they are the ground
  truth of what the code really did.
- Explain your findings to the owner in plain English, and deliver
  complete files.
- **The owner does not press buttons (Sep 14 2026, owner decree).**
  The owner's words: "when me and you talk it's me venting a problem
  to you... I want you to just go do it. When I have a problem I'll
  tell it to you and we just fix it if it's fixable." Two rules came
  out of it. (1) A conversation with the owner is often venting, not
  a work order — fix what is plainly broken, but do not treat every
  musing as a mandate, and NEVER end a fix by handing the owner
  homework. (2) Sessions merge their own pull requests after
  verifying them — the owner is never asked to tap Merge. The one
  thing that still needs the owner's explicit yes IN CONVERSATION is
  a money-path decision (gates, sizing, benches, model promotions —
  the laws above are unchanged); once the owner has said yes, build
  it, verify it, and merge it yourself.
- **The by-all-means mandate (Sep 14 2026, owner's words):** "We're
  gonna make this thing work by all means necessary... I'm giving
  you permission — when you see something, do it... take some of
  those benched ones and play around with them... if you can get it
  on your own, just go get it." What this authorizes: proactive
  RESEARCH — paper lanes, replays, passenger models, free data
  feeds, experiments on the benched cities' paper records — built,
  verified, and merged without asking. What it does NOT change: the
  money path still moves only on the owner's explicit yes in
  conversation, sizing/gates/benches stay owner decisions, and the
  scoreboard still promotes — the mandate widens what gets TESTED,
  never what gets TRUSTED.
- **The standing supply line (Sep 14 2026, owner's words):** "You
  tell me I need this tool, go get it, and that shall be done." When
  a purchase or account genuinely earns its place on the evidence
  (an API plan, a data feed, a connector), don't hedge and don't
  bury it — tell the owner in ONE plain sentence: what it is, what
  it costs, and what the record says it buys. The owner handles the
  getting. Never spend this trust on unproven wants — the scoreboard
  justifies every ask, same as every gate.
