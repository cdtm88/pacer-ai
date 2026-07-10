---
phase: 13
slug: close-gap-adapt-04-transp-03-wire-weekly-adaptation-check-ad
status: draft
shadcn_initialized: true
preset: "new-york / neutral base / lucide icons (project-wide, pre-existing — components.json)"
created: 2026-07-10
---

# Phase 13 — UI Design Contract

> Visual and interaction contract for the new "Adaptations" section in `ProgressScreen.tsx` (TRANSP-03). ADAPT-04's weekly-check trigger has **no UI** (D-04: fire-and-forget, no loading state, no toast) — it is out of scope for this contract entirely. This document covers only the Adaptations log section.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | shadcn (already initialized project-wide; no init needed) |
| Preset | new-york, neutral base color, lucide icons — existing project preset, unchanged by this phase |
| Component library | Radix primitives via shadcn/ui — **not used in this phase's new markup**. The Adaptations section is plain styled `div`/`p`/`button` matching `ProgressScreen.tsx`'s existing inline-style convention (KPI row, Ride log section), not a shadcn `<Card>`. No new shadcn component is installed or required. |
| Icon library | lucide — **no icon introduced in this phase's new markup** (no icon in the row, empty state, or error state; matches Ride log section, which is also icon-free) |
| Font | Inter (`var(--font-family-sans)`) — inherited from the app root, no override |

---

## Layout & Placement

- Section lives in `frontend/src/screens/ProgressScreen.tsx`, as the **5th and final** top-level block in the centered `max-width: 720px` column, directly after the "Ride log" `<div>` block (D-07: KPIs → PMC chart → weekly load → ride log → adaptation log).
- No new wrapping card / `card-elev`. Matches the Ride log section's own container: a bare `<div>` inside the parent flex column (`gap: 28`), not the KPI row's `card-elev` treatment.
- Section header uses the existing `SectionLabel` component **unchanged** (11px / 600 / uppercase / `letterSpacing: 0.06em` / `var(--color-ink-3)`) with the label text `Adaptations`.
- No pagination, no "show more" — full list rendered (D-10).

---

## Spacing Scale

Declared values (must be multiples of 4) — no new values introduced; this phase reuses exact spacing already present in `ProgressScreen.tsx` / `RideRow.tsx`:

