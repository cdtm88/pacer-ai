---
phase: 12-athletic-redesign
plan: 03
subsystem: ui
tags: [react, typescript, shadcn, tailwind, design-system]

# Dependency graph
requires:
  - phase: 04-web-ui
    provides: ChatScreen/OnboardingScreen local PromptChip implementations (source of the extraction), shadcn component conventions
provides:
  - Shared frontend/src/components/ui/PromptChip.tsx (named export, visually identical to the two local duplicates it replaces)
  - Shared frontend/src/components/ui/card.tsx (shadcn new-york Card block: Card, CardHeader, CardTitle, CardDescription, CardAction, CardContent, CardFooter)
  - Removal of the dead frontend/src/components/session/SessionStepList.tsx (5th duplicate zone map eliminated)
affects: [12-08-slice-e-screen-wiring]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Shared inline-styled pill components live in components/ui alongside shadcn-generated blocks (PromptChip.tsx pattern)"

key-files:
  created:
    - frontend/src/components/ui/PromptChip.tsx
    - frontend/src/components/ui/card.tsx
  modified: []

key-decisions:
  - "shadcn CLI (npx shadcn add card) wrote card.tsx to a literal ./@/components/ui/card.tsx directory instead of resolving the @ alias to src/components/ui — moved the generated file to the correct path and removed the stray @/ directory rather than hand-writing a replacement, since the CLI output was the correct official template content, just misplaced."

patterns-established:
  - "PromptChip.tsx: pure extraction pattern for byte-identical local components — copy-out first, consumer migration deferred to a later plan (12-08) to keep this plan conflict-free."

requirements-completed: [D-8, D-12]

coverage:
  - id: D1
    description: "Shared PromptChip.tsx extracted from ChatScreen/OnboardingScreen local duplicates, exported for future consumption by both screens"
    requirement: D-8
    verification:
      - kind: unit
        ref: "npx tsc --noEmit (clean)"
        status: pass
    human_judgment: false
  - id: D2
    description: "shadcn card.tsx primitive (Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter, CardAction) added for the Settings redesign"
    requirement: D-12
    verification:
      - kind: unit
        ref: "npx tsc --noEmit (clean); npm test -- --run (140/140 passing)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Dead SessionStepList.tsx deleted with zero dangling references"
    verification:
      - kind: unit
        ref: "grep -rn SessionStepList frontend/src (no matches)"
        status: pass
    human_judgment: false

# Metrics
duration: 6min
completed: 2026-07-09
status: complete
---

# Phase 12 Plan 03: Shared UI Building Blocks (PromptChip + shadcn Card) Summary

**Extracted the byte-identical PromptChip pill component into a shared file, added the shadcn `card.tsx` primitive via the official registry, and deleted the dead SessionStepList duplicate zone map.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-07-09T18:34:01Z
- **Completed:** 2026-07-09T18:38:21Z
- **Tasks:** 2
- **Files modified:** 3 (2 created, 1 deleted)

## Accomplishments
- `frontend/src/components/ui/PromptChip.tsx` created as a named export, matching the exact inline-style treatment from the two local duplicates (padding, radius, border, hover swap, disabled opacity) with zero visual changes
- `frontend/src/components/ui/card.tsx` added via `npx shadcn add card` (official registry, new-york style) — no new npm runtime dependency
- `frontend/src/components/session/SessionStepList.tsx` deleted after confirming zero external render sites via grep — removes a 5th duplicate zone map

## Task Commits

Each task was committed atomically:

1. **Task 1: Extract shared PromptChip and delete dead SessionStepList** - `e4ab322` (feat)
2. **Task 2: Add the shadcn card primitive** - `d11da41` (feat)

_Note: no test-only or refactor commits were needed; both tasks were creation-only._

## Files Created/Modified
- `frontend/src/components/ui/PromptChip.tsx` - Shared pill-button component (label, onClick, disabled) extracted from ChatScreen.tsx/OnboardingScreen.tsx local copies; not yet consumed (consumer migration is 12-08)
- `frontend/src/components/ui/card.tsx` - shadcn new-york Card block (Card, CardHeader, CardTitle, CardDescription, CardAction, CardContent, CardFooter); not yet consumed (Settings redesign is 12-08)
- `frontend/src/components/session/SessionStepList.tsx` - Deleted (dead code, zero render sites, 5th duplicate zone map)

## Decisions Made
- **shadcn CLI path resolution quirk:** `npx shadcn add card` reported writing to `@/components/ui/card.tsx` but actually created a literal `frontend/@/components/ui/card.tsx` directory instead of resolving the `@` alias against `tsconfig.app.json`'s `paths` mapping to `src/`. The generated file content was verified to be the correct, unmodified official shadcn new-york Card template (matches the current shadcn registry, uses only the existing `cn` util, no new Radix/npm dependency). Rather than treating this as a "CLI unavailable" fallback (which the plan permits via hand-writing), the file was moved to `frontend/src/components/ui/card.tsx` and the stray `@/` directory removed, preserving the exact CLI-generated content per the plan's "no restyle" intent.
- No dependencies were installed prior to this plan's execution in this worktree (`node_modules` was absent); ran `npm install` once at the start of Task 1 verification to restore the existing lockfile-pinned dependency tree (no `package.json`/`package-lock.json` diff resulted).

## Deviations from Plan

None — plan executed exactly as written. The shadcn CLI path-resolution quirk above was a mechanical relocation of correctly-generated content, not a deviation from the specified artifact (the plan's own fallback clause anticipated CLI friction and permitted either CLI or hand-written output; the CLI output was used verbatim, just moved to the correct directory).

## Issues Encountered
- `node_modules` was not present in this worktree at start; `npm install` was run once (no lockfile changes) so `npx tsc --noEmit` and `npm test -- --run` could execute. This is routine environment setup, not a code change.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `PromptChip.tsx` and `card.tsx` exist, type-check cleanly, and are ready for consumption by 12-08 (Onboarding/Chat migration to shared PromptChip; Settings redesign using Card)
- `SessionStepList.tsx` removed with no dangling references; `ZoneChip.tsx` confirmed still live (imported by `RideChart.tsx`) and untouched
- Full suite green (140/140 tests); no new npm dependency introduced
- `ChatScreen.tsx` and `OnboardingScreen.tsx` intentionally left unchanged per plan scope; their migration to the shared `PromptChip` import is deferred to 12-08

---
*Phase: 12-athletic-redesign*
*Completed: 2026-07-09*

## Self-Check: PASSED

- FOUND: frontend/src/components/ui/PromptChip.tsx
- FOUND: frontend/src/components/ui/card.tsx
- CONFIRMED DELETED: frontend/src/components/session/SessionStepList.tsx
- FOUND: .planning/phases/12-athletic-redesign/12-03-SUMMARY.md
- FOUND commit: e4ab322 (Task 1)
- FOUND commit: d11da41 (Task 2)
- FOUND commit: 56ca773 (SUMMARY.md)
