---
phase: 10-hygiene-safety-nets
reviewed: 2026-07-08T00:00:00Z
depth: standard
files_reviewed: 18
files_reviewed_list:
  - backend/auth.py
  - backend/rate_limit.py
  - backend/routes/chat.py
  - backend/routes/onboarding.py
  - backend/sports_science/profile.py
  - frontend/src/hooks/useSSEStream.ts
  - frontend/src/lib/api.ts
  - frontend/src/screens/OnboardingScreen.tsx
  - frontend/tests/e2e/full-uat.spec.ts
  - frontend/tests/e2e/phase4.spec.ts
  - tests/agent/test_sse.py
  - tests/api/test_chat_token.py
  - tests/api/test_chat.py
  - tests/api/test_contracts.py
  - tests/api/test_onboarding.py
  - tests/api/test_rate_limit.py
  - tests/sports_science/conftest.py
  - .github/workflows/ci.yml
  - .gitignore
findings:
  critical: 1
  warning: 3
  info: 2
  total: 6
status: issues_found
---

# Phase 10: Code Review Report

**Reviewed:** 2026-07-08
**Depth:** standard
**Files Reviewed:** 18
**Status:** issues_found

## Summary

This phase adds a short-lived SSE token exchange (`POST /chat/token` + a
namespaced `sse_token` verify branch in `get_current_user`), a hand-rolled
in-process rate limiter shared by `/chat/stream` and `/onboarding/start`,
matching frontend rate-limit/error handling, a `profile.py` test-reset seam,
new contract tests, corrected Playwright fixture shapes, and — for the first
time in this repo — a CI workflow.

The token-exchange design itself is sound: the `typ == "sse_token"` namespace
guard and dedicated `SSE_TOKEN_SECRET` correctly prevent a real Supabase JWT
and an ephemeral SSE token from ever cross-validating, algorithms are
explicitly pinned (no `alg: none` / confusion risk), and the rate limiter's
test-isolation fixtures were correctly added to three of the four test files
that exercise it. However, actually running the tools this phase claims to
add surfaced a serious problem: the new CI workflow's own `ruff check .` step
fails against the current tree (237 errors repo-wide, 55 of them in files
this very phase touched), so the "hygiene safety net" this phase is named for
would never go green. A second test file (`tests/agent/test_sse.py`) is
missing the rate-limit-log reset fixture its siblings received, making its
correctness order-dependent rather than deterministic. Both are detailed
below, verified by actually running `ruff` and `pytest` against the repo.

## Critical Issues

### CR-01: The CI workflow added by this phase fails immediately (`ruff check .` has 237 pre-existing/introduced errors)

**File:** `.github/workflows/ci.yml:15` (backend job: `run: ruff check .`)

**Issue:** This phase introduces the repo's first CI workflow. Its backend
job runs `ruff check .` (whole repository, no path scoping, no ignore
config) as a gating step before `pytest`. Running this exact command against
the current tree fails:

```
$ ruff check .
Found 237 errors.
[*] 142 fixable with the `--fix` option (6 hidden fixes can be enabled with the `--unsafe-fixes` option).
```

This is not a hypothetical — it was run directly against this checkout.
Restricting to just the files this phase touches still yields 55 errors,
several of which are newly introduced by this phase's own test files, not
pre-existing debt:

- `tests/api/test_chat.py:15` — `F401` unused import `unittest.mock.AsyncMock`
- `tests/api/test_chat.py:20` — `F401` unused import `TEST_USER_ID` (imported from `tests.api.conftest` but never referenced)
- `tests/api/test_onboarding.py:220` — `F841` unused local `event_types`
- `tests/api/test_onboarding.py:301` — `F841` unused local `result`
- `tests/api/test_chat_token.py:18`, `tests/api/test_contracts.py`, `tests/agent/test_sse.py:22-27` and others — `I001` unsorted/unformatted import blocks
- `backend/auth.py:138`, `backend/routes/chat.py:229`, several `tests/agent/test_sse.py` lines — `E501` line-too-long (>100 cols)

