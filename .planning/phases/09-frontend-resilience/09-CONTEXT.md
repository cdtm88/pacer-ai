# Phase 9: Frontend Resilience - Context

**Gathered:** 2026-07-07
**Status:** Ready for planning

<domain>
## Phase Boundary

The frontend stops silently breaking under real-world conditions — dead chat/SSE streams, stale local storage hijacking the wrong session, cross-account cache bleed, and unhandled render crashes. Scope is bug-fix/resilience work only, no new capabilities.

**Scope was explicitly expanded** beyond ROADMAP.md's condensed 8-item goal line to the full 14 Critical+Major findings in `.planning/research/APP-REVIEW-260703.md` §"Phase 9 — Frontend Resilience" (see D-01). ROADMAP.md's Phase 9 goal text should be updated during/before planning to reflect this.

</domain>

<decisions>
## Implementation Decisions

### Scope
- **D-01:** Full 14-item Critical+Major list from `APP-REVIEW-260703.md` is in scope, not just the 8 items ROADMAP.md's goal line names. The 6 additional items: ZWO export error-shape mismatch, iOS ZWO popup-block, live-resume overshoot, `AppLayout` scroll/pin breakage, cross-account query-cache bleed, upload progress/drag-drop validation.

### SSE / Chat Error Recovery
- **D-02:** On chat SSE stream error: auto-retry silently 1-2 times with backoff; if retries fail, clear `activeStreamUrl`, re-enable input, show an inline error banner with a manual **Retry** button.
- **D-03:** Empty-done-swallow (tool-only turn, `isDone && !content`): clear `activeStreamUrl` and unbrick input silently — render nothing extra. Matches a normal tool-only turn with no visible reply.
- **D-04:** Conversation history on `['active-conversation']` cache miss (5min GC): refetch the existing conversation from the DB instead of creating a new row; show a brief loading state while it loads. (Not a gcTime bump — that doesn't fix the root cause.)
- **D-05:** Onboarding's confirm-stream (server error / early close currently sticks the spinner forever): same recovery pattern as chat — clear stream state, show inline error, manual retry button. Keep the two SSE consumers consistent; share `useSSEStream.ts` if onboarding doesn't already.

### Stale Session Recovery
- **D-06:** `PersistedSession` (`sessionPersistence.ts`) gains `sessionId` + `date` fields. On mismatch vs. today's actual session, silently discard the stale localStorage entry and render Today's real state — no dialog, no toast. The user was never actually mid-session on the correct one.

### Error Boundary
- **D-09:** Fallback UI is minimal: "Something went wrong" message + reload button. No error detail, no report action — single-user personal app, no support pipeline.
- **D-10:** Error boundary is **per-route**, nested inside `AppLayout` — a crash on one screen must not take out the nav shell (bottom tab bar / desktop sidebar); the user can navigate away from the broken screen.

### Claude's Discretion
These are deterministic bug fixes with one obviously-correct behavior — no real UX ambiguity, so not individually discussed:
- **Live-resume overshoot:** make live backgrounding resume match the already-correct reload-path fast-forward behavior (`DuringSessionScreen.tsx`).
- **Cross-account cache bleed:** clear the React Query cache on `SIGNED_IN` / sign-out auth transitions (natural hook point: `AuthGate`/`FirstRunGate`, Phase 4).
- **Ride field mismatch:** align frontend field reads (`duration_seconds`/`avg_power_watts`/`file_name`) to the backend's actual response shape (`duration_secs`/`avg_power`) in `api.ts` vs `rides.py`.
- **ZWO export error shape:** FastAPI wraps `{detail:{error}}`; frontend currently reads `err.error` — fix parsing so the `session_not_found` branch is reachable.
- **iOS ZWO export popup-block:** `window.open(blobUrl)` must fire synchronously inside the click handler, before any `await` — currently called after an `await` in `api.ts`.
- **Auth callback double-exchange:** resolve to a single code-consumption path — either disable `detectSessionInUrl` or drop the redundant manual `exchangeCodeForSession` call (researcher confirms which is correct for the current Supabase client version).
- **Upload query invalidation:** extend success invalidation beyond `['rides']` to also invalidate PMC/session queries.
- **Upload UX:** add progress indication; validate `.fit` extension on drag-drop (currently only validated on file-picker path).
- **AppLayout scroll/pin:** fix `min-h-screen` breaking inner scroll panes so the chat input stays pinned and auto-scroll actually works.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Scope source
- `.planning/research/APP-REVIEW-260703.md` §"Phase 9 — Frontend Resilience" — the full 14-item Critical+Major finding list with file:line references; primary scope document per D-01. Read this, not just ROADMAP.md's condensed goal line.

### Roadmap
- `.planning/ROADMAP.md` §"Phase 9: Frontend Resilience" — original 8-item goal text; needs reconciling with the expanded 14-item scope before/during planning.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `frontend/src/lib/sessionPersistence.ts` — Phase 5's absolute-epoch (`Date.now()`) pattern already proven for iOS backgrounding survival. Extend `PersistedSession` with `sessionId`/`date` in this same file rather than inventing a new mechanism.
- `frontend/src/hooks/useSSEStream.ts` — shared SSE hook already used by `ChatScreen.tsx`. Error/reconnect logic (D-02, D-03) belongs here so onboarding's confirm-stream (D-05) can reuse it instead of duplicating stream-handling logic.

### Established Patterns
- React Query `queryClient.invalidateQueries` — already used for `['rides']` on upload success; extend the same pattern to PMC/session query keys.
- `AuthGate` / `FirstRunGate` (Phase 4) wrap the router — natural location to hook `queryClient.clear()` on `SIGNED_IN`.

### Integration Points
- `ChatScreen.tsx` (SSE error / empty-done / history reload), `useSSEStream.ts` (shared reconnect logic), `OnboardingScreen.tsx` (confirm-stream)
- `sessionPersistence.ts` + `TodayScreen.tsx` + `DuringSessionScreen.tsx` (stale session hijack + live-resume overshoot)
- `router.tsx` + `AppLayout.tsx` (error boundary placement, per-route nesting, scroll/pin fix, cache clear on auth change)
- `api.ts` + `backend/routes/rides.py` (Ride field-name contract, ZWO error-shape, upload invalidation)
- `AuthCallbackScreen.tsx` + `supabase.ts` (auth callback double-exchange)
- `FitUploadZone.tsx` (upload progress, drag-drop validation)

</code_context>

<specifics>
## Specific Ideas

Single-user personal app — error boundary UX is deliberately kept minimal (no error reporting pipeline, no crash analytics). SSE/stream recovery should mirror the already-working Phase 5 pattern (absolute-epoch persistence, consistent recovery UX across chat and onboarding) rather than inventing new mechanisms per screen.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. Scope was explicitly *expanded* (D-01) to the full app-review list rather than narrowed; nothing was pushed out to a future phase.

</deferred>

---

*Phase: 09-frontend-resilience*
*Context gathered: 2026-07-07*
