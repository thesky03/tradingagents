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


# --- methods panel -----------------------------------------------------------


from tradingagents.analytics import methods


def _mini_universe():
    return [
        SecuritySnapshot(ticker="CHEAPGOOD", earnings_yield=0.09, roic=0.25,
                         momentum_12_1_percentile=40, annual_volatility=0.25,
                         revenue_cagr_3y=0.08, dividend_yield=0.02,
                         buyback_yield=0.03, sbc_yield=0.003,
                         valuation_percentile_vs_history=20.0,
                         gross_profit_to_assets=0.4, wacc=0.08,
                         fcf_to_net_income=1.0, gross_margin_stability=0.9,
                         net_debt_to_ebitda=1.0, pct_off_52w_high=0.15,
                         above_200dma=True),
        SecuritySnapshot(ticker="HOTMOMO", earnings_yield=0.02, roic=0.15,
                         momentum_12_1_percentile=95, annual_volatility=0.55,
                         revenue_cagr_3y=0.30, sbc_yield=0.03,
                         valuation_percentile_vs_history=90.0,
                         gross_profit_to_assets=0.3, wacc=0.09,
                         fcf_to_net_income=0.7, gross_margin_stability=0.6,
                         net_debt_to_ebitda=0.5, pct_off_52w_high=0.02,
                         above_200dma=True),
        SecuritySnapshot(ticker="BROKENVAL", earnings_yield=0.11, roic=0.10,
                         momentum_12_1_percentile=10, annual_volatility=0.30,
                         revenue_cagr_3y=0.00, dividend_yield=0.05,
                         buyback_yield=0.04, sbc_yield=0.002,
                         valuation_percentile_vs_history=5.0,
                         gross_profit_to_assets=0.2, wacc=0.08,
                         fcf_to_net_income=0.9, gross_margin_stability=0.8,
                         net_debt_to_ebitda=3.0, pct_off_52w_high=0.35,
                         above_200dma=False),
    ]


def test_momentum_favors_hot_and_penalizes_broken_trend():
    r = methods.momentum(_mini_universe())
    assert r["HOTMOMO"] > r["CHEAPGOOD"] > r["BROKENVAL"]
    # below-200dma haircut applied
    assert r["BROKENVAL"] < 50


def test_magic_formula_favors_cheap_and_good():
    r = methods.magic_formula(_mini_universe())
    assert r["CHEAPGOOD"] == max(r.values())


def test_expected_return_decomposition():
    u = _mini_universe()
    er = {s.ticker: methods.expected_return(s) for s in u}
    # CHEAPGOOD: btr 4.7% + growth 8% + cheap-multiple tailwind > 12%
    assert er["CHEAPGOOD"] > 0.12
    # HOTMOMO: -3% btr + 30% growth - rich-multiple drag, still high but lower than raw growth
    assert 0.20 < er["HOTMOMO"] < 0.30


def test_spearman_bounds_and_selfcorrelation():
    u = _mini_universe()
    m = methods.momentum(u)
    assert methods.spearman(m, m) == 1.0
    q = methods.quality(u)
    rho = methods.spearman(m, q)
    assert rho is None or -1.0 <= rho <= 1.0


def test_consensus_weighted_average():
    a = {"X": 100.0, "Y": 0.0}
    b = {"X": 0.0, "Y": 100.0}
    even = methods.consensus({"a": a, "b": b})
    assert even["X"] == even["Y"] == 50.0
    tilted = methods.consensus({"a": a, "b": b}, weights={"a": 3.0, "b": 1.0})
    assert tilted["X"] == 75.0 and tilted["Y"] == 25.0


# --- AOQ and QII (operator-directed methods) ---------------------------------


def test_aoq_rewards_asymmetry_not_level():
    base = dict(dividend_yield=0.0, buyback_yield=0.02, sbc_yield=0.0,
                revenue_cagr_3y=0.10, valuation_percentile_vs_history=50.0,
                annual_volatility=0.30)
    tight = SecuritySnapshot(ticker="TIGHT", downside_loss_if_growth_halves=0.10, **base)
    wide = SecuritySnapshot(ticker="WIDE", downside_loss_if_growth_halves=0.45, **base)
    assert methods.aoq(tight) > methods.aoq(wide)
    # positive catalyst EV improves the quotient; negative EV does not count
    c_good = SecuritySnapshot(ticker="C", downside_loss_if_growth_halves=0.10,
                              catalyst=Catalyst(payoff_if_hits=0.2, loss_if_misses=0.05), **base)
    c_bad = SecuritySnapshot(ticker="C2", downside_loss_if_growth_halves=0.10,
                             catalyst=Catalyst(payoff_if_hits=0.05, loss_if_misses=0.2), **base)
    assert methods.aoq(c_good) > methods.aoq(tight)
    assert methods.aoq(c_bad) == methods.aoq(tight)


