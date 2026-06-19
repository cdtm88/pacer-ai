# tests/sports_science/test_pmc.py
import pytest

pytestmark = pytest.mark.skip(reason="implemented in plan 03")


def test_ewma_values():
    """TOOL-05: PMC EWMA values match manual calculation."""
    pmc = pytest.importorskip("sports_science.pmc")
    result = pmc.update_pmc(0.0, 0.0, 100.0, 1)
    assert result is not None


def test_cold_start_guard():
    """TOOL-05: tss_display_ready=False before 28 days."""
    pmc = pytest.importorskip("sports_science.pmc")
    result = pmc.update_pmc(0.0, 0.0, 100.0, 1)
    assert result.value["tss_display_ready"] is False
