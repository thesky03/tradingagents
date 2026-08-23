"""Backtesting and specification-testing harness for the scoring stack.

A score that has never been attacked is a hypothesis, not a tool. This
module supplies the attacks:

- ``perturb`` / ``rank_stability``: Monte Carlo over input uncertainty.
  If a ranking scrambles when inputs move within their stated error
  bars, its precision is decorative.
- ``lens_correlation``: are the components measuring distinct things,
  or is one factor wearing several hats and collecting several weights?
- ``weight_sensitivity``: does the answer survive reasonable
  disagreement about the weights?
- ``information_coefficient`` / ``decile_table``: the classic
  cross-sectional tests, for when real forward returns are available.
- ``regime_stress``: rescore under different macro assumptions. A
  long-horizon score that flips with the 10-year yield is a
  short-horizon score in disguise.

IMPORTANT on interpretation: an IC computed on scores whose inputs were
set with knowledge of the outcome measures hindsight, not skill. The
``structural_only`` filter exists to reduce (not eliminate) that
contamination by blanking the price- and tape-derived fields, leaving
slow-moving business characteristics.
"""

from __future__ import annotations

import random
from dataclasses import replace
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from .fable_score import SecuritySnapshot
from .methods import _percentile_ranks, spearman


# Fields whose value is derived from price action or recent tape. When
# testing predictive content, these are the contaminated ones: their
# values in a snapshot built today encode what the market already did.
PRICE_DERIVED_FIELDS = (
    "momentum_12_1_percentile", "above_200dma", "relative_strength_on_down_days",
    "pct_off_52w_high", "valuation_percentile_vs_history", "earnings_yield",
    "ev_ebit", "short_interest_pct_float", "estimate_revision_breadth",
)

# Percentile-scaled fields get additive noise; ratio fields multiplicative.
_PERCENTILE_FIELDS = ("momentum_12_1_percentile", "valuation_percentile_vs_history")
_RATIO_FIELDS = (
    "gross_profit_to_assets", "roic", "wacc", "fcf_to_net_income",
    "accruals_to_assets", "revenue_cagr_3y", "earnings_yield", "ev_ebit",
    "implied_growth", "demonstrated_growth", "downside_loss_if_growth_halves",
    "gross_margin_stability", "net_debt_to_ebitda", "interest_coverage",
    "pct_off_52w_high", "dividend_yield", "buyback_yield", "sbc_yield",
    "annual_volatility", "share_count_growth_3y",
)


def structural_only(s: SecuritySnapshot) -> SecuritySnapshot:
    """Blank every price-derived field, keeping business characteristics.

    Used to build a lower-contamination variant of a score for
    predictive testing: owner yield, leverage, margins, moat and cash
    conversion move slowly and were largely knowable before the period
    being tested; momentum and valuation percentile were not.
    """
    return replace(s, **{f: None for f in PRICE_DERIVED_FIELDS
                         if getattr(s, f, None) is not None})


def perturb(s: SecuritySnapshot, rng: random.Random,
            magnitude: float = 1.0) -> SecuritySnapshot:
    """Jitter one snapshot within its stated uncertainty.

    Ratio fields get ~15% relative Gaussian noise, percentile fields
    ~10 points additive, and ``margin_trend`` flips one notch with 15%
    probability - roughly the +/-10-point score uncertainty the sweep
    inputs carry. ``magnitude`` scales all of it.
    """
    changes: Dict[str, object] = {}
    for f in _RATIO_FIELDS:
        v = getattr(s, f, None)
        if v is None:
            continue
        changes[f] = v * (1.0 + rng.gauss(0.0, 0.15 * magnitude))
    for f in _PERCENTILE_FIELDS:
        v = getattr(s, f, None)
        if v is None:
            continue
        changes[f] = max(0.0, min(100.0, v + rng.gauss(0.0, 10.0 * magnitude)))
    if s.margin_trend is not None and rng.random() < 0.15 * magnitude:
        changes["margin_trend"] = max(-1, min(1, s.margin_trend + rng.choice((-1, 1))))
    return replace(s, **changes)


def rank_stability(universe: Sequence[SecuritySnapshot],
                   scorer: Callable[[Sequence[SecuritySnapshot]], Dict[str, float]],
                   top_k: int = 25, trials: int = 200,
                   magnitude: float = 1.0, seed: int = 7) -> Dict[str, float]:
    """How much of the top-K survives input noise?

    Returns mean Jaccard overlap of the perturbed top-K against the
    unperturbed top-K, the mean rank correlation, and per-name
    retention for the baseline top-K.
    """
    rng = random.Random(seed)
    base = scorer(universe)
    base_top = set(sorted(base, key=lambda t: -base[t])[:top_k])
    overlaps: List[float] = []
    rhos: List[float] = []
    retention: Dict[str, int] = {t: 0 for t in base_top}
    for _ in range(trials):
        jittered = [perturb(s, rng, magnitude) for s in universe]
        scores = scorer(jittered)
        top = set(sorted(scores, key=lambda t: -scores[t])[:top_k])
        overlaps.append(len(top & base_top) / max(len(base_top), 1))
        rho = spearman(base, scores)
        if rho is not None:
            rhos.append(rho)
        for t in top & base_top:
            retention[t] += 1
    return {
        "mean_topk_overlap": round(sum(overlaps) / len(overlaps), 3),
        "min_topk_overlap": round(min(overlaps), 3),
        "mean_rank_corr": round(sum(rhos) / len(rhos), 3) if rhos else float("nan"),
        "retention": {t: round(n / trials, 2) for t, n in sorted(
            retention.items(), key=lambda kv: -kv[1])},
    }


