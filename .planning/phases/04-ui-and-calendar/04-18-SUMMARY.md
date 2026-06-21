---
phase: 04-ui-and-calendar
plan: 18
subsystem: frontend/session
tags: [gap-closure, uat, alert-dialog, mark-missed]
dependency_graph:
  requires: [04-15]
  provides: [UAT-GAP-2-closed]
  affects: [frontend/src/components/session/SessionCard.tsx]
tech_stack:
  added: []
  patterns: [shadcn-alert-dialog, controlled-dialog]
key_files:
  created: []
  modified:
    - frontend/src/components/session/SessionCard.tsx
decisions:
  - "Use plain Button (not AlertDialogAction) for confirm to suppress Radix auto-close; dialog stays open on failure for retry"
  - "AlertDialog controlled by existing missedOpen state via open/onOpenChange; no AlertDialogTrigger needed"
metrics:
  duration: "~8 minutes"
  completed: "2026-06-21"
  tasks_completed: 1
  tasks_total: 1
  files_changed: 1
status: complete
---

# Phase 04 Plan 18: Mark Missed AlertDialog Summary

Replace the inline missed-confirmation block in SessionCard with a proper shadcn AlertDialog controlled by the existing missedOpen state, closing UAT GAP 2 (Test 8: "mark missed popup is just broken").

## What Was Built

SessionCard now imports and renders a controlled `AlertDialog` for the Mark Missed confirmation flow. Previously, the confirmation rendered as a state-toggled inline block (missedOpen ternary), which produced no `role=alertdialog` in the DOM. The four primary action buttons (Start session, Export to Zwift, Mark done, Mark missed) now always render. Clicking Mark missed opens the AlertDialog.

The dialog has the exact required copy:
- Title: "Mark this session as missed?"
- Description: "This will trigger a re-plan. Your coach will adjust upcoming sessions."
- Confirm: "Yes, mark missed" (plain Button, destructive style)
- Cancel: "Keep it" (AlertDialogCancel)

The confirm control is a plain `Button` rather than `AlertDialogAction` so Radix's auto-close behavior is suppressed. Closing is owned entirely by `handleMarkMissed`'s success path, keeping the dialog open on failure for retry. This is documented with a one-line comment in the code.

No em dashes appear in the dialog copy.

## Tasks

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Replace inline missed-confirmation with controlled AlertDialog | 9c20b3d | frontend/src/components/session/SessionCard.tsx |

## Verification

- `grep alert-dialog src/components/session/SessionCard.tsx` confirms import
- `grep "Mark this session as missed?" src/components/session/SessionCard.tsx` confirms title
- `tsc --noEmit` passes (no TypeScript errors)
- `npm run build` succeeds (built in 262ms)

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

None - no new network endpoints, auth paths, or schema changes introduced.

## Self-Check: PASSED

- File modified: `frontend/src/components/session/SessionCard.tsx` - FOUND
- Commit `9c20b3d` - FOUND (`feat(04-18): replace inline missed-confirmation with controlled AlertDialog`)
