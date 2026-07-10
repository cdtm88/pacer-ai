---
phase: 04-ui-and-calendar
plan: "06"
subsystem: frontend-screens
tags: [sse, chat, onboarding, history, fit-upload, recharts, vitest]
dependency_graph:
  requires: ["04-04"]
  provides: [useSSEStream, ChatBubble, ChatInput, FitUploadZone, RideRow, CtlSparkline, HistoryScreen, ChatScreen, OnboardingScreen]
  affects: [frontend/src/lib/api.ts, api/routes/sessions.py]
tech_stack:
  added: [recharts LineChart, fetch ReadableStream SSE reader]
  patterns: [EventSource SSE consumer, fetch-based POST SSE, D-14 sparkline gate, isOnboardingComplete detection export]
key_files:
  created:
    - frontend/src/hooks/useSSEStream.ts
    - frontend/src/components/chat/ChatBubble.tsx
    - frontend/src/components/chat/ChatInput.tsx
    - frontend/src/components/history/FitUploadZone.tsx
    - frontend/src/components/history/RideRow.tsx
    - frontend/src/components/history/CtlSparkline.tsx
    - frontend/src/screens/HistoryScreen.tsx
    - frontend/src/screens/ChatScreen.tsx
    - frontend/src/screens/OnboardingScreen.tsx
    - frontend/src/tests/history.test.tsx
    - frontend/src/tests/onboarding.test.tsx
  modified:
    - frontend/src/lib/api.ts
    - api/routes/sessions.py
decisions:
  - "fetch-based SSE reader for POST /onboarding/start (EventSource only supports GET)"
  - "ONBOARDING_COMPLETION_MARKER exported as constant shared between runtime and tests"
  - "getPmcHistory() added to api.ts with matching GET /pmc_history/ backend endpoint"
  - "tss_display_ready added to PmcEntry type; getLatestPmc handles empty-dict cold-start"
metrics:
  duration: "~35 minutes"
  completed: "2026-06-20"
  tasks_completed: 3
  tasks_total: 3
  files_created: 11
  files_modified: 2
  tests_added: 18
status: complete
---

# Phase 04 Plan 06: History, Chat, and Onboarding Screens Summary

**One-liner:** SSE streaming consumer hook, full History screen with FIT upload and gated CTL sparkline, Chat screen with adaptation bubble detection, and Onboarding screen with fetch-based POST SSE and confirmation gate detection covered by 18 Vitest tests.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | useSSEStream hook, ChatBubble, ChatInput | cd42f09 | useSSEStream.ts, ChatBubble.tsx, ChatInput.tsx |
| 2 | FitUploadZone, RideRow, CtlSparkline, HistoryScreen | a1254df | FitUploadZone.tsx, RideRow.tsx, CtlSparkline.tsx, HistoryScreen.tsx |
| 3 | ChatScreen, OnboardingScreen, tests | c51dda0 | ChatScreen.tsx, OnboardingScreen.tsx, history.test.tsx, onboarding.test.tsx |

## What Was Built

### Task 1: useSSEStream hook + chat primitives

`useSSEStream(url)` opens an `EventSource` when url is non-null. Handles all five backend event types: `token` appends to content buffer; `tool_start`/`tool_result` set/clear `isThinking`; `done` closes and sets `isDone`; `error` surfaces message and closes. URL must include `?token=<jwt>` via `sseUrl()` helper (EventSource cannot send Authorization headers, Pitfall 1). Returns `{ content, isDone, isThinking, error }`.

`ChatBubble` renders coach/user/adaptation/capability-gap roles per UI-SPEC with correct border-radius and left-border accents. No `dangerouslySetInnerHTML` (T-04-19 mitigated). Streaming ellipsis via `isStreaming` prop.

`ChatInput` is a textarea that auto-expands to 4 lines with a Send icon button. Disabled when streaming.

### Task 2: History screen components

`FitUploadZone`: drag-over + click, calls `uploadRide` (multipart, no user_id), success toast "Ride uploaded. History updated." + `invalidateQueries(['rides'])` (D-08), error toast with backend reason. No external drag-drop library.

`RideRow`: compliance chip with thresholds (>=90 green, <90 warn, null "Unmatched"), TSS, duration. Tap-to-expand shows power/HR summary, planned-vs-actual table, file name footnote.

`CtlSparkline`: returns `null` unless `latest.tss_display_ready === true` (D-14). When shown: recharts `LineChart`, blue-6 stroke, no dots, no axes, 48px height.

