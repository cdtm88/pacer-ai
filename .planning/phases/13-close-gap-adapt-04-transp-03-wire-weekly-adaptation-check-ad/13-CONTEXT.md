# Phase 13: Close gap: ADAPT-04/TRANSP-03 — wire weekly adaptation check + adaptation log UI - Context

**Gathered:** 2026-07-10
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase closes two integration gaps surfaced by the v1.0 milestone audit (`.planning/v1.0-MILESTONE-AUDIT.md`, status `gaps_found`). Both requirements have correct, tested backend implementations but no consumer:

- **ADAPT-04** — `POST /adaptations/check` (backend/routes/adaptations.py:751) runs `detect_signals -> decide_scope -> apply_micro_adjustment/apply_macro_replan` correctly but is never called by anything: no cron, no scheduler, no frontend caller, no lazy in-conversation hook.
- **TRANSP-03** — `getAdaptations()` (frontend/src/lib/api.ts:213) calls `GET /api/adaptations/` correctly but no screen or component ever calls it, so a user has no way to review past adaptation decisions.

This phase wires both: (1) a trigger that actually invokes the weekly check, (2) a UI surface that actually renders the adaptation log. TRANSP-01/02 (reasoning surfaced inline in chat) are already correctly wired and out of scope here — don't touch them.

No new capabilities, no new adaptation logic — this is pure integration wiring for already-built, already-tested backend behavior.

</domain>

<decisions>
## Implementation Decisions

