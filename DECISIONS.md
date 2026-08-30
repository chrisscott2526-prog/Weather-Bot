# DECISIONS.md — builder decisions the owner can overrule

One line of why per decision, newest first, as the standing orders require.

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
