"""
VaR, Conditional VaR (CVaR/ES), expected loss, and tail loss analytics.
"""
from __future__ import annotations

from typing import List

import numpy as np


def value_at_risk(losses: np.ndarray, confidence: float = 0.95) -> float:
    """VaR at a given confidence level.

    Parameters
    ----------
    losses:
        Array of portfolio loss values (one per simulation path).
    confidence:
        Confidence level (e.g. 0.95 for 95th percentile VaR).
    """
    if len(losses) == 0:
        raise ValueError("losses array must not be empty")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be in (0, 1)")
    return float(np.percentile(losses, confidence * 100))


def conditional_var(losses: np.ndarray, confidence: float = 0.95) -> float:
    """Conditional VaR (Expected Shortfall / CVaR) — mean loss beyond VaR.

    CVaR is a coherent risk measure and more informative than VaR alone
    for fat-tailed loss distributions.
    """
    if len(losses) == 0:
        raise ValueError("losses array must not be empty")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be in (0, 1)")
    var = value_at_risk(losses, confidence)
    tail_losses = losses[losses >= var]
    return float(np.mean(tail_losses)) if len(tail_losses) > 0 else var


def expected_loss(losses: np.ndarray) -> float:
    """Expected (mean) portfolio loss across all simulation paths."""
    if len(losses) == 0:
        raise ValueError("losses array must not be empty")
    return float(np.mean(losses))


def tail_loss(losses: np.ndarray, pct: float = 0.01) -> float:
    """Mean of the worst pct fraction of losses (e.g. worst 1%)."""
    if len(losses) == 0:
        raise ValueError("losses array must not be empty")
    if not 0 < pct < 1:
        raise ValueError("pct must be in (0, 1)")
    n_tail = max(1, int(len(losses) * pct))
    return float(np.mean(np.sort(losses)[-n_tail:]))
