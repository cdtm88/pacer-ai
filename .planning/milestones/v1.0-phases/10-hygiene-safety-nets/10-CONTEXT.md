# Phase 10: Hygiene and Safety Nets - Context

**Gathered:** 2026-07-08
**Status:** Ready for planning

<domain>
## Phase Boundary

The test suite goes green and gets seam-level guards so the bug classes from Phases 6-9 (contract drift, silent auth breakage, log-leaked secrets, unbounded LLM cost) can't recur silently. Eight items, all bug-fix/infra hygiene, no new product capability:

1. 8 stale SSE tests fixed (now failing 401 instead of exercising the endpoint — JWT auth middleware was added after these tests were written)
2. Capability-gap test-order leak fixed (verify existing `_reset_client_for_tests` autouse fixture actually closes the leak; not reproducing in current full-suite run, so this may be a verify-and-close item rather than a build item)
3. Playwright mocks corrected to match real backend response shapes
4. Frontend-backend contract tests added (would have caught the past Ride/Profile/FTP-key field-name mismatches)
5. Short-lived SSE token exchange endpoint added, removing full Supabase JWTs from `?token=` query strings/logs
6. LLM endpoints (chat/stream, onboarding/start) rate-limited
7. CI runs pytest + vitest + ruff
8. Repo cleaned: root `node_modules/`, `test-ride.fit`, root `.gitignore` gaps

This is auto mode (`--auto`): no interactive questions were asked. Gray areas below were auto-resolved to the recommended option; all are logged for review before planning.

</domain>

<decisions>
## Implementation Decisions

### Contract Tests
- **D-01 [auto]:** Q: "How rigorous should frontend-backend contract tests be — full OpenAPI-to-TypeScript codegen, or targeted pytest assertions against the exact fields the frontend reads?" → Selected: **targeted pytest assertions**, scoped to the endpoints that have actually broken before (`rides`, `profile`/`save_profile`, `sessions`). Each contract test hits the real route (via the existing `httpx.AsyncClient` + `ASGITransport` pattern already used in `tests/api/`) with a mocked Supabase layer and asserts the response contains every key `frontend/src/lib/api.ts` reads for that resource, by name. Rationale: full OpenAPI→TS codegen is the structurally stronger fix (impossible for the two sides to drift), but it's a build-pipeline change (new codegen step, CI check that generated types are current, migration of hand-written interfaces in `api.ts`) that's disproportionate to a hygiene phase whose other 7 items are narrow, low-risk fixes. Codegen is a reasonable future phase, not this one — noted under Deferred.

### Rate Limiting
- **D-02 [auto]:** Q: "What rate-limiting mechanism for LLM endpoints, given Vercel's serverless/Fluid-Compute backend and a single-user personal app?" → Selected: **in-process limiter** (e.g. `slowapi` or an equivalent small dict/token-bucket keyed by `user_id`) on `chat/stream` and `onboarding/start`. This is a best-effort cost/abuse safety net, not a strict distributed guarantee — Fluid Compute reuses instances but doesn't guarantee a single shared instance across all requests, so the limiter can under-count across cold starts/multiple instances. Explicitly not selecting a Redis-backed limiter (Upstash via Vercel Marketplace): that's real infra + cost for a single-user app where the risk is "I fat-finger a loop," not adversarial multi-tenant abuse.
- **D-03 [auto]:** Exact limit values are Claude's discretion at planning/execution time (e.g. ~10 requests/min per user_id on chat/stream) — pick a threshold generous enough not to interrupt normal onboarding/chat use, tight enough to stop a runaway retry loop from burning Anthropic API spend.

### SSE Token Exchange
- **D-04 [pre-decided, from existing code]:** `backend/auth.py` already documents the target design inline (WR-006 TODO): add `POST /chat/token` that verifies the caller's real Supabase JWT (Bearer header) and returns a short-lived (~60s) opaque/signed token; the SSE URL then carries only that ephemeral token via `?token=`, not the full Supabase JWT. Implement exactly this — stateless verification (HMAC-signed with a short `exp` claim, no DB/cache row needed) fits the serverless backend and requires no new infra. This was locked by the prior implementer's own code comment, not re-litigated here.

### CI
- **D-05 [auto]:** Q: "Should CI gate merges (branch protection) or just report status?" → Selected: **report status only**. This repo has no PR-based workflow today (commits land directly on `main`; no branch protection observed). Add a GitHub Actions workflow triggered on push (and PRs, if any occur) running `pytest`, `vitest`, and `ruff check`; do not configure branch protection rules as part of this phase — that's a GitHub repo-settings change outside code scope, and premature for a solo project with no PR gate to attach it to.

