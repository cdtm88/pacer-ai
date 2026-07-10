---
phase: 04
slug: ui-and-calendar
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-20
---

# Phase 04 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Vitest + React Testing Library (frontend) / pytest + httpx (backend) |
| **Config file** | `frontend/vite.config.ts` (vitest inline) / `pytest.ini` |
| **Quick run command** | `cd frontend && npm run test:run` |
| **Full suite command** | `cd frontend && npm run test:run && cd .. && pytest tests/ -x -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd frontend && npm run test:run`
- **After every plan wave:** Run `cd frontend && npm run test:run && cd .. && pytest tests/ -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------|-------------------|--------|
| Scaffold | 01 | 0 | UI-01..10 | build | `cd frontend && npm run build` | ⬜ pending |
| Auth JWT | 02 | 0 | UI-01 | unit | `pytest tests/test_auth.py -x -q` | ⬜ pending |
| Calendar OAuth | 03 | 1 | CAL-01,CAL-03 | unit | `pytest tests/test_calendar.py -x -q` | ⬜ pending |
| Nav routes | 04 | 1 | UI-07,UI-08 | component | `cd frontend && npm run test:run -- --reporter=verbose` | ⬜ pending |
| Session card | 05 | 2 | UI-02 | component | `cd frontend && npm run test:run` | ⬜ pending |
| Calendar sync | 06 | 2 | CAL-02,CAL-04 | integration | `pytest tests/test_calendar_sync.py -x -q` | ⬜ pending |
| PWA manifest | 07 | 3 | UI-09,UI-10 | build | `cd frontend && npm run build && ls dist/manifest.webmanifest` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `frontend/` — Vite + React + TypeScript project scaffolded
- [ ] `frontend/src/test/setup.ts` — Vitest + RTL setup
- [ ] `tests/test_auth.py` — JWT middleware stubs
- [ ] `tests/test_calendar.py` — Google Calendar OAuth stubs

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| iOS PWA install banner | UI-10 | iOS Simulator does not accurately represent Safari PWA behavior | Load on physical iOS device, verify banner appears on first visit |
| iOS install to home screen | UI-09 | No programmatic install API on iOS | Verify Share > Add to Home Screen flow on physical device |
| Google Calendar OAuth flow | CAL-01 | Requires live Google Cloud project + real OAuth redirect | Set up OAuth credentials, complete full consent flow end-to-end |
| During-Session offline | UI-05 | Requires network throttling | Use DevTools offline mode, verify session view still renders |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
