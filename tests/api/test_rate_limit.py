# tests/api/test_rate_limit.py
"""
Unit tests for backend/rate_limit.py (item 6, D-02/D-03).

Covers the sliding-window token bucket keyed by user_id:
  - The (MAX_REQUESTS_PER_WINDOW + 1)th call within the window is rejected.
  - Two distinct user_ids have independent budgets.
  - is_rate_limited flips to True only after the budget is spent.
  - rate_limited_user raises HTTPException(429) with the structured detail
    once over limit.

asyncio_mode = auto (pytest.ini) -- no @pytest.mark.asyncio needed.
"""
import pytest
from fastapi import HTTPException

import backend.rate_limit as rate_limit_module
from backend.rate_limit import (
    MAX_REQUESTS_PER_WINDOW,
    _check_and_record,
    is_rate_limited,
    rate_limited_user,
)


@pytest.fixture(autouse=True)
def _reset_rate_limit_log():
    """Clear the module-level request log between tests to avoid cross-test bleed."""
    rate_limit_module._request_log.clear()
    yield
    rate_limit_module._request_log.clear()


def test_nth_plus_one_call_is_limited():
    """
    MAX_REQUESTS_PER_WINDOW calls to _check_and_record return True; the next
    (N+1th) call returns False.
    """
    user_id = "user-a"
    for i in range(MAX_REQUESTS_PER_WINDOW):
        assert _check_and_record(user_id) is True, f"call {i} should be allowed"
    assert _check_and_record(user_id) is False, "the (N+1)th call must be rejected"


def test_two_user_ids_have_independent_budgets():
    """Exhausting one user_id's budget must not affect a different user_id."""
    user_a = "user-a"
    user_b = "user-b"
    for _ in range(MAX_REQUESTS_PER_WINDOW):
        assert _check_and_record(user_a) is True
    assert _check_and_record(user_a) is False

    # user_b is unaffected -- independent budget.
    for i in range(MAX_REQUESTS_PER_WINDOW):
        assert _check_and_record(user_b) is True, f"user_b call {i} should be allowed"
    assert _check_and_record(user_b) is False


def test_is_rate_limited_flips_true_only_after_budget_spent():
    """is_rate_limited returns False while under limit, True once over."""
    user_id = "user-c"
    for _ in range(MAX_REQUESTS_PER_WINDOW):
        assert is_rate_limited(user_id) is False
    assert is_rate_limited(user_id) is True


async def test_rate_limited_user_raises_429_once_over_limit():
    """
    rate_limited_user returns current_user while under limit, and raises
    HTTPException(429) with the structured {"error": "rate_limited", ...}
    detail once over.
    """
    user_id = "user-d"
    stub_user = {"user_id": user_id, "email": "test@example.com"}

    async def _stub_get_current_user():
        return stub_user

    # rate_limited_user's Depends default resolves get_current_user, but we
    # can call the function directly passing current_user explicitly since
    # it's a plain async function (FastAPI only wires Depends() at request time).
    for _ in range(MAX_REQUESTS_PER_WINDOW):
        result = await rate_limited_user(current_user=stub_user)
        assert result == stub_user

    with pytest.raises(HTTPException) as exc_info:
        await rate_limited_user(current_user=stub_user)

    assert exc_info.value.status_code == 429
    assert exc_info.value.detail["error"] == "rate_limited"
    assert "detail" in exc_info.value.detail
