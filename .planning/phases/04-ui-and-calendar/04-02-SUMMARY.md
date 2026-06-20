---
phase: 04-ui-and-calendar
plan: "02"
subsystem: backend-auth
tags: [jwt, auth, security, fastapi, sse]
dependency_graph:
  requires: []
  provides: [api/auth.py, get_current_user, PyJWT]
  affects: [api/routes/chat.py, api/routes/onboarding.py, api/routes/rides.py, api/routes/adaptations.py]
tech_stack:
  added: [PyJWT>=2.8.0]
  patterns: [FastAPI Depends JWT, HS256 audience=authenticated, SSE ?token= fallback]
key_files:
  created:
    - api/auth.py
    - tests/api/test_auth.py
  modified:
    - requirements.txt
    - api/routes/chat.py
    - api/routes/onboarding.py
    - api/routes/rides.py
    - api/routes/adaptations.py
    - tests/api/conftest.py
    - tests/api/test_adaptations.py
    - tests/api/test_onboarding.py
    - tests/api/test_rides.py
decisions:
  - "PyJWT reads SUPABASE_JWT_SECRET at call time (not module import) so tests can monkeypatch.setenv without import-order issues"
  - "validate_uuid kept in upload_fit as defence-in-depth after JWT migration; JWT sub claim is a valid UUID from Supabase but belt-and-suspenders is acceptable"
  - "UserIdBody and MissedSessionBody models removed from adaptations.py; Body and Query imports removed from fastapi"
  - "Existing tests updated to use auth_headers() helper and monkeypatch.setenv for SUPABASE_JWT_SECRET; test_get_adaptations_requires_user_id renamed to test_get_adaptations_requires_auth (now expects 401 not 422)"
metrics:
  duration: "10m"
  completed: "2026-06-20"
  tasks_completed: 4
  tasks_total: 4
  files_created: 2
  files_modified: 9
status: complete
requirements: [UI-01, UI-06]
---

# Phase 04 Plan 02: JWT Auth Security Gate Summary

Supabase JWT verification via PyJWT HS256 + audience='authenticated' on all four existing API route modules; SSE endpoints accept JWT via ?token= query param; 7 new auth tests prove 401 on unauthenticated/forged requests.

## Tasks Completed

| Task | Description | Commit | Status |
|------|-------------|--------|--------|
| 1 | Create api/auth.py with get_current_user JWT dependency | df26010 | Complete |
| 2 | Migrate chat.py and onboarding.py SSE endpoints to JWT | 28fef86 | Complete |
| 3 | Migrate rides.py and adaptations.py endpoints to JWT | 42f89f2 | Complete |
| 4 | Write JWT middleware tests and fix existing tests | 7e92299 | Complete |

## What Was Built

### api/auth.py (new)

`get_current_user` async FastAPI dependency that:
- Accepts JWT from `Authorization: Bearer <token>` (standard REST) or `?token=<jwt>` (SSE fallback; EventSource cannot send headers)
- Calls `jwt.decode(raw, SUPABASE_JWT_SECRET, algorithms=["HS256"], audience="authenticated")`
- Returns `{"user_id": payload["sub"], "email": payload.get("email")}`
- Raises `HTTPException(401)` with `{"error": "unauthorized", "detail": "..."}` for missing or invalid tokens
- Reads `SUPABASE_JWT_SECRET` at call time (not module import) for testability

### Route Migrations

All four existing route modules now use `Depends(get_current_user)` instead of insecure user_id query/body/form params:

| File | Endpoint | Change |
|------|----------|--------|
| chat.py | GET /chat/stream | `user_id: str = Query(...)` removed; `current_user: dict = Depends(get_current_user)` added |
| onboarding.py | POST /onboarding/start | `OnboardingStartRequest` model removed; `current_user: dict = Depends(get_current_user)` added |
| rides.py | POST /rides/upload | `user_id: str = Form(...)` removed; `current_user: dict = Depends(get_current_user)` added |
| adaptations.py | GET /adaptations/ | `user_id: str = Query(...)` replaced |
| adaptations.py | POST /adaptations/check | `UserIdBody` model replaced |
| adaptations.py | POST /adaptations/sessions/{id}/missed | `MissedSessionBody` model replaced |

