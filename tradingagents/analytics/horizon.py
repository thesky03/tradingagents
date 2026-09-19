"""Multi-year outcome simulation: P(total return >= target) over N years.

A score ranks. This module answers the question a ranking cannot: what
are the odds this specific name clears a specific bar over a specific
horizon, and which part of the return is doing the work?

Total return over n years decomposes into four multiplicative pieces,
each with its own uncertainty:

    (1 + owner_yield)^n     dividends + buybacks - SBC. The LOW-VARIANCE
                            term. A company retiring 8% of its shares
                            compounds ~26% over three years whatever the
                            market thinks, provided it keeps doing it.
    (1 + growth)^n          per-share earnings growth, faded toward
                            nominal GDP because no company outgrows the
                            economy forever and the market knows it.
    multiple_ratio          mean reversion of the valuation multiple
                            toward its own median. The largest source of
                            variance and the least forecastable.
    (1 - impairment)        probability-weighted permanent capital loss.

The design point: the owner-yield term is the closest thing to a
bankable return that exists in equities, because it does not require
the market to agree with you. Everything else does. When a candidate's
P(hit target) is high, this module reports HOW MUCH of the expected
return comes from the bankable term versus from hoping for a re-rating
- which is the difference between an investment case and a wish.

Nothing here forecasts prices. It propagates stated assumptions through
arithmetic and reports a distribution. Garbage assumptions produce a
confident-looking garbage distribution, which is why every result
carries the inputs that produced it.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from .fable_score import SecuritySnapshot, fable_score


NOMINAL_GDP = 0.05          # terminal growth anchor
GROWTH_PERSISTENCE = 0.55   # weight on demonstrated growth vs the anchor
BASE_IMPAIRMENT_PA = 0.015  # annual probability of permanent capital loss


@dataclass
class HorizonResult:
    ticker: str
    years: int
    target: float
    p_hit: float                       # P(total return >= target)
    p_loss: float                      # P(total return < 0)
    median_return: float
    p10_return: float
    p90_return: float
    bankable_return: float             # owner yield alone, compounded
    bankable_share: float              # bankable / median expected
    expected_growth: float
    expected_multiple_change: float
    inputs: Dict[str, float] = field(default_factory=dict)

    @property
    def verdict(self) -> str:
        if self.p_hit >= 0.65 and self.bankable_share >= 0.40:
            return "HIGH ODDS, WELL-FOUNDED"
        if self.p_hit >= 0.65:
            return "HIGH ODDS, RERATING-DEPENDENT"
        if self.p_hit >= 0.45:
            return "COIN FLIP"
        return "UNLIKELY"


def _expected_growth(s: SecuritySnapshot) -> float:
    """Demonstrated growth regressed toward nominal GDP."""
    g = s.demonstrated_growth
    if g is None:
        g = s.revenue_cagr_3y
    if g is None:
        return NOMINAL_GDP
    return GROWTH_PERSISTENCE * g + (1 - GROWTH_PERSISTENCE) * NOMINAL_GDP


def _growth_sigma(s: SecuritySnapshot) -> float:
    """Growth uncertainty. Cyclicals get more; stable margins get less."""
    stab = s.gross_margin_stability if s.gross_margin_stability is not None else 0.7
    base = 0.07 + 0.10 * (1.0 - stab)
    if s.moat_evidence_count is not None:
        base *= (1.0 - 0.06 * s.moat_evidence_count)   # moats narrow the cone
    return max(base, 0.03)


def _multiple_drift(s: SecuritySnapshot, years: int) -> float:
    """Expected multiple ratio from mean reversion toward the own-history median.

    A name at the 20th percentile of its own valuation history has room
    to re-rate up; one at the 90th owes the market a de-rating. Only
    half the gap is assumed to close over the horizon, and never more
    than a factor of two either way.
    """
    vp = s.valuation_percentile_vs_history
    if vp is None:
        return 1.0
    gap = (50.0 - vp) / 100.0          # +0.30 if at the 20th percentile
    closed = gap * 0.5 * min(years / 3.0, 1.0)
    return max(0.5, min(2.0, 1.0 + closed))


def _impairment_pa(s: SecuritySnapshot) -> float:
    """Annual probability of permanent capital loss."""
    p = BASE_IMPAIRMENT_PA
    if s.net_debt_to_ebitda is not None and s.net_debt_to_ebitda > 2.5:
        p += 0.010 * (s.net_debt_to_ebitda - 2.5)
    if s.moat_evidence_count is not None:
        p *= (1.0 - 0.12 * s.moat_evidence_count)
    if s.margin_trend is not None and s.margin_trend < 0:
        p += 0.010
    if fable_score(s).gates_tripped:
        p += 0.040
    return max(0.002, min(p, 0.15))


def simulate_horizon(s: SecuritySnapshot, years: int = 3, target: float = 0.50,
                     trials: int = 20000, seed: int = 7) -> Optional[HorizonResult]:
    """Monte Carlo the N-year total return; report the odds of clearing target."""
    btr = s.base_total_return()
    if btr is None:
        return None
    rng = random.Random(seed)

    g_mu, g_sd = _expected_growth(s), _growth_sigma(s)
    m_mu = _multiple_drift(s, years)
    m_sd = 0.22 + 0.25 * (s.annual_volatility or 0.30)   # re-rating is the wild term
    imp = _impairment_pa(s)
    oy_sd = 0.25 * abs(btr) + 0.004                      # buyback pace can slip

    hits = losses = 0
    outcomes: List[float] = []
    for _ in range(trials):
        oy = rng.gauss(btr, oy_sd)
        g = rng.gauss(g_mu, g_sd)
        m = max(0.15, rng.gauss(m_mu, m_sd))
        total = ((1.0 + max(oy, -0.30)) ** years) * ((1.0 + max(g, -0.50)) ** years) * m
        for _y in range(years):
            if rng.random() < imp:
                total *= rng.uniform(0.25, 0.60)         # permanent haircut
                break
        r = total - 1.0
        outcomes.append(r)
        if r >= target:
            hits += 1
        if r < 0:
            losses += 1

    outcomes.sort()
    n = len(outcomes)
    bankable = (1.0 + btr) ** years - 1.0
    median = outcomes[n // 2]
    return HorizonResult(
        ticker=s.ticker, years=years, target=target,
        p_hit=round(hits / n, 3), p_loss=round(losses / n, 3),
        median_return=round(median, 3),
        p10_return=round(outcomes[n // 10], 3),
        p90_return=round(outcomes[9 * n // 10], 3),
        bankable_return=round(bankable, 3),
        bankable_share=round(bankable / median, 3) if median > 0.01 else 0.0,
        expected_growth=round(g_mu, 4),
        expected_multiple_change=round(m_mu - 1.0, 3),
        inputs={"owner_yield": round(btr, 4), "growth_sigma": round(g_sd, 3),
                "impairment_pa": round(imp, 4), "multiple_sigma": round(m_sd, 3)},
    )


def rank_by_odds(universe: Sequence[SecuritySnapshot], years: int = 3,
                 target: float = 0.50, trials: int = 8000,
                 require_ungated: bool = True) -> List[HorizonResult]:
    """Rank a universe by P(total return >= target). Gated names excluded."""
    out: List[HorizonResult] = []
    for s in universe:
        if require_ungated and fable_score(s).gates_tripped:
            continue
        r = simulate_horizon(s, years=years, target=target, trials=trials)
        if r is not None:
            out.append(r)
    out.sort(key=lambda r: (-r.p_hit, -r.bankable_share))
    return out
