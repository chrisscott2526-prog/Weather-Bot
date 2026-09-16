# DECISIONS.md — builder decisions the owner can overrule

One line of why per decision, newest first, as the standing orders require.

## 2026-09-16 (later) — the shaded pair (owner order: "add Atlanta and San Francisco... subtract 1 degree on Atlanta and add 1 degree to San Francisco")

1. **The shade is applied to the NWS number before the bracket is
   chosen, and before the reality floor.** Why: it corrects the
   forecast's recorded lean (Atlanta all-warm misses, SF nearly
   all-cool), and the floor must always outrank any forecast.

2. **nws_f keeps logging the RAW NWS number.** Why: the raw record
   grades the NWS itself; the selected row grades the shaded
   decision — two questions, both answerable forever.

3. **Backtest stated plainly at ship time: Atlanta −1 went 2-of-7,
   SF +1 went 1-of-7 on the stored nights** (SF's lean ran 2–3°, so
   +1 usually falls short). Why recorded: the owner chose this as
   their own test with the numbers on the table — ~$2/day max
   exposure, the band still gating, and the shaded-vs-raw record
   accruing daily for the October review.

## 2026-09-16 — THE NWS LANE (owner order, verbatim intent: "bench everything except Washington, Las Vegas, Minneapolis, San Antonio, New Orleans... only allowed to purchase what NWS says on those")

