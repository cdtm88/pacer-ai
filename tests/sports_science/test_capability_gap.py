# tests/sports_science/test_capability_gap.py
import pytest

pytestmark = pytest.mark.skip(reason="implemented in plan 04")


def test_user_message_no_method_name():
    """TOOL-08: log_capability_gap returns user-safe string (no internal method_name)."""
    cap_gap = pytest.importorskip("sports_science.capability_gap")
    result = cap_gap.log_capability_gap("some_internal_method", {"key": "val"})
    assert "some_internal_method" not in result.value["message"]


def test_db_insert():
    """TOOL-08: log_capability_gap writes to capability_gaps table."""
    cap_gap = pytest.importorskip("sports_science.capability_gap")
    result = cap_gap.log_capability_gap("test_method", {"key": "val"})
    assert result.value["status"] == "logged"
