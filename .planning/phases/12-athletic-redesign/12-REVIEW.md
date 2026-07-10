---
phase: 12-athletic-redesign
reviewed: 2026-07-10T00:00:00Z
depth: standard
files_reviewed: 26
files_reviewed_list:
  - frontend/index.html
  - frontend/src/components/AppLayout.tsx
  - frontend/src/components/history/RideRow.tsx
  - frontend/src/components/nav/BottomTabBar.tsx
  - frontend/src/components/nav/DesktopSidebar.tsx
  - frontend/src/components/progress/WeeklyLoadChart.tsx
  - frontend/src/components/session/SessionCard.tsx
  - frontend/src/components/session/WorkoutProfileChart.tsx
  - frontend/src/components/session/ZoneChip.tsx
  - frontend/src/components/session/ZwoExportModal.tsx
  - frontend/src/components/ui/PromptChip.tsx
  - frontend/src/components/ui/StatTile.tsx
  - frontend/src/components/ui/card.tsx
  - frontend/src/index.css
  - frontend/src/lib/format.ts
  - frontend/src/lib/zones.ts
  - frontend/src/screens/AgendaScreen.tsx
  - frontend/src/screens/ChatScreen.tsx
  - frontend/src/screens/DuringSessionScreen.tsx
  - frontend/src/screens/LoginScreen.tsx
  - frontend/src/screens/OnboardingScreen.tsx
  - frontend/src/screens/SettingsScreen.tsx
  - frontend/src/screens/TodayScreen.tsx
  - frontend/src/tests/SettingsScreen.test.tsx
  - frontend/src/tests/rideChart.test.tsx
  - frontend/src/tests/today.test.tsx
  - frontend/src/tests/zones.test.ts
findings:
  critical: 0
  warning: 6
  info: 4
  total: 10
status: issues_found
---

# Phase 12: Code Review Report

**Reviewed:** 2026-07-10T00:00:00Z
**Depth:** standard
**Files Reviewed:** 26
**Status:** issues_found

## Summary

This is a re-review against the current state of the files (a prior 12-REVIEW.md dated 2026-07-09 already exists in this directory; several of its findings — the em-dash copy violations in `ZwoExportModal.tsx`/`SessionCard.tsx`, the keyboard-focusable hidden "Log without riding" region in `SessionCard.tsx`, and the lost `<h2>` heading semantics in `SettingsScreen.tsx` — have already been fixed in the code as currently written and are confirmed resolved, not re-flagged here).

Evaluating the current file contents directly: no crash-level or authentication-bypass defects were found. The main remaining themes are: (1) a security/privacy concern in `ChatScreen.tsx` where the bearer token and the full user chat message are embedded in the SSE request URL, (2) a genuine timezone bug in `RideRow.formatDate` that can show the wrong day for users behind UTC, (3) a missing lower-bound clamp on the compliance bar in `RideRow.tsx`, (4) a recurring pattern of `as unknown as X` type casts at the API boundary in `TodayScreen.tsx`, `AgendaScreen.tsx`, and `DuringSessionScreen.tsx` that defeats TypeScript's guarantees, (5) a ~45-line duplicated JSX block in `TodayScreen.tsx`, and (6) a self-documented pause/persistence gap in `DuringSessionScreen.tsx` that can misreport elapsed workout time after an iOS kill while paused. No hardcoded secrets, `eval`, `innerHTML`, or genuinely empty catch blocks were found; the handful of empty `catch {}` blocks present are all commented and intentional.

## Warnings

### WR-01: `RideRow.formatDate` has no timezone anchor — can display the wrong day