def test_aoq_volatility_scales_downside_and_caps():
    base = dict(buyback_yield=0.05, revenue_cagr_3y=0.20,
                valuation_percentile_vs_history=20.0,
                downside_loss_if_growth_halves=0.10)
    calm = SecuritySnapshot(ticker="CALM", annual_volatility=0.20, **base)
    wild = SecuritySnapshot(ticker="WILD", annual_volatility=0.60, **base)
    assert methods.aoq(calm) > methods.aoq(wild)
    assert methods.aoq(calm) <= 5.0
    assert methods.aoq(SecuritySnapshot(ticker="NONE")) is None


def test_qii_scores_direction_of_change():
    improving = SecuritySnapshot(ticker="UP", margin_trend=1,
                                 estimate_revision_breadth=0.6,
                                 fcf_to_net_income=1.1,
                                 momentum_12_1_percentile=80.0,
                                 net_debt_to_ebitda=0.5, buyback_yield=0.04)
    deteriorating = SecuritySnapshot(ticker="DOWN", margin_trend=-1,
                                     estimate_revision_breadth=-0.6,
                                     fcf_to_net_income=0.5,
                                     momentum_12_1_percentile=15.0,
                                     net_debt_to_ebitda=3.5, sbc_yield=0.04)
    up, down = methods.qii(improving), methods.qii(deteriorating)
    assert up > 70 and down < 35 and 0 <= down < up <= 100
    assert methods.qii(SecuritySnapshot(ticker="NONE")) is None


# --- TRIAD composition --------------------------------------------------------


def test_triad_gates_and_threshold_are_absolute():
    d = methods.triad_decision(_quality_snapshot(
        mania_exposure=True, dividend_yield=0.05, buyback_yield=0.10))
    assert (d.own, d.size_fraction, d.signal) == (False, 0.0, "AVOID")
    d2 = methods.triad_decision(SecuritySnapshot(ticker="EMPTY"))
    assert not d2.own and d2.size_fraction == 0.0


def test_triad_aoq_scales_size_but_respects_caps():
    tight = methods.triad_decision(_quality_snapshot(
        downside_loss_if_growth_halves=0.10, dividend_yield=0.02,
        buyback_yield=0.05, revenue_cagr_3y=0.12))
    wide = methods.triad_decision(_quality_snapshot(
        downside_loss_if_growth_halves=0.45, sbc_yield=0.01))
    assert tight.own and wide.own
    assert tight.size_fraction >= wide.size_fraction
    cap = 0.15 if tight.fable_total >= 80 else 0.12 if tight.fable_total >= 70 else 0.08
    assert tight.size_fraction <= cap


def test_triad_qii_sets_stance_not_ownership():
    deteriorating = methods.triad_decision(_quality_snapshot(
        margin_trend=-1, estimate_revision_breadth=-0.8,
        momentum_12_1_percentile=30.0, fcf_to_net_income=0.6))
    if deteriorating.own:
        assert deteriorating.stance in ("HOLD", "NO_ADD")
    improving = methods.triad_decision(_quality_snapshot(
        dividend_yield=0.01, buyback_yield=0.04))
    assert improving.own and improving.stance == "ACCUMULATE"


def test_triad_wait_zeroes_size_but_keeps_ownership_verdict():
    s = _quality_snapshot(has_defined_exit=False)
    d = methods.triad_decision(s)
    if d.own and d.signal == "WAIT":
        assert d.size_fraction == 0.0


# --- Lifecycle: manage_position ----------------------------------------------


from tradingagents.analytics import PositionState, manage_position


def _pos(**kw):
    base = dict(ticker="TEST", entry_price=100.0, current_price=100.0,
                days_held=90, entry_fable=75.0, entry_val_percentile=50.0,
                adds_used=0, position_fraction=0.08)
    base.update(kw)
    return PositionState(**base)


def test_stop_is_absolute_even_when_thesis_intact():
    a = manage_position(_quality_snapshot(), _pos(current_price=74.0))
    assert a.action == "SELL" and a.fraction == 1.0
    assert any("stop" in r for r in a.rationale)


