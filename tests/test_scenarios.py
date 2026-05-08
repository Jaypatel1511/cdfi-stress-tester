"""Tests for scenario builder and shock application."""
import pytest
from cdfistress.scenarios.builder import (
    apply_shock_to_loan,
    create_rate_shock_scenario,
    create_recession_scenario,
    create_sector_specific_scenario,
    from_standard,
)


class TestScenarioBuilder:
    def test_create_recession_scenario(self):
        s = create_recession_scenario()
        assert s.noi_shock == pytest.approx(-0.35)
        assert s.severity == "severe"

    def test_create_rate_shock(self):
        s = create_rate_shock_scenario(rate_shock=0.03)
        assert s.rate_shock == pytest.approx(0.03)
        assert s.severity == "severe"

    def test_mild_rate_shock_severity(self):
        s = create_rate_shock_scenario(rate_shock=0.005)
        assert s.severity == "mild"

    def test_sector_specific_scenario(self):
        s = create_sector_specific_scenario("retail", noi_shock=-0.25)
        assert s.noi_shock == pytest.approx(-0.25)
        assert "Retail" in s.name

    def test_from_standard_2008(self):
        s = from_standard("2008_recession")
        assert s.default_rate_multiplier == pytest.approx(4.0)

    def test_from_standard_covid(self):
        s = from_standard("covid_shock")
        assert s.severity == "moderate"

    def test_from_standard_unknown_raises(self):
        with pytest.raises(KeyError):
            from_standard("unknown_scenario_xyz")


class TestApplyShock:
    def test_noi_reduced(self, loan_healthy, scenario_recession):
        stressed = apply_shock_to_loan(loan_healthy, scenario_recession)
        assert stressed.noi < loan_healthy.noi

    def test_property_value_reduced(self, loan_healthy, scenario_recession):
        stressed = apply_shock_to_loan(loan_healthy, scenario_recession)
        assert stressed.property_value < loan_healthy.property_value

    def test_ltv_increases_after_value_decline(self, loan_healthy, scenario_recession):
        stressed = apply_shock_to_loan(loan_healthy, scenario_recession)
        assert stressed.ltv > loan_healthy.ltv

    def test_rate_shock_applied(self, loan_healthy, scenario_rate_spike):
        stressed = apply_shock_to_loan(loan_healthy, scenario_rate_spike)
        assert stressed.interest_rate > loan_healthy.interest_rate

    def test_rate_never_negative(self, loan_healthy):
        extreme_rate_cut = create_rate_shock_scenario(rate_shock=-0.99)
        stressed = apply_shock_to_loan(loan_healthy, extreme_rate_cut)
        assert stressed.interest_rate >= 0

    def test_loan_id_preserved(self, loan_healthy, scenario_recession):
        stressed = apply_shock_to_loan(loan_healthy, scenario_recession)
        assert stressed.loan_id == loan_healthy.loan_id
