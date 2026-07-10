---
phase: 10
slug: hygiene-safety-nets
status: verified
threats_open: 0
asvs_level: 1
created: 2026-07-08
---

# Phase 10 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| browser → `GET /chat/stream?token=` | EventSource cannot send headers; a credential rides in the query string and lands in access logs | bearer-equivalent token |
| `POST /chat/token` minting | server-side signing of a bearer-equivalent credential | Supabase JWT in, ephemeral `sse_token` out |
| `sse_token` ↔ real Supabase JWT | two token types verified by the same `get_current_user` dependency must never be confused | JWT claims |
| `chat/stream`, `onboarding/start` rate limiter | per-user_id request budget guarding Anthropic API spend | user_id, request timestamps |
| GitHub Actions CI | third-party action execution, dependency install | no repo secrets referenced |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-10-01-01 | Elevation | `test_sse.py` `_resolve_conversation_id` monkeypatch | medium | mitigate | Bypass exists only in test doubles; production `chat_stream` keeps the CR-03 ownership check unchanged | closed |
| T-10-01-02 | Tampering | `profile.py` module-level `_supabase_client` | low | mitigate | `_reset_client_for_tests()` + autouse fixture reset (parity with `capability_gap.py`) | closed |
| T-10-01-03 | Tampering | `test_contracts.py` false-green risk | low | mitigate | Subset field-presence assertions verified to FAIL when a field is dropped | closed |
| T-10-02-01 | Tampering | e2e `fixtureRides` field names | low | mitigate | Mock field names aligned with real `GET /rides/` contract | closed |
| T-10-02-02 | Repudiation | e2e suite as regression guard | low | accept | Playwright deliberately out of CI (D-05); run pre-merge manually | closed |
| T-10-03-01 | Information Disclosure | `GET /chat/stream?token=` query param | high | mitigate | Short-lived (~60s) namespaced `sse_token` replaces the full Supabase JWT in the SSE URL — verified via `tests/api/test_chat_token.py` | closed |
| T-10-03-02 | Spoofing (token confusion) | `get_current_user` verify path | high | mitigate | `typ: "sse_token"` namespace guard + dedicated `SSE_TOKEN_SECRET` (never `SUPABASE_JWT_SECRET`) | closed |
| T-10-03-03 | Elevation (weak secret) | `SSE_TOKEN_SECRET` | high | mitigate | High-entropy secret (`openssl rand -hex 32`); HS256 via PyJWT; missing secret → HTTP 500, never an unsigned token — confirmed set in Vercel Production+Preview (UAT test 1) | closed |
| T-10-03-04 | Spoofing (token replay) | ephemeral sse_token | medium | accept | 60s `exp` bounds replay window; no nonce tracking (D-04, single-user app) | closed |
| T-10-03-05 | Information Disclosure | `.env.example` / committed secrets | low | mitigate | Only a commented placeholder in `.env.example`; real value lives in Vercel env only | closed |
| T-10-04-01 | Denial of Service (cost) | `POST /onboarding/start`, `GET /chat/stream` | high | mitigate | In-process sliding-window token bucket (~10 req/60s) keyed by user_id | closed |
| T-10-04-02 | Spoofing / bypass | rate-limit key dimension | medium | mitigate | Keyed by post-auth `user_id`, never IP/Request | closed |
| T-10-04-03 | Denial of Service (under-count) | Fluid Compute multi-instance | low | accept | Best-effort in-process limiter; Redis/Upstash deferred per D-02 | closed |
| T-10-04-04 | Denial of Service (self-inflicted retry storm) | frontend auto-retry on rate limit | medium | mitigate | Frontend skips silent auto-retry on `rate_limited` errors | closed |
| T-10-05-SC | Tampering (supply chain) | GitHub Actions checkout/setup-python/setup-node | medium | mitigate | Actions pinned to `@v6`, first-party only; `npm ci`/`requirements.txt`, no floating installs | closed |
| T-10-05-01 | Information Disclosure | ci.yml (secrets in logs) | medium | mitigate | Workflow references no repository secrets; runs against fixtures | closed |
| T-10-05-02 | Information Disclosure | root `node_modules/` + `test-ride.fit` | low | mitigate | Removed and gitignored | closed |
| T-10-06-SC | Tampering (supply chain) | GitHub Actions (post e2e-job removal) | low | mitigate | Net reduction in action surface; remaining actions/deps unchanged and pinned | closed |
| T-10-06-01 | Information Disclosure | ci.yml (secrets in logs) | low | mitigate | No repository secret referenced; confirmed via real GitHub Actions run 28959849726 | closed |
| T-10-06-02 | Denial of Service (false-red erosion) | ci.yml reliability | medium | mitigate | Both false-red sources (out-of-scope e2e job, frontend flake) removed/guarded; verified against a real GitHub Actions run, not local checks only | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above `workflow.security_block_on` (high) count toward `threats_open`*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-10-01 | T-10-02-02 | Playwright e2e is out of CI scope per D-05 (browser-binary provisioning cost); run manually pre-merge | Phase 10 CONTEXT.md D-05 | 2026-07-08 |
| AR-10-02 | T-10-03-04 | 60s token replay window accepted without nonce tracking; durable state explicitly ruled out by D-04 for a single-user app | Phase 10 CONTEXT.md D-04 | 2026-07-08 |
| AR-10-03 | T-10-04-03 | In-process rate limiter under-counts across Fluid Compute cold starts/multiple instances; best-effort accepted per D-02, Redis/Upstash deferred | Phase 10 CONTEXT.md D-02 | 2026-07-08 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-08 | 20 | 20 | 0 | gsd-secure-phase (retroactive register from PLAN.md threat_model blocks; L1/ASVS-1 short-circuit — all threats authored at plan time with mitigate/accept dispositions, verified closed via code review, tests, and live CI/UAT evidence) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-07-08
