"""Tests for Loan, StressScenario, and StressResult dataclasses."""
import pytest
from cdfistress.data.schema import Loan, StressScenario, StressResult, STANDARD_SCENARIOS


class TestLoan:
    def test_dscr_healthy(self, loan_healthy):
        assert loan_healthy.dscr == pytest.approx(200_000 / 150_000)

    def test_dscr_stressed_below_one(self, loan_stressed):
        assert loan_stressed.dscr < 1.0

    def test_is_stressed_false(self, loan_healthy):
        assert loan_healthy.is_stressed is False

    def test_is_stressed_true(self, loan_stressed):
        assert loan_stressed.is_stressed is True

    def test_ltv_stored(self, loan_healthy):
        assert loan_healthy.ltv == pytest.approx(0.667, abs=0.001)


class TestStressScenario:
    def test_valid_scenario(self, scenario_recession):
        assert scenario_recession.severity == "severe"

    def test_invalid_severity_raises(self):
        with pytest.raises(ValueError):
            StressScenario("Test", -0.2, 0.01, -0.1, 2.0, "catastrophic")

    def test_invalid_multiplier_raises(self):
        with pytest.raises(ValueError):
            StressScenario("Test", -0.2, 0.01, -0.1, -1.0, "severe")

    def test_summary_contains_name(self, scenario_recession):
        summary = scenario_recession.summary()
        assert scenario_recession.name in summary

    def test_standard_scenarios_keys(self):
        assert "2008_recession" in STANDARD_SCENARIOS
        assert "covid_shock" in STANDARD_SCENARIOS
        assert "rate_spike" in STANDARD_SCENARIOS
        assert "regional_cre_crash" in STANDARD_SCENARIOS


class TestSamplePortfolio:
    def test_generates_50_loans(self, sample_loans):
        assert len(sample_loans) == 50

    def test_reproducible_with_seed(self):
        from cdfistress.data.sample import generate_sample_portfolio
        p1 = generate_sample_portfolio(seed=99)
        p2 = generate_sample_portfolio(seed=99)
        assert p1[0].outstanding_balance == p2[0].outstanding_balance

    def test_different_seeds_differ(self):
        from cdfistress.data.sample import generate_sample_portfolio
        p1 = generate_sample_portfolio(seed=1)
        p2 = generate_sample_portfolio(seed=2)
        assert p1[0].outstanding_balance != p2[0].outstanding_balance

    def test_balances_in_range(self, sample_loans):
        for loan in sample_loans:
            assert 500_000 <= loan.outstanding_balance <= 8_000_000
