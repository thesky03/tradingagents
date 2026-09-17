"""Dislocation screen: quality crushed by a narrative, not by its numbers.

WHY THIS EXISTS. FABLE-5's Behavior pillar scores momentum, and SKY
inherits it. That makes both structurally incapable of buying a crash:
a price collapse drives the Behavior pillar toward zero, which drags the
composite below the ownership threshold, which makes the entry
discipline return AVOID. The reasoning is circular - the stock is
rejected *because* it fell.

Measured on Accenture in 2026, down ~30% on "AI eats IT consulting":
Behavior 1.8/20, FABLE 42.8, SKY 51.2, entry AVOID. The horizon
simulator, which ignores momentum entirely, put P(+50% over 3y) at
62.7% on the same inputs. The tools disagreed and the odds model was
right. This module is the systematic version of that disagreement.

THE CENTRAL PROBLEM. On the tape, a dislocation and a value trap look
identical - both are quality-shaped things down 40%. Momentum cannot
separate them because it is the one thing they share.

WHAT VERSION 1 GOT WRONG, AND HOW WE KNOW. v1 assumed the separator was
"price collapsed but the business is intact", and scored a blend of
drawdown depth (as the prize), cheapness against the name's own history,
balance-sheet survival, and a level-of-quality intactness reading. Run
against 25 labelled 2025-26 crashes (``analytics.cases``), it scored
AUC 0.591 - a coin flip - and its severity veto classified Accenture,
ServiceNow, UnitedHealth, Constellation and Atlassian as traps. It
failed on the case it was built for.

The per-input diagnostic said why. Measured as single-input classifiers
on those cases:

    growth deceleration (fwd vs trailing)   AUC 0.79   <- the signal
    demonstrated forward growth             AUC 0.76
    margin trend                            AUC 0.74
    cash conversion (FCF/NI)                AUC 0.69
    ---------------------------------------------------
    return on capital, moat count, margin
      stability (the LEVEL of quality)      AUC 0.44-0.50  (nothing)
    interest coverage                       AUC 0.38   (inverted)
    buyback yield                           AUC 0.37   (inverted)
    DRAWDOWN DEPTH                          AUC 0.33   (inverted)

So: depth of decline predicted traps, not recoveries. Cheapness against
a name's own history predicted traps too - which independently matches
Sparkline Capital's May 2026 finding that among software names down
30%+, every one of them was cheap and cheapness carried no information,
with "an abnormally long left tail of value traps". Buying back stock
into the fall, which v1 treated as the strongest survival signal there
is, was done just as hard by Fiserv (9% buyback yield), Gartner (6%)
and Lululemon (5.5%) on their way down.

WHAT SEPARATES THEM, THEN. Not the level of quality and not the price -
the FIRST DERIVATIVE of the numbers. Recoveries were still compounding
at the trough; traps were decelerating, and had been for a while:

    CoStar grew revenue 18% while falling 51%; its net new bookings were
    down 26%. The Trade Desk went from 19% growth to 3% in four
    quarters. Gartner's operating margin halved, 16.6% -> 5.7%, and its
    FCF margin halved with it. Nike's revenue returned to FY2022 levels
    with net income down 49% and free cash flow down 51%.

    Accenture, at the same moment, missed revenue by 0.3% and kept its
    margins and its cash conversion. So did Salesforce and ServiceNow -
    ServiceNow beat every metric in the quarter that took it down 17%.

Reported revenue growth is no defence. Direction is.

HOW THE SCORE IS BUILT NOW. Drawdown is an ELIGIBILITY test, not a
scoring term - a name must be down 25% to be in the conversation, and
past that, depth adds nothing. Score is trajectory (80%) plus a small
anchor on the level of quality (20%), so that a wrecked business cannot
score on one good quarter. Cheapness and survival are computed and
REPORTED, because they size the prize and the waiting time, but they do
not move the score.

HONEST STATUS OF THE NUMBERS. The rebuild scores AUC 0.79 on the same
25 cases, 72% leave-one-out accuracy against a 56% base rate. That is
IN-SAMPLE: the weights were chosen after seeing which inputs separated
those labels, and the case inputs were themselves encoded by someone
who knew the outcomes. The honest reading is "this is the most
optimistic version of its performance". A trajectory weight of 1.00
scores AUC 0.815; 0.80 was chosen instead, at a cost of 0.023, because
a screen with no level anchor at all would happily buy junk that is
merely decelerating less than it was.

WHAT IT IS NOT. Not a timing tool: dislocations stay dislocated for
quarters. Not a substitute for SKY: a name can be a fine dislocation
trade and a poor decade-long hold. Run both and read the disagreement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from .backtest import structural_only
from .fable_score import SecuritySnapshot, fable_score
from .methods import qii


MIN_DRAWDOWN = 0.25          # eligibility only: below this there is nothing to trade
SEVERE_DRAWDOWN = 0.50       # reported as a caution, no longer a veto (see below)
TRAJECTORY_WEIGHT = 0.80     # vs the level-of-quality anchor
TRAP_PENALTY = 0.45          # traps are penalised, not zeroed - they can be right


def _structural_qii(s: SecuritySnapshot) -> Optional[float]:
    """Trajectory with the tape removed.

    QII carries a momentum term and an estimate-revision term, and in
    a crash both are downstream of the price: the stock falls, the
    tape term collapses, analysts cut, and the trajectory reading turns
    negative without a single number in the business having moved.
    Feeding that into this screen would rebuild the circularity the
    module exists to break, so QII is computed on a price-blanked
    snapshot - margins, cash conversion, leverage and capital
    allocation only.
    """
    return qii(structural_only(s))


def growth_deceleration(s: SecuritySnapshot) -> Optional[float]:
    """Forward growth minus trailing growth: the single best separator.

    Positive means the business is accelerating into the crash, which
    is the shape of a narrative dislocation. Negative means the market
    is extrapolating a slowdown that is already in the reported
    numbers, which is the shape of a trap - CoStar's bookings down 26%
    against 18% reported revenue growth, or The Trade Desk going from
    19% to 3% over four quarters.
    """
    if s.demonstrated_growth is None or s.revenue_cagr_3y is None:
        return None
    return s.demonstrated_growth - s.revenue_cagr_3y


@dataclass
class DislocationResult:
    ticker: str
    score: float                      # 0-100
    drawdown: float                   # eligibility, not a scoring input
    trajectory: float                 # 0-100: are the numbers still improving?
    intactness: float                 # 0-100: level of quality (minor weight)
    narrative_gap: float              # REPORTED, UNSCORED: cheap vs own history
    survival: float                   # REPORTED, UNSCORED except as a veto
    upside_to_normal: float           # return if the multiple returns to its median
    is_trap: bool
    trap_reasons: List[str] = field(default_factory=list)
    cautions: List[str] = field(default_factory=list)

    @property
    def verdict(self) -> str:
        if self.is_trap:
            return f"TRAP ({', '.join(self.trap_reasons)})"
        if self.score >= 70:
            return "PRIME DISLOCATION"
        if self.score >= 55:
            return "DISLOCATION"
        if self.score >= 40:
            return "WATCH"
        return "NO EDGE"


def _trajectory(s: SecuritySnapshot) -> float:
    """The first derivative of the numbers, price excluded entirely.

    Weights within this pillar follow the measured single-input
    separation on the 2025-26 case set, in that order: deceleration,
    margin direction, the absolute forward growth rate, cash
    conversion. All four are things a narrative cannot change in a
    quarter, and all four were reported BEFORE the troughs they are
    being asked to identify.
    """
    parts: List[float] = []
    weights: List[float] = []

    d = growth_deceleration(s)
    if d is not None:
        parts.append(max(0.0, min(100.0, 50.0 + d * 500.0)))
        weights.append(0.35)
    if s.margin_trend is not None:
        parts.append({1: 90.0, 0: 60.0, -1: 15.0}[s.margin_trend])
        weights.append(0.25)
    if s.demonstrated_growth is not None:
        parts.append(max(0.0, min(100.0, 40.0 + s.demonstrated_growth * 300.0)))
        weights.append(0.20)
    if s.fcf_to_net_income is not None:
        parts.append(max(0.0, min(100.0, s.fcf_to_net_income * 70.0)))
        weights.append(0.20)

    if not parts:
        return 50.0
    return round(sum(p * w for p, w in zip(parts, weights)) / sum(weights), 1)


def _intactness(s: SecuritySnapshot) -> float:
    """The LEVEL of quality: is this a good business at all?

    On the 2025-26 cases the level fields carried essentially no
    information about which crashes recovered - return on capital,
    moat count and margin stability all scored AUC 0.44-0.50. That is
    not surprising: quality is what gets a stock into this screen in
    the first place, so it barely varies across the candidates. It is
    kept at a fifth of the weight as an anchor against buying
    something merely decelerating less than it used to.

    Excludes every price-derived field by construction.
    """
    parts: List[float] = []
    if s.roic is not None and s.wacc is not None:
        parts.append(max(0.0, min(100.0, 50.0 + (s.roic - s.wacc) * 400.0)))
    if s.gross_margin_stability is not None:
        parts.append(s.gross_margin_stability * 100.0)
    if s.moat_evidence_count is not None:
        parts.append(min(100.0, 25.0 * s.moat_evidence_count))
    if s.fcf_to_net_income is not None:
        parts.append(max(0.0, min(100.0, s.fcf_to_net_income * 75.0)))
    q = _structural_qii(s)
    if q is not None:
        parts.append(q)
    return round(sum(parts) / len(parts), 1) if parts else 50.0


def _survival(s: SecuritySnapshot) -> float:
    """Can it fund itself long enough for the market to change its mind?

    REPORTED, NOT SCORED. A strong balance sheet lets you wait; it does
    not make you right. On the case set, interest coverage separated
    the labels at AUC 0.38 and buyback yield at 0.37 - both inverted.
    Management buying stock into the fall, which v1 treated as the
    strongest survival signal there is, was done hardest by Fiserv,
    Gartner and Lululemon on their way down. Only leverage retains a
    role, as a veto, because leverage is the clock.
    """
    parts: List[float] = []
    if s.net_debt_to_ebitda is not None:
        parts.append(max(0.0, min(100.0, (3.5 - s.net_debt_to_ebitda) / 3.5 * 100.0)))
    if s.interest_coverage is not None:
        parts.append(max(0.0, min(100.0, s.interest_coverage / 12.0 * 100.0)))
    if s.fcf_to_net_income is not None:
        parts.append(max(0.0, min(100.0, s.fcf_to_net_income * 80.0)))
    return round(sum(parts) / len(parts), 1) if parts else 50.0


def _narrative_gap(s: SecuritySnapshot) -> float:
    """Cheap versus its own history. REPORTED, NOT SCORED.

    v1 scored this as the signature of a dislocation. The case set says
    the opposite: valuation percentile separated the labels at AUC
    0.72 in the direction that the LESS cheap names recovered, which
    independently matches Sparkline's finding that every crashed
    software name was cheap and that cheapness carried no information.
    It is retained because it sizes the prize - how far a re-rating
    could carry - not because it identifies one.
    """
    if s.valuation_percentile_vs_history is None:
        return 50.0
    return round(100.0 - s.valuation_percentile_vs_history, 1)


def _upside_to_normal(s: SecuritySnapshot, years: int = 3) -> float:
    """Return if the multiple simply returns to this name's own median.

    No heroic assumptions: no new products, no margin miracle. Just the
    multiple normalising plus whatever growth the business delivers.
    """
    g = s.demonstrated_growth if s.demonstrated_growth is not None else (
        s.revenue_cagr_3y if s.revenue_cagr_3y is not None else 0.03)
    g = max(min(g, 0.25), -0.05)
    mult = 1.0
    if s.valuation_percentile_vs_history is not None:
        mult = 1.0 + (50.0 - s.valuation_percentile_vs_history) / 100.0
        mult = max(0.6, min(2.0, mult))
    return round(((1.0 + g) ** years) * mult - 1.0, 3)


def _trap_check(s: SecuritySnapshot, trajectory: float) -> List[str]:
    """Reasons to believe the bear case is RIGHT.

    Every item is a way the market's verdict turns out to be correct:
    the numbers already confirm the story, or the balance sheet cannot
    wait for the argument to be settled.

    Two of v1's vetoes were removed here because the case set
    disconfirmed them. "Returns below cost of capital" vetoed
    Atlassian, CVS and Humana - in a crash, ROIC is often at a
    cyclical trough, so demanding it clear WACC at the bottom rejects
    exactly the names whose returns are about to recover. And "down
    more than 50%, assume the market knows something" vetoed
    Accenture, ServiceNow, UnitedHealth, Constellation and Atlassian -
    five of the six largest recoveries in the set, including the case
    this module was built for. Severity is now a caution, not a veto.
    """
    reasons: List[str] = []
    if trajectory < 35.0:
        reasons.append("the numbers already confirm the bear case")
    if (s.margin_trend is not None and s.margin_trend < 0
            and (growth_deceleration(s) or 0.0) < 0.0):
        reasons.append("margins falling while growth decelerates")
    if s.demonstrated_growth is not None and s.demonstrated_growth < 0.0:
        reasons.append("forward growth is negative")
    if s.net_debt_to_ebitda is not None and s.net_debt_to_ebitda > 3.5:
        reasons.append("leverage limits the waiting time")
    if fable_score(s).gates_tripped:
        reasons.append("FABLE gate tripped")
    return reasons


def _cautions(s: SecuritySnapshot, dd: float) -> List[str]:
    """Things worth knowing that are not disqualifying on this evidence."""
    out: List[str] = []
    if dd > SEVERE_DRAWDOWN:
        out.append(f"down >{SEVERE_DRAWDOWN:.0%} - a majority of the traps in the "
                   f"case set were, but so were five of the six best recoveries")
    if s.roic is not None and s.wacc is not None and s.roic < s.wacc:
        out.append("returns below cost of capital at the trough")
    if s.valuation_percentile_vs_history is not None and \
            s.valuation_percentile_vs_history < 5.0:
        out.append("cheapest in its own history - on the case set that was "
                   "mildly ANTI-predictive, not supportive")
    return out


def dislocation_score(s: SecuritySnapshot) -> Optional[DislocationResult]:
    """Score one name as a narrative-dislocation candidate.

    Returns None when there is no drawdown to trade - this screen has
    nothing to say about a stock near its highs.
    """
    dd = s.pct_off_52w_high
    if dd is None or dd < MIN_DRAWDOWN:
        return None

    traj = _trajectory(s)
    intact = _intactness(s)
    traps = _trap_check(s, traj)

    score = TRAJECTORY_WEIGHT * traj + (1.0 - TRAJECTORY_WEIGHT) * intact
    if traps:
        score *= TRAP_PENALTY

    return DislocationResult(
        ticker=s.ticker, score=round(score, 1), drawdown=round(dd, 3),
        trajectory=traj, intactness=intact,
        narrative_gap=_narrative_gap(s), survival=_survival(s),
        upside_to_normal=_upside_to_normal(s),
        is_trap=bool(traps), trap_reasons=traps, cautions=_cautions(s, dd),
    )


def screen_dislocations(universe: Sequence[SecuritySnapshot],
                        include_traps: bool = False) -> List[DislocationResult]:
    """Rank a universe by dislocation score; drops non-drawdown names."""
    out: List[DislocationResult] = []
    for s in universe:
        r = dislocation_score(s)
        if r is None:
            continue
        if r.is_trap and not include_traps:
            continue
        out.append(r)
    out.sort(key=lambda r: -r.score)
    return out


# ---------------------------------------------------------------------------
# Resolving the disagreement: what the book should actually do
# ---------------------------------------------------------------------------

# A dislocation entry is a contrarian one: the tape, the revisions and the
# composite all disagree with it. So it is sized at roughly half of what
# the same conviction would earn in a name where everything agrees, and it
# is entered in thirds rather than at once - because a stock down 35% has
# already proved it can fall 35%, and nothing in this module claims to know
# where the bottom is.
DISLOCATION_CAPS = {"PRIME DISLOCATION": 0.08, "DISLOCATION": 0.05}
ENTRY_TRANCHES = 3


@dataclass
class DislocationStance:
    ticker: str
    action: str                       # BUY_DISLOCATION / WATCH / STAND_ASIDE
    max_weight: float                 # fraction of the sleeve, all tranches in
    tranche_weight: float
    dislocation: DislocationResult
    fable_total: float
    fable_signal: str                 # what the momentum-aware system said
    disagreement: bool                # the two lenses point opposite ways
    exit_rule: str
    reasons: List[str] = field(default_factory=list)


def dislocation_stance(s: SecuritySnapshot) -> Optional[DislocationStance]:
    """Reconcile the drawdown screen with the momentum-aware verdict.

    Both lenses are kept, because each is right about something. FABLE
    is right that a falling stock has worse near-term odds; this screen
    is right that the fall is where the asymmetry lives. The rule is
    therefore not "override FABLE" but "act on the disagreement, at
    contrarian size, in tranches, with the falsifier written down".

    Returns None when the name is not in a drawdown at all - there is
    nothing here to reconcile.
    """
    d = dislocation_score(s)
    if d is None:
        return None

    from .fable_score import entry_signal          # local: avoids a cycle
    f = fable_score(s)
    sig, _ = entry_signal(s)
    verdict = d.verdict
    reasons: List[str] = []

    if f.gates_tripped:
        action, cap = "STAND_ASIDE", 0.0
        reasons.append(f"absolute gate: {', '.join(f.gates_tripped)}")
    elif d.is_trap:
        action, cap = "STAND_ASIDE", 0.0
        reasons.extend(d.trap_reasons)
    elif verdict in DISLOCATION_CAPS:
        action, cap = "BUY_DISLOCATION", DISLOCATION_CAPS[verdict]
        reasons.append(f"down {d.drawdown:.0%} with trajectory {d.trajectory:.0f} "
                       f"- the numbers are still improving")
        reasons.append(f"{d.upside_to_normal:+.0%} if the multiple only returns "
                       f"to its own median")
    elif verdict == "WATCH":
        action, cap = "WATCH", 0.0
        reasons.append("cheap and falling, but the trajectory is not clear enough")
    else:
        action, cap = "STAND_ASIDE", 0.0
        reasons.append("no edge: the drawdown is not backed by an improving trajectory")

    reasons.extend(d.cautions)
    disagree = action == "BUY_DISLOCATION" and sig in ("AVOID", "WAIT")
    if disagree:
        reasons.append(f"momentum-aware system says {sig} at FABLE {f.total:.1f} "
                       f"(Behavior {f.behavior:.1f}/20) - this is the disagreement "
                       f"being traded")

    return DislocationStance(
        ticker=s.ticker, action=action, max_weight=cap,
        tranche_weight=round(cap / ENTRY_TRANCHES, 4),
        dislocation=d, fable_total=f.total, fable_signal=sig,
        disagreement=disagree,
        # The falsifier, written before the position exists. A dislocation
        # trade ends when the gap it was buying closes - or when the
        # trajectory that justified it turns over.
        exit_rule=("exit on re-rating to the ~50th valuation percentile of its "
                   "own history, or immediately if the trajectory breaks: "
                   "forward growth falling below trailing growth for two "
                   "consecutive quarters, margins contracting while growth "
                   "decelerates, or any FABLE gate tripping"),
        reasons=reasons,
    )
