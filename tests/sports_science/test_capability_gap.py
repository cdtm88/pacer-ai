# tests/sports_science/test_capability_gap.py
"""
TDD tests for sports_science.capability_gap.log_capability_gap (TOOL-08, GAP-01/02/03).
The Supabase async client is patched so no network call happens in unit tests.
asyncio_mode = auto (pytest.ini) means async test functions run without explicit marks.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_mock_async_supabase():
    """Return a mock AsyncClient that silently accepts awaited inserts."""
    client = AsyncMock()
    # acreate_client is awaitable and returns the client
    client.table.return_value.insert.return_value.execute = AsyncMock(
        return_value=MagicMock()
    )
    return client


@patch("sports_science.capability_gap.acreate_client", new_callable=AsyncMock)
async def test_user_message_no_method_name(mock_acreate_client):
    """GAP-03: user-facing message must NOT contain the internal method name."""
    mock_acreate_client.return_value = _make_mock_async_supabase()
    from sports_science.capability_gap import log_capability_gap

    result = await log_capability_gap("estimate_vo2max", {"foo": "bar"})
    message = result.value["message"]
    assert isinstance(message, str) and len(message) > 0, "message must be a non-empty string"
    assert "estimate_vo2max" not in message, (
        f"Internal method name leaked into user-facing message: {message!r}"
    )


@patch("sports_science.capability_gap.acreate_client", new_callable=AsyncMock)
async def test_returns_tool_result(mock_acreate_client):
    """TOOL-09: log_capability_gap returns a ToolResult with all required keys."""
    mock_acreate_client.return_value = _make_mock_async_supabase()
    from sports_science.capability_gap import log_capability_gap
    from sports_science.types import ToolResult

    result = await log_capability_gap("some_method", {"key": "value"})

    assert isinstance(result, ToolResult), "must return a ToolResult instance"
    assert hasattr(result, "value")
    assert hasattr(result, "unit")
    assert hasattr(result, "methodology")
    assert hasattr(result, "inputs")
    assert result.value["status"] == "logged"
    assert "message" in result.value


@patch("sports_science.capability_gap.acreate_client", new_callable=AsyncMock)
async def test_inputs_no_secret(mock_acreate_client):
    """Security: inputs must contain only context_keys (key names), not values or secrets."""
    mock_acreate_client.return_value = _make_mock_async_supabase()
    from sports_science.capability_gap import log_capability_gap

    context = {"athlete_weight": 72, "power_data": [100, 200, 300]}
    result = await log_capability_gap("secret_method", context, user_id="user-123")

    inputs = result.inputs
    assert "context_keys" in inputs, "inputs must have context_keys"
    assert set(inputs["context_keys"]) == set(context.keys())
    assert "SUPABASE_SERVICE_ROLE_KEY" not in str(inputs)
    assert "service_role" not in str(inputs)


@patch("sports_science.capability_gap.acreate_client", new_callable=AsyncMock)
async def test_supabase_insert_called_with_correct_fields(mock_acreate_client):
    """GAP-01: structured row inserted with method_name, description, context."""
    mock_client = _make_mock_async_supabase()
    mock_acreate_client.return_value = mock_client
    from sports_science.capability_gap import log_capability_gap

    await log_capability_gap("missing_tool", {"a": 1}, user_id="uid-abc")

    mock_client.table.assert_called_once_with("capability_gaps")
    insert_call = mock_client.table.return_value.insert
    call_args = insert_call.call_args[0][0]
    assert call_args["method_name"] == "missing_tool"
    assert "Missing tool:" in call_args["description"]
    assert call_args["context"] == {"a": 1}
    assert call_args["user_id"] == "uid-abc"


@patch("sports_science.capability_gap.acreate_client", new_callable=AsyncMock)
async def test_never_computes_physiological_number(mock_acreate_client):
    """GAP-02: log_capability_gap must not return a physiological number."""
    mock_acreate_client.return_value = _make_mock_async_supabase()
    from sports_science.capability_gap import log_capability_gap

    result = await log_capability_gap("estimate_ftp", {"rides": [{"tss": 50}]})

    assert isinstance(result.value, dict), "value must be a dict (status), not a number"
    assert result.value.get("status") == "logged"
    assert "capability_gap" in result.methodology


@patch("sports_science.capability_gap.acreate_client", new_callable=AsyncMock)
async def test_methodology_is_capability_gap_log(mock_acreate_client):
    """Methodology field must equal 'capability_gap_log'."""
    mock_acreate_client.return_value = _make_mock_async_supabase()
    from sports_science.capability_gap import log_capability_gap

    result = await log_capability_gap("some_tool", {"x": 1})
    assert result.methodology == "capability_gap_log"


@patch("sports_science.capability_gap.acreate_client", new_callable=AsyncMock)
async def test_db_error_returns_fallback_tool_result(mock_acreate_client):
    """GAP-02: DB insert failure must not prevent returning the fallback ToolResult."""
    mock_client = AsyncMock()
    mock_client.table.return_value.insert.return_value.execute = AsyncMock(
        side_effect=Exception("DB connection failed")
    )
    mock_acreate_client.return_value = mock_client
    from sports_science.capability_gap import log_capability_gap
    from sports_science.types import ToolResult

    # Should not raise even when DB fails
    result = await log_capability_gap("some_tool", {"key": "val"})
    assert isinstance(result, ToolResult)
    assert result.value["status"] == "logged"


def test_log_capability_gap_is_coroutine():
    """log_capability_gap must be an async coroutine function."""
    from sports_science.capability_gap import log_capability_gap
    assert asyncio.iscoroutinefunction(log_capability_gap), (
        "log_capability_gap must be async def"
    )
