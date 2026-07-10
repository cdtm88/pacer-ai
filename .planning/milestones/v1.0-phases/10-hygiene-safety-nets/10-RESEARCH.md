# Phase 10: Hygiene and Safety Nets - Research

**Researched:** 2026-07-08
**Domain:** Test infrastructure hygiene, backend auth/rate-limiting, CI, repo cleanup (no new product surface)
**Confidence:** HIGH

## Summary

This phase is 8 narrow, independently-verifiable fixes across an already-mature FastAPI + React codebase. All research below is grounded directly in the current repo state (files read, `pytest tests/ -q` actually executed, and 3 of the 8 fixes verified end-to-end against a live `httpx.AsyncClient(ASGITransport)` instance during this research session, not just inferred from reading code).

The most important finding: **fixing the 8 stale SSE tests requires three coordinated changes, not one.** CONTEXT.md's discretion note ("reuse `auth_headers()`") undersells the real fix. Adding auth headers alone still fails, because (a) `test_sse.py`'s `conversation_id="test-001"` is not a valid UUID and gets silently rejected by the CR-03 ownership check added in Phase 8, and (b) the 4 mock `run_turn` functions in that file have a stale signature that doesn't accept the `user_id`/`conversation_id` kwargs `sse_generator` now always forwards. All three fixes were verified together in this session (see Pitfall 1) and produce a passing stream end-to-end.

Second finding beyond CONTEXT.md's scope: the "check for other unreset singletons" instruction pointed at `backend/agent/audit.py` (which turned out clean — it already uses the centralized `backend/db.py` singleton). The actual sibling risk is `backend/sports_science/profile.py`, which duplicates `capability_gap.py`'s pre-fix module-level `_supabase_client` pattern with no `_reset_client_for_tests()` hook. It is not causing an observed failure today (no test calls its real `_get_async_supabase()` un-mocked), but it is the same latent class of bug and should get the same fix as a preventive safety net, matching this phase's theme.

Third finding: the UI-SPEC's rate-limit interaction rule ("skip retry on `code: rate_limited`") requires code changes in **two** places, not one — `useSSEStream.ts`'s error handler (chat path) AND `OnboardingScreen.tsx`'s `!res.ok` branch (onboarding path), which today does not read the response body at all on failure and always shows a generic message. This is a gap between the UI-SPEC's assumption ("the existing `!res.ok` branch can read a detail/message string") and actual code (verified: it currently cannot).

**Primary recommendation:** Fix items 1-4 and 7-8 as narrow, mechanical changes using patterns already proven elsewhere in this codebase (no new abstractions). For item 5 (SSE token exchange), mint the ephemeral token with the existing `PyJWT` dependency and a dedicated new env var, verified inline in `get_current_user`. For item 6 (rate limiting), prefer a small hand-rolled in-process token-bucket dependency over `slowapi` (flagged `[SUS]` by the automated package-legitimacy gate; also cross-verified independently in this session — see Package Legitimacy Audit) since the codebase is small, single-user, and already has the `Depends(get_current_user)` pattern to key off of.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| SSE test auth fixtures | Backend (test) | — | Pure test-infra fix; no runtime code changes beyond signature updates in test doubles |
| Capability-gap / profile singleton reset | Backend (sports_science) | Backend (test) | Module-level client cache is a backend concern; the reset hook is test-only plumbing |
| Playwright mock shapes | Frontend (test) | — | E2E mocks must mirror the API tier's actual response contract |
| Contract tests | API / Backend | Frontend (types) | Backend response shape is the source of truth; frontend `api.ts` interfaces must match it, not the reverse |
| SSE token exchange | API / Backend (auth) | Frontend (fetch layer) | Token minting and verification is backend auth; frontend only needs to call the new endpoint before opening `EventSource` |
| Rate limiting | API / Backend | Frontend (error UI) | Enforcement point is the backend route; frontend only needs to render the existing terminal-error banner differently |
| CI | Repo / Infra | — | Not owned by any runtime tier — build/test automation only |
| Repo cleanup | Repo / Infra | — | Same |

## Standard Stack

### Core (already in place, reused unmodified)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PyJWT | `>=2.8.0` (requirements.txt); `2.10.x` current per PyPI [VERIFIED: PyPI registry] | JWT encode/decode, already used by `backend/auth.py` | Already the project's JWT library; reuse for the new short-lived SSE token — no new dependency needed |
| httpx + `ASGITransport` | already a transitive dep via `fastapi`/`anthropic` | In-process FastAPI test client | Already the established pattern across `tests/api/*.py` and `tests/agent/test_sse.py`; contract tests (item 4) must reuse this, not introduce a new test client |
| pytest / pytest-asyncio | `9.1.1` / `1.4.0` (requirements.txt) [VERIFIED: local venv] | Test runner | Already pinned; `asyncio_mode = auto` in `pytest.ini` means no `@pytest.mark.asyncio` needed anywhere in new tests |
| ruff | `0.15.18` (requirements.txt) [VERIFIED: local venv] | Lint | Already the project's sole linter (`ruff.toml`: `select = ["E","F","I"]`, `line-length=100`) |
| vitest / Playwright | `4.1.9` / `1.61.0` (frontend/package.json) [VERIFIED: package.json] | Frontend unit + e2e test runners | Already configured (`frontend/vitest.config.ts`, `frontend/playwright.config.ts`); CI (item 7) reuses `npm run test` (vitest) per D-05 — Playwright e2e is NOT in CI scope this phase |

