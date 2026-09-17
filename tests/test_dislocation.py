"""Tests for the dislocation screen (tradingagents.analytics.dislocation).

The module exists to fix a specific failure: FABLE-5 and SKY reject a
stock *because* it fell, since the Behavior pillar scores momentum. So
these tests are written around one question - can the screen tell a
narrative dislocation apart from a value trap, when on the tape they
look identical?
"""

from __future__ import annotations

import pytest

from tradingagents.analytics import (
    MIN_DRAWDOWN,
    SEVERE_DRAWDOWN,
    SecuritySnapshot,
    dislocation_score,
    entry_signal,
    screen_dislocations,
)


def _dislocated(**overrides) -> SecuritySnapshot:
    """Down 40%; the business is still compounding. Accenture-shaped."""
    base = dict(
        ticker="DISLOC",
        # the business: unchanged by the narrative
        gross_profit_to_assets=0.38, roic=0.20, wacc=0.085,
        fcf_to_net_income=1.10, accruals_to_assets=0.02,
        margin_trend=0, revenue_cagr_3y=0.06,
        demonstrated_growth=0.08,
        gross_margin_stability=0.88, moat_evidence_count=3,
        net_debt_to_ebitda=0.4, interest_coverage=25.0,
        reinvestment_runway=True, insider_alignment=True,
        # the price: wrecked
        momentum_12_1_percentile=4.0, above_200dma=False,
        pct_off_52w_high=0.40, valuation_percentile_vs_history=8.0,
        earnings_yield=0.075, treasury_10y_yield=0.042,
        # management buying its own stock into the fall
        dividend_yield=0.022, buyback_yield=0.045, sbc_yield=0.012,
        has_defined_exit=True, adequately_liquid=True,
    )
    base.update(overrides)
    return SecuritySnapshot(**base)


def _trap(**overrides) -> SecuritySnapshot:
    """Also down 40% - but the numbers agree with the bears."""
    base = dict(
        ticker="TRAP",
        gross_profit_to_assets=0.14, roic=0.05, wacc=0.09,
        fcf_to_net_income=0.55, accruals_to_assets=0.06,
        margin_trend=-1, revenue_cagr_3y=-0.03,
        demonstrated_growth=-0.02,
        gross_margin_stability=0.45, moat_evidence_count=0,
        net_debt_to_ebitda=3.9, interest_coverage=3.0,
        reinvestment_runway=False, insider_alignment=False,
        momentum_12_1_percentile=4.0, above_200dma=False,
        pct_off_52w_high=0.40, valuation_percentile_vs_history=8.0,
        earnings_yield=0.075, treasury_10y_yield=0.042,
        dividend_yield=0.03, buyback_yield=0.0, sbc_yield=0.02,
        has_defined_exit=True, adequately_liquid=True,
    )
    base.update(overrides)
    return SecuritySnapshot(**base)


# --- The screen only speaks about drawdowns -----------------------------------

def test_silent_on_names_near_their_highs():
    assert dislocation_score(_dislocated(pct_off_52w_high=0.05)) is None
    assert dislocation_score(_dislocated(pct_off_52w_high=None)) is None


def test_threshold_is_exactly_min_drawdown():
    assert dislocation_score(
        _dislocated(pct_off_52w_high=MIN_DRAWDOWN - 0.001)) is None
    assert dislocation_score(
        _dislocated(pct_off_52w_high=MIN_DRAWDOWN)) is not None


# --- The central discrimination -----------------------------------------------

def test_same_drawdown_opposite_verdicts():
    """The whole point: identical on the tape, opposite underneath."""
    good = dislocation_score(_dislocated())
    bad = dislocation_score(_trap())
    assert good.drawdown == bad.drawdown
    assert not good.is_trap
    assert bad.is_trap
    assert good.score > bad.score + 25.0
    assert good.verdict in ("DISLOCATION", "PRIME DISLOCATION")
    assert bad.verdict.startswith("TRAP")


