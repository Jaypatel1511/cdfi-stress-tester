"""
Generates a realistic 50-loan CDFI portfolio for testing and prototyping.
"""
from __future__ import annotations

import random
from typing import List

from cdfistress.data.schema import Loan

# Deterministic seed for reproducible sample data
_SEED = 42

_SECTORS = ["multifamily", "retail", "office", "industrial", "healthcare", "mixed_use"]
_STATES = ["CA", "TX", "NY", "IL", "FL", "OH", "GA", "NC", "CO", "WA"]


def generate_sample_portfolio(n: int = 50, seed: int = _SEED) -> List[Loan]:
    """Generate a synthetic CDFI loan portfolio.

    Parameters
    ----------
    n:
        Number of loans (default 50).
    seed:
        Random seed for reproducibility.

    Returns
    -------
    List of Loan objects with realistic CDFI-market parameters.
    """
    rng = random.Random(seed)
    loans = []

    for i in range(n):
        sector = rng.choice(_SECTORS)
        state = rng.choice(_STATES)

        # Balance range typical for a community development lender
        balance = rng.uniform(500_000, 8_000_000)

        # LTV: CDFI loans often 65–85%
        ltv = rng.uniform(0.65, 0.85)
        property_value = balance / ltv

        # NOI: yield on value roughly 6–9% for affordable/CRE
        noi_yield = rng.uniform(0.06, 0.09)
        noi = property_value * noi_yield

        # Interest rate: 5–8%
        interest_rate = rng.uniform(0.05, 0.08)
        debt_service = balance * (interest_rate + 0.02)   # I/O + amortization proxy

        loans.append(
            Loan(
                loan_id=f"CDFI-{i+1:04d}",
                borrower_name=f"Borrower {i+1}",
                outstanding_balance=round(balance, 2),
                noi=round(noi, 2),
                debt_service=round(debt_service, 2),
                property_value=round(property_value, 2),
                interest_rate=round(interest_rate, 4),
                sector=sector,
                state=state,
                ltv=round(ltv, 4),
            )
        )
    return loans
