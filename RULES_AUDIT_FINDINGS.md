# Rules-panel settlement-source audit — Aug 23, 2026

**Question:** the operator found a note in one market's rules saying it
settles on data from The Weather Company (TWC). Is that one market, or
all of them? CLAUDE.md and cities.py say settlement is the NWS CLI
Daily Climate Report.

**Method:** `rules_audit.py` (this branch) pulled the live rules text
(`rules_primary` + `rules_secondary`) for one open Aug-24 market per
series, unauthenticated, via GitHub Actions run
[32671425569](https://github.com/chrisscott2526-prog/Weather-Bot/actions/runs/32671425569)
(full verbatim text of all 20 panels is in that run's log). Read-only:
no orders, no CSV changes.

## Answer: it is universal. 20 of 20 name TWC; 0 of 20 name the NWS.

Every `rules_primary` reads (city/date/threshold varying):

> "If the maximum temperature recorded at {City} (CLI{XXX}) for
> {date}, is greater than {N}° fahrenheit **according to The Weather
> Company**, then the market resolves to Yes."

Every `rules_secondary` is the same boilerplate:

> "…the official and final value used to determine this market is the
> maximum/minimum temperature **as reported by the Weather Company**.
> … Preliminary Weather Company data may be subject to rounding and
> conversion differences from the final reported value."

The words "National Weather Service", "NWS", "Daily Climate Report"
appear **nowhere** in any of the 20 panels.

## The CLI station codes are still there, and all 20 match ours

| series | city | our station | CLI code in rules | match |
|---|---|---|---|---|
| KXHIGHNY | New York City | KNYC | CLINYC | yes |
| KXHIGHMIA | Miami | KMIA | CLIMIA | yes |
| KXHIGHDEN | Denver | KDEN | CLIDEN | yes |
| KXHIGHLAX | Los Angeles | KLAX | CLILAX | yes |
| KXHIGHPHIL | Philadelphia | KPHL | CLIPHL | yes |
| KXHIGHAUS | Austin | KAUS | CLIAUS | yes |
| KXHIGHCHI | Chicago | KMDW | CLIMDW | yes (Midway) |
| KXHIGHTSFO | San Francisco | KSFO | CLISFO | yes |
| KXHIGHTPHX | Phoenix | KPHX | CLIPHX | yes |
| KXHIGHTDC | Washington DC | KDCA | CLIDCA | yes |
| KXHIGHTATL | Atlanta | KATL | CLIATL | yes |
| KXHIGHTDAL | Dallas | KDFW | CLIDFW | yes (DFW) |
| KXHIGHTSEA | Seattle | KSEA | CLISEA | yes |
| KXHIGHTLV | Las Vegas | KLAS | CLILAS | yes |
| KXHIGHTOKC | Oklahoma City | KOKC | CLIOKC | yes |
| KXHIGHTBOS | Boston | KBOS | CLIBOS | yes |
| KXHIGHTMIN | Minneapolis | KMSP | CLIMSP | yes |
| KXHIGHTSATX | San Antonio | KSAT | CLISAT | yes (not KSSF) |
| KXHIGHTNOLA | New Orleans | KMSY | CLIMSY | yes |
| KXHIGHTHOU | Houston | KHOU | CLIHOU | yes (Hobby) |

So the *stations* we verified Aug 3 are still exactly the stations the
rules point at — the CLI-code trick still works. What changed (or what
we mis-read all along) is *whose report of that station's max* is
official: Kalshi names TWC, not the NWS CLI product.

## What this means for the bot (assessment, nothing changed yet)

- **The money path is already protected.** `settle.py` grades only by
  Kalshi's own `result` field, and calibration is settlement-pinned.
  Whoever Kalshi reads, the scoreboard records what actually paid.
- **The thermometer caveat gets one word stronger.** Our METAR highs
  from `temps_log.csv` were already documented as "not what settles"
  (CLI catches between-hour peaks). Now the official number is TWC's
  station max — normally the same station-day observation, but with
  TWC's own "rounding and conversion" caveat in the rules. The board
  must keep understating and must never claim to show settlement.
- **Docs are stale.** CLAUDE.md and the cities.py docstring say the
  NWS CLI report settles the market. The station mapping is right; the
  named source is not. Fix the wording in a future commit — no code
  behavior needs to change for this finding alone.
- Aug-24 markets were still `active` at audit time (22:42 UTC); the
  boilerplate is series-level, so one market per series is
  representative.

Note: the audit ran through a temporary manual-only workflow at
`.github/workflows/probe.yml` (GitHub will only dispatch workflow
paths it already knows, and the retired sports-probe path was the one
registered). That workflow was deleted when this branch merged.
`rules_audit.py` stays in the repo and can be wired to a fresh
workflow any time the rules text needs re-auditing.
