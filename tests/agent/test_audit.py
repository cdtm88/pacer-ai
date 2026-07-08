# tests/agent/test_audit.py
"""
TDD tests for backend.agent.audit (TRUST-06, TRUST-04, D-01/D-04).

write_audit_entry: best-effort per-dispatch write to the new audit_log table.
load_prior_audit_values: conversation-scoped reload of prior tool-result JSON
strings, used to re-seed trust-scanner attribution across turns (D-04).

The Supabase async client is patched via backend.agent.audit.get_async_supabase
(imported directly from backend.db, per backend/db.py's "Test monkeypatching"
docstring) so no network call happens in unit tests.
asyncio_mode = auto (pytest.ini) means async test functions run without
explicit marks.
"""
import json
from unittest.mock import AsyncMock, MagicMock


def _make_mock_insert_client():
    """Return a mock AsyncClient whose insert chain silently succeeds.

    Chain: client.table("audit_log").insert({...}).execute()
    """
    execute_mock = AsyncMock(return_value=MagicMock())
    insert_mock = MagicMock()
    insert_mock.execute = execute_mock
    table_mock = MagicMock()
    table_mock.insert.return_value = insert_mock
    client = MagicMock()
    client.table.return_value = table_mock
    return client, table_mock


def _make_mock_select_client(rows: list[dict]):
    """Return a mock AsyncClient whose select/order chain returns given rows.

    Chain: client.table("audit_log").select("result").eq(...).eq(...)
           .order("created_at").execute()
    All chain methods return self so any call order/count works.
    """
    execute_mock = AsyncMock(return_value=MagicMock(data=rows))

    class _Query:
        def __init__(self):
            self.eq_calls = []

        def eq(self, key, value):
            self.eq_calls.append((key, value))
            return self

        def order(self, *args, **kwargs):
            return self

        async def execute(self):
            return await execute_mock()

    query = _Query()
    table_mock = MagicMock()
    table_mock.select.return_value = query
    client = MagicMock()
    client.table.return_value = table_mock
    return client, query


async def test_write_audit_entry_inserts_one_row(monkeypatch):
    """write_audit_entry inserts exactly one audit_log row with all expected keys."""
    import backend.agent.audit as audit_module

    client, table_mock = _make_mock_insert_client()

    async def _mock_get_async_supabase():
        return client

    monkeypatch.setattr(audit_module, "get_async_supabase", _mock_get_async_supabase)

    await audit_module.write_audit_entry(
        user_id="user-1",
        conversation_id="conv-1",
        tool_use_id="toolu_1",
        tool_name="update_pmc",
        inputs={"date": "2026-07-04"},
        result={"ctl": 42.0},
        is_error=False,
    )

    client.table.assert_called_once_with("audit_log")
    table_mock.insert.assert_called_once()
    inserted = table_mock.insert.call_args[0][0]
    assert inserted["user_id"] == "user-1"
    assert inserted["conversation_id"] == "conv-1"
    assert inserted["tool_use_id"] == "toolu_1"
    assert inserted["tool_name"] == "update_pmc"
    assert inserted["inputs"] == {"date": "2026-07-04"}
    assert inserted["result"] == {"ctl": 42.0}
    assert inserted["is_error"] is False


async def test_write_audit_entry_swallows_insert_exception(monkeypatch):
    """write_audit_entry must not raise when the awaited insert raises (best-effort, D-14)."""
    import backend.agent.audit as audit_module

    execute_mock = AsyncMock(side_effect=Exception("DB connection failed"))
    insert_mock = MagicMock()
    insert_mock.execute = execute_mock
    table_mock = MagicMock()
    table_mock.insert.return_value = insert_mock
    client = MagicMock()
    client.table.return_value = table_mock

    async def _mock_get_async_supabase():
        return client

    monkeypatch.setattr(audit_module, "get_async_supabase", _mock_get_async_supabase)

    # Should not raise even though the DB write fails.
    result = await audit_module.write_audit_entry(
        user_id="user-1",
        conversation_id="conv-1",
        tool_use_id="toolu_1",
        tool_name="update_pmc",
        inputs={},
        result=None,
        is_error=True,
    )
    assert result is None


async def test_load_prior_audit_values_empty_conversation(monkeypatch):
    """load_prior_audit_values returns [] for a conversation with no rows."""
    import backend.agent.audit as audit_module

    client, query = _make_mock_select_client([])

    async def _mock_get_async_supabase():
        return client

    monkeypatch.setattr(audit_module, "get_async_supabase", _mock_get_async_supabase)

    values = await audit_module.load_prior_audit_values("conv-empty", user_id="user-1")
    assert values == []


async def test_load_prior_audit_values_returns_result_json_strings(monkeypatch):
    """load_prior_audit_values returns the prior tool-result JSON strings, ordered."""
    import backend.agent.audit as audit_module

    rows = [
        {"result": {"ctl": 41.5}},
        {"result": {"ftp_watts": 210, "confidence": "high"}},
    ]
    client, query = _make_mock_select_client(rows)

    async def _mock_get_async_supabase():
        return client

    monkeypatch.setattr(audit_module, "get_async_supabase", _mock_get_async_supabase)

    values = await audit_module.load_prior_audit_values("conv-1", user_id="user-1")

    assert len(values) == 2
    # The recognisable ctl value must appear in the serialised string a
    # downstream trust-scanner attribution check would scan against.
    assert "41.5" in values[0]
    assert json.loads(values[0]) == {"ctl": 41.5}
    assert "210" in values[1]


async def test_load_prior_audit_values_enforces_user_id_filter(monkeypatch):
    """load_prior_audit_values re-enforces .eq('user_id', user_id) at the app layer."""
    import backend.agent.audit as audit_module

    client, query = _make_mock_select_client([])

    async def _mock_get_async_supabase():
        return client

    monkeypatch.setattr(audit_module, "get_async_supabase", _mock_get_async_supabase)

    await audit_module.load_prior_audit_values("conv-1", user_id="user-42")

    assert ("user_id", "user-42") in query.eq_calls
    assert ("conversation_id", "conv-1") in query.eq_calls


async def test_load_prior_audit_values_never_raises(monkeypatch):
    """load_prior_audit_values returns [] on any failure, never raises."""
    import backend.agent.audit as audit_module

    async def _mock_get_async_supabase():
        raise Exception("DB unavailable")

    monkeypatch.setattr(audit_module, "get_async_supabase", _mock_get_async_supabase)

    values = await audit_module.load_prior_audit_values("conv-1", user_id="user-1")
    assert values == []


async def test_load_prior_audit_values_skips_null_results(monkeypatch):
    """Rows whose result is None (error rows) are skipped, not serialised as 'null'."""
    import backend.agent.audit as audit_module

    rows = [{"result": None}, {"result": {"ctl": 30.0}}]
    client, query = _make_mock_select_client(rows)

    async def _mock_get_async_supabase():
        return client

    monkeypatch.setattr(audit_module, "get_async_supabase", _mock_get_async_supabase)

    values = await audit_module.load_prior_audit_values("conv-1", user_id="user-1")
    assert len(values) == 1
    assert json.loads(values[0]) == {"ctl": 30.0}