def test_trap_reasons_are_specific_not_generic():
    r = dislocation_score(_trap())
    joined = " ".join(r.trap_reasons)
    assert "returns below cost of capital" in joined
    assert any("leverage" in x for x in r.trap_reasons)


def test_intactness_ignores_the_price():
    """Momentum must not move the intactness reading - that was the bug."""
    wrecked = dislocation_score(_dislocated(
        momentum_12_1_percentile=1.0, above_200dma=False,
        relative_strength_on_down_days=False))
    calm = dislocation_score(_dislocated(
        momentum_12_1_percentile=60.0, above_200dma=True,
        relative_strength_on_down_days=True))
    assert wrecked.intactness == calm.intactness
    assert wrecked.score == calm.score


# --- Drawdown is scored as the prize, and it saturates ------------------------

def test_deeper_drawdown_scores_higher_while_intact():
    shallow = dislocation_score(_dislocated(pct_off_52w_high=0.27))
    deep = dislocation_score(_dislocated(pct_off_52w_high=0.44))
    assert deep.score > shallow.score


def test_drawdown_term_saturates():
    at_cap = dislocation_score(_dislocated(pct_off_52w_high=0.45))
    past_cap = dislocation_score(_dislocated(pct_off_52w_high=0.49))
    assert at_cap.score == past_cap.score


def test_severe_drawdown_is_treated_as_information():
    r = dislocation_score(_dislocated(pct_off_52w_high=SEVERE_DRAWDOWN + 0.05))
    assert r.is_trap
    assert any("market knows something" in x for x in r.trap_reasons)


# --- Survival and the narrative gap -------------------------------------------

def test_buying_back_stock_into_the_crash_raises_survival():
    buying = dislocation_score(_dislocated(buyback_yield=0.06))
    issuing = dislocation_score(_dislocated(buyback_yield=0.0, sbc_yield=0.03))
    assert buying.survival > issuing.survival


def test_narrative_gap_rewards_cheap_against_own_history():
    cheap = dislocation_score(_dislocated(valuation_percentile_vs_history=5.0))
    normal = dislocation_score(_dislocated(valuation_percentile_vs_history=55.0))
    assert cheap.narrative_gap > normal.narrative_gap
    assert cheap.upside_to_normal > normal.upside_to_normal


def test_upside_to_normal_needs_no_heroics():
    """Multiple back to its own median plus delivered growth - nothing more."""
    r = dislocation_score(_dislocated(valuation_percentile_vs_history=10.0,
                                      demonstrated_growth=0.08))
    assert 0.40 < r.upside_to_normal < 1.20


# --- The regression this module was written for -------------------------------

def test_screen_buys_what_fable_refuses():
    """FABLE says AVOID because it fell; the screen says look closer."""
    s = _dislocated()
    signal, _reasons = entry_signal(s)
    assert signal == "AVOID"
    assert dislocation_score(s).score >= 55.0


# --- Universe behaviour --------------------------------------------------------

def test_screen_ranks_and_drops_traps_by_default():
    universe = [_dislocated(ticker="A", pct_off_52w_high=0.44),
                _dislocated(ticker="B", pct_off_52w_high=0.28),
                _trap(ticker="C"),
                _dislocated(ticker="D", pct_off_52w_high=0.05)]
    ranked = screen_dislocations(universe)
    assert [r.ticker for r in ranked] == ["A", "B"]
    assert [r.score for r in ranked] == sorted(
        (r.score for r in ranked), reverse=True)

    with_traps = screen_dislocations(universe, include_traps=True)
    assert "C" in [r.ticker for r in with_traps]


def test_sparse_snapshot_does_not_raise():
    r = dislocation_score(SecuritySnapshot(ticker="SPARSE",
                                           pct_off_52w_high=0.35))
    assert r is not None
    assert 0.0 <= r.score <= 100.0
