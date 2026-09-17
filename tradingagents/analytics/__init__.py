"""Quantitative scoring layer: priors distilled from market history.

Complements the experience-based memory log (agents/utils/memory.py):
the memory log learns from this account's own closed trades; this module
encodes the base rates the account has not lived through yet.
"""

from .fable_score import (
    Catalyst,
    FableResult,
    SecuritySnapshot,
    entry_signal,
    fable_score,
    input_coverage,
    kelly_fraction,
    position_size,
    validate_book,
    PORTFOLIO_RULES,
)
from . import methods
from .lifecycle import Action, PositionState, manage_position
from .sky import (SkyResult, sky_scores, cyclically_adjusted_earnings_yield,
                  value_conviction_multiplier, rate_pressure_lens,
                  equity_duration)
from . import backtest
from .horizon import HorizonResult, simulate_horizon, rank_by_odds
from .holdco import (Stake, SumOfParts, evidence_summary,
                     EVIDENCE_HAIRCUT, CONTROL_BLOCK_DISCOUNT)
from .compounding import (CompoundingCase, compounding_case, rank_compounders,
                          required_cagr, required_growth, size_headroom)
from .dislocation import (DislocationResult, DislocationStance,
                          dislocation_score, dislocation_stance,
                          screen_dislocations, growth_deceleration,
                          MIN_DRAWDOWN, SEVERE_DRAWDOWN, MIN_COVERAGE,
                          DISLOCATION_CAPS)

__all__ = [
    "Catalyst",
    "FableResult",
    "SecuritySnapshot",
    "entry_signal",
    "fable_score",
    "input_coverage",
    "kelly_fraction",
    "position_size",
    "validate_book",
    "PORTFOLIO_RULES",
    "methods",
    "Action",
    "PositionState",
    "manage_position",
    "SkyResult",
    "sky_scores",
    "cyclically_adjusted_earnings_yield",
    "value_conviction_multiplier",
    "rate_pressure_lens",
    "equity_duration",
    "backtest",
    "HorizonResult",
    "simulate_horizon",
    "rank_by_odds",
    "CompoundingCase",
    "compounding_case",
    "rank_compounders",
    "required_cagr",
    "required_growth",
    "size_headroom",
    "Stake",
    "SumOfParts",
    "evidence_summary",
    "EVIDENCE_HAIRCUT",
    "CONTROL_BLOCK_DISCOUNT",
    "DislocationResult",
    "DislocationStance",
    "dislocation_score",
    "dislocation_stance",
    "screen_dislocations",
    "growth_deceleration",
    "MIN_DRAWDOWN",
    "SEVERE_DRAWDOWN",
    "MIN_COVERAGE",
    "DISLOCATION_CAPS",
]
