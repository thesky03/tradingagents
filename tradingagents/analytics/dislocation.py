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
separate them because it is the one thing they share. The separator is
the DIVERGENCE between what the price did and what the business did:

    dislocation = price collapsed AND fundamentals intact
    value trap   = price collapsed AND fundamentals collapsed

So this screen inverts the usual sign. A large drawdown is scored as
OPPORTUNITY, not as risk - but only after the business clears an
intactness test. Without that test the screen is a knife-catching
machine; the test is doing all the work, and the drawdown term is just
sizing the prize.

WHAT IT IS NOT. Not a timing tool: dislocations stay dislocated for
quarters, and this says nothing about when the market changes its mind.
Not a substitute for SKY: a name can be a fine dislocation trade and a
poor decade-long hold. Run both and read the disagreement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from .backtest import structural_only
from .fable_score import SecuritySnapshot, fable_score
from .methods import qii


def _structural_qii(s: SecuritySnapshot) -> Optional[float]:
    """Trajectory with the tape removed.

    QII carries a momentum term and an estimate-revision term, and in
    a crash both are downstream of the price: the stock falls, the
    tape term collapses, analysts cut, and the trajectory reading
    turns negative without a single number in the business having
    moved. Feeding that into an intactness test would rebuild the
    circularity this module exists to break, so QII is computed here
    on a price-blanked snapshot - margins, cash conversion, leverage
    and capital allocation only.
    """
    return qii(structural_only(s))


MIN_DRAWDOWN = 0.25          # below this there is no dislocation to trade
SEVERE_DRAWDOWN = 0.50       # past this, assume the market may know something


@dataclass
class DislocationResult:
    ticker: str
    score: float                      # 0-100
    drawdown: float
    intactness: float                 # 0-100: is the business still working?
    survival: float                   # 0-100: can it wait for the re-rating?
    narrative_gap: float              # 0-100: cheap vs its own history, given ROIC
    upside_to_normal: float           # return if the multiple returns to its median
    is_trap: bool
    trap_reasons: List[str] = field(default_factory=list)

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


def _intactness(s: SecuritySnapshot) -> float:
    """Is the business still working while the price says it is not?

    Deliberately excludes every price-derived field. The question is
    whether revenue still grows, margins hold, cash still converts and
    returns on capital still clear the cost of capital - the things a
    narrative cannot change in a quarter.
    """
    parts: List[float] = []
    if s.revenue_cagr_3y is not None:
        parts.append(max(0.0, min(100.0, 50.0 + s.revenue_cagr_3y * 400.0)))
    if s.roic is not None and s.wacc is not None:
        parts.append(max(0.0, min(100.0, 50.0 + (s.roic - s.wacc) * 400.0)))
    if s.fcf_to_net_income is not None:
        parts.append(max(0.0, min(100.0, s.fcf_to_net_income * 75.0)))
    if s.margin_trend is not None:
        parts.append({1: 90.0, 0: 60.0, -1: 20.0}[s.margin_trend])
    if s.gross_margin_stability is not None:
        parts.append(s.gross_margin_stability * 100.0)
    q = _structural_qii(s)
    if q is not None:
        parts.append(q)
    return round(sum(parts) / len(parts), 1) if parts else 50.0


def _survival(s: SecuritySnapshot) -> float:
    """Can it fund itself long enough for the market to change its mind?

    A dislocation only pays if the company is still there when the
    re-rating arrives. Leverage is the clock.
    """
    parts: List[float] = []
    if s.net_debt_to_ebitda is not None:
        parts.append(max(0.0, min(100.0, (3.5 - s.net_debt_to_ebitda) / 3.5 * 100.0)))
    if s.interest_coverage is not None:
        parts.append(max(0.0, min(100.0, s.interest_coverage / 12.0 * 100.0)))
    if s.fcf_to_net_income is not None:
        parts.append(max(0.0, min(100.0, s.fcf_to_net_income * 80.0)))
    btr = s.base_total_return()
    if btr is not None:
        # Buying back stock into the crash is the strongest survival signal
        # there is: it is management betting against the narrative with cash.
        parts.append(max(0.0, min(100.0, 50.0 + btr * 500.0)))
    return round(sum(parts) / len(parts), 1) if parts else 50.0


