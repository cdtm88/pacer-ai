# Phase 9: Frontend Resilience - Research

**Researched:** 2026-07-07
**Domain:** React 19 SPA resilience — SSE stream recovery, localStorage session integrity, React Query cache scoping, React Router error boundaries, Supabase auth PKCE flow, FastAPI error-envelope contracts
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Full 14-item Critical+Major list from `APP-REVIEW-260703.md` is in scope, not just the 8 items ROADMAP.md's goal line names. The 6 additional items: ZWO export error-shape mismatch, iOS ZWO popup-block, live-resume overshoot, `AppLayout` scroll/pin breakage, cross-account query-cache bleed, upload progress/drag-drop validation.
- **D-02:** On chat SSE stream error: auto-retry silently 1-2 times with backoff; if retries fail, clear `activeStreamUrl`, re-enable input, show an inline error banner with a manual **Retry** button.
- **D-03:** Empty-done-swallow (tool-only turn, `isDone && !content`): clear `activeStreamUrl` and unbrick input silently — render nothing extra. Matches a normal tool-only turn with no visible reply.
- **D-04:** Conversation history on `['active-conversation']` cache miss (5min GC): refetch the existing conversation from the DB instead of creating a new row; show a brief loading state while it loads. (Not a gcTime bump — that doesn't fix the root cause.)
- **D-05:** Onboarding's confirm-stream (server error / early close currently sticks the spinner forever): same recovery pattern as chat — clear stream state, show inline error, manual retry button. Keep the two SSE consumers consistent; share `useSSEStream.ts` if onboarding doesn't already. **Research finding: literal hook-sharing is not implementable — see Pitfall 1. The UX-consistency intent is satisfied via a shared retry policy + shared `StreamErrorBanner` component instead.**
- **D-06:** `PersistedSession` (`sessionPersistence.ts`) gains `sessionId` + `date` fields. On mismatch vs. today's actual session, silently discard the stale localStorage entry and render Today's real state — no dialog, no toast. The user was never actually mid-session on the correct one.
- **D-09:** Fallback UI is minimal: "Something went wrong" message + reload button. No error detail, no report action — single-user personal app, no support pipeline.
- **D-10:** Error boundary is **per-route**, nested inside `AppLayout` — a crash on one screen must not take out the nav shell (bottom tab bar / desktop sidebar); the user can navigate away from the broken screen.

### Claude's Discretion

These are deterministic bug fixes with one obviously-correct behavior — no real UX ambiguity, so not individually discussed:
- **Live-resume overshoot:** make live backgrounding resume match the already-correct reload-path fast-forward behavior (`DuringSessionScreen.tsx`).
- **Cross-account cache bleed:** clear the React Query cache on `SIGNED_IN` / sign-out auth transitions (natural hook point: `AuthGate`/`FirstRunGate`, Phase 4).
- **Ride field mismatch:** align frontend field reads (`duration_seconds`/`avg_power_watts`/`file_name`) to the backend's actual response shape (`duration_secs`/`avg_power`) in `api.ts` vs `rides.py`.
- **ZWO export error shape:** FastAPI wraps `{detail:{error}}`; frontend currently reads `err.error`; fix parsing so the `session_not_found` branch is reachable.
- **iOS ZWO export popup-block:** `window.open(blobUrl)` must fire synchronously inside the click handler, before any `await`; currently called after an `await` in `api.ts`.
- **Auth callback double-exchange:** resolve to a single code-consumption path — either disable `detectSessionInUrl` or drop the redundant manual `exchangeCodeForSession` call (researcher confirms which is correct for the current Supabase client version). **Research finding: drop the manual call — see Pattern 4.**
- **Upload query invalidation:** extend success invalidation beyond `['rides']` to also invalidate PMC/session queries.
- **Upload UX:** add progress indication; validate `.fit` extension on drag-drop (currently only validated on the file-picker path).
- **AppLayout scroll/pin:** fix `min-h-screen` breaking inner scroll panes so the chat input stays pinned and auto-scroll actually works.

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope. Scope was explicitly *expanded* (D-01) to the full app-review list rather than narrowed; nothing was pushed out to a future phase.
</user_constraints>

## Summary

This phase fixes 14 verified bugs across the existing frontend codebase (no new features, no new dependencies). All 14 items were re-verified against the **live code** in this session — the file:line references in `APP-REVIEW-260703.md` are stale in several places (the code has moved since the review), but every one of the 14 underlying bugs is still present and confirmed by direct inspection. Current line numbers and exact fix locations are documented per item below.

Three items diverge meaningfully from what the review/CONTEXT.md implied, and the planner must account for this:

1. **Auth callback double-exchange (item 11):** the codebase already has the infrastructure to fix this cleanly. `useAuth.ts` already special-cases `/auth/callback` to avoid the null-session bounce race and already listens globally via `onAuthStateChange`. Official Supabase docs are unambiguous: with `detectSessionInUrl: true`, the manual `exchangeCodeForSession(code)` call in `AuthCallbackScreen.tsx` must be **deleted**, not kept. This is a net code-deletion fix, not a rework.
2. **Live-resume overshoot (item 8):** the bug is real but lives in a different place than a literal read of the stale line numbers suggests. It's in the `useEffect` that watches `secondsLeft === 0` and calls `goNext()` exactly once (`DuringSessionScreen.tsx`), which does not use the same multi-step fast-forward loop that `computeRestoredState()` already correctly uses on remount. The fix is to route the live-resume path through equivalent fast-forward logic, not to touch the reload path (which is already correct).
3. **D-05's "share `useSSEStream.ts`" instruction cannot be implemented literally.** `useSSEStream.ts` is hardcoded to browser `EventSource`, which is GET-only and cannot send an `Authorization` header or a JSON body. Onboarding's `runStream` is POST-based (`fetch()` + manual `ReadableStream` SSE parsing) by necessity, and cannot be swapped onto `EventSource` without a larger auth/token-exchange rework that is out of scope. **What can and should be shared** is the retry/error-recovery *policy* (1-2 silent retries → terminal error state) and the `StreamErrorBanner` UI component (already specified in `09-UI-SPEC.md`) — not the transport hook itself. See Pitfall 1 and Open Question 1 below; this satisfies D-05's actual UX intent (consistent recovery behavior across both screens) without a false-equivalence transport merge.

**Primary recommendation:** Treat this as 14 independent, narrowly-scoped bug fixes. Do not batch them into shared abstractions beyond what's already specified in `09-UI-SPEC.md` (the `StreamErrorBanner` component) — most of the "shared root cause" items are already isolated to one function/file each.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| SSE stream retry/error state | Browser / Client | — | `useSSEStream.ts` + `OnboardingScreen.tsx` own reconnect policy; no backend change needed (error event contract already correct, verified in `_sse.py`) |
| Conversation history reload | Browser / Client (React Query cache policy) | API / Backend (read endpoint) | Cache-miss recovery is a client concern; requires a `GET /conversations/{id}` (or equivalent) read path — verify existence before assuming client-only fix |
| Stale session id/date guard | Browser / Client | — | Pure localStorage read/compare logic in `sessionPersistence.ts` |
| Router error boundary | Browser / Client | — | React Router `ErrorBoundary` route property; no backend involvement |
| Ride field contract | API / Backend (source of truth) | Browser / Client (consumer) | Backend field names (`duration_secs`, `avg_power`) are authoritative; frontend interface must match, not vice versa |
| ZWO export error shape | API / Backend (source of truth) | Browser / Client (consumer) | FastAPI's `HTTPException(detail={...})` envelope is fixed framework behavior; frontend must parse the real shape |
| iOS export popup-block | Browser / Client | — | Pure event-loop/user-gesture timing issue in `api.ts` |
| Live-resume overshoot | Browser / Client | — | Pure client-side timer/state logic in `DuringSessionScreen.tsx` |
| AppLayout scroll/pin | Browser / Client (CSS/layout) | — | Tailwind height utility chain, no logic change |
| Cross-account cache bleed | Browser / Client (React Query) | — | `queryClient.clear()` on auth transition, in `router.tsx`'s `RootProvider` |
| Auth callback double-exchange | Browser / Client (Supabase client config) | — | Client-side PKCE flow config; no backend change |
| Upload progress + validation | Browser / Client | — | `FitUploadZone.tsx` UI-only; backend upload endpoint unchanged |

## Standard Stack

No new libraries are introduced in this phase. All fixes use frameworks and APIs already installed and in production use.

### Core (already installed, versions verified)
| Library | Installed Version | Latest (npm) | Used For |
|---------|---------|---------|--------------|
| react-router | 8.0.1 | 8.1.0 `[VERIFIED: npm registry]` | `ErrorBoundary` route property for the per-route error boundary (item 12) |
| @supabase/supabase-js | 2.108.2 | — (current, matches installed) | PKCE auth flow fix (item 11) |
| @tanstack/react-query | 5.101.0 | — (current) | Cache invalidation fixes (items 4, 10, 14) |

**No `npm install` is required for this phase.** If the planner considers upgrading `react-router` 8.0.1 → 8.1.0 in passing, treat that as out-of-scope opportunistic churn — do not bundle a dependency bump into a bug-fix phase unless a specific fix requires it (none do; `ErrorBoundary` route property has existed since React Router v6.4).

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| React Router `ErrorBoundary` route property (item 12) | Hand-rolled class-component `<ErrorBoundary>` wrapper + manual placement | React Router's built-in mechanism is already wired to the existing `createBrowserRouter` tree, requires zero new component, and correctly scopes to "per-route, parent layout stays mounted" (D-10) for free. A hand-rolled wrapper would have to be manually inserted at every route `element:` and reimplement the "closest boundary" bubbling React Router already gives. Use the built-in. |
| `react-error-boundary` npm package | (same, not needed) | Not needed — React Router's own `ErrorBoundary` route property supersedes it for this codebase's routing structure. Do not add this dependency. |

## Package Legitimacy Audit

**No new external packages are introduced by this phase.** All 14 fixes are implemented with libraries already in `package.json` and already vetted in prior phases. This section is intentionally empty — no audit table required.

## Architecture Patterns

### System Architecture Diagram — SSE Retry State Machine (chat + onboarding, shared policy)

```
User sends message
      │
      ▼
Open stream (EventSource for chat / fetch+ReadableStream for onboarding)
      │
      ├── token/tool_start/tool_result events ──► accumulate content, show thinking indicator
      │
      ├── done event (with content) ──► commit coach message, clear stream state, re-enable input
      │
      ├── done event (empty content, tool-only turn) ──► clear stream state SILENTLY, re-enable
      │        (D-03: render nothing extra — matches a normal tool-only turn)
      │
      └── error event / stream fault
                │
                ▼
        Silent auto-retry (attempt 1) ── same URL/request, backoff delay ──┐
                │ fails again                                              │
                ▼                                                          │
        Silent auto-retry (attempt 2) ── backoff delay ─────────────────────┘
                │ fails again
                ▼
        Terminal error state
                │
                ├──► clear activeStreamUrl / isStreaming, re-enable input
                └──► render StreamErrorBanner (icon + "Connection failed."/"Couldn't save your
                     profile." + manual Retry button)
                            │
                       user clicks Retry
                            │
                            ▼
                 Re-derive fresh URL/request (last user message, fresh JWT)
                            │
                            ▼
                 Open stream again (re-enters top of diagram; banner clears optimistically)
```

### Recommended Project Structure (no new files required)

```
frontend/src/
├── hooks/
│   └── useSSEStream.ts          # add: internal 1-2x silent retry with backoff; keep transport = EventSource
├── screens/
│   ├── ChatScreen.tsx           # add: terminal-error effect (clear activeStreamUrl), track last-sent
│   │                             #      message for Retry, render StreamErrorBanner
│   └── OnboardingScreen.tsx     # add: apply same retry-then-terminal-error policy inside runStream's
│                                 #      catch/error branches; render StreamErrorBanner
├── components/
│   ├── chat/
│   │   └── StreamErrorBanner.tsx   # NEW small component per 09-UI-SPEC.md — shared by both screens
│   └── ErrorBoundaryFallback.tsx   # NEW — rendered via route ErrorBoundary property
├── lib/
│   └── sessionPersistence.ts    # add: sessionId + date fields to PersistedSession
├── router.tsx                   # add: ErrorBoundary per protected leaf route; SIGNED_IN cache clear
├── components/AppLayout.tsx     # fix: min-h-screen -> h-dvh (both wrapping divs)
└── lib/api.ts                   # fix: Ride interface field names; ZWO error-shape parse;
                                  #      window.open ordering relative to await
```

### Pattern 1: Internal retry-with-backoff inside `useSSEStream` (item 2, D-02)

**What:** The hook currently opens exactly one `EventSource` and, on `error`, sets `error` state and closes — with nothing ever clearing `activeStreamUrl` in the consumer, `isStreaming` stays true forever (input stays disabled). Fix: retry inside the hook's effect closure using the *same* `url`, so no consumer re-render is required to trigger a retry attempt.

**When to use:** Any transient SSE `error` event (network blip, mid-stream 5xx) before the stream has reached `done`.

**Verified current code** (`frontend/src/hooks/useSSEStream.ts:74-87`):
```typescript
// CURRENT (buggy) — no retry, error never clears, consumer's activeStreamUrl never clears
es.addEventListener('error', (e: Event) => {
  if (streamCompleted) return
  try {
    const data = JSON.parse((e as MessageEvent).data) as { code?: string; message?: string }
    setError(data.message ?? 'Stream error')
  } catch {
    setError('Stream error')
  }
  setIsThinking(false)
  es.close()
})
```

**Fix shape** (retry inside the effect, terminal error only after exhausting attempts):
```typescript
// Inside the useEffect(() => { ... }, [url]) closure:
let retryCount = 0
const MAX_RETRIES = 2
const BACKOFF_MS = [500, 1500] // attempt 1 waits 500ms, attempt 2 waits 1500ms

function openStream() {
  const es = new EventSource(url)
  // ... token/tool_start/tool_result/done listeners unchanged ...
  es.addEventListener('error', (e: Event) => {
    if (streamCompleted) return
    es.close()
    if (retryCount < MAX_RETRIES) {
      const delay = BACKOFF_MS[retryCount]
      retryCount++
      setTimeout(openStream, delay) // no state change -> consumer stays "streaming", no flash
    } else {
      // terminal: surface to consumer
      try {
        const data = JSON.parse((e as MessageEvent).data) as { message?: string }
        setError(data.message ?? 'Stream error')
      } catch {
        setError('Connection failed.')
      }
      setIsThinking(false)
    }
  })
}
openStream()
```

Note: the backend's `error` event payload is confirmed as `{"code": "server_error", "message": str(exc)}` (`backend/routes/_sse.py:131-132`) — the frontend's existing `JSON.parse` shape assumption is already correct, no backend change needed.

### Pattern 2: Empty-done-swallow fix (item 3, D-03)

**What:** `ChatScreen.tsx:88` gates the "commit message + clear stream" effect on `if (isDone && content)`. A tool-only turn produces `isDone=true, content=''`, so the effect body never runs and `activeStreamUrl` is never cleared. Because `isStreaming = activeStreamUrl !== null && !isDone` reads `isDone` directly from the hook (not from the effect having run), the input *visually* re-enables once `isDone` flips true — but `handleSend`'s guard `if (!conversation?.id || activeStreamUrl) return` still blocks every subsequent send because `activeStreamUrl` itself was never nulled. This is a **silent** forever-stuck state (no visible symptom except "nothing happens" — matches the review's "handleSend silently returns forever").

