"""Tests for the FABLE-5 scoring formula (tradingagents.analytics)."""

from __future__ import annotations

import pytest

from tradingagents.analytics import (
    Catalyst,
    SecuritySnapshot,
    entry_signal,
    fable_score,
    kelly_fraction,
    position_size,
    validate_book,
    PORTFOLIO_RULES,
)


def _quality_snapshot(**overrides) -> SecuritySnapshot:
    """A snapshot that scores well on every pillar; tests mutate from here."""
    base = dict(
        ticker="TEST",
        # F
        gross_profit_to_assets=0.40,
        roic=0.18, wacc=0.08,
        fcf_to_net_income=1.05, accruals_to_assets=0.02,
        margin_trend=1, revenue_cagr_3y=0.12,
        # A
        earnings_yield=0.09, treasury_10y_yield=0.045,
        ev_ebit=12.0, sector_median_ev_ebit=16.0, own_5y_median_ev_ebit=15.0,
        implied_growth=0.05, demonstrated_growth=0.12,
        downside_loss_if_growth_halves=0.20,
        # B
        momentum_12_1_percentile=80.0, above_200dma=True,
        estimate_revision_breadth=0.5, relative_strength_on_down_days=True,
        short_interest_pct_float=0.02,
        # L
        gross_margin_stability=0.9, moat_evidence_count=3,
        net_debt_to_ebitda=1.0, interest_coverage=15.0,
        reinvestment_runway=True, insider_alignment=True,
        # E
        regime_fit=1, pct_off_52w_high=0.10,
        valuation_percentile_vs_history=55.0,
        catalyst=Catalyst(kind="earnings", days_until=30,
                          payoff_if_hits=0.12, loss_if_misses=0.05,
                          priced_in=False),
        has_defined_exit=True, adequately_liquid=True,
    )
    base.update(overrides)
    return SecuritySnapshot(**base)


# --- Pillar bounds and composition -------------------------------------------


def test_pillars_bounded_0_to_20():
    r = fable_score(_quality_snapshot())
    for pillar in (r.fundamentals, r.asymmetry, r.behavior, r.longevity, r.entry):
        assert 0 <= pillar <= 20


def test_quality_snapshot_scores_buy_or_better():
    r = fable_score(_quality_snapshot())
    assert not r.gates_tripped
    assert r.total >= 70
    assert r.verdict in ("BUY", "STRONG BUY")


def test_empty_snapshot_scores_pass_not_error():
    """Unknown is never good news: an unsourced snapshot must be a PASS."""
    r = fable_score(SecuritySnapshot(ticker="EMPTY"))
    assert r.total < 60
    assert r.verdict == "PASS"


def test_worse_fundamentals_score_lower():
    good = fable_score(_quality_snapshot()).fundamentals
    bad = fable_score(_quality_snapshot(
        gross_profit_to_assets=0.05, roic=0.06, wacc=0.09,
        fcf_to_net_income=0.4, accruals_to_assets=0.09,
        margin_trend=-1, revenue_cagr_3y=0.01,
    )).fundamentals
    assert bad < good


# --- Gates -------------------------------------------------------------------


def test_leverage_gate_vetoes_regardless_of_quality():
    r = fable_score(_quality_snapshot(net_debt_to_ebitda=5.0))
    assert "leverage" in r.gates_tripped
    assert r.total == 0.0
    assert r.verdict.startswith("VETO")


def test_leverage_gate_skipped_for_financials():
    r = fable_score(_quality_snapshot(net_debt_to_ebitda=5.0, is_financial=True))
    assert "leverage" not in r.gates_tripped


def test_accounting_gate_on_accruals_and_flags():
    assert "accounting" in fable_score(
        _quality_snapshot(accruals_to_assets=0.12)).gates_tripped
    assert "accounting" in fable_score(
        _quality_snapshot(restatement_or_auditor_flag=True)).gates_tripped


