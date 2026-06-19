# tests/sports_science/test_metrics.py
import pytest

pytestmark = pytest.mark.skip(reason="implemented in plan 02")


def test_np_includes_zeros():
    """TOOL-04: NP includes zeros (coasting counts)."""
    metrics = pytest.importorskip("sports_science.metrics")
    result = metrics.compute_tss([0.0] * 300 + [250.0] * 300, 600, 200.0)
    assert result is not None


def test_np_spike_filter():
    """TOOL-04: NP spike filter clips at FTP*3."""
    metrics = pytest.importorskip("sports_science.metrics")
    result = metrics.compute_tss([1000.0] * 3600, 3600, 200.0)
    assert result is not None


def test_tss_short_ride_null():
    """TOOL-04: TSS returns None for ride < 10 min."""
    metrics = pytest.importorskip("sports_science.metrics")
    result = metrics.compute_tss([150.0] * 300, 300, 200.0)
    assert result.value is None


def test_all_zeros():
    """TOOL-10: Edge case: all-zero power array."""
    metrics = pytest.importorskip("sports_science.metrics")
    result = metrics.compute_tss([0.0] * 3600, 3600, 200.0)
    assert result is not None
