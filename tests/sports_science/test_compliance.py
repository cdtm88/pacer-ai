# tests/sports_science/test_compliance.py
import pytest

pytestmark = pytest.mark.skip(reason="implemented in plan 04")


def test_compliance_pct():
    """TOOL-07: Compliance percentage calculation."""
    compliance = pytest.importorskip("sports_science.compliance")
    result = compliance.validate_session_vs_actual(
        {"tss": 80},
        {"tss": 60},
    )
    assert result is not None
