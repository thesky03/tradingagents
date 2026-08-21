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
    kelly_fraction,
    position_size,
    validate_book,
    PORTFOLIO_RULES,
)

__all__ = [
    "Catalyst",
    "FableResult",
    "SecuritySnapshot",
    "entry_signal",
    "fable_score",
    "kelly_fraction",
    "position_size",
    "validate_book",
    "PORTFOLIO_RULES",
]