| Token | Value | Usage in this phase |
|-------|-------|----------------------|
| xs | 4px | `SectionLabel` bottom margin (existing, unchanged) |
| sm | 8px | Gap between stacked skeleton rows |
| — | 12px | Per-row vertical padding (`padding: '12px 0'`), matches `RideRow`'s collapsed-row padding exactly |
| — | 24px | Empty/error state `paddingTop`, matches Ride log's own empty state (`paddingTop: 24`) |
| xl | 28px | Gap between this section and the section above it (inherited automatically from the parent flex column's `gap: 28` — no section-level margin needed) |

Exceptions: none. Row border uses `1px solid var(--color-line)` (not a spacing token, a border width — matches `RideRow`'s `borderBottom` exactly).

---

## Typography

Exactly 4 sizes, 2 weights, matching `RideRow.tsx`/`ProgressScreen.tsx` precedent verbatim (no new values invented):

| Role | Size | Weight | Line Height |
|------|------|--------|-------------|
| Row title (humanized `trigger`) | 14px | 600 (semibold) | 1.2 |
| Row body (`explanation_text`) | 13px | 400 (regular) | 1.5 |
| Row meta (formatted `created_at`) | 12px | 400 (regular) | 1.2 |
| Empty / error state sentence | 15px | 400 (regular) | 1.5 |

`SectionLabel` (11px/600, pre-existing, reused unchanged) is not counted as a new size — it is inherited verbatim from the component already in the file.

Weights used: **400 and 600 only** — do not introduce 500 (used elsewhere in `RideRow.tsx` for its date/compliance text, but not needed here; this section's title role maps to 600 to match `SectionLabel`'s weight family, keeping the new section's palette of weights to exactly two).

---

## Color

| Role | Value | Usage |
|------|-------|-------|
| Dominant (60%) | `var(--color-bg)` `#F2F4F7` | Screen background (inherited, unchanged) |
| Secondary (30%) | `var(--color-surface)` `#FFFFFF` (card/list surfaces elsewhere on screen) + `var(--color-line)` `#DFE0E2` (row divider) | Row divider: `border-bottom: 1px solid var(--color-line)`, matching `RideRow` exactly |
| Accent (10%) | `var(--color-brand)` `#1F6FE5` | **Not used anywhere in this phase's new markup.** Reserved project-wide for nav-active state and the Ride log's "View analysis" link — the Adaptations rows have no link/CTA, so introduce zero brand-blue elements here. Do not add a brand-colored element "for visual interest"; if this section ever needs a tap-through in a future phase, that's when accent would apply, not now. |
| Destructive / error | `var(--color-bad)` `#C0341D` | Error-state retry text/button only — identical treatment to the Ride log section's existing error button (same color, same "Tap to retry" pattern) |
| Text — primary | `var(--color-ink)` `#1A2230` | Row title (humanized trigger) |
| Text — secondary | `var(--color-ink-2)` `#5F646E` | Row body (`explanation_text`), empty-state sentence |
| Text — muted | `var(--color-ink-3)` `#888C93` | Row meta (formatted date), `SectionLabel` (unchanged) |
| Skeleton fill | `var(--color-line-2)` `#EDEDEE` | Loading-state `SkeletonRow` (reused component, unchanged) |

No new color tokens are introduced by this phase. `--color-warn` (used elsewhere for compliance <90%) and `--color-good` are **not** used here — this section has no compliance/success semantics, only informational rows.

---

## States (row-level contract for the Adaptations section)

### Loading
- Reuse the existing `SkeletonRow` component **unchanged**.
- Render exactly **2** stacked `SkeletonRow`s (not 3, unlike the Ride log's loading state) — adaptation volume is inherently lower (weekly check at most), so 2 skeleton placeholders reads more honestly than 3.

### Error
- Copy: **"Could not load adaptations. Tap to retry."**
- Styling: identical to the Ride log's existing error button — `<button>` with `background: none`, `border: none`, `cursor: pointer`, `color: var(--color-bad)`, `fontSize: 14px`, `width: 100%`, `textAlign: center`, `padding: 12px`.
- Behavior: `onClick={() => adaptationsQuery.refetch()}` — same pattern as `ridesQuery.refetch()`.

### Empty
- Copy (corrected from CONTEXT.md D-11's draft, which used an em dash — forbidden per CLAUDE.md): **"No adaptations yet. Your plan hasn't needed adjustment."**
- No heading, no icon, no illustration — a single centered `<p>`, matching D-11's "plain sentence" instruction.
- Styling: `fontSize: 15px`, `color: var(--color-ink-2)`, `textAlign: center`, `lineHeight: 1.5`, `paddingTop: 24px`, `margin: 0`.

### Data (populated rows)
- Reverse-chronological (backend already orders `created_at desc` — no client-side sort).
- Each row is a bare `<div>` (not a `<button>` — unlike `RideRow`, these rows are **not** expandable/tappable; there is no drill-down detail view for an adaptation in this phase), with:
  - `borderBottom: '1px solid var(--color-line)'`, `padding: '12px 0'` (matches `RideRow`'s collapsed-row rhythm)
  - Row title: humanized `trigger` value, 14px/600/`var(--color-ink)`
  - Row body: `explanation_text` verbatim (already human-readable per backend `log_adaptation`), 13px/400/`var(--color-ink-2)`, `margin: '2px 0'`
  - Row meta: formatted `created_at`, 12px/400/`var(--color-ink-3)`
- **No `scope` badge** ("micro"/"macro") is added alongside the trigger label — `explanation_text` already names the scope in its own sentence (e.g. "Micro-adjustment triggered by..."), so a second UI element would be redundant. This resolves RESEARCH.md's Open Question 1: skip the scope badge for this phase.
- **No tap-to-expand affordance** — unlike `RideRow`, there is no richer detail to reveal (no power/HR breakdown analog for an adaptation record), so do not copy `RideRow`'s `useState(expanded)` interaction pattern here. Keep it a static row.

### Trigger humanization map (locks RESEARCH.md's recommendation as the contract)

| Raw `trigger` value | Display label |
|---|---|
| `missed` | Missed session |
| `underperformance` | Underperformance |
| `overreaching` | Overreaching |

Implement as a small `Record<string, string>` lookup (matching the existing `ZONE_LABELS` pattern in `lib/format.ts:13-19`), falling back to `titleCase(trigger)` for any unrecognized value (defensive, matches `sessionTypeLabel`'s existing fallback shape) — do not throw or render blank on an unexpected value.

### Date formatting
- Reuse the exact format already used by `RideRow.tsx`'s local `formatDate`: `new Date(iso).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })` (e.g. "Mon, Jul 6"). Whether this is extracted to `lib/format.ts` as a shared export or duplicated locally is an implementation-only decision (per CONTEXT.md's discretion clause) — the **visual output must match RideRow's date format exactly**, no new date format is introduced.

---

## Copywriting Contract

| Element | Copy |
|---------|------|
| Primary CTA | N/A — this phase adds no primary action button. The only interactive element is the error-state retry, which is a recovery action, not a CTA. |
| Section label | "Adaptations" (existing `SectionLabel` styling, unchanged) |
| Empty state heading | None — single sentence only, no heading (per D-11) |
| Empty state body | "No adaptations yet. Your plan hasn't needed adjustment." |
| Error state | "Could not load adaptations. Tap to retry." |
| Destructive confirmation | N/A — no destructive actions in this phase (read-only log view; ADAPT-04's check is silent/fire-and-forget per D-04, not a user-facing action at all) |

All copy uses periods, not em dashes, per CLAUDE.md's "no em dashes in any generated content or copy" constraint — this corrects CONTEXT.md D-11's draft wording, which used an em-dash-style construction.

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|--------------|
| shadcn official | None new — this phase adds zero new shadcn components. Existing project components (`Outlet`, `TooltipProvider`, etc.) are untouched by this UI-SPEC. | not required |
| Third-party | none | not applicable |

No registry vetting gate applies — this phase's entire new-markup surface is plain styled JSX following `RideRow.tsx`/`ProgressScreen.tsx`'s pre-existing inline-style convention, with zero new shadcn/ui or third-party component installs.

---

## Checker Sign-Off

- [ ] Dimension 1 Copywriting: PASS
- [ ] Dimension 2 Visuals: PASS
- [ ] Dimension 3 Color: PASS
- [ ] Dimension 4 Typography: PASS
- [ ] Dimension 5 Spacing: PASS
- [ ] Dimension 6 Registry Safety: PASS

**Approval:** pending
