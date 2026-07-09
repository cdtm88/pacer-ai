---
phase: 12-athletic-redesign
plan: 08
subsystem: frontend-ui
tags: [settings, zonechip, promptchip, component-unification, tokens]
dependency-graph:
  requires: [12-01, 12-02, 12-03]
  provides: [settings-card-redesign, zonechip-on-lib-zones, onboarding-chat-shared-promptchip]
  affects: [frontend/src/screens/SettingsScreen.tsx, frontend/src/components/session/ZoneChip.tsx, frontend/src/screens/OnboardingScreen.tsx, frontend/src/screens/ChatScreen.tsx]
tech-stack:
  added: []
  patterns:
    - "shadcn Card/CardHeader/CardTitle/CardContent for grouped settings sections"
    - "Button variant=link / variant=destructive replacing hand-rolled buttons"
    - "Single lib/zones map as the only source of zone color/label metadata"
key-files:
  created:
    - frontend/src/tests/SettingsScreen.test.tsx
  modified:
    - frontend/src/screens/SettingsScreen.tsx
    - frontend/src/components/session/ZoneChip.tsx
    - frontend/src/tests/rideChart.test.tsx
    - frontend/src/screens/OnboardingScreen.tsx
    - frontend/src/screens/ChatScreen.tsx
decisions:
  - "Re-send magic link uses Button variant=link (relies on the text-primary token = var(--color-brand) via index.css from 12-01), not an inline color override -- consistent with the rest of the token-driven Button system."
  - "ZoneChip keeps 'export type ZoneType = ZoneKey' as a pure alias so RideChart.tsx's existing import needs zero changes."
metrics:
  duration: ~25min
  completed: 2026-07-09
status: complete
---

# Phase 12 Plan 08: Secondary Surfaces (Settings, ZoneChip, PromptChip) Summary

Redesigned SettingsScreen into card-grouped sections with real `<Button>` variants and on-token colors (closing out the last off-token colors from Foundation Fixes), migrated ZoneChip onto the single `lib/zones` map while preserving RideChart's `ZoneType` import, and moved Onboarding/Chat onto the shared `PromptChip` component, deleting both duplicated local copies.

## What Was Built

**Task 1 — Settings card redesign + smoke test (D-12, D-8):**
- `SettingsScreen.tsx`'s three `<section>` blocks (Training, Profile, Account) are now `<Card><CardHeader><CardTitle>...</CardTitle></CardHeader><CardContent>...</CardContent></Card>`; the two manual 1px divider `<div>`s are gone (card boundaries replace them).
- "Re-send magic link" is now `<Button variant="link">` (was a plain `<button>` styled with the undefined `var(--color-accent)` token, which silently fell back to inherited ink color).
- "Sign out" is now `<Button variant="destructive">` (was a plain `<button>` with a hardcoded `var(--color-destructive, #dc2626)` fallback; the token now resolves correctly via the `index.css` additions from 12-01, so the fallback is dropped entirely).
- Auth logic (`supabase.auth.getSession()`, `signOut()`, resend-magic-link handler) is unchanged — only surrounding markup and button elements changed.
- New `frontend/src/tests/SettingsScreen.test.tsx`: first automated coverage for this screen. Mocks `@/lib/api` (getProfileMe), `@/lib/supabase` (getSession/signOut/signInWithOtp), and `sonner`; asserts the screen renders without throwing and exposes a `/sign out/i` button.

**Task 2 — ZoneChip migration to lib/zones + coupled rideChart test update (D-8):**
- `ZoneChip.tsx` no longer defines local `ZONE_VAR`/`ZONE_LABEL` maps. It imports `zoneColor`, `zoneLabel`, and `type ZoneKey` from `@/lib/zones`, and re-exports `export type ZoneType = ZoneKey` so `RideChart.tsx`'s existing `import { ZoneChip, type ZoneType }` keeps compiling with zero changes to `RideChart.tsx`.
- The badge JSX/color-mix visual treatment is unchanged (15% background tint + zone-color text).
- This unifies the vo2 label from `'VO2max'` to the canonical `'VO2 Max'` (since `RideChart` renders `<ZoneChip zone={zone} />` with no label override). `rideChart.test.tsx`'s dependent assertion was updated in the same commit (`getByText('VO2max')` → `getByText('VO2 Max')`); the mock `hr_zone_distribution` `name` field ('VO2max') was left as-is per plan, since the assertion targets the rendered `ZoneChip` label, not `row.name`.

**Task 3 — Migrate Onboarding + Chat to the shared PromptChip (D-8):**
- Deleted the byte-identical local `PromptChip` function definitions from both `OnboardingScreen.tsx` and `ChatScreen.tsx`; both now `import { PromptChip } from '@/components/ui/PromptChip'`.
- All existing `<PromptChip>` call sites (same `label`/`onClick`/`disabled` props) are unchanged — the shared component is byte-identical, so no visual or behavioral change.
- The `useState` import was kept in both files (still used elsewhere for unrelated state), consistent with the plan's "verify it is not used elsewhere before removing" guidance.

## Verification

- `cd frontend && npx vitest run src/tests/SettingsScreen.test.tsx src/tests/rideChart.test.tsx` — 2 files, 6 tests passed.
- `cd frontend && npx tsc --noEmit` — clean, no errors.
- `cd frontend && npm test -- --run` — full suite green: 19 files, 148 tests passed.

## Deviations from Plan

None — plan executed exactly as written.

**Environment note (not a plan deviation):** this worktree had no `node_modules` installed. Since `frontend/package-lock.json` in this worktree is byte-identical (md5-matched) to the main repo's lockfile, a symlink to the main repo's `frontend/node_modules` was created locally to run `vitest`/`tsc` without a slow reinstall. `node_modules` is gitignored and this symlink is not part of any commit.

## Known Stubs

None.

## Threat Flags

None — this plan only touches presentation-layer markup/imports; no new endpoints, auth paths, or trust boundaries. Matches the plan's `<threat_model>` disposition (both T-12-08 and T-12-08b are `accept`, low severity, no auth-flow change).

## Self-Check: PASSED

- FOUND: frontend/src/tests/SettingsScreen.test.tsx
- FOUND: frontend/src/screens/SettingsScreen.tsx (Card/Button usage confirmed via grep)
- FOUND: frontend/src/components/session/ZoneChip.tsx (imports @/lib/zones, ZoneType = ZoneKey confirmed)
- FOUND: frontend/src/tests/rideChart.test.tsx (VO2 Max assertion confirmed)
- FOUND: frontend/src/screens/OnboardingScreen.tsx (no local PromptChip, imports @/components/ui/PromptChip)
- FOUND: frontend/src/screens/ChatScreen.tsx (no local PromptChip, imports @/components/ui/PromptChip)
- FOUND commit 95caf65 (Task 1)
- FOUND commit 8a53915 (Task 2)
- FOUND commit cee4693 (Task 3)