### Claude's Discretion
Deterministic bug fixes with one clearly correct behavior — not real UX/product ambiguity:
- **8 stale SSE tests:** update `tests/agent/test_sse.py` to authenticate requests (reuse `tests/api/conftest.py`'s `make_test_token`/`auth_headers` pattern) so tests exercise real behavior instead of hitting 401 from the JWT middleware added since these tests were written.
- **Capability-gap test-order leak:** confirm `_reset_client_for_tests()` (already wired as an autouse fixture in `tests/sports_science/conftest.py`) actually eliminates the leak under the full suite and any other run order that matters (e.g. `pytest tests/ -q` already shows 322 passed / 8 failed with only the known SSE failures — no capability-gap flakiness observed). If confirmed closed, this item is verify-and-document, not new code.
- **Playwright mock corrections:** align `frontend/tests/e2e/*.spec.ts` route mocks with actual backend response shapes (the same field-name corrections already applied in production code during Phase 9, e.g. `duration_secs`/`avg_power`).
- **Repo cleanup:** `rm -rf node_modules/` (root-level, untracked, no `package.json` at root to justify its presence) and `rm test-ride.fit` (untracked stray fixture); add `node_modules/` and the stray fixture pattern to the root `.gitignore` so they can't silently reappear untracked.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Scope source
- `.planning/ROADMAP.md` §"Phase 10: Hygiene and Safety Nets" — the 8-item goal line this phase implements.
- `.planning/research/APP-REVIEW-260703.md` — origin of the Phase 6-10 roadmap split; background on why these items were flagged (contract mismatches, stale tests, missing CI).

### Existing design intent for the SSE token exchange
- `backend/auth.py` (module docstring + inline `WR-006 KNOWN LIMITATION` comment on `get_current_user`) — documents the exact short-lived-token design to implement for D-04. Read this before designing the token-exchange endpoint; the shape is already specified.
- `backend/routes/chat.py` (module docstring, SSE event schema) and `frontend/src/hooks/useSSEStream.ts` (header comment: "url MUST already include `?token=<jwt>`") — both sides of the current token-in-query-string mechanism that D-04 replaces.

### Prior phase context (patterns to follow)
- `.planning/phases/09-frontend-resilience/09-CONTEXT.md` — most recent prior phase; established the shared `useSSEStream.ts` hook and the project's "single-user personal app" framing (used above to size the rate-limiting decision).

No other external specs/ADRs apply — requirements fully captured in decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tests/api/conftest.py` — `TEST_USER_ID`, `make_test_token()`, `auth_headers()` already generate valid Supabase-style JWTs for authenticated test requests. `tests/agent/test_sse.py` should import and reuse this instead of inventing its own auth fixture.
- `tests/sports_science/conftest.py` — `_reset_client_for_tests()` autouse fixture pattern for module-level singleton clients; same pattern (`backend/sports_science/capability_gap.py`'s `_supabase_client` singleton) should be checked against `backend/agent/audit.py` or any other module-level client cache if the leak resurfaces elsewhere.
- `backend/auth.py`'s `get_current_user` — already supports both `Authorization: Bearer` and `?token=` query-param verification paths; the new short-lived-token endpoint slots into this same dependency rather than replacing it.

### Established Patterns
- `httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")` — the standard pattern across `tests/api/*.py` and `tests/agent/test_sse.py` for hitting FastAPI routes in tests without a live server.
- Mocked async Supabase client via `AsyncMock`/`MagicMock` chains (`client.table().insert().execute()`) — used throughout `tests/api/` and `tests/sports_science/test_capability_gap.py`; contract tests (D-01) should reuse this rather than a new mocking approach.

### Integration Points
- `tests/agent/test_sse.py` — the 8 failing tests; needs `current_user` dependency override or a valid `auth_headers()`-style token added to each request.
- `backend/routes/chat.py` + `backend/auth.py` — new `POST /chat/token` endpoint (D-04) and its consumption by the `?token=` fallback.
- `frontend/src/hooks/useSSEStream.ts` + `frontend/src/lib/api.ts`'s `sseUrl()` helper — frontend side of the token-exchange call before opening the `EventSource`.
- `backend/main.py` — where a new rate-limit dependency/middleware would be wired onto `chat/stream` and `onboarding/start` routes.
- Root `.gitignore`, root directory — repo cleanup targets (`node_modules/`, `test-ride.fit`).
- New: `.github/workflows/ci.yml` (does not exist yet) — CI workflow to add.

</code_context>

<specifics>
## Specific Ideas

No specific UI/UX requirements — this is backend/infra/test hygiene work. The one framing that carries through every decision: this is a **single-user personal app**, not a multi-tenant product. That context (established in Phase 9's CONTEXT.md) is why rate limiting is sized as a cost/abuse safety net rather than hardened multi-tenant infrastructure, and why CI is report-only rather than a merge gate.

</specifics>

<deferred>
## Deferred Ideas

- **Full OpenAPI → TypeScript codegen contract enforcement** — structurally stronger than the targeted pytest contract tests chosen for D-01 (impossible for frontend/backend types to silently drift), but it's a build-pipeline change disproportionate to this hygiene phase's scope. Worth a future phase if contract drift recurs despite the targeted tests.
- **Redis-backed distributed rate limiting** (Upstash via Vercel Marketplace) — the correct choice if this app ever has multiple real users or adversarial traffic; not needed for a single-user personal app today (D-02).
- **GitHub branch protection / required CI checks** — natural follow-on once there's an actual PR-based workflow; not applicable while commits land directly on `main`.

### Reviewed Todos (not folded)
None — no pending todos matched this phase (`todo.match-phase` returned zero matches).

</deferred>

---

*Phase: 10-hygiene-safety-nets*
*Context gathered: 2026-07-08*