def test_thesis_decay_sells_in_profit_too():
    weak = _quality_snapshot(gross_profit_to_assets=0.05, roic=0.06,
                             earnings_yield=0.02, momentum_12_1_percentile=20.0,
                             moat_evidence_count=0, regime_fit=-1,
                             estimate_revision_breadth=-0.5, margin_trend=-1,
                             fcf_to_net_income=0.5, accruals_to_assets=0.08,
                             gross_margin_stability=0.3, above_200dma=False,
                             relative_strength_on_down_days=False,
                             implied_growth=0.15, demonstrated_growth=0.05,
                             downside_loss_if_growth_halves=0.45,
                             valuation_percentile_vs_history=92.0, catalyst=None,
                             reinvestment_runway=False, insider_alignment=False)
    a = manage_position(weak, _pos(current_price=130.0))
    assert a.action == "SELL"


def test_quiet_period_holds():
    a = manage_position(_quality_snapshot(), _pos(days_held=5, current_price=92.0))
    assert a.action == "HOLD"
    # but the stop still fires inside the quiet period
    a2 = manage_position(_quality_snapshot(), _pos(days_held=5, current_price=70.0))
    assert a2.action == "SELL"


def test_eat_fact_driven_loss():
    deteriorating = _quality_snapshot(margin_trend=-1, estimate_revision_breadth=-0.8,
                                      fcf_to_net_income=0.5, momentum_12_1_percentile=25.0,
                                      net_debt_to_ebitda=3.0, sbc_yield=0.03)
    a = manage_position(deteriorating, _pos(current_price=85.0))
    assert a.action == "SELL"
    assert any("eat it" in r for r in a.rationale)


def test_double_down_price_only_once():
    s = _quality_snapshot(dividend_yield=0.01, buyback_yield=0.03)
    a = manage_position(s, _pos(current_price=85.0, position_fraction=0.06))
    assert a.action == "ADD" and 0 < a.fraction <= 0.50
    # second add is refused
    a2 = manage_position(s, _pos(current_price=85.0, adds_used=1, position_fraction=0.06))
    assert a2.action == "HOLD"


def test_harvest_blowoff_and_trim_granted_gain():
    blow = _quality_snapshot(valuation_percentile_vs_history=95.0, pct_off_52w_high=0.01)
    a = manage_position(blow, _pos(current_price=150.0))
    assert a.action == "HARVEST" and a.fraction == 0.75
    granted = _quality_snapshot(valuation_percentile_vs_history=80.0,
                                estimate_revision_breadth=-0.2, margin_trend=0,
                                momentum_12_1_percentile=55.0, buyback_yield=0.0,
                                fcf_to_net_income=0.9)
    a2 = manage_position(granted, _pos(current_price=135.0, entry_val_percentile=50.0))
    assert a2.action == "TRIM" and a2.fraction in (0.33, 0.50)


def test_earned_gain_rides():
    earned = _quality_snapshot(valuation_percentile_vs_history=48.0,
                               dividend_yield=0.01, buyback_yield=0.03)
    a = manage_position(earned, _pos(current_price=140.0, entry_val_percentile=55.0))
    assert a.action == "RIDE"
    assert any("earned" in r for r in a.rationale)


# --- SKY composite -------------------------------------------------------------


from tradingagents.analytics import sky_scores
from tradingagents.analytics.sky import dcf_lens, lbo_lens, firepower_lens, precedents_lens


def test_sky_bounds_verdicts_and_gate_zero():
    u = [_quality_snapshot(ticker="GOOD", dividend_yield=0.02, buyback_yield=0.03),
         _quality_snapshot(ticker="GATED", mania_exposure=True),
         SecuritySnapshot(ticker="EMPTY")]
    res = sky_scores(u)
    assert 0 <= res["GOOD"].total <= 100 and res["GOOD"].verdict in (
        "GENERATIONAL", "CORE", "ACCUMULATE", "WATCH", "PASS")
    assert res["GATED"].total == 0.0 and res["GATED"].verdict.startswith("VETO")
    assert res["EMPTY"].coverage < res["GOOD"].coverage


def test_dcf_lens_monotone_in_cheapness():
    cheap = dcf_lens(_quality_snapshot(earnings_yield=0.10))
    rich = dcf_lens(_quality_snapshot(earnings_yield=0.03))
    assert cheap > rich
    assert dcf_lens(SecuritySnapshot(ticker="X")) is None


def test_lbo_lens_floor_logic():
    lbo_able = lbo_lens(_quality_snapshot(earnings_yield=0.09, fcf_to_net_income=1.0,
                                          net_debt_to_ebitda=0.5, gross_margin_stability=0.9))
    fragile = lbo_lens(_quality_snapshot(earnings_yield=0.03, fcf_to_net_income=0.6,
                                         net_debt_to_ebitda=4.0, gross_margin_stability=0.3))
    assert lbo_able > fragile
    assert lbo_lens(_quality_snapshot(is_financial=True)) is None
    assert lbo_lens(_quality_snapshot(is_regulated_utility=True)) is None


