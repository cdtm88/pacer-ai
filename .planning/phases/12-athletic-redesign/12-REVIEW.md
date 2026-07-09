---
phase: 12-athletic-redesign
reviewed: 2026-07-09T00:00:00Z
depth: standard
files_reviewed: 27
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
  - frontend/src/lib/api.ts
findings:
  critical: 0
  warning: 6
  info: 3
  total: 9
status: issues_found
---

# Phase 12: Code Review Report

**Reviewed:** 2026-07-09
**Depth:** standard
**Files Reviewed:** 27 (+ frontend/src/lib/api.ts hand-fix)
**Status:** issues_found

## Summary

Reviewed all 27 files from Phase 12 "Athletic Redesign" (dark cockpit during-session view, Today hub redesign, component-token unification, zone-map consolidation, Settings redesign) plus the orchestrator's post-merge hand-fix to `api.ts`. I cross-referenced each file's diff against `b869212c9e0fdcc85d45a4d62d0fe12b655d1f27^..HEAD` to isolate what this phase actually changed, rather than re-litigating pre-existing code.

Overall the merge is clean: the zone-map consolidation (`lib/zones.ts`) is genuinely singular (no orphaned duplicate zone maps left in `AgendaScreen`, `TodayScreen`, `DuringSessionScreen`, or `ZoneChip`, all confirmed via diff and grep), `PromptChip` was correctly extracted with both call sites (`ChatScreen`, `OnboardingScreen`) migrated and their local duplicates deleted, the `--color-cockpit-*` dark tokens are scoped to `DuringSessionScreen` only (grep-confirmed, no leakage), no pure-black value appears anywhere including the new cockpit tokens (`#14171D`/`#1D2129`/`#2A2F3A`), and the frozen persistence boundary in `DuringSessionScreen.tsx` (state, effects, `saveSession`/`fastForwardSteps`/`computeRestoredState`) is untouched — the diff confirms only the render layer changed plus one correctly-threaded new prop (`rpe_target`).

That said, I found six real defects introduced by this phase's changes (visual overflow bug, a hidden-but-still-keyboard-focusable interactive region, a lost heading-semantics regression, two em-dash copy violations against the project's explicit "no em dashes" rule, and an incomplete API type contract) plus three minor informational items. None rise to Critical (no crash, security, or data-loss risk), but several are real user-facing regressions that should be fixed before this ships.

## Warnings

### WR-01: Compliance bar can overflow its container up to 50% past the edge

