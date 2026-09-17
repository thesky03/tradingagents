"""Long-horizon compounding: what a 5x in a decade actually requires.

A score ranks. A probability hedges. Neither tells you the thing that
decides a decade-long hold, which is arithmetic: a 5x in ten years is
17.46% a year, every year, and that number has to come from somewhere.

    total return = (1 + owner_yield)^n x (1 + growth)^n x multiple_ratio

Fix the multiple at its own median - assume no re-rating help, because
over ten years the starting multiple's contribution decays toward
nothing and assuming otherwise is how a thesis becomes a wish - and the
equation solves for the only free term:

    required_growth = (target / (1+oy)^n / mult_ratio)^(1/n) - 1

That is the number to argue about. Everything else in this module exists
to put it next to what the company has actually done.

THE GAP IS THE THESIS. A name that needs 14% and has delivered 25% has
room to decelerate by eleven points and still get there. A name that
needs 18% and has delivered 8% is not a compounding candidate, it is a
hope with a spreadsheet. The sign and size of that gap says more than
any composite score, because it is falsifiable one quarter at a time.

WHY SIZE IS A SEPARATE CONSTRAINT. Growth rates do not care about market
capitalisation; outcomes do. A $3B company compounding at 18% becomes a
$15B company, which happens routinely. A $500B company doing the same
becomes $2.5T, which requires the world to rearrange itself around it.
The arithmetic is identical and the base rates are not, so headroom is
computed separately and reported next to the required growth rather
than blended into a single number that hides it.

BASE RATES, BECAUSE THE HONEST PRIOR IS LOW. Sustaining mid-teens
per-share growth for a full decade is rare - the large majority of
companies that have done it for five years do not do it for ten, and
the ones that do are concentrated in businesses with reinvestment
runway at high returns on capital. This module does not estimate that
base rate from data it does not have. It reports the required number,
the demonstrated number, and the headroom, and leaves the judgement
visible instead of burying it in a probability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from .fable_score import SecuritySnapshot, fable_score
from .horizon import NOMINAL_GDP, simulate_horizon


# A decade is long enough that the starting multiple stops mattering much
# and short enough that the business still has to do the work.
DEFAULT_YEARS = 10
DEFAULT_MULTIPLE = 5.0

# Above this, a required growth rate is being asked of a decade that
# almost nothing delivers. Not a veto - a label.
IMPLAUSIBLE_GROWTH = 0.22


def required_cagr(multiple: float, years: int = DEFAULT_YEARS) -> float:
    """The annual return a target multiple implies. 5x in 10y = 17.46%."""
    return multiple ** (1.0 / years) - 1.0


def required_growth(s: SecuritySnapshot, multiple: float = DEFAULT_MULTIPLE,
                    years: int = DEFAULT_YEARS,
                    multiple_ratio: float = 1.0) -> Optional[float]:
    """Per-share growth the business must deliver for the target multiple.

    ``multiple_ratio`` is what the valuation multiple does over the
    period; the default of 1.0 assumes no help from a re-rating, which
    is the assumption to argue against rather than the one to make
    quietly.
    """
    oy = s.base_total_return()
    if oy is None:
        return None
    oy = max(oy, -0.20)
    denom = ((1.0 + oy) ** years) * max(multiple_ratio, 0.2)
    if denom <= 0:
        return None
    return (multiple / denom) ** (1.0 / years) - 1.0


def demonstrated(s: SecuritySnapshot) -> Optional[float]:
    """The growth rate this company has actually put on the board."""
    if s.demonstrated_growth is not None:
        return s.demonstrated_growth
    return s.revenue_cagr_3y


def size_headroom(market_cap: float, multiple: float = DEFAULT_MULTIPLE,
                  tam: Optional[float] = None,
                  current_revenue: Optional[float] = None) -> dict:
    """Where the target multiple would put this company, and whether that fits.

    Reports the implied terminal market cap, and - when a total
    addressable market and current revenue are supplied - the share of
    that market the company would need. A candidate that must take 40%
    of its TAM to justify the target is making a different and much
    larger claim than one that needs 4%.
    """
    terminal = market_cap * multiple
    out = {"market_cap": market_cap, "terminal_cap": terminal}
    if tam and current_revenue and tam > 0:
        # Revenue is assumed to scale with the cap, which is conservative
        # in a margin-expansion story and aggressive in a de-rating one.
        out["implied_revenue"] = current_revenue * multiple
        out["implied_tam_share"] = min(1.0, current_revenue * multiple / tam)
        out["current_tam_share"] = min(1.0, current_revenue / tam)
    return out


@dataclass
class CompoundingCase:
    ticker: str
    years: int
    multiple: float
    required_cagr: float              # the whole-return hurdle
    required_growth: Optional[float]  # what the BUSINESS must do
    demonstrated_growth: Optional[float]
    gap: Optional[float]              # demonstrated - required; positive is room
    owner_yield: Optional[float]
    owner_yield_complete: bool
    p_hit: Optional[float] = None     # simulated P(reaching the multiple)
    reinvestment_runway: Optional[bool] = None
    roic_spread: Optional[float] = None
    headroom: dict = field(default_factory=dict)
    blockers: List[str] = field(default_factory=list)

    @property
    def verdict(self) -> str:
        if self.blockers:
            return f"BLOCKED ({', '.join(self.blockers)})"
        if self.gap is None:
            return "CANNOT ASSESS"
        if self.gap >= 0.06:
            return "ROOM TO DECELERATE"
        if self.gap >= 0.0:
            return "NEEDS CURRENT PACE HELD"
        if self.gap >= -0.05:
            return "NEEDS RE-ACCELERATION"
        return "REQUIRES A DIFFERENT COMPANY"


def _blockers(s: SecuritySnapshot, req_growth: Optional[float]) -> List[str]:
    """Reasons a decade-long compounding case does not start.

    These are structural, not valuation calls. A company that cannot
    reinvest at a return above its cost of capital cannot compound
    internally, whatever its multiple does, and a decade is long enough
    that leverage and dilution stop being details.
    """
    out: List[str] = []
    if s.roic is not None and s.wacc is not None and s.roic <= s.wacc:
        out.append("returns at or below cost of capital")
    if req_growth is not None and req_growth > IMPLAUSIBLE_GROWTH:
        out.append(f"needs >{IMPLAUSIBLE_GROWTH:.0%} growth for a decade")
    if s.share_count_growth_3y is not None and s.share_count_growth_3y > 0.03:
        out.append("share count growing >3%/yr - dilution eats the compounding")
    if s.net_debt_to_ebitda is not None and s.net_debt_to_ebitda > 4.0:
        out.append("leverage too high to survive one full cycle, let alone three")
    if fable_score(s).gates_tripped:
        out.append("FABLE gate tripped")
    return out


def compounding_case(s: SecuritySnapshot, multiple: float = DEFAULT_MULTIPLE,
                     years: int = DEFAULT_YEARS,
                     market_cap: Optional[float] = None,
                     tam: Optional[float] = None,
                     revenue: Optional[float] = None,
                     simulate: bool = True) -> CompoundingCase:
    """State the arithmetic of a target multiple, and what it would take."""
    req_g = required_growth(s, multiple, years)
    dem = demonstrated(s)
    gap = None if (req_g is None or dem is None) else dem - req_g

    p = None
    if simulate:
        r = simulate_horizon(s, years=years, target=multiple - 1.0, trials=12000)
        p = r.p_hit if r else None

    return CompoundingCase(
        ticker=s.ticker, years=years, multiple=multiple,
        required_cagr=round(required_cagr(multiple, years), 4),
        required_growth=None if req_g is None else round(req_g, 4),
        demonstrated_growth=None if dem is None else round(dem, 4),
        gap=None if gap is None else round(gap, 4),
        owner_yield=s.base_total_return(),
        owner_yield_complete=s.owner_yield_is_complete(),
        p_hit=p,
        reinvestment_runway=s.reinvestment_runway,
        roic_spread=(None if (s.roic is None or s.wacc is None)
                     else round(s.roic - s.wacc, 4)),
        headroom=(size_headroom(market_cap, multiple, tam, revenue)
                  if market_cap else {}),
        blockers=_blockers(s, req_g),
    )


def rank_compounders(universe: Sequence[SecuritySnapshot],
                     multiple: float = DEFAULT_MULTIPLE,
                     years: int = DEFAULT_YEARS,
                     require_room: bool = True) -> List[CompoundingCase]:
    """Rank by how much room a name has, not by how high it scores.

    Sorted on the gap between demonstrated and required growth, because
    that is the margin of safety in a compounding case: everything else
    can be right and a name that must accelerate to clear the bar is
    still relying on something that has not happened.
    """
    out: List[CompoundingCase] = []
    for s in universe:
        c = compounding_case(s, multiple, years, simulate=False)
        if c.blockers or c.gap is None:
            continue
        if require_room and c.gap < 0:
            continue
        out.append(c)
    out.sort(key=lambda c: -c.gap)
    return out
