"""Sum-of-the-parts for a controlled company, and the anatomy of its discount.

Some companies trade below the arithmetic of their pieces. The usual
retail reading is that the market has missed something. The usual
correct reading is that the market has priced something the arithmetic
does not capture - and the whole analytical task is separating those two
cases.

This module refuses to produce a single "fair value". It produces four
numbers and makes the operator look at all of them:

    SOTP            the parts, added up, at stated valuations
    implied stub    market cap - stakes - net cash; what the market is
                    paying for the operating business, which is often
                    the number that makes the case rather than the SOTP
    discount        the gap, as a fraction of SOTP
    residual        the gap AFTER subtracting the parts of it that are
                    explainable. Only the residual is a claim about
                    mispricing; the rest is the cost of the structure.

THREE THINGS THAT MAKE A SOTP DISHONEST, AND HOW EACH IS HANDLED HERE.

1. VALUING A STAKE AT A PRICE NOBODY IS OFFERING. A private round from
   three years ago is a historical fact, not a current bid. Every stake
   carries an evidence grade and a valuation date, and stale marks are
   haircut toward nothing as they age. A stake with no third-party mark
   at all is reported separately and never silently added in.

2. COUNTING VALUE THE HOLDER CANNOT REACH. A minority shareholder owns
   a claim on a stake; the controlling shareholder decides whether it is
   ever sold, and whether the proceeds are distributed or redeployed.
   A stake with no realisation path is worth its dividend stream, which
   is frequently zero. ``realizable`` separates the two, and the
   realisable SOTP is the one that belongs in a position-sizing
   decision.

3. TREATING THE WHOLE DISCOUNT AS MISPRICING. Control blocks, thin
   floats and the tax due on a disposal are real costs borne by the
   minority holder. Empirically, closed-end funds and holding companies
   trade at persistent double-digit discounts for exactly these reasons
   without anything being wrong. ``decompose_discount`` subtracts the
   explainable components first, so that what remains is the actual
   claim being made - and it is usually much smaller than the headline.

WHAT THIS MODULE CANNOT TELL YOU. Whether the discount closes. A
persistent discount is only a return if something forces convergence -
a sale, a distribution, a spin, a buyback below intrinsic value, or a
change of control. Absent a catalyst, a 60% discount can be a 60%
discount a decade later, and the holder has earned the dividend and
nothing else. ``catalysts`` exists to make that argument explicit
rather than assumed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Sequence


# How much of a stated valuation survives, by the quality of the evidence.
# A priced third-party round is a fact; a broker's estimate is a view.
EVIDENCE_HAIRCUT = {
    "marked": 1.00,     # an observable arm's-length transaction in the asset
    "carried": 0.85,    # the company's own balance-sheet carrying value
    "reported": 0.70,   # credible press reporting of a round, not confirmed
    "estimated": 0.50,  # someone's model, including ours
}

# A private mark decays toward irrelevance. Roughly: a round is a strong
# signal for a year, a weak one at three, and archaeology at five.
STALENESS_HALFLIFE_YEARS = 3.0

# Typical explainable components of a holding-company discount. These are
# not tuned to any one name; they are the standing costs of the structure.
CONTROL_BLOCK_DISCOUNT = 0.15    # a minority stake in a controlled company
THIN_FLOAT_DISCOUNT = 0.08       # illiquidity, index exclusion, no coverage
DISPOSAL_TAX_RATE = 0.20         # tax due if a stake were actually sold


@dataclass
class Stake:
    """One piece of the sum, with the evidence behind its value."""

    name: str
    ownership: float                  # 0-1, the fraction owned
    asset_valuation: Optional[float]  # value of the WHOLE asset, not the stake
    evidence: str = "estimated"       # see EVIDENCE_HAIRCUT
    as_of: Optional[date] = None      # date of the valuation reference
    realizable: bool = False          # is there any path to cash for a minority holder?
    realization_note: str = ""
    dividend_stream: float = 0.0      # annual cash the stake actually pays out
    note: str = ""

    def gross_value(self) -> Optional[float]:
        if self.asset_valuation is None:
            return None
        return self.asset_valuation * self.ownership

    def staleness_factor(self, today: Optional[date] = None) -> float:
        """How much of a mark survives the passage of time."""
        if self.as_of is None:
            return EVIDENCE_HAIRCUT["estimated"] / EVIDENCE_HAIRCUT.get(
                self.evidence, 0.5)
        today = today or date.today()
        years = max(0.0, (today - self.as_of).days / 365.25)
        return 0.5 ** (years / STALENESS_HALFLIFE_YEARS)

    def adjusted_value(self, today: Optional[date] = None) -> Optional[float]:
        """Stake value after the evidence haircut and the staleness decay."""
        g = self.gross_value()
        if g is None:
            return None
        return g * EVIDENCE_HAIRCUT.get(self.evidence, 0.5) * self.staleness_factor(today)


@dataclass
class SumOfParts:
    ticker: str
    market_cap: float
    net_cash: float                       # negative for net debt
    operating_value: Optional[float]      # the core business, valued on its own
    stakes: List[Stake] = field(default_factory=list)
    float_fraction: Optional[float] = None    # shares genuinely tradable
    controlled: bool = True
    catalysts: List[str] = field(default_factory=list)
    today: Optional[date] = None

    # --- the four numbers -------------------------------------------------

    def stake_value(self, realizable_only: bool = False) -> float:
        total = 0.0
        for s in self.stakes:
            if realizable_only and not s.realizable:
                continue
            v = s.adjusted_value(self.today)
            if v is not None:
                total += v
        return total

    def unvalued_stakes(self) -> List[Stake]:
        """Assets with no usable valuation. Reported, never added in."""
        return [s for s in self.stakes if s.gross_value() is None]

    def sotp(self, realizable_only: bool = False) -> Optional[float]:
        if self.operating_value is None:
            return None
        return self.operating_value + self.net_cash + self.stake_value(realizable_only)

    def implied_stub(self) -> float:
        """What the market pays for the operating business.

        Market cap less net cash less the adjusted stakes. When this goes
        negative the market is valuing the core business at less than
        nothing, which is either the opportunity or a signal that the
        stake marks are wrong. It is usually the latter.
        """
        return self.market_cap - self.net_cash - self.stake_value()

    def discount(self, realizable_only: bool = False) -> Optional[float]:
        s = self.sotp(realizable_only)
        if s is None or s <= 0:
            return None
        return 1.0 - (self.market_cap / s)

    # --- the honest part --------------------------------------------------

    def decompose_discount(self) -> Optional[Dict[str, float]]:
        """Split the gap into what the structure costs and what is left.

        Only the residual is a claim about mispricing. Everything above
        it is the standing cost of owning a minority slice of a company
        somebody else controls, and it does not go away because the
        arithmetic is compelling.
        """
        d = self.discount()
        if d is None:
            return None
        parts: Dict[str, float] = {}
        parts["control_block"] = CONTROL_BLOCK_DISCOUNT if self.controlled else 0.0
        if self.float_fraction is not None and self.float_fraction < 0.40:
            # thinner float, larger penalty, capped at the standing figure
            parts["thin_float"] = THIN_FLOAT_DISCOUNT * min(
                1.0, (0.40 - self.float_fraction) / 0.30)
        else:
            parts["thin_float"] = 0.0
        sotp = self.sotp() or 0.0
        if sotp > 0:
            gain_at_risk = self.stake_value() / sotp
            parts["disposal_tax"] = gain_at_risk * DISPOSAL_TAX_RATE
        else:
            parts["disposal_tax"] = 0.0
        explained = sum(parts.values())
        parts["explained"] = explained
        parts["headline"] = d
        parts["residual"] = d - explained
        return {k: round(v, 4) for k, v in parts.items()}

    def verdict(self) -> str:
        d = self.decompose_discount()
        if d is None:
            return "CANNOT ASSESS - no operating value supplied"
        if not self.catalysts:
            return ("DISCOUNT WITHOUT A CATALYST - a gap that nothing forces "
                    "to close is not a return")
        r = d["residual"]
        if r >= 0.30:
            return "LARGE UNEXPLAINED DISCOUNT"
        if r >= 0.15:
            return "MODERATE UNEXPLAINED DISCOUNT"
        if r >= 0.0:
            return "DISCOUNT LARGELY EXPLAINED BY THE STRUCTURE"
        return "NO DISCOUNT ONCE THE STRUCTURE IS PRICED"


def evidence_summary(sop: SumOfParts) -> Dict[str, float]:
    """What share of the claimed stake value rests on what quality of evidence.

    A sum-of-the-parts where most of the value is 'estimated' is a
    restatement of the analyst's priors, not a valuation.
    """
    out: Dict[str, float] = {}
    total = 0.0
    for s in sop.stakes:
        v = s.adjusted_value(sop.today)
        if v is None:
            continue
        out[s.evidence] = out.get(s.evidence, 0.0) + v
        total += v
    if total <= 0:
        return {}
    return {k: round(v / total, 3) for k, v in sorted(out.items())}
