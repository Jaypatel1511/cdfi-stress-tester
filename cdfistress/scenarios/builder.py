"""
Scenario construction helpers and per-loan shock application.
"""
from __future__ import annotations

from typing import Optional

from cdfistress.data.schema import (
    STANDARD_SCENARIOS,
    Loan,
    StressScenario,
)


def create_recession_scenario(
    noi_shock: float = -0.35,
    rate_shock: float = 0.0,
    property_value_shock: float = -0.40,
    default_rate_multiplier: float = 4.0,
) -> StressScenario:
    """Create a configurable recession scenario (defaults: 2008-style)."""
    return StressScenario(
        name="Custom Recession",
        noi_shock=noi_shock,
        rate_shock=rate_shock,
        property_value_shock=property_value_shock,
        default_rate_multiplier=default_rate_multiplier,
        severity="severe",
    )


def create_rate_shock_scenario(
    rate_shock: float = 0.03,
    property_value_shock: Optional[float] = None,
) -> StressScenario:
    """Create a rate-shock scenario.

    If property_value_shock is not provided, it is derived from the rate shock
    assuming a 5x cap-rate sensitivity (e.g. +300 bps → −20% value).
    """
    if property_value_shock is None:
        property_value_shock = -rate_shock * (20 / 3)  # rough cap-rate sensitivity

    severity: str
    if abs(rate_shock) >= 0.03:
        severity = "severe"
    elif abs(rate_shock) >= 0.015:
        severity = "moderate"
    else:
        severity = "mild"

    # Rate cuts lower default risk; rate hikes raise it.  Clamp to a safe minimum.
    multiplier = max(0.5, 1.5 + rate_shock * 10) if rate_shock >= 0 else max(0.5, 1.0 + rate_shock)
    return StressScenario(
        name=f"Rate Shock ({rate_shock*100:+.0f} bps)",
        noi_shock=-0.05,
        rate_shock=rate_shock,
        property_value_shock=property_value_shock,
        default_rate_multiplier=multiplier,
        severity=severity,
    )


def create_sector_specific_scenario(
    sector: str,
    noi_shock: float = -0.30,
    property_value_shock: float = -0.35,
) -> StressScenario:
    """Create a scenario targeting a specific asset sector."""
    return StressScenario(
        name=f"{sector.title()} Sector Stress",
        noi_shock=noi_shock,
        rate_shock=0.005,
        property_value_shock=property_value_shock,
        default_rate_multiplier=2.5,
        severity="moderate",
    )


def from_standard(key: str) -> StressScenario:
    """Build a StressScenario from the STANDARD_SCENARIOS library by key."""
    if key not in STANDARD_SCENARIOS:
        raise KeyError(f"Unknown scenario '{key}'. Available: {list(STANDARD_SCENARIOS)}")
    params = STANDARD_SCENARIOS[key]
    return StressScenario(**{k: v for k, v in params.items()})


def apply_shock_to_loan(loan: Loan, scenario: StressScenario) -> Loan:
    """Return a new Loan with macro shocks applied.

    Shocks are applied multiplicatively to NOI and property value;
    the rate shock shifts the interest rate additively.
    """
    stressed_noi = loan.noi * (1 + scenario.noi_shock)
    stressed_property = loan.property_value * (1 + scenario.property_value_shock)
    stressed_rate = max(0.0, loan.interest_rate + scenario.rate_shock)
    stressed_ds = loan.outstanding_balance * (stressed_rate + 0.02)

    return Loan(
        loan_id=loan.loan_id,
        borrower_name=loan.borrower_name,
        outstanding_balance=loan.outstanding_balance,
        noi=round(stressed_noi, 2),
        debt_service=round(stressed_ds, 2),
        property_value=round(stressed_property, 2),
        interest_rate=round(stressed_rate, 4),
        sector=loan.sector,
        state=loan.state,
        ltv=round(loan.outstanding_balance / stressed_property, 4)
        if stressed_property > 0 else loan.ltv,
    )