1. **The NWS number is fetched LIVE at scan time, never read from
   model_research.csv.** Why: the research-log law ("nothing that
   trades may ever read it") stands; sharing the fetch function is
   code reuse, sharing the file would be a law break.

2. **The pick column stays the ensemble's pick everywhere; the NWS
   choice rides a new nws_f column on its own bracket's row.** Why:
   every existing record (the race, the bench paper, the judge
   comparison) keeps accruing unbroken, and the NWS decision is
   still self-documenting in the data.

3. **The 45–54¢ band still gates the NWS bracket; MIN_PICK_PROB does
   not.** Why: the band is the second expert (on stored days where
   the NWS bracket priced under 45¢, the NWS was usually wrong), and
   a member-share bar cannot apply to a single-number expert.

4. **The reality floor applies to the NWS number.** Why: a fresh
   observed high the station already reached outranks any forecast
   — same physics as the member floor, same freshness rule.

5. **Stated caveat recorded with the ship**: the five cities were
   chosen on the same 7 graded nights the 9W–1L replay ran on, so
   the replay is partly circular and the honest test starts out of
   sample. The owner made the call with the sample size stated —
   the Handful Cut precedent.

## 2026-09-16 — the NWS second-opinion test (owner hypothesis: the local forecast should veto far-away picks)

1. **Graded the hypothesis from stored data instead of building a
   gate** (`nws_second_opinion.py` + CLAUDE.md section). Why: the
   by-all-means mandate authorizes research; gates are owner
   decisions, and the veto's real-money sample is one bet (a win).

2. **NWS verified within one bracket 86% of 140 city-days; picks
   2+ brackets from NWS ran 5W–34L on paper.** Why recorded: the
   October review already weighs promoting NWS — this pre-registers
   the "within one bracket of NWS" gate as a candidate to judge on
   post-tail-fix data.

3. **Nothing on the money path changed.** Why: the 45¢ price floor
   already blocks every cheap veto-zone pick, so today the veto has
   nothing to protect and n=1 to argue from.

## 2026-09-12 — per-model bias (owner: "Go for it", after catching the wild brackets themselves)

1. **Each ensemble member is now shifted by its own model's learned
   bias, not one station-wide number.** Why: the pooled bias is
   dominated by ECMWF's 51 votes, and where the two models lean
   opposite ways it manufactured phantom extreme-bracket clusters
   (New Orleans 39% on "95° or above" against a 90.7° median).

2. **A model needs 4 tagged settled nights at a station to earn its
   own bias; otherwise its members use the pooled bias.** Why: the
   fallback is the exact old behavior, so thin history can never
   make the fix worse than what it replaced.

3. **bias_applied stores the exact per-slice correction
   (`pool:…|gfs:…|ecmwf:…`), measured after widening.** Why: the
   Feedback Fix's raw-error reconstruction must stay exact per
   model, with no guessing of the widening scale.

4. **Nothing else moved** — gates, sizing, widening, the scanner's
   display table, and the pick-first law are untouched. Why: the
   gates were the part that worked that morning.

## 2026-09-10 (later) — the league expansion (owner ask: CFB, NFL, MLB, NBA, tennis, golf on the card)

1. **Verified every new Kalshi series against live markets before
   whitelisting it** (two probe runs, Sep 10): KXNCAAFGAME (200
   open), KXNBAGAME (Oct slate open now), KXATPMATCH/KXWTAMATCH (US
   Open semis). Why: the whitelist law; a series title read by hand
   is the only admission ticket.

2. **New sports match by name against Kalshi's own subtitles, not a
   hand-typed code table.** Why: NCAAF/NBA/tennis event tickers
   carry no game time and variable-length codes; 130+ hand-guessed
   school codes would be invented data, while Kalshi's subtitles are
   verified on every scan. The rule is exact-or-full-word-prefix,
   both sides must pair inside one event on the right date, and any
   ambiguity refuses loudly.

3. **Golf stays off, with the reason recorded.** Why: the odds feed
   quotes only tournament-winner outrights (favorites ~20-30%, under
   every pick and leg bar — the honest golf card would be permanently
   empty), and KXGOLFTOURN had zero open markets to verify. Two
   preconditions to revisit: a matchup-odds source, and live series
   verification.

4. **Flagged the Odds API credit wall to the owner instead of coding
   around it.** Why: 106 of 500 free monthly credits remained at
   ship time and the wider card needs ~480/month — the fix is the
   owner's plan upgrade, not a silent thinning of the card. A dry
   key fails RED by the dead-feed law.

5. **NBA shelves ship now but stay naturally silent until the season
   is inside the 30-hour scan window** (first games Oct 20). Why:
   MAX_HOURS_OUT already gates it; no special-casing needed.

6. **The weather money lane is untouched.** The expansion lives
   entirely in sports_scanner.py and its CSVs; the combo board only
   READS edges.csv. Nothing that trades weather changed.

## 2026-09-10 — the combo board (owner ask: "high paying combos, any sector")

1. **Read "highest payout" as "stack MORE real favorites", never as
   "buy longer shots."** Why: payout and probability are the same
   number upside down, and every long-shot record in this repo lost
   (under-20¢ weather bets 2W–22L; the edge-first sports card 9–21).
   The board's payout ladder tops out at 8 legs of 60%+ favorites.

2. **Weather legs need BOTH experts at 60%+ (ensemble member share
   AND live Kalshi bid), stating the lower number.** Why: the
   ensemble's claimed probability alone is proven overconfident
   (autopsy §4: 55%+ claims delivered ~35%), while the dual bar
   backtests 14W–2L (88%) stating only ~66% — understating, the only
   allowed direction. Sixteen legs is thin; combo_results.csv grades
   the rule for real from day one.

3. **Sports legs are exactly the parlay pool; combos exist only when
   at least one weather leg qualifies.** Why: a sports-only stack IS
   the parlay board, and logging the same stack under two names would
   double-count the record.

4. **Benched cities never supply a leg, and the bench list is parsed
   from scanner.py's source at run time, fail-closed.** Why: a board
   of "most likely winners" cannot seat a city the scoreboard benched
   for losing, and a mirrored copy could drift (watchdog precedent).

5. **No sector without a calibrated expert and hand-verified series
   was added.** Why: politics/econ/etc. have no sharps and no
   ensemble here; Kalshi's own price is not an expert we can grade an
   edge against, and series discovery is banned. Adding a third
   sector is an owner decision that needs both prerequisites first.

6. **No dollar P&L on combos; fair_payout = 1/combined prob is
   stated instead, with the card saying Kalshi has no combo ticket.**
   Why: no venue's combo payout is knowable (honesty rules), and the
   owner must not read the multiplied number as something buying the
   legs individually on Kalshi would pay.

## 2026-08-30 (evening) — full audit on the owner's ask ("say it and let's correct it")

11. **Added the end-of-day resting-order sweep** (`trader.py
    --sweep-resting`, run by morning.yml when the buying day ends).
    Why: with the night cancel runs benched, an unfilled morning order
    sat on the book where it could fill hours-stale AND be graded by
    settle.py as a bet that never filled — a scoreboard poisoner found
    by audit before it struck.

12. **Did NOT move the buying window later in the day.** Why: grading
    every scan hour against settlements shows 9–11 AM in-band picks win
    62%/53% while 11 AM–2 PM shows no improvement (47–56% on thinner
    samples) — and after ~2 PM city time there is almost nothing left
    priced inside 45–60¢ to buy at all.

13. **Did NOT touch the 45–60¢ band or the 40% vote gate.** Why: they
    are one day old and already have a scheduled evidence review
    (~Sep 11); changing them again tonight would be vibes, not
    scoreboard.

14. **Flagged the funding problem to the owner instead of coding around
    it.** Why: all six checkable insufficient-balance orders (Aug 24,
    26, 29) would have WON — the only fix for an empty wallet is money
    in the account, and that is the owner's lever, not code.

## 2026-08-30 — the city bench (owner mandate: "bring wins up, losses down")

8. **Benched Oklahoma City (0W–7L) and Dallas (1W–9L) from real-money
   buys; both still scanned and logged on paper.** Why: they lose under
   the current rules too (0–4 combined in-band/morning), and together
   they account for half the account's entire net loss.

9. **Did NOT bench Denver, Washington DC, San Francisco, or Austin
   despite ugly totals; put them on a written watch list instead.**
   Why: their losses came almost entirely from the already-banned cheap
   night bets — Denver's only morning-lane bet actually won.

10. **Set the bench's review date to ~Sep 11, alongside the band trial.**
    Why: one review of all three changes on settled evidence beats three
    separate arguments.

## 2026-08-30 — first session under the standing orders

1. **Kept `CLAUDE.md` as the authoritative operating manual; the standing
   orders apply only where they don't contradict it.** Why: `CLAUDE.md`
   records explicit owner decisions backed by settled-bet evidence, and its
   rules were paid for with real losses.

2. **Did not adopt the "bets with a real edge" framing; pick-first stands.**
   Why: edge-first betting went 9–21 and was banned by the owner's Aug 6
   law — edges are logged for grading only and decide nothing.

3. **Did not create `guards.py` or a `guards.replay()` harness.** Why: their
   contract is defined only in `WEATHER_BOT_SPEC.md`, which is not in the
   repo — inventing the interface would be guesswork dressed up as the spec.

4. **Did not write `WEATHER_BOT_SPEC.md` myself.** Why: the standing orders
   call it "the blueprint" the owner provided; fabricating it would put my
   words in the owner's mouth.

5. **Left the bot LIVE; did not revert to paper.** Why: going live was an
   explicit owner decision with the scoreboard running, and the storage
   threshold the orders set (30 station-days) is exceeded 31 times over
   (930 stored).

6. **Touched no trading logic.** Why: both the standing orders and
   `CLAUDE.md` forbid it this session.

7. **Wrote `STATUS.md` as a functional inventory instead of a §1–9 spec
   comparison.** Why: with the spec file missing, an honest inventory beats
   a comparison against a document I'd have to imagine.
