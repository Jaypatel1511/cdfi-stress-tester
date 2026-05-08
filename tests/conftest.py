"""Shared fixtures for cdfi-stress-tester tests."""
import pytest
import numpy as np
from cdfistress.data.schema import Loan, StressScenario
from cdfistress.data.sample import generate_sample_portfolio
from cdfistress.scenarios.builder import from_standard
from cdfistress.montecarlo.simulator import MonteCarloEngine


@pytest.fixture
def loan_healthy():
    return Loan(
        loan_id="CDFI-0001",
        borrower_name="Healthy Borrower",
        outstanding_balance=2_000_000,
        noi=200_000,
        debt_service=150_000,
        property_value=3_000_000,
        interest_rate=0.065,
        sector="multifamily",
        state="CO",
        ltv=0.667,
    )


@pytest.fixture
def loan_stressed():
    return Loan(
        loan_id="CDFI-0002",
        borrower_name="Stressed Borrower",
        outstanding_balance=1_500_000,
        noi=100_000,
        debt_service=130_000,   # DSCR < 1.0
        property_value=1_800_000,
        interest_rate=0.075,
        sector="retail",
        state="OH",
        ltv=0.833,
    )


@pytest.fixture
def scenario_recession():
    return from_standard("2008_recession")


@pytest.fixture
def scenario_rate_spike():
    return from_standard("rate_spike")


@pytest.fixture
def scenario_mild():
    return from_standard("mild_downturn")


@pytest.fixture
def sample_loans():
    return generate_sample_portfolio(n=50, seed=42)


@pytest.fixture
def engine(sample_loans):
    return MonteCarloEngine(
        loans=sample_loans,
        available_capital=3_000_000,
    )


@pytest.fixture
def loss_array():
    """Synthetic loss distribution for VaR/capital tests."""
    rng = np.random.default_rng(0)
    return rng.lognormal(mean=12, sigma=1.0, size=1000)