Because `ruff check .` is unscoped and there is no `ruff.toml`/`pyproject.toml`
exclusion for `tests/` or historical debt, the very first run of this
workflow (on the commit that adds it) will be red, and will stay red until
someone either fixes the whole repo's lint debt or changes the CI
configuration. A CI job that starts in a permanently-failing state provides
no safety net at all — team members learn to ignore the red check, which
defeats the purpose of a phase titled "hygiene-safety-nets."

I independently confirmed `pytest tests/ -q` passes cleanly (343 passed) in
the same environment, so this is specifically a `ruff` configuration/scope
problem, not a broader "tests don't pass" problem.

**Fix:** Before merging, either:
1. Run `ruff check . --fix` (safe fixes) plus manual cleanup of the remaining
   unused-import/unused-variable findings, especially the ones this phase
   itself introduced (`test_chat.py`, `test_onboarding.py`), or
2. Scope the CI `ruff` step and/or add a `[lint] exclude`/per-file-ignore
   policy that reflects an intentional debt-acceptance decision, so the
   workflow reflects the actual bar the team intends to hold, rather than
   failing unconditionally on day one.

Either way, verify with `ruff check .` locally (exit code 0) before relying
on this workflow as a merge gate.

## Warnings

### WR-01: `tests/agent/test_sse.py` is missing the rate-limit-log reset fixture added to its sibling test files, making it order-dependent

**File:** `tests/agent/test_sse.py:1-27` (and its `tests/agent/conftest.py`)

