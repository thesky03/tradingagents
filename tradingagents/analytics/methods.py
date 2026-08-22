"""Alternative ranking methods over a universe of SecuritySnapshots.

Each method is a classic, evidence-backed selection discipline reduced to
the fields ``SecuritySnapshot`` carries. They exist to be compared - each
has a documented edge, a documented failure mode, and a natural horizon:

==================  =======================  ==========================
Method              Edge (evidence)          Failure mode
==================  =======================  ==========================
momentum            Strongest documented     Crashes at regime turns
                    premium (Jegadeesh-      (1932, 2009): the winners
                    Titman 1993; ~1%/mo)     portfolio inverts hardest
magic_formula       Cheap x good compounds   Value traps; long droughts
                    (Greenblatt 2005; ey +   (2015-2020 style regimes)
                    ROIC combined rank)
quality             Profitable, safe, high-  Pays off slowly; can lag
                    payout beats junk        raging bull markets
                    (Asness/AQR QMJ 2019)
growth_momentum     New-high leadership      Buys blow-off tops when
                    (O'Neil CAN-SLIM)        the cycle is late
low_volatility      Low-beta anomaly         Rate-sensitive; crowded
                    (Haugen/Baker)           when fear is popular
expected_return     TSR decomposition:       Assumes multiple mean-
                    owner yield + growth     reversion; slow clock
                    +/- rerating drag
==================  =======================  ==========================

All rank-based methods return {ticker: percentile 0-100} over the given
universe. ``expected_return`` is absolute (decimal per year), not a rank.

None of these see the FABLE gates. That is deliberate: comparing what a
naive method buys against what the gates forbid is the risk lesson -
momentum loves the mania names right up until it doesn't.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, Sequence

from .fable_score import SecuritySnapshot


# ---------------------------------------------------------------------------
# Ranking plumbing
# ---------------------------------------------------------------------------


def _percentile_ranks(values: Dict[str, float]) -> Dict[str, float]:
    """Map ticker -> 0-100 percentile of its value within the universe."""
    if not values:
        return {}
    ordered = sorted(values, key=lambda t: values[t])
    n = len(ordered)
    if n == 1:
        return {ordered[0]: 50.0}
    return {t: round(100.0 * i / (n - 1), 1) for i, t in enumerate(ordered)}


def _collect(universe: Sequence[SecuritySnapshot],
             fn: Callable[[SecuritySnapshot], Optional[float]]) -> Dict[str, float]:
    out = {}
    for s in universe:
        v = fn(s)
        if v is not None:
            out[s.ticker] = v
    return out


# ---------------------------------------------------------------------------
# Methods
# ---------------------------------------------------------------------------


def momentum(universe: Sequence[SecuritySnapshot]) -> Dict[str, float]:
    """Pure 12-1 momentum with a trend-intact requirement.

    A name below its 200-day gets its percentile halved rather than
    zeroed - momentum that just broke may resume, but the position of
    strength is gone.
    """
    raw = _collect(universe, lambda s: s.momentum_12_1_percentile)
    ranks = _percentile_ranks(raw)
    for s in universe:
        if s.ticker in ranks and s.above_200dma is False:
            ranks[s.ticker] = round(ranks[s.ticker] * 0.5, 1)
    return ranks


def magic_formula(universe: Sequence[SecuritySnapshot]) -> Dict[str, float]:
    """Greenblatt: combined rank of earnings yield and ROIC.

    'Cheap' and 'good' each rank 0-100; the method is their average, so
    a name must be decently both - the whole point of the formula.
    """
    ey = _percentile_ranks(_collect(universe, lambda s: s.earnings_yield))
    roic = _percentile_ranks(_collect(universe, lambda s: s.roic))
    out = {}
    for t in set(ey) & set(roic):
        out[t] = round((ey[t] + roic[t]) / 2, 1)
    return out


def quality(universe: Sequence[SecuritySnapshot]) -> Dict[str, float]:
    """AQR-style quality-minus-junk proxy.

    Profitability (GP/A, ROIC spread, cash conversion), safety (low
    volatility, low leverage, stable margins), payout (positive owner
    yield). Equal-weighted percentile composite.
    """
    components = [
        _percentile_ranks(_collect(universe, lambda s: s.gross_profit_to_assets)),
        _percentile_ranks(_collect(
            universe,
            lambda s: (s.roic - s.wacc) if s.roic is not None and s.wacc is not None else None)),
        _percentile_ranks(_collect(universe, lambda s: s.fcf_to_net_income)),
        _percentile_ranks(_collect(universe, lambda s: -s.annual_volatility)),
        _percentile_ranks(_collect(
            universe,
            lambda s: -s.net_debt_to_ebitda if s.net_debt_to_ebitda is not None else None)),
        _percentile_ranks(_collect(universe, lambda s: s.gross_margin_stability)),
        _percentile_ranks(_collect(universe, lambda s: s.base_total_return())),
    ]
    out: Dict[str, float] = {}
    for s in universe:
        vals = [c[s.ticker] for c in components if s.ticker in c]
        if vals:
            out[s.ticker] = round(sum(vals) / len(vals), 1)
    return out


def growth_momentum(universe: Sequence[SecuritySnapshot]) -> Dict[str, float]:
    """O'Neil-style: accelerating growth bought near strength.

    Growth rank and momentum rank, with a new-high proximity kicker -
    CAN-SLIM buys leaders near highs, exactly what value disciplines
    refuse to do. Kept honest by comparison, not by dilution.
    """
    g = _percentile_ranks(_collect(universe, lambda s: s.revenue_cagr_3y))
    m = _percentile_ranks(_collect(universe, lambda s: s.momentum_12_1_percentile))
    out = {}
    for s in universe:
        t = s.ticker
        if t in g and t in m:
            near_high = 1.0 - min(s.pct_off_52w_high or 0.5, 0.5)
            out[t] = round((0.45 * g[t] + 0.45 * m[t]) * (0.6 + 0.8 * near_high) / 1.4 * 1.4, 1)
    # normalize back to percentiles for comparability
    return _percentile_ranks(out)


def low_volatility(universe: Sequence[SecuritySnapshot]) -> Dict[str, float]:
    """Low-vol anomaly with a quality tilt (70/30)."""
    lv = _percentile_ranks(_collect(universe, lambda s: -s.annual_volatility))
    q = quality(universe)
    out = {}
    for t in set(lv) & set(q):
        out[t] = round(0.7 * lv[t] + 0.3 * q[t], 1)
    return out


def expected_return(s: SecuritySnapshot,
                    rerating_horizon_years: float = 7.0) -> Optional[float]:
    """Long-horizon total shareholder return decomposition, decimal/yr.

    TSR = owner yield (dividend + buyback - SBC)
        + per-share organic growth
        +/- multiple mean-reversion drag.

    The rerating term assumes a name at its valuation extremes drifts
    halfway back to its own median over the horizon: an expensive
    multiple is a scheduled headwind, a cheap one a scheduled tailwind.
    This extends the base-total-return idea to "the gain you get before
    the market moves, plus the move the market owes you".
    """
    btr = s.base_total_return()
    if btr is None or s.revenue_cagr_3y is None:
        return None
    drag = 0.0
    if s.valuation_percentile_vs_history is not None:
        # +/-50 percentile from median, half-reverted over the horizon,
        # ~0.8% of price per 10 percentile points as a coarse elasticity.
        displacement = (s.valuation_percentile_vs_history - 50.0) / 10.0
        drag = -(displacement * 0.008) * 0.5 * (7.0 / rerating_horizon_years)
    return round(btr + s.revenue_cagr_3y + drag, 4)


def expected_return_ranks(universe: Sequence[SecuritySnapshot]) -> Dict[str, float]:
    return _percentile_ranks(_collect(universe, expected_return))


# ---------------------------------------------------------------------------
# Comparison utilities
# ---------------------------------------------------------------------------


def spearman(a: Dict[str, float], b: Dict[str, float]) -> Optional[float]:
    """Spearman rank correlation over the tickers both methods scored."""
    common = sorted(set(a) & set(b))
    if len(common) < 3:
        return None
    ra = _percentile_ranks({t: a[t] for t in common})
    rb = _percentile_ranks({t: b[t] for t in common})
    xs = [ra[t] for t in common]
    ys = [rb[t] for t in common]
    n = len(common)
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs) ** 0.5
    vy = sum((y - my) ** 2 for y in ys) ** 0.5
    if vx == 0 or vy == 0:
        return None
    return round(cov / (vx * vy), 3)


def consensus(rankings: Dict[str, Dict[str, float]],
              weights: Optional[Dict[str, float]] = None) -> Dict[str, float]:
    """Weighted average percentile across methods (missing = skipped)."""
    weights = weights or {name: 1.0 for name in rankings}
    out: Dict[str, float] = {}
    tickers = set()
    for r in rankings.values():
        tickers |= set(r)
    for t in tickers:
        num = den = 0.0
        for name, r in rankings.items():
            if t in r:
                w = weights.get(name, 1.0)
                num += w * r[t]
                den += w
        if den:
            out[t] = round(num / den, 1)
    return out


# ---------------------------------------------------------------------------
# Operator-directed methods (defined in-session under delegated judgment)
# ---------------------------------------------------------------------------


def aoq(s: SecuritySnapshot) -> Optional[float]:
    """Asymmetry-of-Outcomes Quotient: upside per unit of modeled downside.

    Definition (authored by the model at the operator's direction; the
    operator named the method, the construction is this module's):

        AOQ = (expected annual return + positive catalyst EV)
              / (downside-if-wrong, scaled by volatility)

    where expected annual return is the TSR decomposition from
    ``expected_return`` (owner yield + growth +/- rerating drag), the
    catalyst term counts only positive coin-flip EV, and the denominator
    is the modeled loss if growth halves, scaled up for high-volatility
    names (a 50% drawdown risked in a 0.5-vol name is a live scenario,
    not a tail). Values: <1 poor shape, 1-2 acceptable, >2 attractive,
    capped at 5 so one heroic denominator cannot dominate a ranking.

    This scores payoff GEOMETRY where FABLE scores level; a mediocre
    business at a bid-backstopped price can carry a better AOQ than a
    great business priced for perfection.
    """
    er = expected_return(s)
    if er is None or s.downside_loss_if_growth_halves is None:
        return None
    upside = max(er, 0.0)
    if s.catalyst is not None:
        ev = s.catalyst.expected_value()
        if ev is not None and ev > 0:
            upside += ev
    vol_scale = 0.5 + (s.annual_volatility or 0.30)
    downside = max(s.downside_loss_if_growth_halves * vol_scale, 0.08)
    return round(min(upside / downside, 5.0), 3)


def qii(s: SecuritySnapshot) -> Optional[float]:
    """Quality-Improvement Index, 0-100: is the business getting BETTER?

    Definition (authored by the model at the operator's direction).
    FABLE's F and L pillars score the level of quality; QII scores its
    first derivative - the inflections the market systematically
    underprices (earnings-revision drift, Bernard-Thomas PEAD;
    Piotroski's improvement signals). Components from a neutral 50:

        margin trend        +/-12   (expanding vs contracting)
        revision breadth    +/-15   (estimates moving up or down)
        cash quality        +/-10   (FCF/NI vs a 0.85 par)
        tape confirmation   +/- 8   (momentum agreeing with the story)
        balance-sheet room  +/- 5   (headroom to keep improving)
        capital allocation  +/- 5   (owner yield sign and size)

    A high-QII/low-FABLE name is an inflection candidate; a low-QII/
    high-FABLE name is a great business past its improvement phase.
    """
    known = 0
    score = 50.0
    if s.margin_trend is not None:
        score += s.margin_trend * 12; known += 1
    if s.estimate_revision_breadth is not None:
        score += max(-1.0, min(1.0, s.estimate_revision_breadth)) * 15; known += 1
    if s.fcf_to_net_income is not None:
        score += max(-10.0, min(10.0, (s.fcf_to_net_income - 0.85) * 30)); known += 1
    if s.momentum_12_1_percentile is not None:
        score += (s.momentum_12_1_percentile - 50.0) / 50.0 * 8; known += 1
    if s.net_debt_to_ebitda is not None:
        score += max(-1.0, min(1.0, (2.0 - s.net_debt_to_ebitda) / 2.0)) * 5; known += 1
    btr = s.base_total_return()
    if btr is not None:
        score += max(-5.0, min(5.0, btr * 100)); known += 1
    if known == 0:
        return None
    return round(max(0.0, min(100.0, score)), 1)


def aoq_ranks(universe: Sequence[SecuritySnapshot]) -> Dict[str, float]:
    return _percentile_ranks(_collect(universe, aoq))


def qii_ranks(universe: Sequence[SecuritySnapshot]) -> Dict[str, float]:
    return _percentile_ranks(_collect(universe, qii))