### tests/api/test_auth.py (new)

7 tests covering full JWT middleware behavior:
- AUTH-01: Missing token returns 401
- AUTH-02: Garbage/malformed bearer token returns 401
- AUTH-03: Token signed by wrong secret returns 401
- AUTH-04: Valid token resolves user_id == TEST_USER_ID (unit test on get_current_user directly)
- AUTH-05: Valid token via `?token=` query param (SSE path) authenticates
- AUTH-06: Wrong audience (aud != 'authenticated') returns 401
- AUTH-07: Valid token via full HTTP path returns 200 with data

### conftest.py Additions

- `TEST_JWT_SECRET`: shared secret constant for all auth tests
- `make_test_token()`: generates valid Supabase-style JWTs for test use
- `auth_headers()`: ready-made `{"Authorization": "Bearer <token>"}` dict

### Existing Test Fixes

8 existing tests updated to pass a valid JWT (Rule 1 auto-fix: tests broken by auth migration):
- `test_adaptations.py`: test_weekly_check, test_get_adaptations (now use auth_headers()); test_get_adaptations_requires_user_id renamed to test_get_adaptations_requires_auth (401 not 422)
- `test_onboarding.py`: test_onboarding_returns_sse, test_confirmation_gate
- `test_rides.py`: test_upload_returns_200, test_fit_upload_integration, test_corrupt_fit_returns_422

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Existing tests broken by JWT migration**
- **Found during:** Task 4
- **Issue:** 8 existing tests in test_adaptations.py, test_onboarding.py, and test_rides.py sent requests without any JWT and expected 200/422. After auth migration, those endpoints return 401 before any handler logic runs.
- **Fix:** Added `TEST_JWT_SECRET`, `make_test_token()`, `auth_headers()` to conftest.py. Updated all 8 affected tests to use `monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)` and `headers=auth_headers()`. Renamed `test_get_adaptations_requires_user_id` to `test_get_adaptations_requires_auth` since the behavior changed from 422 (missing query param) to 401 (missing auth).
- **Files modified:** tests/api/conftest.py, tests/api/test_adaptations.py, tests/api/test_onboarding.py, tests/api/test_rides.py
- **Commit:** 7e92299

## Verification Results

```
python3 -c "import ast; ast.parse(open('api/auth.py').read()); print('ok')"  -> ok
grep -q 'audience="authenticated"' api/auth.py                               -> PASS
grep -q '^PyJWT' requirements.txt                                            -> PASS
grep -rn 'SECURITY TODO|phase-4-auth' api/routes/                           -> NO MATCHES
pytest tests/api/test_auth.py -x -q                                         -> 7 passed
pytest tests/api/ -q                                                         -> 27 passed
```

## Threat Surface Scan

No new network endpoints or trust boundaries introduced beyond those described in the plan's threat model. The `?token=` query param path (T-04-05) is documented as an accepted tradeoff per RESEARCH.md; Supabase access tokens are short-lived (~1hr) and refreshed by the client. Server-side log suppression of the `token` query param is a deployment-config concern noted for Phase 5.

## Self-Check

```
FOUND: api/auth.py
FOUND: tests/api/test_auth.py
FOUND: PyJWT in requirements.txt
FOUND commit df26010: feat(04-02): create api/auth.py get_current_user JWT dependency
FOUND commit 28fef86: feat(04-02): migrate chat.py and onboarding.py SSE endpoints to JWT auth
FOUND commit 42f89f2: feat(04-02): migrate rides.py and adaptations.py endpoints to JWT auth
FOUND commit 7e92299: feat(04-02): add JWT middleware tests and fix existing tests for Phase 4 auth
```

## Self-Check: PASSED
