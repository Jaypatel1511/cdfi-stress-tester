"""Tests for MonteCarloEngine and correlation matrix."""
import pytest
import numpy as np
from cdfistress.montecarlo.simulator import MonteCarloEngine
from cdfistress.montecarlo.correlations import (
    build_correlation_matrix,
    default_correlations,
    is_positive_semidefinite,
    sector_correlation_boost,
)
from cdfistress.data.sample import generate_sample_portfolio


class TestCorrelationMatrix:
    def test_default_is_3x3(self):
        C = default_correlations()
        assert C.shape == (3, 3)

    def test_diagonal_is_one(self):
        C = default_correlations()
        assert np.allclose(np.diag(C), 1.0)

    def test_symmetric(self):
        C = default_correlations()
        assert np.allclose(C, C.T)

    def test_positive_semidefinite(self):
        C = default_correlations()
        assert is_positive_semidefinite(C)

    def test_custom_correlations(self):
        C = build_correlation_matrix(noi_rate=-0.1, noi_property=0.5, rate_property=-0.3)
        assert C[0, 1] == pytest.approx(-0.1)
        assert C[0, 2] == pytest.approx(0.5)

    def test_sector_boost_multifamily(self):
        assert sector_correlation_boost("multifamily") == pytest.approx(1.0)

    def test_sector_boost_retail_higher(self):
        assert sector_correlation_boost("retail") > sector_correlation_boost("multifamily")


class TestMonteCarloEngine:
    def test_engine_requires_loans(self):
        with pytest.raises(ValueError):
            MonteCarloEngine(loans=[], available_capital=1_000_000)

    def test_engine_requires_positive_capital(self, sample_loans):
        with pytest.raises(ValueError):
            MonteCarloEngine(loans=sample_loans, available_capital=-1)

    def test_run_simulation_returns_result(self, engine, scenario_recession):
        result = engine.run_simulation(scenario_recession, n_iterations=100, seed=42)
        assert result.expected_loss > 0

    def test_seed_reproducibility(self, engine, scenario_recession):
        r1 = engine.run_simulation(scenario_recession, n_iterations=200, seed=7)
        r2 = engine.run_simulation(scenario_recession, n_iterations=200, seed=7)
        assert r1.expected_loss == pytest.approx(r2.expected_loss)

    def test_different_seeds_differ(self, engine, scenario_recession):
        r1 = engine.run_simulation(scenario_recession, n_iterations=200, seed=1)
        r2 = engine.run_simulation(scenario_recession, n_iterations=200, seed=2)
        assert r1.expected_loss != pytest.approx(r2.expected_loss)

    def test_var99_gte_var95(self, engine, scenario_recession):
        result = engine.run_simulation(scenario_recession, n_iterations=500, seed=42)
        assert result.var_99 >= result.var_95

    def test_var95_gte_expected_loss(self, engine, scenario_recession):
        result = engine.run_simulation(scenario_recession, n_iterations=500, seed=42)
        assert result.var_95 >= result.expected_loss

    def test_severe_scenario_higher_loss_than_mild(self, engine, scenario_recession, scenario_mild):
        r_severe = engine.run_simulation(scenario_recession, n_iterations=500, seed=42)
        r_mild = engine.run_simulation(scenario_mild, n_iterations=500, seed=42)
        assert r_severe.expected_loss > r_mild.expected_loss

    def test_correlated_shocks_shape(self, engine, scenario_recession):
        shocks = engine.apply_correlated_shocks(scenario_recession, n_iterations=100, seed=0)
        assert shocks.shape == (100, 3)

    def test_simulate_default_events_returns_dict(self, engine, scenario_recession):
        pds = engine.simulate_default_events(scenario_recession)
        assert len(pds) == len(engine.loans)

    def test_default_probabilities_bounded(self, engine, scenario_recession):
        pds = engine.simulate_default_events(scenario_recession)
        for pd in pds.values():
            assert 0 <= pd <= 1

    def test_convergence_with_more_iterations(self, sample_loans, scenario_recession):
        engine_s = MonteCarloEngine(sample_loans, available_capital=5_000_000)
        r_small = engine_s.run_simulation(scenario_recession, n_iterations=200, seed=0)
        r_large = engine_s.run_simulation(scenario_recession, n_iterations=2000, seed=0)
        # Both should produce positive expected losses
        assert r_large.expected_loss > 0
        # Relative difference in EL should be modest as n grows
        rel_diff = abs(r_large.expected_loss - r_small.expected_loss) / r_large.expected_loss
        assert rel_diff < 0.40
