"""Tests for VaR, CVaR, capital adequacy, and report generation."""
import pytest
import numpy as np
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
from cdfistress.analysis.reports import generate_stress_report, scenario_comparison_table


class TestVaR:
    def test_var_95_greater_than_mean(self, loss_array):
        assert value_at_risk(loss_array, 0.95) > expected_loss(loss_array)

    def test_var_99_gte_var_95(self, loss_array):
        assert value_at_risk(loss_array, 0.99) >= value_at_risk(loss_array, 0.95)

    def test_empty_array_raises(self):
        with pytest.raises(ValueError):
            value_at_risk(np.array([]), 0.95)

    def test_invalid_confidence_raises(self):
        with pytest.raises(ValueError):
            value_at_risk(np.array([1, 2, 3]), 1.0)

    def test_known_var(self):
        losses = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
        var90 = value_at_risk(losses, 0.90)
        assert var90 == pytest.approx(9.1, abs=0.5)


class TestCVaR:
    def test_cvar_gte_var(self, loss_array):
        var = value_at_risk(loss_array, 0.95)
        cvar = conditional_var(loss_array, 0.95)
        assert cvar >= var

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            conditional_var(np.array([]), 0.95)

    def test_tail_loss_gt_mean(self, loss_array):
        assert tail_loss(loss_array, pct=0.01) > expected_loss(loss_array)


class TestCapitalAdequacy:
    def test_car_above_one_when_adequate(self):
        assert capital_adequacy(2_000_000, 1_000_000) == pytest.approx(2.0)

    def test_car_below_one_when_insufficient(self):
        assert capital_adequacy(500_000, 1_000_000) == pytest.approx(0.5)

    def test_car_inf_when_no_loss(self):
        result = capital_adequacy(1_000_000, 0)
        assert result == float("inf")

    def test_buffer_breach_count(self):
        losses = np.array([100, 200, 300, 400, 500])
        assert buffer_breach_count(losses, 350) == 2

    def test_tier1_under_stress(self, loss_array):
        t1 = tier1_under_stress(10_000_000, loss_array, risk_weighted_assets=50_000_000, confidence=0.99)
        assert isinstance(t1, float)

    def test_capital_report_keys(self, loss_array):
        report = capital_adequacy_report(5_000_000, loss_array)
        for key in ["expected_loss", "var_95", "var_99", "car_vs_el", "breaches"]:
            assert key in report

    def test_breach_rate_in_range(self, loss_array):
        report = capital_adequacy_report(100_000, loss_array)
        assert 0 <= report["breach_rate"] <= 1


class TestReports:
    def test_generate_report_contains_scenario_name(self, engine, scenario_recession):
        result = engine.run_simulation(scenario_recession, n_iterations=100, seed=0)
        report = generate_stress_report(result)
        assert scenario_recession.name in report

    def test_comparison_table_has_header(self, engine, scenario_recession, scenario_mild):
        r1 = engine.run_simulation(scenario_recession, n_iterations=100, seed=0)
        r2 = engine.run_simulation(scenario_mild, n_iterations=100, seed=0)
        table = scenario_comparison_table([r1, r2])
        assert "Scenario" in table

    def test_empty_results_comparison(self):
        table = scenario_comparison_table([])
        assert "No results" in table
