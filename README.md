# cdfi-stress-tester

[![PyPI version](https://badge.fury.io/py/cdfi-stress-tester.svg)](https://badge.fury.io/py/cdfi-stress-tester)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Professional CDFI portfolio stress testing engine for Python.**

Monte Carlo simulation with correlated shocks to NOI, interest rates, and property values. Compute VaR, CVaR, and capital adequacy across 2008-style recession, COVID, rate-spike, and regional CRE crash scenarios — all from pure numpy/pandas, no simulation libraries required.

---

## Why cdfi-stress-tester?

CDFI Fund regulations and investor due diligence increasingly require stress-tested capital adequacy projections. Building Monte Carlo models in Excel is brittle and hard to audit. `cdfi-stress-tester` provides a reproducible, testable Python engine tuned to community development finance portfolio characteristics.

## Installation

```bash
pip install cdfi-stress-tester
```

Requires: `numpy`, `pandas` (Python 3.9+).

## Quickstart

```python
from cdfistress import (
    generate_sample_portfolio,
    from_standard,
    MonteCarloEngine,
    generate_stress_report,
    scenario_comparison_table,
    value_at_risk, conditional_var, capital_adequacy_report,
)

# Load a 50-loan CDFI portfolio
loans = generate_sample_portfolio(n=50, seed=42)

# Build the Monte Carlo engine
engine = MonteCarloEngine(loans=loans, available_capital=5_000_000)

# Run a 2008-style recession scenario
scenario = from_standard("2008_recession")
result = engine.run_simulation(scenario, n_iterations=1000, seed=42)

# Print human-readable report
print(generate_stress_report(result))
# ============================================================
# CDFI PORTFOLIO STRESS TEST REPORT
# Scenario: 2008-Style Recession  [SEVERE]
# ============================================================
# LOSS METRICS
#   Expected Loss        :     $2,341,205
#   VaR (95%)            :     $3,879,450
#   VaR (99%)            :     $4,672,000
# CAPITAL ADEQUACY
#   CAR vs Expected Loss : 2.14x
#   STATUS: ADEQUATE

# Compare multiple scenarios
scenarios = [from_standard(k) for k in ["mild_downturn", "rate_spike", "2008_recession"]]
results = [engine.run_simulation(s, n_iterations=500, seed=0) for s in scenarios]
print(scenario_comparison_table(results))

# Capital adequacy deep-dive
import numpy as np
losses = np.array([result.expected_loss])   # or use internal loss distribution
report = capital_adequacy_report(5_000_000, np.random.default_rng(0).lognormal(14, 0.5, 1000))
```

## Key Features

| Feature | Detail |
|---|---|
| **Monte Carlo engine** | `MonteCarloEngine` with seed-controlled reproducibility |
| **Correlated shocks** | Multivariate normal draws for NOI, rate, and property value |
| **Standard scenarios** | 2008 recession, COVID, rate spike (+300 bps), regional CRE crash, mild downturn |
| **Custom scenarios** | `create_recession_scenario()`, `create_rate_shock_scenario()`, `create_sector_specific_scenario()` |
| **VaR / CVaR** | 95th and 99th percentile VaR; Expected Shortfall (CVaR) |
| **Capital adequacy** | CAR vs EL, VaR, and CVaR; breach count and breach rate |
| **Tier 1 under stress** | Post-stress Tier 1 ratio given risk-weighted assets |
| **Sample portfolio** | Reproducible 50-loan CDFI portfolio with realistic parameters |
| **LGD modeling** | Per-loan LGD with collateral shortfall and 30% foreclosure-cost floor |
| **Reports** | `generate_stress_report()` and `scenario_comparison_table()` |

## Scenarios

```python
STANDARD_SCENARIOS = {
    "2008_recession":    {"noi_shock": -0.35, "rate_shock": 0.00, "property_value_shock": -0.40, "default_rate_multiplier": 4.0},
    "covid_shock":       {"noi_shock": -0.25, "rate_shock": -0.01, "property_value_shock": -0.15, "default_rate_multiplier": 2.5},
    "rate_spike":        {"noi_shock": -0.05, "rate_shock": +0.03, "property_value_shock": -0.20, "default_rate_multiplier": 1.8},
    "regional_cre_crash":{"noi_shock": -0.20, "rate_shock": +0.01, "property_value_shock": -0.50, "default_rate_multiplier": 3.0},
    "mild_downturn":     {"noi_shock": -0.10, "rate_shock": +0.005,"property_value_shock": -0.08, "default_rate_multiplier": 1.4},
}
```

## Use Cases

- **CDFI Fund reporting** — Demonstrate capital adequacy under regulatory stress scenarios.
- **Rating agency submissions** — Produce reproducible loss distributions for credit analysis.
- **Board risk committees** — Run scenario comparison tables for governance reporting.
- **Investors / lenders** — Stress-test CDFI portfolios during due diligence.
- **Policy researchers** — Analyze CDFI sector resilience across geographic and sector concentrations.

## API Reference

```python
# Data
generate_sample_portfolio(n=50, seed=42)   # 50-loan CDFI portfolio
Loan(loan_id, borrower_name, outstanding_balance, noi, debt_service,
     property_value, interest_rate, sector, state, ltv)
  .dscr                    # noi / debt_service
  .is_stressed             # dscr < 1.0

StressScenario(name, noi_shock, rate_shock, property_value_shock,
               default_rate_multiplier, severity)
  .summary()

# Scenarios
from_standard("2008_recession")
create_recession_scenario(noi_shock, rate_shock, property_value_shock, default_rate_multiplier)
create_rate_shock_scenario(rate_shock, property_value_shock)
create_sector_specific_scenario(sector, noi_shock, property_value_shock)
apply_shock_to_loan(loan, scenario)        # returns stressed Loan

# Simulation
MonteCarloEngine(loans, available_capital, correlation_matrix)
  .run_simulation(scenario, n_iterations=1000, seed=None)  # → StressResult
  .apply_correlated_shocks(scenario, n_iterations, seed)   # → ndarray (n, 3)
  .simulate_default_events(scenario, seed)                  # → {loan_id: pd}

# VaR / Capital
value_at_risk(losses, confidence=0.95)
conditional_var(losses, confidence=0.95)
expected_loss(losses)
tail_loss(losses, pct=0.01)
capital_adequacy(available_capital, expected_loss_amount)
tier1_under_stress(tier1_capital, losses, risk_weighted_assets, confidence=0.99)
buffer_breach_count(losses, capital_buffer)
capital_adequacy_report(available_capital, losses)

# Correlations
build_correlation_matrix(noi_rate, noi_property, rate_property)
default_correlations()
is_positive_semidefinite(matrix)

# Reports
generate_stress_report(result)         # → str
scenario_comparison_table(results)     # → str
```

## License

MIT © Jay Patel
