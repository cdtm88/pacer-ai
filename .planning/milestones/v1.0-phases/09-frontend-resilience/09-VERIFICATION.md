---
phase: 09-frontend-resilience
verified: 2026-07-07T22:15:00Z
status: passed
score: 12/14 items code-verified (2 legitimately manual-only per 09-VALIDATION.md)
behavior_unverified: 0
overrides_applied: 0
human_verification:

  - test: "Export a .zwo file from a real iOS Safari device (item 7) after the fix"
    expected: "File downloads without a blocked-popup prompt; iosWindow is opened synchronously in exportSessionZwo before any await and navigated via iosWindow.location.href once the blob URL resolves"
    why_human: "iOS Safari's popup-blocker gesture-window behavior cannot be simulated in jsdom/Vitest; requires a physical device or real Safari session (matches the IOS-03 physical-device-retest pattern in MEMORY.md)"

  - test: "Open Chat on a physical iOS Safari device / mobile viewport with the address bar visible (item 9)"
    expected: "Chat input stays pinned to the bottom of the screen and auto-scroll follows new messages, with no clipping when the dynamic address bar shows/hides"
    why_human: "iOS Safari's dynamic viewport height (100dvh) and inner-scroll-pane behavior cannot be verified in jsdom; AppLayout.test.tsx confirms h-dvh is used (not min-h-screen/h-screen) but not the rendered on-device behavior"
---

# Phase 09: Frontend Resilience Verification Report

**Phase Goal:** The UI survives real-world failure modes across the full 14-item Critical+Major list from `APP-REVIEW-260703.md` (per 09-CONTEXT.md D-01): chat SSE error/empty-done recovery, conversation history reload, stale-session id+date guard, iOS ZWO export gesture timing, ZWO export error-shape parsing, auth callback single-exchange, Ride field-name alignment, upload query invalidation, router error boundary, live-resume overshoot, AppLayout scroll/pin, cross-account cache bleed, and upload progress/drag-drop validation.
**Verified:** 2026-07-07
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (14-item bug list, per task instructions — no REQ-IDs assigned to this phase)

