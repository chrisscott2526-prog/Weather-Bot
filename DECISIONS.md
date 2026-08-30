# DECISIONS.md — builder decisions the owner can overrule

One line of why per decision, newest first, as the standing orders require.

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