def test_precedents_lens_mania_scores_zero():
    assert precedents_lens(_quality_snapshot(mania_exposure=True)) == 0.0
    scarce_cheap = precedents_lens(_quality_snapshot(
        moat_evidence_count=4, valuation_percentile_vs_history=15.0))
    common_rich = precedents_lens(_quality_snapshot(
        moat_evidence_count=1, valuation_percentile_vs_history=90.0))
    assert scarce_cheap > common_rich


def test_firepower_rewards_dry_powder_and_will():
    loaded = firepower_lens(_quality_snapshot(net_debt_to_ebitda=-0.5,
                                              buyback_yield=0.06, dividend_yield=0.02))
    spent = firepower_lens(_quality_snapshot(net_debt_to_ebitda=2.9,
                                             sbc_yield=0.03, buyback_yield=0.0))
    assert loaded > spent


# --- Backtest harness ---------------------------------------------------------


import random as _random
from tradingagents.analytics import backtest as bt


def _mini_scoring_universe(n=30):
    rng = _random.Random(3)
    u = []
    for i in range(n):
        u.append(SecuritySnapshot(
            ticker=f"T{i:02d}",
            gross_profit_to_assets=rng.uniform(0.05, 0.5),
            roic=rng.uniform(0.04, 0.30), wacc=0.085,
            fcf_to_net_income=rng.uniform(0.4, 1.2),
            accruals_to_assets=rng.uniform(0.0, 0.08),
            margin_trend=rng.choice((-1, 0, 1)),
            revenue_cagr_3y=rng.uniform(-0.02, 0.35),
            earnings_yield=rng.uniform(0.01, 0.11), treasury_10y_yield=0.047,
            valuation_percentile_vs_history=rng.uniform(5, 95),
            implied_growth=rng.uniform(0.0, 0.25),
            demonstrated_growth=rng.uniform(0.0, 0.3),
            downside_loss_if_growth_halves=rng.uniform(0.12, 0.5),
            momentum_12_1_percentile=rng.uniform(0, 100),
            above_200dma=rng.random() > 0.3,
            gross_margin_stability=rng.uniform(0.3, 0.98),
            moat_evidence_count=rng.randint(0, 4),
            net_debt_to_ebitda=rng.uniform(-0.5, 3.5),
            interest_coverage=rng.uniform(3, 25),
            reinvestment_runway=rng.random() > 0.4,
            regime_fit=rng.choice((-1, 0, 1)),
            pct_off_52w_high=rng.uniform(0.0, 0.4),
            has_defined_exit=True, adequately_liquid=True,
            dividend_yield=rng.uniform(0, 0.05),
            buyback_yield=rng.uniform(0, 0.07),
            sbc_yield=rng.uniform(0, 0.04),
            annual_volatility=rng.uniform(0.18, 0.55),
        ))
    return u


def _sky_scorer(u):
    return {t: r.total for t, r in sky_scores(u).items()}


def test_structural_only_blanks_price_fields():
    s = _quality_snapshot()
    st = bt.structural_only(s)
    for f in bt.PRICE_DERIVED_FIELDS:
        assert getattr(st, f) is None
    # business characteristics survive
    assert st.gross_profit_to_assets == s.gross_profit_to_assets
    assert st.net_debt_to_ebitda == s.net_debt_to_ebitda


def test_perturb_moves_inputs_but_preserves_identity():
    rng = _random.Random(1)
    s = _quality_snapshot()
    p = bt.perturb(s, rng)
    assert p.ticker == s.ticker
    assert p.roic != s.roic
    # zero magnitude is (almost) a no-op on percentile fields' bounds
    p0 = bt.perturb(s, _random.Random(1), magnitude=0.0)
    assert p0.momentum_12_1_percentile == s.momentum_12_1_percentile


def test_rank_stability_reports_overlap_in_bounds():
    u = _mini_scoring_universe()
    res = bt.rank_stability(u, _sky_scorer, top_k=10, trials=15)
    assert 0.0 <= res["mean_topk_overlap"] <= 1.0
    assert -1.0 <= res["mean_rank_corr"] <= 1.0
    assert len(res["retention"]) == 10


