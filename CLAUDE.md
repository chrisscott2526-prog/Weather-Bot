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

## THE STRATEGY IS PICK-FIRST (Law of Aug 6, 2026)

1. **Pick the bracket.** For each city and market date, the ensemble
   (GFS + ECMWF pooled since Aug 24 2026, ~82 members) votes: the
   bracket containing the **most ensemble members** is the pick.
   Full stop. Price plays **no part** in choosing it.
2. **Price is only a gate.** If the pick's YES ask is inside
   `MIN_PICK_COST..MAX_PICK_COST` (**40¢–60¢ since Aug 28 2026 — the
   two-week band trial, see its own section below**; the history:
   8¢ floor → 15¢ on Aug 24 2026 — see the accuracy rebuild — → 20¢
   on Aug 28 2026 ("no long shots") → the 40–60¢ trial that evening).
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
   - `MIN_PICK_PROB = 35`: if even the top bracket has under 35% of
     members, the day is too uncertain — no bet.
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
  the night runs that placed them.
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
- `MIN_COST, MAX_COST = 40, 60` — must always equal the scanner's gate.
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
                forecasts vs actuals. The actual, in order of trust
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

poller.py    (every 15 min, and   NWS METAR temps -> temps_log.csv
              piggybacked inside
              morning.yml +
              swoop.yml runs)
                                  (the RAW source of truth for highs);
                                  also regenerates daily_highs.csv from
                                  it -- a derived summary NO code reads
highs.py     (library, no cron)   THE one way a daily high is computed:
                                  temps_log.csv -> per-station local-day
                                  highs + freshness. Used by swoop_alert,
                                  calibration, autopsy, poller; mirrored
                                  in JS by index.html
settlements.py (4x daily)         Kalshi settled result fields (unauth)
                                  -> settlements.csv: the OFFICIAL high
                                  range each city's markets paid on;
                                  feeds the board's "Yesterday" line
                                  AND (Aug 24 2026) the actuals that
                                  calibration and autopsy learn from
swoop_alert.py (every 15 min      advisor board -> swoop.html, swoop_log.csv
              16:00-01:59 UTC,    (polls its own fresh temps first;
              2-hourly rest)      grades each position on its CITY'S
                                  local day, so West Coast evenings
                                  stay on the board)
sports_scanner.py (2x daily)      sharps consensus vs Kalshi props ->
                                  sports.html card, sports_picks.csv;
                                  grades by Kalshi settlement ->
                                  sports_results.csv. ADVISORY ONLY.
sports_probe.py  (on demand)      read-only inventory: what the Odds API
                                  plan carries + Kalshi's live sports
                                  series. Run sports.yml with probe=true.
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
| `forecasts.csv` | `forecast.py` | `forecast_date,station,city,forecast_high_f,fetched_utc,members,bias_applied` (members pipe-separated, already calibrated, pooled across GFS+ECMWF since Aug 24 2026; bias_applied added Aug 26 2026 = the correction already subtracted from that row's members, so calibration can reconstruct the raw error — blank on old rows, read as 0; a morning `--today` row is fetched on its own forecast_date between 06:00–22:59 UTC — `csvio.is_morning_row` is the one true classifier, there is no extra column. The hour window exists because a delayed nightly cron slips past UTC midnight and stamps the same date; those rows are still night) |
| `afternoon_forecasts.csv` | `forecast.py --today --out afternoon_forecasts.csv` (afternoon.yml, 19:30 UTC) | same header as `forecasts.csv` (RESEARCH LOG ONLY, added Aug 24 2026 — measures the value of forecast freshness; **no trading or calibration code reads it**, and it must stay that way: pointing scanner/calibration at it would poison the race and the bias table) |
| `temps_log.csv` | `poller.py` | `utc_time,station,city,temp_f,obs_time_utc` |
| `daily_highs.csv` | `poller.py` (full rewrite each run, regenerated from `temps_log.csv` via `highs.py`) | `date,station,city,high_f,last_update_utc,obs_time_utc` (last_update/obs_time = poll/observation time of the day's peak; derived human-readable summary ONLY — since Aug 21 2026 **no code reads it**; retirement candidate) |
| `settlements.csv` | `settlements.py` (full rewrite each run) | `date,station,city,series,low_f,high_f,n_markets,n_settled,source,utc_offset_hours,checked_utc` (blank low/high = unbounded tail; row exists only when a market settled YES — exclusions alone never make a row) |
| `edges.csv` | `scanner.py` | `scanned_utc,city,market,subtitle,floor,cap,yes_ask,no_ask,model_prob_pct,edge_yes,edge_no,bias_f,spread_scale,sigma_f,n_members,pick,edge_pick,would_bet,strategy` (strategy added Aug 20 2026, old rows backfilled `night`; sigma_f added Aug 24 2026 = the calibration's learned target error spread in °F — it replaces the old unitless spread_scale ratio, whose column stays so old rows keep meaning; new rows leave spread_scale blank, the two numbers must never share a column) |
| `trades.csv` | `trader.py` | `placed_utc,ticker,subtitle,side,count,limit_cents,model_pct,edge,live,status,order_id,strategy` (strategy added Aug 20 2026, old rows backfilled `night`) |
| `results.csv` | `settle.py` | `graded_utc,ticker,city,action,cost_cents,count,fee_cents,market_result,result,pnl,strategy` (fee_cents added Aug 18, strategy Aug 20 2026; old rows backfilled `night`; readers treat a blank strategy as night) |
| `sports_picks.csv` | `sports_scanner.py` | `scanned_utc,sport,shelf,game,detail,commence_utc,series,ticker,side,pick,books_pct,kalshi_cents,fee_cents,gap_cents,n_books,shown,why` (wiped + new header Aug 19, 2026 — edge-era rows graded a dead rule) |
| `sports_results.csv` | `sports_scanner.py` | `graded_utc,sport,shelf,game,detail,ticker,side,pick,books_pct,kalshi_cents,gap_cents,market_result,result,pnl` (wiped same commit) |

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
- **A failed pass warns and the next pass retries; any failed pass
  turns the finished run red.** Same honesty rule as ever: a problem
  may not scroll away green. An insufficient-balance order no longer
  kills the rest of the day's passes — it flags red at the finish
  while later passes keep buying the cities that can still be bought.

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
