---
phase: 05-during-session-and-zwo-export
verified: 2026-06-21T12:23:00Z
status: human_needed
score: 6/8 must-haves verified
behavior_unverified: 0
overrides_applied: 0
human_verification:
  - test: "Import a generated .zwo file into the real Zwift app"
    expected: "File imports without error; workout preview shows correct segment count and intensities (SteadyState with Power fractions 0.0-2.0 for FTP sessions; FreeRide + textevent for pre-FTP sessions)"
    why_human: "ZWO format is community-reverse-engineered with no official schema. Unit tests confirm XML structure but only a real Zwift import confirms Zwift accepts the file. Plan 05 auto-approved this checkpoint in auto-chain mode — developer must verify on real hardware before milestone sign-off. (ZWO-05, IOS requirement A1/A2/A3)"
  - test: "Open the deployed app on a physical iPhone in installed-PWA mode (Home Screen icon), run a full session"
    expected: "Screen stays lit for 60+ seconds (wake lock / NoSleep.js holding); after backgrounding ~20s and returning the timer reflects elapsed wall-clock time (resync, not freeze/reset); auto-advance 3-second countdown appears; Skip advances immediately; Session complete overlay shows after last step"
    why_human: "iOS Safari wake-lock behavior before iOS 18.4 cannot be reproduced in a simulator. The visibilitychange resync behavior depends on installed-PWA timing that unit tests with fake timers cannot fully replicate on real hardware. Plan 05 auto-approved this checkpoint in auto-chain mode — developer must verify on physical iOS device. Record the tested iOS version. (IOS-03)"
---

# Phase 05: During-Session and ZWO Export — Verification Report

**Phase Goal:** The during-session stepper works reliably on iOS Safari with the timer surviving tab switches; a generated .zwo file imports cleanly in Zwift
**Verified:** 2026-06-21T12:23:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A planned session exports as valid .zwo XML (ZWO-01) | VERIFIED | `api/sports_science/zwo.py` — `generate_zwo()` emits `workout_file` root with `sportType=bike`, `SteadyState` or `FreeRide` segments; 4/4 unit tests pass |
| 2 | Power values are FTP fractions 0.0-2.0, decimal strings, never raw watts (ZWO-02) | VERIFIED | `POWER_BY_SEGMENT = {warmup: 0.50, main_set: 0.65, cooldown: 0.50}`; `round(max(0.0, min(2.0, raw_fraction)), 4)` clamp applied; `test_power_fraction_bounds` passes |
| 3 | Pre-FTP sessions use FreeRide blocks with textevent RPE cues, not SteadyState (ZWO-03) | VERIFIED | `use_free_ride = ftp_watts is None` branch in `generate_zwo`; `FreeRide` + `textevent` with `timeoffset="0"` and `message=description`; `test_pre_ftp_uses_freeride` passes |
| 4 | `<sportType>bike</sportType>` present; no Cadence attribute on any segment (ZWO-04) | VERIFIED | `sport_el.text = "bike"` in `generate_zwo`; Cadence intentionally omitted (code comment at line 102); `test_sport_type_and_cadence` passes |
| 5 | Screen wake lock uses Wake Lock API with NoSleep.js fallback for iOS < 18.4 (IOS-01) | VERIFIED | `useWakeLock.ts` feature-detects `'wakeLock' in navigator`, falls back to dynamic `import('nosleep.js')` when sentinel is null; 4/4 unit tests pass; nosleep.js@0.12.0 in package.json; `DuringSessionScreen` calls `useWakeLock()` at mount |
| 6 | Timer uses `Date.now()` deltas; `visibilitychange` resyncs on tab return (IOS-02) | VERIFIED | `useSessionTimer.ts` computes `elapsed = pausedElapsedRef.current + Math.floor((Date.now() - startRef.current)/1000)`; both hidden and visible transitions snapshot elapsed into `pausedElapsedRef` and reset `startRef`; 5/5 unit tests pass including resync test |
| 7 | Generated .zwo imports cleanly in real Zwift (ZWO-05) | HUMAN NEEDED | Auto-approved in auto-chain mode; no real Zwift device verification on record |
| 8 | During-session view tested and functional on physical iOS Safari (IOS-03) | HUMAN NEEDED | Auto-approved in auto-chain mode; no physical device verification on record |

