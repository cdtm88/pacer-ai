---
phase: 11
slug: ride-analysis-dashboard
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-09
---

# Phase 11 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 + pytest-asyncio 1.4.0 (backend, `asyncio_mode = auto`) / Vitest + @testing-library/react (frontend, jsdom) |
| **Config file** | `pytest.ini` (backend) / `frontend/vitest.config.ts` (frontend) |
| **Quick run command** | `python -m pytest tests/sports_science/test_zones.py tests/api/test_rides_stream.py -x` (backend) / `cd frontend && npx vitest run src/tests/rideChart.test.tsx` (frontend) |
| **Full suite command** | `python -m pytest` (backend) / `cd frontend && npx vitest run` (frontend) |
| **Estimated runtime** | ~30 seconds (targeted) / ~3 minutes (full suite) |

---

## Sampling Rate

- **After every task commit:** Run the quick run command matching the task's layer (backend zone/stream tests, or `rideChart.test.tsx`)
- **After every plan wave:** Run both full suite commands (`python -m pytest` and `cd frontend && npx vitest run`)
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 11-01 | 01 | 0 | RIDE-01, RIDE-02, RIDE-03 | — | Aligned per-second arrays, channel presence, downsample cap | unit | `pytest tests/api/test_rides_stream.py -k "parse or channels or downsample" -x` | ❌ Wave 0 | ⬜ pending |
| 11-02 | 02 | 0 | RIDE-04 | — | `time_in_hr_zones` seconds/pct hand-checked | unit | `pytest tests/sports_science/test_zones.py -k time_in_hr_zones -x` | ❌ Wave 0 (append to existing file) | ⬜ pending |
| 11-03 | 03 | 1 | RIDE-05 | T-11-01 / T-11-02 / T-11-03 | Scoped 404, missing-file 404, corrupt-file 422 | integration | `pytest tests/api/test_rides_stream.py -x` | ❌ Wave 1 | ⬜ pending |
| 11-04 | 04 | 2 | RIDE-06 | — | Typed fetcher, implicit via component test | unit (implicit) | `npx vitest run src/tests/rideChart.test.tsx` | ❌ Wave 2 | ⬜ pending |
| 11-05 | 05 | 2 | RIDE-07, RIDE-08, RIDE-09 | — | Per-present-channel charts, synced readout, zone bars | component | `npx vitest run src/tests/rideChart.test.tsx` | ❌ Wave 2/3 | ⬜ pending |
| 11-06 | 06 | 2 | RIDE-10, RIDE-11 | — | Route + nav tab + `RideRow` link | component/manual | `npx vitest run src/tests/routerErrorBoundary.test.tsx` (routing smoke) + manual click-through | Partial — routing infra exists, new routes don't | ⬜ pending |
| 11-07 | 07 | 3 | RIDE-12 | — | Fixture-driven backend + frontend assertions (6 laps, not 7 — RESEARCH.md Pitfall 4) | integration + component | `pytest tests/api/test_rides_stream.py -x` + `npx vitest run src/tests/rideChart.test.tsx` | ❌ Wave 3 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/api/test_rides_stream.py` — new file, covers RIDE-01, RIDE-02, RIDE-03, RIDE-05, RIDE-12 (backend half)
- [ ] `tests/sports_science/test_zones.py` — append `time_in_hr_zones` tests (RIDE-04); file already exists, no new file needed
- [ ] `frontend/src/tests/rideChart.test.tsx` — new file, covers RIDE-07, RIDE-08, RIDE-09, RIDE-12 (frontend half)
- [ ] No new framework installs needed — pytest/pytest-asyncio and Vitest/RTL are both already configured and used by adjacent test files (`tests/api/test_rides.py`, `frontend/src/tests/history.test.tsx`)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Cross-chart hover sync (Recharts `syncId`) renders correctly on iOS Safari | RIDE-08 | Recharts synced tooltip visual behavior on the PWA target isn't meaningfully assertable via jsdom | Open Analysis tab on a physical iOS device or Safari, hover over one chart, confirm all charts show synced crosshair/readout |
| Nav tab + route click-through end to end | RIDE-10, RIDE-11 | Full navigation UX (tab highlight state, route transition) benefits from a visual check beyond the routing smoke test | Click a `RideRow` in Progress screen, confirm navigation to `/rides/:id`; click Analysis nav tab, confirm `/analysis` loads latest ride |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