**Issue:** This phase added an autouse fixture that clears
`rate_limit_module._request_log` before and after each test to
`tests/api/test_chat.py`, `tests/api/test_onboarding.py`, and
`tests/api/test_rate_limit.py` — explicitly to prevent the shared
module-global rate-limit state from leaking between tests that reuse
`TEST_USER_ID` (per each file's own docstring: "so exhausting the budget in
one test doesn't bleed into another"). `tests/agent/test_sse.py` drives the
same `/chat/stream` endpoint with the same `TEST_USER_ID` (via
`auth_headers()`) across 7 tests in `TestSSEEventSequence`, but received no
equivalent fixture — neither in the file itself nor in
`tests/agent/conftest.py`.

Today this happens not to manifest because pytest's default alphabetical
directory collection runs `tests/agent/` before `tests/api/`, so
`test_sse.py`'s tests are the first consumers of `TEST_USER_ID`'s rate-limit
budget in the session and the module-global dict starts empty. I verified
this by running `pytest tests/api tests/agent/test_sse.py -q` (alternate
order) and confirming it still passes only because `tests/api`'s own
teardown fixtures clear the log afterward — i.e. correctness currently
depends on every *other* test file's teardown running cleanly, not on
`test_sse.py` protecting itself.

This is exactly the fragility the phase brief asked to be checked for: any
of the following would silently start producing `rate_limited` SSE `error`
frames instead of the expected deterministic mock sequences in
`test_sse.py`, with a confusing failure mode (wrong event sequence, not an
obviously rate-limit-related assertion message):
- A test-ordering plugin (`pytest-randomly`, `pytest-xdist` work-stealing) reorders tests.
- A new test file/test is added to `tests/agent/` alphabetically before `test_sse.py` that also drives `TEST_USER_ID` through `/chat/stream` or `/onboarding/start`.
- `tests/agent/test_sse.py` itself grows past `MAX_REQUESTS_PER_WINDOW` (10) HTTP-driving tests in `TestSSEEventSequence` (currently 7; 3 more and it fails on its own, in-file, regardless of ordering).

**Fix:** Add the same reset fixture already used elsewhere, e.g. in
`tests/agent/conftest.py`:

```python
@pytest.fixture(autouse=True)
def _reset_rate_limit_log():
    import backend.rate_limit as rate_limit_module
    rate_limit_module._request_log.clear()
    yield
    rate_limit_module._request_log.clear()
```

### WR-02: The new CI workflow never runs the Playwright e2e suite this phase modified

**File:** `.github/workflows/ci.yml:18-31` (frontend job)

**Issue:** This phase corrected fixture field-name mismatches in
`frontend/tests/e2e/full-uat.spec.ts` and `frontend/tests/e2e/phase4.spec.ts`
(e.g. `duration_seconds` → `duration_secs`, `avg_power_watts` → `avg_power`,
wrapping the `/rides/` mock response in `{ rides: [...] }`). These files live
under `frontend/tests/e2e/` and are run via `npm run test:e2e` (Playwright),
per `frontend/package.json`. The new CI workflow's frontend job only runs
`npm run test -- --run`, which invokes Vitest — and Vitest's `include` glob
in `frontend/vitest.config.ts` is `src/tests/**/*.{test,spec}.{ts,tsx}`,
which does not match `frontend/tests/e2e/*.spec.ts`. I confirmed this by
inspecting both the vitest config and `package.json` scripts directly.

Net effect: the e2e fixture corrections this phase makes (and any future
regression to the same contract fields) are not exercised by the CI this
phase adds at all. The "safety net" doesn't cover the files it just fixed.

**Fix:** Add a `playwright` job (or a step in the frontend job) that runs
`npx playwright install --with-deps && npm run test:e2e`, or explicitly
document that e2e is intentionally out of CI scope for now (manual-only) so
the gap is a documented decision rather than an oversight.

### WR-03: `get_current_user`'s `sse_token` branch can raise an unhandled `KeyError` instead of falling through cleanly

**File:** `backend/auth.py:107-116`

**Issue:** Inside the `sse_token` verify branch, the code does:

```python
sse_payload = jwt.decode(token, sse_secret, algorithms=["HS256"], audience="authenticated")
if sse_payload.get("typ") == "sse_token":
    return {"user_id": sse_payload["sub"], "email": None}
```

`sse_payload["sub"]` uses plain dict indexing. If a token verifies (correct
signature, correct `typ`) but is missing a `sub` claim, this raises a
`KeyError`, which is **not** a subclass of `jwt.PyJWTError` and therefore is
**not** caught by the surrounding `except jwt.PyJWTError: pass`. I reproduced
this directly:

```python
bad = jwt.encode({"aud": "authenticated", "typ": "sse_token", "exp": ...}, SSE_TOKEN_SECRET, algorithm="HS256")
await get_current_user(cred=None, token=bad)
# -> KeyError: 'sub'  (propagates out of the dependency, not a clean 401)
```

Every other failure mode in this branch (bad signature, expired, wrong
`typ`) falls through gracefully to the Supabase verification path per the
function's own documented contract ("On any failure ... fall through
unchanged"). This one doesn't — it crashes the request handler instead of
producing a 401. Exploitability today is low (forging a token that passes
signature verification requires already possessing `SSE_TOKEN_SECRET`), but
it's a latent crash path inconsistent with the rest of the function's error
handling, and would bite immediately if `issue_sse_token`'s payload shape
ever changes without a matching update here.

**Fix:**
```python
if sse_payload.get("typ") == "sse_token":
    sub = sse_payload.get("sub")
    if sub:
        return {"user_id": sub, "email": None}
    # missing sub -- fall through to Supabase verification below
```

## Info

### IN-01: Vacuous assertion in `test_issue_sse_token_returns_short_lived_token`

**File:** `tests/api/test_chat_token.py:61`

**Issue:** `assert decoded["exp"] - decoded["iat"] <= 90 if "iat" in decoded else True` is unconditionally true in practice, because `backend/routes/chat.py`'s `issue_sse_token` never sets an `iat` claim and PyJWT does not add one automatically. The line reads as if it verifies token lifetime via `iat`, but it verifies nothing (the following line, `decoded["exp"] - int(time.time()) <= 90`, is the assertion that actually does the work). Not a functional test gap since the real check exists right below it, but the dead conditional is misleading and worth removing or fixing to assert `"iat" not in decoded` if that's the intended contract.

### IN-02: `POST /chat/token` is not itself rate-limited

**File:** `backend/routes/chat.py:89-132`

**Issue:** `issue_sse_token` uses `Depends(get_current_user)` rather than `Depends(rate_limited_user)`. An authenticated caller can mint an unbounded number of ephemeral tokens per minute. This is low-risk (token minting is cheap and doesn't touch the LLM), and is consistent with the rate limiter's stated scope ("LLM-backed endpoints"), but worth a deliberate one-line acknowledgment in the docstring alongside the other D-02/D-03 references, since a future reader may otherwise assume all D-04-related endpoints share the same budget.

---

_Reviewed: 2026-07-08_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
