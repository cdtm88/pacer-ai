---
phase: 13
slug: close-gap-adapt-04-transp-03-wire-weekly-adaptation-check-ad
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-10
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Vitest 4.1.x + React Testing Library (frontend); pytest + pytest-asyncio, `asyncio_mode = auto` (backend, no changes expected) |
| **Config file** | `frontend/vite.config.ts` (vitest config), `pytest.ini` (testpaths = tests) |
| **Quick run command** | `cd frontend && npx vitest run src/tests/progress.test.tsx` |
| **Full suite command** | `cd frontend && npx vitest run` (frontend); `python -m pytest` (backend regression check) |
| **Estimated runtime** | ~15-30 seconds (frontend suite), ~60-90 seconds (full backend suite) |

---

## Sampling Rate

- **After every task commit:** Run the targeted vitest file for the file just changed (e.g. `npx vitest run src/tests/progress.test.tsx`)
- **After every plan wave:** Run `cd frontend && npx vitest run` (full frontend suite)
- **Before `/gsd-verify-work`:** Full frontend suite green + `python -m pytest tests/api/test_adaptations.py` green (regression check only, no backend changes expected)
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 13-01-01 | 01 | 0 | ADAPT-04/TRANSP-03 | T-13-01 | Malformed/nullable adaptation fields don't crash render | unit | `npx vitest run src/tests/progress.test.tsx` | ❌ W0 | ⬜ pending |
| 13-01-02 | 01 | 1 | TRANSP-03 | — | `Adaptation` interface matches real DB schema (`trigger`/`explanation_text`/`scope`/`trigger_session_ids`/`status`) | unit/contract | `cd frontend && npx tsc --noEmit` + `npx vitest run src/tests/progress.test.tsx` | ✅ (api.ts exists, interface wrong) | ⬜ pending |
| 13-02-01 | 02 | 0 | ADAPT-04 | T-13-02 | Fetch failure does NOT update the localStorage throttle timestamp (D-05) | unit | `npx vitest run src/tests/useAdaptationCheck.test.ts` | ❌ W0 | ⬜ pending |
| 13-02-02 | 02 | 1 | ADAPT-04 | — | `useAdaptationCheck` fires `checkAdaptations()` only when throttle window elapsed; mounts once via AppLayout, not per-route | unit | `npx vitest run src/tests/useAdaptationCheck.test.ts` (or extended `AppLayout.test.tsx`) | ⚠️ partial (AppLayout.test.tsx exists, no throttle coverage) | ⬜ pending |
| 13-03-01 | 03 | 1 | TRANSP-03 | — | Adaptations section renders humanized trigger + explanation_text + formatted date; empty state shows exact D-11 sentence | unit | `npx vitest run src/tests/progress.test.tsx` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `frontend/src/tests/progress.test.tsx` — does not exist; needed to cover the new Adaptations section (empty/loading/error/data states)
- [ ] `frontend/src/tests/useAdaptationCheck.test.ts` (or extend `frontend/src/tests/AppLayout.test.tsx`) — needed to cover throttle timing + silent-failure-does-not-update-timestamp behavior (D-05 is the highest-risk decision in this phase and has zero existing test coverage)
- [ ] Shared test fixture for a realistic `Adaptation` object (using the corrected real schema fields: `trigger`, `explanation_text`, `scope`, `created_at`, etc.) — needed by the new progress test file to avoid re-deriving the shape ad hoc

---

## Manual-Only Verifications

*None — all phase behaviors have automated verification. This is a frontend-only, single-tenant wiring phase with no physical-device or third-party-integration surface.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