**Fix:** split the effect into two conditions — always clear `activeStreamUrl`/`pendingUserMessage` on `isDone`, and only push a message onto the list when `content` is non-empty:
```typescript
useEffect(() => {
  if (!isDone) return
  if (content) {
    setMessages((prev) => [...prev, { id: `coach-${Date.now()}`, role: 'coach', content, bubbleRole: detectBubbleRole(content), timestamp: formatTime(new Date()) }])
  }
  // D-03: always clear stream state on done, regardless of content — tool-only turns
  // render nothing extra but must still unbrick input.
  setActiveStreamUrl(null)
  setPendingUserMessage(null)
}, [isDone, content])
```

### Pattern 3: Router `ErrorBoundary` per-route (item 12, D-09/D-10)

**Verified via official React Router docs (v7/v8 data router):** use the `ErrorBoundary` property (not the older `errorElement` JSX prop) on `createBrowserRouter` route objects. When an error is thrown rendering a nested route's element, only the **closest** `ErrorBoundary` up the tree renders — parent route elements (here, `AppLayout`) remain mounted. This is exactly D-10's requirement ("crash on one screen must not take out the nav shell").

```typescript
// Source: https://reactrouter.com/how-to/error-boundary (verified 2026-07-07)
{
  element: <AppLayout />,
  children: [
    { index: true, element: <TodayScreen />, ErrorBoundary: RouteErrorFallback },
    { path: 'agenda', element: <AgendaScreen />, ErrorBoundary: RouteErrorFallback },
    { path: 'history', element: <HistoryScreen />, ErrorBoundary: RouteErrorFallback },
    { path: 'chat', element: <ChatScreen />, ErrorBoundary: RouteErrorFallback },
    { path: 'settings', element: <SettingsScreen />, ErrorBoundary: RouteErrorFallback },
  ],
},
```
`RouteErrorFallback` reads the error via `useRouteError()` but per D-09 must **not** render any error detail — just the fixed "Something went wrong" / "This page ran into a problem." copy + Reload button (`window.location.reload()`), per `09-UI-SPEC.md` §2.