**Score:** 6/8 truths verified (2 require human verification)

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `api/sports_science/zwo.py` | Pure XML builder for ZWO export | VERIFIED | 105 lines; `def generate_zwo`, `POWER_BY_SEGMENT` constant; stdlib-only import |
| `api/routes/sessions.py` | `GET /sessions/{id}/export.zwo` route | VERIFIED | Route at line 269; `validate_uuid` before DB; dual-filter `.eq("id").eq("user_id")`; calls `generate_zwo`; `Content-Disposition` attachment header |
| `tests/sports_science/test_zwo.py` | Unit tests ZWO-01 through ZWO-04 | VERIFIED | 4 tests pass: `test_zwo_basic_structure`, `test_power_fraction_bounds`, `test_pre_ftp_uses_freeride`, `test_sport_type_and_cadence` |
| `frontend/src/hooks/useSessionTimer.ts` | Date.now() delta timer with visibilitychange resync | VERIFIED | 48 lines; `export function useSessionTimer`; `Date.now()`, `setInterval`, `visibilitychange`; 5/5 tests pass |
| `frontend/src/hooks/useWakeLock.ts` | Wake Lock with NoSleep.js fallback | VERIFIED | 40 lines; `export function useWakeLock`; `'wakeLock' in navigator` guard; dynamic nosleep.js import; cleanup releases sentinel and disables NoSleep; 4/4 tests pass |
| `frontend/src/types/nosleep.d.ts` | Ambient module declaration for nosleep.js | VERIFIED | `declare module 'nosleep.js'` (confirmed in plan 02 summary; nosleep.js in package.json) |
| `frontend/src/screens/DuringSessionScreen.tsx` | Live stepper with timer, auto-advance, wake lock, complete overlay | VERIFIED | 299 lines; uses `useSessionTimer`, `useWakeLock`; auto-advance at `secondsLeft === 0`; 3-second warning; `Skip step`; `Session complete` overlay; `Back to today`; free-ride path via `generateFreeRideSteps` |
| `frontend/src/components/session/DurationPickerModal.tsx` | Rest-day duration picker (30/45/60 + custom 10-180) | VERIFIED | Contains `freeRideDurationMins`; presets and custom validation wired |
| `frontend/src/stores/uiStore.ts` | `freeRideDurationMins` ephemeral slice | VERIFIED | `freeRideDurationMins: number | null` and `setFreeRideDurationMins` confirmed |
| `frontend/src/lib/api.ts` | `exportSessionZwo` + `SessionStructure` type | VERIFIED | `export async function exportSessionZwo`; `interface SessionStructure`; `URL.createObjectURL` + `URL.revokeObjectURL`; throws structured error on failure |
| `frontend/src/components/session/ZwoExportModal.tsx` | Two-step ZWO export preview + download modal | VERIFIED | 115 lines; `Export to Zwift`, `Download .zwo`, `FTP used:`, `Workout` literals; catch block does NOT call `onOpenChange(false)` (modal stays open on error); 4/4 modal tests pass |
| `frontend/src/components/session/SessionCard.tsx` | Enabled "Export to Zwift" button wired to `ZwoExportModal` | VERIFIED | Imports and renders `ZwoExportModal`; "Coming in the next update" tooltip removed |
| `frontend/src/screens/TodayScreen.tsx` | "Ride anyway" rest-day entry point | VERIFIED | Imports `DurationPickerModal`; renders "Ride anyway" button in `!session` branch |

---

### Key Link Verification

| From | To | Via | Status |
|------|----|-----|--------|
| `api/routes/sessions.py` | `api/sports_science/zwo.py` | `from api.sports_science.zwo import generate_zwo` (local import at line 332) | WIRED |
| `api/routes/sessions.py` | sessions table | `.eq("id", session_id).eq("user_id", user_id)` dual-filter at line 307 | WIRED |
| `frontend/src/screens/DuringSessionScreen.tsx` | `useSessionTimer.ts` | `import { useSessionTimer }` — line 8; called at line 99 | WIRED |
| `frontend/src/screens/DuringSessionScreen.tsx` | `useWakeLock.ts` | `import { useWakeLock }` — line 9; called at line 256 | WIRED |
| `frontend/src/components/session/ZwoExportModal.tsx` | `frontend/src/lib/api.ts` | `import { exportSessionZwo }` — line 12; called in `handleDownload` | WIRED |
| `frontend/src/lib/api.ts` | `GET /sessions/{id}/export.zwo` | `apiFetch('/sessions/${sessionId}/export.zwo', { headers: { Accept: 'application/xml' } })` | WIRED |
| `frontend/src/components/session/SessionCard.tsx` | `ZwoExportModal.tsx` | `import { ZwoExportModal }` — line 21; rendered at line 221 | WIRED |
| `frontend/src/components/session/DurationPickerModal.tsx` | `uiStore.ts` | `freeRideDurationMins` referenced in picker; calls `setFreeRideDurationMins` then `navigate('/session')` | WIRED |
| `frontend/src/screens/TodayScreen.tsx` | `DurationPickerModal.tsx` | `import { DurationPickerModal }` — line 6; rendered at line 127 | WIRED |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| ZWO unit tests (ZWO-01 to ZWO-04) | `python3 -m pytest tests/sports_science/test_zwo.py` | 4/4 passed (confirmed in SUMMARY 01) | PASS |
| Frontend hooks + screen + modal tests | `npx vitest run src/tests/useSessionTimer.test.ts useWakeLock.test.ts session.test.tsx zwo-modal.test.tsx` | 17/17 passed (4 test files) | PASS |
| nosleep.js installed | `grep nosleep.js frontend/package.json` | `"nosleep.js": "^0.12.0"` | PASS |

