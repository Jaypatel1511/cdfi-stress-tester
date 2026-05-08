"""
Report generation: stress report and scenario comparison table.
"""
from __future__ import annotations

from typing import Dict, List

from cdfistress.data.schema import StressResult


def generate_stress_report(result: StressResult) -> str:
    """Generate a human-readable stress test report."""
    lines = [
        "=" * 60,
        f"CDFI PORTFOLIO STRESS TEST REPORT",
        f"Scenario: {result.scenario.name}  [{result.scenario.severity.upper()}]",
        "=" * 60,
        "",
        "SCENARIO PARAMETERS",
        f"  NOI shock            : {result.scenario.noi_shock:+.1%}",
        f"  Rate shock           : {result.scenario.rate_shock * 100:+.0f} bps",
        f"  Property value shock : {result.scenario.property_value_shock:+.1%}",
        f"  Default mult         : {result.scenario.default_rate_multiplier:.1f}x baseline",
        "",
        "LOSS METRICS",
        f"  Expected Loss        : ${result.expected_loss:>15,.0f}",
        f"  VaR (95%)            : ${result.var_95:>15,.0f}",
        f"  VaR (99%)            : ${result.var_99:>15,.0f}",
        "",
        "CAPITAL ADEQUACY",
        f"  CAR vs Expected Loss : {result.capital_adequacy_ratio:.2f}x",
        f"  Simulation breaches  : {result.num_breaches} / {result.total_simulations} "
        f"({result.num_breaches / result.total_simulations:.1%})",
        "",
        "STATUS: " + (
            "ADEQUATE" if result.capital_adequacy_ratio >= 1.5 else
            "MARGINAL" if result.capital_adequacy_ratio >= 1.0 else
            "INSUFFICIENT"
        ),
        "=" * 60,
    ]
    return "\n".join(lines)


def scenario_comparison_table(results: List[StressResult]) -> str:
    """Format a multi-scenario comparison as a text table."""
    if not results:
        return "No results to compare."

    header = f"{'Scenario':<30} {'Severity':<10} {'EL':>14} {'VaR95':>14} {'VaR99':>14} {'CAR':>7} {'Breaches':>10}"
    separator = "-" * len(header)
    rows = [header, separator]

    for r in results:
        row = (
            f"{r.scenario.name:<30} "
            f"{r.scenario.severity:<10} "
            f"${r.expected_loss:>13,.0f} "
            f"${r.var_95:>13,.0f} "
            f"${r.var_99:>13,.0f} "
            f"{r.capital_adequacy_ratio:>6.2f}x "
            f"{r.num_breaches:>7}/{r.total_simulations}"
        )
        rows.append(row)

    return "\n".join(rows)
