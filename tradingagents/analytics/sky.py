"""SKY: the composite long-term buy-and-hold score (0-100).

SKY unifies everything this system knows about a security into one
number whose meaning is deliberately narrow: HOW GOOD A LONG-TERM BUY
AND HOLD IS THIS, TODAY. It is not an entry timer (the entry discipline
and lifecycle handle that) and momentum is intentionally near-absent -
a decade-long holding should not be chosen by last quarter's tape.

Three families of lenses feed it:

SESSION METHODOLOGIES        BANKING TOOLKIT (adapted)     FACTOR PANEL
  FABLE-5 (level + gates)      DCF lens (intrinsic gap)      Quality (AQR-style)
  QII (trajectory)             LBO lens (sponsor floor)      Expected return (TSR)
  AOQ (payoff shape)           Comps lens (relative value)
                               Precedents lens (scarcity)
                               Firepower lens (EY-adapted)

Banking-lens calibration (researched Aug 2026):
- LBO: sponsors underwrite 20-25% gross IRR at 5.0-5.5x leverage with
  45-50% equity, and value creation is expected from EBITDA growth, not
  multiple expansion. The lens asks: does a financial-buyer floor exist
  under this stock? (ctacquisitions.com 2026 LBO guides; macabacus.com)
- Firepower: EY defines it as capacity to fund transactions from the
  balance sheet - cash, debt capacity, market cap - with the combined
  entity capped near 30% debt-to-equity. Adapted here to the company's
  OWN capacity to deploy capital opportunistically. (ey.com Firepower)

Composition rules:
- The FABLE gates remain absolute: a gated name's SKY is 0.
- Weights sum to 1 and favor durability over everything; a lens whose
  inputs are missing is dropped and the remaining weights renormalize,
  so sparse data lowers confidence (reported as coverage) rather than
  silently biasing the score.

Verdicts: >=80 GENERATIONAL - the own-it-for-a-decade shelf;
70-79 CORE - portfolio backbone; 60-69 ACCUMULATE - build on weakness;
50-59 WATCH; <50 PASS; gated VETO.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from .fable_score import SecuritySnapshot, fable_score
from . import methods


# 2026 sponsor-market calibration (see module docstring for sources).
LBO_LEVERAGE_TURNS = 5.25      # midpoint of 5.0-5.5x available leverage
LBO_FCF_YIELD_PAR = 0.08       # unlevered FCF/EV yield that clears ~20% IRR
FIREPOWER_ND_CAP = 3.0         # EY's ~30% D/E spirit mapped to ND/EBITDA turns

WEIGHTS = {
    "fable": 0.22,      # level of the business + margin of safety + gates
    "exp_ret": 0.15,    # TSR decomposition: what the hold actually earns
    "quality": 0.12,    # AQR-style durability
    "dcf": 0.12,        # intrinsic-value gap
    "firepower": 0.10,  # capacity to keep compounding through cycles
    "lbo": 0.08,        # financial-buyer floor under the equity
    "comps": 0.06,      # relative value, cross-sectional and historical
    "qii": 0.06,        # trajectory (small: decade holds outlive quarters)
    "precedents": 0.05, # scarcity / strategic value
    "aoq": 0.04,        # payoff shape (mostly an entry concern)
}


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


# ---------------------------------------------------------------------------
# Banking lenses (each 0-100 or None when inputs are missing)
# ---------------------------------------------------------------------------


def dcf_lens(s: SecuritySnapshot) -> Optional[float]:
    """Intrinsic-value gap via a compact Gordon frame.

    Fair earnings yield ~ WACC - sustainable growth (terminal growth
    capped at 5% - no company outgrows nominal GDP forever). The lens
    scores the ratio of the actual earnings yield to that fair yield:
    paying a 9% yield when 5% would be fair is a wide intrinsic gap.
    An expectations kicker (Mauboussin): implied growth already below
    75% of demonstrated growth adds a notch.
    """
    if s.earnings_yield is None or s.wacc is None:
        return None
    g_sustain = min(s.revenue_cagr_3y if s.revenue_cagr_3y is not None else 0.03, 0.05)
    fair_ey = max(s.wacc - g_sustain, 0.02)
    gap = s.earnings_yield / fair_ey
    score = 50.0 + (gap - 1.0) * 50.0
    if (s.implied_growth is not None and s.demonstrated_growth is not None
            and s.implied_growth <= 0.75 * s.demonstrated_growth):
        score += 10.0
    return round(_clamp(score), 1)


def lbo_lens(s: SecuritySnapshot) -> Optional[float]:
    """The paper-LBO test: does a financial-buyer floor exist?

    A sponsor underwriting ~20% IRR at 2026 terms needs durable free
    cash flow bought at a yield near LBO_FCF_YIELD_PAR, unused debt
    capacity against ~5.25x available turns, and margins stable enough
    to survive the leverage. Businesses that pass trade with a floor:
    if the market ever offers them cheap enough, someone takes them
    out. Not meaningful for financials and regulated utilities.
    """
    if s.is_financial or s.is_regulated_utility:
        return None
    if s.earnings_yield is None or s.fcf_to_net_income is None:
        return None
    fcf_yield = s.earnings_yield * s.fcf_to_net_income
    score = 50.0 * min(fcf_yield / LBO_FCF_YIELD_PAR, 1.6)
    if s.net_debt_to_ebitda is not None:
        headroom = max(LBO_LEVERAGE_TURNS - max(s.net_debt_to_ebitda, 0.0), 0.0)
        score += 25.0 * min(headroom / LBO_LEVERAGE_TURNS, 1.0)
    if s.gross_margin_stability is not None:
        score += 25.0 * s.gross_margin_stability
    return round(_clamp(score), 1)


def comps_lens(universe: Sequence[SecuritySnapshot]) -> Dict[str, float]:
    """Trading comparables: cheap versus peers and versus own history.

    Cross-sectional earnings-yield rank (the universe IS the comp set),
    inverted own-history valuation percentile, and EV/EBIT vs sector
    median where sourced. Equal-weighted across whatever is available.
    """
    ey_rank = methods._percentile_ranks(
        methods._collect(universe, lambda s: s.earnings_yield))
    out: Dict[str, float] = {}
    for s in universe:
        parts: List[float] = []
        if s.ticker in ey_rank:
            parts.append(ey_rank[s.ticker])
        if s.valuation_percentile_vs_history is not None:
            parts.append(100.0 - s.valuation_percentile_vs_history)
        if s.ev_ebit is not None and s.sector_median_ev_ebit:
            rel = (s.sector_median_ev_ebit - s.ev_ebit) / s.sector_median_ev_ebit
            parts.append(_clamp(50.0 + rel * 100.0))
        if parts:
            out[s.ticker] = round(sum(parts) / len(parts), 1)
    return out


def precedents_lens(s: SecuritySnapshot) -> Optional[float]:
    """Precedent-transactions logic: would an acquirer pay a premium?

    Control premiums historically run 25-35%, and they are paid for
    scarcity - moats that cannot be built, margin structures that
    survive integration - at prices not already reflecting a deal.
    Scarce AND cheap is the activist/strategic magnet; a mania multiple
    already prices more than any acquirer would pay (lens scores 0).
    """
    if s.moat_evidence_count is None:
        return None
    if s.mania_exposure:
        return 0.0
    score = (s.moat_evidence_count / 4.0) * 50.0
    if s.valuation_percentile_vs_history is not None:
        score += (100.0 - s.valuation_percentile_vs_history) * 0.30
    if s.gross_margin_stability is not None:
        score += s.gross_margin_stability * 20.0
    return round(_clamp(score), 1)


def firepower_lens(s: SecuritySnapshot) -> Optional[float]:
    """EY-adapted firepower: the company's own capacity to keep deploying.

    Long-term compounding is bought in downturns by whoever still has
    dry powder. Inputs mirror EY's construction (cash/debt capacity
    against a conservative leverage ceiling) plus the demonstrated
    WILL to deploy (owner yield) and somewhere to deploy INTO
    (reinvestment runway).
    """
    parts: List[float] = []
    if s.net_debt_to_ebitda is not None:
        parts.append(_clamp((FIREPOWER_ND_CAP - s.net_debt_to_ebitda)
                            / FIREPOWER_ND_CAP * 100.0) * 0.35)
    if s.fcf_to_net_income is not None:
        parts.append(_clamp(s.fcf_to_net_income * 80.0) * 0.25)
    btr = s.base_total_return()
    if btr is not None:
        parts.append(_clamp(50.0 + btr * 500.0) * 0.25)
    if s.reinvestment_runway is not None:
        parts.append((100.0 if s.reinvestment_runway else 30.0) * 0.15)
    if not parts:
        return None
    weight_used = (0.35 * (s.net_debt_to_ebitda is not None)
                   + 0.25 * (s.fcf_to_net_income is not None)
                   + 0.25 * (btr is not None)
                   + 0.15 * (s.reinvestment_runway is not None))
    return round(_clamp(sum(parts) / weight_used), 1)


# ---------------------------------------------------------------------------
# Composite
# ---------------------------------------------------------------------------


@dataclass
class SkyResult:
    ticker: str
    total: float
    components: Dict[str, float] = field(default_factory=dict)
    coverage: float = 1.0            # weight-share of lenses that had data
    gates_tripped: List[str] = field(default_factory=list)

    @property
    def verdict(self) -> str:
        if self.gates_tripped:
            return f"VETO ({', '.join(self.gates_tripped)})"
        t = self.total
        if t >= 80: return "GENERATIONAL"
        if t >= 70: return "CORE"
        if t >= 60: return "ACCUMULATE"
        if t >= 50: return "WATCH"
        return "PASS"


def sky_scores(universe: Sequence[SecuritySnapshot]) -> Dict[str, SkyResult]:
    """Score a universe. Cross-sectional lenses need the whole set."""
    fab = {s.ticker: fable_score(s) for s in universe}
    comps = comps_lens(universe)
    er_rank = methods.expected_return_ranks(universe)
    qual = methods.quality(universe)

    out: Dict[str, SkyResult] = {}
    for s in universe:
        t = s.ticker
        r = fab[t]
        if r.gates_tripped:
            out[t] = SkyResult(t, 0.0, gates_tripped=list(r.gates_tripped))
            continue
        a = methods.aoq(s)
        q = methods.qii(s)
        lens: Dict[str, Optional[float]] = {
            "fable": r.total,                       # already 0-100
            "exp_ret": er_rank.get(t),
            "quality": qual.get(t),
            "dcf": dcf_lens(s),
            "firepower": firepower_lens(s),
            "lbo": lbo_lens(s),
            "comps": comps.get(t),
            "qii": q,
            "precedents": precedents_lens(s),
            "aoq": None if a is None else _clamp(a * 40.0),   # 2.5 quotient -> 100
        }
        num = den = 0.0
        used: Dict[str, float] = {}
        for name, val in lens.items():
            if val is None:
                continue
            w = WEIGHTS[name]
            num += w * val
            den += w
            used[name] = round(val, 1)
        total = round(num / den, 1) if den else 0.0
        out[t] = SkyResult(t, total, components=used,
                           coverage=round(den / sum(WEIGHTS.values()), 2))
    return out
