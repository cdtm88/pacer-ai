# tests/sports_science/test_types.py
import pytest
from pydantic import ValidationError

from backend.sports_science.types import ToolResult


def test_toolresult_constructs():
    """Test 1: ToolResult constructs with all required fields."""
    result = ToolResult(value=1, unit="watts", methodology="m", inputs={})
    assert result.value == 1
    assert result.unit == "watts"
    assert result.methodology == "m"
    assert result.inputs == {}


def test_model_dump_keys():
    """Test 2: .model_dump() returns a dict with exactly the required keys."""
    result = ToolResult(value=1, unit="watts", methodology="m", inputs={})
    d = result.model_dump()
    assert set(d.keys()) == {"value", "unit", "methodology", "inputs"}


def test_to_tool_response_equals_model_dump():
    """Test 3: .to_tool_response() equals .model_dump()."""
    result = ToolResult(value=42, unit="TSS", methodology="m", inputs={"ftp": 200})
    assert result.to_tool_response() == result.model_dump()


def test_toolresult_is_frozen():
    """Test 4: ToolResult is frozen -- assigning to .value after construction raises."""
    result = ToolResult(value=1, unit="watts", methodology="m", inputs={})
    with pytest.raises((ValidationError, TypeError)):
        result.value = 999  # type: ignore[misc]


def test_value_accepts_none():
    """Test 5: value accepts None (sparse-data contract D-04)."""
    result = ToolResult(value=None, unit="watts", methodology="m", inputs={})
    assert result.value is None