**File:** `frontend/src/components/history/RideRow.tsx:56-66`
**Issue:** `formatDate` calls `new Date(isoDate).toLocaleDateString(...)` directly on what is expected to be a bare `YYYY-MM-DD` date string. Every other date-only string in this same phase's screens (`AgendaScreen.tsx:36,45,50`, `TodayScreen.tsx:13,18`) is deliberately anchored with `+ 'T12:00:00'` specifically to avoid the UTC-midnight rollback problem: `new Date('2026-07-10')` parses as UTC midnight, and `.toLocaleDateString()` in any timezone behind UTC (all of the Americas) renders the *previous* calendar day. `RideRow` is the one component in this family that doesn't follow the pattern, so a ride logged on "Jul 10" can show as "Jul 9" in the history list for US-timezone users.
**Fix:**
```tsx
function formatDate(isoDate: string): string {
  try {
    return new Date(isoDate + 'T12:00:00').toLocaleDateString(undefined, {
      weekday: 'short', month: 'short', day: 'numeric',
    })
  } catch {
    return isoDate
  }
}
```

### WR-02: Compliance bar has no lower-bound clamp

**File:** `frontend/src/components/history/RideRow.tsx:276`
**Issue:** The "Actual" bar width is `` `${Math.min(100, ride.compliance_pct)}%` ``. This clamps the upper bound (a prior overflow bug on this line was fixed) but not the lower one. `compliance_pct` is typed `number | null` with no guarantee of non-negativity; a negative value produces an invalid negative-length CSS width, and the adjacent `ComplianceChip` will print something like "-40% on target" with no sanity check.
**Fix:**
```tsx
width: `${Math.min(100, Math.max(0, ride.compliance_pct))}%`,
```

### WR-03: Chat message content and auth token sent via SSE request URL

**File:** `frontend/src/screens/ChatScreen.tsx:224-227, 236-239`
**Issue:** `handleSend`/`handleRetry` build the stream URL as:
```ts
await sseUrl(`/api/chat/stream?conversation_id=${encodeURIComponent(conversation.id)}&message=${encodeURIComponent(text)}`)
```
and `sseUrl` (in `lib/api.ts`) appends the user's JWT access token as a `?token=` query parameter because `EventSource` cannot set headers. Every chat turn — including potentially sensitive personal/health context the user types to their coach — plus the bearer token ends up in the URL. URLs are commonly persisted in browser history and service/proxy access logs, and can leak via the `Referer` header to any cross-origin resource the page loads. This is a recognized sensitive-data-exposure anti-pattern (OWASP A02), not just a style nit — and `OnboardingScreen.tsx` in the same phase already demonstrates the alternative (fetch + `ReadableStream`, token in an `Authorization` header, message in the POST body).
**Fix:** Use the same fetch/POST + `ReadableStream` pattern `OnboardingScreen.tsx` uses for its own SSE consumption instead of `EventSource` for chat, or at minimum replace the full access token in the query string with a short-lived, single-use stream ticket, and move the message out of the URL and into a request body.

### WR-04: Repeated unsafe `as unknown as X` casts at the session/API boundary

**File:** `frontend/src/screens/TodayScreen.tsx:208-209`, `frontend/src/screens/AgendaScreen.tsx:167`, `frontend/src/screens/DuringSessionScreen.tsx:795`
**Issue:** Several call sites bypass the type system entirely rather than fixing the underlying type mismatch:
```tsx
// TodayScreen.tsx
session={session as unknown as Parameters<typeof SessionCard>[0]['session']}
pmc={pmc as unknown as Parameters<typeof SessionCard>[0]['pmc']}
// AgendaScreen.tsx
const rows = sessions as unknown as SessionRow[]
// DuringSessionScreen.tsx
const raw = (session as unknown as { structure?: unknown }).structure
```
Casting through `unknown` suppresses all structural checking, so if the backend's actual session/PMC shape ever drifts from these ad-hoc local interfaces (`SessionData`, `SessionRow`, `PmcRow`), the compiler will not catch it — the bug will only surface at runtime as silently blank/`--` fields with no compile-time warning.
**Fix:** Define one canonical session/PMC type in `lib/api.ts` that actually matches the backend response, and have the query functions return it directly so screens can consume it without local re-declarations or `as unknown as` casts.

