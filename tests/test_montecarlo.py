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
from cdfistress.data.schema import SECTOR_DEFAULT_RATES


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

    def test_default_probabilities_returns_dict(self, engine, scenario_recession):
        pds = engine.default_probabilities(scenario_recession)
        assert len(pds) == len(engine.loans)

    def test_default_probabilities_bounded(self, engine, scenario_recession):
        pds = engine.default_probabilities(scenario_recession)
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


class TestDefaultProbabilityValues:
    """0.2.0 gated only the LENGTH and the [0, 1] bound of these PDs.

    Deleting ``* scenario.default_rate_multiplier`` understates every PD by 4x
    under ``2008_recession`` (0.16 -> 0.04) and both of those gates still passed,
    because a 4x understatement has the right length and lies inside [0, 1].
    The docstring makes a precise numerical claim; these tests are that claim.
    """

    def test_each_pd_is_its_sector_rate_times_the_scenario_multiplier(
        self, engine, scenario_recession
    ):
        """The exact value, derived from SECTOR_DEFAULT_RATES -- no literals."""
        expected = {
            loan.loan_id: round(
                min(
                    1.0,
                    SECTOR_DEFAULT_RATES.get(loan.sector, 0.035)
                    * scenario_recession.default_rate_multiplier,
                ),
                4,
            )
            for loan in engine.loans
        }
        assert engine.default_probabilities(scenario_recession) == expected

    def test_the_multiplier_is_actually_applied(self, engine, scenario_recession):
        """Dropping the multiplier must not survive: PDs exceed the baselines."""
        assert scenario_recession.default_rate_multiplier > 1
        pds = engine.default_probabilities(scenario_recession)
        for loan in engine.loans:
            baseline = SECTOR_DEFAULT_RATES.get(loan.sector, 0.035)
            assert pds[loan.loan_id] > baseline, (
                f"{loan.loan_id} ({loan.sector}) PD {pds[loan.loan_id]} is not above "
                f"its unstressed baseline {baseline}; the scenario multiplier "
                f"({scenario_recession.default_rate_multiplier}x) is not being applied"
            )

    def test_pds_scale_linearly_with_the_multiplier(self, engine):
        """Doubling the multiplier doubles every unclipped PD."""
        from cdfistress.scenarios.builder import create_recession_scenario

        single = create_recession_scenario(default_rate_multiplier=1.0)
        double = create_recession_scenario(default_rate_multiplier=2.0)
        one = engine.default_probabilities(single)
        two = engine.default_probabilities(double)
        for loan_id, value in one.items():
            assert two[loan_id] == pytest.approx(2 * value, rel=1e-9), loan_id

    def test_pds_are_clipped_at_one(self, engine):
        from cdfistress.scenarios.builder import create_recession_scenario

        extreme = create_recession_scenario(default_rate_multiplier=1_000.0)
        assert set(engine.default_probabilities(extreme).values()) == {1.0}

    def test_pds_are_sector_differentiated_within_one_run(
        self, engine, scenario_recession
    ):
        """The engine DOES resolve sector per loan.

        This is the gate behind the 0.2.0 wording change: the missing piece for
        segment-targeted stress is calibration, not mechanism. If this ever goes
        red, the per-loan sector resolution has been lost and README limitation 1
        and the create_recession_scenario docstring both become wrong.
        """
        pds = engine.default_probabilities(scenario_recession)
        distinct_rates = {
            SECTOR_DEFAULT_RATES.get(loan.sector, 0.035) for loan in engine.loans
        }
        assert len(distinct_rates) > 1, "fixture portfolio spans only one sector band"
        assert len(set(pds.values())) == len(distinct_rates), (
            f"{len(set(pds.values()))} distinct PDs for {len(distinct_rates)} distinct "
            "sector baselines: sector is no longer resolved per loan"
        )

    def test_simulation_pds_are_at_least_the_lookup_pds(
        self, sample_loans, scenario_recession
    ):
        """The docstring claims realised simulation PDs are >= these values.

        run_simulation scales each path's PD by ``1 + max(0, -noi_i)``, which is
        >= 1, so simulated losses must exceed what the lookup PDs alone imply.
        Compared with wide headroom: the 2008 scenario's mean NOI shock of -0.35
        gives roughly a 35% uplift, so a 10% threshold is not a coin flip.
        """
        engine = MonteCarloEngine(loans=sample_loans, available_capital=5_000_000)
        pds = engine.default_probabilities(scenario_recession)
        lgd = engine._compute_lgd(scenario_recession)
        implied = sum(
            pds[loan.loan_id] * loan.outstanding_balance * float(l)
            for loan, l in zip(sample_loans, lgd)
        )
        result = engine.run_simulation(scenario_recession, n_iterations=4000, seed=0)
        assert result.expected_loss > 1.10 * implied, (
            f"simulated EL ${result.expected_loss:,.0f} is not meaningfully above the "
            f"${implied:,.0f} implied by the lookup PDs; the docstring claims the "
            "simulation additionally scales PD by 1 + max(0, -noi_i)"
        )


