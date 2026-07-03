# tests/api/test_onboarding.py
"""
Onboarding route tests (Wave 2 / Plan 03-03).

Tests cover:
  - test_onboarding_returns_sse: POST /onboarding/start returns SSE stream (ONBD-01)
  - test_confirmation_gate: structural contract that save_profile only appears after
    the approval marker in the mock sequence (ONBD-04 D-03 gate)
  - test_back_status_constraint: save_profile with moderate back_status persists the
    correct constraints JSONB (ONBD-02)
  - test_profile_persisted: save_profile upserts to profiles table and returns saved=True
    (ONBD-03)

asyncio_mode = auto (pytest.ini) -- no @pytest.mark.asyncio needed.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from tests.api.conftest import TEST_USER_ID, parse_sse_frames, TEST_JWT_SECRET, auth_headers


# ---------------------------------------------------------------------------
# Mock run_turn helpers
# ---------------------------------------------------------------------------


async def _mock_interview_run_turn(messages, client, model, trust_scanner, audit_log, **kwargs):
    """
    Deterministic mock of run_turn for onboarding SSE tests.
    Simulates a complete coaching interview: token, tool_start, tool_result, done.
    Accepts **kwargs to absorb the system= keyword arg from sse_generator.
    """
    yield {"event": "token", "data": {"text": "What are your fitness goals?"}}
    yield {"event": "tool_start", "data": {"name": "save_profile", "tool_use_id": "t1"}}
    yield {
        "event": "tool_result",
        "data": {
            "tool_use_id": "t1",
            "name": "save_profile",
            "value": '{"saved": true}',
        },
    }
    yield {"event": "done", "data": {}}


async def _mock_interview_with_approval(messages, client, model, trust_scanner, audit_log, **kwargs):
    """
    Mock that simulates the approval gate sequence:
      1. Token with confirmation summary (includes 'Here is what I have')
      2. save_profile tool call AFTER the approval marker token
      3. done

    This validates the structural contract (D-03 / ONBD-04): save_profile
    must not appear before the approval confirmation.
    """
    # Step 1: Emit the confirmation summary token (approval marker)
    yield {"event": "token", "data": {"text": "Here is what I have collected so far..."}}
    # Step 2: Emit save_profile AFTER the approval marker (structurally correct)
    yield {"event": "tool_start", "data": {"name": "save_profile", "tool_use_id": "t2"}}
    yield {
        "event": "tool_result",
        "data": {
            "tool_use_id": "t2",
            "name": "save_profile",
            "value": '{"saved": true}',
        },
    }
    yield {"event": "done", "data": {}}


async def _mock_interview_save_without_approval(messages, client, model, trust_scanner, audit_log, **kwargs):
    """
    Mock that simulates a VIOLATION: save_profile called WITHOUT a prior approval marker.
    Used to confirm the structural test can distinguish compliant vs. non-compliant sequences.

    NOTE (manual-only verification): the actual gate is enforced by the LLM's adherence
    to ONBOARDING_SYSTEM_PROMPT. The structural test below asserts the CONTRACT using mocks.
    Whether the real LLM respects the gate requires manual verification (see 03-VALIDATION
    manual-only row ONBD-04-MANUAL). Cross-reference: tests only assert mock sequences.
    """
    # save_profile appears BEFORE any approval token -- violation sequence
    yield {"event": "tool_start", "data": {"name": "save_profile", "tool_use_id": "t3"}}
    yield {
        "event": "tool_result",
        "data": {
            "tool_use_id": "t3",
            "name": "save_profile",
            "value": '{"saved": true}',
        },
    }
    yield {"event": "done", "data": {}}


# ---------------------------------------------------------------------------
# Supabase mock helpers
# ---------------------------------------------------------------------------


def _make_onboarding_mock_supabase(conversation_id="conv-001"):
    """
    Return an async callable that produces a mock Supabase client capturing
    conversation inserts and returning a known conversation_id.
    """
    execute_result = MagicMock()
    execute_result.data = [{"id": conversation_id}]

    mock_client = MagicMock()
    mock_client.table.return_value = mock_client
    mock_client.select.return_value = mock_client
    mock_client.insert.return_value = mock_client
    mock_client.upsert.return_value = mock_client
    mock_client.eq.return_value = mock_client
    mock_client.order.return_value = mock_client
    mock_client.limit.return_value = mock_client
    mock_client.execute = AsyncMock(return_value=execute_result)

    async def _get_mock():
        return mock_client

    return _get_mock, mock_client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_onboarding_returns_sse(monkeypatch):
    """
    ONBD-01: POST /onboarding/start returns Content-Type: text/event-stream.
    Monkeypatches run_turn with _mock_interview_run_turn so no live API call.
    Monkeypatches _get_async_supabase so no live DB call.
    Phase 4: request requires a valid JWT in the Authorization: Bearer header.
    Asserts at least one token frame and one done frame in the parsed SSE output.
    """
    import httpx
    from httpx import ASGITransport
    from backend.main import app
    import backend.routes.onboarding as onboarding_module

    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)

    # Patch run_turn (used by sse_generator via _run_turn parameter)
    monkeypatch.setattr(onboarding_module, "run_turn", _mock_interview_run_turn)

    # Patch DB to avoid live Supabase call
    mock_factory, _ = _make_onboarding_mock_supabase()
    monkeypatch.setattr(onboarding_module, "_get_async_supabase", mock_factory)

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/onboarding/start",
            headers=auth_headers(),
        )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    frames = parse_sse_frames(response.text)
    event_types = [f["event"] for f in frames]

    assert "token" in event_types, f"Expected at least one token frame, got: {event_types}"
    assert "done" in event_types, f"Expected a done frame, got: {event_types}"


async def test_confirmation_gate(monkeypatch):
    """
    ONBD-04 / D-03: Structural contract assertion for the approval gate.

    The compliant mock (_mock_interview_with_approval) emits the 'Here is what I have'
    confirmation token BEFORE the save_profile tool_start event. The test asserts that
    in a compliant sequence the approval marker appears before save_profile.

    The non-compliant mock (_mock_interview_save_without_approval) emits save_profile
    WITHOUT an approval marker -- used to confirm the structural distinction is detectable.

    Phase 4: both requests require a valid JWT.

    Note: LLM gate enforcement (whether Claude actually respects the system prompt)
    is a manual-only verification (ONBD-04-MANUAL in 03-VALIDATION). This test only
    asserts the structural contract on mock sequences.
    """
    import httpx
    from httpx import ASGITransport
    from backend.main import app
    import backend.routes.onboarding as onboarding_module

    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)

    mock_factory, _ = _make_onboarding_mock_supabase()
    monkeypatch.setattr(onboarding_module, "_get_async_supabase", mock_factory)

    # --- Compliant sequence: approval token appears before save_profile ---
    monkeypatch.setattr(onboarding_module, "run_turn", _mock_interview_with_approval)

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/onboarding/start",
            headers=auth_headers(),
        )

    frames = parse_sse_frames(response.text)
    event_types = [f["event"] for f in frames]

    # Find index of the approval marker token ("Here is what I have")
    approval_idx = None
    for i, f in enumerate(frames):
        if f["event"] == "token" and "Here is what I have" in f["data"].get("text", ""):
            approval_idx = i
            break

    # Find index of first save_profile tool_start
    save_profile_idx = None
    for i, f in enumerate(frames):
        if f["event"] == "tool_start" and f["data"].get("name") == "save_profile":
            save_profile_idx = i
            break

    assert approval_idx is not None, "Compliant sequence must contain the approval marker token"
    assert save_profile_idx is not None, "Compliant sequence must contain save_profile tool_start"
    assert approval_idx < save_profile_idx, (
        f"Approval token (idx={approval_idx}) must appear BEFORE save_profile "
        f"tool_start (idx={save_profile_idx}) -- D-03 gate contract violated in compliant mock"
    )

    # --- Non-compliant sequence: save_profile appears without approval marker ---
    monkeypatch.setattr(onboarding_module, "run_turn", _mock_interview_save_without_approval)

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response2 = await client.post(
            "/onboarding/start",
            headers=auth_headers(),
        )

    frames2 = parse_sse_frames(response2.text)

    # Confirm NO approval marker token in the non-compliant sequence
    approval_tokens = [
        f for f in frames2
        if f["event"] == "token" and "Here is what I have" in f["data"].get("text", "")
    ]
    save_profile_events = [
        f for f in frames2
        if f["event"] == "tool_start" and f["data"].get("name") == "save_profile"
    ]
    assert len(approval_tokens) == 0, "Non-compliant sequence must have no approval token"
    assert len(save_profile_events) == 1, "Non-compliant sequence still emits save_profile (detectable)"


async def test_back_status_constraint(monkeypatch):
    """
    ONBD-02: save_profile with back_status='moderate' persists constraints JSONB
    equal to {"back_issues": True, "load_ramp_flag_threshold_pct": 10}.

    Calls save_profile directly with a mocked _get_async_supabase that captures
    the upsert payload.
    """
    import backend.sports_science.profile as profile_module

    # Track captured upsert payload
    captured_payload = {}

    # Build a mock chain that captures the upsert data argument
    execute_result = MagicMock()
    execute_result.data = [{"id": "profile-uuid-002"}]

    mock_client = MagicMock()
    mock_client.table.return_value = mock_client

    def capture_upsert(data, **kwargs):
        captured_payload.update(data)
        return mock_client

    mock_client.upsert.side_effect = capture_upsert
    mock_client.execute = AsyncMock(return_value=execute_result)

    monkeypatch.setattr(profile_module, "_supabase_client", mock_client)

    from backend.sports_science.profile import save_profile

    result = await save_profile(
        user_id=TEST_USER_ID,
        fitness_goals="fitness and weight loss",
        weekly_hours=3.0,
        preferred_days=["Tuesday", "Thursday", "Saturday"],
        back_status="moderate",
        equipment={"trainer": "Wahoo Kickr Core", "platform": "Zwift"},
        rpe_baseline="beginner",
        lthr_estimate=None,
    )

    expected_constraints = {"back_issues": True, "load_ramp_flag_threshold_pct": 10}
    assert captured_payload.get("constraints") == expected_constraints, (
        f"Expected constraints {expected_constraints}, got {captured_payload.get('constraints')}"
    )
    assert captured_payload.get("back_status") == "moderate"


async def test_plan_calendar_sync_inline_await(monkeypatch):
    """
    DEPLOY-BG-01: POST /onboarding/plan-calendar-sync inline-awaits
    push_all_sessions_to_calendar before returning (no BackgroundTasks scheduling).

    Asserts:
      - push_all_sessions_to_calendar is awaited exactly once with the authenticated user_id
      - the response body reports completion, not scheduling (CAL-01)
      - onboarding_plan_calendar_sync no longer declares a background_tasks parameter --
        the deterministic RED signal that the route still depends on FastAPI BackgroundTasks
        (fails against current code, which schedules via background_tasks.add_task and
        still declares the parameter)
    """
    import inspect
    import httpx
    from httpx import ASGITransport
    from backend.main import app
    import backend.routes.onboarding as onboarding_module

    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)

    mock_push = AsyncMock(return_value=None)
    monkeypatch.setattr(onboarding_module, "push_all_sessions_to_calendar", mock_push)

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/onboarding/plan-calendar-sync",
            headers=auth_headers(),
        )

    assert response.status_code == 200
    mock_push.assert_awaited_once_with(TEST_USER_ID)

    body = response.json()
    assert body.get("status") != "scheduled", f"Expected an inline-completed status, got: {body}"
    assert body.get("status") == "completed"

    sig = inspect.signature(onboarding_module.onboarding_plan_calendar_sync)
    assert "background_tasks" not in sig.parameters, (
        "onboarding_plan_calendar_sync must not declare a background_tasks parameter "
        "after the inline-await conversion (DEPLOY-BG-01)"
    )


async def test_resolve_conversation_id_rejects_malformed_id(monkeypatch):
    """
    WR-08 (07-REVIEW.md): a malformed conversation_id (not a valid UUID) must be
    treated as absent, not passed through to the DB layer as-is.
    """
    import backend.routes.onboarding as onboarding_module

    async def _unexpected_supabase():
        raise AssertionError("must not query Supabase for a malformed conversation_id")

    monkeypatch.setattr(onboarding_module, "_get_async_supabase", _unexpected_supabase)

    result = await onboarding_module._resolve_conversation_id(TEST_USER_ID, "not-a-uuid")
    assert result is None


async def test_resolve_conversation_id_rejects_foreign_id(monkeypatch):
    """
    WR-08 (07-REVIEW.md): a well-formed conversation_id that does not belong to the
    requesting user (ownership check returns no rows) must be treated as absent.
    """
    import backend.routes.onboarding as onboarding_module

    foreign_id = "11111111-1111-1111-1111-111111111111"

    execute_empty = MagicMock()
    execute_empty.data = []

    mock_client = MagicMock()
    mock_client.table.return_value = mock_client
    mock_client.select.return_value = mock_client
    mock_client.eq.return_value = mock_client
    mock_client.execute = AsyncMock(return_value=execute_empty)

    async def _mock_supabase():
        return mock_client

    monkeypatch.setattr(onboarding_module, "_get_async_supabase", _mock_supabase)

    result = await onboarding_module._resolve_conversation_id(TEST_USER_ID, foreign_id)
    assert result is None


async def test_resolve_conversation_id_accepts_owned_id(monkeypatch):
    """
    WR-08 (07-REVIEW.md): a well-formed conversation_id owned by the requesting user
    (ownership check returns a row) is retained as resumable.
    """
    import backend.routes.onboarding as onboarding_module

    owned_id = "22222222-2222-2222-2222-222222222222"

    execute_found = MagicMock()
    execute_found.data = [{"id": owned_id}]

    mock_client = MagicMock()
    mock_client.table.return_value = mock_client
    mock_client.select.return_value = mock_client
    mock_client.eq.return_value = mock_client
    mock_client.execute = AsyncMock(return_value=execute_found)

    async def _mock_supabase():
        return mock_client

    monkeypatch.setattr(onboarding_module, "_get_async_supabase", _mock_supabase)

    result = await onboarding_module._resolve_conversation_id(TEST_USER_ID, owned_id)
    assert result == owned_id


async def test_profile_persisted(monkeypatch):
    """
    ONBD-03: save_profile upserts to the profiles table with on_conflict=user_id
    and returns ToolResult with saved=True.

    Monkeypatches _supabase_client directly (bypasses _get_async_supabase) so
    the mock is used without live Supabase.
    """
    import backend.sports_science.profile as profile_module

    execute_result = MagicMock()
    execute_result.data = [{"id": "profile-uuid-003"}]

    mock_client = MagicMock()
    mock_client.table.return_value = mock_client
    mock_client.upsert.return_value = mock_client
    mock_client.execute = AsyncMock(return_value=execute_result)

    monkeypatch.setattr(profile_module, "_supabase_client", mock_client)

    from backend.sports_science.profile import save_profile

    result = await save_profile(
        user_id=TEST_USER_ID,
        fitness_goals="weight loss",
        weekly_hours=4.0,
        preferred_days=["Monday", "Wednesday", "Friday", "Sunday"],
        back_status="none",
        equipment={"trainer": "Wahoo Kickr Core", "platform": "Zwift"},
        rpe_baseline="beginner",
        lthr_estimate=None,
    )

    # Verify upsert was called on the profiles table
    mock_client.table.assert_called_with("profiles")
    mock_client.upsert.assert_called_once()
    upsert_args = mock_client.upsert.call_args

    # Verify on_conflict=user_id
    assert upsert_args.kwargs.get("on_conflict") == "user_id", (
        f"Expected on_conflict='user_id', got: {upsert_args}"
    )

    # Verify ToolResult
    assert result.value["saved"] is True, f"Expected saved=True, got {result.value}"
    assert result.value["profile_id"] == "profile-uuid-003"