def _narrative_gap(s: SecuritySnapshot) -> float:
    """Cheap versus its OWN history while the returns on capital still hold.

    The signature of a narrative dislocation: the multiple has collapsed
    toward the bottom of its historical range while ROIC has not. That
    combination says the market re-rated the story, not the economics.
    """
    if s.valuation_percentile_vs_history is None:
        return 50.0
    cheap = 100.0 - s.valuation_percentile_vs_history
    if s.roic is not None and s.wacc is not None and s.roic > s.wacc:
        quality_bonus = min(25.0, (s.roic - s.wacc) * 200.0)
        return round(min(100.0, cheap * 0.75 + quality_bonus + 12.5), 1)
    return round(cheap * 0.6, 1)


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
        # percentile -> rough multiple ratio back to the median
        mult = 1.0 + (50.0 - s.valuation_percentile_vs_history) / 100.0
        mult = max(0.6, min(2.0, mult))
    return round(((1.0 + g) ** years) * mult - 1.0, 3)


def _trap_check(s: SecuritySnapshot, intact: float) -> List[str]:
    """Reasons to believe the bear case is RIGHT.

    Every item here is a way the market's verdict turns out to be
    correct: the numbers are already confirming the story, the balance
    sheet cannot wait, or the fall is so severe that assuming the crowd
    is wrong requires more conviction than evidence supports.
    """
    reasons: List[str] = []
    if intact < 45.0:
        reasons.append("fundamentals confirm the bear case")
    q = _structural_qii(s)
    if q is not None and q < 35.0:
        reasons.append("trajectory deteriorating")
    if s.margin_trend is not None and s.margin_trend < 0 and (
            s.revenue_cagr_3y is not None and s.revenue_cagr_3y < 0.02):
        reasons.append("margins AND revenue both falling")
    if s.net_debt_to_ebitda is not None and s.net_debt_to_ebitda > 3.5:
        reasons.append("leverage limits the waiting time")
    if s.roic is not None and s.wacc is not None and s.roic < s.wacc:
        reasons.append("returns below cost of capital")
    if s.pct_off_52w_high is not None and s.pct_off_52w_high > SEVERE_DRAWDOWN:
        reasons.append(f"down >{SEVERE_DRAWDOWN:.0%} - assume the market knows something")
    if fable_score(s).gates_tripped:
        reasons.append("FABLE gate tripped")
    return reasons


def dislocation_score(s: SecuritySnapshot) -> Optional[DislocationResult]:
    """Score one name as a narrative-dislocation candidate.

    Returns None when there is no drawdown to trade - this screen has
    nothing to say about a stock near its highs.
    """
    dd = s.pct_off_52w_high
    if dd is None or dd < MIN_DRAWDOWN:
        return None

    intact = _intactness(s)
    surv = _survival(s)
    gap = _narrative_gap(s)
    traps = _trap_check(s, intact)

    # Drawdown is the PRIZE term, and it saturates: past ~45% the extra
    # fall stops being extra opportunity and starts being information.
    dd_term = min(dd / 0.45, 1.0) * 100.0

    score = (0.40 * intact + 0.22 * gap + 0.20 * surv + 0.18 * dd_term)
    if traps:
        score *= 0.45          # heavily penalised, not zeroed - traps can be right

    return DislocationResult(
        ticker=s.ticker, score=round(score, 1), drawdown=round(dd, 3),
        intactness=intact, survival=surv, narrative_gap=gap,
        upside_to_normal=_upside_to_normal(s),
        is_trap=bool(traps), trap_reasons=traps,
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