`HistoryScreen`: FitUploadZone pinned at top, gated sparkline, ride list with skeleton/empty/error states. "No rides yet" + upload prompt for empty state.

### Task 3: Chat + Onboarding screens + tests

`ChatScreen`: calls `createConversation` on mount (cached via react-query `staleTime: Infinity`). On user send, builds SSE URL with `sseUrl('/chat/stream?conversation_id=...')` and passes to `useSSEStream`. Detects adaptation/capability-gap messages via content heuristics. Amber disconnect banner when SSE errors. Empty state: "Ask your coach anything" / "Start by uploading a ride, or ask about your plan."

`OnboardingScreen`: uses `fetch` with `ReadableStream` reader to consume POST SSE (EventSource is GET-only). Progress bar advances 0-90% as messages accumulate. Exports `isOnboardingComplete(message)` and `ONBOARDING_COMPLETION_MARKER = 'Here is what I have'` as shared constants. On confirmation gate detection: renders summary card with "This looks right" CTA and "Edit a detail" link. After confirm: sends confirmation message, polls `getProfileMe`, invalidates `['profile']` cache, navigates to `/` (D-02).

**Tests (18 total, all pass):**
- `history.test.tsx`: CtlSparkline absent when `tss_display_ready=false`, present when `true`, absent when empty; "No rides yet" empty state; `uploadRide` called on file select with success toast
- `onboarding.test.tsx`: `isOnboardingComplete` returns true for marker prefix, false for mid-interview messages, false for empty string, false when marker appears mid-sentence

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] Added GET /pmc_history/ list endpoint**
- **Found during:** Task 2 — CtlSparkline requires history rows but only `/pmc_history/latest` existed
- **Fix:** Added `list_pmc_history` endpoint to `api/routes/sessions.py`, returning up to 30 rows (ascending) for sparkline window
- **Files modified:** `api/routes/sessions.py`, `frontend/src/lib/api.ts`
- **Commit:** a1254df

**2. [Rule 2 - Missing Critical Functionality] Added tss_display_ready to PmcEntry type**
- **Found during:** Task 2 — backend returns `tss_display_ready` in `/pmc_history/latest` but TypeScript type lacked the field
- **Fix:** Added `tss_display_ready?: boolean` to `PmcEntry` interface; fixed `getLatestPmc` to handle empty-dict cold-start response
- **Files modified:** `frontend/src/lib/api.ts`
- **Commit:** a1254df

**3. [Rule 1 - Architecture Constraint] Onboarding uses fetch streaming instead of EventSource**
- **Found during:** Task 3 — `POST /onboarding/start` cannot be consumed by `EventSource` (GET-only browser API)
- **Fix:** OnboardingScreen uses `fetch()` with `ReadableStream` reader and inline SSE line parser. Same five event types; same `?token=` auth via `sseUrl()` helper. `useSSEStream` is used by ChatScreen (GET endpoint) as planned.
- **Files modified:** `frontend/src/screens/OnboardingScreen.tsx`
- **Commit:** c51dda0

## Threat Surface Scan

No new network endpoints, auth paths, or schema changes beyond what the plan's threat model covers. The D-14 gate (`tss_display_ready`) is enforced at the component level. Streamed chat content renders via React safe text in all three consumers (no `dangerouslySetInnerHTML`) — T-04-19 mitigated.

## Self-Check

Files created/modified verified via git log. All 18 tests pass (`npm test -- --run`). `npx tsc --noEmit` produces no errors.

### Self-Check: PASSED

- [x] `frontend/src/hooks/useSSEStream.ts` — exists, contains `EventSource` and `addEventListener`
- [x] `frontend/src/components/chat/ChatBubble.tsx` — no `dangerouslySetInnerHTML`
- [x] `frontend/src/components/chat/ChatInput.tsx` — exists
- [x] `frontend/src/components/history/FitUploadZone.tsx` — contains `uploadRide`, success toast copy
- [x] `frontend/src/components/history/RideRow.tsx` — exists
- [x] `frontend/src/components/history/CtlSparkline.tsx` — contains `tss_display_ready`, `LineChart`
- [x] `frontend/src/screens/HistoryScreen.tsx` — exists
- [x] `frontend/src/screens/ChatScreen.tsx` — no em dashes in copy
- [x] `frontend/src/screens/OnboardingScreen.tsx` — exports `isOnboardingComplete`, no em dashes
- [x] `frontend/src/tests/history.test.tsx` — 10 tests pass
- [x] `frontend/src/tests/onboarding.test.tsx` — 8 tests pass
- [x] Commits: cd42f09, a1254df, c51dda0
