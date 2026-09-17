"""Tests for the dislocation screen (tradingagents.analytics.dislocation).

The module exists to fix a specific failure: FABLE-5 and SKY reject a
stock *because* it fell, since the Behavior pillar scores momentum. So
these tests are written around one question - can the screen tell a
narrative dislocation apart from a value trap, when on the tape they
look identical?

Several of these assertions are the INVERSE of what v1 of this module
asserted. That is deliberate. v1 scored drawdown depth as the prize and
cheapness as the signature; run against 25 labelled 2025-26 crashes,
both turned out to be mildly anti-predictive (AUC 0.33 and 0.28). The
tests changed because the model was disconfirmed, and the old
expectations are named in comments where that happened.
"""

from __future__ import annotations

import pytest

from tradingagents.analytics import (
    DISLOCATION_CAPS,
    MIN_DRAWDOWN,
    MIN_COVERAGE,
    SEVERE_DRAWDOWN,
    SecuritySnapshot,
    dislocation_score,
    dislocation_stance,
    entry_signal,
    growth_deceleration,
    screen_dislocations,
)
from tradingagents.analytics import backtest as bt
from tradingagents.analytics.cases import labels, load_cases, realized_returns


def _dislocated(**overrides) -> SecuritySnapshot:
    """Down 40%; the numbers are still improving. Accenture-shaped."""
    base = dict(
        ticker="DISLOC",
        # trajectory: forward growth above trailing, margins holding,
        # cash converting - none of which a narrative can change
        margin_trend=0, revenue_cagr_3y=0.05, demonstrated_growth=0.08,
        fcf_to_net_income=1.15,
        # level of quality
        gross_profit_to_assets=0.38, roic=0.20, wacc=0.085,
        accruals_to_assets=0.02,
        gross_margin_stability=0.88, moat_evidence_count=3,
        net_debt_to_ebitda=0.4, interest_coverage=25.0,
        reinvestment_runway=True, insider_alignment=True,
        # the price: wrecked
        momentum_12_1_percentile=4.0, above_200dma=False,
        pct_off_52w_high=0.40, valuation_percentile_vs_history=8.0,
        earnings_yield=0.075, treasury_10y_yield=0.042,
        dividend_yield=0.022, buyback_yield=0.045, sbc_yield=0.012,
        has_defined_exit=True, adequately_liquid=True,
    )
    base.update(overrides)
    return SecuritySnapshot(**base)


