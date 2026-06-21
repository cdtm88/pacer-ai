---
phase: 05
slug: during-session-and-zwo-export
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-21
---

# Phase 05 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | vitest (frontend) + pytest 7.x (backend) |
| **Config file** | `frontend/vite.config.ts` / `api/pytest.ini` |
| **Quick run command** | `cd frontend && npm test -- --run` |
| **Full suite command** | `cd frontend && npm test -- --run && cd ../api && pytest` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd frontend && npm test -- --run`
- **After every plan wave:** Run `cd frontend && npm test -- --run && cd ../api && pytest`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | IOS-01 | — | N/A | unit | `cd frontend && npm test -- --run useDuringSession` | ❌ W0 | ⬜ pending |
| 05-01-02 | 01 | 1 | IOS-02 | — | N/A | unit | `cd frontend && npm test -- --run useWakeLock` | ❌ W0 | ⬜ pending |
| 05-02-01 | 02 | 1 | ZWO-01 | — | N/A | unit | `cd api && pytest tests/test_zwo_export.py -k test_xml_structure` | ❌ W0 | ⬜ pending |
| 05-02-02 | 02 | 1 | ZWO-02 | — | N/A | unit | `cd api && pytest tests/test_zwo_export.py -k test_power_fraction` | ❌ W0 | ⬜ pending |
| 05-02-03 | 02 | 1 | ZWO-03 | — | N/A | unit | `cd api && pytest tests/test_zwo_export.py -k test_pre_ftp_session` | ❌ W0 | ⬜ pending |
| 05-02-04 | 02 | 1 | ZWO-04 | — | N/A | unit | `cd api && pytest tests/test_zwo_export.py -k test_no_cadence_when_unspecified` | ❌ W0 | ⬜ pending |
| 05-03-01 | 03 | 2 | ZWO-05 | — | N/A | manual | human-verify: real Zwift import | — | ⬜ pending |
| 05-04-01 | 04 | 2 | IOS-03 | — | N/A | manual | human-verify: physical iOS Safari wake lock + tab switch | — | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `api/tests/test_zwo_export.py` — stubs for ZWO-01 through ZWO-05
- [ ] `frontend/src/hooks/__tests__/useDuringSession.test.ts` — timer + visibilitychange stubs for IOS-01
- [ ] `frontend/src/hooks/__tests__/useWakeLock.test.ts` — wake lock stub for IOS-02

*Existing vitest and pytest infrastructure is present; only test files need creation.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| ZWO file imports cleanly in Zwift app | ZWO-05 | Requires licensed Zwift install on real hardware; no public API | Export a planned session; drag .zwo into Zwift workout folder; confirm workout appears with correct name, power targets, and duration |
| Timer survives iOS Safari tab switch; screen stays on | IOS-03 | iOS Simulator does not replicate Safari PWA Wake Lock behavior | On physical iPhone, open PWA; start session; switch to another app for 30s; return; verify timer shows correct elapsed, screen did not lock |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
