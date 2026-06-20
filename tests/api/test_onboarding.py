# tests/api/test_onboarding.py
"""
Onboarding route tests (Wave 2).

Most tests are stubs (skipped) pending Wave 2 router implementation.
The mock_interview_run_turn and parse_sse_frames helpers are defined
here so Wave 2 can reuse them without reimplementation.

asyncio_mode = auto (pytest.ini) -- no @pytest.mark.asyncio needed.
"""
import pytest

from tests.api.conftest import TEST_USER_ID, parse_sse_frames


# ---------------------------------------------------------------------------
# Mock run_turn for onboarding tests (Wave 2 reuses this)
# ---------------------------------------------------------------------------


async def _mock_interview_run_turn(messages, client, model, trust_scanner, audit_log):
    """
    Deterministic mock of run_turn for onboarding SSE tests.
    Simulates a coaching interview with save_profile tool call.
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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="Wave 2 implements: onboarding router not yet created")
async def test_onboarding_returns_sse(monkeypatch):
    """
    Wave 2: POST /onboarding/start returns Content-Type: text/event-stream.
    Monkeypatches run_turn with _mock_interview_run_turn.
    """
    import httpx
    from httpx import ASGITransport
    from api.main import app
    import api.routes.onboarding as onboarding_module

    monkeypatch.setattr(onboarding_module, "run_turn", _mock_interview_run_turn)

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post("/onboarding/start", json={"user_id": TEST_USER_ID})

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    frames = parse_sse_frames(response.text)
    assert len(frames) > 0


@pytest.mark.skip(reason="Wave 2 implements: onboarding router not yet created")
async def test_back_status_constraint(monkeypatch):
    """
    Wave 2: Back status is validated as none/mild/moderate; invalid value rejected with 422.
    """
    pass


@pytest.mark.skip(reason="Wave 2 implements: onboarding router not yet created")
async def test_profile_persisted(monkeypatch):
    """
    Wave 2: save_profile is called with the collected interview data after user confirmation.
    """
    pass


@pytest.mark.skip(reason="Wave 2 implements: confirmation gate (D-03) not yet implemented")
async def test_confirmation_gate(monkeypatch):
    """
    Wave 2: D-03 gate -- save_profile is only called after explicit user approval.
    A confirmation message triggers the save; earlier messages do not.
    """
    pass
