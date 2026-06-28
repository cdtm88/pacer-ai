# tests/sports_science/test_pmc.py
import math
import pytest
from backend.sports_science.pmc import update_pmc, CTL_ALPHA, ATL_ALPHA
from backend.sports_science.types import ToolResult
from backend.sports_science.constants import CTL_TC, ATL_TC, PMC_MIN_DAYS


class TestEWMAValues:
    """TOOL-05: PMC EWMA step matches manual 1 - exp(-1/TC) calculation."""

    def test_ewma_values_from_established_base(self):
        """update_pmc(prev_ctl=50, prev_atl=50, tss=100, days_of_data=60)
        should return CTL and ATL that match the manual EWMA step within 0.01.
        """
        expected_ctl_alpha = 1 - math.exp(-1 / CTL_TC)  # ~0.0235
        expected_atl_alpha = 1 - math.exp(-1 / ATL_TC)  # ~0.1331

        prev_ctl, prev_atl, tss = 50.0, 50.0, 100.0
        expected_ctl = round(prev_ctl + expected_ctl_alpha * (tss - prev_ctl), 2)
        expected_atl = round(prev_atl + expected_atl_alpha * (tss - prev_atl), 2)

        result = update_pmc(prev_ctl=prev_ctl, prev_atl=prev_atl, tss=tss, days_of_data=60)

        assert isinstance(result, ToolResult)
        assert abs(result.value["ctl"] - expected_ctl) <= 0.01, (
            f"CTL={result.value['ctl']} expected={expected_ctl}"
        )
        assert abs(result.value["atl"] - expected_atl) <= 0.01, (
            f"ATL={result.value['atl']} expected={expected_atl}"
        )

    def test_ewma_from_zero_baseline(self):
        """Starting from zero, one step with TSS=100 matches manual EWMA from 0."""
        expected_ctl = round(0 + CTL_ALPHA * (100 - 0), 2)
        expected_atl = round(0 + ATL_ALPHA * (100 - 0), 2)

        result = update_pmc(prev_ctl=0.0, prev_atl=0.0, tss=100.0, days_of_data=60)

        assert abs(result.value["ctl"] - expected_ctl) <= 0.01
        assert abs(result.value["atl"] - expected_atl) <= 0.01

    def test_tsb_equals_previous_ctl_minus_atl(self):
        """TSB = prev_ctl - prev_atl (today's form is yesterday's CTL - ATL)."""
        prev_ctl, prev_atl = 60.0, 70.0
        result = update_pmc(prev_ctl=prev_ctl, prev_atl=prev_atl, tss=80.0, days_of_data=60)
        expected_tsb = round(prev_ctl - prev_atl, 2)
        assert abs(result.value["tsb"] - expected_tsb) <= 0.01, (
            f"TSB={result.value['tsb']} expected={expected_tsb}"
        )

    def test_module_level_alphas_match_constants(self):
        """CTL_ALPHA and ATL_ALPHA at module level must match 1 - exp(-1/TC)."""
        assert abs(CTL_ALPHA - (1 - math.exp(-1 / CTL_TC))) < 1e-9
        assert abs(ATL_ALPHA - (1 - math.exp(-1 / ATL_TC))) < 1e-9


class TestColdStartGuard:
    """TOOL-05, D-06: tss_display_ready gates on PMC_MIN_DAYS (28)."""

    def test_cold_start_guard_false_at_10_days(self):
        """days_of_data=10 < PMC_MIN_DAYS=28: tss_display_ready must be False."""
        result = update_pmc(prev_ctl=0.0, prev_atl=0.0, tss=100.0, days_of_data=10)
        assert result.value["tss_display_ready"] is False, (
            f"10 days: tss_display_ready should be False, got {result.value['tss_display_ready']}"
        )

    def test_cold_start_guard_false_at_27_days(self):
        """days_of_data=27: still False (one day before threshold)."""
        result = update_pmc(prev_ctl=0.0, prev_atl=0.0, tss=100.0, days_of_data=27)
        assert result.value["tss_display_ready"] is False

    def test_cold_start_guard_true_at_28_days(self):
        """days_of_data=28 == PMC_MIN_DAYS: tss_display_ready must be True."""
        result = update_pmc(prev_ctl=0.0, prev_atl=0.0, tss=100.0, days_of_data=28)
        assert result.value["tss_display_ready"] is True, (
            f"28 days: tss_display_ready should be True, got {result.value['tss_display_ready']}"
        )

    def test_cold_start_guard_true_beyond_threshold(self):
        """days_of_data=60: tss_display_ready must be True."""
        result = update_pmc(prev_ctl=0.0, prev_atl=0.0, tss=100.0, days_of_data=60)
        assert result.value["tss_display_ready"] is True


class TestReturnsToolResult:
    """TOOL-09: update_pmc returns a ToolResult with all four required keys."""

    def test_returns_tool_result_instance(self):
        result = update_pmc(prev_ctl=50.0, prev_atl=50.0, tss=80.0, days_of_data=60)
        assert isinstance(result, ToolResult)

    def test_tool_result_has_required_keys(self):
        result = update_pmc(prev_ctl=50.0, prev_atl=50.0, tss=80.0, days_of_data=60)
        assert hasattr(result, "value")
        assert hasattr(result, "unit")
        assert hasattr(result, "methodology")
        assert hasattr(result, "inputs")

    def test_value_has_all_pmc_keys(self):
        result = update_pmc(prev_ctl=50.0, prev_atl=50.0, tss=80.0, days_of_data=60)
        assert "ctl" in result.value
        assert "atl" in result.value
        assert "tsb" in result.value
        assert "tss_display_ready" in result.value
