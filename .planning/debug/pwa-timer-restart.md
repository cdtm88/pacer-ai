---
slug: pwa-timer-restart
status: resolved
trigger: manual
created: 2026-06-21
updated: 2026-06-21
goal: find_and_fix
---

## Symptoms

When the user closes the PWA (iOS Safari, added to home screen) and reopens it, the session timer resets to zero. Expected behavior: timer should continue from where it left off, computed from a persisted `startTimestamp` in localStorage rather than relying on `setInterval` state.

**Prior attempt:** Commit `2fdbe3a` ("fix(05): iOS PWA timer persistence + session screen redesign") was supposed to address this but the issue still occurs. The memory note references a plan to use interval-based localStorage save every 5s, which is the wrong approach — the fix should use a persisted `startTimestamp` and compute elapsed on mount.

## Current Focus

hypothesis: Two separate bugs. (1) For free-ride sessions: freeRideDurationMins is ephemeral Zustand state — on iOS kill+reopen, Zustand is wiped, the session type can't be determined, steps = [], timer cannot be restored. (2) For structured sessions: the per-step epoch approach is architecturally correct but computeRestoredState returns a fresh epoch when saved is null — this means any scenario where localStorage wasn't written (e.g., session killed before the first 1s interval save fires, or session killed before save-on-mount useEffect ran) causes timer reset.

fix: (1) Persist freeRideDurationMins in PersistedSession so free rides survive iOS kill. (2) Add sessionStartTimestamp to PersistedSession and write it on first mount — this gives the total session elapsed anchor. (3) Read freeRideDurationMins from persisted session in DuringSessionScreen when Zustand is empty.

next_action: Apply fix to sessionPersistence.ts and DuringSessionScreen.tsx

## Evidence

- timestamp: 2026-06-21
  checked: useSessionTimer.ts
  found: Epoch-based timer — secondsLeft = stepDuration - floor((Date.now() - stepStartEpoch) / 1000). Recomputes on every 250ms tick. Correct design.
  implication: Per-step timer is self-correcting across any background duration. Not the bug.

- timestamp: 2026-06-21
  checked: sessionPersistence.ts
  found: PersistedSession stores stepIndex, completedDurationSecs, stepStartEpoch. No freeRideDurationMins. No sessionStartTimestamp.
  implication: Free-ride sessions cannot be restored after iOS kill. Zustand freeRideDurationMins is ephemeral.

- timestamp: 2026-06-21
  checked: uiStore.ts freeRideDurationMins
  found: Explicitly documented as "Ephemeral per-navigation handoff for rest-day free rides; not persisted". Initial value null.
  implication: On iOS PWA kill+reopen, freeRideDurationMins = null, isFreeRide = false, session = null (rest day), steps = [], DuringSessionScreen shows "No session steps available" — timer lost.

- timestamp: 2026-06-21
  checked: DuringSessionScreen.tsx SessionRunner mount
  found: save-on-mount useEffect runs after first render. If iOS kills before this useEffect fires, no localStorage entry exists for the session. Also: for free rides, no persistence of freeRideDurationMins.
  implication: Small window where kill before first save causes no persistence.

- timestamp: 2026-06-21
  checked: TodayScreen.tsx hasActiveSession redirect
  found: useEffect checks hasActiveSession() and navigate('/session'). Fires after first render paint. This is the iOS start_url workaround.
  implication: For structured sessions, redirect works. For free rides, redirect fires but DuringSessionScreen can't reconstruct the session type.

- timestamp: 2026-06-21
  checked: vite.config.ts PWA manifest
  found: start_url: '/'. navigateFallback: '/index.html'.
  implication: iOS PWA kill+reopen always starts at '/', handled by TodayScreen redirect.

## Eliminated

- hypothesis: useSessionTimer uses setInterval as source of truth (counting up elapsed internally)
  evidence: useSessionTimer recomputes secondsLeft from Date.now() - stepStartEpoch on every tick. Epoch-based, not interval-based.
  timestamp: 2026-06-21

- hypothesis: visibilitychange/pagehide events not registered
  evidence: Both are registered in SessionRunner with correct dependency arrays.
  timestamp: 2026-06-21

- hypothesis: computeRestoredState has logic error in while loop
  evidence: While loop correctly advances stepIndex while elapsedInStepMs >= stepTotalMs, accumulates completedDurationSecs. Logic is correct.
  timestamp: 2026-06-21

## Resolution

root_cause: Two bugs. (1) For free-ride sessions: freeRideDurationMins is ephemeral Zustand state not persisted to localStorage. On iOS kill+reopen, Zustand is wiped, DuringSessionScreen cannot determine session type, steps = [], timer is lost (shows "No session steps" or cannot restore). (2) For both session types: PersistedSession lacked sessionStartTimestamp, so computeRestoredState had no stable anchor for total elapsed time and could produce a fresh epoch in edge cases (kill before first save).

fix: (1) Added freeRideDurationMins to PersistedSession interface — now written with every saveSession call and read back in DuringSessionScreen when Zustand freeRideDurationMinsFromStore is null. (2) Added sessionStartTimestamp to PersistedSession — set once on SessionRunner first mount from computeRestoredState (preserved from prior saved session, or Date.now() for fresh). Never changes after first mount. (3) Refactored all saveSession calls to use buildPayload() callback that includes both new fields. (4) computeRestoredState now returns sessionStartTimestamp for RestoredState.

files_changed:
  - frontend/src/lib/sessionPersistence.ts (added sessionStartTimestamp, freeRideDurationMins to PersistedSession)
  - frontend/src/screens/DuringSessionScreen.tsx (RestoredState + computeRestoredState updated; SessionRunner accepts freeRideDurationMins prop; buildPayload centralizes save state; DuringSessionScreen falls back to persisted freeRideDurationMins when Zustand is null)

verification: TypeScript compiles clean (npx tsc --noEmit: no errors). Logic verified by code review: free-ride sessions now survive iOS kill; sessionStartTimestamp preserved across restores.
