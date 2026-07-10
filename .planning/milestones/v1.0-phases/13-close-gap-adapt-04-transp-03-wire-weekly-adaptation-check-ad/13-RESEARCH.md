# Phase 13: Close gap: ADAPT-04/TRANSP-03 - Research

**Researched:** 2026-07-10
**Domain:** Frontend integration wiring (React Router mount hook + localStorage throttle + TanStack Query section) for two already-correct backend endpoints. No new backend logic, no new packages.
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Weekly check trigger (ADAPT-04)**
- D-01: Trigger is client-initiated, not a server cron. `AppLayout` (frontend/src/components/AppLayout.tsx) is the root layout mounted once per authenticated session (wraps `<Outlet/>`, doesn't remount on route changes) - fire the check from a `useEffect` there so it covers every entry point.
- D-02: Rationale for client-triggered over Vercel Cron: single-user personal app, a scheduled cron would need a shared-secret auth bypass around `get_current_user` for zero material benefit. Matches original design intent in 03-RESEARCH.md ("checked lazily when the user next opens a conversation"), broadened to "next opens the app."
- D-03: Throttle via `localStorage` timestamp (precedent: `frontend/src/lib/sessionPersistence.ts`). Key suggestion: `pacerai_adaptation_checked_at`, ISO string. On `AppLayout` mount, if `Date.now() - lastChecked >= 7 * 86_400_000` (7 days), fire `POST /adaptations/check` and update the timestamp regardless of whether signals were found.
- D-04: Fire-and-forget: don't block render, don't show a loading state, don't toast on completion. No separate notification UI.
- D-05: On fetch failure (network error, 401, etc.), fail silently - do not retry in a loop, do not update the localStorage timestamp (so it's retried on next mount instead of skipped for a full week).

**Adaptation log UI (TRANSP-03)**
- D-06: Surface lives inside `ProgressScreen.tsx`, not a new nav tab/screen.
- D-07: New "Adaptations" section using the existing `SectionLabel` pattern, placed after the Ride log section (KPIs -> PMC chart -> weekly load -> ride log -> adaptation log).
- D-08: Data fetching follows the exact `useQuery` + `getRides`/`getPmcHistory` pattern already in ProgressScreen - add `getAdaptations` to the same import line, same `useQuery({ queryKey: ['adaptations'], queryFn: getAdaptations })` shape.
- D-09: Row format: reverse-chronological list (backend already orders `created_at desc`), each row shows a humanized adaptation-type-like field, a description-like text as-is, and a formatted `created_at` date (reuse existing date-formatting utility "from `lib/format.ts`, same one used elsewhere for consistency").
  - **RESEARCH FLAG:** This decision's field names (`adaptation_type`, `description`) and the claim that a shared date formatter lives in `lib/format.ts` do not match what exists in the codebase - see `## Contract Mismatch` below. The planner must resolve this before writing tasks; the *intent* of D-09 (humanized type + explanation text + formatted date) is still correct, only the exact field/utility names need substitution.
- D-10: No pagination - show the full list returned by `getAdaptations()`.
- D-11: Empty state: a plain sentence (e.g. "No adaptations yet - your plan hasn't needed adjustment."), not a skeleton or illustration.

### Claude's Discretion
- Exact visual styling of the new Adaptations section - follow ProgressScreen's existing visual language (tokens, colors).
- Whether to extract adaptation-type/trigger humanization into a small helper in `lib/format.ts` or inline - whichever matches how nearby code in the same file already handles similar formatting.
- Whether the throttle check happens in a small extracted hook (e.g. `useAdaptationCheck`) or inline in `AppLayout` - planner's call based on how much logic accumulates.

### Deferred Ideas (OUT OF SCOPE)
- A notifications/toast system for surfacing adaptation results proactively - not on the roadmap.
- Deleting the dead `HistoryScreen.tsx` + its orphaned test - unrelated cleanup, own task.
- Server-side `last_checked_at` persistence (new column/table) instead of localStorage - unnecessary complexity for a single-user app.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ADAPT-04 | A weekly automated check runs independently of upload events to catch accumulating fatigue that no single session triggers | Backend `POST /adaptations/check` (backend/routes/adaptations.py:751-777) fully implemented and unit-tested; this phase adds the only missing piece - a caller. Trigger mechanics confirmed in `## AppLayout Mount Mechanics` below. |
| TRANSP-03 | The adaptation log is readable (not just a raw database table); the user can review past adaptation decisions | Backend `GET /adaptations/` (backend/routes/adaptations.py:728-748) and frontend `getAdaptations()` (frontend/src/lib/api.ts:213-217) fully implemented; this phase adds the UI consumer. Exact response shape (and a contract bug in the existing `Adaptation` TS interface) documented in `## Contract Mismatch` below. |

**Traceability note:** REQUIREMENTS.md's traceability table (line ~199, 203) currently maps ADAPT-04 and TRANSP-03 to "Phase 3 / Complete." That mapping is stale after this gap-closure phase - `.planning/REQUIREMENTS.md` traceability should be updated to note Phase 13 as the phase that made these requirements *genuinely* satisfied (endpoint existed since Phase 3, but per the milestone audit, "Complete" was previously true only for the backend half). ROADMAP.md's Phase 13 Requirements field currently says "TBD" - the planner should set it to `ADAPT-04, TRANSP-03` and flag the REQUIREMENTS.md traceability update as a documentation task in this phase (or note it as a follow-up if out of scope for a wiring-only phase).
</phase_requirements>

## Summary

This is a pure integration-wiring phase: two backend endpoints are correct and tested; nothing calls them. All architectural decisions are locked in CONTEXT.md. The concrete mechanics needed for planning are:

1. **AppLayout mount is single-fire per session** - confirmed by reading `frontend/src/router.tsx`: `AppLayout` is a layout route element (`element: <AppLayout />` with nested `children`), which React Router keeps mounted across all nested-route navigations. It only unmounts on a full page reload or a navigation that leaves its subtree (e.g. to `/login`, `/onboarding`, or `/session`, none of which round-trip back through it without a fresh mount). A `useEffect(() => {...}, [])` in `AppLayout` fires exactly once per authenticated app session, satisfying D-01 without any extra plumbing.
2. **localStorage throttle precedent exists but isn't a generic key-value helper** - `sessionPersistence.ts` uses one dedicated constant key (`SESSION_PERSIST_KEY`) with try/catch-wrapped `localStorage.getItem`/`setItem`, JSON-serializing a typed object. The throttle timestamp is a single raw ISO string (not JSON), so the new code should follow the *safety pattern* (try/catch around every localStorage call) but doesn't need JSON.stringify for a bare string.
3. **`apiFetch` already provides everything needed for a `checkAdaptations()` wrapper** - it is a thin `fetch` wrapper that injects the Supabase JWT; a `POST /adaptations/check` call is a one-line addition following the exact shape of `markSessionMissed`/`createConversation` (POST, empty or no body, throws on `!res.ok`).
4. **A real contract bug exists and must be fixed as part of this phase** - the frontend `Adaptation` TypeScript interface (`api.ts:133-139`: `id`, `session_id`, `adaptation_type`, `description`, `created_at`) does not match the actual `adaptations` table schema or what `GET /adaptations/` (`select("*")`) returns. The real columns are `id`, `user_id`, `trigger`, `signal_count`, `scope`, `before_snapshot`, `after_snapshot`, `explanation_text`, `status`, `trigger_session_ids`, `created_at` - confirmed against `supabase/migrations/0002_phase3_schema.sql` and `0005_phase6_persistence.sql`, and against every `log_adaptation(...)` call site in `backend/routes/adaptations.py`. There is no `session_id` singular column and no `adaptation_type`/`description` columns anywhere in the codebase. This is not a decision to research further - it's a bug the planner must schedule a fix for (correct the TS interface, then build the UI against the corrected fields: humanize `trigger` and/or `scope`, display `explanation_text`, format `created_at`).
5. **No shared date-formatting utility exists in `lib/format.ts`** - contrary to D-09's phrasing, the only existing date formatter (`formatDate` in `frontend/src/components/history/RideRow.tsx:56-66`) is a private, non-exported function local to that component. `lib/format.ts` currently exports `titleCase`, `sessionTypeLabel`, zone re-exports, and `classifyTsb` - no date formatter. The planner has two valid options (both consistent with "Claude's Discretion"): extract `formatDate` into `lib/format.ts` as a shared export (best consistency, small refactor) or write a local inline formatter in the new Adaptations component (matches RideRow's existing precedent of "date formatting lives next to its one usage").
6. **No test file exists for ProgressScreen** - `frontend/src/tests/` has no `progress.test.tsx`. `history.test.tsx` tests the now-superseded `HistoryScreen` (flagged dead code in the milestone audit) using a reusable pattern (`vi.mock('../lib/api')` + `QueryClientProvider` wrapper) that a new `progress.test.tsx` (or an added `describe` block covering the Adaptations section) should copy. This is a Wave 0 gap - see `## Validation Architecture`.
7. **Backend requires zero changes** - `check_adaptations` and `list_adaptations` both already gate on `Depends(get_current_user)`, correctly scope all reads/writes to the JWT's `user_id`, and are already covered by `tests/api/test_adaptations.py`. This phase touches only `frontend/`.

**Primary recommendation:** Implement the throttle check as a small extracted hook (`useAdaptationCheck`, called from `AppLayout`'s body) to keep `AppLayout.tsx` uncluttered and independently testable; fix the `Adaptation` interface in `api.ts` to match the real `adaptations` table schema before building the UI section against it; extract `formatDate` from `RideRow.tsx` into `lib/format.ts` as a shared export (small, low-risk refactor that also removes duplication going forward).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Weekly adaptation check trigger | Browser / Client (React) | API / Backend (endpoint already exists) | D-01/D-02 lock this as a client-initiated lazy check, not a server cron; the client owns *when* to call, the backend owns *what happens* when called |
| Throttle timestamp storage | Browser / Client (localStorage) | - | D-03/D-10 lock this as client-only state; no backend column added |
| Adaptation log rendering | Browser / Client (React, ProgressScreen) | API / Backend (GET /adaptations/) | UI-side rendering of an existing read-only endpoint; no new backend surface |
| Adaptation detection/scoring logic (detect_signals, decide_scope, apply_micro/macro) | API / Backend | - | Already implemented (Phase 3/6); explicitly out of scope for this phase (CONTEXT.md: "No new adaptation logic") |

## Standard Stack

No new libraries. This phase uses only what's already installed and imported elsewhere in the same files:

| Library | Version (installed) | Purpose | Why Standard (already used identically nearby) |
|---------|---------|---------|--------------|
| react (useEffect) | 19.x | Mount-once trigger hook | Already the pattern in `router.tsx`'s `RootProvider` (`useEffect` + `onAuthStateChange`) |
| @tanstack/react-query | 5.x | `useQuery` for the Adaptations section | Already the exact pattern used 3x in `ProgressScreen.tsx` for rides/pmc-history/pmc-latest |
| react-router | 7.x | No change needed - confirms AppLayout mount-once behavior | Existing route tree in `router.tsx` |
| Browser localStorage API | native | Throttle timestamp | Already the mechanism in `sessionPersistence.ts` |

**Installation:** None required - no `npm install` needed for this phase.

## Package Legitimacy Audit

Not applicable - this phase introduces zero new external packages. No install commands are added to any task.

## Architecture Patterns

### System Architecture Diagram

```
App mount (any authenticated route lands in AppLayout)
        |
        v
  AppLayout useEffect (fires once per session)
        |
        v
  useAdaptationCheck() hook
        |
        +-- read localStorage['pacerai_adaptation_checked_at']
        |
        +-- Date.now() - lastChecked >= 7 days? ---- no --> do nothing
        |                                   |
        |                                  yes
        |                                   v
        |                        checkAdaptations() [POST /api/adaptations/check via apiFetch]
        |                                   |
        |                    success -------+------- failure (network/401/etc.)
        |                        |                          |
        |               write new timestamp          leave timestamp unchanged
        |               to localStorage               (silent fail, D-05)
        |               (regardless of signals found)
        v
  (fire-and-forget: no loading UI, no toast, D-04)

--------------------------------------------------------------

User navigates to /progress
        |
        v
  ProgressScreen renders
        |
        +-- existing: KPI row, PmcChart, WeeklyLoadChart, Ride log
        |
        v
  New "Adaptations" section (after Ride log)
        |
        v
  useQuery(['adaptations'], getAdaptations) --> GET /api/adaptations/
        |
        +-- loading: SkeletonRow x N
        +-- error: retry button (matches Ride log error pattern)
        +-- empty: plain sentence (D-11)
        +-- data: reverse-chron list, each row = humanized trigger/scope +
        |          explanation_text + formatted created_at
        v
  (backend already orders created_at desc - no client sort needed)
```

### Recommended Project Structure

No new files strictly required by CONTEXT.md's decisions, but the discretion areas suggest this structure:

```
frontend/src/
├── lib/
│   ├── api.ts                    # ADD: checkAdaptations(); FIX: Adaptation interface fields
│   ├── format.ts                 # ADD (discretion): formatDate export, extracted from RideRow.tsx
│   └── adaptationThrottle.ts     # NEW (optional, discretion): localStorage get/set for throttle key,
│                                  #   mirroring sessionPersistence.ts's try/catch shape
├── hooks/
│   └── useAdaptationCheck.ts     # NEW (discretion): extracted mount-effect hook
├── components/
│   └── AppLayout.tsx             # EDIT: call useAdaptationCheck() (or inline useEffect)
├── screens/
│   └── ProgressScreen.tsx        # EDIT: add getAdaptations import + useQuery + Adaptations section
└── tests/
    └── progress.test.tsx         # NEW: Wave 0 gap - no existing ProgressScreen test file
```

### Pattern 1: Mount-once lazy check via useEffect in a layout route

**What:** A `useEffect(() => { ... }, [])` placed in a component that React Router keeps mounted across nested navigations (a layout route's element, not a leaf route's element).
**When to use:** Any cross-cutting check that should fire once per authenticated session regardless of which screen the user lands on first.
**Example (matches existing pattern already in `router.tsx`'s `RootProvider`):**
```typescript
// Source: frontend/src/router.tsx (existing RootProvider pattern, lines 26-42)
export function RootProvider() {
  useAuth()
  const queryClient = useQueryClient()
  useEffect(() => {
    const { data: { subscription } } = supabase.auth.onAuthStateChange((event) => {
      if (event === 'SIGNED_OUT' || event === 'USER_UPDATED' || event === 'SIGNED_IN') {
        queryClient.clear()
      }
    })
    return () => subscription.unsubscribe()
  }, [queryClient])
  return <Outlet />
}
```
The new `useAdaptationCheck()` in `AppLayout` should follow this same "effect with empty/stable deps, fire-and-forget async work inside, no cleanup needed since it's a one-shot POST" shape (no subscription to unsubscribe, unlike the example above).

### Pattern 2: localStorage safety wrapper (try/catch every call)

**What:** Every localStorage read/write in this codebase is wrapped in try/catch, never left to throw (Safari private mode / quota errors).
**When to use:** Any new localStorage key.
**Example:**
```typescript
// Source: frontend/src/lib/sessionPersistence.ts:29-44 (existing precedent)
export function loadSession(): PersistedSession | null {
  try {
    const raw = localStorage.getItem(SESSION_PERSIST_KEY)
    return raw ? (JSON.parse(raw) as PersistedSession) : null
  } catch {
    return null
  }
}

export function saveSession(s: PersistedSession): void {
  try {
    localStorage.setItem(SESSION_PERSIST_KEY, JSON.stringify(s))
  } catch {
    // QuotaExceededError -- nothing we can do
  }
}
```
For the throttle timestamp (a bare ISO string, not an object), the equivalent is simpler - no `JSON.parse`/`JSON.stringify` needed, just `getItem`/`setItem` wrapped in try/catch.

### Pattern 3: POST wrapper through apiFetch, following createConversation/markSessionMissed shape

**What:** A typed async function that calls `apiFetch`, checks `res.ok`, and either returns parsed JSON or throws.
**When to use:** Any new backend endpoint call.
**Example:**
```typescript
// Source: frontend/src/lib/api.ts:219-232 (createConversation, existing pattern to mirror)
export async function createConversation(title?: string): Promise<Conversation> {
  const res = await apiFetch('/api/conversations/', {
    method: 'POST',
    body: JSON.stringify({ title: title ?? null }),
  })
  if (!res.ok) throw new Error(`createConversation failed: ${res.status}`)
  const data = await res.json() as { conversation_id?: string; id?: string } & Record<string, unknown>
  const id = data.conversation_id ?? data.id
  if (!id) throw new Error('createConversation: backend returned no conversation id')
  return { ...data, id } as unknown as Conversation
}
```
The new `checkAdaptations()` should be simpler still (no body needed - `check_adaptations` takes no request payload, only the JWT):
```typescript
// Recommended shape, following the same file's existing conventions
export interface CheckAdaptationsResponse {
  signals: { type: string; session_id: string; compliance_pct?: number }[]
  scope: 'micro' | 'macro' | null
  result: Record<string, unknown> | null
}

export async function checkAdaptations(): Promise<CheckAdaptationsResponse> {
  const res = await apiFetch('/api/adaptations/check', { method: 'POST' })
  if (!res.ok) throw new Error(`checkAdaptations failed: ${res.status}`)
  return res.json() as Promise<CheckAdaptationsResponse>
}
```
Per D-05, the caller (the throttle hook) must NOT throw this error further up into a render path - it must be caught and swallowed at the call site (fire-and-forget), with the localStorage timestamp only updated on the success path.

### Anti-Patterns to Avoid
- **Do not add a new backend `last_checked_at` column or cron.** Explicitly deferred (CONTEXT.md `## Deferred Ideas`); would duplicate the localStorage mechanism for no benefit on a single-user app.
- **Do not block ProgressScreen or Today render on the adaptation check.** D-04 is explicit: fire-and-forget, no loading state tied to the check itself (the *Adaptations section's own* `useQuery` loading state is separate and expected).
- **Do not build the Adaptations UI against the `Adaptation` interface as currently written in `api.ts`.** It has never been exercised against a live response (no consumer existed until this phase) and does not match the real table schema - see `## Contract Mismatch`.

## Contract Mismatch

**This is the single most important finding for planning this phase correctly.**

The frontend `Adaptation` TypeScript interface (`frontend/src/lib/api.ts:133-139`) is:
```typescript
export interface Adaptation {
  id: string
  session_id: string
  adaptation_type: string
  description: string
  created_at: string
}
```

The actual `adaptations` table (confirmed via `supabase/migrations/0002_phase3_schema.sql:72-82` and `0005_phase6_persistence.sql:65-72`, and cross-checked against every field written by `log_adaptation()` in `backend/routes/adaptations.py:336-373`) has these columns:

| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid | matches interface |
| `user_id` | uuid | not in interface, not needed client-side (RLS-scoped) |
| `trigger` | text | CHECK IN ('missed', 'underperformance', 'overreaching') - closest analog to "adaptation_type" |
| `signal_count` | int | not in interface |
| `scope` | text | CHECK IN ('micro', 'macro') |
| `before_snapshot` | jsonb | not needed for the log UI |
| `after_snapshot` | jsonb | not needed for the log UI |
| `explanation_text` | text | this is the human-readable description - closest analog to "description" |
| `status` | text | 'applied' \| 'proposed' \| 'superseded' (added in migration 0005) |
| `trigger_session_ids` | uuid[] | array, not a single `session_id` |
| `created_at` | timestamptz | matches interface |

`GET /adaptations/` (`list_adaptations`, backend/routes/adaptations.py:728-748) does `select("*")` and returns these rows as-is - **there is no `adaptation_type`, no `description`, and no singular `session_id` field anywhere in the response.** Confirmed via a repo-wide grep: `adaptation_type` appears in exactly one place in the entire codebase (`api.ts:136`), nowhere else - not in any backend file, migration, or test fixture.

**Planner action required:**
1. Add a task to correct the `Adaptation` interface in `api.ts` to match the real schema (at minimum: `id`, `trigger`, `signal_count`, `scope`, `explanation_text`, `status`, `trigger_session_ids`, `created_at`; `user_id`/snapshots can be typed but aren't needed by the UI).
2. Re-read D-09 as: humanize `trigger` (values: "missed" -> "Missed session", "underperformance" -> "Underperformance", "overreaching" -> "Overreaching") - `scope` ("micro"/"macro") could additionally be shown as a small badge alongside it (discretion). Display `explanation_text` in place of "description" (it is already human-readable per the `log_adaptation` docstring - confirmed by reading the `explanation_text` strings actually constructed in `apply_micro_adjustment`/`apply_macro_replan`, e.g. `"Micro-adjustment triggered by missed session {id}. Next N sessions reduced to 80% intensity to ease back in."`). Format `created_at` with a date formatter (see next section).
3. This is a pre-existing bug independent of this phase's scope creep concerns - it was written speculatively in Phase 3 against an endpoint that had zero consumers to catch the mismatch until now. Fixing it is in-scope because TRANSP-03's UI cannot be built correctly without it.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cross-reload throttle timestamp | A new state-management abstraction | Raw `localStorage.getItem`/`setItem` wrapped in try/catch, following `sessionPersistence.ts`'s exact safety pattern | Precedent already exists in this codebase for exactly this problem class |
| Weekly-check scheduling | A client-side setInterval/cron-like poller | Mount-once useEffect (checks age of last-check on each app open, not a background timer) | D-01/D-02 lock this; a running timer would need cleanup logic and doesn't match "checked lazily when the user next opens the app" |
| Adaptation type -> display label mapping | A generic i18n/enum library | A small `Record<string, string>` lookup, exactly like `ZONE_LABELS` already in `lib/format.ts:13-19` | Only 3 possible `trigger` values (DB CHECK constraint enforces this) - a full mapping library is unjustified overhead |

**Key insight:** Every piece of this phase already has a direct precedent somewhere else in the same small codebase. There is no genuinely novel technical problem here - the research risk was entirely in confirming field-name/schema accuracy (found one real bug) and in confirming AppLayout's mount-once behavior (confirmed correct).

## Common Pitfalls

### Pitfall 1: Building the Adaptations UI against the stale `Adaptation` interface
**What goes wrong:** Rendering `adaptation.adaptation_type` and `adaptation.description` silently renders `undefined` for every row (TypeScript won't catch this at compile time if the interface itself is wrong, since the interface and the UI code would agree with each other while both disagree with the actual runtime JSON).
**Why it happens:** The interface was written in Phase 3 against an endpoint with no consumer, so the mismatch was never exercised.
**How to avoid:** Fix the interface first (see `## Contract Mismatch`), then write the UI against the corrected fields. A test that mocks `getAdaptations()` with a realistic fixture (using real column names) and asserts the rendered text will catch this.
**Warning signs:** Rows all show blank/undefined type labels or blank description text when manually tested against a live check-triggered adaptation row.

### Pitfall 2: Placing the throttle-check useEffect on a route/screen component instead of AppLayout
**What goes wrong:** If placed on `TodayScreen` or another leaf route instead of the layout, the check only fires when the user visits that specific screen, not "whenever the app is opened" - directly violating D-01/D-02's rationale ("covers every entry point... not just one screen").
**Why it happens:** Easy to reach for the most familiar/nearby component (e.g. `ChatScreen`, since 03-RESEARCH.md's original design note mentioned chat) instead of the actual mount-once root.
**How to avoid:** Confirmed in this research: `AppLayout` (frontend/src/components/AppLayout.tsx) is the correct location - it is the single layout route wrapping every screen except `/login`, `/onboarding`, and `/session`.
**Warning signs:** A test that navigates directly to `/agenda` (skipping `/`) and observes no check fired would catch this if the hook were misplaced on `TodayScreen`.

### Pitfall 3: Updating the localStorage timestamp on failure
**What goes wrong:** If the timestamp write happens unconditionally (success or failure), a transient network error or expired JWT silently disables the weekly check for a full 7 days - directly undermining ADAPT-04's purpose (catching fatigue that "no single event triggers").
**Why it happens:** Easy to structure the code as "always update timestamp after attempting the check" rather than "update timestamp only in the success branch."
**How to avoid:** D-05 is explicit: on fetch failure (network error, 401, etc.), do not update the timestamp, so the check is retried on the next app open instead of being skipped for a week. Structure the code so the timestamp write is inside the `try` block's success path, not in a `finally`.
**Warning signs:** A test that mocks `checkAdaptations()` to reject and then asserts `localStorage.getItem(...)` was NOT updated.

### Pitfall 4: Assuming a shared date formatter already exists in lib/format.ts
**What goes wrong:** Writing `import { formatDate } from '../lib/format'` will fail to compile - no such export currently exists there (confirmed by reading the full file).
**Why it happens:** D-09's wording implies one exists ("reuse existing date-formatting utility from `lib/format.ts`").
**How to avoid:** Either extract `RideRow.tsx`'s local `formatDate` (lines 56-66) into `lib/format.ts` as a new export (recommended, low-risk, removes a future duplication point) or write a new local formatter scoped to the Adaptations component, matching `RideRow.tsx`'s existing `toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })` shape for visual consistency with the Ride log section directly above it.
**Warning signs:** A build/typecheck failure on the new import.

## Code Examples

### AppLayout.tsx integration point (exact insertion, function-body level)

```typescript
// Source: frontend/src/components/AppLayout.tsx (current file, lines 1-29)
// Existing imports (top of file):
import { Outlet, useNavigate, useLocation } from 'react-router'
import { Settings } from 'lucide-react'
import { TooltipProvider } from '@/components/ui/tooltip'
import { BottomTabBar } from './nav/BottomTabBar'
import { DesktopSidebar } from './nav/DesktopSidebar'
import { IOSInstallBanner } from './pwa/IOSInstallBanner'
// ADD: import { useAdaptationCheck } from '../hooks/useAdaptationCheck' (if extracted)

export function AppLayout() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const title = pathname.startsWith('/rides/') ? 'Analysis' : (ROUTE_TITLES[pathname] ?? 'PacerAI')
  const isToday = pathname === '/'
  const showSettingsGear = pathname !== '/settings'
  // ADD HERE (before the return statement): useAdaptationCheck()
  // This is the exact and only correct insertion point -- AppLayout has no
  // other useEffect currently, and this line runs once per component mount
  // (which is once per authenticated session, per router.tsx's route tree).

  return ( /* ...unchanged JSX... */ )
}
```

### Recommended useAdaptationCheck hook (discretion: extracted vs inline)

```typescript
// New file: frontend/src/hooks/useAdaptationCheck.ts
import { useEffect } from 'react'
import { checkAdaptations } from '../lib/api'

const THROTTLE_KEY = 'pacerai_adaptation_checked_at'
const THROTTLE_MS = 7 * 24 * 60 * 60 * 1000 // 7 days (D-03)

function getLastChecked(): number | null {
  try {
    const raw = localStorage.getItem(THROTTLE_KEY)
    return raw ? new Date(raw).getTime() : null
  } catch {
    return null
  }
}

function setLastChecked(iso: string): void {
  try {
    localStorage.setItem(THROTTLE_KEY, iso)
  } catch {
    // QuotaExceededError -- nothing we can do, mirrors sessionPersistence.ts
  }
}

export function useAdaptationCheck(): void {
  useEffect(() => {
    const lastChecked = getLastChecked()
    const now = Date.now()
    if (lastChecked !== null && now - lastChecked < THROTTLE_MS) return

    // Fire-and-forget (D-04): no loading state, no toast.
    checkAdaptations()
      .then(() => {
        // D-05: only update the timestamp on success, regardless of whether
        // signals were found -- a clean check still counts as "checked."
        setLastChecked(new Date().toISOString())
      })
      .catch(() => {
        // D-05: fail silently, do not update the timestamp, do not retry in
        // a loop -- next mount will retry naturally.
      })
  }, [])
}
```

### Adaptations section in ProgressScreen.tsx (illustrative shape, matching existing Ride log section structure)

```typescript
// Source pattern: frontend/src/screens/ProgressScreen.tsx existing Ride log section (lines 189-269)
// Add to the existing import line (currently: getRides, getPmcHistory, getLatestPmc):
import { getRides, getPmcHistory, getLatestPmc, getAdaptations } from '../lib/api'

// Inside ProgressScreen():
const adaptationsQuery = useQuery({ queryKey: ['adaptations'], queryFn: getAdaptations })
const adaptations = adaptationsQuery.data ?? []

// After the existing "4. Ride log" <div> block, add:
<div>
  <SectionLabel>Adaptations</SectionLabel>
  {adaptationsQuery.isLoading && (<><SkeletonRow /><SkeletonRow /></>)}
  {adaptationsQuery.isError && (
    <button onClick={() => adaptationsQuery.refetch()} /* same style as Ride log's retry button */>
      Could not load adaptations. Tap to retry.
    </button>
  )}
  {!adaptationsQuery.isLoading && !adaptationsQuery.isError && adaptations.length === 0 && (
    <p style={{ fontSize: '15px', color: 'var(--color-ink-2)', textAlign: 'center', paddingTop: 24 }}>
      No adaptations yet -- your plan hasn't needed adjustment.
    </p>
  )}
  {!adaptationsQuery.isLoading && !adaptationsQuery.isError &&
    adaptations.map((a) => (
      <div key={a.id} style={{ borderBottom: '1px solid var(--color-line)', padding: '12px 0' }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-ink)' }}>
          {triggerLabel(a.trigger)} {/* humanized, e.g. "Missed session" */}
        </div>
        <p style={{ fontSize: 13, color: 'var(--color-ink-2)', margin: '2px 0' }}>
          {a.explanation_text}
        </p>
        <span style={{ fontSize: 12, color: 'var(--color-ink-3)' }}>
          {formatDate(a.created_at)}
        </span>
      </div>
    ))}
</div>
```

## State of the Art

Not applicable in the traditional sense (no external library version drift to track) - this section instead documents the internal drift between what CONTEXT.md's decisions assumed existed and what actually exists in the codebase as of this research pass:

| CONTEXT.md assumed | Actual current state | Impact |
|---|---|---|
| `Adaptation` interface fields `adaptation_type`/`description`/`session_id` are correct | Real schema uses `trigger`/`explanation_text`/`trigger_session_ids` (array) | Planner must add a fix-the-interface task before the UI task |
| A shared date-formatting utility exists in `lib/format.ts` | No date formatter exists there; only a private one in `RideRow.tsx` | Planner must add an extract-or-inline decision + task |
| (Implicit) ProgressScreen has existing test coverage to extend | No `progress.test.tsx` exists at all | Wave 0 test-infrastructure gap, see below |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Recommended trigger-humanization label text ("Missed session", "Underperformance", "Overreaching") is a stylistic suggestion, not verified against any existing copy-style guide beyond CLAUDE.md's "no em dashes, warm and professional tone" | Contract Mismatch, Code Examples | Low - purely cosmetic, easy to adjust in review; does not affect functional correctness |
| A2 | Extracting `formatDate` from `RideRow.tsx` into `lib/format.ts` is the better of the two discretion options (vs. inline duplication) | Common Pitfalls, Project Structure | Low - both options are explicitly sanctioned by CONTEXT.md's discretion clause; a reviewer could reasonably choose either |

**All claims about file contents, schema columns, existing patterns, and mount-once behavior in this research were verified by direct file reads and grep in this session - none are `[ASSUMED]` in the sense of unverified training-data guesses.** The two items above are the only genuinely open stylistic choices.

## Open Questions

1. **Should `scope` ("micro"/"macro") be surfaced in the UI alongside the humanized `trigger`?**
   - What we know: D-09 only mentions humanizing "adaptation_type" (now understood to map to `trigger`) and showing `explanation_text` + date.
   - What's unclear: Whether `scope` adds useful signal to the user (e.g. "Micro adjustment" vs "Macro re-plan" as a badge) or is redundant with the `explanation_text` (which already says "Micro-adjustment triggered by..." inline).
   - Recommendation: Skip a separate `scope` badge for v1 of this section - `explanation_text` already names the scope in its own sentence (confirmed by reading the actual strings built in `apply_micro_adjustment`/`apply_macro_replan`), so a second UI element would be redundant. Revisit only if user feedback says otherwise.

2. **Should the REQUIREMENTS.md traceability table be updated in this phase or deferred?**
   - What we know: ROADMAP.md's Phase 13 entry says Requirements "TBD"; REQUIREMENTS.md still shows ADAPT-04/TRANSP-03 mapped to "Phase 3 / Complete."
   - What's unclear: Whether updating REQUIREMENTS.md's traceability table counts as in-scope "wiring" work or is purely a docs follow-up.
   - Recommendation: Include a small doc-update task in this phase's plan (low cost, keeps the audit trail accurate) rather than deferring - the milestone audit specifically flagged this as a documentation gap, and leaving it stale would reproduce the exact blind spot the audit exists to catch.

## Environment Availability

Skipped - this phase has no new external tool/service dependencies. All work happens against already-running Supabase Postgres (existing table, no migration needed) and already-installed npm packages.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework (frontend) | Vitest 4.1.x + React Testing Library (existing, confirmed via `frontend/package.json`) |
| Framework (backend) | pytest + pytest-asyncio, `asyncio_mode = auto` (confirmed via `pytest.ini`) |
| Config file | `frontend/vite.config.ts` (vitest config), `pytest.ini` (testpaths = tests) |
| Quick run command (frontend) | `cd frontend && npx vitest run src/tests/progress.test.tsx` |
| Quick run command (backend) | `python -m pytest tests/api/test_adaptations.py -x` (existing, no changes needed unless a new test is added) |
| Full suite command (frontend) | `cd frontend && npx vitest run` |
| Full suite command (backend) | `python -m pytest` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ADAPT-04 | `useAdaptationCheck` fires `checkAdaptations()` when throttle window elapsed, skips when not | unit | `npx vitest run src/tests/useAdaptationCheck.test.ts` (or `AppLayout.test.tsx` extended) | Neither exists yet - Wave 0 |
| ADAPT-04 | On failure, localStorage timestamp is NOT updated (D-05) | unit | same file as above | Wave 0 |
| ADAPT-04 | AppLayout mounts once per session (not per-route) | unit (already partially covered) | `npx vitest run src/tests/AppLayout.test.tsx` | Exists (height-chain test only) - extend, don't replace |
| TRANSP-03 | Adaptations section renders humanized trigger + explanation_text + formatted date for each row | unit | `npx vitest run src/tests/progress.test.tsx` | Missing entirely - Wave 0 |
| TRANSP-03 | Empty state renders the exact D-11 sentence when `getAdaptations()` returns `[]` | unit | same file as above | Wave 0 |
| TRANSP-03 | `checkAdaptations()`/`getAdaptations()` correctly shaped against real backend response | contract/unit | `python -m pytest tests/api/test_adaptations.py -x` (already exists and passes; no backend change needed, but re-run as a regression check) | Exists |

### Sampling Rate
- **Per task commit:** targeted vitest file for the file just changed (e.g. `npx vitest run src/tests/progress.test.tsx`)
- **Per wave merge:** `cd frontend && npx vitest run` (full frontend suite)
- **Phase gate:** Full frontend suite green + `python -m pytest tests/api/test_adaptations.py` green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `frontend/src/tests/progress.test.tsx` - does not exist; needed to cover the new Adaptations section (empty/loading/error/data states) and, ideally, the existing Ride log section it currently lacks coverage for entirely
- [ ] `frontend/src/tests/useAdaptationCheck.test.ts` (or extend `AppLayout.test.tsx`) - needed to cover throttle timing + silent-failure-does-not-update-timestamp behavior (D-05 is the highest-risk decision in this phase and has zero test coverage today)
- [ ] Shared test fixture for a realistic `Adaptation` object (using the corrected real schema fields) - needed by both new test files to avoid re-deriving the shape ad hoc

### TDD-eligibility per task (workflow.tdd_mode: true)
Per the standard TDD heuristic (business logic / data transforms / API contracts = TDD-eligible; pure UI layout/styling = not):
- **TDD-eligible:** `checkAdaptations()`/corrected `Adaptation` interface (api contract), `useAdaptationCheck` throttle logic (business logic - time math + success/failure branching), trigger-humanization helper function (pure data transform)
- **Not TDD-eligible (glue/UI):** JSX layout of the Adaptations section itself, `SectionLabel`/`SkeletonRow` reuse, exact spacing/styling - these should still get a rendering smoke test, but writing the test first for pure JSX layout provides little value per the project's own heuristic

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | Indirect | No change - `checkAdaptations()` reuses `apiFetch`, which already injects the current Supabase JWT via `Authorization: Bearer` |
| V3 Session Management | No | Not touched - no session/cookie handling changes |
| V4 Access Control | Yes (already enforced, unchanged) | Both endpoints already gate on `Depends(get_current_user)` and scope every DB read/write by `user_id` from the verified JWT (backend/routes/adaptations.py:738, 762). This phase adds no new access-control surface - confirmed no change needed. |
| V5 Input Validation | Minimal | `POST /adaptations/check` takes no request body (no new input surface); `GET /adaptations/` takes no query params |
| V6 Cryptography | No | Not touched |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Cross-user data disclosure via a shared/cached React Query cache after account switch | Information Disclosure | Already mitigated globally - `router.tsx`'s `RootProvider` clears the entire query cache on `SIGNED_OUT`/`USER_UPDATED`/`SIGNED_IN` (lines 32-39), which covers the new `['adaptations']` query key automatically; no additional code needed |
| Stale/replayed localStorage throttle timestamp used to suppress a legitimate check indefinitely | Denial of Service (soft) | D-05's "don't update timestamp on failure" already mitigates the main risk (permanent suppression from one bad network blip); worst case is a false-negative skip for up to 7 days, which is the accepted behavior per D-03, not a security gap |
| Malformed/unexpected `getAdaptations()` response shape causing a render crash | (not STRIDE - a robustness concern raised because the Contract Mismatch finding shows the interface was previously wrong) | Standard defensive coding: the corrected interface should mark fields optional where the DB allows NULL (`before_snapshot`, `after_snapshot`, `signal_count` all nullable/defaulted in the schema), and the UI should use `??`/optional-chaining exactly as the existing Ride log section does for `ride.compliance_pct` |

No new attack surface is introduced by this phase (no new endpoints, no new auth paths, no new input parsing) - the only security-adjacent finding is the pre-existing correct scoping of both endpoints, confirmed unchanged.

## Sources

### Primary (HIGH confidence - direct codebase reads, this session)
- `frontend/src/components/AppLayout.tsx` - full file read, confirmed no existing useEffect, confirmed insertion point
- `frontend/src/router.tsx` - full file read, confirmed AppLayout is a layout route (mount-once) via nested `children` structure
- `frontend/src/lib/sessionPersistence.ts` - full file read, confirmed localStorage safety pattern
- `frontend/src/lib/api.ts` - full file read, confirmed `apiFetch`, `getAdaptations`, `Adaptation` interface, and POST-wrapper conventions (`createConversation`, `markSessionMissed`)
- `backend/routes/adaptations.py` - full file read, confirmed `check_adaptations`/`list_adaptations` implementation, auth, and `log_adaptation` field names
- `supabase/migrations/0002_phase3_schema.sql`, `0005_phase6_persistence.sql` - confirmed real `adaptations` table schema, found the contract mismatch
- `frontend/src/screens/ProgressScreen.tsx` - full file read, confirmed exact section structure, `SectionLabel`/`SkeletonRow` signatures, useQuery pattern
- `frontend/src/lib/format.ts` - full file read, confirmed no date formatter exists there
- `frontend/src/components/history/RideRow.tsx` - full file read, confirmed the only existing (private) date formatter
- `frontend/src/tests/AppLayout.test.tsx`, `frontend/src/tests/history.test.tsx` - confirmed existing test patterns and the ProgressScreen test-coverage gap
- `tests/api/test_adaptations.py` - confirmed existing backend test coverage and conftest fixtures (`mock_supabase_factory`, `auth_headers`, `TEST_JWT_SECRET`, `TEST_USER_ID`)
- `.planning/config.json` - confirmed `workflow.tdd_mode: true`, `workflow.nyquist_validation: true`, `workflow.security_enforcement: true` (ASVS level 1)
- Repo-wide grep for `adaptations/check`, `getAdaptations`, `checkAdaptations`, `adaptation_type`, `pacerai_adaptation` - confirmed zero pre-existing consumers/callers beyond what CONTEXT.md already documented, and confirmed the `adaptation_type` mismatch is isolated to one line in `api.ts`

### Secondary (MEDIUM confidence)
- None - all findings for this phase were directly verifiable against the local repository; no external documentation lookup was needed since this phase uses only already-installed, already-patterned internal code.

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - zero new dependencies, all patterns copied verbatim from existing code in the same repo
- Architecture: HIGH - AppLayout mount-once behavior confirmed by direct read of router.tsx's route tree structure, not inferred
- Pitfalls: HIGH - the two most important pitfalls (contract mismatch, missing date formatter) were discovered via direct file reads and cross-referenced against actual DB migrations, not assumed

**Research date:** 2026-07-10
**Valid until:** No expiry concern - this is a snapshot of the current local codebase state, not a third-party API/library version. Re-verify only if the `adaptations` table schema or `api.ts`'s `Adaptation` interface changes before this phase executes.