### WR-05: Duplicated "Coming up" strip JSX block

**File:** `frontend/src/screens/TodayScreen.tsx:143-188` and `frontend/src/screens/TodayScreen.tsx:222-268`
**Issue:** The empty-state "Coming up" strip and the post-session "Coming up" strip are near byte-identical ~45-line blocks (same button markup, same zone dot, same date/duration formatting, same inline styles), differing only in the source array (`emptyStateUpcoming` vs `stripSessions`) and outer container classes. Any future change (styling, a11y fix, new field) has to be made twice and will drift if only one copy is updated.
**Fix:** Extract a shared `UpcomingStrip({ sessions, className })` component and use it from both render branches.

### WR-06: Paused wall-clock time can be miscounted as elapsed on iOS kill

**File:** `frontend/src/screens/DuringSessionScreen.tsx:227-230`
**Issue:** The code's own comment acknowledges this: the 1s interval save and the `visibilitychange`/`pagehide` save handlers persist `stepStartEpoch` unshifted while `isPaused` is true (only `togglePause`'s resume path shifts it). If the user pauses, backgrounds the app, and iOS kills the PWA process while still paused, the persisted `stepStartEpoch` on restore will treat the entire paused duration as if the step had been actively running, so `fastForwardSteps` can skip past steps the user never actually rode. Given this is a cycling coaching app where pausing mid-ride (stoplight, mechanical issue, phone call) is a realistic scenario, this isn't a rare edge case.
**Fix:** Persist an `isPaused`/pause-start timestamp as part of the saved payload so `computeRestoredState` can subtract the paused duration correctly on restore, instead of accepting the drift as permanent.

## Info

### IN-01: Dead CSS variable fallback

**File:** `frontend/src/screens/SettingsScreen.tsx:180`
**Issue:** `color: 'var(--color-ink-3, var(--color-ink-2))'` — `--color-ink-3` is unconditionally defined in `index.css`, so the fallback value can never trigger. Reads as leftover defensive code / copy-paste artifact.
**Fix:** `color: 'var(--color-ink-3)'`.

### IN-02: Unreachable `undefined` branch in `ComplianceChip`

**File:** `frontend/src/components/history/RideRow.tsx:19-20`
**Issue:** `ComplianceChip`'s prop type is `pct: number | null`, and its only call sites pass `ride.compliance_pct ?? null`, so `pct === undefined` can never be true. Harmless, but signals lingering uncertainty about whether the underlying API field can be `undefined` vs `null`.
**Fix:** Drop the `undefined` check, or confirm and align the `Ride` type in `lib/api.ts` if `undefined` really is possible.

### IN-03: Inconsistent zero-duration formatting between components

**File:** `frontend/src/components/history/RideRow.tsx:48-54` vs `frontend/src/screens/AgendaScreen.tsx:65-71`
**Issue:** `RideRow.formatDuration` treats `0` as falsy and renders `'--'` for a zero-second ride, while `AgendaScreen.formatDurationTotal` renders `0m` for a zero-minute total. Both are plausible individually but inconsistent, so the same underlying "no duration data" case reads differently across screens.
**Fix:** Align on one convention (reserve `'--'` strictly for `null`/`undefined`; render `0m`/`0h 0m` for an explicit zero).

### IN-04: Restored chat history renders with a blank timestamp

**File:** `frontend/src/screens/ChatScreen.tsx:151-159`
**Issue:** When hydrating `conversation.priorMessages` after a cache-miss reload, each historical message is given `timestamp: ''`. `ChatBubble` renders these with no time label at all, while newly sent/received messages in the same session show a real time — a visible inconsistency after any reload.
**Fix:** If the backend message history includes a created-at timestamp, format and use it; otherwise omit the timestamp slot consistently rather than only for reloaded history.

---

_Reviewed: 2026-07-10T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
