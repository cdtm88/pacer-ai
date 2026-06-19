# tests/sports_science/test_capability_gap.py
"""
TDD tests for sports_science.capability_gap.log_capability_gap (TOOL-08, GAP-01/02/03).
The Supabase client is patched so no network call happens in unit tests.
Live DB insert is verified in the human checkpoint (Task 4).
"""
import pytest
from unittest.mock import MagicMock, patch


def _make_mock_supabase():
    """Return a mock Supabase client that silently accepts inserts."""
    client = MagicMock()
    client.table.return_value.insert.return_value.execute.return_value = MagicMock()
    return client


@patch("sports_science.capability_gap._get_supabase")
def test_user_message_no_method_name(mock_get_supabase):
    """GAP-03: user-facing message must NOT contain the internal method name."""
    mock_get_supabase.return_value = _make_mock_supabase()
    from sports_science.capability_gap import log_capability_gap

    result = log_capability_gap("estimate_vo2max", {"foo": "bar"})
    message = result.value["message"]
    assert isinstance(message, str) and len(message) > 0, "message must be a non-empty string"
    assert "estimate_vo2max" not in message, (
        f"Internal method name leaked into user-facing message: {message!r}"
    )


@patch("sports_science.capability_gap._get_supabase")
def test_returns_tool_result(mock_get_supabase):
    """TOOL-09: log_capability_gap returns a ToolResult with all required keys."""
    mock_get_supabase.return_value = _make_mock_supabase()
    from sports_science.capability_gap import log_capability_gap
    from sports_science.types import ToolResult

    result = log_capability_gap("some_method", {"key": "value"})

    assert isinstance(result, ToolResult), "must return a ToolResult instance"
    # ToolResult contract: value, unit, methodology, inputs
    assert hasattr(result, "value")
    assert hasattr(result, "unit")
    assert hasattr(result, "methodology")
    assert hasattr(result, "inputs")
    assert result.value["status"] == "logged"
    assert "message" in result.value


@patch("sports_science.capability_gap._get_supabase")
def test_inputs_no_secret(mock_get_supabase):
    """Security: inputs must contain only context_keys (key names), not values or secrets."""
    mock_get_supabase.return_value = _make_mock_supabase()
    from sports_science.capability_gap import log_capability_gap

    context = {"athlete_weight": 72, "power_data": [100, 200, 300]}
    result = log_capability_gap("secret_method", context, user_id="user-123")

    inputs = result.inputs
    assert "context_keys" in inputs, "inputs must have context_keys"
    # Only key names — not values, not the service-role key
    assert set(inputs["context_keys"]) == set(context.keys())
    # Values must NOT appear in inputs
    assert "athlete_weight" not in str(inputs.get("context_keys", [])) or \
        inputs["context_keys"] == list(context.keys()), \
        "context_keys should be key names only"
    # Service-role key must not be in inputs
    assert "SUPABASE_SERVICE_ROLE_KEY" not in str(inputs)
    assert "service_role" not in str(inputs)


@patch("sports_science.capability_gap._get_supabase")
def test_supabase_insert_called_with_correct_fields(mock_get_supabase):
    """GAP-01: structured row inserted with method_name, description, context."""
    mock_client = _make_mock_supabase()
    mock_get_supabase.return_value = mock_client
    from sports_science.capability_gap import log_capability_gap

    log_capability_gap("missing_tool", {"a": 1}, user_id="uid-abc")

    mock_client.table.assert_called_once_with("capability_gaps")
    insert_call = mock_client.table.return_value.insert
    call_args = insert_call.call_args[0][0]  # first positional arg to insert()
    assert call_args["method_name"] == "missing_tool"
    assert "Missing tool:" in call_args["description"]
    assert call_args["context"] == {"a": 1}
    assert call_args["user_id"] == "uid-abc"


@patch("sports_science.capability_gap._get_supabase")
def test_never_computes_physiological_number(mock_get_supabase):
    """GAP-02: log_capability_gap must not return a physiological number — only a logged status."""
    mock_get_supabase.return_value = _make_mock_supabase()
    from sports_science.capability_gap import log_capability_gap

    result = log_capability_gap("estimate_ftp", {"rides": [{"tss": 50}]})

    # value must be a status dict, not a numeric physiological value
    assert isinstance(result.value, dict), "value must be a dict (status), not a number"
    assert result.value.get("status") == "logged"
    # methodology must signal this is a gap log, not a calculation
    assert "capability_gap" in result.methodology