### Weekly check trigger (ADAPT-04)
- **D-01:** Trigger is client-initiated, not a server cron. `AppLayout` (frontend/src/components/AppLayout.tsx) is the root layout mounted once per authenticated session (it wraps `<Outlet/>`, doesn't remount on route changes) — fire the check from a `useEffect` there so it covers every entry point (Today, Chat, Agenda, wherever the user lands first), not just one screen.
- **D-02:** Rationale for client-triggered over Vercel Cron: this is a single-user personal app, not a multi-tenant service — a scheduled cron would need a shared-secret auth bypass around `get_current_user` (which reads the JWT) for zero material benefit. This also matches the original design intent already on record in 03-RESEARCH.md ("checked lazily when the user next opens a conversation") — broadened here to "next opens the app" so it doesn't depend on the user specifically visiting Chat.
- **D-03:** Throttle via `localStorage` timestamp (precedent: `frontend/src/lib/sessionPersistence.ts` already uses localStorage for cross-reload state). Key suggestion: `pacerai_adaptation_checked_at`, ISO string. On `AppLayout` mount, if `Date.now() - lastChecked >= 7 * 86_400_000` (7 days), fire `POST /adaptations/check` and update the timestamp regardless of whether signals were found (a clean check still counts as "checked").
- **D-04:** Fire-and-forget: don't block render, don't show a loading state, don't toast on completion. If the check produces a micro/macro adaptation, that surfaces to the user next time they open Chat (TRANSP-01/02, already correct) or when they view the new adaptation log (TRANSP-03, this phase). No separate notification UI — avoids scope creep into a notifications system that isn't on the roadmap.
- **D-05:** On fetch failure (network error, 401, etc.), fail silently — do not retry in a loop, do not update the localStorage timestamp (so it's retried on next mount instead of being skipped for a full week).

### Adaptation log UI (TRANSP-03)
- **D-06:** Surface lives inside `ProgressScreen.tsx`, not a new nav tab/screen. ProgressScreen is documented in its own header comment as "the emotional core: am I getting fitter?" — a log of why the plan changed fits that narrative directly, and adding a 5th bottom-tab nav item for a low-frequency log is disproportionate.
- **D-07:** New "Adaptations" section using the existing `SectionLabel` pattern already defined in ProgressScreen.tsx, placed after the Ride log section (most recent/relevant content stays higher: KPIs → PMC chart → weekly load → ride log → adaptation log).
- **D-08:** Data fetching follows the exact `useQuery` + `getRides`/`getPmcHistory` pattern already in ProgressScreen — add `getAdaptations` to the same import line, same `useQuery({ queryKey: ['adaptations'], queryFn: getAdaptations })` shape.
- **D-09:** Row format: reverse-chronological list (backend already orders `created_at desc`), each row shows a humanized `adaptation_type` (e.g. "micro_adjustment" → "Micro adjustment"), the `description` text as-is (already human-readable per `log_adaptation`), and a formatted `created_at` date (reuse existing date-formatting utility from `lib/format.ts`, same one used elsewhere for consistency).
- **D-10:** No pagination — personal single-user app, adaptation volume is inherently low (weekly check at most). Show the full list returned by `getAdaptations()`.
- **D-11:** Empty state: a plain sentence, matching the tone of other empty states in the app (e.g. "No adaptations yet — your plan hasn't needed adjustment."), not a skeleton or illustration.

### Claude's Discretion
- Exact visual styling of the new Adaptations section (spacing, row component structure) — follow ProgressScreen's existing visual language (tokens, colors) rather than inventing new patterns.
- Whether to extract adaptation-type humanization into a small helper in `lib/format.ts` or inline — whichever matches how nearby code in the same file already handles similar formatting.
- Whether the throttle check happens in a small extracted hook (e.g. `useAdaptationCheck`) or inline in `AppLayout` — planner's call based on how much logic accumulates.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Gap evidence and audit
- `.planning/v1.0-MILESTONE-AUDIT.md` — the audit that surfaced ADAPT-04 and TRANSP-03 as unwired; contains full evidence trail (grep results, file:line references) for both gaps.

### Backend (already implemented, do not modify logic)
- `backend/routes/adaptations.py:117` — `detect_signals` (signal detection over a 7-day window)
- `backend/routes/adaptations.py:242` — `decide_scope` (micro vs macro decision)
- `backend/routes/adaptations.py:336` — `log_adaptation` (writes the row this phase's UI will read)
- `backend/routes/adaptations.py:728` — `GET /` `list_adaptations` (TRANSP-03 backend, already correct)
- `backend/routes/adaptations.py:751` — `POST /check` `check_adaptations` (ADAPT-04 backend, already correct — this phase adds the caller, not new logic)
- `backend/agent/tools.py:479` — comment referencing `detect_signals`, context for why it's only referenced there and nowhere invoked

### Frontend (integration points)
- `frontend/src/lib/api.ts:213` — `getAdaptations()` (already correct, unused until this phase)
- `frontend/src/lib/api.ts:133` — `Adaptation` interface (`id`, `session_id`, `adaptation_type`, `description`, `created_at`)
- `frontend/src/components/AppLayout.tsx` — root layout, mount point for the lazy weekly-check trigger
- `frontend/src/screens/ProgressScreen.tsx` — target screen for the new Adaptations section; read its full header comment and existing section structure before adding

### Prior-phase precedent
- `frontend/src/lib/sessionPersistence.ts` — existing localStorage-based cross-reload state precedent, mirror this pattern for the check-throttle timestamp rather than inventing a new one

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `SectionLabel` component (defined locally in ProgressScreen.tsx) — reuse directly for the new "Adaptations" section header, matches existing visual rhythm.
- `getAdaptations()` (frontend/src/lib/api.ts:213) — already implemented, just needs a caller.
- `apiFetch` (frontend/src/lib/api.ts:12) — existing authenticated fetch wrapper; `POST /adaptations/check` should go through the same helper, no bespoke fetch logic needed.

### Established Patterns
- ProgressScreen already composes multiple `useQuery`-backed sections (PMC chart, weekly load chart, ride log) in one screen — the Adaptations section should follow the exact same shape (loading skeleton via existing `SkeletonRow`, data-driven list, empty state).
- localStorage is the established mechanism for cross-reload client state (`sessionPersistence.ts` for in-progress session resume) — reuse this mechanism for the check-throttle timestamp instead of adding new backend state (e.g. a `last_checked_at` column) since the check itself is idempotent and stateless from the backend's perspective.

### Integration Points
- `AppLayout.tsx` wraps every authenticated route via `<Outlet/>` and mounts once per session — this is the single integration point for the lazy trigger, no per-screen duplication needed.
- `ProgressScreen.tsx`'s existing import line for `getRides, getPmcHistory, getLatestPmc` is where `getAdaptations` gets added.

</code_context>

<specifics>
## Specific Ideas

No specific visual mockups or exact wording were requested beyond the empty-state tone note above (D-11) — standard approach, consistent with the rest of the app's existing patterns (ProgressScreen sections, SectionLabel, RideRow-style list rows).

</specifics>

<deferred>
## Deferred Ideas

- A notifications/toast system for surfacing adaptation results proactively (e.g. "Your plan changed" banner) — not on the roadmap, would be new capability beyond wiring the existing log/check. Adaptation results already surface via TRANSP-01/02 in chat and via the new log (this phase).
- Deleting the dead `HistoryScreen.tsx` + its orphaned test (noted in the milestone audit as tech debt) — unrelated to ADAPT-04/TRANSP-03, belongs in its own cleanup task, not this phase.
- Server-side `last_checked_at` persistence (e.g. a new column/table) instead of localStorage — would be more robust across devices/browsers but is unnecessary complexity for a single-user personal app; localStorage precedent already exists and is sufficient.

### Reviewed Todos (not folded)
None — `.planning/STATE.md` reports no pending todos at this time.

</deferred>

---

*Phase: 13-close-gap-adapt-04-transp-03-wire-weekly-adaptation-check-ad*
*Context gathered: 2026-07-10*