**File:** `frontend/src/components/history/RideRow.tsx:264-274`
**Issue:** The new "Actual" bar (replacing the old planned-vs-actual table, per the diff) sets `width: \`${Math.min(150, ride.compliance_pct)}%\`` with no `overflow: hidden` anywhere in its ancestor chain (the row `<div>`, the expanded-detail `<div>`, and the bar's own parent `<div>` are all unclipped). For any ride where `compliance_pct` exceeds 100 (riding harder/longer than planned — a realistic outcome, not an edge case), the bar renders wider than its container and bleeds past the row's right edge. There is no test covering `compliance_pct > 100` (`history.test.tsx` only exercises `null` and unset cases), so this shipped untested.
**Fix:**
```tsx
<div style={{ height: '8px', borderRadius: '4px', overflow: 'hidden', backgroundColor: 'var(--color-line-2)' }}>
  <div
    style={{
      height: '100%',
      borderRadius: '4px',
      width: `${Math.min(100, ride.compliance_pct)}%`, // cap the fill itself at 100%
      backgroundColor: ride.compliance_pct >= 90 ? 'var(--color-good)' : 'var(--color-warn)',
    }}
  />
</div>
```
If showing over-100% compliance visually is intentional (e.g. an "overshoot" indicator), clip the outer track with `overflow: hidden` at minimum so the bar never draws outside the row.

### WR-02: "Log without riding" actions stay keyboard-focusable while visually hidden

**File:** `frontend/src/components/session/SessionCard.tsx:303-334`
**Issue:** The collapsed state of `#log-without-riding-actions` is implemented with `maxHeight: 0, overflow: 'hidden', opacity: 0, pointerEvents: 'none'`. This correctly blocks mouse/touch interaction and hides the content visually, but none of those properties remove the "Mark done" / "Mark missed" buttons from the tab order or the accessibility tree (only `display: none`, `visibility: hidden`, `hidden`, or `tabIndex={-1}`/`inert` do that). A keyboard-only user tabbing through the card will land on two invisible, zero-height buttons and can still activate them with Enter/Space — `pointer-events: none` has no effect on keyboard activation. The code comment ("stay mounted... so their accessible names remain queryable for the test suite regardless of expanded state") shows this was a deliberate trade-off for test convenience, but it leaves a real keyboard-accessibility regression.
**Fix:** Gate keyboard reachability off the same `logExpanded` state, independent of the test-query requirement (tests can still query by role/name on unmounted-but-present elements via `{ hidden: true }` or by expanding the disclosure first):
```tsx
<div
  id="log-without-riding-actions"
  className="flex gap-2"
  inert={!logExpanded ? true : undefined}
  style={logExpanded ? { marginTop: 8 } : { maxHeight: 0, overflow: 'hidden', opacity: 0, marginTop: 0 }}
>
```
(`inert` is supported in all evergreen browsers as of 2023 and removes both focus and pointer interaction while keeping the subtree in the DOM.) Alternatively add `tabIndex={-1}` to both buttons and toggle it with `logExpanded`.

### WR-03: Settings section headers lost heading semantics

**File:** `frontend/src/screens/SettingsScreen.tsx:68-146` (via `frontend/src/components/ui/card.tsx:31-39`)
**Issue:** The diff replaced `<h2 className="text-sm font-semibold uppercase ...">Training</h2>` (and the same for "Profile" and "Account") with shadcn's `<CardTitle>`. `CardTitle` renders a plain `<div data-slot="card-title">`, not a heading element. This removes all three section headings from the page's heading outline — screen-reader users navigating by heading (a primary AT navigation pattern) can no longer jump directly to "Training" / "Profile" / "Account" on the Settings screen. This is a straight regression versus the pre-redesign markup, not a pre-existing issue.
**Fix:** Either add `asChild` with a heading tag if shadcn's Card API in this project supports it, or wrap: `<CardTitle asChild><h2 className="...">Training</h2></CardTitle>`, or simplest — keep `<h2>` for the visible text and drop `CardTitle` for these three call sites:
```tsx
<CardHeader>
  <h2 className="text-sm font-semibold uppercase tracking-wide" style={{ color: 'var(--color-ink-2)' }}>
    Training
  </h2>
</CardHeader>
```

### WR-04: Em dash in user-facing copy violates the project's "no em dashes" constraint

**File:** `frontend/src/components/session/ZwoExportModal.tsx:58`
**Issue:** `'FTP: not yet estimated — free-ride format'` contains a literal em dash (U+2014) in rendered UI copy. CLAUDE.md states explicitly: "No em dashes: In any generated content or copy — use commas, semicolons, colons, or separate sentences." This is real prose copy shown to the user (not a placeholder glyph), so it's a direct violation, not a borderline case.
**Fix:**
```tsx
{ftp != null ? `FTP used: ${ftp}W` : 'FTP: not yet estimated. Free-ride format applies.'}
```
Note `zwo-modal.test.tsx:152` asserts the current em-dash string verbatim and will need updating alongside this fix.

### WR-05: Em dash placeholder glyphs in SessionCard stat tiles

**File:** `frontend/src/components/session/SessionCard.tsx:187, 190, 191`
**Issue:** `'—'` (em dash) is used three times as the "no value" placeholder for Duration / TSS / IF stat tiles. This is a weaker case than WR-04 (it's a glyph convention, not prose), but it's still an em dash character rendered in the UI and the project constraint doesn't carve out an exception for placeholder use.
**Fix:** Use a different missing-value convention, e.g. `'--'` (double hyphen, matching the existing convention already used elsewhere in this same phase's `RideRow.tsx` — `formatDuration` returns `'--'` for null) or `'N/A'`, for consistency both with the copy rule and with the rest of the codebase.

### WR-06: `Session` API type still doesn't match what screens actually consume

**File:** `frontend/src/lib/api.ts:71-83`
**Issue:** The orchestrator's hand-fix added `rpe_target` to the `Session` interface, but the interface is still missing `objective`, `duration_mins`, and `tss_target` — all of which are read from `Session[]` results at runtime via `as unknown as SessionRow[]` (`AgendaScreen.tsx:167`) and `as unknown as Parameters<typeof SessionCard>[0]['session']` (`TodayScreen.tsx:208-209`). Because these are `as unknown as` casts (not `as SomeInterface`), TypeScript provides zero structural checking on the way through — if the backend ever renames or drops one of these fields, nothing in the type system will catch it; only a runtime `undefined` shows up in the UI ("—"/blank values with no compile-time warning). The `rpe_target` patch shows the team is aware these gaps exist but is fixing them reactively one field at a time rather than making `Session` the actual source of truth.
**Fix:** Either extend `Session` in `api.ts` to include the fields the frontend actually consumes (`objective: string | null`, `duration_mins: number | null`, `tss_target: number | null`), or introduce a single shared `SessionDTO` type used by `SessionCard`, `AgendaScreen`, and `api.ts` instead of three independently-hand-maintained subset interfaces (`SessionData`, `SessionRow`, `Session`) plus unchecked casts between them.

## Info

### IN-01: Zone-dot validation silently removed in TodayScreen's upcoming-sessions strip

**File:** `frontend/src/screens/TodayScreen.tsx:145, 226` (was previously gated by `isValidZone`, per diff)
**Issue:** The diff dropped the local `isValidZone`/`ZONE_VAR` lookup in favor of calling `zoneColor()` directly, which is a fine consolidation — but it also changes behavior subtly: previously an unrecognized `type` string meant no dot was rendered at all (`zoneType` was `null`); now any non-null `type` string renders a dot, falling back to the neutral `var(--color-ink-3)` color for unrecognized zones via `zoneColor()`'s internal fallback. Likely harmless (and arguably better — always showing *something*), but worth confirming this was an intentional design call rather than an oversight of the consolidation.
**Fix:** No action required if intentional; otherwise reintroduce an explicit `isValidZone` guard before rendering the dot.

### IN-02: Malformed-looking `var()` fallback predates this phase but sits in a file this phase touched

**File:** `frontend/src/screens/SettingsScreen.tsx:180`
**Issue:** `color: 'var(--color-ink-3, var(--color-ink-2))'` — syntactically valid CSS custom-property fallback, but since `--color-ink-3` is always defined in `index.css`'s `@theme` block, the fallback can never trigger and reads as leftover defensive code or a copy-paste artifact. Not introduced by this phase's diff (unchanged line), noted only because the file was substantially reworked around it.
**Fix:** Simplify to `color: 'var(--color-ink-2)'` for clarity, or drop if intentional documentation of a fallback pattern.

### IN-03: `RideRow.formatDate` has no timezone anchor (pre-existing)

**File:** `frontend/src/components/history/RideRow.tsx:56-66`
**Issue:** `formatDate` calls `new Date(isoDate)` directly on a date-only string, unlike the rest of the phase's screens (`AgendaScreen`, `TodayScreen`) which consistently anchor with `+ 'T12:00:00'` to avoid UTC-midnight timezone rollback. If `ride_date` is a bare `YYYY-MM-DD` string, `new Date()` parses it as UTC midnight, and `.toLocaleDateString()` in a timezone behind UTC (e.g. US timezones) can display the wrong day. Not touched by this phase's diff, flagged only for awareness since the pattern is inconsistent within the same component family this phase reworked.
**Fix:** Match the `+ 'T12:00:00'` convention used elsewhere: `new Date(isoDate + 'T12:00:00')`.

---

_Reviewed: 2026-07-09_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