### New for this phase
| Library | Version | Purpose | Recommendation |
|---------|---------|---------|-----------------|
| None (hand-rolled) | — | In-process rate limiting (item 6) | See "Don't Hand-Roll" below for why this is the one exception — recommended over `slowapi` |
| GitHub Actions: `actions/checkout` | `v6` [CITED: github.com/actions/checkout releases, cross-checked via WebSearch 2026-07] | CI checkout step | Current major version; `v4`/`v5` still work but `v6` is current |
| GitHub Actions: `actions/setup-python` | `v6`, `python-version: '3.12'` | CI Python setup | Matches `requirements.txt`'s Python 3.12 target and `ruff.toml`'s `target-version = "py312"` |
| GitHub Actions: `actions/setup-node` | `v6`, `node-version: '22'` | CI Node setup | LTS; GitHub-hosted runners default to Node 24 for the Actions runtime itself from June 2026, but the *project's* Node target should stay pinned explicitly rather than following the runner's internal Node version |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hand-rolled token-bucket dependency | `slowapi` (`0.1.10`) | Flagged `[SUS]` by the package-legitimacy gate (see audit below); also awkward to key by `user_id` (its decorator pattern is designed around `request`-only key functions, requiring a `request.state` side-channel hack from `get_current_user`) rather than the codebase's existing `Depends(get_current_user)`-chained pattern. Reasonable to revisit if rate-limiting needs grow (multi-tier limits, Redis backend) — not needed for a single-user personal app (D-02) |
| Targeted pytest contract assertions (D-01, locked) | Full OpenAPI → TypeScript codegen | Structurally stronger (impossible to drift) but a disproportionate build-pipeline change for a hygiene phase; explicitly deferred per CONTEXT.md |
| In-process rate limiter (D-02, locked) | Upstash Redis via Vercel Marketplace | Correct choice for multi-tenant/adversarial traffic; unnecessary infra/cost for a single-user app today; explicitly deferred per CONTEXT.md |

**Installation:** No new pip or npm packages required for the recommended approach (hand-rolled rate limiter, PyJWT reuse for token exchange). If `slowapi` is chosen instead of the hand-rolled approach, `pip install slowapi==0.1.10` and add a `checkpoint:human-verify` task before that install per the audit below.

## Package Legitimacy Audit

> Required because item 6 (rate limiting) was evaluated against a candidate new package (`slowapi`). No other item in this phase introduces a new external package — items 1-5, 7, 8 reuse only already-installed dependencies (`PyJWT`, `httpx`, `pytest`, GitHub Actions, which are not registry packages).

| Package | Registry | Age (latest release) | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----------------------|-----------|--------------|---------|--------------|
| `slowapi` | pypi | Latest `0.1.10` published 2026-06-13 [VERIFIED: PyPI JSON API]; first release `0.1.0` dates to ~2020 (10 released versions, `laurentS/slowapi` GitHub repo with active 2026 PRs/discussions) [CITED: WebSearch, github.com/laurentS/slowapi] | Unknown — registry download-count API unavailable in this environment (the same "unknown-downloads" result was returned for `PyJWT`, an unambiguously legitimate package already in production use here, confirming this is a tooling/environment limitation, not a signal specific to `slowapi`) | `github.com/laurentS/slowapi` (exists, active) | **SUS** (gate reasons: `too-new`, `unknown-downloads`) | **Flagged.** Not recommended as the primary path (see Standard Stack) — recommend the hand-rolled in-process limiter instead, which needs no new package. If a future phase still wants `slowapi`, gate its install behind `checkpoint:human-verify` |

**Packages removed due to `[SLOP]` verdict:** none.
**Packages flagged as suspicious `[SUS]`:** `slowapi` — not required by the recommended approach; if the planner chooses it anyway, add `checkpoint:human-verify` before `pip install slowapi` in requirements.txt.

Note on the `too-new` reason: the gate's signal reflects the *latest version's* publish date (2026-06-13), not the package's first-ever release. Manual cross-check (WebSearch + PyPI version history: `0.1.0` through `0.1.10`) shows the package has existed since roughly 2020 with a continuously active GitHub repo. This is provided for context, not to override the gate's verdict — per protocol the `[SUS]` disposition and checkpoint requirement stand regardless of this additional diligence.

## Architecture Patterns

### System Architecture Diagram (SSE token exchange + rate limiting, items 5-6)

```
Browser (ChatScreen.tsx)
  │
  │ 1. apiFetch POST /api/chat/token   (real Supabase JWT, Authorization: Bearer header)
  ▼
FastAPI: POST /chat/token  ──Depends(get_current_user)──▶ verifies real Supabase JWT (ES256/JWKS or HS256)
  │                                                         │
  │ 2. mint ephemeral token                                 │ user_id resolved
  │    jwt.encode({sub:user_id, aud:"authenticated",         ▼
  │                typ:"sse_token", exp:+60s}, SSE_TOKEN_SECRET, HS256)
  ▼
Browser receives {token, expires_in}
  │
  │ 3. sseUrl() appends ?token=<ephemeral>  (NOT the real Supabase JWT anymore)
  ▼
EventSource GET /chat/stream?conversation_id=...&token=<ephemeral>
  │
  ▼
FastAPI: GET /chat/stream  ──Depends(get_current_user)──▶ query-param branch:
  │                              try SSE-token verify (typ=="sse_token", SSE_TOKEN_SECRET) first
  │                              │  success → return {user_id, email:None}
  │                              │  failure → fall through to existing ES256/HS256 Supabase paths
  │                                            (backward-compatible; header-based REST calls unaffected)
  ▼
  4. in-process rate-limit dependency: Depends(get_current_user) result reused,
     token-bucket keyed by user_id checked BEFORE any streaming begins
     │
     ├─ under limit → proceed to sse_generator (existing flow, unchanged)
     └─ over limit  → return StreamingResponse yielding ONE frame:
                       event: error
                       data: {"code":"rate_limited","message":"..."}
                       (mirrors the existing _invalid_conversation_stream() pattern —
                        status 200, Content-Type text/event-stream, so EventSource
                        actually receives and parses this frame instead of treating
                        a raw non-200 response as a network-level connection failure)
```

