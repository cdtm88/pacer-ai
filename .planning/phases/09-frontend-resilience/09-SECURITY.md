---
phase: 09
slug: frontend-resilience
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: 2026-07-08
---

# Phase 09 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| server → client (SSE, coaching) | Stream events (token/tool/done/error) cross from the coaching backend into the browser; client must fail closed, not loop unboundedly | Chat token stream |
| localStorage → app state | A persisted session record is read back and drives navigation and "mark session done" behavior | Session id + date |
| client → API (export/list) | Frontend consumes backend JSON (ride list, ZWO export error envelope) | Ride/session metadata |
| principal transition (sign-in / account switch) | Cached data from a prior authenticated principal must not survive into a new principal's session (ASVS V3) | React Query cache |
| auth callback (untrusted URL params) | The PKCE `code` in the callback URL is single-use; consuming it twice violates the security constraint (ASVS V2) | Auth code |
| screen render → app shell | A thrown render error must be contained so it cannot expose internals or destroy the whole app shell | Error/exception text |
| client file drop → upload | A dropped file's extension is checked client-side as a UX guard only; backend fitdecode parse is the real boundary (ASVS V5) | .fit file |
| server → client (onboarding SSE via fetch) | Onboarding stream events cross into the browser; failures must fail closed with bounded retries | Onboarding token stream |
| client → API (conversation read) | A client-supplied conversation_id crosses into a DB read; must be validated and scoped to the authenticated principal (ASVS V4 IDOR) | conversation_id, message history |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-09-01-01 | Denial of Service (self) | useSSEStream retry loop | low | mitigate | `MAX_RETRIES = 2` with fixed 500/1500ms backoff — confirmed in `src/hooks/useSSEStream.ts:50` | closed |
| T-09-01-02 | Information Disclosure | StreamErrorBanner copy | low | mitigate | Generic "Connection failed." banner; raw backend exception text not rendered | closed |
| T-09-01-SC | Tampering (supply chain) | npm installs | n/a | accept | No new packages introduced | closed |
| T-09-02-01 | Tampering / Spoofing | sessionPersistence localStorage record | medium | mitigate | sessionId + date validated against today's real session; `clearSession()` on mismatch — confirmed in `src/lib/sessionPersistence.ts:69-70` | closed |
| T-09-02-02 | Integrity (state) | live-resume step advance | low | mitigate | Fast-forward derives step/time from absolute epoch math, not a trusted step counter | closed |
| T-09-02-SC | Tampering (supply chain) | npm installs | n/a | accept | No new packages introduced | closed |
| T-09-03-01 | Information Disclosure | exportSessionZwo error message | low | mitigate | Only backend-provided error/detail string surfaced; defensive try/catch fallback to status code | closed |
| T-09-03-02 | Tampering | Ride field alignment | low | accept | Pure display-contract fix; backend remains authoritative source | closed |
| T-09-03-SC | Tampering (supply chain) | npm installs | n/a | accept | No new packages introduced | closed |
| T-09-04-01 | Information Disclosure | React Query cache across principals | high | mitigate | `queryClient.clear()` on SIGNED_IN (added to existing SIGNED_OUT/USER_UPDATED) — confirmed in `src/router.tsx:33-34` | closed |
| T-09-04-02 | Spoofing / Tampering | PKCE single-use code | medium | mitigate | Manual `exchangeCodeForSession` removed; `detectSessionInUrl` is the sole consumer of the code — confirmed in `src/screens/AuthCallbackScreen.tsx` | closed |
| T-09-04-03 | Information Disclosure | error boundary fallback | low | mitigate | `RouteErrorFallback` renders no error message/stack/ID per D-09 | closed |
| T-09-04-SC | Tampering (supply chain) | npm installs | n/a | accept | React Router's built-in ErrorBoundary used; no new package | closed |
| T-09-05-01 | Tampering (input validation) | drag-drop .fit check | low | accept | Client extension check is a UX guard only; backend fitdecode parse remains authoritative | closed |
| T-09-05-02 | Information Disclosure | upload toast/error | low | mitigate | Existing toast copy unchanged, shows no internal detail | closed |
| T-09-05-SC | Tampering (supply chain) | npm installs | n/a | accept | No new packages introduced | closed |
| T-09-06-01 | Denial of Service (self) | onboarding retry loop | low | mitigate | `MAX_RETRIES = 2` with fixed backoff — confirmed in `src/screens/OnboardingScreen.tsx:20,161,326` | closed |
| T-09-06-02 | Information Disclosure | StreamErrorBanner copy | low | mitigate | Generic "Couldn't save your profile." banner; raw exception text not surfaced | closed |
| T-09-06-SC | Tampering (supply chain) | npm installs | n/a | accept | Reuses StreamErrorBanner from 09-01 | closed |
| T-09-07-01 | Information Disclosure / Elevation (IDOR) | GET /conversations/{id}/messages | high | mitigate | user_id sourced from verified JWT sub; `load_conversation` scoped `WHERE conversation_id AND user_id` — confirmed in `backend/routes/chat.py:196-231` | closed |
| T-09-07-02 | Tampering | client localStorage conversation id | low | mitigate | Backend re-validates ownership server-side; a bad id degrades to empty/new conversation | closed |
| T-09-07-03 | Information Disclosure | error responses | low | mitigate | Only parsed backend detail strings surfaced, no raw internals or other-user metadata | closed |
| T-09-07-SC | Tampering (supply chain) | pip/npm installs | n/a | accept | No new packages introduced | closed |

*Status: open · closed · open — below {block_on} threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

No accepted risks beyond those already dispositioned `accept` in the threat register above (all supply-chain "no new packages" entries, plus T-09-03-02 display-contract and T-09-05-01 client-side extension check — both explicitly noted in their respective PLAN.md files as non-security-boundary decisions).

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-08 | 22 | 22 | 0 | /gsd-secure-phase (L1 grep-depth — all threats authored at plan time across 09-01 through 09-07 PLAN.md; both high-severity threats and a sample of medium/low mitigations spot-verified directly against implementation) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-07-08