class TestCorrelationMatrixValidation:
    """`is_positive_semidefinite` was exported as public API and never called.

    Through 0.2.0 a non-PSD matrix, and a matrix with a diagonal of 5 (not a
    correlation matrix at all), both produced numbers. That does not corrupt the
    loss distribution -- limitation 3 says the matrix does not reach it -- but it
    does corrupt `apply_correlated_shocks`, which is public API.
    """

    def test_a_valid_custom_matrix_is_still_accepted(self, sample_loans):
        C = build_correlation_matrix(noi_rate=-0.1, noi_property=0.5, rate_property=-0.3)
        engine = MonteCarloEngine(sample_loans, 5_000_000, correlation_matrix=C)
        assert engine.apply_correlated_shocks(
            from_standard_scenario(), n_iterations=10, seed=0
        ).shape == (10, 3)

    def test_the_identity_matrix_is_accepted(self, sample_loans):
        engine = MonteCarloEngine(sample_loans, 5_000_000, correlation_matrix=np.eye(3))
        assert engine._corr.shape == (3, 3)

    def test_a_non_psd_matrix_is_rejected(self, sample_loans):
        """Symmetric, unit diagonal, entries in [-1, 1] -- but not realisable."""
        C = np.array([[1.0, 0.9, -0.9], [0.9, 1.0, 0.9], [-0.9, 0.9, 1.0]])
        assert np.allclose(C, C.T) and np.allclose(np.diag(C), 1.0)
        assert not is_positive_semidefinite(C), "test matrix is not the intended case"
        with pytest.raises(ValueError, match="positive semi-definite"):
            MonteCarloEngine(sample_loans, 5_000_000, correlation_matrix=C)

    def test_a_non_unit_diagonal_is_rejected(self, sample_loans):
        C = np.eye(3) * 5.0
        with pytest.raises(ValueError, match="unit diagonal"):
            MonteCarloEngine(sample_loans, 5_000_000, correlation_matrix=C)

    def test_a_non_symmetric_matrix_is_rejected(self, sample_loans):
        C = np.array([[1.0, 0.5, 0.1], [-0.5, 1.0, 0.1], [0.1, 0.1, 1.0]])
        with pytest.raises(ValueError, match="symmetric"):
            MonteCarloEngine(sample_loans, 5_000_000, correlation_matrix=C)

    def test_a_wrongly_shaped_matrix_is_rejected(self, sample_loans):
        with pytest.raises(ValueError, match="3x3"):
            MonteCarloEngine(sample_loans, 5_000_000, correlation_matrix=np.eye(4))

    def test_out_of_range_entries_are_rejected(self, sample_loans):
        C = np.array([[1.0, 1.5, 0.0], [1.5, 1.0, 0.0], [0.0, 0.0, 1.0]])
        with pytest.raises(ValueError):
            MonteCarloEngine(sample_loans, 5_000_000, correlation_matrix=C)

    def test_nan_entries_are_rejected(self, sample_loans):
        C = np.eye(3)
        C[0, 1] = C[1, 0] = np.nan
        with pytest.raises(ValueError):
            MonteCarloEngine(sample_loans, 5_000_000, correlation_matrix=C)

    def test_validation_does_not_change_the_loss_distribution(
        self, sample_loans, scenario_recession
    ):
        """Explicitly passing the defaults must reproduce the default engine."""
        plain = MonteCarloEngine(sample_loans, 5_000_000)
        explicit = MonteCarloEngine(
            sample_loans, 5_000_000, correlation_matrix=default_correlations()
        )
        plain.run_simulation(scenario_recession, n_iterations=200, seed=5)
        explicit.run_simulation(scenario_recession, n_iterations=200, seed=5)
        assert np.array_equal(plain.loss_distribution, explicit.loss_distribution)


def from_standard_scenario():
    from cdfistress.scenarios.builder import from_standard

    return from_standard("2008_recession")