### Recommended Project Structure (new/changed files only)
```
backend/
├── auth.py                    # extend get_current_user: try SSE-token verify path first (query-param branch only)
├── rate_limit.py              # NEW: in-process token-bucket dependency, keyed by user_id
├── routes/
│   ├── chat.py                # add POST /chat/token; wire rate_limit dependency into GET /stream
│   └── onboarding.py          # wire rate_limit dependency into POST /start
frontend/src/
├── lib/api.ts                 # sseUrl(): call POST /api/chat/token first, use ephemeral token
├── hooks/useSSEStream.ts      # error handler: skip retry when data.code === "rate_limited"
└── screens/OnboardingScreen.tsx  # !res.ok branch: read JSON body, skip retry on 429, show rate-limit copy
tests/
├── agent/test_sse.py          # fix: add auth headers + valid conversation_id (bypass ownership check) + **kwargs on mock run_turn fns
├── sports_science/conftest.py # extend autouse fixture to also reset profile.py's singleton
tests/api/
└── test_contracts.py          # NEW: targeted field-presence assertions for rides/profile/sessions
.github/workflows/
└── ci.yml                     # NEW: pytest + vitest + ruff, report-only (no branch protection)
.gitignore                     # add node_modules/ (root-level guard) and test-ride.fit pattern
```

### Pattern 1: Fixing the 8 stale SSE tests (item 1) — verified end-to-end this session

**What:** Three coordinated changes to `tests/agent/test_sse.py`'s `TestSSEEventSequence` class (the `TestAssistantSinkGating` class is unaffected — it calls `sse_generator` directly, bypassing HTTP/auth entirely, and its 2 tests already pass).

**Verified failure mode (reproduced against the live app in this session):**
```python
# Adding ONLY auth headers still fails — conversation_id="test-001" is not a
# valid UUID, so CR-03's _resolve_conversation_id (added Phase 8) treats it as
# absent/foreign and short-circuits BEFORE run_turn's mock is ever reached:
r = await client.get("/chat/stream",
    params={"conversation_id": "test-001", "user_id": "test-user-001"},
    headers=auth_headers())
# r.status_code == 200, but body is:
#   event: error
#   data: {"code": "invalid_conversation_id", "message": "..."}
```

**The verified full fix (all three changes together, produces the expected token/done frames):**
```python
# 1. Auth: mirror tests/api/test_chat.py's exact pattern
monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)  # tests/api/conftest.py constant
# ... and pass headers=auth_headers() on every client.get("/chat/stream", ...) call

# 2. Bypass the CR-03 ownership check (these tests exercise SSE framing
#    mechanics, not conversation ownership — that's already covered by
#    tests/api/test_chat.py's CR-03-specific tests). Monkeypatch the CALLER's
#    module-level binding (chat.py imports the name directly via
#    `from backend.routes.onboarding import _resolve_conversation_id`, so
#    `chat_module._resolve_conversation_id` is a distinct, patchable binding):
async def _bypass_resolve(user_id, conversation_id):
    return conversation_id
monkeypatch.setattr(chat_module, "_resolve_conversation_id", _bypass_resolve)

# 3. Update EVERY mock run_turn's signature to accept the kwargs sse_generator
#    now always forwards for a resolved (non-None) user_id/conversation_id
#    (backend/routes/_sse.py: kwargs["user_id"]=..., kwargs["conversation_id"]=...):
async def _mock_run_turn_text_only(messages, client, model, trust_scanner, audit_log, **kwargs):
    yield {"event": "token", "data": {"text": "Hello, "}}
    yield {"event": "done", "data": {}}
# Apply the same **kwargs addition to _mock_run_turn_with_tools,
# _mock_run_turn_token_then_error, _mock_run_turn_token_then_done.
```

