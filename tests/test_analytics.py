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

    def test_tail_loss_actually_selects_the_tail_pct_asks_for(self):
        """`pct` must set the tail width, not merely be validated and discarded.

        The live survivor this closes: `int(len(losses) * pct)` ->
        `int(len(losses) * 0.01)` shipped 161 passed, because the only other
        tail_loss test passes the default pct=0.01 and so cannot tell the two
        apart. Expectations below are computed by hand from a 1..100 ramp, not
        re-derived from the implementation -- a gate that recomputes the formula
        under test moves with the mutation and proves nothing.
        """
        losses = np.arange(1.0, 101.0)  # 100 paths, worst is 100.0
        assert tail_loss(losses, pct=0.01) == pytest.approx(100.0)  # worst 1
        assert tail_loss(losses, pct=0.10) == pytest.approx(95.5)   # mean(91..100)
        assert tail_loss(losses, pct=0.25) == pytest.approx(88.0)   # mean(76..100)
        assert tail_loss(losses, pct=0.50) == pytest.approx(75.5)   # mean(51..100)
        # Strictly monotone in pct: a wider tail reaches further down the ramp.
        widths = [tail_loss(losses, pct=p) for p in (0.01, 0.10, 0.25, 0.50)]
        assert widths == sorted(widths, reverse=True)
        assert len(set(widths)) == len(widths), "tail_loss does not respond to pct"

    def test_tail_loss_rejects_a_pct_outside_the_unit_interval(self):
        """The guard that made `pct` look used must itself stay live."""
        losses = np.arange(1.0, 101.0)
        for bad in (0.0, 1.0, -0.1, 1.5):
            with pytest.raises(ValueError):
                tail_loss(losses, pct=bad)


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


    def test_capital_report_keys(self, loss_array):
        report = capital_adequacy_report(5_000_000, loss_array)
        for key in ["expected_loss", "var_95", "var_99", "car_vs_el", "breaches"]:
            assert key in report

    def test_breach_rate_in_range(self, loss_array):
        report = capital_adequacy_report(100_000, loss_array)
        assert 0 <= report["breach_rate"] <= 1

class TestTier1UnderStress:
    """``tier1_under_stress`` is an exported, README-documented, regulator-facing
    capital ratio whose only test asserted ``isinstance(t1, float)``.

    All four of these mutations shipped 144 passed against that test:

      * replacing the whole body with ``return 0.1234``
      * ``tier1_capital - stressed_loss`` -> ``+`` (adds losses instead of absorbing)
      * ``value_at_risk(losses, confidence)`` -> ``value_at_risk(losses, 0.50)``,
        ignoring the ``confidence`` argument entirely -- the identical shape to
        0.1.0's ``simulate_default_events(seed=...)``
      * ``/ risk_weighted_assets`` -> ``/ risk_weighted_assets * 100`` (percent
        reported where a fraction is documented, a 100x capital-ratio error)

    The arithmetic below is hand-computed, not read back out of the function.
    ``losses`` is 0, 100k, ... 10.0MM in even steps, so linear-interpolated
    percentiles land exactly on an element: VaR(0.99) = $9.90MM, VaR(0.50) = $5.00MM.
    """

    # 101 evenly spaced points, so np.percentile hits an element exactly.
    LOSSES = np.arange(0, 101, dtype=float) * 100_000.0
    TIER1 = 10_000_000.0
    RWA = 50_000_000.0

    def test_var_used_is_the_one_this_class_hand_computes(self):
        """Guard: if the percentile convention moves, the constants below are wrong."""
        assert value_at_risk(self.LOSSES, 0.99) == pytest.approx(9_900_000.0)
        assert value_at_risk(self.LOSSES, 0.50) == pytest.approx(5_000_000.0)

    def test_equals_tier1_less_stressed_var_over_rwa(self):
        """The whole closed form at once. ($10.00MM - $9.90MM) / $50MM = 0.002."""
        t1 = tier1_under_stress(
            self.TIER1, self.LOSSES, risk_weighted_assets=self.RWA, confidence=0.99
        )
        assert t1 == pytest.approx(0.002), (
            f"expected 0.002 = ($10,000,000 - $9,900,000) / $50,000,000; got {t1!r}"
        )

    def test_losses_are_absorbed_not_added(self):
        """A bigger stressed loss must LOWER the residual ratio, never raise it."""
        small = tier1_under_stress(
            self.TIER1, self.LOSSES * 0.1, risk_weighted_assets=self.RWA, confidence=0.99
        )
        large = tier1_under_stress(
            self.TIER1, self.LOSSES, risk_weighted_assets=self.RWA, confidence=0.99
        )
        assert large < small, (
            f"larger losses produced a HIGHER ratio ({large!r} vs {small!r}); "
            "losses are being added to capital instead of absorbed by it"
        )
        # ...and by exactly the loss difference, scaled by RWA.
        assert small - large == pytest.approx((9_900_000.0 - 990_000.0) / self.RWA)

    def test_the_confidence_argument_is_actually_used(self):
        """0.1.0 shipped a method that advertised a parameter it never read."""
        strict = tier1_under_stress(
            self.TIER1, self.LOSSES, risk_weighted_assets=self.RWA, confidence=0.99
        )
        loose = tier1_under_stress(
            self.TIER1, self.LOSSES, risk_weighted_assets=self.RWA, confidence=0.50
        )
        assert strict != loose, (
            "confidence made no difference to the result; the argument is being ignored"
        )
        assert strict == pytest.approx(0.002)
        assert loose == pytest.approx(0.100)
        assert strict < loose, "a stricter confidence must leave less residual capital"

    def test_result_is_a_fraction_of_rwa_not_a_percentage(self):
        """A 100x error here reads as a comfortably capitalised institution."""
        flat_losses = np.full(200, 1_000_000.0)
        t1 = tier1_under_stress(
            5_000_000.0, flat_losses, risk_weighted_assets=50_000_000.0, confidence=0.99
        )
        assert t1 == pytest.approx(0.08), (
            f"expected the fraction 0.08 (i.e. 8%), got {t1!r}; a value of 8.0 means "
            "the ratio is being rendered as a percentage while the docs call it a ratio"
        )
        assert 0.0 < t1 < 1.0

    def test_negative_when_stressed_loss_exceeds_tier1(self):
        """The undercapitalised case must be representable, not clamped to zero."""
        t1 = tier1_under_stress(
            1_000_000.0, self.LOSSES, risk_weighted_assets=self.RWA, confidence=0.99
        )
        assert t1 == pytest.approx((1_000_000.0 - 9_900_000.0) / self.RWA)
        assert t1 < 0

    def test_zero_rwa_returns_zero(self):
        assert tier1_under_stress(
            self.TIER1, self.LOSSES, risk_weighted_assets=0.0, confidence=0.99
        ) == 0.0


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
