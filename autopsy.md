# Loss autopsy — 2026-08-19 15:06 UTC

24 settled bets on the scoreboard. Where did the day's real high land, relative to what we bought?

## Every settled bet

| Date | City | Bracket bought | Price | Verdict | High located by |
|---|---|---|---|---|---|
| 2026-08-17 | Atlanta | 97° to 98° | 34¢ | WIN | settlement |
| 2026-08-17 | Boston | 73° or below | 53¢ | MISS-HIGH-BY-1 | instrument |
| 2026-08-17 | Chicago | 80° to 81° | 40¢ | MISS-LOW-BY-1 | instrument |
| 2026-08-17 | Dallas | 106° to 107° | 20¢ | WIN | settlement |
| 2026-08-17 | Denver | 89° to 90° | 36¢ | MISS-HIGH-BY-1 | instrument |
| 2026-08-17 | Las Vegas | 103° to 104° | 26¢ | MISS-FAR | instrument |
| 2026-08-17 | Los Angeles | 80° to 81° | 16¢ | MISS-FAR | instrument |
| 2026-08-17 | New Orleans | 97° to 98° | 25¢ | MISS-LOW-BY-1 | instrument |
| 2026-08-17 | Oklahoma City | 100° to 101° | 14¢ | MISS-FAR | instrument |
| 2026-08-17 | Philadelphia | 89° to 90° | 46¢ | WIN | settlement |
| 2026-08-17 | San Antonio | 101° to 102° | 36¢ | MISS-LOW-BY-1 | instrument |
| 2026-08-17 | San Francisco | 75° or above | 9¢ | MISS-FAR | instrument |
| 2026-08-17 | Washington DC | 92° to 93° | 37¢ | MISS-HIGH-BY-1 | settlement+instrument |
| 2026-08-18 | Chicago | 82° to 83° | 39¢ | MISS-LOW-BY-1 | instrument |
| 2026-08-18 | Dallas | 106° to 107° | 64¢ | MISS-HIGH-BY-1 | settlement+instrument |
| 2026-08-18 | Denver | 91° to 92° | 32¢ | MISS-FAR | instrument |
| 2026-08-18 | Houston | 98° to 99° | 22¢ | MISS-FAR | instrument |
| 2026-08-18 | Miami | 97° to 98° | 43¢ | MISS-HIGH-BY-1 | instrument |
| 2026-08-18 | Minneapolis | 83° or above | 32¢ | WIN | settlement |
| 2026-08-18 | New Orleans | 94° or below | 23¢ | MISS-HIGH-BY-1 | instrument |
| 2026-08-18 | New York City | 84° or below | 61¢ | MISS-HIGH-BY-1 | instrument |
| 2026-08-18 | Oklahoma City | 104° to 105° | 22¢ | MISS-FAR | instrument |
| 2026-08-18 | Philadelphia | 90° to 91° | 66¢ | MISS-LOW-BY-1 | instrument |
| 2026-08-18 | Washington DC | 90° to 91° | 30¢ | MISS-LOW-BY-1 | instrument |

## 1. Overall

- Wins: **4 of 24** (17%)
- Missed by exactly one bracket: **13** (54%) — 7 high, 6 low
- Missed far (2+ brackets): **7** (29%) — 2 high, 5 low

## 2. Per city

| City | Bets | Wins | 1 off, high | 1 off, low | Far | Model said | Flags |
|---|---|---|---|---|---|---|---|
| Atlanta | 1 | 1 | 0 | 0 | 0 | 71% | - |
| Boston | 1 | 0 | 1 | 0 | 0 | 48% | - |
| Chicago | 2 | 0 | 0 | 2 | 0 | 48% | every miss leans one way — station may run cold vs our model (calibration should be eating this) |
| Dallas | 2 | 1 | 1 | 0 | 0 | 45% | - |
| Denver | 2 | 0 | 1 | 0 | 1 | 73% | - |
| Houston | 1 | 0 | 0 | 0 | 1 | 39% | - |
| Las Vegas | 1 | 0 | 0 | 0 | 1 | 71% | - |
| Los Angeles | 1 | 0 | 0 | 0 | 1 | 64% | - |
| Miami | 1 | 0 | 1 | 0 | 0 | 71% | - |
| Minneapolis | 1 | 1 | 0 | 0 | 0 | 64% | - |
| New Orleans | 2 | 0 | 1 | 1 | 0 | 66% | - |
| New York City | 1 | 0 | 1 | 0 | 0 | 84% | - |
| Oklahoma City | 2 | 0 | 0 | 0 | 2 | 37% | - |
| Philadelphia | 2 | 1 | 0 | 1 | 0 | 48% | - |
| San Antonio | 1 | 0 | 0 | 1 | 0 | 36% | - |
| San Francisco | 1 | 0 | 0 | 0 | 1 | 55% | - |
| Washington DC | 2 | 0 | 1 | 1 | 0 | 45% | - |


## 3. What the market charged vs how we did

| Price band | Bets | Wins | Win rate |
|---|---|---|---|
| under 15¢ | 2 | 0 | 0% |
| 15–35¢ | 11 | 3 | 27% |
| over 35¢ | 11 | 1 | 9% |

The question this table exists to answer: when the market prices our pick cheap (under 15¢), is it right and are we wrong? If the cheap band keeps losing while the mid band holds up, that is the case for raising MIN_PICK_COST.

## 4. What this means (plain English)

- 13 of 20 losses missed by exactly ONE bracket. Plain English: on those days the forecast found the right neighborhood and knocked on the wrong door. That pattern points at small per-station bias — the calibration's job — not at a broken strategy.
- But 7 of 20 losses landed 2+ brackets away. Far misses are worse news than near misses: on those days the model wasn't even in the right neighborhood.
- Misses lean LOW overall: real days ran cooler than the brackets we bought. Watch whether calibration pulls this back as it learns.
- Under-15¢ picks: 0 win(s) in 2 bet(s). Not enough of them yet to judge the cheap-pick rule.

**The honest caveat:** with fewer than ~30 settled bets (24 so far), every pattern above is a HINT, not a conclusion. 24 coin flips can look like a trend. Per the roadmap: the scoreboard promotes, conviction never does — no rule changes, no benchings, no sizing moves on this sample.

*Sources: `settlement` = Kalshi's own result pinned the high; `instrument` = the poller's floored METAR running max; `settlement+instrument` = the instrument read inside our bracket but Kalshi settled NO, and since the instrument can only understate, the official high must have escaped out the top. Note the instrument understates by design, so a rare loss scored `low` could in truth have overshot instead.*