def test_effective_independent_weight_groups_correlated_lenses():
    a = {f"T{i}": float(i) for i in range(20)}
    b = {f"T{i}": float(i) + 0.01 for i in range(20)}      # ~identical to a
    c = {f"T{i}": float(20 - i) for i in range(20)}        # inverted
    blocs = bt.effective_independent_weight(
        {"a": a, "b": b, "c": c}, {"a": 0.2, "b": 0.2, "c": 0.2})
    assert any("+" in k and abs(v - 0.4) < 1e-9 for k, v in blocs.items())


def test_information_coefficient_and_deciles():
    scores = {f"T{i}": float(i) for i in range(20)}
    rets = {f"T{i}": float(i) * 0.01 for i in range(20)}   # perfectly aligned
    ic = bt.information_coefficient(scores, rets)
    assert ic["ic"] == pytest.approx(1.0) and ic["n"] == 20
    assert bt.information_coefficient({"A": 1.0}, {"A": 0.1}) is None
    rows = bt.decile_table(scores, rets, buckets=4)
    assert len(rows) == 4
    assert rows[0]["mean_return"] < rows[-1]["mean_return"]


def test_regime_stress_returns_overlap_per_scenario():
    u = _mini_scoring_universe(20)
    res = bt.regime_stress(u, _sky_scorer,
                           {"rates_6pct": {"treasury_10y_yield": 0.06}}, top_k=8)
    assert 0.0 <= res["rates_6pct"]["topk_overlap"] <= 1.0


# --- v2 refinements -----------------------------------------------------------


from tradingagents.analytics import cyclically_adjusted_earnings_yield as caey
from tradingagents.analytics.sky import comps_lens


def test_caey_haircuts_unstable_earnings():
    stable = _quality_snapshot(earnings_yield=0.08, gross_margin_stability=1.0)
    cyclical = _quality_snapshot(earnings_yield=0.08, gross_margin_stability=0.35)
    assert caey(stable) == pytest.approx(0.08)
    assert caey(cyclical) < caey(stable)
    assert caey(SecuritySnapshot(ticker="X")) is None


def test_lbo_lens_no_longer_reads_cheapness():
    """v2: identical balance sheets must score identically regardless of price."""
    from tradingagents.analytics.sky import lbo_lens
    cheap = _quality_snapshot(earnings_yield=0.12, net_debt_to_ebitda=1.0,
                              fcf_to_net_income=1.0, gross_margin_stability=0.9)
    rich = _quality_snapshot(earnings_yield=0.02, net_debt_to_ebitda=1.0,
                             fcf_to_net_income=1.0, gross_margin_stability=0.9)
    assert lbo_lens(cheap) == lbo_lens(rich)


def test_comps_lens_is_peer_relative():
    """A cheap name in an expensive peer group beats a cheap name among peers."""
    rich_peers = [_quality_snapshot(ticker=f"R{i}", peer_group="rich",
                                    earnings_yield=0.02, gross_margin_stability=0.9)
                  for i in range(4)]
    cheap_peers = [_quality_snapshot(ticker=f"C{i}", peer_group="cheap",
                                     earnings_yield=0.10, gross_margin_stability=0.9)
                   for i in range(4)]
    standout = _quality_snapshot(ticker="STANDOUT", peer_group="rich",
                                 earnings_yield=0.06, gross_margin_stability=0.9)
    laggard = _quality_snapshot(ticker="LAGGARD", peer_group="cheap",
                                earnings_yield=0.06, gross_margin_stability=0.9)
    res = comps_lens(rich_peers + cheap_peers + [standout, laggard])
    # same absolute yield, opposite peer context -> opposite scores
    assert res["STANDOUT"] > res["LAGGARD"]


def test_generational_requires_coverage():
    from tradingagents.analytics import SkyResult
    thin = SkyResult("X", 85.0, coverage=0.60)
    full = SkyResult("Y", 85.0, coverage=1.0)
    assert thin.verdict == "CORE" and full.verdict == "GENERATIONAL"


def test_firepower_leads_on_deployment_not_balance_sheet():
    """v2.2: same balance sheet, different capital allocation -> different score."""
    from tradingagents.analytics.sky import firepower_lens
    deployer = _quality_snapshot(net_debt_to_ebitda=1.0, fcf_to_net_income=1.0,
                                 dividend_yield=0.02, buyback_yield=0.05,
                                 sbc_yield=0.003, reinvestment_runway=True)
    hoarder = _quality_snapshot(net_debt_to_ebitda=1.0, fcf_to_net_income=1.0,
                                dividend_yield=0.0, buyback_yield=0.0,
                                sbc_yield=0.03, reinvestment_runway=False)
    assert firepower_lens(deployer) - firepower_lens(hoarder) > 30