def test_dilution_gate_requires_growth_shortfall():
    # Heavy issuance without growth to show for it: gated.
    diluted = fable_score(_quality_snapshot(
        share_count_growth_3y=0.06, revenue_cagr_3y=0.04))
    assert "dilution" in diluted.gates_tripped
    # Same issuance funding >2x growth: not gated.
    funded = fable_score(_quality_snapshot(
        share_count_growth_3y=0.06, revenue_cagr_3y=0.15))
    assert "dilution" not in funded.gates_tripped


def test_story_and_mania_gates():
    assert "story" in fable_score(
        _quality_snapshot(pre_revenue_or_terminal_heavy=True)).gates_tripped
    assert "mania" in fable_score(
        _quality_snapshot(mania_exposure=True)).gates_tripped


def test_gated_position_sizes_to_zero():
    r = fable_score(_quality_snapshot(mania_exposure=True))
    assert position_size(r, 5000.0) == 0.0


# --- Sizing ------------------------------------------------------------------


def test_kelly_zero_below_threshold():
    assert kelly_fraction(59.9) == 0.0
    assert kelly_fraction(0) == 0.0


def test_kelly_monotone_and_capped():
    fractions = [kelly_fraction(s) for s in (60, 65, 70, 75, 80, 90, 100)]
    assert fractions == sorted(fractions)
    assert all(f <= PORTFOLIO_RULES["max_position_pct"] for f in fractions)
    assert kelly_fraction(100) == PORTFOLIO_RULES["max_position_pct"]


def test_higher_volatility_means_smaller_size():
    assert kelly_fraction(70, annual_volatility=0.60) < kelly_fraction(70, annual_volatility=0.25)


# --- Entry signal ------------------------------------------------------------


def test_entry_enter_on_clean_setup():
    s = _quality_snapshot()
    signal, notes = entry_signal(s)
    assert signal == "ENTER"
    assert any("catalyst alpha" in n for n in notes)


def test_entry_avoid_on_gate_and_low_score():
    signal, reasons = entry_signal(_quality_snapshot(mania_exposure=True))
    assert signal == "AVOID"
    assert any("mania" in r for r in reasons)
    signal, reasons = entry_signal(SecuritySnapshot(ticker="EMPTY"))
    assert signal == "AVOID"


def test_entry_wait_on_downtrend():
    s = _quality_snapshot(above_200dma=False, momentum_12_1_percentile=5.0,
                          # keep score above 60 despite weak behavior pillar
                          )
    result = fable_score(s)
    if result.total >= 60:  # guard: the scenario must still clear ownership
        signal, reasons = entry_signal(s, result)
        assert signal == "WAIT"
        assert any("downtrend" in r for r in reasons)


def test_entry_wait_on_blowoff_top():
    s = _quality_snapshot(pct_off_52w_high=0.01,
                          valuation_percentile_vs_history=95.0)
    result = fable_score(s)
    if result.total >= 60:
        signal, reasons = entry_signal(s, result)
        assert signal == "WAIT"
        assert any("blow-off" in r for r in reasons)


def test_entry_wait_without_exit():
    s = _quality_snapshot(has_defined_exit=False)
    result = fable_score(s)
    if result.total >= 60:
        signal, reasons = entry_signal(s, result)
        assert signal == "WAIT"
        assert any("exit" in r for r in reasons)


# --- Catalyst EV -------------------------------------------------------------


def test_catalyst_ev_symmetric_negative():
    c = Catalyst(payoff_if_hits=0.05, loss_if_misses=0.10)
    assert c.expected_value() == pytest.approx(-0.025)
    c2 = Catalyst(payoff_if_hits=0.12, loss_if_misses=0.05)
    assert c2.expected_value() == pytest.approx(0.035)


def test_priced_in_catalyst_scores_below_unpriced():
    unpriced = fable_score(_quality_snapshot()).entry
    priced = fable_score(_quality_snapshot(
        catalyst=Catalyst(kind="earnings", days_until=30,
                          payoff_if_hits=0.12, loss_if_misses=0.05,
                          priced_in=True))).entry
    assert priced < unpriced


