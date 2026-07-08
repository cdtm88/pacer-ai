---
phase: 10
slug: hygiene-safety-nets
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-08
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 + pytest-asyncio 1.4.0 (`asyncio_mode = auto`, backend); Vitest 4.1.9 + Playwright 1.61.0 (frontend) |
| **Config file** | `pytest.ini` (backend); `frontend/vitest.config.ts` / `frontend/playwright.config.ts` (frontend) |
| **Quick run command** | `.venv/bin/pytest tests/ -q` |
| **Full suite command** | `make check` (ruff check . && pytest tests/ -v) |
| **Estimated runtime** | ~8 seconds (backend full suite, verified this session) |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/ -q`
- **After every plan wave:** Run `make check`
- **Before `/gsd-verify-work`:** Full suite must be green (0 failures); additionally confirm `cd frontend && npx playwright test` passes and `git status --porcelain` shows neither `node_modules/` nor `test-ride.fit` as untracked
- **Max feedback latency:** 8 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 10-xx-01 | TBD | TBD | Item 1: SSE tests | — | Auth + conversation ownership enforced, no bypass in prod code | unit | `.venv/bin/pytest tests/agent/test_sse.py -q` | ✅ | ⬜ pending |
| 10-xx-02 | TBD | TBD | Item 2: capability-gap leak | — | No cross-test client-singleton leak | unit | `.venv/bin/pytest tests/sports_science/ tests/agent/test_tools_phase3.py -q` | ✅ | ⬜ pending |
| 10-xx-03 | TBD | TBD | Item 3: Playwright mocks | — | Mocks match real field names | e2e | `cd frontend && npx playwright test` | ✅ | ⬜ pending |
| 10-xx-04 | TBD | TBD | Item 4: contract tests | — | Response field-presence asserted for rides/profile/sessions | unit/integration | `.venv/bin/pytest tests/api/test_contracts.py -q` | ❌ W0 | ⬜ pending |
| 10-xx-05 | TBD | TBD | Item 5: SSE token exchange | T-10-01 | Short-lived namespaced token (`typ: sse_token`), ~60s exp, never the real Supabase JWT | unit/integration | `.venv/bin/pytest tests/api/test_chat.py -q` (or new `test_chat_token.py`) | ❌ W0 | ⬜ pending |
| 10-xx-06 | TBD | TBD | Item 6: rate limiting | T-10-03 | Limiter keyed by `user_id` (post-auth), not IP; 429/SSE-error on Nth+1 | unit | New tests in `tests/api/test_chat.py` / `tests/api/test_onboarding.py` | ❌ W0 | ⬜ pending |
| 10-xx-07 | TBD | TBD | Item 7: CI | — | Workflow runs pytest+vitest+ruff, reports status | manual-only | N/A — verify via GitHub Actions tab after push | N/A | ⬜ pending |
| 10-xx-08 | TBD | TBD | Item 8: repo cleanup | — | `node_modules/`, `test-ride.fit` removed and gitignored | manual-only | `git status --porcelain` | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*Task IDs are placeholders (`10-xx-NN`) — the planner assigns real plan/task IDs; this table's Item→Test mapping is the binding contract regardless of final IDs.*

---

## Wave 0 Requirements

- [ ] `tests/api/test_contracts.py` — new file, contract tests for rides/profile/sessions (item 4)
- [ ] `backend/rate_limit.py` — new module; no existing test file, Wave 0 must create both the module and its test (item 6)
- [ ] New rate-limit assertions in `tests/api/test_chat.py` / `tests/api/test_onboarding.py` (item 6)
- [ ] New token-exchange assertions (extend `tests/api/test_chat.py` or new `tests/api/test_chat_token.py`) (item 5)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| CI workflow actually runs and reports pass/fail | Item 7 | GitHub Actions execution can't be observed from a local pytest/vitest run | Push the branch/commit; open the repo's Actions tab; confirm the workflow triggers and all 3 jobs (pytest, vitest, ruff) report status |
| Repo cleanup persists | Item 8 | Absence of a file/directory isn't a test assertion, it's a filesystem/git state check | Run `git status --porcelain`; confirm `node_modules/` and `test-ride.fit` do not appear as untracked; confirm `.gitignore` contains entries preventing recurrence |
| Playwright e2e suite passes end-to-end | Item 3 | Full browser automation run, not part of the fast per-commit sampling loop (config already marks e2e as pre-merge, not CI-blocking this phase) | `cd frontend && npx playwright test` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (test_contracts.py, rate_limit.py + test, token-exchange tests)
- [ ] No watch-mode flags
- [ ] Feedback latency < 8s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
