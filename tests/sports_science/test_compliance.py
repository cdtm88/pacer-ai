# tests/sports_science/test_compliance.py
import pytest
from sports_science.compliance import validate_session_vs_actual
from sports_science.types import ToolResult


# --------------------------------------------------------------------------- #
# TOOL-07: Session compliance percentage, delta, and flags
# --------------------------------------------------------------------------- #


def test_compliance_pct():
    """TOOL-07: planned=100, actual=80 -> compliance_pct=80.0, delta_tss=-20.0."""
    result = validate_session_vs_actual({"tss": 100}, {"tss": 80})
    assert result.value["compliance_pct"] == pytest.approx(80.0)
    assert result.value["delta_tss"] == pytest.approx(-20.0)


def test_under_performed_flag():
    """compliance_pct < 70 -> 'under_performed' flag."""
    result = validate_session_vs_actual({"tss": 100}, {"tss": 60})
    assert "under_performed" in result.value["flags"]
    assert "over_performed" not in result.value["flags"]


def test_over_performed_flag():
    """compliance_pct > 130 -> 'over_performed' flag."""
    result = validate_session_vs_actual({"tss": 100}, {"tss": 140})
    assert "over_performed" in result.value["flags"]
    assert "under_performed" not in result.value["flags"]


def test_no_flags_within_normal_range():
    """compliance_pct 70-130 -> no performance flags."""
    result = validate_session_vs_actual({"tss": 100}, {"tss": 100})
    assert result.value["flags"] == []


def test_zero_planned_tss():
    """T-01-07: planned_tss=0 -> compliance_pct=None (no zero-division error)."""
    result = validate_session_vs_actual({"tss": 0}, {"tss": 50})
    assert result.value["compliance_pct"] is None


def test_zero_planned_tss_no_exception():
    """T-01-07: planned_tss=0 must not raise ZeroDivisionError."""
    try:
        validate_session_vs_actual({"tss": 0}, {"tss": 0})
    except ZeroDivisionError:
        pytest.fail("validate_session_vs_actual raised ZeroDivisionError on planned_tss=0")


def test_returns_tool_result():
    """TOOL-09: validate_session_vs_actual must return ToolResult."""
    result = validate_session_vs_actual({"tss": 100}, {"tss": 80})
    assert isinstance(result, ToolResult)


def test_methodology_string():
    """methodology string must describe the compliance calculation."""
    result = validate_session_vs_actual({"tss": 100}, {"tss": 80})
    assert "compliance" in result.methodology.lower() or "TSS" in result.methodology


def test_delta_tss_positive_when_over():
    """actual > planned -> positive delta_tss."""
    result = validate_session_vs_actual({"tss": 80}, {"tss": 100})
    assert result.value["delta_tss"] == pytest.approx(20.0)


def test_missing_tss_keys_default_to_zero():
    """Missing 'tss' keys default to 0 via .get; no KeyError."""
    result = validate_session_vs_actual({}, {})
    assert result.value["compliance_pct"] is None
    assert result.value["delta_tss"] == pytest.approx(0.0)
