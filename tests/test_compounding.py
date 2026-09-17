"""Tests for the long-horizon compounding arithmetic.

The module's claim is narrow and checkable: a target multiple implies a
required growth rate, and the gap between that and what the company has
delivered is the margin of safety. These tests pin the arithmetic and
the places it refuses to answer.
"""

from __future__ import annotations

import pytest

from tradingagents.analytics import (
    SecuritySnapshot,
    compounding_case,
    rank_compounders,
    required_cagr,
    required_growth,
    size_headroom,
)


def _compounder(**overrides) -> SecuritySnapshot:
    base = dict(
        ticker="COMP",
        roic=0.24, wacc=0.09, fcf_to_net_income=1.05, accruals_to_assets=0.02,
        margin_trend=1, revenue_cagr_3y=0.22, demonstrated_growth=0.22,
        gross_margin_stability=0.88, moat_evidence_count=3,
        net_debt_to_ebitda=0.3, interest_coverage=25.0,
        reinvestment_runway=True, insider_alignment=True,
        earnings_yield=0.04, treasury_10y_yield=0.042,
        momentum_12_1_percentile=60.0, above_200dma=True,
        pct_off_52w_high=0.12, valuation_percentile_vs_history=50.0,
        dividend_yield=0.0, buyback_yield=0.01, sbc_yield=0.02,
        annual_volatility=0.40, adequately_liquid=True, has_defined_exit=True,
    )
    base.update(overrides)
    return SecuritySnapshot(**base)


# --- the arithmetic ------------------------------------------------------------

def test_required_cagr_is_the_plain_arithmetic():
    assert required_cagr(5.0, 10) == pytest.approx(0.1746, abs=1e-4)
    assert required_cagr(5.0, 5) == pytest.approx(0.3797, abs=1e-4)
    assert required_cagr(10.0, 10) == pytest.approx(0.2589, abs=1e-4)


def test_owner_yield_lowers_the_growth_the_business_must_deliver():
    """Every point of owner yield is a point the operations need not find."""
    none_paid = _compounder(dividend_yield=0.0, buyback_yield=0.0, sbc_yield=0.0)
    pays = _compounder(dividend_yield=0.02, buyback_yield=0.03, sbc_yield=0.005)
    assert required_growth(pays) < required_growth(none_paid)
    # with no owner yield at all, the business must deliver the whole hurdle
    assert required_growth(none_paid) == pytest.approx(required_cagr(5.0, 10), abs=1e-4)


def test_negative_owner_yield_raises_the_bar():
    """SBC in excess of returns is a headwind the growth has to overcome."""
    dilutive = _compounder(dividend_yield=0.0, buyback_yield=0.0, sbc_yield=0.04)
    assert required_growth(dilutive) > required_cagr(5.0, 10)


def test_a_rerating_assumption_flatters_the_case():
    plain = required_growth(_compounder())
    helped = required_growth(_compounder(), multiple_ratio=1.5)
    assert helped < plain


def test_no_owner_yield_inputs_means_no_answer():
    bare = _compounder(dividend_yield=None, buyback_yield=None, sbc_yield=None)
    assert required_growth(bare) is None
    assert compounding_case(bare, simulate=False).verdict == "CANNOT ASSESS"


# --- the gap is the thesis -----------------------------------------------------

def test_gap_separates_room_from_hope():
    room = compounding_case(_compounder(demonstrated_growth=0.28), simulate=False)
    assert room.gap > 0.06
    assert room.verdict == "ROOM TO DECELERATE"

    hope = compounding_case(_compounder(demonstrated_growth=0.06), simulate=False)
    assert hope.gap < -0.05
    assert hope.verdict == "REQUIRES A DIFFERENT COMPANY"


def test_verdict_bands_are_ordered():
    seen = [compounding_case(_compounder(demonstrated_growth=g), simulate=False).verdict
            for g in (0.30, 0.19, 0.15, 0.05)]
    assert seen == ["ROOM TO DECELERATE", "NEEDS CURRENT PACE HELD",
                    "NEEDS RE-ACCELERATION", "REQUIRES A DIFFERENT COMPANY"]


# --- structural blockers -------------------------------------------------------

def test_returns_below_cost_of_capital_block_internal_compounding():
    c = compounding_case(_compounder(roic=0.07, wacc=0.09), simulate=False)
    assert "returns at or below cost of capital" in c.blockers
    assert c.verdict.startswith("BLOCKED")


def test_dilution_blocks_the_case():
    c = compounding_case(_compounder(share_count_growth_3y=0.05), simulate=False)
    assert any("dilution" in b for b in c.blockers)


def test_leverage_blocks_a_decade_long_hold():
    c = compounding_case(_compounder(net_debt_to_ebitda=4.5), simulate=False)
    assert any("leverage" in b for b in c.blockers)


def test_an_implausible_required_rate_is_labelled():
    """A 10x in ten years off a negative owner yield asks for too much."""
    c = compounding_case(_compounder(dividend_yield=0.0, buyback_yield=0.0,
                                     sbc_yield=0.05),
                         multiple=10.0, simulate=False)
    assert any("for a decade" in b for b in c.blockers)


# --- size is its own constraint ------------------------------------------------

def test_headroom_reports_where_the_target_lands():
    h = size_headroom(3.0e9, 5.0, tam=80.0e9, current_revenue=0.6e9)
    assert h["terminal_cap"] == pytest.approx(15.0e9)
    assert h["implied_tam_share"] == pytest.approx(0.0375, abs=1e-4)
    assert h["current_tam_share"] < h["implied_tam_share"]


def test_headroom_share_is_capped_at_the_whole_market():
    h = size_headroom(50.0e9, 5.0, tam=10.0e9, current_revenue=8.0e9)
    assert h["implied_tam_share"] == 1.0


def test_headroom_omits_share_without_a_tam():
    h = size_headroom(3.0e9, 5.0)
    assert "implied_tam_share" not in h


# --- ranking -------------------------------------------------------------------

def test_ranking_sorts_on_room_not_on_score():
    # this snapshot's owner yield is NEGATIVE (1% buyback against 2% SBC), so
    # the business must beat the 17.5% headline hurdle, not match it - 18%
    # demonstrated growth is not enough and is deliberately not in this list.
    u = [_compounder(ticker="WIDE", demonstrated_growth=0.30),
         _compounder(ticker="TIGHT", demonstrated_growth=0.21),
         _compounder(ticker="SHORT", demonstrated_growth=0.04),
         _compounder(ticker="GATED", mania_exposure=True)]
    ranked = rank_compounders(u)
    assert [c.ticker for c in ranked] == ["WIDE", "TIGHT"]
    assert ranked[0].gap > ranked[1].gap


def test_a_negative_owner_yield_makes_eighteen_percent_insufficient():
    """The headline hurdle is 17.5%, but SBC in excess of buybacks raises it -
    an 18% grower with a -1% owner yield still falls short."""
    c = compounding_case(_compounder(demonstrated_growth=0.18), simulate=False)
    assert c.owner_yield < 0
    assert c.required_growth > 0.1746
    assert c.gap < 0


def test_ranking_can_include_names_that_must_reaccelerate():
    u = [_compounder(ticker="WIDE", demonstrated_growth=0.30),
         _compounder(ticker="SHORT", demonstrated_growth=0.10)]
    assert len(rank_compounders(u, require_room=False)) == 2
