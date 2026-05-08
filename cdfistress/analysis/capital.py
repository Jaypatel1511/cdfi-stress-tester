"""
Capital adequacy and Tier 1 buffer analysis under stress.
"""
from __future__ import annotations

import numpy as np
from typing import List

from cdfistress.analysis.var import conditional_var, expected_loss, value_at_risk


def capital_adequacy(available_capital: float, expected_loss_amount: float) -> float:
    """Capital adequacy ratio = available capital / expected loss.

    A ratio above 1.0 means the institution has adequate capital to cover
    expected losses.  Regulators typically require ≥1.5–2.0× for stress testing.
    """
    if expected_loss_amount <= 0:
        return float("inf")
    return available_capital / expected_loss_amount


def tier1_under_stress(
    tier1_capital: float,
    losses: np.ndarray,
    risk_weighted_assets: float,
    confidence: float = 0.99,
) -> float:
    """Tier 1 capital ratio after absorbing stressed losses at confidence level.

    Parameters
    ----------
    tier1_capital:
        Current Tier 1 capital in dollars.
    losses:
        Array of simulated portfolio losses.
    risk_weighted_assets:
        Total risk-weighted assets in dollars.
    confidence:
        VaR confidence level for the stress loss.
    """
    stressed_loss = value_at_risk(losses, confidence)
    residual_t1 = tier1_capital - stressed_loss
    if risk_weighted_assets <= 0:
        return 0.0
    return residual_t1 / risk_weighted_assets


def buffer_breach_count(
    losses: np.ndarray,
    capital_buffer: float,
) -> int:
    """Count simulation paths where portfolio losses exceed the capital buffer."""
    return int(np.sum(losses > capital_buffer))


def capital_adequacy_report(
    available_capital: float,
    losses: np.ndarray,
) -> dict:
    """Return a full capital adequacy summary dict."""
    el = expected_loss(losses)
    var95 = value_at_risk(losses, 0.95)
    var99 = value_at_risk(losses, 0.99)
    cvar99 = conditional_var(losses, 0.99)

    return {
        "available_capital": available_capital,
        "expected_loss": el,
        "var_95": var95,
        "var_99": var99,
        "cvar_99": cvar99,
        "car_vs_el": capital_adequacy(available_capital, el),
        "car_vs_var99": capital_adequacy(available_capital, var99),
        "car_vs_cvar99": capital_adequacy(available_capital, cvar99),
        "breaches": buffer_breach_count(losses, available_capital),
        "breach_rate": buffer_breach_count(losses, available_capital) / len(losses),
    }
