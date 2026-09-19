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
FIREPOWER_ND_CAP = 3.0         # EY's ~30% D/E spirit mapped to ND/EBITDA turns


#: The 10-year yield the rest of the weights were calibrated against.
#: Deviations from it drive the rate-pressure lens.
RATE_NEUTRAL_10Y = 0.042


def equity_duration(s: SecuritySnapshot) -> Optional[float]:
    """Crude equity duration in years: how distant are the cash flows?

    A high multiple IS long duration - most of the value sits in the
    out-years. P/E is the available proxy; capped at 60 because past
    that the estimate is noise, not information.
    """
    if s.earnings_yield is None or s.earnings_yield <= 0:
        return None
    return min(1.0 / s.earnings_yield, 60.0)


def rate_pressure_lens(s: SecuritySnapshot) -> Optional[float]:
    """What the prevailing risk-free rate does to this name's valuation.

    Added in v3 after a failed out-of-sample test. SKY carried no
    discount-rate channel at all: moving the 10-year from 4.70% to
    5.00% - the actual September 2026 move, to a 19-year high - changed
    its cross-sectional ranking by a Spearman correlation of 1.0000 and
    0.047 points per name. A score claiming a decade horizon cannot be
    indifferent to the rate those decades are discounted at.

    The mechanism is arithmetic, not a fitted pattern: the present value
    of distant cash flows falls roughly in proportion to duration times
    the change in yield. Scored 50 at the neutral anchor, below it when
    rates are above and the name is long-duration, above it when rates
    fall or the name is short-duration.

    HONEST LIMIT: this would NOT have rescued the September test. The
    long-duration names there outperformed (NVDA at ~29x rose 26% on an
    earnings beat while ADBE at ~10x fell) because idiosyncratic
    surprises swamped the rate effect across 17 names in 27 days. It is
    here because the mechanism is real over a decade, not because it
    fixes a month.
    """
    d = equity_duration(s)
    if d is None or s.treasury_10y_yield is None:
        return None
    excess = s.treasury_10y_yield - RATE_NEUTRAL_10Y
    pv_impact = -d * excess          # fractional PV change
    return round(_clamp(50.0 + pv_impact * 100.0), 1)


def cyclically_adjusted_earnings_yield(s: SecuritySnapshot) -> Optional[float]:
    """Earnings yield haircut by how trustworthy the earnings are.

    Graham's ten-year average and Shiller's CAPE exist because a single
    year's earnings mislead most exactly when they look best: at the
    cycle peak. Without an earnings history per name, gross-margin
    stability is the available proxy for how much of current earnings
    is durable. A rock-stable business keeps its full yield; a 0.35-
    stability memory maker keeps ~68% of it.

    Introduced in v2 after the backtest loops traced an 8-of-25
    deep-cyclical concentration in the top ranks to raw earnings yield
    feeding three lenses at once.
    """
    if s.earnings_yield is None:
        return None
    stab = s.gross_margin_stability if s.gross_margin_stability is not None else 0.75
    return s.earnings_yield * (0.5 + 0.5 * stab)

