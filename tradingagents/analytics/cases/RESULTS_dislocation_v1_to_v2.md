# Dislocation screen: what the backtest said, and what it changed

**Run 17 Sep 2026** against the 25 labelled 2025–26 crashes in
`dislocation_2025_2026.py` (14 recovered, 11 kept falling).

Read the contamination warnings at the top of that file first. The short
version: the case inputs were encoded by someone who already knew the
outcomes, the prices come from search summaries rather than a data feed
because every finance domain is blocked in this environment, and the
sample is one regime. Everything below is the most optimistic reading of
the screen's performance.

## v1 failed on the case it was built for

| metric | v1 |
|---|---|
| AUC (recovery vs trap) | **0.591** |
| gap between the groups | 0.55 σ |
| IC vs realised return | +0.277 ± 0.20 |
| Accenture's verdict | **TRAP** |

v1's severity rule — "down more than 50%, assume the market knows
something" — classified ACN, ServiceNow, UnitedHealth, Constellation,
Atlassian and CVS as traps. Five of those are among the six largest
recoveries in the set. An AUC of 0.59 with n=14/11 is not
distinguishable from a coin flip.

## The per-input diagnostic: three of the four pillars were backwards

Each input scored as a single-input classifier. 0.50 is a coin flip;
below 0.50 means the field predicted the opposite of what v1 assumed.

| input | AUC | v1 treated it as |
|---|---|---|
| growth deceleration (forward − trailing) | **0.792** | not used at all |
| demonstrated forward growth | 0.760 | minor |
| QII (price-blanked) | 0.740 | one input among six |
| margin trend | 0.740 | one input among six |
| valuation percentile vs own history | 0.721 *(less cheap → recovered)* | **cheapness rewarded** |
| cash conversion FCF/NI | 0.692 | one input among six |
| net debt / EBITDA | 0.604 | survival pillar |
| revenue CAGR (trailing) | 0.500 | intactness |
| moat evidence count | 0.500 | — |
| ROIC − WACC | 0.455 | intactness + a veto |
| owner yield | 0.448 | survival |
| gross margin stability | 0.435 | intactness |
| interest coverage | 0.383 | survival |
| **buyback yield** | **0.373** | **"the strongest survival signal there is"** |
| **drawdown depth** | **0.334** | **the prize term, 18% of the score** |

Two of these deserve naming. **Depth predicted traps.** And **buying back
stock into the fall** — the behaviour v1 singled out as management
betting against the narrative with cash — was done hardest by Fiserv (9%
buyback yield), Gartner (6%) and Lululemon (5.5%) on their way down.

The cheapness result matches Sparkline Capital's May 2026 finding
independently: among software names down 30%+, all of them were cheap —
GoDaddy, Adobe, Workday, Atlassian and Salesforce all under 13.5×
forward earnings — and cheapness carried no information, with "an
abnormally long left tail of value traps."

## What actually separated them

Not the level of quality and not the price. The **first derivative of
the numbers**, all of it reported before the troughs it is being asked
to identify:

- CoStar grew revenue 18% while falling 51%. Net new bookings: −26%.
- The Trade Desk went from 19% growth to 3% in four quarters.
- Gartner's operating margin halved (16.6% → 5.7%) and FCF margin halved with it.
- Nike's revenue returned to FY2022 levels with net income −49% and FCF −51%.

Against Accenture, which missed revenue by 0.3% and kept its margins and
cash conversion — as did Salesforce, and as did ServiceNow, which beat
every metric in the quarter that took it down 17%.

## v2

Drawdown demoted to eligibility (≥25%, then depth adds nothing).
Cheapness and survival computed and reported but removed from scoring.
Score = trajectory 80% + level-of-quality anchor 20%. The severity and
below-cost-of-capital vetoes downgraded to cautions.

| metric | v1 | v2 |
|---|---|---|
| AUC, all 25 | 0.591 | **0.786** |
| AUC excluding INTC¹ | 0.636 | **0.818** |
| separation | 0.55 σ | **1.20 σ** |
| IC vs realised return | +0.277 ± 0.20 | **+0.572 ± 0.20** |
| precision / recall at the fitted threshold | 0.56 / 1.00 | **0.79 / 0.79** |
| leave-one-out accuracy | — | **72%** vs a 56% base rate |
| Accenture | TRAP | **DISLOCATION (66.2)** |

¹ Intel fails the quality screen at its trough by design — a distressed
turnaround, not a quality company temporarily mispriced. It rose 278%
anyway. It is kept in the primary number rather than quietly dropped.

Trajectory weight 1.00 scores AUC 0.815. 0.80 was chosen instead, at a
cost of 0.023, because a screen with no level anchor would buy anything
that is merely decelerating less than it used to.

## Where v2 is still wrong, and why it is wrong there

**False negatives — the managed-care cohort.** UNH (23.3), ELV (21.5),
HUM (15.1), CVS (15.8) all scored as traps and all recovered. At their
troughs their numbers genuinely were deteriorating: medical-loss ratios
were blowing out and Humana had just cut FY26 EPS guidance ~47%. They
re-rated on the 7 April 2026 CMS rate decision, which came in far above
the January proposal. That is not a business inflection the screen could
have read — it is a regulator deferring a risk. UnitedHealth's DOJ
criminal probe is still open. The screen gets these wrong for a reason
it should get them wrong.

**False positive — Cognizant, the twin.** CTSH scored 60.0 (DISLOCATION)
against ACN's 66.2. Same sector, same AI-deflation narrative, same
catalyst day, opposite outcome. On everything knowable at the trough
they are near-identical: CTSH beat adjusted EPS five quarters running.
What separated them — Accenture's $5.1B of GenAI bookings, 85,000 AI
professionals against an 80,000 target, and a buyback raised to $7.5B —
was disclosed *after* the bottom. The screen ranks ACN above CTSH but
buys both. **This is the honest limit of a trajectory screen: it cannot
see a disclosure that has not happened yet.**

**The timing consequence.** Every Tier-A recovery bottomed *before* its
counter-evidence was published and re-rated *when* it was. ServiceNow is
the controlled experiment: an equally good beat produced −17% in April
and +6% in July, and the only variable that changed was the existence of
a hard AI-monetisation number ($1B ACV). So requiring that disclosure
before entry — the safest rule available — means systematically missing
the bottom. That is a real trade-off between entry price and false
positives, and it is not resolved here.

## What would falsify v2

The next 25 crashes, scored before the outcomes are known. Until then
the AUC above is a description of a sample the weights were fitted to,
and nothing more.
