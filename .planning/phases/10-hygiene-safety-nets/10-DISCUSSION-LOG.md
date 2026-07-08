# Phase 10: Hygiene and Safety Nets - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-08
**Phase:** 10-hygiene-safety-nets
**Areas discussed:** Contract Tests, Rate Limiting, SSE Token Exchange, CI Gating
**Mode:** `--auto` (fully autonomous — no interactive prompts; Claude selected the recommended option for every question and logged it here for review)

---

## Contract Tests

| Option | Description | Selected |
|--------|-------------|----------|
| Full OpenAPI → TypeScript codegen | Generate frontend types from `/openapi.json`; structurally prevents drift but requires a new codegen build step + CI staleness check | |
| Targeted pytest assertions | Contract tests against the 3 endpoints that have actually broken before (rides, profile, sessions), asserting exact field names the frontend reads | ✓ |

**Selected:** Targeted pytest assertions.
**Notes:** Codegen is the stronger long-term fix but disproportionate to a hygiene phase whose other 7 items are narrow bug fixes. Deferred as a future-phase idea.

---

## Rate Limiting

| Option | Description | Selected |
|--------|-------------|----------|
| In-process limiter (slowapi / token bucket, keyed by user_id) | Best-effort cost/abuse guard; no new infra; imprecise across cold starts/multiple Fluid Compute instances | ✓ |
| Redis-backed distributed limiter (Upstash via Vercel Marketplace) | Correct under multi-instance/multi-tenant load; adds real infra + cost | |

**Selected:** In-process limiter.
**Notes:** Single-user personal app — the risk being guarded against is an accidental runaway retry loop burning Anthropic API spend, not adversarial multi-tenant abuse. Redis-backed limiting deferred as a future idea if the app ever gets real multi-user traffic.

---

## SSE Token Exchange

**Not a discussed gray area — pre-decided.** `backend/auth.py`'s existing `WR-006 KNOWN LIMITATION` code comment already specifies the target design (short-lived opaque/signed token via a new `POST /chat/token` endpoint, stateless verification, no DB/cache). Implemented as documented rather than re-litigated.

---

## CI Gating

| Option | Description | Selected |
|--------|-------------|----------|
| Report-only workflow | GitHub Actions runs pytest/vitest/ruff on push/PR; no branch protection | ✓ |
| Gated (branch protection required-checks) | Same workflow, but merges blocked on green CI | |

**Selected:** Report-only.
**Notes:** No PR-based workflow exists today (commits land directly on `main`); branch protection has nothing to attach to and is a repo-settings change outside code scope. Noted as a natural follow-on once a PR workflow exists.

---

## Claude's Discretion

- 8 stale SSE test fixes (reuse `tests/api/conftest.py`'s auth-token helpers)
- Capability-gap test-order leak: verify existing `_reset_client_for_tests` autouse fixture actually closes it (not currently reproducing)
- Playwright mock field-name corrections (match Phase 9's already-fixed backend shapes)
- Repo cleanup mechanics (`rm -rf node_modules/`, `rm test-ride.fit`, `.gitignore` additions)
- Exact rate-limit thresholds (D-03)

## Deferred Ideas

- Full OpenAPI → TypeScript codegen contract enforcement
- Redis-backed distributed rate limiting (Upstash)
- GitHub branch protection / required CI checks
