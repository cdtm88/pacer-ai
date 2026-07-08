# Phase 10: Hygiene and Safety Nets - Pattern Map

**Mapped:** 2026-07-08
**Files analyzed:** 13
**Analogs found:** 12 / 13

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|----------------|
| `tests/agent/test_sse.py` (fix) | test | streaming | itself (existing file, pattern from `tests/api/test_chat.py`) | exact |
| `tests/sports_science/conftest.py` (extend) | test/fixture | event-driven | itself — existing `_reset_capability_gap_client` fixture | exact |
| `backend/sports_science/profile.py` (add reset hook) | service | CRUD | `backend/sports_science/capability_gap.py` | exact |
| `frontend/tests/e2e/full-uat.spec.ts`, `phase4.spec.ts` (fix mocks) | test | request-response | same files (backend `backend/routes/rides.py` is the shape source of truth) | exact |
| `tests/api/test_contracts.py` (new) | test | request-response | `tests/api/test_chat.py` / other `tests/api/*.py` | exact |
| `backend/routes/chat.py` — `POST /chat/token` (new endpoint) | controller/route | request-response | existing handlers in same file (`create_chat_conversation`) | exact |
| `backend/auth.py` — extend `get_current_user` | middleware | request-response | itself (existing JWKS/HS256 fallback chain) | exact |
| `frontend/src/lib/api.ts` — `sseUrl()` (modify) | utility | request-response | itself + `apiFetch` pattern | exact |
| `backend/rate_limit.py` (new) | middleware/utility | request-response | `backend/auth.py` (Depends-chained dependency pattern) | role-match |
| `backend/routes/chat.py` — wire rate limit into `/stream` | controller | streaming | existing `_invalid_conversation_stream` pattern in same file | exact |
| `backend/routes/onboarding.py` — wire rate limit into `/start` | controller | request-response | `backend/routes/chat.py`'s Depends pattern | role-match |
| `frontend/src/hooks/useSSEStream.ts` (extend error handler) | hook | streaming | itself | exact |
| `frontend/src/screens/OnboardingScreen.tsx` (extend `!res.ok` branch, 2 call sites) | component | request-response | itself + `frontend/src/lib/api.ts`'s error-parsing style (`exportSessionZwo`'s `reason` extraction) | role-match |
| `.github/workflows/ci.yml` (new) | config | batch | none in repo | no analog |
| `.gitignore` (extend) | config | — | itself | exact |

## Pattern Assignments

### `tests/agent/test_sse.py` (test, streaming) — fix 8 stale tests

**Analog:** `tests/api/conftest.py` (`TEST_USER_ID`, `make_test_token`, `auth_headers`) + `tests/api/test_chat.py`'s existing auth pattern.

**Auth pattern to import/reuse:**
```python
from tests.api.conftest import TEST_USER_ID, auth_headers, TEST_JWT_SECRET
monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
r = await client.get("/chat/stream", params={...}, headers=auth_headers())
```

**Required additional fixes (verified in RESEARCH.md, not optional):**
1. Use a real UUID for `conversation_id` (not `"test-001"`), or monkeypatch `chat_module._resolve_conversation_id` to bypass ownership check:
```python
async def _bypass_resolve(user_id, conversation_id):
    return conversation_id
monkeypatch.setattr(chat_module, "_resolve_conversation_id", _bypass_resolve)
```
2. Every mock `run_turn` function (`_mock_run_turn_text_only`, `_mock_run_turn_with_tools`, `_mock_run_turn_token_then_error`, `_mock_run_turn_token_then_done`) must accept `**kwargs` since `sse_generator` (backend/routes/_sse.py) now forwards `user_id`/`conversation_id`:
```python
async def _mock_run_turn_text_only(messages, client, model, trust_scanner, audit_log, **kwargs):
    yield {"event": "token", "data": {"text": "Hello, "}}
    yield {"event": "done", "data": {}}
```

**No-op exception:** `test_sse_requires_conversation_id` needs auth headers only — 422 already fires before ownership/ ownership logic when `conversation_id` is omitted.

