"""
CDFI stress-testing data structures, standard scenarios, and correlation defaults.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional


# ---------------------------------------------------------------------------
# Standard CDFI Fund stress scenario definitions
# ---------------------------------------------------------------------------
STANDARD_SCENARIOS: Dict[str, dict] = {
    "2008_recession": {
        "name": "2008-Style Recession",
        "noi_shock": -0.35,              # NOI drops 35%
        "rate_shock": 0.0,               # rates compressed to floor
        "property_value_shock": -0.40,   # CRE values down 40%
        "default_rate_multiplier": 4.0,  # 4× baseline default rate
        "severity": "severe",
    },
    "covid_shock": {
        "name": "COVID-Style Demand Shock",
        "noi_shock": -0.25,
        "rate_shock": -0.01,             # emergency rate cuts
        "property_value_shock": -0.15,
        "default_rate_multiplier": 2.5,
        "severity": "moderate",
    },
    "rate_spike": {
        "name": "Rate Spike (+300 bps)",
        "noi_shock": -0.05,              # modest NOI impact
        "rate_shock": 0.03,              # 300 bps rate rise
        "property_value_shock": -0.20,   # cap rate expansion
        "default_rate_multiplier": 1.8,
        "severity": "moderate",
    },
    "regional_cre_crash": {
        "name": "Regional CRE Crash",
        "noi_shock": -0.20,
        "rate_shock": 0.01,
        "property_value_shock": -0.50,   # local market collapse
        "default_rate_multiplier": 3.0,
        "severity": "severe",
    },
    "mild_downturn": {
        "name": "Mild Cyclical Downturn",
        "noi_shock": -0.10,
        "rate_shock": 0.005,
        "property_value_shock": -0.08,
        "default_rate_multiplier": 1.4,
        "severity": "mild",
    },
}

# Default pairwise correlations between risk factors
CORRELATION_DEFAULTS: Dict[str, float] = {
    "noi_rate": -0.30,            # NOI and rates negatively correlated
    "noi_property": 0.70,         # NOI and property values highly correlated
    "rate_property": -0.60,       # rates and property values negatively correlated
}

# Sector-level default rate baseline (annual probability)
SECTOR_DEFAULT_RATES: Dict[str, float] = {
    "retail": 0.04,
    "office": 0.03,
    "multifamily": 0.015,
    "industrial": 0.02,
    "healthcare": 0.025,
    "mixed_use": 0.03,
    "other": 0.035,
}

SEVERITY_LEVELS = ["mild", "moderate", "severe"]


@dataclass
class StressScenario:
    """A named stress scenario with macro shocks.

    Parameters
    ----------
    name:
        Human-readable scenario name.
    noi_shock:
        Fractional change in NOI (e.g. -0.35 = 35% decline).
    rate_shock:
        Absolute change in interest rate (e.g. 0.03 = +300 bps).
    property_value_shock:
        Fractional change in collateral value (e.g. -0.40 = 40% decline).
    default_rate_multiplier:
        Multiplier applied to baseline sector default rates.
    severity:
        One of 'mild', 'moderate', 'severe'.
    """
    name: str
    noi_shock: float
    rate_shock: float
    property_value_shock: float
    default_rate_multiplier: float
    severity: Literal["mild", "moderate", "severe"]

    def __post_init__(self) -> None:
        if self.severity not in SEVERITY_LEVELS:
            raise ValueError(f"severity must be one of {SEVERITY_LEVELS}")
        if self.default_rate_multiplier <= 0:
            raise ValueError("default_rate_multiplier must be positive")

    def summary(self) -> str:
        return (
            f"Scenario: {self.name} [{self.severity}]\n"
            f"  NOI shock        : {self.noi_shock:+.1%}\n"
            f"  Rate shock       : {self.rate_shock:+.0f} bps\n"
            f"  Property shock   : {self.property_value_shock:+.1%}\n"
            f"  Default mult     : {self.default_rate_multiplier:.1f}x"
        )


@dataclass
class Loan:
    """A single loan in the CDFI portfolio.

    Parameters
    ----------
    loan_id:
        Unique identifier.
    borrower_name:
        Name of the borrower.
    outstanding_balance:
        Current outstanding principal in dollars.
    noi:
        Net Operating Income of the underlying project ($).
    debt_service:
        Annual debt service payment ($).
    property_value:
        Appraised collateral value ($).
    interest_rate:
        Current loan interest rate (decimal).
    sector:
        Asset sector (e.g. 'multifamily', 'retail').
    state:
        US state code.
    ltv:
        Loan-to-value ratio at origination.
    """
    loan_id: str
    borrower_name: str
    outstanding_balance: float
    noi: float
    debt_service: float
    property_value: float
    interest_rate: float
    sector: str
    state: str
    ltv: float

    @property
    def dscr(self) -> float:
        """Debt service coverage ratio."""
        return self.noi / self.debt_service if self.debt_service > 0 else float("inf")

    @property
    def is_stressed(self) -> bool:
        """True if DSCR < 1.0 (loan is not covering debt service)."""
        return self.dscr < 1.0


@dataclass
class StressResult:
    """Result from a single scenario or simulation run.

    Parameters
    ----------
    scenario:
        The scenario that was applied.
    expected_loss:
        Mean portfolio loss across simulations ($).
    var_95:
        Value-at-Risk at 95th percentile ($).
    var_99:
        Value-at-Risk at 99th percentile ($).
    capital_adequacy_ratio:
        Available capital / expected loss (>1 = adequate).
    num_breaches:
        Number of simulations where losses exceed available capital.
    """
    scenario: StressScenario
    expected_loss: float
    var_95: float
    var_99: float
    capital_adequacy_ratio: float
    num_breaches: int
    total_simulations: int = 1000

    def summary(self) -> str:
        lines = [
            f"=== Stress Result: {self.scenario.name} ===",
            f"  Expected loss        : ${self.expected_loss:,.0f}",
            f"  VaR (95%)            : ${self.var_95:,.0f}",
            f"  VaR (99%)            : ${self.var_99:,.0f}",
            f"  Capital adequacy     : {self.capital_adequacy_ratio:.2f}x",
            f"  Breaches ({self.total_simulations} sims): {self.num_breaches}",
        ]
        return "\n".join(lines)