def _trap(**overrides) -> SecuritySnapshot:
    """Also down 40% - but decelerating, with margins rolling over."""
    base = dict(
        ticker="TRAP",
        margin_trend=-1, revenue_cagr_3y=0.12, demonstrated_growth=0.03,
        fcf_to_net_income=0.70,
        gross_profit_to_assets=0.14, roic=0.05, wacc=0.09,
        accruals_to_assets=0.06,
        gross_margin_stability=0.45, moat_evidence_count=0,
        net_debt_to_ebitda=2.0, interest_coverage=8.0,
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


def test_deceleration_is_what_separates_them():
    """Forward growth below trailing growth is the single best separator."""
    assert growth_deceleration(_dislocated()) > 0
    assert growth_deceleration(_trap()) < 0

    accelerating = dislocation_score(
        _dislocated(revenue_cagr_3y=0.05, demonstrated_growth=0.12))
    decelerating = dislocation_score(
        _dislocated(revenue_cagr_3y=0.12, demonstrated_growth=0.05))
    assert accelerating.trajectory > decelerating.trajectory
    assert accelerating.score > decelerating.score


def test_reported_growth_is_no_defence():
    """CoStar grew revenue 18% while falling 51%; its bookings fell 26%."""
    costar_shaped = _dislocated(revenue_cagr_3y=0.18, demonstrated_growth=0.02,
                                margin_trend=-1)
    assert dislocation_score(costar_shaped).is_trap


def test_trajectory_ignores_the_price():
    """Momentum must not move the reading - that was the original bug."""
    wrecked = dislocation_score(_dislocated(
        momentum_12_1_percentile=1.0, above_200dma=False,
        relative_strength_on_down_days=False))
    calm = dislocation_score(_dislocated(
        momentum_12_1_percentile=60.0, above_200dma=True,
        relative_strength_on_down_days=True))
    assert wrecked.trajectory == calm.trajectory
    assert wrecked.intactness == calm.intactness
    assert wrecked.score == calm.score


# --- Drawdown is eligibility, NOT a scoring term -------------------------------

def test_depth_of_the_fall_does_not_move_the_score():
    """v1 scored depth as the prize. On the case set depth separated the
    labels at AUC 0.33 - it predicted traps. It is now eligibility only."""
    shallow = dislocation_score(_dislocated(pct_off_52w_high=0.27))
    deep = dislocation_score(_dislocated(pct_off_52w_high=0.62))
    assert shallow.score == deep.score


def test_cheapness_does_not_move_the_score_either():
    """Every crashed software name in 2026 was cheap; it carried no signal."""
    cheap = dislocation_score(_dislocated(valuation_percentile_vs_history=2.0))
    dear = dislocation_score(_dislocated(valuation_percentile_vs_history=45.0))
    assert cheap.score == dear.score
    assert cheap.narrative_gap > dear.narrative_gap      # still reported
    assert cheap.upside_to_normal > dear.upside_to_normal


def test_severe_drawdown_is_a_caution_not_a_veto():
    """v1 vetoed anything down >50%, which rejected ACN, NOW, UNH, CEG and
    TEAM - five of the six largest recoveries in the case set."""
    r = dislocation_score(_dislocated(pct_off_52w_high=SEVERE_DRAWDOWN + 0.11))
    assert not r.is_trap
    assert any("down >" in c for c in r.cautions)
    assert r.verdict in ("DISLOCATION", "PRIME DISLOCATION")


def test_returns_below_cost_of_capital_is_a_caution_not_a_veto():
    """In a crash ROIC is often at a cyclical trough; vetoing on it rejects
    exactly the names whose returns are about to recover."""
    r = dislocation_score(_dislocated(roic=0.06, wacc=0.09))
    assert any("cost of capital" in c for c in r.cautions)
    assert not r.is_trap


# --- Trap reasons --------------------------------------------------------------

def test_trap_reasons_are_specific_not_generic():
    r = dislocation_score(_trap())
    joined = " ".join(r.trap_reasons)
    assert "margins falling while growth decelerates" in joined


def test_negative_forward_growth_is_a_trap():
    """Novo Nordisk guided to a 5-13% sales DECLINE after a failed trial."""
    r = dislocation_score(_dislocated(demonstrated_growth=-0.05))
    assert r.is_trap
    assert "forward growth is negative" in r.trap_reasons


def test_leverage_still_vetoes_because_it_is_the_clock():
    r = dislocation_score(_dislocated(net_debt_to_ebitda=4.2))
    assert r.is_trap
    assert any("leverage" in x for x in r.trap_reasons)


# --- The regression this module was written for -------------------------------

def test_screen_buys_what_fable_refuses():
    """FABLE says AVOID because it fell; the screen says look closer."""
    s = _dislocated()
    signal, _reasons = entry_signal(s)
    assert signal == "AVOID"
    assert dislocation_score(s).score >= 55.0


# --- Backtest regression: the labelled 2025-26 cases ---------------------------
#
# These lock the measured result into CI. They are IN-SAMPLE - the weights
# were chosen after seeing these labels - so they are a floor against
# regression, not evidence the screen works.

def test_separates_the_labelled_cases_better_than_a_coin_flip():
    scores = {c["ticker"]: dislocation_score(s).score for c, s in load_cases()}
    r = bt.label_separation(scores, labels())
    assert r["auc"] >= 0.70, f"AUC regressed to {r['auc']}"
    assert r["gap_sd"] >= 1.0


def test_ranks_the_anchor_case_as_a_dislocation():
    """ACN is why this module exists. v1 called it a TRAP."""
    acn = next(s for c, s in load_cases() if c["ticker"] == "ACN")
    r = dislocation_score(acn)
    assert not r.is_trap
    assert r.verdict in ("DISLOCATION", "PRIME DISLOCATION")


def test_beats_the_momentum_aware_score_it_was_built_to_fix():
    from tradingagents.analytics import fable_score
    cases = load_cases()
    disloc = {c["ticker"]: dislocation_score(s).score for c, s in cases}
    fable = {c["ticker"]: fable_score(s).total for c, s in cases}
    lab = labels()
    assert bt.label_separation(disloc, lab)["auc"] > \
           bt.label_separation(fable, lab)["auc"] + 0.20


def test_score_correlates_with_what_actually_happened():
    scores = {c["ticker"]: dislocation_score(s).score for c, s in load_cases()}
    ic = bt.information_coefficient(scores, realized_returns())
    assert ic["ic"] > 2 * ic["stderr"], "IC is inside its own noise floor"


# --- Universe behaviour --------------------------------------------------------

def test_screen_ranks_and_drops_traps_by_default():
    universe = [_dislocated(ticker="A", demonstrated_growth=0.14),
                _dislocated(ticker="B", demonstrated_growth=0.06),
                _trap(ticker="C"),
                _dislocated(ticker="D", pct_off_52w_high=0.05)]
    ranked = screen_dislocations(universe)
    assert [r.ticker for r in ranked] == ["A", "B"]
    with_traps = screen_dislocations(universe, include_traps=True)
    assert "C" in [r.ticker for r in with_traps]


def test_sparse_snapshot_does_not_raise():
    r = dislocation_score(SecuritySnapshot(ticker="SPARSE",
                                           pct_off_52w_high=0.35))
    assert r is not None
    assert 0.0 <= r.score <= 100.0


# --- Stance: what the book actually does with the disagreement -----------------

def test_stance_buys_at_contrarian_size_and_in_tranches():
    st = dislocation_stance(_dislocated())
    assert st.action == "BUY_DISLOCATION"
    assert st.max_weight <= 0.08          # half of a normal high-conviction cap
    assert st.tranche_weight == pytest.approx(st.max_weight / 3, abs=1e-4)
    assert st.max_weight == DISLOCATION_CAPS[st.dislocation.verdict]


def test_stance_flags_the_disagreement_it_is_trading():
    st = dislocation_stance(_dislocated())
    assert st.fable_signal == "AVOID"
    assert st.disagreement is True
    assert any("disagreement" in r for r in st.reasons)


def test_stance_stands_aside_on_traps_and_gates():
    trap = dislocation_stance(_trap())
    assert trap.action == "STAND_ASIDE" and trap.max_weight == 0.0
    gated = dislocation_stance(_dislocated(mania_exposure=True))
    assert gated.action == "STAND_ASIDE"
    assert any("gate" in r for r in gated.reasons)


def test_stance_carries_a_written_falsifier():
    st = dislocation_stance(_dislocated())
    assert "trajectory breaks" in st.exit_rule
    assert "percentile" in st.exit_rule


def test_stance_silent_outside_a_drawdown():
    assert dislocation_stance(_dislocated(pct_off_52w_high=0.05)) is None


# --- Missing data must not masquerade as a verdict -----------------------------

def test_unsourced_forward_growth_yields_no_verdict():
    """The sweep-grade universe rarely carries forward growth. Scored
    without it, Nike reads as a PRIME DISLOCATION - and Nike is a
    labelled trap that scores 16 when the input is present."""
    blind = _dislocated(demonstrated_growth=None)
    r = dislocation_score(blind)
    assert r is not None
    assert not r.has_decisive_input
    assert r.verdict.startswith("INSUFFICIENT DATA")


def test_screen_drops_unscoreable_names_rather_than_ranking_them():
    universe = [_dislocated(ticker="FULL"),
                _dislocated(ticker="BLIND", demonstrated_growth=None)]
    assert [r.ticker for r in screen_dislocations(universe)] == ["FULL"]


def test_stance_stands_aside_on_missing_data_and_says_so():
    st = dislocation_stance(_dislocated(demonstrated_growth=None))
    assert st.action == "STAND_ASIDE"
    assert any("missing data, not a negative verdict" in r for r in st.reasons)


def test_coverage_is_reported_as_a_fraction():
    full = dislocation_score(_dislocated())
    assert full.coverage == pytest.approx(1.0)
    partial = dislocation_score(_dislocated(demonstrated_growth=None,
                                            fcf_to_net_income=None))
    assert partial.coverage < MIN_COVERAGE


def test_contracting_bookings_is_reported_but_unscored():
    """Bookings direction was the loudest trap signal in the research -
    CoStar grew revenue 18% while its bookings fell 26% - but the case
    set did not carry enough bookings figures to test it, so it is a
    caution and nothing more."""
    contracting = _dislocated(bookings_growth=-0.03)
    healthy = _dislocated(bookings_growth=0.14)
    assert dislocation_score(contracting).score == dislocation_score(healthy).score
    assert any("bookings" in c for c in dislocation_score(contracting).cautions)
    assert not any("bookings" in c for c in dislocation_score(healthy).cautions)