def lens_correlation(components: Dict[str, Dict[str, float]]) -> Dict[Tuple[str, str], float]:
    """Pairwise Spearman among lens outputs: {lens: {ticker: value}}."""
    names = sorted(components)
    out: Dict[Tuple[str, str], float] = {}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            rho = spearman(components[a], components[b])
            if rho is not None:
                out[(a, b)] = rho
    return out


def effective_independent_weight(components: Dict[str, Dict[str, float]],
                                 weights: Dict[str, float],
                                 threshold: float = 0.70) -> Dict[str, float]:
    """Group lenses correlated above ``threshold`` and sum their weights.

    Reveals when several nominally-separate components are one bet:
    three 'cheap' lenses at 8% each are a 24% value bet, not
    diversification.
    """
    names = [n for n in weights if n in components]
    parent = {n: n for n in names}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for (a, b), rho in lens_correlation({n: components[n] for n in names}).items():
        if rho >= threshold:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra
    blocs: Dict[str, float] = {}
    members: Dict[str, List[str]] = {}
    for n in names:
        root = find(n)
        blocs[root] = blocs.get(root, 0.0) + weights[n]
        members.setdefault(root, []).append(n)
    return {"+".join(sorted(members[r])): round(w, 3)
            for r, w in sorted(blocs.items(), key=lambda kv: -kv[1])}


def weight_sensitivity(universe: Sequence[SecuritySnapshot],
                       scorer_factory: Callable[[Dict[str, float]],
                                                Callable[[Sequence[SecuritySnapshot]],
                                                         Dict[str, float]]],
                       weights: Dict[str, float], top_k: int = 25,
                       trials: int = 100, jitter: float = 0.30,
                       seed: int = 11) -> Dict[str, float]:
    """Perturb the WEIGHTS (not the data) and measure ranking stability.

    Each weight is multiplied by 1 +/- up to ``jitter`` and renormalized.
    A score whose top-K survives 30% weight disagreement is robust to
    the fact that nobody can defend 12% versus 15% precisely.
    """
    rng = random.Random(seed)
    base = scorer_factory(weights)(universe)
    base_top = set(sorted(base, key=lambda t: -base[t])[:top_k])
    overlaps, rhos = [], []
    for _ in range(trials):
        w = {k: max(v * (1.0 + rng.uniform(-jitter, jitter)), 1e-6)
             for k, v in weights.items()}
        tot = sum(w.values())
        w = {k: v / tot for k, v in w.items()}
        scores = scorer_factory(w)(universe)
        top = set(sorted(scores, key=lambda t: -scores[t])[:top_k])
        overlaps.append(len(top & base_top) / max(len(base_top), 1))
        rho = spearman(base, scores)
        if rho is not None:
            rhos.append(rho)
    return {"mean_topk_overlap": round(sum(overlaps) / len(overlaps), 3),
            "min_topk_overlap": round(min(overlaps), 3),
            "mean_rank_corr": round(sum(rhos) / len(rhos), 3) if rhos else float("nan")}


def information_coefficient(scores: Dict[str, float],
                            forward_returns: Dict[str, float]) -> Optional[Dict[str, float]]:
    """Spearman IC between a score and realized forward returns.

    Also reports n and an approximate standard error (1/sqrt(n-1)), so
    an IC can be read against its own noise floor instead of being
    admired in isolation.
    """
    common = sorted(set(scores) & set(forward_returns))
    if len(common) < 5:
        return None
    rho = spearman({t: scores[t] for t in common},
                   {t: forward_returns[t] for t in common})
    n = len(common)
    return {"ic": rho, "n": n, "stderr": round((n - 1) ** -0.5, 3)}


def decile_table(scores: Dict[str, float], forward_returns: Dict[str, float],
                 buckets: int = 5) -> List[Dict[str, float]]:
    """Bucket by score, report mean forward return per bucket.

    Monotonicity across buckets matters more than the spread between
    the extremes: a score that only works at the tails is a screen for
    outliers, not a ranking.
    """
    common = sorted(set(scores) & set(forward_returns))
    if len(common) < buckets * 2:
        return []
    ordered = sorted(common, key=lambda t: scores[t])
    size = len(ordered) / buckets
    rows = []
    for b in range(buckets):
        chunk = ordered[int(b * size):int((b + 1) * size)]
        if not chunk:
            continue
        rets = [forward_returns[t] for t in chunk]
        rows.append({
            "bucket": b + 1,
            "n": len(chunk),
            "mean_score": round(sum(scores[t] for t in chunk) / len(chunk), 1),
            "mean_return": round(sum(rets) / len(rets), 3),
            "hit_rate": round(sum(1 for r in rets if r > 0) / len(rets), 2),
        })
    return rows


def regime_stress(universe: Sequence[SecuritySnapshot],
                  scorer: Callable[[Sequence[SecuritySnapshot]], Dict[str, float]],
                  scenarios: Dict[str, Dict[str, object]],
                  top_k: int = 25) -> Dict[str, Dict[str, float]]:
    """Rescore the universe under macro scenarios.

    ``scenarios`` maps a label to field overrides applied to every
    snapshot (e.g. {"rates_6pct": {"treasury_10y_yield": 0.06}}).
    Reports top-K overlap and rank correlation against the base case.
    """
    base = scorer(universe)
    base_top = set(sorted(base, key=lambda t: -base[t])[:top_k])
    out: Dict[str, Dict[str, float]] = {}
    for label, overrides in scenarios.items():
        shifted = [replace(s, **overrides) for s in universe]
        scores = scorer(shifted)
        top = set(sorted(scores, key=lambda t: -scores[t])[:top_k])
        out[label] = {
            "topk_overlap": round(len(top & base_top) / max(len(base_top), 1), 3),
            "rank_corr": spearman(base, scores),
            "entered": sorted(top - base_top)[:6],
            "exited": sorted(base_top - top)[:6],
        }
    return out