**Frame parsing:** reuse existing `parse_sse_frames()` already defined in this file (and re-exported from `tests/api/conftest.py`) — do not write a new parser.

---

### `tests/sports_science/conftest.py` (test/fixture) + `backend/sports_science/profile.py` (add reset hook)

**Analog:** `backend/sports_science/capability_gap.py` lines 24-41 (module-level singleton + reset hook) and `tests/sports_science/conftest.py` lines 5-14 (autouse fixture).

**Exact pattern to replicate in `profile.py`** (copy `capability_gap.py`'s `_reset_client_for_tests`):
```python
# backend/sports_science/profile.py — add below the existing _supabase_client declaration
def _reset_client_for_tests() -> None:
    """Test-only seam: clear the module-level client cache. See
    capability_gap.py's identical pattern (WR-04) for rationale."""
    global _supabase_client
    _supabase_client = None
```

**Wire into conftest.py** (extend the existing autouse fixture, don't add a parallel one, to match the single-fixture style already there):
```python
@pytest.fixture(autouse=True)
def _reset_capability_gap_client():
    from backend.sports_science import capability_gap, profile

    capability_gap._reset_client_for_tests()
    profile._reset_client_for_tests()
    yield
    capability_gap._reset_client_for_tests()
    profile._reset_client_for_tests()
```

---

### `tests/api/test_contracts.py` (new, test, request-response)

**Analog:** `tests/api/conftest.py`'s `mock_supabase_factory` + the `httpx.AsyncClient(transport=ASGITransport(app=app))` pattern used across every file in `tests/api/`.

**Imports pattern:**
```python
import httpx
from httpx import ASGITransport
from backend.main import app
from tests.api.conftest import auth_headers, mock_supabase_factory, TEST_JWT_SECRET
```

**Core pattern (mock Supabase + assert field presence, not exact equality):**
```python
async def test_rides_contract(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    fake_row = {"id": "...", "ride_date": "...", "duration_secs": 3600,
                "avg_power": 180, "np_watts": 190, "tss": 65, "compliance_pct": 90}
    monkeypatch.setattr(rides_module, "_get_async_supabase", mock_supabase_factory([fake_row]))
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/rides/", headers=auth_headers())
    body = r.json()[0]
    required = {"id", "ride_date", "duration_secs", "avg_power", "np_watts", "tss", "compliance_pct"}
    assert required <= set(body.keys())
```
Repeat for `test_sessions_today_contract` (fields: `id, objective, structure, type, duration_mins, scheduled_date, rpe_target`) and `test_profile_me_contract` (field: `ftp` — verify via `DuringSessionScreen.tsx:554`'s actual read).

---

### `backend/auth.py` — extend `get_current_user` (item 5, D-04)

**Analog:** itself — the existing ES256/HS256 fallback chain (lines 96-135) is the pattern to extend, inserting a new branch before it.

**Exact insertion point and pattern (module docstring already specifies this design at lines 64-69 — the WR-006 TODO):**
```python
# Inside get_current_user, BEFORE the ES256/JWKS attempt, query-param path only:
if token and not cred:
    sse_secret = os.environ.get("SSE_TOKEN_SECRET")
    if sse_secret:
        try:
            payload = jwt.decode(token, sse_secret, algorithms=["HS256"], audience="authenticated")
            if payload.get("typ") == "sse_token":
                return {"user_id": payload["sub"], "email": None}
        except jwt.PyJWTError:
            pass  # not an sse_token (or expired) — fall through to existing paths
```
Do not touch the Bearer-header path — only the `?token=` fallback gets the new branch.

---

### `backend/routes/chat.py` — `POST /chat/token` (new endpoint)

**Analog:** `create_chat_conversation` in the same file (lines 181-198) — same file, same `Depends(get_current_user)` + no-request-body pattern.

**Imports pattern (already present in file, no new imports needed beyond `jwt`, `time`, `os`):**
```python
import time
import jwt
```

**Core pattern:**
```python
@router.post("/token")
async def issue_sse_token(current_user: dict = Depends(get_current_user)) -> dict:
    secret = os.environ.get("SSE_TOKEN_SECRET")
    if not secret:
        raise HTTPException(status_code=500, detail={"error": "server_error", "detail": "SSE_TOKEN_SECRET not configured"})
    exp_secs = 60
    token = jwt.encode(
        {"sub": current_user["user_id"], "aud": "authenticated", "typ": "sse_token",
         "exp": int(time.time()) + exp_secs},
        secret, algorithm="HS256",
    )
    return {"token": token, "expires_in": exp_secs}
```
Note: `POST /chat/token` must be authenticated via the Bearer-header path only (real Supabase JWT) — this is naturally enforced since `Depends(get_current_user)` accepts either, and the client always calls this via `apiFetch` (header-based), never via query param.

---

### `frontend/src/lib/api.ts` — `sseUrl()` (modify, utility, request-response)

**Analog:** itself (current `sseUrl` at line 35) + `apiFetch` (line 12) for the header-injection call, + `exportSessionZwo`'s error-body-parsing style (lines 276-321) for reading a JSON error body on failure.

**Core pattern (from RESEARCH.md, verified against actual `apiFetch`/`sseUrl` signatures):**
```typescript
export async function sseUrl(path: string): Promise<string> {
  const res = await apiFetch('/api/chat/token', { method: 'POST' })
  if (!res.ok) throw new Error(`chat token exchange failed: ${res.status}`)
  const { token } = await res.json() as { token: string; expires_in: number }
  const sep = path.includes('?') ? '&' : '?'
  return `${BASE}${path}${sep}token=${encodeURIComponent(token)}`
}
```
No changes needed at call sites in `ChatScreen.tsx` — both already `await sseUrl(...)`.

---

### `backend/rate_limit.py` (new, middleware/utility, request-response)

**Analog:** `backend/auth.py`'s `Depends`-chained dependency pattern (role-match; no existing rate-limit precedent in repo).

**Imports pattern:**
```python
import time
from collections import defaultdict, deque
from fastapi import Depends, HTTPException
from backend.auth import get_current_user
```

**Core pattern (full module — see RESEARCH.md Code Examples section for the verified, ready-to-use version):**
```python
_request_log: dict[str, deque] = defaultdict(deque)
WINDOW_SECS = 60
MAX_REQUESTS_PER_WINDOW = 10

def _check_and_record(user_id: str) -> bool:
    now = time.monotonic()
    log = _request_log[user_id]
    while log and now - log[0] > WINDOW_SECS:
        log.popleft()
    if len(log) >= MAX_REQUESTS_PER_WINDOW:
        return False
    log.append(now)
    return True

async def rate_limited_user(current_user: dict = Depends(get_current_user)) -> dict:
    """For JSON endpoints (onboarding/start): raises HTTP 429 with structured body."""
    if not _check_and_record(current_user["user_id"]):
        raise HTTPException(status_code=429, detail={"error": "rate_limited", "detail": "..."})
    return current_user

def is_rate_limited(user_id: str) -> bool:
    """For streaming endpoints (chat/stream): non-raising, caller returns an SSE error frame."""
    return not _check_and_record(user_id)
```

**Wiring into `chat_stream`** — mirrors the existing `_invalid_conversation_stream` pattern already in `backend/routes/chat.py` (lines 120-138):
```python
if is_rate_limited(user_id):
    async def _rate_limited_stream():
        error_data = json.dumps({"code": "rate_limited", "message": "..."})
        yield f"event: error\ndata: {error_data}\n\n"
    return StreamingResponse(_rate_limited_stream(), media_type="text/event-stream",
                              headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
```

**Wiring into `onboarding.py`'s `/start`:** swap `Depends(get_current_user)` for `Depends(rate_limited_user)` on that route (same file already imports `Depends`, `HTTPException`).

**Anti-pattern to avoid (from RESEARCH.md):** never raise `HTTPException(429)` from inside `chat_stream`'s streaming body — the 200/`text/event-stream` headers are already committed once `StreamingResponse` iteration begins.

---

### `frontend/src/hooks/useSSEStream.ts` — extend error handler

**Analog:** itself — existing `error` event listener and retry-count logic (see silent-retry block, lines 40-50 already read).

**Core pattern (skip retry when rate_limited):**
```typescript
es.addEventListener('error', (e: MessageEvent) => {
  const data = JSON.parse(e.data)
  if (data.code === 'rate_limited') {
    setError(data.message)
    // do NOT call retry() — mirrors OnboardingScreen.tsx's parallel fix
    return
  }
  // ... existing retry-count logic unchanged
})
```

---

### `frontend/src/screens/OnboardingScreen.tsx` — extend `!res.ok` branch (2 call sites, lines ~188 and ~353)

**Analog:** itself (both `!res.ok || !res.body` branches) + `frontend/src/lib/api.ts`'s `exportSessionZwo` (lines 276-321) for the "read JSON body for a reason/detail string" style already used elsewhere in this codebase.

**Core pattern (apply at both call sites):**
```typescript
if (!res.ok || !res.body) {
  if (res.status === 429) {
    const body = await res.json().catch(() => ({}))
    setStreamError(body.detail?.detail || body.detail || "You're sending messages a bit fast. Wait a moment and try again.")
    return  // skip retry() — same rule as useSSEStream.ts
  }
  if (retry()) return
  // ... existing generic fallback unchanged
}
```
Note the rate-limit dependency's `HTTPException(429, detail={"error": ..., "detail": ...})` shape — `res.json()` gives `{ detail: { error, detail } }` per FastAPI's own `HTTPException` serialization; adjust the exact key path to match once implemented.

---

## Shared Patterns

### Auth (JWT) — all backend routes and tests
**Source:** `backend/auth.py`'s `get_current_user` (lines 62-135); `tests/api/conftest.py`'s `auth_headers()`/`make_test_token()`
**Apply to:** every new/modified route (`/chat/token`, rate-limited routes) and every fixed test in `tests/agent/test_sse.py`, `tests/api/test_contracts.py`

### Module-level Supabase singleton + test-reset hook
**Source:** `backend/sports_science/capability_gap.py` lines 24-65
**Apply to:** `backend/sports_science/profile.py` (item 2's preventive fix)

### SSE frame construction ("one error frame, 200 status")
**Source:** `backend/routes/chat.py`'s `_invalid_conversation_stream` (lines 120-138)
**Apply to:** `backend/rate_limit.py`'s streaming-path integration in `chat_stream`

### Mocked async Supabase client for tests
**Source:** `tests/api/conftest.py`'s `mock_supabase_factory()` (lines 77-110)
**Apply to:** `tests/api/test_contracts.py` (item 4)

### httpx ASGITransport test client
**Source:** used throughout `tests/api/*.py` and `tests/agent/test_sse.py`
**Apply to:** all new/modified backend tests in this phase

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `.github/workflows/ci.yml` | config | batch | No `.github/workflows/` directory exists yet in this repo; use the verified YAML in RESEARCH.md's "Code Examples" section (pytest + vitest + ruff, report-only per D-05) as the direct template — no codebase analog to copy from instead |

## Metadata

**Analog search scope:** `backend/`, `backend/routes/`, `backend/sports_science/`, `tests/api/`, `tests/agent/`, `tests/sports_science/`, `frontend/src/lib/`, `frontend/src/hooks/`, `frontend/src/screens/`
**Files scanned:** `backend/auth.py`, `backend/routes/chat.py`, `backend/routes/onboarding.py`, `backend/main.py`, `backend/sports_science/capability_gap.py`, `backend/sports_science/profile.py`, `tests/api/conftest.py`, `tests/sports_science/conftest.py`, `tests/agent/test_sse.py`, `frontend/src/lib/api.ts`, `frontend/src/hooks/useSSEStream.ts`, `frontend/src/screens/OnboardingScreen.tsx`, `.gitignore`
**Pattern extraction date:** 2026-07-08
