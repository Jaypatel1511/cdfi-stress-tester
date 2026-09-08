"""
Monte Carlo stress simulation engine using correlated multivariate normal shocks.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np

from cdfistress.data.schema import (
    SECTOR_DEFAULT_RATES,
    Loan,
    StressResult,
    StressScenario,
)
from cdfistress.montecarlo.correlations import build_correlation_matrix, default_correlations


class MonteCarloEngine:
    """Monte Carlo stress simulation engine.

    Generates correlated shocks to NOI, interest rates, and property values
    using numpy multivariate normal, then computes loan-level default events
    and portfolio loss distribution.

    Parameters
    ----------
    loans:
        The CDFI loan portfolio.
    available_capital:
        Capital buffer available to absorb losses ($).
    correlation_matrix:
        3×3 correlation matrix for [NOI, Rate, PropertyValue].
        Defaults to CORRELATION_DEFAULTS if not provided.
    """

    # Risk-factor indices
    _NOI_IDX = 0
    _RATE_IDX = 1
    _PROP_IDX = 2

    def __init__(
        self,
        loans: List[Loan],
        available_capital: float,
        correlation_matrix: Optional[np.ndarray] = None,
    ) -> None:
        if not loans:
            raise ValueError("loans must not be empty")
        if available_capital <= 0:
            raise ValueError("available_capital must be positive")
        self.loans = loans
        self.available_capital = available_capital
        self._corr = correlation_matrix if correlation_matrix is not None else default_correlations()
        self._loss_distribution: Optional[np.ndarray] = None

    def run_simulation(
        self,
        scenario: StressScenario,
        n_iterations: int = 1000,
        seed: Optional[int] = None,
    ) -> StressResult:
        """Run the full Monte Carlo simulation.

        Parameters
        ----------
        scenario:
            The macro stress scenario to simulate.
        n_iterations:
            Number of Monte Carlo paths.
        seed:
            Random seed for reproducibility.

        Returns
        -------
        StressResult with EL, VaR 95/99, capital adequacy, and breach count.
        """
        losses = self._compute_loss_distribution(scenario, n_iterations, seed)
        self._loss_distribution = losses

        expected_loss = float(np.mean(losses))
        var_95 = float(np.percentile(losses, 95))
        var_99 = float(np.percentile(losses, 99))
        car = self.available_capital / expected_loss if expected_loss > 0 else float("inf")
        breaches = int(np.sum(losses > self.available_capital))

        return StressResult(
            scenario=scenario,
            expected_loss=expected_loss,
            var_95=var_95,
            var_99=var_99,
            capital_adequacy_ratio=car,
            num_breaches=breaches,
            total_simulations=n_iterations,
        )

    @property
    def loss_distribution(self) -> np.ndarray:
        """Portfolio losses from the most recent :meth:`run_simulation` call.

        Returns a copy, so callers cannot mutate the engine's internal state.

        Raises
        ------
        RuntimeError
            If :meth:`run_simulation` has not been called yet.
        """
        if self._loss_distribution is None:
            raise RuntimeError(
                "No simulation has been run yet; call run_simulation() first."
            )
        return self._loss_distribution.copy()

    def _compute_loss_distribution(
        self,
        scenario: StressScenario,
        n_iterations: int,
        seed: Optional[int],
    ) -> np.ndarray:
        """Core simulation loop — returns array of portfolio losses per path."""
        rng = np.random.default_rng(seed)

        # Scenario means for each risk factor (as z-score equivalents)
        means = np.array([
            scenario.noi_shock,
            scenario.rate_shock,
            scenario.property_value_shock,
        ])
        # Volatilities (annualized): NOI 15%, Rate 0.5%, Property 20%
        vols = np.array([0.15, 0.005, 0.20])
        # Build covariance matrix from correlation and vols
        D = np.diag(vols)
        cov = D @ self._corr @ D

        # Draw n_iterations × 3 correlated shocks
        shocks = rng.multivariate_normal(means, cov, size=n_iterations)

        # Pre-compute baseline default rates per loan
        base_rates = np.array([
            SECTOR_DEFAULT_RATES.get(loan.sector, 0.035)
            for loan in self.loans
        ])
        base_rates *= scenario.default_rate_multiplier
        base_rates = np.clip(base_rates, 0.0, 1.0)

        balances = np.array([loan.outstanding_balance for loan in self.loans])
        loan_lgd = self._compute_lgd(scenario)

        total_losses = np.zeros(n_iterations)
        for i, shock in enumerate(shocks):
            noi_shock_i, rate_shock_i, prop_shock_i = shock

            # Adjust default rates by NOI shock (worse NOI → higher PD)
            pd_adjust = 1.0 + max(0, -noi_shock_i)   # negative NOI shock raises PD
            pd_i = np.clip(base_rates * pd_adjust, 0.0, 1.0)

            # Bernoulli default events for each loan
            defaults = rng.random(len(self.loans)) < pd_i
            losses_i = defaults * balances * loan_lgd
            total_losses[i] = float(np.sum(losses_i))

        return total_losses

    def _compute_lgd(self, scenario: StressScenario) -> np.ndarray:
        """Compute per-loan Loss-Given-Default under the scenario.

        A base LGD floor of 30% reflects foreclosure costs, workout expenses,
        and the portion of loss not recovered through collateral, even when
        property values fully cover the outstanding balance.

        LGD = max(base_floor, 1 - recovery)
        where recovery = (property_value_stressed / outstanding_balance)
                       = (1 + property_value_shock) / ltv
        """
        base_floor = 0.30
        lgd = np.array([
            max(base_floor, min(1.0, 1.0 - (1.0 / loan.ltv) * (1 + scenario.property_value_shock)))
            for loan in self.loans
        ])
        return lgd

    def apply_correlated_shocks(
        self,
        scenario: StressScenario,
        n_iterations: int = 1000,
        seed: Optional[int] = None,
    ) -> np.ndarray:
        """Return raw shock matrix of shape (n_iterations, 3).

        Useful for inspecting the multivariate normal draw directly.
        """
        rng = np.random.default_rng(seed)
        means = np.array([scenario.noi_shock, scenario.rate_shock, scenario.property_value_shock])
        vols = np.array([0.15, 0.005, 0.20])
        D = np.diag(vols)
        cov = D @ self._corr @ D
        return rng.multivariate_normal(means, cov, size=n_iterations)

    def default_probabilities(
        self,
        scenario: StressScenario,
    ) -> Dict[str, float]:
        """Return each loan's scenario-adjusted annual default probability.

        This is a lookup, not a simulation.  Each loan's baseline sector default
        rate (``SECTOR_DEFAULT_RATES``) is multiplied by the scenario's
        ``default_rate_multiplier`` and clipped to [0, 1].  Nothing is drawn at
        random, so there is no ``seed`` parameter.

        These are NOT the probabilities used inside :meth:`run_simulation`.  The
        simulation additionally scales each path's PD by ``1 + max(0, -noi_i)``
        using that path's own drawn NOI shock, so realised simulation PDs are
        greater than or equal to the values returned here.

        Renamed in 0.2.0 from ``simulate_default_events``, which accepted a
        ``seed`` argument that it then never used.
        """
        base_rates = np.array([
            SECTOR_DEFAULT_RATES.get(loan.sector, 0.035) * scenario.default_rate_multiplier
            for loan in self.loans
        ])
        base_rates = np.clip(base_rates, 0.0, 1.0)
        return {
            loan.loan_id: round(float(pd), 4)
            for loan, pd in zip(self.loans, base_rates)
        }