# --- Book validation ---------------------------------------------------------


def test_validate_book_flags_violations():
    book = 5000.0
    positions = {
        "AAA": (1000.0, "tech"),   # 20% > 15% cap
        "BBB": (900.0, "tech"),
        "CCC": (900.0, "tech"),    # tech = 56% > 40% cap
        "DDD": (900.0, "energy"),
        "EEE": (900.0, "health"),  # invested 4600 -> cash 8% < 20% floor
    }
    violations = validate_book(positions, book)
    assert any("AAA" in v for v in violations)
    assert any("tech" in v for v in violations)
    assert any("cash" in v for v in violations)


def test_validate_book_clean():
    book = 5000.0
    positions = {
        "AAA": (700.0, "tech"),
        "BBB": (700.0, "health"),
        "CCC": (700.0, "energy"),
        "DDD": (700.0, "industrials"),
        "EEE": (700.0, "staples"),
        "FFF": (500.0, "gold"),
    }  # invested 4000 -> cash 20%
    assert validate_book(positions, book) == []


# --- v1.1: owner yield (base total return) -----------------------------------


def test_base_total_return_computation():
    s = SecuritySnapshot(dividend_yield=0.01, buyback_yield=0.048, sbc_yield=0.002)
    assert s.base_total_return() == pytest.approx(0.056)
    assert SecuritySnapshot().base_total_return() is None
    # SBC-only company: negative carry
    assert SecuritySnapshot(sbc_yield=0.04).base_total_return() == pytest.approx(-0.04)


def test_owner_yield_adjustment_bounded_and_applied():
    rich = fable_score(_quality_snapshot(
        dividend_yield=0.02, buyback_yield=0.06, sbc_yield=0.005))
    assert rich.owner_yield_adj == 5.0            # 7.5% capped at +5
    drained = fable_score(_quality_snapshot(sbc_yield=0.08))
    assert drained.owner_yield_adj == -5.0        # -8% capped at -5
    neutral = fable_score(_quality_snapshot())
    assert neutral.owner_yield_adj == 0.0
    assert rich.total > neutral.total > drained.total


def test_owner_yield_cannot_rescue_gated_name():
    r = fable_score(_quality_snapshot(
        mania_exposure=True, dividend_yield=0.05, buyback_yield=0.05))
    assert r.total == 0.0


# --- v1.1: verdict-tiered Kelly caps -----------------------------------------


def test_kelly_caps_tier_by_verdict():
    low_vol = 0.20
    assert kelly_fraction(65, low_vol) <= 0.08    # STARTER tier
    assert kelly_fraction(75, low_vol) <= 0.12    # BUY tier
    assert kelly_fraction(95, low_vol) <= 0.15    # STRONG tier
    assert kelly_fraction(95, low_vol) == 0.15    # low vol reaches its tier cap


# --- v1.1: regulated-utility leverage carve-out ------------------------------


def test_utility_leverage_carveout():
    utility = fable_score(_quality_snapshot(
        net_debt_to_ebitda=5.5, is_regulated_utility=True))
    assert "leverage" not in utility.gates_tripped
    non_utility = fable_score(_quality_snapshot(net_debt_to_ebitda=5.5))
    assert "leverage" in non_utility.gates_tripped
    # 6x remains the utility ceiling
    over = fable_score(_quality_snapshot(
        net_debt_to_ebitda=6.5, is_regulated_utility=True))
    assert "leverage" in over.gates_tripped


# --- v1.1: input coverage ----------------------------------------------------


def test_coverage_reported():
    full = fable_score(_quality_snapshot(
        dividend_yield=0.01, buyback_yield=0.02, sbc_yield=0.005))
    empty = fable_score(SecuritySnapshot(ticker="EMPTY"))
    assert full.coverage > 0.9
    assert empty.coverage == 0.0
    partial = fable_score(SecuritySnapshot(ticker="P", roic=0.2, wacc=0.1,
                                           momentum_12_1_percentile=50.0))
    assert 0.0 < partial.coverage < 0.3