---

### Requirements Coverage

| Requirement | Phase | Description | Status | Evidence |
|-------------|-------|-------------|--------|----------|
| ZWO-01 | 5 | Valid .zwo file export | SATISFIED | `generate_zwo` produces conformant XML; `export_session_zwo` download endpoint |
| ZWO-02 | 5 | Power as FTP fraction 0.0-2.0 | SATISFIED | `POWER_BY_SEGMENT` constants; clamp; decimal string rendering; test passes |
| ZWO-03 | 5 | Pre-FTP uses FreeRide + textevent | SATISFIED | `use_free_ride = ftp_watts is None` path; test passes |
| ZWO-04 | 5 | `sportType=bike`; no Cadence | SATISFIED | Implemented and tested |
| ZWO-05 | 5 | Real Zwift import acceptance | PENDING HUMAN | Auto-approved in auto-chain; real device required |
| IOS-01 | 5 | Wake Lock + NoSleep.js fallback | SATISFIED | `useWakeLock` implementation; tests pass; wired in `DuringSessionScreen` |
| IOS-02 | 5 | Date.now() delta timer + visibilitychange resync | SATISFIED | `useSessionTimer` implementation; 5 tests pass including resync |
| IOS-03 | 5 | Physical iOS Safari verification | PENDING HUMAN | Auto-approved in auto-chain; physical device required |

---

### Anti-Patterns Found

No blockers. No TBD, FIXME, or XXX markers found in phase-modified files. No stub patterns (placeholder text, empty handlers, hardcoded empty returns) detected in the implementation files examined.

---

### Human Verification Required

#### 1. ZWO-05: Real Zwift Import

**Test:** Start the app, navigate to a structured session, tap "Export to Zwift" then "Download .zwo". Open the downloaded file and confirm well-formed XML with `<sportType>bike</sportType>` and no `Cadence` attribute. Import into the real Zwift app.
**Expected:** Zwift imports without error; workout preview shows correct segment count and intensities (SteadyState with Power fractions 0.0-2.0 for FTP sessions; FreeRide + textevent for pre-FTP sessions).
**Why human:** ZWO format is community-reverse-engineered with no official schema. Unit tests verify XML structure, but only a real Zwift import confirms the app accepts the file. Research assumptions A1 (Power is FTP fraction), A2 (textevent child of FreeRide), A3 (sportType "bike") are unresolved until verified.

#### 2. IOS-03: Physical iOS Safari — Timer and Wake Lock

**Test:** Deploy the app over HTTPS, open on a physical iPhone in Safari, add to Home Screen, launch from the Home Screen icon (installed PWA mode). Start a session. Leave untouched for 60+ seconds. Switch to another app for ~20 seconds and return. Let steps expire naturally and tap Skip on one. Complete the last step. Record the tested iOS version.
**Expected:** Screen does not dim or lock during the 60-second wait. After backgrounding, the timer reflects elapsed wall-clock time (not frozen, not reset to step start). 3-second countdown warning appears before auto-advance. Skip advances immediately. "Session complete" overlay shows total time, steps completed, and "Back to today" navigates correctly.
**Why human:** iOS Safari wake-lock behavior differs between browser and installed-PWA mode and changed in iOS 18.4. The visibilitychange resync behavior cannot be fully replicated in Vitest fake-timer tests on real hardware. NoSleep.js fallback engagement on iOS < 18.4 requires a physical device to confirm.

---

### Gaps Summary

No implementation gaps. All 6 automated truths are VERIFIED with substantive, wired, data-flowing code and passing tests. The 2 remaining items (ZWO-05, IOS-03) are acceptance checkpoints that were explicitly noted as auto-approved in auto-chain mode by plan 05-05 and require physical device verification by the developer before milestone sign-off.

---

_Verified: 2026-06-21T12:23:00Z_
_Verifier: Claude (gsd-verifier)_