**When to use:** Exactly this file. `test_sse_requires_conversation_id` (the 422 test) is the one test in the class that does NOT need the ownership-check bypass — verified in this session that omitting `conversation_id` with valid auth headers still correctly returns 422 (FastAPI's own required-Query validation fires before any dependency body runs its 401/ownership logic in this no-token, param-missing case — this one was already effectively correct once auth is added).

### Pattern 2: Contract tests (item 4, D-01 locked)

**What:** Targeted pytest assertions against the 3 endpoints that have broken before, using the exact `httpx.AsyncClient(transport=ASGITransport(app=app))` + mocked-Supabase pattern already used across `tests/api/*.py`.

**Verified actual response shapes vs. frontend reads (this session cross-referenced `backend/routes/{rides,sessions}.py`'s `.select(...)` columns against every field frontend components actually dereference, via `grep` across `frontend/src`):**

| Resource | Backend source of truth | Fields frontend code actually reads (verified via grep) | Frontend TS interface (api.ts) — has EXTRA unused fields |
|----------|--------------------------|---------------------------------------------------------|------------------------------------------------------------|
| Ride (`GET /rides/`) | `.select("id, user_id, tss, np_watts, intensity_factor, duration_secs, ride_date, avg_power, avg_hr, avg_cadence, ftp_used, session_id, compliance_pct")` | `id, ride_date, duration_secs, avg_power, np_watts, tss, compliance_pct` | `intensity_factor, avg_hr, avg_cadence, ftp_used, user_id, session_id` declared but unread — benign dead typing, not a bug |
| Session (`GET /sessions/today`, `/sessions/upcoming`) | `_SESSION_COLUMNS = "id, objective, structure, targets, duration_mins, duration_minutes, status, scheduled_date, type, zone_targets, power_targets, rpe_target, tss_target, calendar_event_id"` | `id, objective, structure, type, duration_mins, scheduled_date, rpe_target` (verified via grep; `status` consumed by callers elsewhere) | Interface also declares `user_id, date, planned_tss, actual_tss, notes` — **none of these exist in the backend's SELECT at all**, and none are read anywhere in frontend code either. Dead on both sides — worth a one-line interface cleanup, not a functional bug |
| Profile (`GET /profiles/me`) | `.select("*")` (whole row) | Only `.ftp` is read as a specific field (`DuringSessionScreen.tsx:554`); `router.tsx`'s `FirstRunGate` only checks null-vs-not-null, doesn't read fields | Interface fields (`display_name, lthr, weight_kg, onboarding_complete, created_at, updated_at`) match table columns by convention (`select("*")`), lower drift risk since there's no explicit column list to fall out of sync |

**Recommendation:** Write `tests/api/test_contracts.py` with 3 test functions (`test_rides_contract`, `test_sessions_today_contract`, `test_profile_me_contract`), each hitting the real route with a mocked Supabase client returning a realistic row, and asserting (by name) presence of the fields frontend code actually reads today (the middle column above) — not the full declared TS interface, since some of those fields are provably dead on both sides. Use `assert set(actually_read_fields) <= set(response.json().keys())` rather than exact equality, so backend can add columns without breaking the test.

### Pattern 3: SSE token exchange (item 5, D-04 locked design)

**What:** `POST /chat/token`, authenticated via the existing `get_current_user` dependency (Bearer header path, unchanged), mints a short-lived (~60s) HS256 JWT signed with a **new, dedicated** `SSE_TOKEN_SECRET` env var — not the existing `SUPABASE_JWT_SECRET`.

**Why a dedicated secret rather than reusing `SUPABASE_JWT_SECRET`:** `get_current_user`'s existing HS256 fallback path only activates when `SUPABASE_JWT_SECRET` is set — but that variable may be absent in a production deployment that uses JWKS/ES256 exclusively (per `auth.py`'s own docstring: "Newer Supabase projects issue ES256 tokens... Older projects use HS256"). Minting the ephemeral token with a project-owned secret that's always present removes that dependency on which Supabase auth mode the deployment happens to use, and avoids ever giving a token that could be confused with (or need the same rotation policy as) the real Supabase signing secret.

**Verification path (extend `get_current_user`, query-param branch only — Bearer/header path is untouched):**
```python
# backend/auth.py — inside get_current_user, BEFORE the existing JWKS attempt,
# but only for the query-param (`token`) path (never for the Authorization header):
if token and not cred:
    sse_secret = os.environ.get("SSE_TOKEN_SECRET")
    if sse_secret:
        try:
            payload = jwt.decode(token, sse_secret, algorithms=["HS256"], audience="authenticated")
            if payload.get("typ") == "sse_token":
                return {"user_id": payload["sub"], "email": None}
        except jwt.PyJWTError:
            pass  # not an sse_token (or expired) — fall through to existing Supabase verification
# ... existing ES256/HS256 Supabase verification unchanged below
```
The `typ: "sse_token"` claim is a deliberate namespace guard so a real Supabase-issued JWT (which never carries this claim) can never be misinterpreted as one, and vice versa.

**Frontend change (`frontend/src/lib/api.ts`'s `sseUrl`):**
```typescript
export async function sseUrl(path: string): Promise<string> {
  const res = await apiFetch('/api/chat/token', { method: 'POST' })  // real Supabase JWT via apiFetch's existing header injection
  if (!res.ok) throw new Error(`chat token exchange failed: ${res.status}`)
  const { token } = await res.json() as { token: string; expires_in: number }
  const sep = path.includes('?') ? '&' : '?'
  return `${BASE}${path}${sep}token=${encodeURIComponent(token)}`
}
```
No changes needed at either call site in `ChatScreen.tsx` (`handleSend`/`handleRetry`) — both already `await sseUrl(...)`.

### Anti-Patterns to Avoid
- **Storing the ephemeral SSE token anywhere durable (DB row, cache table):** defeats the entire point of D-04 (stateless, no new infra). The `exp` claim alone is the enforcement mechanism.
- **Reusing `slowapi`'s default `get_remote_address` key function:** wrong dimension entirely for this app — Vercel-fronted requests may share an edge IP, and the requirement is per-`user_id`, not per-IP.
- **Raising `HTTPException(429)` from inside `GET /chat/stream`'s streaming body:** by the time `StreamingResponse` has been returned and iteration begins, the 200 status and `text/event-stream` headers are already committed — a mid-stream exception cannot change them to a 429. The rate-limit check must happen (and the `StreamingResponse` must be constructed) synchronously in the route function, mirroring the existing `_invalid_conversation_stream()` pattern (return a `StreamingResponse` yielding one `error` frame), not a raised HTTP error.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JWT signing/verification | Custom HMAC signing code | `jwt.encode`/`jwt.decode` (PyJWT, already installed) | Already the project's JWT library; hand-rolling signature verification is exactly the kind of security-sensitive code that must never be reinvented |
| SSE frame parsing (tests) | A new parser | `parse_sse_frames()` (already in both `tests/agent/test_sse.py` and re-exported from `tests/api/conftest.py`) | Already exists, already tested, already used by 3+ test files |
| Contract test HTTP client | A new mock-request harness | `httpx.AsyncClient(transport=ASGITransport(app=app))` | Established pattern across every file in `tests/api/` |

**Key insight — the one deliberate exception in this phase:** rate limiting (item 6) is the one place this phase recommends a small hand-rolled solution (~20-30 lines: a `dict[str, deque[float]]` token-bucket keyed by `user_id`, checked as a FastAPI dependency chained after `Depends(get_current_user)`) rather than reaching for a library. This is not a general license to hand-roll — it is specific to this exact fit: (a) the codebase already has zero rate-limiting infrastructure to build on, (b) the requirement is explicitly "best-effort, single-user, not a strict distributed guarantee" (D-02), (c) the one credible library candidate (`slowapi`) is flagged `[SUS]` by the legitimacy gate and its key-function design doesn't fit this app's `Depends(get_current_user)`-first auth pattern without an awkward `request.state` side-channel, and (d) the actual data structure needed (a sliding window counter per user) is genuinely simple enough that the library adds more integration surface (middleware registration, exception handler wiring, decorator + `Request` param plumbing on 2 routes) than it removes.

## Runtime State Inventory

> This phase includes deterministic bug-fix/hygiene items but is not a rename/refactor/migration phase (no strings are being renamed across systems). This section is included for completeness per protocol but most categories are not applicable.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — no renamed keys, IDs, or collection names in this phase | None |
| Live service config | None — no n8n/Datadog/Tailscale/Cloudflare equivalents in this stack | None |
| OS-registered state | None — no Task Scheduler/pm2/launchd/systemd registrations in this project | None |
| Secrets/env vars | **New:** `SSE_TOKEN_SECRET` must be generated (e.g. `openssl rand -hex 32`) and added to local `.env`/`.env.example` and to Vercel's production environment variables before item 5 can work end-to-end in deployment. This is a genuinely new secret, not a rename of an existing one | Generate + add to both local `.env.example` (placeholder) and Vercel env (real value); verify presence at deploy time |
| Build artifacts | Root `node_modules/` (4.0K, effectively empty, no root `package.json` exists to justify it — verified via `ls -la`) and `test-ride.fit` (66 bytes, verified as a stray fixture, not a real ride file) are both currently untracked and unignored (verified: `git check-ignore` returns nothing for either) | `rm -rf node_modules/ test-ride.fit` at repo root; add both patterns to root `.gitignore` |

## Common Pitfalls

### Pitfall 1: "Just add auth headers" is necessary but not sufficient for the 8 SSE tests
**What goes wrong:** Adding `auth_headers()` alone still fails all 8 tests, but with a *different* symptom (200 status, but an `invalid_conversation_id` error frame instead of the expected mock event sequence), which can look like a new, confusing regression if the fix is applied incrementally without awareness of the CR-03 ownership check added in Phase 8.
**Why it happens:** `chat_stream` added a conversation-ownership validation step (`_resolve_conversation_id`) after these tests were originally written, and the test file's placeholder `conversation_id="test-001"` is not a valid UUID, so it is silently treated as unowned/foreign.
**How to avoid:** Apply all three fixes from Pattern 1 together (auth headers + `_resolve_conversation_id` bypass + `**kwargs` on mock `run_turn` functions), verified together in this session to produce the correct token/done frame sequence.
**Warning signs:** A 200 response with a single `error` frame containing `"code": "invalid_conversation_id"` (not the expected token/tool_start/tool_result/done sequence) — that specific error code, seen after adding only auth headers, is the tell that the ownership-check bypass step is still missing.

### Pitfall 2: The other module-level Supabase singleton
**What goes wrong:** CONTEXT.md's discretion note directs attention to `backend/agent/audit.py` as the place to check for a similar leak to `capability_gap.py`'s (already-fixed) pattern. `audit.py` is actually clean (it uses the centralized `backend/db.py` singleton via `get_async_supabase`, per its own module docstring: "this module intentionally does NOT define its own module-level client-cache singleton"). The real duplicate is `backend/sports_science/profile.py`, which has the exact same unreset `_supabase_client` module-level cache pattern that `capability_gap.py` had before its fix — verified by direct comparison of both files' source.
**Why it happens:** `profile.py`'s `_get_async_supabase()` was written by copying `capability_gap.py`'s pre-fix pattern (its own docstring says "Uses the same async singleton pattern as capability_gap.py (WR-04)") but the `_reset_client_for_tests()` fixup was never propagated to it.
**How to avoid:** Add an identical `_reset_client_for_tests()` function to `profile.py` and wire it into the same autouse fixture in `tests/sports_science/conftest.py` (extend `_reset_capability_gap_client` to also reset `profile`, or add a second autouse fixture) as a preventive fix, even though no test currently exercises the leak (verified: the one existing `save_profile` test, `test_tools_phase3.py::test_save_profile_upserts`, uses `monkeypatch.setattr(profile_module, "_supabase_client", mock_client)`, which self-reverts via monkeypatch's own teardown and doesn't currently trigger the leak — but a future test that calls the real `_get_async_supabase()` un-mocked would be exposed to it, exactly as `capability_gap.py`'s tests once were).
**Warning signs:** A `save_profile`-related test passing or failing depending on test execution order/`-p no:randomly` settings, or a DB-outage regression test for `profile.py` silently returning a cached "working" client instead of exercising the failure path.

### Pitfall 3: Playwright mocks use different field names than the real backend (verified, not just suspected)
**What goes wrong:** Both `frontend/tests/e2e/full-uat.spec.ts` and `phase4.spec.ts`'s `fixtureRides` use `duration_seconds` and `avg_power_watts` — the pre-Phase-9 field names. The real backend (and the frontend's own `Ride` TS interface) use `duration_secs` and `avg_power` (verified via direct read of both spec files and `backend/routes/rides.py`/`api.ts`). The fixtures also include `file_name` and `distance_m`, which don't exist in the real `Ride` shape at all, and omit `intensity_factor`, `avg_hr`, `avg_cadence`, `ftp_used` that the real backend does return.
**Why it happens:** The Phase 9 field-name fix (`duration_secs`/`avg_power`) was applied to production code (`backend/routes/rides.py`, `frontend/src/lib/api.ts`) but never propagated to the Playwright test fixtures, so the e2e tests have been asserting against a shape the real API hasn't returned since Phase 9.
**How to avoid:** Update `fixtureRides` in both spec files to the real shape: `duration_secs`, `avg_power` (drop `duration_seconds`, `avg_power_watts`, `file_name`, `distance_m`); optionally add `intensity_factor`/`avg_hr`/`avg_cadence`/`ftp_used` for completeness even though the UI doesn't currently read them, so the fixture stays a faithful mirror of the real response.
**Warning signs:** A Playwright test asserting on a rendered ride-history row's power/duration values passing today only because the UI component being tested doesn't actually read the (wrong) mocked field name for that value — a false-negative-safe test, not a true one.

### Pitfall 4: The rate-limit banner's "skip retry" rule needs a fix in `OnboardingScreen.tsx` too, not just `useSSEStream.ts`
**What goes wrong:** `10-UI-SPEC.md` assumes `OnboardingScreen.tsx`'s existing `!res.ok` branch "can read a detail/message string" from a 429 response body. Verified in this session: it currently cannot — the branch (`if (!res.ok || !res.body)`) unconditionally calls the existing silent `retry()` and then falls back to a single hardcoded string (`'Could not connect to coach. Try again.'`), regardless of status code or response body content.
**Why it happens:** This branch predates the rate-limiting feature; it was written to handle generic connection failures only.
**How to avoid:** Add a status-code check (`res.status === 429`) before the existing `retry()` call in both `OnboardingScreen.tsx` fetch call sites (there are two — initial start and continuation), parse the JSON body for a `detail`/`message` string, and set that as `streamError` directly (skipping `retry()`) per the UI-SPEC's interaction rule. This mirrors the change already needed in `useSSEStream.ts`'s `error` listener (check `data.code === 'rate_limited'` before the existing retry-count logic).
**Warning signs:** A rate-limited onboarding request auto-retrying immediately (visibly compounding the rate limit, exactly the failure mode the UI-SPEC's interaction rule exists to prevent) or showing the generic "Could not connect to coach" copy instead of the rate-limit-specific copy.

### Pitfall 5: `slowapi`'s decorator model doesn't naturally key by `user_id`
**What goes wrong:** `slowapi`'s `@limiter.limit(...)` decorator's `key_func` receives only a `Request` object — it has no visibility into the FastAPI `Depends(get_current_user)` result unless that dependency is modified to stash `user_id` onto `request.state` as a side effect (verified via WebSearch: this is the documented workaround pattern, not a first-class feature).
**Why it happens:** `slowapi` (and the Flask-Limiter design it ports) was built around IP-based limiting as the default case; user-identity-based limiting is a secondary use case requiring the `request.state` side-channel.
**How to avoid:** This is exactly why the hand-rolled dependency (chained directly after `Depends(get_current_user)`, receiving `current_user["user_id"]` as a normal function argument, no `Request`/`request.state` plumbing needed) is simpler for this specific app than adopting `slowapi`.
**Warning signs:** A rate-limit implementation that requires modifying `get_current_user`'s signature to accept `request: Request` purely to satisfy a rate-limiting library's key function, when the same information is already available directly as `current_user["user_id"]` inside the route handler.

## Code Examples

### Hand-rolled in-process rate limiter (item 6, recommended)
```python
# backend/rate_limit.py — NEW FILE
"""
In-process, best-effort rate limiter for LLM-backed endpoints (D-02, D-03).

Not a distributed guarantee: Vercel Fluid Compute may reuse instances across
requests but does not guarantee a single shared instance, so this can
under-count across cold starts / multiple warm instances. That is an accepted
tradeoff for a single-user personal app (D-02) — this is a cost/abuse safety
net against a runaway retry loop, not hardened multi-tenant infrastructure.
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
    """Returns True if the request is allowed; False if over the limit."""
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
            detail={"error": "rate_limited", "detail": "You're sending messages a bit fast. Wait a moment and try again."},
        )
    return current_user


def is_rate_limited(user_id: str) -> bool:
    """
    Non-raising check for streaming endpoints (chat/stream), where a 429
    status can't be used mid-stream — the caller returns a StreamingResponse
    yielding an `error` frame instead (see chat.py's existing
    _invalid_conversation_stream pattern).
    """
    return not _check_and_record(user_id)
```

### Wiring into `chat_stream` (mirrors the existing `_invalid_conversation_stream` pattern)
```python
# backend/routes/chat.py — inside chat_stream, after resolving user_id,
# before the conversation_id resolution:
from backend.rate_limit import is_rate_limited

if is_rate_limited(user_id):
    async def _rate_limited_stream():
        error_data = json.dumps({
            "code": "rate_limited",
            "message": "You're sending messages a bit fast. Wait a moment and try again.",
        })
        yield f"event: error\ndata: {error_data}\n\n"
    return StreamingResponse(
        _rate_limited_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

### GitHub Actions CI workflow (item 7, D-05 locked: report-only, no branch protection)
```yaml
# .github/workflows/ci.yml — NEW FILE
name: CI
on:
  push:
  pull_request:

jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-python@v6
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt
      - run: ruff check .
      - run: pytest tests/ -q

  frontend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-node@v6
        with:
          node-version: '22'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json
      - run: npm ci
      - run: npm run test -- --run
```
Note: `npm run test` invokes `vitest` (from `frontend/package.json`'s `scripts.test`), which defaults to watch mode — `-- --run` is required in CI to run once and exit. Playwright e2e (`npm run test:e2e`) is deliberately NOT included per D-05's scope (CONTEXT.md only specifies pytest + vitest + ruff for CI; Playwright requires browser binary provisioning and is a reasonable future CI addition, not this phase's scope).

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Full Supabase JWT in `?token=` query string for SSE | Short-lived (~60s) opaque/signed exchange token | This phase (item 5) | Full JWT no longer appears in server access logs for the SSE endpoint; exposure window limited to the token's 60s lifetime |
| No rate limiting on LLM endpoints | In-process token-bucket, best-effort | This phase (item 6) | A runaway client-side retry loop can no longer burn unbounded Anthropic API spend silently |
| No CI | GitHub Actions: pytest + vitest + ruff, report-only | This phase (item 7) | Regressions like the 8 stale SSE tests become visible on every push instead of only being caught by a full manual `pytest tests/ -q` run |

**Deprecated/outdated:**
- Embedding the real Supabase access token directly in the SSE URL (`frontend/src/lib/api.ts`'s `sseUrl`, pre-this-phase) — replaced by the token-exchange endpoint.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `SSE_TOKEN_SECRET` does not already exist as an env var in this project (a genuinely new secret, not a rename) | Runtime State Inventory | Low — if it does exist for another purpose, a name collision would need to be caught in code review before deploy; trivial to rename |
| A2 | 10 requests/minute per `user_id` is a reasonable default threshold for both `chat/stream` and `onboarding/start` | Code Examples (rate_limit.py) | Low — D-03 explicitly leaves the exact number to Claude's discretion at planning/execution time; easy to tune post-hoc since it's a single constant |
| A3 | GitHub Actions `actions/checkout@v6`/`setup-python@v6`/`setup-node@v6` are the current major versions as of this research date | Standard Stack, Code Examples | Low — action versions are trivially bumpable; even if a newer major exists by execution time, `v6` will still function (GitHub maintains back-compat within reason) |

**If this table is empty:** N/A — see entries above. All three are low-risk, easily-correctable assumptions; none affect the core design decisions (which are all `[VERIFIED]` against the actual codebase and a live test run in this session).

## Open Questions

1. **Is `SUPABASE_JWT_SECRET` actually configured in the production (Vercel) environment, or does production rely solely on JWKS/ES256?**
   - What we know: `backend/auth.py` supports both paths; local test env sets `SUPABASE_JWT_SECRET` via `monkeypatch.setenv`, proving the HS256 path works when the var is present. `.env`/`.env.example` are outside this research session's read permissions (project sandboxing denied access).
   - What's unclear: Whether production Vercel env vars include `SUPABASE_JWT_SECRET` at all.
   - Recommendation: Irrelevant to item 5's design as recommended here — the new `SSE_TOKEN_SECRET` is deliberately independent of `SUPABASE_JWT_SECRET`'s presence/absence, precisely to sidestep this uncertainty. No action needed unless a future phase wants to consolidate secrets.

2. **Exact rate-limit threshold values (D-03, explicitly Claude's discretion)**
   - What we know: Must not interrupt normal onboarding/chat use; must stop a runaway retry loop.
   - What's unclear: No usage telemetry exists yet to calibrate precisely (single-user app, no prior traffic data).
   - Recommendation: Start with 10 requests/minute per `user_id` on both endpoints (see Code Examples); trivially tunable as a single constant if it proves too tight or too loose during actual use.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 venv (`.venv/`) | All backend test/lint work | ✓ | 3.12 (venv); host `python3` reports 3.14.4 but `.venv` is pinned to project's target | — |
| Node.js | Frontend build/test, CI | ✓ | v25.9.0 (host); CI pins `node-version: '22'` explicitly | — |
| `pytest`/`ruff` installed in `.venv` | Items 1-4, CI | ✓ | 9.1.1 / 0.15.18 | — |
| `frontend/package-lock.json` | CI's `npm ci` step | ✓ | present | — |
| Root `package-lock.json` | N/A | ✗ (does not exist, and should not — no root `package.json` exists either) | — | Confirms root `node_modules/` (item 8) is orphaned, not a legitimate root-level JS project |
| GitHub Actions (`.github/workflows/`) | Item 7 | ✗ (directory does not exist yet) | — | This phase creates it; no fallback needed, it's the deliverable |

**Missing dependencies with no fallback:** None — the one "missing" item (`.github/workflows/`) is this phase's own deliverable, not a blocker.

**Missing dependencies with fallback:** None applicable.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework (backend) | pytest 9.1.1 + pytest-asyncio 1.4.0, `asyncio_mode = auto` (`pytest.ini`) |
| Framework (frontend) | Vitest 4.1.9 (`frontend/vitest.config.ts`) + Playwright 1.61.0 (e2e, not in CI scope this phase) |
| Config file | `pytest.ini` (backend), `frontend/vitest.config.ts` / `frontend/playwright.config.ts` (frontend) |
| Quick run command (backend) | `.venv/bin/pytest tests/agent/test_sse.py -q` (targeted) or `.venv/bin/pytest tests/ -q` (full, currently 7.5s for 330 tests — verified in this session) |
| Full suite command | `make check` (runs `ruff check .` then `pytest tests/ -v`, per existing `Makefile`) |

### Phase Requirement → Test Map
> This phase has no mapped REQ-IDs (predates REQ-ID mapping — see phase description). The table below maps the 8 scope items to their verification instead.

| Item | Behavior | Test Type | Automated Command | File Exists? |
|------|----------|-----------|---------------------|--------------|
| 1. SSE tests | 8 stale tests pass with real auth + real event sequencing | unit | `.venv/bin/pytest tests/agent/test_sse.py -q` | Yes (fix in place, verified this session — see Pattern 1) |
| 2. Capability-gap leak | No cross-test leak in full suite; `profile.py` gets the same reset hook as a preventive measure | unit | `.venv/bin/pytest tests/ -q` (confirm 0 unexpected failures) + `.venv/bin/pytest tests/sports_science/ tests/agent/test_tools_phase3.py -q` | Yes — `tests/sports_science/conftest.py` exists; extend it |
| 3. Playwright mocks | e2e fixtures match real field names | e2e | `cd frontend && npx playwright test` | Yes (`frontend/tests/e2e/*.spec.ts`) — not run in CI this phase, run manually/pre-merge |
| 4. Contract tests | New tests assert field-presence for rides/profile/sessions | unit/integration | `.venv/bin/pytest tests/api/test_contracts.py -q` | ❌ Wave 0 — new file |
| 5. SSE token exchange | `POST /chat/token` mints a valid ephemeral token; `GET /chat/stream?token=<ephemeral>` authenticates | unit/integration | `.venv/bin/pytest tests/api/test_chat.py -q` (extend) or a new `tests/api/test_chat_token.py` | ❌ Wave 0 — new test(s) needed |
| 6. Rate limiting | Nth+1 request within window returns rate-limited response (SSE error frame for chat, 429 for onboarding) | unit | New tests in `tests/api/test_chat.py` / `tests/api/test_onboarding.py` | ❌ Wave 0 — new tests needed |
| 7. CI | Workflow runs and reports status on push | manual-only (infra) | N/A — verified by pushing and observing the Actions tab | N/A |
| 8. Repo cleanup | `node_modules/`, `test-ride.fit` removed and gitignored | manual-only | `git status --porcelain` shows neither as untracked after cleanup | N/A |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/ -q` (7.5s full run, verified in this session — cheap enough to run on every commit, no need to scope down)
- **Per wave merge:** `make check` (ruff + full pytest)
- **Phase gate:** Full suite green (0 failures) before `/gsd-verify-work`; additionally confirm `frontend && npx playwright test` passes for item 3, and `.gitignore`/`git status` are clean for item 8.

### Wave 0 Gaps
- [ ] `tests/api/test_contracts.py` — new file, covers item 4
- [ ] New rate-limit assertions in `tests/api/test_chat.py`/`test_onboarding.py` — covers item 6
- [ ] New token-exchange assertions (extend `tests/api/test_chat.py` or new `test_chat_token.py`) — covers item 5
- [ ] `backend/rate_limit.py` — new module, no existing test file (Wave 0 must create both the module and its test)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|----------------|---------|-------------------|
| V2 Authentication | Yes | Existing `get_current_user` (JWT via JWKS/ES256 or HS256) — item 5 extends this with a namespaced (`typ: "sse_token"`), short-lived, separately-keyed token type; never weakens the existing verification paths |
| V3 Session Management | Yes | The new SSE token is explicitly non-persistent and short-lived (~60s `exp`) by design — no session store introduced |
| V4 Access Control | Yes | CR-03's conversation ownership check (`_resolve_conversation_id`) is preserved unchanged by all fixes in this phase; item 1's test fix bypasses it only in test doubles, never in production code |
| V5 Input Validation | Yes | `validate_uuid` (existing, `backend/utils.py`) already guards `conversation_id`/`session_id` path/query params; no new user input surfaces are introduced by this phase except the rate-limit dependency, which takes no user-controlled input beyond the already-verified `user_id` |
| V6 Cryptography | Yes | Token signing continues to use `PyJWT` (HS256/ES256, already vetted); the new `SSE_TOKEN_SECRET` must be a high-entropy random value (e.g. `openssl rand -hex 32`), never hand-rolled |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|-----------------------|
| JWT leaking into access logs via query string | Information Disclosure | Item 5's short-lived token exchange (this phase) — reduces exposure window from the token's full lifetime to ~60s, and the leaked value can never be the real Supabase JWT |
| Token replay after the intended single-use window | Spoofing | The 60s `exp` claim bounds replay risk; no single-use/nonce tracking is added since that would require durable state, which D-04 explicitly rules out for this design |
| Unbounded LLM cost via runaway client retry loop | Denial of Service (cost-based) | Item 6's rate limiter — best-effort, in-process, accepted as non-distributed per D-02 |
| Rate-limit key confusion (limiting by IP instead of identity) | Spoofing / bypass | Key the limiter by `user_id` (post-auth), not by `Request`/IP — see Pitfall 5 for why `slowapi`'s default doesn't fit this cleanly |

## Sources

### Primary (HIGH confidence — direct codebase reads + live verification in this session)
- `backend/auth.py`, `backend/routes/chat.py`, `backend/routes/_sse.py`, `backend/routes/onboarding.py`, `backend/routes/rides.py`, `backend/routes/sessions.py`, `backend/main.py`, `backend/db.py`, `backend/sports_science/capability_gap.py`, `backend/sports_science/profile.py`, `backend/agent/audit.py` — read in full
- `tests/agent/test_sse.py`, `tests/api/conftest.py`, `tests/api/test_auth.py`, `tests/api/test_chat.py`, `tests/sports_science/conftest.py` — read in full
- `frontend/src/hooks/useSSEStream.ts`, `frontend/src/lib/api.ts`, `frontend/src/screens/OnboardingScreen.tsx`, `frontend/src/screens/ChatScreen.tsx`, `frontend/src/components/chat/StreamErrorBanner.tsx`, `frontend/tests/e2e/full-uat.spec.ts`, `frontend/tests/e2e/phase4.spec.ts` — read in full
- `.venv/bin/pytest tests/ -q` — executed this session, confirmed 322 passed / 8 failed (all 8 in `test_sse.py`, no capability-gap flakiness observed)
- 3 standalone verification scripts run against a live `httpx.AsyncClient(ASGITransport(app=app))` instance this session, confirming: (a) auth-headers-only still fails with `invalid_conversation_id`, (b) bypassing `_resolve_conversation_id` alone still fails with an unexpected-kwarg error, (c) all three fixes together produce the correct token/done frame sequence, and (d) omitting `conversation_id` with valid auth correctly 422s

### Secondary (MEDIUM confidence — cross-checked via WebSearch + PyPI registry)
- PyPI JSON API (`https://pypi.org/pypi/slowapi/json`) — version history, latest release date, dependency list
- [slowapi GitHub repo](https://github.com/laurentS/slowapi) — maintenance activity cross-check
- [GitHub Actions setup-python/setup-node/checkout release pages](https://github.com/actions/setup-python/releases) — current major versions

### Tertiary (LOW confidence — single WebSearch, not independently cross-checked)
- `slowapi` custom `key_func`/`request.state` pattern (Pitfall 5) — sourced from blog posts found via WebSearch, not official `slowapi` docs directly; flagged `[ASSUMED]`-adjacent even though the underlying mechanism (decorator receives only `Request`) is a reasonable inference from the library's public API shape

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages recommended for the primary path; existing pinned versions read directly from `requirements.txt`/`package.json`
- Architecture: HIGH — every pattern above was either read directly from existing code or executed against a live instance of the app this session
- Pitfalls: HIGH — all 5 pitfalls are verified findings from this session (live test execution or direct grep/read), not inferred from documentation alone
- Package legitimacy (`slowapi`): MEDIUM — gate returned `[SUS]`, cross-checked manually, disposition follows protocol (flag + recommend avoiding rather than override)

**Research date:** 2026-07-08
**Valid until:** 30 days (stable hygiene-phase findings; the one fast-moving element — GitHub Actions major versions — is trivially bumpable and non-blocking if stale by execution time)
