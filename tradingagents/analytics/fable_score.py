"""FABLE-5: a five-pillar, five-gate security scoring formula.

Pillars (each 0-20, total 0-100):

    F  Fundamentals  - quality of the business's economics
    A  Asymmetry     - valuation as margin of safety, not as prediction
    B  Behavior      - momentum and crowd mechanics
    L  Longevity     - moat and balance-sheet survival
    E  Entry         - regime fit, catalyst, and exit discipline

Gates (any one tripped caps the total at 0, regardless of pillar sums):
leverage, accounting, dilution, story, mania. A high score must never be
able to argue its way past a disqualifier - every historical blow-up was
a high-conviction position whose one fatal flaw was outvoted by its many
virtues.

Evidence base per rule is cited inline. The intellectual sources, in the
order they shaped the design:

- Graham, "The Intelligent Investor" ch. 8 & 20: price is what you pay
  for a claim, margin of safety is the only defense against being wrong.
- Buffett shareholder letters: moats, "no called strikes", the
  distinction between a great company and a great stock.
- Fama & French (1992, 2015): value (HML), profitability (RMW), and
  investment factors carry persistent premia.
- Novy-Marx (2013): gross profitability predicts returns about as well
  as book-to-market, and works best combined with value.
- Piotroski (2000): simple accounting health separates winners from
  losers inside the cheap bucket.
- Sloan (1996): high accruals (earnings not backed by cash) predict
  underperformance - the market extrapolates paper earnings.
- Jegadeesh & Titman (1993): 12-month-minus-1 momentum persists;
  skipping the most recent month avoids short-term reversal.
- Thorp, "Fortune's Formula" context: Kelly sizing grows wealth fastest
  but estimation error makes full Kelly overbetting; fractional Kelly
  trades a little growth for a lot of survival.
- Marks, "The Most Important Thing": you cannot predict the cycle but
  you must know where you stand in it.
- Kindleberger, "Manias, Panics, and Crashes" / Minsky: every crisis is
  a credit story; stability breeds the leverage that ends it.
- Kahneman, "Thinking, Fast and Slow": your entry price is an anchor
  the market does not know about.
- Lefevre, "Reminiscences of a Stock Operator": the trend deserves
  respect; averaging down into a falling knife is how operators die.

The scorer is pure and I/O-free: callers (the LLM analyst layer or the
dataflows vendors) populate a ``SecuritySnapshot`` with whatever fields
they could source; every field is optional and a missing field simply
earns zero for its rule. That degrades conviction, not correctness -
unknown is never treated as good news.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------


@dataclass
class Catalyst:
    """A dated, tradeable reason for the market to re-rate the security.

    Catalyst alpha is the edge that comes from events with a date on
    them - earnings, FOMC decisions, product launches, regulatory
    rulings, capital-return announcements, index inclusions. The score
    rewards catalysts that are near, asymmetric, and not already priced:
    a catalyst everyone sees and has positioned for transfers no alpha
    (efficient-markets baseline); one with a defined date, a payoff
    larger than its miss-cost, and skeptical positioning around it is
    the classic special-situations setup (Greenblatt, "You Can Be a
    Stock Market Genius").
    """

    kind: str = "other"            # earnings | macro | product | regulatory | capital_return | corporate_action | other
    days_until: Optional[int] = None
    payoff_if_hits: Optional[float] = None   # est. upside, decimal (0.15 = +15%)
    loss_if_misses: Optional[float] = None   # est. downside, positive decimal
    priced_in: Optional[bool] = None         # is consensus already positioned for it?

    def expected_value(self, p_hit: float = 0.5) -> Optional[float]:
        """EV at an assumed hit probability (default coin-flip: the edge
        must come from asymmetric payoff, not from claiming forecast skill)."""
        if self.payoff_if_hits is None or self.loss_if_misses is None:
            return None
        return p_hit * self.payoff_if_hits - (1 - p_hit) * self.loss_if_misses


@dataclass
class SecuritySnapshot:
    """Everything the formula may consider about one security.

    All fields optional; ``None`` means "not sourced" and scores zero for
    the rules that need it. Ratios are decimals (0.15 == 15%) unless the
    name says otherwise.
    """

    ticker: str = ""

    # --- F: Fundamentals ---
    gross_profit_to_assets: Optional[float] = None   # Novy-Marx GP/A
    roic: Optional[float] = None                     # return on invested capital
    wacc: Optional[float] = None                     # cost of capital
    fcf_to_net_income: Optional[float] = None        # cash conversion
    accruals_to_assets: Optional[float] = None       # Sloan; lower is better
    margin_trend: Optional[int] = None               # +1 expanding / 0 flat / -1 contracting
    revenue_cagr_3y: Optional[float] = None          # nominal 3y revenue CAGR
    nominal_gdp_growth: float = 0.05                 # hurdle for growth durability

    # --- A: Asymmetry ---
    earnings_yield: Optional[float] = None           # fwd E/P
    treasury_10y_yield: Optional[float] = None       # risk-free comparator
    ev_ebit: Optional[float] = None                  # own multiple
    sector_median_ev_ebit: Optional[float] = None    # peer comparator
    own_5y_median_ev_ebit: Optional[float] = None    # history comparator
    implied_growth: Optional[float] = None           # reverse-DCF implied g
    demonstrated_growth: Optional[float] = None      # delivered g (e.g. 3-5y EPS CAGR)
    downside_loss_if_growth_halves: Optional[float] = None  # modeled drawdown, positive decimal

    # --- B: Behavior ---
    momentum_12_1_percentile: Optional[float] = None  # 0-100 vs universe
    above_200dma: Optional[bool] = None
    estimate_revision_breadth: Optional[float] = None  # -1..+1 (net up revisions)
    relative_strength_on_down_days: Optional[bool] = None
    short_interest_pct_float: Optional[float] = None   # crowding check

    # --- L: Longevity ---
    gross_margin_stability: Optional[float] = None   # 0-1; 1 = rock stable through cycles
    moat_evidence_count: Optional[int] = None        # 0-4: pricing power, switching costs, network, scale
    net_debt_to_ebitda: Optional[float] = None
    interest_coverage: Optional[float] = None        # EBIT / interest expense
    reinvestment_runway: Optional[bool] = None       # can deploy retained earnings at high ROIC
    insider_alignment: Optional[bool] = None         # ownership + buybacks below intrinsic value

    # --- E: Entry ---
    regime_fit: Optional[int] = None                 # -1 fights regime / 0 neutral / +1 aligned
    pct_off_52w_high: Optional[float] = None         # positive decimal, 0.10 = 10% below high
    valuation_percentile_vs_history: Optional[float] = None  # 0-100
    has_dated_catalyst: Optional[bool] = None     # coarse fallback when no Catalyst detail
    catalyst: Optional[Catalyst] = None           # preferred: typed catalyst detail
    has_defined_exit: Optional[bool] = None
    adequately_liquid: Optional[bool] = None

    # --- Owner yield (base total return) ---
    # "The gain or loss you get before the market moves": what the company
    # pays you (dividends), buys back for you (repurchases), and takes back
    # from you (stock-based compensation), each as a yield on market cap.
    dividend_yield: Optional[float] = None           # decimal, 0.012 = 1.2%
    buyback_yield: Optional[float] = None            # gross repurchases / market cap
    sbc_yield: Optional[float] = None                # SBC expense / market cap

    # --- Gates ---
    is_financial: bool = False                       # leverage gate not meaningful for banks
    is_regulated_utility: bool = False               # rate-base leverage is structural
    restatement_or_auditor_flag: bool = False
    share_count_growth_3y: Optional[float] = None    # annualized dilution
    pre_revenue_or_terminal_heavy: bool = False      # >80% of value in terminal assumptions
    mania_exposure: bool = False                     # majority revenue from a theme in
                                                     # "demanding evidence" phase, priced >2 sigma rich

    # --- Sizing ---
    annual_volatility: float = 0.30                  # for Kelly variance

    def base_total_return(self) -> Optional[float]:
        """Dividend + buyback - SBC, as a yield on market cap.

        The pre-appreciation return: what an owner collects (or silently
        loses) with the price standing still. A company paying 1% in
        dividends and retiring 4% of its shares while granting 0.5% in
        SBC hands its owner +4.5% before the market moves; a company
        granting 4% in SBC with no offset starts every year -4% behind.
        Buffett's "tolls between the business and its owner", made a
        number. Returns None when none of the three inputs was sourced.
        """
        parts = (self.dividend_yield, self.buyback_yield, self.sbc_yield)
        if all(x is None for x in parts):
            return None
        return ((self.dividend_yield or 0.0)
                + (self.buyback_yield or 0.0)
                - (self.sbc_yield or 0.0))


@dataclass
class FableResult:
    ticker: str
    fundamentals: float
    asymmetry: float
    behavior: float
    longevity: float
    entry: float
    owner_yield_adj: float = 0.0        # +/-5: base total return, 1pt per 1%
    base_total_return: Optional[float] = None
    coverage: float = 1.0               # fraction of scoreable inputs sourced
    gates_tripped: List[str] = field(default_factory=list)

    @property
    def total(self) -> float:
        """0 if any gate tripped - gates are vetoes, not deductions.

        Otherwise pillar sum plus the owner-yield adjustment (v1.1):
        base total return earns +/-1 point per 1% of yield, capped at
        +/-5, so carry can promote a borderline name or demote an
        SBC-heavy one, but can never outvote the pillars.
        """
        if self.gates_tripped:
            return 0.0
        raw = (self.fundamentals + self.asymmetry + self.behavior
               + self.longevity + self.entry + self.owner_yield_adj)
        return round(_clamp(raw, 0.0, 100.0), 1)

    @property
    def verdict(self) -> str:
        if self.gates_tripped:
            return f"VETO ({', '.join(self.gates_tripped)})"
        t = self.total
        if t >= 80:
            return "STRONG BUY"
        if t >= 70:
            return "BUY"
        if t >= 60:
            return "STARTER"
        return "PASS"


# ---------------------------------------------------------------------------
# Pillar scorers - each returns 0-20
# ---------------------------------------------------------------------------


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def score_fundamentals(s: SecuritySnapshot) -> float:
    """Quality: does the business earn real cash on its assets?

    Novy-Marx GP/A carries the load (0-6); ROIC spread over WACC (0-5)
    is the Buffett/Greenblatt compounding engine; cash conversion and
    low accruals (0-5) apply Sloan's finding that paper earnings revert;
    margin trend and durable growth take the rest.
    """
    pts = 0.0
    if s.gross_profit_to_assets is not None:
        # 0.33+ GP/A is roughly top-quartile US non-financials.
        pts += _clamp(s.gross_profit_to_assets / 0.33, 0, 1) * 6
    if s.roic is not None and s.wacc is not None:
        spread = s.roic - s.wacc
        pts += _clamp(spread / 0.10, 0, 1) * 5
    if s.fcf_to_net_income is not None and s.accruals_to_assets is not None:
        conv = _clamp((s.fcf_to_net_income - 0.5) / 0.5, 0, 1)      # 1.0x FCF/NI = full marks
        accr = _clamp(1 - s.accruals_to_assets / 0.10, 0, 1)        # 10%+ accruals = zero
        pts += (conv * 0.6 + accr * 0.4) * 5
    if s.margin_trend is not None:
        pts += {1: 2, 0: 1}.get(s.margin_trend, 0)
    if s.revenue_cagr_3y is not None:
        if s.revenue_cagr_3y > s.nominal_gdp_growth:
            pts += 2
    return round(_clamp(pts, 0, 20), 1)


def score_asymmetry(s: SecuritySnapshot) -> float:
    """Margin of safety: is being wrong survivable?

    Graham's earnings-yield-vs-bonds test modernized against the 10Y
    (0-6); relative and historical EV/EBIT (0-5); Mauboussin's
    expectations test - implied growth must be below demonstrated
    growth (0-5); and an explicit downside case (0-4). The pillar asks
    not "is it cheap" but "what happens to me if the bull case fails".
    """
    pts = 0.0
    if s.earnings_yield is not None and s.treasury_10y_yield is not None:
        # Full marks when earnings yield doubles the 10Y (Graham's 2x AAA rule).
        ratio = s.earnings_yield / max(s.treasury_10y_yield, 1e-9)
        pts += _clamp((ratio - 1.0) / 1.0, 0, 1) * 6
    if s.ev_ebit is not None:
        sub = 0.0
        if s.sector_median_ev_ebit:
            sub += _clamp((s.sector_median_ev_ebit - s.ev_ebit) / s.sector_median_ev_ebit + 0.5, 0, 1) * 0.5
        if s.own_5y_median_ev_ebit:
            sub += _clamp((s.own_5y_median_ev_ebit - s.ev_ebit) / s.own_5y_median_ev_ebit + 0.5, 0, 1) * 0.5
        pts += sub * 5
    if s.implied_growth is not None and s.demonstrated_growth is not None:
        # Paying for less growth than the company has already delivered.
        if s.implied_growth <= 0.75 * s.demonstrated_growth:
            pts += 5
        elif s.implied_growth <= s.demonstrated_growth:
            pts += 3
    if s.downside_loss_if_growth_halves is not None:
        pts += _clamp((0.50 - s.downside_loss_if_growth_halves) / 0.35, 0, 1) * 4
    return round(_clamp(pts, 0, 20), 1)


def score_behavior(s: SecuritySnapshot) -> float:
    """Crowd mechanics: is the tape agreeing, without being crowded?

    Jegadeesh-Titman 12-1 momentum (0-6) with the last month skipped;
    trend filter via the 200-day (0-4); estimate revision breadth as
    post-earnings drift proxy (0-4); relative strength on market down
    days - Livermore's tell for accumulation (0-3); and a crowding
    penalty check (0-3).
    """
    pts = 0.0
    if s.momentum_12_1_percentile is not None:
        pts += _clamp(s.momentum_12_1_percentile / 100.0, 0, 1) * 6
    if s.above_200dma is not None:
        pts += 4 if s.above_200dma else 0
    if s.estimate_revision_breadth is not None:
        pts += _clamp((s.estimate_revision_breadth + 1) / 2, 0, 1) * 4
    if s.relative_strength_on_down_days is not None:
        pts += 3 if s.relative_strength_on_down_days else 0
    if s.short_interest_pct_float is not None:
        # Moderate short interest (<5% float) = uncrowded both ways.
        pts += 3 if s.short_interest_pct_float < 0.05 else 1 if s.short_interest_pct_float < 0.10 else 0
    return round(_clamp(pts, 0, 20), 1)


def score_longevity(s: SecuritySnapshot) -> float:
    """Survival first: compounding only works on companies still alive.

    Moat evidence (0-8) per Buffett - gross margin stability through a
    cycle is the accounting fingerprint of pricing power; balance sheet
    (0-6) per Kindleberger - the panic's casualty list is always sorted
    by leverage; reinvestment runway (0-4); alignment (0-2).
    """
    pts = 0.0
    if s.moat_evidence_count is not None:
        pts += _clamp(s.moat_evidence_count / 4, 0, 1) * 5
    if s.gross_margin_stability is not None:
        pts += _clamp(s.gross_margin_stability, 0, 1) * 3
    bs = 0.0
    if s.net_debt_to_ebitda is not None:
        bs += _clamp((2.0 - s.net_debt_to_ebitda) / 2.0 + 0.5, 0, 1) * 0.5
    if s.interest_coverage is not None:
        bs += _clamp(s.interest_coverage / 12.0, 0, 1) * 0.5
    pts += bs * 6
    if s.reinvestment_runway is not None:
        pts += 4 if s.reinvestment_runway else 0
    if s.insider_alignment is not None:
        pts += 2 if s.insider_alignment else 0
    return round(_clamp(pts, 0, 20), 1)


def score_entry(s: SecuritySnapshot) -> float:
    """Context: right security, right regime, right structure.

    Regime fit (0-6) per Marks - a fine asset fighting the rate regime
    is still a fight; blow-off-top avoidance (0-5) per the Nifty Fifty
    and 1999 - parabolic price at peak valuation percentile scores zero;
    dated catalyst (0-5); exit and liquidity discipline (0-4).
    """
    pts = 0.0
    if s.regime_fit is not None:
        pts += {1: 6, 0: 3}.get(s.regime_fit, 0)
    if s.pct_off_52w_high is not None and s.valuation_percentile_vs_history is not None:
        at_high = s.pct_off_52w_high < 0.03
        at_peak_val = s.valuation_percentile_vs_history > 90
        if at_high and at_peak_val:
            pts += 0                                   # the blow-off-top configuration
        elif at_peak_val:
            pts += 1
        else:
            pts += _clamp(s.pct_off_52w_high / 0.15, 0, 1) * 3 + 2
    pts += _score_catalyst(s)
    if s.has_defined_exit is not None:
        pts += 2 if s.has_defined_exit else 0
    if s.adequately_liquid is not None:
        pts += 2 if s.adequately_liquid else 0
    return round(_clamp(pts, 0, 20), 1)


def _score_catalyst(s: SecuritySnapshot) -> float:
    """Catalyst alpha, 0-5.

    Typed catalyst detail beats the coarse boolean. Points require the
    catalyst to be (a) dated and near - within ~90 days it can anchor a
    position, beyond that it is a narrative; (b) asymmetric - EV at a
    coin-flip hit rate must be positive, so the edge is structural, not
    a forecast; (c) not fully priced - a consensus catalyst is a
    scheduled news event, not alpha.
    """
    c = s.catalyst
    if c is None:
        if s.has_dated_catalyst is not None:
            return 3.0 if s.has_dated_catalyst else 0.0
        return 0.0
    pts = 0.0
    if c.days_until is not None and 0 <= c.days_until <= 90:
        pts += 2.0 if c.days_until <= 45 else 1.0
    ev = c.expected_value()
    if ev is not None and ev > 0:
        pts += 2.0 if ev >= 0.03 else 1.0
    if c.priced_in is False:
        pts += 1.0
    return min(pts, 5.0)


def entry_signal(s: SecuritySnapshot, result: Optional[FableResult] = None):
    """When to enter: ENTER / WAIT / AVOID with the reasons spelled out.

    The rule set, in order of authority:

    1. Gates or score < 60      -> AVOID. No timing question exists for
       a security you should not own (Buffett: no called strikes).
    2. Trend disagreement       -> WAIT. Below the 200-day with bottom-
       decile momentum is knife-catching (Lefevre); the thesis may be
       right and early, which the market grades the same as wrong.
    3. Blow-off configuration   -> WAIT. At the 52-week high AND the
       >90th valuation percentile, the entry is what the Nifty Fifty
       and 1999 punished - wait for either price or time to correct it.
    4. No exit defined          -> WAIT. An entry without an exit is a
       position sized by hope (risk rules precede conviction).
    5. Otherwise                -> ENTER, sized by ``position_size``.
       A near, unpriced, asymmetric catalyst upgrades the note - enter
       before the date, never after the move.
    """
    result = result or fable_score(s)
    reasons: List[str] = []
    if result.gates_tripped:
        return "AVOID", [f"gate tripped: {g}" for g in result.gates_tripped]
    if result.total < 60:
        return "AVOID", [f"score {result.total} below ownership threshold 60"]

    if s.above_200dma is False and (
            s.momentum_12_1_percentile is not None and s.momentum_12_1_percentile < 10):
        reasons.append("downtrend: below 200dma with bottom-decile momentum")
    if (s.pct_off_52w_high is not None and s.pct_off_52w_high < 0.03
            and s.valuation_percentile_vs_history is not None
            and s.valuation_percentile_vs_history > 90):
        reasons.append("blow-off configuration: at 52w high and >90th valuation percentile")
    if s.has_defined_exit is False:
        reasons.append("no defined exit level")
    if reasons:
        return "WAIT", reasons

    notes = [f"score {result.total} ({result.verdict})"]
    c = s.catalyst
    if c is not None and c.days_until is not None and c.days_until <= 90:
        ev = c.expected_value()
        if (ev or 0) > 0 and c.priced_in is False:
            notes.append(
                f"catalyst alpha: {c.kind} in {c.days_until}d, EV {ev:+.1%} at coin-flip odds, not priced in")
        else:
            notes.append(f"catalyst: {c.kind} in {c.days_until}d")
    return "ENTER", notes


# ---------------------------------------------------------------------------
# Gates - vetoes that no pillar arithmetic can overcome
# ---------------------------------------------------------------------------


def check_gates(s: SecuritySnapshot) -> List[str]:
    """Return names of tripped gates.

    Each gate encodes one class of historical blow-up:

    - leverage:  Kindleberger/Minsky - crises are credit events; >4x
      net debt/EBITDA (non-financials) has no margin for a bad year.
    - accounting: Sloan at the extreme, plus Enron/Wirecard - accruals
      >10% of assets or restatement/auditor flags mean the numbers the
      other pillars scored may be fiction.
    - dilution:  >3%/yr share issuance without matching growth means
      shareholders are the product being sold.
    - story:     South Sea, 1999, SPACs - >80% of value in terminal
      assumptions is faith, not analysis.
    - mania:     Nifty Fifty - majority revenue from a theme currently
      in its "prove it" phase, priced >2 sigma above sector. A great
      company at a mania price is not a great stock.
    """
    tripped: List[str] = []
    if not s.is_financial and s.net_debt_to_ebitda is not None:
        # Regulated utilities carry rate-base leverage by design; the
        # survival question starts at ~6x for them, ~4x for everyone else.
        ceiling = 6.0 if s.is_regulated_utility else 4.0
        if s.net_debt_to_ebitda > ceiling:
            tripped.append("leverage")
    if s.restatement_or_auditor_flag or (
            s.accruals_to_assets is not None and s.accruals_to_assets > 0.10):
        tripped.append("accounting")
    if s.share_count_growth_3y is not None and s.share_count_growth_3y > 0.03:
        growth = s.revenue_cagr_3y or 0.0
        if growth < 2 * s.share_count_growth_3y:
            tripped.append("dilution")
    if s.pre_revenue_or_terminal_heavy:
        tripped.append("story")
    if s.mania_exposure:
        tripped.append("mania")
    return tripped


# ---------------------------------------------------------------------------
# Composite + sizing
# ---------------------------------------------------------------------------


#: Optional inputs that carry scoring weight; used for the coverage metric.
_SCOREABLE_FIELDS = (
    "gross_profit_to_assets", "roic", "fcf_to_net_income", "accruals_to_assets",
    "margin_trend", "revenue_cagr_3y", "earnings_yield", "ev_ebit",
    "implied_growth", "downside_loss_if_growth_halves",
    "momentum_12_1_percentile", "above_200dma", "estimate_revision_breadth",
    "relative_strength_on_down_days", "short_interest_pct_float",
    "gross_margin_stability", "moat_evidence_count", "net_debt_to_ebitda",
    "interest_coverage", "reinvestment_runway", "insider_alignment",
    "regime_fit", "pct_off_52w_high", "valuation_percentile_vs_history",
    "has_defined_exit", "adequately_liquid",
    "dividend_yield", "buyback_yield", "sbc_yield",
)


def input_coverage(s: SecuritySnapshot) -> float:
    """Fraction of scoreable inputs actually sourced (0-1).

    Because unknown fields score zero, a low-coverage snapshot is
    systematically haircut - correct for ranking within a uniformly
    sourced universe, but the absolute 60/70/80 thresholds assume high
    coverage. Interpret a 58 at 0.6 coverage as "insufficiently
    researched", not "researched and rejected".
    """
    sourced = sum(1 for f in _SCOREABLE_FIELDS if getattr(s, f) is not None)
    if s.catalyst is not None or s.has_dated_catalyst is not None:
        sourced += 1
    return round(sourced / (len(_SCOREABLE_FIELDS) + 1), 2)


def fable_score(s: SecuritySnapshot) -> FableResult:
    """Score a security. Gates are evaluated regardless of pillar scores."""
    btr = s.base_total_return()
    adj = _clamp(btr * 100.0, -5.0, 5.0) if btr is not None else 0.0
    return FableResult(
        ticker=s.ticker,
        fundamentals=score_fundamentals(s),
        asymmetry=score_asymmetry(s),
        behavior=score_behavior(s),
        longevity=score_longevity(s),
        entry=score_entry(s),
        owner_yield_adj=round(adj, 1),
        base_total_return=btr,
        coverage=input_coverage(s),
        gates_tripped=check_gates(s),
    )


def kelly_fraction(score: float, annual_volatility: float = 0.30) -> float:
    """Quarter-Kelly position fraction from a FABLE score.

    Edge heuristic: scores are centered so 55 is "no edge"; each point
    above adds 40bp of estimated annual excess return, giving a 10%
    edge estimate at a perfect 80+ conviction. Continuous Kelly is
    f* = mu / sigma^2; we take a quarter of it (Thorp: estimation error
    makes full Kelly overbetting) and cap by conviction tier (STARTER
    8%, BUY 12%, STRONG 15%) so no single estimate can dominate. Below 60 the fraction is zero -
    Buffett's "no called strikes": pass is always available.
    """
    if score < 60:
        return 0.0
    mu = (score - 55) * 0.004
    variance = max(annual_volatility, 0.05) ** 2
    f_star = mu / variance
    # v1.1: cap tiers by verdict so a low-volatility STARTER cannot reach
    # the full position cap - conviction, not just variance, earns size.
    cap = 0.08 if score < 70 else 0.12 if score < 80 else 0.15
    return round(min(f_star / 4, cap), 4)


def position_size(result: FableResult, book_value: float,
                  annual_volatility: float = 0.30) -> float:
    """Dollars to allocate for one security given the whole book's value."""
    if result.gates_tripped:
        return 0.0
    return round(book_value * kelly_fraction(result.total, annual_volatility), 2)


#: Book-level constraints. Sizing one name well does not make a book:
#: these are checked across positions.
PORTFOLIO_RULES = {
    "max_position_pct": 0.15,     # cap even for a perfect score
    "max_sector_pct": 0.40,       # no thesis deserves half the book
    "min_names_full_deploy": 6,   # diversification floor at full deployment
    "cash_floor_pct": 0.20,       # dry powder is a position (Marks)
    "per_name_stop_loss": 0.25,   # hard exit; thesis review, not averaging down
    "book_circuit_breaker": 0.30, # drawdown that halts the program for review
}


def validate_book(positions: dict, book_value: float) -> List[str]:
    """Check {ticker: (dollars, sector)} against PORTFOLIO_RULES.

    Returns a list of violations (empty = compliant). Cash is
    ``book_value`` minus the sum of position dollars.
    """
    violations: List[str] = []
    if not positions:
        return violations
    invested = sum(d for d, _ in positions.values())
    cash_pct = (book_value - invested) / book_value if book_value else 0
    if cash_pct < PORTFOLIO_RULES["cash_floor_pct"]:
        violations.append(
            f"cash {cash_pct:.0%} below floor {PORTFOLIO_RULES['cash_floor_pct']:.0%}")
    sectors: dict = {}
    for ticker, (dollars, sector) in positions.items():
        if book_value and dollars / book_value > PORTFOLIO_RULES["max_position_pct"]:
            violations.append(
                f"{ticker} {dollars / book_value:.0%} exceeds position cap "
                f"{PORTFOLIO_RULES['max_position_pct']:.0%}")
        sectors[sector] = sectors.get(sector, 0) + dollars
    for sector, dollars in sectors.items():
        if book_value and dollars / book_value > PORTFOLIO_RULES["max_sector_pct"]:
            violations.append(
                f"sector '{sector}' {dollars / book_value:.0%} exceeds cap "
                f"{PORTFOLIO_RULES['max_sector_pct']:.0%}")
    return violations