**Placement decision:** attach `ErrorBoundary` to each of the 5 leaf routes individually (not once on the `AppLayout` route object itself). Attaching it once on `AppLayout`'s route entry would still keep the sidebar/tab-bar mounted (React Router's rendering model separates the route's own `element` from its `ErrorBoundary`), but per-leaf attachment gives a clearer mental model matching "a crash on one screen" (D-10's exact phrasing) and avoids the fallback also swallowing errors thrown by `AppLayout` itself (which should probably bubble to a higher boundary, not silently blame nav). Recommend one shared `RouteErrorFallback` component reused across all 5 `ErrorBoundary` slots (DRY, matches D-09's "single minimal fallback" intent) — do not write 5 separate fallback components.

### Pattern 4: Supabase PKCE — remove manual exchange, rely on `detectSessionInUrl` (item 11)

**Verified via official Supabase docs** (`https://supabase.com/docs/guides/auth/sessions/pkce-flow`, fetched 2026-07-07): *"Do not manually call `exchangeCodeForSession()` if `detectSessionInUrl` is enabled... this would result in attempting to exchange the same auth code twice, which violates the security constraint that codes can only be exchanged for an access token once."*

Current code has both mechanisms active simultaneously:
- `frontend/src/lib/supabase.ts:12` — `detectSessionInUrl: true` (auto-exchanges the code in the background on client init)
- `frontend/src/screens/AuthCallbackScreen.tsx:29-47` — manually calls `supabase.auth.exchangeCodeForSession(code)` again

Whichever consumes the single-use code first wins; the second exchange attempt fails, and the existing `.catch`-equivalent branch (`if (error) navigate('/login')`) bounces a user with a **valid session** back to the login screen.

**Fix:** delete the manual `exchangeCodeForSession(code)` branch in `AuthCallbackScreen.tsx` entirely. `useAuth.ts` (already in the codebase, unmodified) already:
1. Special-cases `pathname === '/auth/callback'` to skip writing a premature `{session: null}` seed (`useAuth.ts:19,32`) — this guard exists specifically so it doesn't race the callback screen.
2. Subscribes globally via `onAuthStateChange` and writes any resolved session into `authStore` (`useAuth.ts:45-54`).

So once `detectSessionInUrl` finishes its background exchange, `onAuthStateChange` fires and `useAuth.ts` populates the store automatically — `AuthCallbackScreen` just needs to watch `useAuthStore` (or poll `getSession()`) for a session to appear, then `navigate('/', {replace: true})`, with a short timeout (recommend 5-8s, well under the code's 5-minute validity window) falling back to `/login` if no session ever resolves (handles a genuinely invalid/expired code).

The implicit-flow branch (`hasImplicitTokens`) is not part of the double-exchange bug (`getSession()` is idempotent — it reads whatever `detectSessionInUrl` already parsed from the hash, it doesn't consume a single-use code) and can be left largely as-is, though it could be simplified to the same "watch the store" pattern for consistency. Not required to fix the bug.

### Pattern 5: Live-resume overshoot fix (item 8, Claude's Discretion)

**Verified current code** (`DuringSessionScreen.tsx`):
- Reload-path restore (`computeRestoredState`, lines 100-119) is **already correct**: a `while` loop walks forward through however many steps' worth of wall-clock time has elapsed since `stepStartEpoch`, correctly fast-forwarding through multiple completed steps and landing on the right in-progress step with the right remaining time.
- Live-path resume (component stays mounted, e.g., tab backgrounded then foregrounded without a reload) uses a *different* code path: `useSessionTimer` clamps `secondsLeft` to `Math.max(0, ...)`, and a separate `useEffect` (lines 219-221) fires `goNext()` exactly once whenever `secondsLeft` hits 0. `goNext()` always advances exactly one step and resets `stepStartEpoch = Date.now()` for the new step (full duration), with no awareness of how much *additional* time (beyond the just-finished step) has already elapsed. If the user was backgrounded long enough for 2+ steps to complete, only 1 step advances and the new step's timer starts fresh — silently absorbing/discarding the overshoot instead of fast-forwarding through it like the reload path does.

**Fix:** make the `secondsLeft === 0` effect call the *same* fast-forwarding logic used by `computeRestoredState`, anchored on the current `stepStartEpoch`, rather than a bare `goNext()`. Concretely: extract the `while` loop body from `computeRestoredState` into a shared helper `fastForwardSteps(stepIndex, completedDurationSecs, stepStartEpoch, steps, now)` that both call sites use — `computeRestoredState` calls it once on mount with `saved.stepStartEpoch`, and the live-resume effect calls it with the *current* `stepStartEpoch` state whenever it detects `secondsLeft === 0`, then applies the returned `{stepIndex, completedDurationSecs, stepStartEpoch}` via `setState` + `saveSession(...)` (matching the existing `goNext()` persistence pattern) instead of assuming exactly one step elapsed.

### Anti-Patterns to Avoid
- **Don't literally merge `OnboardingScreen`'s fetch-based SSE reader into `useSSEStream`'s `EventSource`-based hook.** `EventSource` cannot do POST or set `Authorization` headers — the two are fundamentally different transports for a documented reason (see comment at `OnboardingScreen.tsx:42-44`, and `api.ts`'s WR-006 comment on why chat is forced onto the query-param-token GET pattern). Share the *retry policy* and the *UI banner*, not the transport code.
- **Don't add a toast/dialog for the stale-session discard (item 1).** D-06 is explicit: silent discard, no UI. If the plan's verification steps expect any visible feedback here, that's a spec violation.
- **Don't fix the `Ride.file_name` mismatch by adding a `file_name` column/migration.** Verified: `rides` table (`0001_initial_schema.sql:70-79`) has no filename column, and the upload path (`rides.py:537`) uses **content-addressed storage** (`{user_id}/{content_hash}.fit`) — the original uploaded filename is never captured or persisted anywhere in the pipeline. Adding a migration to support this is a scope increase beyond a field-mismatch bug fix; the pragmatic fix (matching CONTEXT.md's Claude's Discretion framing of this as a fast, obviously-correct fix) is to remove `file_name` from the `Ride` interface and delete the "Source: {ride.file_name}" footnote block in `RideRow.tsx` (dead code — it never renders today since the field is always `undefined`).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Per-route crash isolation | Custom class-component `<ErrorBoundary>` wired manually into every route `element` | React Router's `ErrorBoundary` route config property + `useRouteError()` | Already wired to the existing `createBrowserRouter` tree; gives "closest boundary wins, parent stays mounted" behavior for free — exactly D-10's requirement |
| SSE reconnect/backoff | A generic reconnect library (e.g. an npm SSE client wrapper) | Hand-written retry loop inside the existing `useSSEStream` effect (2 attempts, small fixed backoff) | The retry surface is tiny (1-2 attempts, single hook) and the existing `EventSource`-based hook already owns the state; a library adds a dependency for a ~15-line fix |
| Cross-tab / cross-user cache scoping | Manually namespacing every React Query key by `user_id` | `queryClient.clear()` on `SIGNED_IN` (in addition to the already-handled `SIGNED_OUT`/`USER_UPDATED`) inside `RootProvider`'s existing `onAuthStateChange` listener (`router.tsx:31-35`) | The app is single-account-at-a-time; a full clear on any identity transition is simpler and sufficient — no need to thread `user_id` through every query key |

**Key insight:** every one of the 14 items is small in isolation (localStorage field addition, one CSS class change, one field-name rename, one `await` reorder, one route config property, one deleted function call). The risk in this phase is not technical complexity — it's touching 8+ files with narrowly scoped, easy-to-verify-in-isolation-but-easy-to-regress-together changes. Plan waves so items that touch the same file (see file-overlap table below) are sequenced, not parallelized blindly.

## Common Pitfalls

### Pitfall 1: D-05's "share `useSSEStream.ts`" cannot mean literal code reuse
**What goes wrong:** A plan that tries to make `OnboardingScreen.tsx` call `useSSEStream(url)` directly will break, because onboarding's request is `POST /api/onboarding/start` with a JSON body and an `Authorization: Bearer` header — `EventSource` supports neither.
**Why it happens:** D-05's wording ("share `useSSEStream.ts` if onboarding doesn't already") reads as a literal code-sharing instruction, but was written before this session's code-level verification of the transport constraint.
**How to avoid:** Scope this item as "apply the same retry-then-terminal-error *state machine* and render the same `StreamErrorBanner` component in both screens" — implemented as two separate but structurally parallel retry loops (one inside `useSSEStream`'s `EventSource` handler, one inside `OnboardingScreen.runStream`'s fetch/catch handling), not a shared hook.
**Warning signs:** A diff that imports `useSSEStream` into `OnboardingScreen.tsx` or that tries to make `useSSEStream` accept a `method`/`body` option — either is a sign the transport-merge trap has been fallen into.

### Pitfall 2: React Query key naming is inconsistent — invalidating "PMC" doesn't invalidate all PMC data
**What goes wrong:** `HistoryScreen.tsx` uses `queryKey: ['pmc-history']` (single string, hyphenated) while `TodayScreen.tsx` uses `queryKey: ['pmc', 'latest']` (two-element array). React Query's `invalidateQueries` does prefix matching on the array — `invalidateQueries({queryKey: ['pmc']})` matches `['pmc', 'latest']` but does **not** match `['pmc-history']` (different top-level key entirely). A fix that only adds `['pmc']` to the upload-success invalidation list will silently miss the History screen's PMC sparkline.
**Why it happens:** the two screens were built at different times with different naming conventions and neither was ever reconciled.
**How to avoid:** the upload-success invalidation (item 14c) must explicitly list every affected key: `['rides']`, `['pmc', 'latest']`, `['pmc-history']`, `['session', 'today']`, `['sessions', 'upcoming']`. Do not rely on prefix-matching a shortened key.
**Warning signs:** After implementing, manually check `HistoryScreen.tsx:40` and `TodayScreen.tsx:58` both still say what you listed in the invalidation call.

### Pitfall 3: Existing tests encode the *current buggy* behavior as the expected behavior
**What goes wrong:** `frontend/src/tests/chat.test.tsx:308` has a test titled `'after error event fires before done, "Connection lost. Reconnecting..." banner appears'` — this asserts the OLD permanent-banner behavior that D-02 explicitly replaces (silent retry → terminal error → manual Retry button, not a permanent "Reconnecting..." message). If this phase's plan only *adds* tests without *updating* this one, CI will have a passing test that contradicts the new correct behavior — a false-green signal.
**Why it happens:** tests were written when the "amber reconnecting" banner was still the intended (if broken) design.
**How to avoid:** the plan must include an explicit task to update/replace this test (and check `onboarding.test.tsx`, `auth.test.tsx`, `session.test.tsx` for the same pattern) alongside the implementation change, not as an afterthought.
**Warning signs:** `npm run test` passes but a test name still references "Reconnecting..." after the fix is implemented.

### Pitfall 4: `AppLayout`'s height-chain fix must account for `env(safe-area-inset)` / iOS Safari dynamic viewport
**What goes wrong:** Simply swapping `min-h-screen` → `h-screen` (`100vh`) can reintroduce the classic iOS Safari "100vh is taller than the visible viewport when the address bar is showing" bug, which is exactly why `DuringSessionScreen.tsx` already uses `100dvh` (dynamic viewport height) elsewhere in this same codebase (lines 233, 282, 472, 504).
**Why it happens:** `100vh` on iOS Safari measures the *largest possible* viewport (address bar collapsed), not the *current* one, causing overflow/clipping at the bottom.
**How to avoid:** use Tailwind's `h-dvh` utility (not `h-screen`) for both wrapping divs in `AppLayout.tsx` (lines 14 and 21), matching the project's own established pattern rather than introducing a second, inconsistent height unit. Confirm Tailwind v4 (already in this project) supports `dvh` utilities — it does, as of Tailwind v3.4+ and unchanged in v4.
**Warning signs:** Chat input appears pinned in desktop Chrome DevTools but is clipped or scrolls oddly on a physical iOS Safari test (IOS-03 already requires physical-device testing per `MEMORY.md`'s "IOS-03 timer persistence resolved... needs physical-device re-test" — this AppLayout fix should be covered by the same re-test pass).

### Pitfall 5: `SIGNED_IN` cache-clear must not clear on token refresh
**What goes wrong:** A naive fix might add `event === 'SIGNED_IN'` to the existing `if (event === 'SIGNED_OUT' || event === 'USER_UPDATED')` check without checking whether Supabase also fires `SIGNED_IN` on ordinary token refresh (it does not — that's `TOKEN_REFRESHED`, a separate event — but this is worth a deliberate one-line verification rather than an assumption, since an over-aggressive clear would refetch all queries on every silent token refresh, a real performance/UX regression).
**Why it happens:** Supabase's `onAuthStateChange` event taxonomy is easy to conflate (`SIGNED_IN`, `TOKEN_REFRESHED`, `USER_UPDATED`, `INITIAL_SESSION`, `SIGNED_OUT`, `PASSWORD_RECOVERY`).
**How to avoid:** add exactly `'SIGNED_IN'` to the existing OR-chain (`router.tsx:32`) — do not add `'TOKEN_REFRESHED'` or `'INITIAL_SESSION'`. `useAuth.ts:48` already shows this codebase is aware of the `INITIAL_SESSION` distinction (`if (newSession === null && event === 'INITIAL_SESSION') return`), reuse that awareness.
**Warning signs:** Chat/history/session queries visibly re-fetch (loading skeletons flash) every ~time the JWT auto-refreshes in the background during normal use.

## Code Examples

### Ride interface field-name alignment (item 5)
```typescript
// Source: verified against backend/routes/rides.py:628-657 (GET /rides/ SELECT columns)
// BEFORE (frontend/src/lib/api.ts:82-95) — fields never match what the backend sends:
export interface Ride {
  id: string
  user_id: string
  session_id: string | null
  file_name: string              // never returned by backend — remove
  ride_date: string
  duration_seconds: number | null   // backend field is duration_secs
  distance_m: number | null         // never returned by backend — remove
  np_watts: number | null
  tss: number | null
  avg_power_watts: number | null    // backend field is avg_power
  compliance_pct?: number | null
  created_at: string                // never returned by backend — remove, or add to backend SELECT
}

// AFTER — matches backend/routes/rides.py:647-649 SELECT list exactly:
export interface Ride {
  id: string
  user_id: string
  session_id: string | null
  ride_date: string
  duration_secs: number | null
  np_watts: number | null
  tss: number | null
  avg_power: number | null
  intensity_factor: number | null
  avg_hr: number | null
  avg_cadence: number | null
  ftp_used: number | null
  compliance_pct?: number | null
}
```
`RideRow.tsx` must be updated in lockstep: `ride.duration_seconds` → `ride.duration_secs` (3 call sites: lines 126, 209, 226), `ride.avg_power_watts` → `ride.avg_power` (2 call sites: lines 167, 184), remove the `ride.file_name` block (lines 305-315) entirely, and change `formatDate(ride.ride_date ?? ride.created_at)` (line 103) to just `formatDate(ride.ride_date)` since `ride_date` is always populated by the insert path (`rides.py:560-562` always sets it, falling back to today's date, never null) and `created_at` is not selected by the backend anyway.

### ZWO export error-shape fix (item 6)
```typescript
// Source: verified against backend/routes/sessions.py:315-320 — FastAPI's HTTPException(detail={...})
// wraps the dict under a top-level "detail" key automatically. Actual JSON response body:
//   {"detail": {"error": "session_not_found", "detail": "No session found for this user with the given id"}}

// BEFORE (frontend/src/lib/api.ts:250-252):
if (!res.ok) {
  const err = await res.json().catch(() => ({})) as { error?: string }
  throw new Error(err?.error ?? `export failed ${res.status}`)   // err.error is always undefined
}

// AFTER:
if (!res.ok) {
  const err = await res.json().catch(() => ({})) as { detail?: { error?: string; detail?: string } }
  throw new Error(err?.detail?.error ?? err?.detail?.detail ?? `export failed ${res.status}`)
}
```
This mirrors the pattern already correctly used elsewhere in the same file for `markSessionMissed`/`markSessionDone`/`uploadRide` (`api.ts:210-217, 233-237, 307-317`), which already correctly read `body?.detail?.detail` / `body?.detail?.error` — the ZWO export function is the one outlier that never got this treatment.

### iOS popup-block fix (item 7)
```typescript
// Source: verified frontend/src/lib/api.ts:246-277 — window.open fires at line 265,
// AFTER `await apiFetch(...)` (line 247) and `await res.blob()` (line 258). By the time
// window.open executes, the click handler's synchronous execution window has long closed,
// so iOS Safari's popup blocker treats it as programmatic (non-user-initiated) and blocks it.
//
// Fix: the export must be split into two phases — (1) an async fetch+blob phase that runs
// first WITHOUT opening anything, (2) a synchronous window.open call issued directly inside
// the onClick handler using the already-resolved blob URL. Because the current function is a
// single async function called from onClick, the cleanest fix within this function's shape is
// to pre-fetch the blob on a user gesture that's closer to the open() call — OR (simpler,
// matches existing code structure) switch iOS to the same hidden-anchor-click pattern already
// used for non-iOS (lines 270-276), which does NOT have the same popup-blocker restriction
// window.open() does; anchor.click() on a link element is not subject to popup blocking rules
// the way window.open() is. Recommended fix: drop the isIOS window.open() branch entirely and
// use the anchor-click path unconditionally — the comment at line 261-262 claims "iOS Safari
// ignores <a download> for blob URLs" as the reason for the window.open() branch; verify this
// claim empirically before deciding whether to unify the two paths or keep window.open() but
// restructure the function to call it synchronously from the onClick handler.
```
**This one needs an explicit implementation decision, not just a mechanical fix — see Open Question 2.**

### Cross-account cache clear (item 10)
```typescript
// Source: frontend/src/router.tsx:30-37 — existing listener, minimal diff
useEffect(() => {
  const { data: { subscription } } = supabase.auth.onAuthStateChange((event) => {
    if (event === 'SIGNED_OUT' || event === 'USER_UPDATED' || event === 'SIGNED_IN') {
      queryClient.clear()
    }
  })
  return () => subscription.unsubscribe()
}, [queryClient])
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| `errorElement` JSX prop on route objects (React Router v6.4-v6) | `ErrorBoundary` component property on route config objects | React Router v7 data-router API consolidation, carried into v8 (installed here) | Same behavior, new prop name; `errorElement` still works in v8 for back-compat but `ErrorBoundary` is the current documented pattern — use it since this is a fresh implementation, not a migration |

**Deprecated/outdated:** none of the 14 fixes involve deprecated APIs — every fix touches actively-maintained, current-version code paths.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | iOS Safari genuinely ignores `<a download>` for blob: URLs (the stated reason for the existing `window.open()` iOS branch in `api.ts:261-267`) | Code Examples — iOS popup-block fix | If this claim is actually false/outdated on current iOS Safari versions, the simpler fix (drop the iOS branch, use the anchor-click path unconditionally for all platforms) is correct and the whole `isIOS` special-case can be deleted. If true, the fix must instead restructure to call `window.open()` synchronously inside the click handler before any `await`. This materially changes the shape of the fix — flagged as Open Question 2, needs a quick empirical check (or an iOS Safari changelog check) before planning the exact diff. |
| A2 | Recommended backoff delays for SSE retry (500ms, 1500ms) are reasonable defaults | Pattern 1 | Low risk — D-02 only specifies "1-2 times with backoff," not exact timings; these are a reasonable implementation default, not a locked requirement. Planner/implementer can adjust without re-confirming with the user. |
| A3 | `['pmc', 'latest']` and `['pmc-history']` are the only two PMC-related query keys needing invalidation (no others exist elsewhere in the codebase) | Pitfall 2 / Code Examples | Verified via repo-wide grep for `queryKey:` (11 call sites total, all enumerated) — low risk, but if a future screen adds a new PMC query key without updating the upload invalidation list, the same staleness bug recurs. Worth a code comment at the invalidation call site pointing future authors at this pattern. |

## Open Questions

1. **Can `useSSEStream.ts` and `OnboardingScreen.tsx`'s retry logic share an extracted policy helper, or should they stay as two independent implementations?**
   - What we know: both need the same state machine (silent retry x1-2 with backoff, then terminal error). Transport layer cannot be shared (Pitfall 1).
   - What's unclear: whether extracting a tiny `retryWithBackoff(fn, attempts, delays)` utility used by both is worth the indirection for ~15 lines of logic each, versus just duplicating the small retry loop in both places with a comment cross-referencing the other.
   - Recommendation: duplicate the small loop with a cross-reference comment (`// Mirrors the retry policy in useSSEStream.ts — keep behavior in sync`) rather than introducing a shared utility module for two call sites. Revisit only if a third SSE consumer appears.

2. **Does iOS Safari actually still block `<a download>` on blob: URLs?** (see Assumption A1)
   - What we know: the existing code comment asserts this as fact and branches on `isIOS` because of it; this comment predates this research session and may itself be stale (iOS Safari's blob/download handling has changed across versions in the past).
   - What's unclear: whether this needs re-verification against a current iOS Safari version before deciding the fix shape, or whether the safer move is to keep the two-branch structure but fix the *ordering* (fetch+blob synchronously-adjacent to a fresh user gesture is not achievable in a pure refactor — the real fix likely requires either (a) confirming the anchor-click path works fine on iOS too and dropping the branch, or (b) restructuring `exportSessionZwo` so the network fetch happens on `mousedown`/earlier and only the already-resolved `window.open(blobUrl)` happens in the `onClick`).
   - Recommendation: planner should scope a task to empirically test the anchor-click (`a.download` on blob URL) path on the target iOS Safari version as the first step of implementing this fix, before committing to a specific code shape. This is a case where "verify on real device" (already an established pattern per IOS-03/`MEMORY.md`) applies again.

3. **Should the `AuthCallbackScreen` timeout-fallback-to-`/login` duration be tied to anything, or is a fixed ~5-8s reasonable?**
   - What we know: the PKCE code itself is valid for 5 minutes server-side, but the *client-side* auto-exchange via `detectSessionInUrl` should resolve within a second or two of page load under normal network conditions.
   - What's unclear: no explicit UX decision was made on this exact timeout value (not covered in `09-CONTEXT.md`, which is fine — this is exactly the kind of small deterministic implementation detail the CONTEXT.md's "Claude's Discretion" framing already covers for adjacent items).
   - Recommendation: 5-8 seconds is reasonable; not worth a discuss-phase follow-up.

## Environment Availability

Skipped — this phase has no new external tool/service dependencies. All fixes use already-installed npm packages and already-configured Supabase/backend endpoints (verified live in this session; no missing dependency found).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Vitest 4.1.9 (`frontend/package.json`) |
| Config file | `frontend/vitest.config.ts` (jsdom environment, `src/tests/setup.ts`, glob `src/tests/**/*.{test,spec}.{ts,tsx}`) |
| Quick run command | `cd frontend && npx vitest run src/tests/<file>.test.tsx` |
| Full suite command | `cd frontend && npx vitest run` |

Existing test files directly relevant to this phase's scope (all pre-date the fixes and, per Pitfall 3, some encode the *current buggy* behavior as expected):
`chat.test.tsx` (327 lines), `onboarding.test.tsx` (65 lines), `useSSEStream.test.ts` (190 lines), `useSessionTimer.test.ts`, `auth.test.tsx` (215 lines), `session.test.tsx` (203 lines).

### Bug Item → Test Map

| Item | Behavior | Test Type | Automated Command | File Exists? |
|------|----------|-----------|-------------------|-------------|
| 1. Stale session hijack | `PersistedSession` id/date mismatch discards stale entry silently | unit | `npx vitest run src/tests/session.test.tsx` | Exists — extend |
| 2. Chat SSE error bricks input | Auto-retry then terminal error clears `activeStreamUrl`, re-enables input | unit | `npx vitest run src/tests/useSSEStream.test.ts src/tests/chat.test.tsx` | Exists — must update the stale "Reconnecting..." assertion (Pitfall 3) |
| 3. Empty-done swallow | Tool-only turn (done + empty content) clears stream state silently | unit | `npx vitest run src/tests/chat.test.tsx` | Exists — extend |
| 4. History reload on cache miss | `['active-conversation']` GC'd → refetch existing conversation, not a new row | unit/integration | `npx vitest run src/tests/chat.test.tsx` | Extend — requires mocking a conversation-read endpoint; confirm it exists in `api.ts`/backend before planning this task (see note below) |
| 5. Ride field mismatch | History displays real values, not "--" | unit | `npx vitest run src/tests/` (new `history.test.tsx` likely needed — none currently found under this name) | Wave 0 gap — no `history.test.tsx`/`RideRow.test.tsx` found in repo |
| 6. ZWO error shape | `session_not_found` branch reachable, correct toast | unit | new test needed | Wave 0 gap |
| 7. iOS ZWO popup-block | manual/device verification (see Open Question 2) | manual-only | — | N/A — physical iOS Safari test, same pattern as IOS-03 |
| 8. Live-resume overshoot | Multi-step background suspension fast-forwards correctly | unit | `npx vitest run src/tests/useSessionTimer.test.ts src/tests/session.test.tsx` | Exists — extend with a multi-step-elapsed scenario |
| 9. AppLayout scroll/pin | Chat input stays pinned, auto-scroll works | manual/visual + iOS device retest | — | manual-only (layout/CSS, not easily unit-testable) |
| 10. Cross-account cache bleed | `queryClient.clear()` fires on `SIGNED_IN` | unit | `npx vitest run src/tests/auth.test.tsx` | Exists — extend |
| 11. Auth callback double-exchange | Single code-consumption path, no login bounce on valid session | unit | `npx vitest run src/tests/auth.test.tsx` | Exists — extend/rewrite the manual-exchange-mock scenario |
| 12. Router error boundary | Per-route crash renders fallback, nav shell stays mounted | unit/integration | new test needed (render a route tree with a throwing component) | Wave 0 gap |
| 13. Onboarding confirm-stream stuck spinner | Server error/early close surfaces retry banner, not infinite spinner | unit | `npx vitest run src/tests/onboarding.test.tsx` | Exists — extend |
| 14. Upload progress/drag-drop/invalidation | Progress bar renders while uploading; drag-drop rejects non-.fit; success invalidates pmc/session queries | unit | new test likely needed (no `FitUploadZone.test.tsx` found) | Wave 0 gap |

**Note on item 4 (history reload):** before scoping this as a pure client-side fix, verify whether a `GET /conversations/{id}` (or `GET /conversations/{id}/messages`) read endpoint already exists in the backend. This research pass did not locate `backend/routes/conversations.py`'s full read-path contract — the planner/implementer must check this first, since "refetch the existing conversation from the DB" (D-04) requires a backend read endpoint to exist. If none exists, this single item has a backend-endpoint sub-task hiding inside what CONTEXT.md frames as a client-only fix.

### Sampling Rate
- **Per task commit:** run the specific test file(s) touched by that task's fix (see table above)
- **Per wave merge:** `cd frontend && npx vitest run` (full suite)
- **Phase gate:** full suite green + the 4 manual-only items (7, 9, and the iOS physical-device retest) explicitly checked off before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `frontend/src/tests/history.test.tsx` or `RideRow.test.tsx` — covers item 5 (Ride field alignment)
- [ ] New test coverage for item 6 (ZWO export error-shape parsing) — likely belongs in an existing `zwo`/export-related test file if one exists, otherwise new
- [ ] New test coverage for item 12 (router error boundary render + nav-shell-stays-mounted assertion)
- [ ] `frontend/src/tests/FitUploadZone.test.tsx` (or equivalent) — covers item 14 (progress indicator, drag-drop validation, invalidation call list)
- [ ] Verify backend read-endpoint contract for item 4 before finalizing its test plan (see note above)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Item 11 (auth callback) touches Supabase PKCE session establishment — fix must not weaken the single-use-code guarantee; removing the redundant manual exchange *strengthens* this (eliminates a race that could theoretically be exploited by an attacker replaying a stale code against the manual path — low real-world risk here, but worth noting the fix is a net security improvement, not just a UX fix) |
| V3 Session Management | yes | Item 10 (`queryClient.clear()` on `SIGNED_IN`) directly addresses a session-boundary data-leakage class bug (previous account's cached data rendering after a new sign-in) — this is the correct ASVS V3 control (session data must not persist across a principal change) |
| V5 Input Validation | yes | Item 14's drag-drop `.fit` extension check is a client-side UX guard only, **not** a security boundary — the backend's `fitdecode` parse-and-validate path (`ErrorHandling.WARN`, already in place per FIT-02) remains the actual trust boundary. Do not treat the frontend extension check as sufficient input validation; it exists purely to give the user a fast, friendly error before an upload round-trip. |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Stale cached data rendering after account switch (item 10) | Information Disclosure | `queryClient.clear()` on identity-transition auth events — already the chosen fix |
| Single-use auth code double-consumption (item 11) | (not a classic STRIDE attack here, but a correctness/DoS-of-self bug) — fixing it also closes a theoretical race where two code-exchange attempts racing could produce inconsistent client-observable auth state | Single code-consumption path per official Supabase guidance |
| JWT exposed as SSE query param (`?token=...`) | Information Disclosure (logs) | **Not in scope for this phase** — already tracked as WR-006 in `api.ts`'s own comment, explicitly deferred (short-lived token exchange endpoint is future work per Phase 10's hygiene list, not Phase 9's 14-item scope). Do not let the planner accidentally pull this into Phase 9 — it's adjacent but explicitly out of D-01's list. |

## Sources

### Primary (HIGH confidence)
- Live codebase inspection (all 14 items traced to exact current file/line locations in this session, 2026-07-07): `frontend/src/hooks/useSSEStream.ts`, `frontend/src/screens/ChatScreen.tsx`, `frontend/src/screens/OnboardingScreen.tsx`, `frontend/src/lib/sessionPersistence.ts`, `frontend/src/screens/TodayScreen.tsx`, `frontend/src/screens/DuringSessionScreen.tsx`, `frontend/src/hooks/useSessionTimer.ts`, `frontend/src/router.tsx`, `frontend/src/components/AppLayout.tsx`, `frontend/src/lib/api.ts`, `frontend/src/screens/AuthCallbackScreen.tsx`, `frontend/src/lib/supabase.ts`, `frontend/src/hooks/useAuth.ts`, `frontend/src/components/history/FitUploadZone.tsx`, `frontend/src/components/history/RideRow.tsx`, `backend/routes/rides.py`, `backend/routes/sessions.py`, `backend/routes/_sse.py`, `supabase/migrations/0001_initial_schema.sql`
- `npm view react-router version` — confirmed 8.1.0 latest against 8.0.1 installed `[VERIFIED: npm registry]`

### Secondary (MEDIUM confidence)
- [React Router — Error Boundaries](https://reactrouter.com/how-to/error-boundary) — `ErrorBoundary` route config property, "closest boundary" bubbling behavior, parent-stays-mounted semantics `[CITED]`
- [Supabase Docs — PKCE flow](https://supabase.com/docs/guides/auth/sessions/pkce-flow) — do-not-double-exchange guidance when `detectSessionInUrl: true` `[CITED]`
- [supabase/auth-js#782 — exchangeCodeForSession throws error instead of returning](https://github.com/supabase/auth-js/issues/782) `[CITED — corroborating, not primary]`

### Tertiary (LOW confidence)
- None — every claim above was either verified against live code/registry or cited to official docs in this session.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies; all fixes use already-installed, already-verified library versions
- Architecture: HIGH — every pattern verified against live code in this session, not inferred from the (partially stale) app-review document
- Pitfalls: HIGH — all 5 pitfalls derived from direct code/test inspection, not speculation

**Research date:** 2026-07-07
**Valid until:** 30 days (stable dependency set, no fast-moving APIs; re-verify if `frontend/package.json` versions change before planning executes)
