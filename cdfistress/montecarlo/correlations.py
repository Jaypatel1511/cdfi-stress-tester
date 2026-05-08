"""
Correlation matrix construction for Monte Carlo simulation.
"""
from __future__ import annotations

import numpy as np
from typing import Dict, Optional

from cdfistress.data.schema import CORRELATION_DEFAULTS


def build_correlation_matrix(
    noi_rate: float = CORRELATION_DEFAULTS["noi_rate"],
    noi_property: float = CORRELATION_DEFAULTS["noi_property"],
    rate_property: float = CORRELATION_DEFAULTS["rate_property"],
) -> np.ndarray:
    """Build a 3×3 correlation matrix for [NOI, Rate, PropertyValue] shocks.

    Parameters
    ----------
    noi_rate:
        Correlation between NOI shocks and interest rate shocks.
    noi_property:
        Correlation between NOI shocks and property value shocks.
    rate_property:
        Correlation between rate shocks and property value shocks.

    Returns
    -------
    3×3 numpy array (symmetric, diagonal = 1).
    """
    C = np.array([
        [1.0,        noi_rate,    noi_property],
        [noi_rate,   1.0,         rate_property],
        [noi_property, rate_property, 1.0],
    ])
    return C


def default_correlations() -> np.ndarray:
    """Return the default 3×3 correlation matrix using CORRELATION_DEFAULTS."""
    return build_correlation_matrix()


def is_positive_semidefinite(matrix: np.ndarray) -> bool:
    """Return True if the matrix is positive semi-definite (all eigenvalues ≥ 0)."""
    eigenvalues = np.linalg.eigvalsh(matrix)
    return bool(np.all(eigenvalues >= -1e-8))


def sector_correlation_boost(sector: str) -> float:
    """Return an intra-sector correlation multiplier for concentrated portfolios.

    Retail and office have higher intra-sector correlations than multifamily.
    """
    boosts = {
        "retail": 1.30,
        "office": 1.25,
        "industrial": 1.10,
        "healthcare": 1.05,
        "multifamily": 1.00,
        "mixed_use": 1.15,
    }
    return boosts.get(sector, 1.10)
