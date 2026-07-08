# backend/rate_limit.py
"""
In-process, best-effort rate limiter for LLM-backed endpoints (D-02, D-03).

Not a distributed guarantee: Vercel Fluid Compute may reuse instances across
requests but does not guarantee a single shared instance, so this can
under-count across cold starts / multiple warm instances. That is an accepted
tradeoff for a single-user personal app (D-02) -- this is a cost/abuse safety
net against a runaway retry loop, not hardened multi-tenant infrastructure.

This is deliberately hand-rolled rather than a third-party rate-limiting
library (see 10-RESEARCH.md's Package Legitimacy Audit and Pitfall 5 for the
rejected candidate and why its decorator/key_func model doesn't fit this
app's Depends(get_current_user)-first auth pattern without an awkward
request.state side-channel). A ~30-line sliding-window token bucket keyed
by user_id is simpler and sufficient here.
"""
import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException

from backend.auth import get_current_user

# user_id -> deque of request timestamps within the current window
_request_log: dict[str, deque] = defaultdict(deque)

WINDOW_SECS = 60
MAX_REQUESTS_PER_WINDOW = 10  # Claude's discretion per D-03; generous enough
                              # not to interrupt normal chat/onboarding use


def _check_and_record(user_id: str) -> bool:
    """Returns True if the request is allowed (and records it); False if over the limit."""
    now = time.monotonic()
    log = _request_log[user_id]
    while log and now - log[0] > WINDOW_SECS:
        log.popleft()
    if len(log) >= MAX_REQUESTS_PER_WINDOW:
        return False
    log.append(now)
    return True


async def rate_limited_user(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    Dependency for JSON-response endpoints (onboarding/start): raises a real
    HTTP 429 with a structured body the frontend's existing !res.ok branch
    can read (per 10-UI-SPEC.md).
    """
    if not _check_and_record(current_user["user_id"]):
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limited",
                "detail": "You're sending messages a bit fast. Wait a moment and try again.",
            },
        )
    return current_user


def is_rate_limited(user_id: str) -> bool:
    """
    Non-raising check for streaming endpoints (chat/stream), where a 429
    status can't be used mid-stream -- the caller returns a StreamingResponse
    yielding an `error` frame instead (see chat.py's existing
    _invalid_conversation_stream pattern).
    """
    return not _check_and_record(user_id)