# v2 weights. The value bloc (dcf+comps+lbo) fell 26% -> 21% after the
# redundancy loop measured comps x lbo at rho 0.88 and comps x dcf at
# 0.71 - one cheapness factor collecting three weights. The freed
# weight went to quality, the least redundant lens and the one most
# aligned with a decade-long hold.
# v3 weights. Adding the rate-pressure lens at 8% required taking
# weight from everything else; fable and exp_ret gave up the most since
# they were the largest. The value bloc (dcf+comps+lbo) is now 19%.
WEIGHTS = {
    "fable": 0.20,      # level of the business + margin of safety + gates
    "exp_ret": 0.15,    # TSR decomposition: what the hold actually earns
    "quality": 0.14,    # AQR-style durability
    "dcf": 0.09,        # intrinsic-value gap, cyclically adjusted
    "firepower": 0.09,  # capacity to keep compounding through cycles
    "rate": 0.08,       # NEW v3: duration x prevailing risk-free rate
    "qii": 0.06,        # trajectory (small: decade holds outlive quarters)
    "lbo": 0.05,        # financeability, not cheapness
    "comps": 0.05,      # purely cross-sectional relative value
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
    caey = cyclically_adjusted_earnings_yield(s)
    if caey is None or s.wacc is None:
        return None
    g_sustain = min(s.revenue_cagr_3y if s.revenue_cagr_3y is not None else 0.03, 0.05)
    fair_ey = max(s.wacc - g_sustain, 0.02)
    gap = caey / fair_ey
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
    if s.net_debt_to_ebitda is None and s.fcf_to_net_income is None:
        return None
    # v2: the earnings-yield term was removed - it duplicated the DCF and
    # comps lenses (measured rho 0.68 and 0.88). This lens now answers only
    # "can this balance sheet and cash flow CARRY sponsor leverage", which
    # is the part no other lens measures.
    score = 0.0
    if s.net_debt_to_ebitda is not None:
        headroom = max(LBO_LEVERAGE_TURNS - max(s.net_debt_to_ebitda, 0.0), 0.0)
        score += 45.0 * min(headroom / LBO_LEVERAGE_TURNS, 1.0)
    if s.fcf_to_net_income is not None:
        score += 30.0 * min(s.fcf_to_net_income / 1.0, 1.2)
    if s.gross_margin_stability is not None:
        score += 25.0 * s.gross_margin_stability
    return round(_clamp(score), 1)


def comps_lens(universe: Sequence[SecuritySnapshot]) -> Dict[str, float]:
    """Trading comparables: cheap versus peers and versus own history.

    Cross-sectional earnings-yield rank (the universe IS the comp set),
    inverted own-history valuation percentile, and EV/EBIT vs sector
    median where sourced. Equal-weighted across whatever is available.
    """
    # v2.1: ranked WITHIN peer group, not across the whole universe. A
    # comps table compares a refiner to refiners. Universe-wide ranking
    # made this lens a second copy of the DCF lens (measured rho +0.78);
    # peer-relative ranking asks the different question - cheap versus
    # the businesses it actually competes with - and drops that overlap.
    groups: Dict[str, List[SecuritySnapshot]] = {}
    for sec in universe:
        groups.setdefault(sec.peer_group or "_all", []).append(sec)
    ey_rank: Dict[str, float] = {}
    for label, members in groups.items():
        # A peer set of one or two says nothing; fall back to the universe.
        pool = members if len(members) >= 4 else list(universe)
        ey_rank.update({
            t: v for t, v in methods._percentile_ranks(
                methods._collect(pool, cyclically_adjusted_earnings_yield)).items()
            if any(m.ticker == t for m in members)})
    out: Dict[str, float] = {}
    for s in universe:
        parts: List[float] = []
        if s.ticker in ey_rank:
            parts.append(ey_rank[s.ticker])
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
    # v2.2: the balance-sheet terms were cut (0.35 -> 0.15 leverage, 0.25 ->
    # 0.10 conversion) because they duplicated the LBO lens at rho +0.81.
    # Firepower now leads with what only it measures: the DEMONSTRATED WILL
    # to deploy (owner yield) and somewhere worth deploying into (runway).
    # LBO asks whether a buyer could carry the debt; firepower asks whether
    # this management actually turns capacity into per-share value.
    parts: List[float] = []
    if s.net_debt_to_ebitda is not None:
        parts.append(_clamp((FIREPOWER_ND_CAP - s.net_debt_to_ebitda)
                            / FIREPOWER_ND_CAP * 100.0) * 0.15)
    if s.fcf_to_net_income is not None:
        parts.append(_clamp(s.fcf_to_net_income * 80.0) * 0.10)
    btr = s.base_total_return()
    if btr is not None:
        parts.append(_clamp(50.0 + btr * 500.0) * 0.45)
    if s.reinvestment_runway is not None:
        parts.append((100.0 if s.reinvestment_runway else 30.0) * 0.30)
    if not parts:
        return None
    weight_used = (0.15 * (s.net_debt_to_ebitda is not None)
                   + 0.10 * (s.fcf_to_net_income is not None)
                   + 0.45 * (btr is not None)
                   + 0.30 * (s.reinvestment_runway is not None))
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
        # v2: the noise loop showed only three names held the top tier in
        # every Monte Carlo trial. GENERATIONAL now requires the data to
        # back the claim, not just the arithmetic.
        if t >= 80 and self.coverage >= 0.90: return "GENERATIONAL"
        if t >= 80: return "CORE"
        if t >= 70: return "CORE"
        if t >= 60: return "ACCUMULATE"
        if t >= 50: return "WATCH"
        return "PASS"


def value_conviction_multiplier(s: SecuritySnapshot,
                                qii_value: Optional[float]) -> float:
    """Piotroski's discipline: inside the cheap bucket, separate the
    improving from the deteriorating.

    v2.3, motivated by the style-tilt loop. SKY's highest-scoring names
    cluster in recent decliners - which is the value mechanism working,
    and also exactly the population where value traps live. Cheapness
    earned by a business that is getting worse is not margin of safety,
    it is a discount that keeps widening.

    Returns a multiplier applied ONLY to the cheapness lenses (dcf,
    comps). Deterioration does not touch quality, moat, or firepower -
    a temporarily struggling great business keeps its durability score.
    A name with no QII reading is treated as neutral.

    RETAINED ON PRIOR EVIDENCE, NOT ON OURS. The loop-7 check against
    2026 trailing returns did not support this rule: the names it
    discounts averaged +25.9% against +20.1% for the rest. That sample
    was 8 names of trailing (not forward) return, so it has no real
    power either way - but it is not confirmation, and calling it
    confirmation would be dishonest. The rule stands because Piotroski
    (2000) is among the best-replicated results in the literature, and
    because it is deliberately mild (at most a 35% haircut, on 2 of 10
    lenses). Revisit it the moment genuine forward returns exist.
    """
    if qii_value is None:
        return 1.0
    if qii_value >= 50.0:
        return 1.0
    if qii_value >= 35.0:
        return 0.85
    return 0.65


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
        vcm = value_conviction_multiplier(s, q)
        _dcf = dcf_lens(s)
        _comps = comps.get(t)
        lens: Dict[str, Optional[float]] = {
            "fable": r.total,                       # already 0-100
            "exp_ret": er_rank.get(t),
            "quality": qual.get(t),
            "dcf": None if _dcf is None else round(_dcf * vcm, 1),
            "firepower": firepower_lens(s),
            "rate": rate_pressure_lens(s),
            "lbo": lbo_lens(s),
            "comps": None if _comps is None else round(_comps * vcm, 1),
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
