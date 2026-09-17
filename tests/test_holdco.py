"""Tests for the controlled-company sum-of-the-parts.

The module's job is to stop a sum-of-the-parts from flattering itself.
These tests pin the three ways that happens: valuing a stake at a price
nobody is offering, counting value the holder cannot reach, and calling
the whole gap mispricing.
"""

from __future__ import annotations

from datetime import date

import pytest

from tradingagents.analytics import Stake, SumOfParts, evidence_summary
from tradingagents.analytics.holdco import STALENESS_HALFLIFE_YEARS

TODAY = date(2026, 9, 17)


def _sop(**overrides) -> SumOfParts:
    base = dict(
        ticker="HOLD", market_cap=2_000e6, net_cash=300e6,
        operating_value=1_500e6, float_fraction=0.30, controlled=True,
        today=TODAY,
        stakes=[Stake(name="Fintech", ownership=0.10, asset_valuation=4_000e6,
                      evidence="marked", as_of=date(2026, 3, 1),
                      realizable=True, realization_note="secondary market exists")],
        catalysts=["announced secondary sale"],
    )
    base.update(overrides)
    return SumOfParts(**base)


# --- a stake is worth the evidence behind it ----------------------------------

def test_evidence_grade_haircuts_the_mark():
    marked = Stake("A", 0.10, 1_000e6, evidence="marked", as_of=TODAY)
    estimated = Stake("A", 0.10, 1_000e6, evidence="estimated", as_of=TODAY)
    assert marked.adjusted_value(TODAY) == pytest.approx(100e6)
    assert estimated.adjusted_value(TODAY) == pytest.approx(50e6)


def test_a_stale_mark_decays_toward_nothing():
    """A private round is a historical fact, not a current bid."""
    fresh = Stake("A", 0.10, 1_000e6, evidence="marked", as_of=TODAY)
    old = Stake("A", 0.10, 1_000e6, evidence="marked",
                as_of=date(TODAY.year - int(STALENESS_HALFLIFE_YEARS), 9, 17))
    assert old.adjusted_value(TODAY) == pytest.approx(
        fresh.adjusted_value(TODAY) * 0.5, rel=0.02)

    ancient = Stake("A", 0.10, 1_000e6, evidence="marked", as_of=date(2016, 9, 17))
    assert ancient.adjusted_value(TODAY) < fresh.adjusted_value(TODAY) * 0.15


def test_a_stake_with_no_valuation_is_never_silently_added():
    s = _sop(stakes=[Stake("Opaque", 0.25, None, evidence="estimated")])
    assert s.stake_value() == 0.0
    assert [u.name for u in s.unvalued_stakes()] == ["Opaque"]


def test_evidence_summary_exposes_a_sotp_built_on_guesses():
    s = _sop(stakes=[
        Stake("Real", 0.10, 1_000e6, evidence="marked", as_of=TODAY),
        Stake("Guess", 0.50, 1_800e6, evidence="estimated", as_of=TODAY)])
    mix = evidence_summary(s)
    assert mix["estimated"] > mix["marked"]     # most of the value is a view


# --- value you cannot reach ----------------------------------------------------

def test_realizable_only_excludes_what_the_holder_cannot_reach():
    s = _sop(stakes=[
        Stake("Sellable", 0.10, 2_000e6, evidence="marked", as_of=TODAY,
              realizable=True),
        Stake("Locked", 0.10, 2_000e6, evidence="marked", as_of=TODAY,
              realizable=False,
              realization_note="controlling shareholder decides; no dividend")])
    assert s.stake_value() == pytest.approx(400e6)
    assert s.stake_value(realizable_only=True) == pytest.approx(200e6)
    assert s.discount(realizable_only=True) < s.discount()


def test_the_realizable_discount_is_the_one_that_sizes_a_position():
    s = _sop(stakes=[Stake("Locked", 0.20, 5_000e6, evidence="marked",
                           as_of=TODAY, realizable=False)])
    headline = s.discount()
    honest = s.discount(realizable_only=True)
    assert headline > honest
    # the locked stake inflates the headline gap by a third or more
    assert headline - honest > 0.15


# --- the stub ------------------------------------------------------------------

def test_implied_stub_is_what_the_market_pays_for_the_business():
    """2000 market cap - 300 net cash - the stake, leaves the operations.
    The stake is a fresh mark, so no decay: 10% of 4,000 = 400."""
    s = _sop(stakes=[Stake("Fintech", 0.10, 4_000e6, evidence="marked",
                           as_of=TODAY, realizable=True)])
    assert s.stake_value() == pytest.approx(400e6)
    assert s.implied_stub() == pytest.approx(1_300e6)


def test_the_stub_widens_as_a_mark_ages():
    """Decay cuts the stake value, so the market looks like it is paying
    MORE for the operating business - which is the correct reading."""
    fresh = _sop(stakes=[Stake("F", 0.10, 4_000e6, evidence="marked",
                               as_of=TODAY, realizable=True)])
    stale = _sop(stakes=[Stake("F", 0.10, 4_000e6, evidence="marked",
                               as_of=date(2021, 9, 17), realizable=True)])
    assert stale.implied_stub() > fresh.implied_stub()


def test_a_negative_stub_is_a_warning_not_a_windfall():
    """When the stakes exceed the whole market cap, the marks are usually
    wrong - the module still reports it rather than clamping to zero."""
    s = _sop(market_cap=500e6,
             stakes=[Stake("Huge", 0.30, 6_000e6, evidence="marked", as_of=TODAY)])
    assert s.implied_stub() < 0


# --- the discount is mostly not mispricing -------------------------------------

def test_decomposition_subtracts_the_cost_of_the_structure_first():
    d = _sop().decompose_discount()
    assert d["control_block"] == 0.15
    assert d["thin_float"] > 0                       # 30% float is thin
    assert d["disposal_tax"] > 0
    assert d["residual"] == pytest.approx(d["headline"] - d["explained"], abs=1e-9)
    assert d["residual"] < d["headline"]


def test_an_uncontrolled_widely_held_company_carries_no_structural_discount():
    d = _sop(controlled=False, float_fraction=0.95).decompose_discount()
    assert d["control_block"] == 0.0
    assert d["thin_float"] == 0.0


def test_thinner_float_costs_more():
    thin = _sop(float_fraction=0.10).decompose_discount()["thin_float"]
    wider = _sop(float_fraction=0.35).decompose_discount()["thin_float"]
    assert thin > wider


# --- a discount without a catalyst is not a return -----------------------------

def test_no_catalyst_dominates_the_verdict():
    """A 60% discount can still be a 60% discount a decade later."""
    s = _sop(market_cap=800e6, catalysts=[])
    assert s.discount() > 0.5
    assert s.verdict().startswith("DISCOUNT WITHOUT A CATALYST")


def test_with_a_catalyst_the_verdict_reads_the_residual():
    wide = _sop(market_cap=800e6, catalysts=["tender offer announced"])
    assert wide.verdict() == "LARGE UNEXPLAINED DISCOUNT"
    fair = _sop(market_cap=1_950e6, catalysts=["buyback running"])
    assert fair.verdict() in ("DISCOUNT LARGELY EXPLAINED BY THE STRUCTURE",
                              "NO DISCOUNT ONCE THE STRUCTURE IS PRICED")


def test_no_operating_value_means_no_answer():
    s = _sop(operating_value=None)
    assert s.sotp() is None
    assert s.discount() is None
    assert s.verdict().startswith("CANNOT ASSESS")
