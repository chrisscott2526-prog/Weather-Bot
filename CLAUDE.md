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

1. **Pick the bracket.** For each city and market date, the GFS ensemble
   votes: the bracket containing the **most ensemble members** is the pick.
   Full stop. Price plays **no part** in choosing it.
2. **Price is only a gate.** If the pick's YES ask is inside
   `MIN_PICK_COST..MAX_PICK_COST` (8¢–68¢ in `scanner.py`), buy is flagged.
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
   - Under `MIN_PICK_COST` (8¢): the market is screaming we're wrong —
     believe it, don't "value-buy".
   - No ensemble members for a (date, city) → **SKIP loudly**.

## THE RACE: NIGHT vs MORNING (Aug 20, 2026)

Two strategies run the same pick-first rules against the same markets,
and the scoreboard decides which one earns the money:

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
- `MIN_COST, MAX_COST = 8, 68` — must always equal the scanner's gate.
  (They were once 15/10, an impossible range that silently placed zero
  trades for days.)
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
- `daily_highs.csv` is the **hourly METAR instrument reading so far** —
  Kalshi settles on the NWS **CLI Daily Climate Report**, a different
  product that catches between-hour peaks. They usually agree; they are not
  the same number. Never present the board as "what will settle."
- **Settlement truth outranks any thermometer.** Kalshi's own `result`
  field is the only thermometer that pays. `settle.py` grades only markets
  Kalshi says are settled/finalized; `calibration.py` overrides the
  instrument reading whenever one of our own settled bets proves the high
  landed in a different bracket.
- Failures print and skip. An "ERROR" row with a blank date is a trap for
  every downstream reader (this exact trap poisoned `forecasts.csv` once).
- **A finished day's high is never answered from repo CSVs alone.** When
  asked what a day's high WAS (past tense, day complete), the poller's
  running max in `daily_highs.csv` is a **floor, not the final** — it only
  samples hourly METARs. The authoritative answer is the NWS **CLI Daily
  Climate Report** for that station (published ~5:30 PM local); fetch it
  or weather.gov's station page live if network access allows. If it
  can't be fetched, say plainly: "our last logged reading was X at
  [time], but the official CLI high may be higher — check weather.gov."
  Never present the logged running max as the day's final high after the
  day ends.
- **Reading age = minutes since the station's latest reading** in
  `temps_log.csv` (what the Station Board shows) — never the timestamp of
  the reading that set the daily high, which is hours old by every
  afternoon. The swoop board once called a 41-minute-fresh thermometer
  "162m old" that way and suppressed valid tags (fixed Aug 21, 2026 in
  `latest_reading_ages` in `swoop_alert.py`).

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
  - `git pull --rebase` **with a conflict fallback** before push (see
    `poll.yml` for the pattern) — 15-minute polling means pushes race.
  - Every job must carry `timeout-minutes`.
- **Sports whitelist (Aug 2, 2026).** Substring matching on series names
  swept in inning props and player-signing markets and reported fantasy
  40¢ "edges". Real moneyline edges are 2–5¢ and rare. Whitelist only.

## HOW THE PIECES FIT (data flow)

```
forecast.py  (nightly 23:00 UTC)  GFS 31-member ensemble via Open-Meteo,
     |                            calibrated per-station -> forecasts.csv
     v
scanner.py   (9x daily + after forecast)  Kalshi open markets + ensemble
     |                            votes -> picks + gates -> edges.csv
     v
trader.py    (9x daily + after scan)  latest scan's would_bet=YES rows,
     |                            $1 each -> Kalshi orders -> trades.csv
     v
settle.py    (daily 12:20 UTC)    asks Kalshi how each market settled
     |                            -> results.csv  (THE scoreboard)
     v
calibration.py  learns per-station bias from NIGHT forecasts vs
                actuals, settlement-pinned; feeds back into
                forecast.py (both the nightly and --today pulls).

morning.yml  (daily ~13:45 UTC)   the race's morning lane, one job:
                                  forecast.py --today ->
                                  scanner.py --strategy morning ->
                                  trader.py --strategy morning
                                            --keep-resting
                                  (same files, strategy=morning rows)

poller.py    (every 15 min)       NWS METAR temps -> temps_log.csv,
                                  running local-day highs -> daily_highs.csv
settlements.py (4x daily)         Kalshi settled result fields (unauth)
                                  -> settlements.csv: the OFFICIAL high
                                  range each city's markets paid on;
                                  feeds the board's "Yesterday" line
swoop_alert.py (4x afternoon)     advisor board -> swoop.html, swoop_log.csv
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
| `forecasts.csv` | `forecast.py` | `forecast_date,station,city,forecast_high_f,fetched_utc,members` (members pipe-separated, already calibrated; a morning `--today` row is fetched on its own forecast_date between 06:00–22:59 UTC — `csvio.is_morning_row` is the one true classifier, there is no extra column. The hour window exists because a delayed nightly cron slips past UTC midnight and stamps the same date; those rows are still night) |
| `temps_log.csv` | `poller.py` | `utc_time,station,city,temp_f,obs_time_utc` |
| `daily_highs.csv` | `poller.py` (full rewrite each run) | `date,station,city,high_f,last_update_utc,obs_time_utc` |
| `settlements.csv` | `settlements.py` (full rewrite each run) | `date,station,city,series,low_f,high_f,n_markets,n_settled,source,utc_offset_hours,checked_utc` (blank low/high = unbounded tail; row exists only when a market settled YES — exclusions alone never make a row) |
| `edges.csv` | `scanner.py` | `scanned_utc,city,market,subtitle,floor,cap,yes_ask,no_ask,model_prob_pct,edge_yes,edge_no,bias_f,spread_scale,n_members,pick,edge_pick,would_bet,strategy` (strategy added Aug 20 2026, old rows backfilled `night`) |
| `trades.csv` | `trader.py` | `placed_utc,ticker,subtitle,side,count,limit_cents,model_pct,edge,live,status,order_id,strategy` (strategy added Aug 20 2026, old rows backfilled `night`) |
| `results.csv` | `settle.py` | `graded_utc,ticker,city,action,cost_cents,count,fee_cents,market_result,result,pnl,strategy` (fee_cents added Aug 18, strategy Aug 20 2026; old rows backfilled `night`; readers treat a blank strategy as night) |
| `sports_picks.csv` | `sports_scanner.py` | `scanned_utc,sport,shelf,game,detail,commence_utc,series,ticker,side,pick,books_pct,kalshi_cents,fee_cents,gap_cents,n_books,shown,why` (wiped + new header Aug 19, 2026 — edge-era rows graded a dead rule) |
| `sports_results.csv` | `sports_scanner.py` | `graded_utc,sport,shelf,game,detail,ticker,side,pick,books_pct,kalshi_cents,gap_cents,market_result,result,pnl` (wiped same commit) |

Calibration is applied **exactly once**, at forecast time
(`calibrate_members` inside `forecast.py`). The scanner only reports the
calibration table for display — never re-apply it.

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