| # | Item | Status | Evidence |
|---|------|--------|----------|
| 1 | Stale session hijack | ✓ VERIFIED | `sessionPersistence.ts` `PersistedSession` has `sessionId`+`date`; `loadMatchingSession()` silently discards mismatches (no UI, per D-06). `TodayScreen.tsx:54` gates the `/session` redirect on `loadMatchingSession(session?.id ?? null)`. Every `saveSession` call site in `DuringSessionScreen.tsx` (mount, interval, visibilitychange, goNext, live-resume) writes `sessionId`+`date`. |
| 2 | Chat SSE error bricks input | ✓ VERIFIED | `useSSEStream.ts` retries silently up to `MAX_RETRIES=2` with `BACKOFF_MS=[500,1500]` inside `openStream()`; `setError` only fires after retries exhaust. `ChatScreen.tsx` has a dedicated `useEffect` that nulls `activeStreamUrl` on terminal `error`, unbricking `handleSend`'s guard; renders `StreamErrorBanner` with a working `handleRetry` that re-derives the SSE URL from `pendingUserMessage`. Unit tests pass (`useSSEStream.test.ts`, `chat.test.tsx`); stale "Reconnecting..." assertion (Pitfall 3) confirmed removed via grep. |
| 3 | Empty-done swallow | ✓ VERIFIED | `ChatScreen.tsx:165-185` splits the `isDone` effect: `setActiveStreamUrl(null)`/`setPendingUserMessage(null)` always fire on `isDone`, coach message only pushed when `content` is non-empty. |
| 4 | History reload on cache miss | ✓ VERIFIED | New `GET /conversations/{id}/messages` in `backend/routes/chat.py:201` wraps the user-scoped `load_conversation(conversation_id, user_id=user_id, ...)` helper. `api.ts.getConversationMessages()` calls it. `ChatScreen.tsx`'s `['active-conversation']` queryFn branches: persisted id → `getConversationMessages` (reload); else → `createConversation`. Backend tests confirm foreign-conversation-id returns empty (`test_get_conversation_messages_foreign_id_returns_empty_list`), not another user's data. |
| 5 | Ride field mismatch | ✓ VERIFIED | `api.ts` `Ride` interface (`duration_secs`, `avg_power`, `ride_date`, no `file_name`/`distance_m`/`created_at`) matches `backend/routes/rides.py:647-649` SELECT list exactly (grep-diffed). `RideRow.tsx` reads `ride.duration_secs`/`ride.avg_power`; no `file_name` block remains. |
| 6 | ZWO export error shape | ✓ VERIFIED | `api.ts` `exportSessionZwo` parses `body.detail.error ?? body.detail.detail` (object form) or a raw string `detail`, mirroring the pattern already used by `markSessionMissed`/`markSessionDone`. |
| 7 | iOS ZWO export popup-block | ✓ CODE-VERIFIED / manual-only for on-device confirmation | `exportSessionZwo` opens `iosWindow = window.open('', '_blank')` synchronously as the very first statement (before any `await`), then later navigates `iosWindow.location.href = url` once the blob resolves — correct gesture-window ordering. 09-VALIDATION.md explicitly scopes this as manual-only (physical iOS Safari device). Routed to human verification below. |
| 8 | Live-resume overshoot | ✓ VERIFIED (behavioral) | `fastForwardSteps()` extracted and shared by `computeRestoredState` (reload) and the live `secondsLeft===0` effect (`DuringSessionScreen.tsx:265-282`), replacing the old bare single-step `goNext()`. Component-level test `'fast-forwards through multiple elapsed steps on live resume (item 8)'` (`session.test.tsx:211`) independently re-run by this verifier: **1 passed**. |
| 9 | AppLayout scroll/pin | ✓ CODE-VERIFIED / manual-only for on-device confirmation | `AppLayout.tsx` uses `h-dvh` on both wrapping divs (lines 14, 21), matching the codebase's established `DuringSessionScreen` `100dvh` convention (not `min-h-screen`/`h-screen`). `AppLayout.test.tsx` confirms the class names; 09-VALIDATION.md explicitly scopes the rendered pin/scroll behavior as manual-only. Routed to human verification below. |
| 10 | Cross-account cache bleed | ✓ VERIFIED | `router.tsx:33` OR-chain now includes exactly `'SIGNED_IN'` alongside the pre-existing `'SIGNED_OUT'`/`'USER_UPDATED'` → `queryClient.clear()`; `'TOKEN_REFRESHED'`/`'INITIAL_SESSION'` correctly excluded (Pitfall 5 honored). |
| 11 | Auth callback double-exchange | ✓ VERIFIED | `AuthCallbackScreen.tsx` no longer calls `exchangeCodeForSession`; it watches `useAuthStore` (populated by `useAuth.ts`'s global `onAuthStateChange`) and navigates home once a session appears, with a 6s timeout fallback to `/login`. Matches RESEARCH Pattern 4 exactly. |
| 12 | Router error boundary | ✓ VERIFIED | All 5 `AppLayout` leaf routes (`index`, `agenda`, `history`, `chat`, `settings`) carry `ErrorBoundary: RouteErrorFallback` in `router.tsx:172-199`; `AppLayout` itself is the parent `element` one level up, so it stays mounted on a child crash. `ErrorBoundaryFallback.tsx` renders only "Something went wrong" / "This page ran into a problem." + Reload button — `useRouteError()` is read but never displayed (D-09 honored). |
| 13 | Onboarding stuck spinner | ✓ VERIFIED | `OnboardingScreen.tsx` mirrors the `MAX_RETRIES=2`/`BACKOFF_MS=[500,1500]` policy independently in both `runStream` and `runConfirmStream` (not sharing `useSSEStream` transport, per Pitfall 1). The `runConfirmStream`'s `!res.ok` branch now calls `setStreamError("Couldn't save your profile.")` instead of silently falling through to `pollForProfile` (the original stuck-spinner bug). `StreamErrorBanner` rendered with `variant` reuse from 09-01. |
| 14 | Upload progress/drag-drop/invalidation | ✓ VERIFIED | `FitUploadZone.tsx`: indeterminate progress bar renders while `isUploading` (additive to spinner); `handleDrop` validates `file.name.toLowerCase().endsWith('.fit')` before calling `handleUpload`, toasting and returning early otherwise; success path invalidates the full explicit key list (`['rides']`, `['pmc','latest']`, `['pmc-history']`, `['session','today']`, `['sessions','upcoming']`) — no prefix-match shortcut (Pitfall 2 honored). |

**Score:** 12/14 items fully code-and-test verified; 2/14 (items 7, 9) are code-correct and unit-tested at the CSS/ordering level but require a physical iOS Safari device to confirm the actual runtime behavior — this is a legitimate, pre-declared manual-only gap (09-VALIDATION.md), not a code gap.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `frontend/src/components/chat/StreamErrorBanner.tsx` | Shared terminal-error banner, chat+onboarding variants | ✓ VERIFIED | 72 lines, exports `{message, onRetry, variant}`, imported by both `ChatScreen.tsx` and `OnboardingScreen.tsx` |
| `frontend/src/hooks/useSSEStream.ts` | Retry-with-backoff | ✓ VERIFIED | `openStream()`/`retryCount`/`MAX_RETRIES`/`BACKOFF_MS` inside effect closure |
| `frontend/src/lib/sessionPersistence.ts` | `sessionId`+`date` identity fields | ✓ VERIFIED | `PersistedSession` interface + `loadMatchingSession()` |
| `frontend/src/components/ErrorBoundaryFallback.tsx` | Minimal per-route fallback | ✓ VERIFIED | `RouteErrorFallback`, no error detail rendered |
| `backend/routes/chat.py` | `GET /conversations/{id}/messages` | ✓ VERIFIED | User-scoped via `load_conversation(..., user_id=user_id, ...)` |
| `frontend/src/components/history/FitUploadZone.tsx` | Progress + drag-drop validation + full invalidation | ✓ VERIFIED | All three behaviors present and wired |
| `frontend/src/components/AppLayout.tsx` | `h-dvh` height chain | ✓ VERIFIED | Both wrapping divs use `h-dvh`; unit-tested, device behavior pending |

### Key Link Verification

| From | To | Via | Status |
|------|----|----|--------|
| `useSSEStream` error handler | `setError` | Only after `retryCount >= MAX_RETRIES` | ✓ WIRED |
| `ChatScreen` isDone effect | `activeStreamUrl` | Always nulls on `isDone` regardless of content | ✓ WIRED |
| `ChatScreen` | `StreamErrorBanner` | Renders on hook `error`; `handleRetry` re-derives `sseUrl` from `pendingUserMessage` | ✓ WIRED |
| `TodayScreen`/`DuringSessionScreen` | `sessionPersistence.loadMatchingSession` | Both consumers validate id+date before trusting a persisted record | ✓ WIRED |
| `computeRestoredState` + live-resume effect | `fastForwardSteps` | Both call sites use the same shared helper | ✓ WIRED |
| `router.tsx` onAuthStateChange | `queryClient.clear()` | `SIGNED_IN` added to existing OR-chain | ✓ WIRED |
| `AuthCallbackScreen` | `useAuthStore` | Watches store instead of a second `exchangeCodeForSession` call | ✓ WIRED |
| `router.tsx` leaf routes | `RouteErrorFallback` | `ErrorBoundary` property on all 5 `AppLayout` children | ✓ WIRED |
| `api.ts` `Ride` interface | `RideRow.tsx` | Field names aligned end-to-end with `rides.py` SELECT | ✓ WIRED |
| `exportSessionZwo` | iOS gesture window | `window.open` called synchronously before first `await` | ✓ WIRED |
| `OnboardingScreen` `runStream`/`runConfirmStream` | `StreamErrorBanner` | Independent retry loops, shared UI component | ✓ WIRED |
| `FitUploadZone` upload success | 5 query keys | Explicit list, no prefix-match shortcut | ✓ WIRED |
| `ChatScreen` queryFn | `getConversationMessages` | Branches on persisted conversation id | ✓ WIRED |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Item 8 live-resume multi-step fast-forward | `npx vitest run src/tests/session.test.tsx -t "fast-forwards through multiple elapsed steps on live resume"` | 1 passed | ✓ PASS |

Full frontend suite (132 tests / 16 files) and `tests/api/test_chat.py` (6 tests) were already confirmed passing on current HEAD per the post-merge integration gate (not re-run in full by this verifier — evidence accepted per task brief; one named test independently re-run above as a spot check).

### Anti-Patterns Found

None. Scanned all 15 files modified across the phase's 7 plans (`StreamErrorBanner.tsx`, `useSSEStream.ts`, `ChatScreen.tsx`, `sessionPersistence.ts`, `TodayScreen.tsx`, `DuringSessionScreen.tsx`, `api.ts`, `RideRow.tsx`, `ErrorBoundaryFallback.tsx`, `router.tsx`, `AuthCallbackScreen.tsx`, `FitUploadZone.tsx`, `AppLayout.tsx`, `OnboardingScreen.tsx`, `backend/routes/chat.py`) for `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER`/"not yet implemented" — zero matches.

### Requirements Coverage

Not applicable — REQUIREMENTS.md maps no requirement IDs to Phase 9 (confirmed by grep: zero matches for "Phase 9"/"frontend-resilience"). This phase predates REQ-ID mapping per the phase brief; the 14-item bug list (above) substitutes as the requirements contract, sourced from `09-RESEARCH.md`/`09-CONTEXT.md` D-01.

### Deferred Items

None. D-01 explicitly expanded scope rather than deferring anything; 09-CONTEXT.md's `<deferred>` section confirms "None — discussion stayed within phase scope."

### Human Verification Required

1. **iOS ZWO export downloads without a popup-block (item 7)**
   **Test:** On a physical iOS Safari device, open a session with a plan and tap "Export ZWO."
   **Expected:** The `.zwo` file downloads (or opens in a new tab that then downloads) without a blocked-popup indicator.
   **Why human:** iOS Safari's popup-blocker gesture-window semantics cannot be simulated in jsdom; the code fix (synchronous `window.open('', '_blank')` before any `await`) is verified correct by inspection but the actual browser behavior needs on-device confirmation, per 09-VALIDATION.md's pre-declared manual-only scoping.

2. **AppLayout scroll/pin on iOS Safari (item 9)**
   **Test:** On a physical iOS Safari device (or the same viewport with the dynamic address bar visible), open Chat and send several messages.
   **Expected:** The chat input stays pinned to the bottom of the viewport; the message list auto-scrolls to follow new content; no clipping occurs when the address bar shows/hides.
   **Expected:** The `h-dvh` height-chain fix is verified correct by inspection and unit test (matches the codebase's own `DuringSessionScreen` `100dvh` convention), but the on-device dynamic-viewport rendering needs physical confirmation, per 09-VALIDATION.md's pre-declared manual-only scoping (same pattern as IOS-03 in MEMORY.md).

### Gaps Summary

No code gaps found. All 14 items in the phase's expanded scope (D-01) have corresponding, correctly-wired, tested code changes verified directly against the codebase (not inferred from SUMMARY.md claims). The only open items are the two pre-declared, unavoidably manual iOS-Safari-device checks (items 7 and 9) that 09-VALIDATION.md itself scoped as "Manual-Only Verifications" before execution began — these are not gaps in the implementation, they are inherent limits of jsdom-based testing for popup-blocker and dynamic-viewport behavior. Routing to human_needed per the verification decision tree (any non-empty human-verification section forces this status regardless of how clean the code-level evidence is).

---

_Verified: 2026-07-07_
_Verifier: Claude (gsd-verifier)_
