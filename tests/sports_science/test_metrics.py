# tests/sports_science/test_metrics.py
import math
import pytest
from api.sports_science.metrics import compute_tss, _compute_np
from api.sports_science.types import ToolResult
from api.sports_science.constants import NP_SPIKE_MULTIPLIER, NP_MIN_DURATION_SECS


class TestNPIncludesZeros:
    """TOOL-04, TOOL-10: NP includes zeros (coasting counts as load)."""

    def test_np_includes_zeros(self, variable_power_array, sample_ftp):
        """NP of array with coasting zeros is lower than flat-power array at same mean non-zero power.

        variable_power_array = [0]*300 + [250]*300 (600 samples)
        Arithmetic mean of non-zero portion = 250W.
        Flat array at 250W would yield NP=250W.
        variable_power_array NP must be < 250W because zeros drag down the 30s rolling windows.
        Also NP must be > 0 (not None) for a valid ride duration.
        """
        result = compute_tss(variable_power_array, 600, sample_ftp)
        assert result.value is not None, "compute_tss should return value for 600s ride"
        np_watts = result.value["np_watts"]
        # NP must be a real positive number, not 250W (which would mean zeros were filtered)
        assert np_watts > 0
        assert np_watts < 250, (
            f"NP={np_watts} should be < 250W (zeros are included, they reduce NP)"
        )


class TestNPSpikeFilter:
    """TOOL-10: Spike filter clips power at FTP*NP_SPIKE_MULTIPLIER before rolling mean."""

    def test_np_spike_filter(self, sample_ftp):
        """Array with a 5000W spike yields same NP as array clipped at FTP*3.

        Build two arrays:
          1. spiked: 3600 samples at 150W with one 5000W spike
          2. clipped: same but spike replaced by ftp * NP_SPIKE_MULTIPLIER (600W)
        Both should produce near-identical NP (within 1W tolerance) because the
        spike filter clips before the rolling mean.
        """
        baseline = [150.0] * 3600
        spiked = baseline[:1800] + [5000.0] + baseline[1801:]
        clipped_val = sample_ftp * NP_SPIKE_MULTIPLIER
        clipped = baseline[:1800] + [clipped_val] + baseline[1801:]

        # Both must produce a valid result at 3600s
        r_spike = compute_tss(spiked, 3600, sample_ftp)
        r_clip = compute_tss(clipped, 3600, sample_ftp)

        assert r_spike.value is not None
        assert r_clip.value is not None
        # NP values must be nearly identical (within 1W) because spike is clipped
        np_spike = r_spike.value["np_watts"]
        np_clip = r_clip.value["np_watts"]
        assert abs(np_spike - np_clip) <= 1.0, (
            f"Spiked NP={np_spike}, clipped NP={np_clip}: spike filter must equalize them"
        )


class TestTSSShortRideNull:
    """TOOL-04, TOOL-10: compute_tss returns value=None for rides under 10 minutes."""

    def test_tss_short_ride_null(self, sample_ftp):
        """duration_secs=300 (5 min) < NP_MIN_DURATION_SECS (600s) -> value=None."""
        result = compute_tss([150.0] * 300, 300, sample_ftp)
        assert isinstance(result, ToolResult)
        assert result.value is None, (
            f"Short ride should return value=None but got {result.value}"
        )

    def test_tss_exactly_at_minimum_returns_value(self, sample_ftp):
        """duration_secs == NP_MIN_DURATION_SECS (600s) should return a value (boundary)."""
        # 600 samples at 150W; duration = 600s
        result = compute_tss([150.0] * 600, 600, sample_ftp)
        assert isinstance(result, ToolResult)
        # At exactly the minimum, the ride is valid (not strictly less than)
        assert result.value is not None


class TestAllZeros:
    """TOOL-10: All-zero power array does not raise; returns TSS=0 or graceful None."""

    def test_all_zeros_no_exception(self, sample_ftp):
        """compute_tss on all-zero array of valid duration must not raise any exception."""
        try:
            result = compute_tss([0.0] * 3600, 3600, sample_ftp)
        except Exception as exc:
            pytest.fail(f"compute_tss raised {exc} on all-zero power array")
        assert isinstance(result, ToolResult)

    def test_all_zeros_tss_is_zero_or_none(self, sample_ftp):
        """All-zero power array: TSS should be 0.0 (zero load) or value=None, never an error."""
        result = compute_tss([0.0] * 3600, 3600, sample_ftp)
        if result.value is not None:
            assert result.value["tss"] == 0.0 or result.value["tss"] is None


class TestNPGreaterThanAverage:
    """TOOL-10: NP of a variable ride > arithmetic mean (NP != average power)."""

    def test_np_greater_than_average(self, variable_power_array, sample_ftp):
        """NP must exceed arithmetic mean for a variable-intensity effort.

        variable_power_array = [0]*300 + [250]*300; arithmetic mean = 125W.
        Because NP raises values to 4th power before averaging, high-power efforts
        weight more heavily -- NP > 125W.
        """
        arr = variable_power_array
        arithmetic_mean = sum(arr) / len(arr)  # 125W

        result = compute_tss(arr, 600, sample_ftp)
        assert result.value is not None
        np_watts = result.value["np_watts"]
        assert np_watts > arithmetic_mean, (
            f"NP={np_watts} should exceed arithmetic mean={arithmetic_mean:.1f}W"
        )


class TestReturnsToolResult:
    """TOOL-09: compute_tss returns a ToolResult with all four required keys."""

    def test_returns_tool_result_instance(self, flat_power_array, sample_ftp):
        result = compute_tss(flat_power_array, 3600, sample_ftp)
        assert isinstance(result, ToolResult)

    def test_tool_result_has_required_keys(self, flat_power_array, sample_ftp):
        result = compute_tss(flat_power_array, 3600, sample_ftp)
        assert hasattr(result, "value")
        assert hasattr(result, "unit")
        assert hasattr(result, "methodology")
        assert hasattr(result, "inputs")

    def test_valid_result_value_has_tss_np_if_warnings(self, flat_power_array, sample_ftp):
        result = compute_tss(flat_power_array, 3600, sample_ftp)
        assert result.value is not None
        assert "tss" in result.value
        assert "np_watts" in result.value
        assert "intensity_factor" in result.value
        assert "warnings" in result.value
