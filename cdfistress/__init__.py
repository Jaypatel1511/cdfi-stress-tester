"""
cdfi-stress-tester — CDFI Portfolio Stress Testing Engine
==========================================================
Monte Carlo simulation with correlated NOI, rate, and property-value shocks;
VaR/CVaR analytics; capital adequacy reporting.
"""
from cdfistress.data.schema import (
    CORRELATION_DEFAULTS,
    SECTOR_DEFAULT_RATES,
    STANDARD_SCENARIOS,
    Loan,
    StressResult,
    StressScenario,
)
from cdfistress.data.sample import generate_sample_portfolio
from cdfistress.scenarios.builder import (
    apply_shock_to_loan,
    create_rate_shock_scenario,
    create_recession_scenario,
    from_standard,
)
from cdfistress.montecarlo.correlations import (
    build_correlation_matrix,
    default_correlations,
    is_positive_semidefinite,
    sector_correlation_boost,
)
from cdfistress.montecarlo.simulator import MonteCarloEngine
from cdfistress.analysis.var import (
    conditional_var,
    expected_loss,
    tail_loss,
    value_at_risk,
)
from cdfistress.analysis.capital import (
    buffer_breach_count,
    capital_adequacy,
    capital_adequacy_report,
    tier1_under_stress,
)
from cdfistress.analysis.reports import (
    generate_stress_report,
    scenario_comparison_table,
)

__version__ = "0.2.0"
__author__ = "Jay Patel"

__all__ = [
    # Data
    "Loan",
    "StressScenario",
    "StressResult",
    "STANDARD_SCENARIOS",
    "CORRELATION_DEFAULTS",
    "SECTOR_DEFAULT_RATES",
    # Sample data
    "generate_sample_portfolio",
    # Scenarios
    "from_standard",
    "create_recession_scenario",
    "create_rate_shock_scenario",
    "apply_shock_to_loan",
    # Correlations
    "build_correlation_matrix",
    "default_correlations",
    "is_positive_semidefinite",
    "sector_correlation_boost",
    # Simulation
    "MonteCarloEngine",
    # VaR
    "value_at_risk",
    "conditional_var",
    "expected_loss",
    "tail_loss",
    # Capital
    "capital_adequacy",
    "tier1_under_stress",
    "buffer_breach_count",
    "capital_adequacy_report",
    # Reports
    "generate_stress_report",
    "scenario_comparison_table",
]
