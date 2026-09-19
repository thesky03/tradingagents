"""Position lifecycle: the complete path from screen to exit.

The front half of the methodology (screen -> gate -> enter -> size) lives
in fable_score.py and methods.py. This module is the back half: what to
do with a position you already own, as facts and price move.

The central principle - the answer to every P&L question is "decompose
WHY":

  A gain is either EARNED (the business grew into the price; multiple
  flat or lower) or GRANTED (the market re-rated the multiple; nothing
  fundamental changed). Earned gains ride - selling a compounder because
  it is up is how the great trades get amputated (the momentum
  literature and every Buffett letter agree on little else but this).
  Granted gains get partially returned to cash - a re-rating pulls
  forward returns the business has not produced yet.

  A loss is either PRICE-ONLY (facts intact, the market is offering the
  same asset cheaper) or FACT-DRIVEN (the score fell with the price).
  Price-only losses in names whose score HELD are the only permitted
  double-downs, once, in size, above the stop. Fact-driven losses are
  eaten immediately - averaging down into deterioration is the single
  most reliable account-killer in market history (Livermore's rule;
  every blown-up value fund's post-mortem).

Authority order is inherited from the Triad and never inverted:
gates/score decide if the name may be owned at all; hard risk rails
(stop, first-days quiet period) bind before any opportunistic rule;
tax status (short vs long-term, this being a taxable account) shifts
thresholds but never overrides risk.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .fable_score import SecuritySnapshot, fable_score, PORTFOLIO_RULES
from .methods import qii


# Rails and thresholds (all overridable at call sites via PositionState
# where noted; module constants are the doctrine's defaults).
STOP_LOSS = PORTFOLIO_RULES["per_name_stop_loss"]     # -25%: absolute
QUIET_DAYS = 14            # no discretionary action in the first two weeks
LT_DAYS = 365              # long-term capital-gains threshold (taxable acct)
BLOWOFF_GAIN = 0.40        # parabolic harvest arms above +40%...
RERATE_TRIM_GAIN = 0.30    # ...re-rating trim arms above +30%
RERATE_PTS = 25.0          # valuation percentile rise that counts as "granted"
DD_WINDOW = (-0.20, -0.10) # double-down window: between -20% and -10%
DD_MAX_FRACTION = 0.50     # an add may be at most half the original position


@dataclass
class PositionState:
    """What we know about an open position, independent of the market's
    current opinion (which arrives via a fresh SecuritySnapshot)."""

    ticker: str
    entry_price: float
    current_price: float
    days_held: int
    entry_fable: float                 # score on the day of entry
    entry_val_percentile: Optional[float] = None   # valuation pct at entry
    adds_used: int = 0                 # double-downs already taken (max 1)
    position_fraction: float = 0.0     # current % of book

    @property
    def pnl(self) -> float:
        return self.current_price / self.entry_price - 1.0

    @property
    def is_long_term(self) -> bool:
        return self.days_held >= LT_DAYS


@dataclass
class Action:
    ticker: str
    action: str        # HOLD | RIDE | TRIM | HARVEST | ADD | SELL
    fraction: float    # of the CURRENT position: sell/trim fraction, or
                       # add size as a fraction of the ORIGINAL position
    rationale: List[str] = field(default_factory=list)


def manage_position(s: SecuritySnapshot, p: PositionState) -> Action:
    """One open position + fresh facts -> one instruction.

    Decision order (first match wins; risk before opportunity):

    1. STOP        pnl <= -25%: SELL all. No rule below may see a
                   position that has hit the stop; this is why the stop
                   exists. Never average down through it.
    2. GATE/DECAY  a gate tripped, or FABLE < 60 on fresh facts: SELL
                   all, in profit or loss alike - the reason to own it
                   is gone, the P&L is history's business.
    3. QUIET       first 14 days: HOLD unless (1) or (2) fired. New
                   positions do not get managed into noise.
    -- loss side --
    4. EAT IT      loss > 10% AND (QII < 35 or FABLE fell 8+ points
                   from entry): SELL. The loss is fact-driven; the
                   market found something. Tax note: short-term losses
                   are the one thing this account harvests eagerly.
    5. DOUBLE DOWN loss in [-20%, -10%], FABLE >= entry score, QII >=
                   50, trend not in freefall, no add used yet: ADD up
                   to 50% of the original position (respecting the tier
                   cap). Price-only weakness in an improving name is
                   the market's gift; it is offered once.
    -- gain side --
    6. HARVEST     blow-off configuration (>=90th valuation percentile
                   within 3% of the high) with gain >= 40%: SELL 75%,
                   keep a runner. Parabolas retrace; the tax bill on a
                   short-term parabolic gain is the cheapest insurance
                   sold anywhere.
    7. TRIM        gain >= 30% AND granted by re-rating (valuation
                   percentile up 25+ points since entry) AND stance is
                   not ACCUMULATE: TRIM 33% (50% if also short-term
                   stance NO_ADD). Return the market's gift; keep the
                   business.
    8. RIDE        gain of any size that the business EARNED (multiple
                   flat/down while price rose, QII >= 50): explicit
                   instruction to do nothing, recorded - so that doing
                   nothing is a decision, not a default. Approaching
                   long-term status (>300 days held, short of 365)
                   raises the bar for any sale to "stop or gate only".
    9. HOLD        everything else.
    """
    r = fable_score(s)
    q = qii(s)
    q = 50.0 if q is None else q
    why: List[str] = []
    pnl = p.pnl

    # 1. Stop - absolute.
    if pnl <= -STOP_LOSS:
        return Action(p.ticker, "SELL", 1.0,
                      [f"stop: {pnl:.1%} through -{STOP_LOSS:.0%}. No averaging through stops - ever."])

    # 2. Gate / thesis decay - absolute.
    if r.gates_tripped:
        return Action(p.ticker, "SELL", 1.0,
                      [f"gate tripped on fresh facts: {', '.join(r.gates_tripped)}"])
    if r.total < 60:
        return Action(p.ticker, "SELL", 1.0,
                      [f"FABLE decayed to {r.total} (<60): the reason to own it is gone",
                       f"entry score was {p.entry_fable}; P&L {pnl:+.1%} is irrelevant to this rule"])

    # 3. Quiet period.
    if p.days_held < QUIET_DAYS:
        return Action(p.ticker, "HOLD", 0.0,
                      [f"day {p.days_held}: quiet period - new positions are not managed into noise"])

    # ---- loss side ----
    if pnl < 0:
        fact_driven = q < 35 or (r.total <= p.entry_fable - 8)
        if pnl <= -0.10 and fact_driven:
            return Action(p.ticker, "SELL", 1.0,
                          [f"eat it: {pnl:.1%} with deterioration (QII {q}, FABLE {r.total} vs {p.entry_fable} at entry)",
                           "fact-driven loss; short-term loss harvest is a tax asset in this account"])
        in_window = DD_WINDOW[0] <= pnl <= DD_WINDOW[1]
        trend_ok = not (s.above_200dma is False and (s.momentum_12_1_percentile or 50) < 10)
        if (in_window and p.adds_used == 0 and r.total >= p.entry_fable
                and q >= 50 and trend_ok):
            room = max(0.0, (0.15 if r.total >= 80 else 0.12 if r.total >= 70 else 0.08)
                       - p.position_fraction)
            add = min(DD_MAX_FRACTION, room / max(p.position_fraction, 1e-9))
            if add > 0.05:
                return Action(p.ticker, "ADD", round(add, 2),
                              [f"double down (once): {pnl:.1%} is price-only - FABLE {r.total} >= {p.entry_fable} at entry, QII {q}",
                               f"add {add:.0%} of original position; stop remains at -{STOP_LOSS:.0%} from ORIGINAL entry"])
        return Action(p.ticker, "HOLD", 0.0,
                      [f"loss {pnl:.1%} but thesis intact (FABLE {r.total}, QII {q}); no add signal"])

    # ---- gain side ----
    granted = (p.entry_val_percentile is not None
               and s.valuation_percentile_vs_history is not None
               and s.valuation_percentile_vs_history - p.entry_val_percentile >= RERATE_PTS)
    blowoff = ((s.valuation_percentile_vs_history or 0) >= 90
               and (s.pct_off_52w_high if s.pct_off_52w_high is not None else 1) < 0.03)

    if blowoff and pnl >= BLOWOFF_GAIN:
        return Action(p.ticker, "HARVEST", 0.75,
                      [f"blow-off: +{pnl:.0%} at >=90th valuation percentile within 3% of the high",
                       "sell 75%, keep a runner; the tax bill is cheap insurance against the retrace"])

    if pnl >= RERATE_TRIM_GAIN and granted:
        stance_accumulate = q >= 65
        if not stance_accumulate:
            frac = 0.50 if (q < 35 and not p.is_long_term) else 0.33
            note = ("short-term tax accepted: deteriorating stance overrides tax preference"
                    if not p.is_long_term else "long-term rate applies; trim is cheap")
            return Action(p.ticker, "TRIM", frac,
                          [f"granted gain: +{pnl:.0%} with valuation percentile up "
                           f"{s.valuation_percentile_vs_history - p.entry_val_percentile:.0f} pts since entry",
                           f"the re-rating pulled returns forward; QII {q} says don't reinvest the market's gift here",
                           note])

    if pnl > 0 and not granted and q >= 50:
        near_lt = 300 <= p.days_held < LT_DAYS
        why = [f"earned gain: +{pnl:.0%} with the multiple flat/down - the business grew into the price",
               f"QII {q}: ride it; selling compounders because they are up is how great trades get amputated"]
        if near_lt:
            why.append(f"day {p.days_held}: long-term tax status in {LT_DAYS - p.days_held} days - "
                       "bar for any sale rises to stop-or-gate-only")
        return Action(p.ticker, "RIDE", 0.0, why)

    return Action(p.ticker, "HOLD", 0.0,
                  [f"P&L {pnl:+.1%}, FABLE {r.total}, QII {q}: no rule fires; holding is the decision"])
