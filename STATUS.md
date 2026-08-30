# STATUS.md — where the build actually stands

Written Aug 30, 2026, in response to the new standing orders. Plain English.

## First, an honest problem with the orders themselves

The standing orders say to compare the codebase against `WEATHER_BOT_SPEC.md`
sections 1–9 and to wire in `guards.py`. **Neither file exists in this
repository**, and neither does the §10 build order they reference. There is
no spec to compare against, no `guards.py` to wire in, and no
`guards.replay()` to run. Rather than invent a spec after the fact, this
file maps the nine things a weather-betting bot needs onto what actually
exists here today. If the real `WEATHER_BOT_SPEC.md` lives somewhere else,
add it to the repo and this file gets redone against it, section by section.

One more thing said plainly: this repo is not a fresh build waiting for a
first session. It is a **running, live-money system** with an operating
manual (`CLAUDE.md`), months of stored data, and a scoreboard of 146 settled
bets. The status below reflects that.

## Section-by-section inventory

| # | Function | Status | Where it lives |
|---|---|---|---|
| 1 | City/station map (20 cities, hand-verified) | **EXISTS** | `cities.py` — 20 series → station, all verified against Kalshi rules panels (`RULES_AUDIT_FINDINGS.md`) |
| 2 | **Data storage** (priority zero) | **EXISTS and RUNNING** | `poller.py` on an all-day relay (every 15 min) → `temps_log.csv`. **20/20 stations, 930 station-days stored since Jul 9, 2026.** The 30-station-day minimum was passed long ago. |
| 3 | Forecasting | **EXISTS** | `forecast.py` — GFS (31) + ECMWF (51) ensemble members via Open-Meteo, bias-corrected and spread-widened per station |
| 4 | Market scan + pick | **EXISTS** | `scanner.py` — pick-first (most ensemble members wins), price is only a gate (45–60¢ band, min 40% vote share), day-of 9–11 AM local window |
| 5 | Trade execution | **EXISTS, LIVE** | `trader.py` — $1 per bet, max 5 orders / $10 per run, 1 position per city per day, fail-closed if the account can't be read |
| 6 | Settlement + scoreboard | **EXISTS** | `settle.py` → `results.csv` (grades only by Kalshi's own result field); `settlements.py` → official settled ranges |
| 7 | Calibration | **EXISTS** | `calibration.py` — learns per-station bias and error spread from settled truth, not our own thermometer; monitored via `autopsy.md` §4 (claimed % vs delivered %) |
| 8 | Guards / safety rails | **PARTIAL** | No `guards.py` file. The guards themselves exist, spread across the code: price band, vote minimum, sanity gap, sizing caps, fail-closed exposure check (`scanner.py`, `trader.py`), plus `watchdog.py` checking seven pulses every ~15 min. **Missing: a replay harness and any pytest suite — there are zero automated tests in this repo.** |
| 9 | Reporting / monitoring | **EXISTS** (different shape than the orders describe) | Station Board (`index.html`) answers "did it buy and why" per city; swoop board grades open positions; `autopsy.md` is the deep report; `watchdog.py` + `health.json` turn failures into a red banner within ~15 min. There is no emailed "evening report" — GitHub emails only on red runs. |

## What the standing orders ask for that genuinely does not exist

- `WEATHER_BOT_SPEC.md` — missing. Blocks any real §-by-§ comparison.
- `guards.py` with `guards.replay()` — missing, and its contract is defined
  only in the missing spec, so it was **not** invented from guesswork
  (see `DECISIONS.md`).
- A pytest suite — missing entirely.
- `DECISIONS.md`, `CHANGELOG.md` — created in this session.

## Where the standing orders conflict with owner decisions already on record

These were **not** adopted, because `CLAUDE.md` records the owner deciding
the opposite, with evidence:

1. The orders describe a bot that "places bets with a real edge." **Edge
   betting is banned here.** The pick-first law (Aug 6, 2026) exists because
   edge-ranking went 9–21 and lost money; edges are logged for grading only
   and decide nothing.
2. The orders imply paper trading until 30 station-days are stored. The bot
   is **already live** by explicit owner decision, and 930 station-days are
   stored. Going back to paper is an owner call, not a builder call.

## Against the standing orders' own definition of "done"

The four tests, answered plainly:

- **14 straight days unattended, zero manual fixes** — NO. Until the
  Aug 30 relay rework, dropped GitHub crons meant the owner pressed Run by
  hand on money days. The relays exist precisely to fix this; the 14-day
  clock effectively starts now.
- **Daily report landing every evening** — PARTIAL. The Station Board is
  always current, but nothing "lands" in the owner's hands each evening.
- **Calibration holding (~80% intervals)** — NOT YET PROVABLE. The Aug 24
  accuracy rebuild and Aug 26 feedback fix are too recent; autopsy §4 is
  the standing monitor and needs ~2 more weeks of settled bets.
- **Positive net P&L after fees** — NO. 146 settled bets: 52 wins, 94
  losses, **net −$20.95**. The 45–60¢ band and 40% vote gate (owner
  decisions of Aug 28–30) are the active attempt to fix this; they get
  reviewed ~Sep 11 on settled results.

**So: the bot is not done, and this file says so plainly.**

---

## END-OF-SESSION REPORT (plain English)

    WHERE WE ARE:   7 of 9 areas built and running; missing a test/replay
                    harness and a hand-delivered evening report
    WHAT I DID:     Took stock of the codebase against the new standing
                    orders and wrote the status/decision files. Then, on
                    the owner's direct ask to cut losses: benched Oklahoma
                    City (0W-7L) and Dallas (1W-9L) from real-money buys
                    on scoreboard evidence — they lose under every rule
                    set, and together are half the total net loss. Both
                    still tracked on paper; Denver/DC/SF/Austin put on a
                    written watch list, not benched.
    WHAT'S NEXT:    Sep 11 review of the bench + price band + vote gate,
                    all on settled results.
    DATA STORED:    930 station-days across all 20 stations (need was 30 —
                    passed long ago)
    ANYTHING WRONG: Yes — the scoreboard is net negative (−$20.95 over 146
                    settled bets). Not a code failure; the tightened price
                    band and vote gate the owner chose Aug 28–30 are the
                    fix on trial, reviewed ~Sep 11.
    BOT STATUS:     LIVE ($1 bets, morning lane only)
