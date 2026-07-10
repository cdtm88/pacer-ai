# UI Review — Phase 05: During-Session and ZWO Export

**Audited:** 2026-06-21
**Baseline:** `05-UI-SPEC.md` (approved)
**Overall Score:** 15/24

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 2/4 | Session complete overlay uses wrong heading and wrong stat copy; countdown warning not implemented |
| 2. Visuals | 2/4 | Timer is 96px not 40px (spec Display slot); ZWO export is inline panel not Dialog modal |
| 3. Color | 3/4 | `--color-warn` never applied; "Back to today" button uses `--color-ink` fill instead of `--color-blue-6` |
| 4. Typography | 2/4 | Timer at 96px and session-complete time at 56px exceed declared 40px Display slot; `font-semibold` (600) used but spec only declares 400/700 |
| 5. Spacing | 3/4 | Off-scale values: 28px side padding (spec 24px), 20px step counter mb, 14px timer mb |
| 6. Experience Design | 3/4 | Loading and error states present; countdown warning interaction contract not met |

---

## Top 3 Priority Fixes

1. **BLOCKER — Session complete overlay is entirely wrong** — Users see "Complete" (small badge) + "{N} steps finished" instead of "Session complete" (40px/700 heading) + "{N} steps completed". CTA "Back to today" uses dark `--color-ink` fill instead of `--color-blue-6`. Fix: replace the complete overlay structure per spec. `DuringSessionScreen.tsx:243-268`

2. **BLOCKER — Countdown warning not implemented** — Spec contract requires "Starting [step name] in 3..." at `secondsLeft <= 3`, shown at `--color-warn` replacing the sublabel. Actual: `nearEnd` triggers at `secondsLeft <= 5`, copy is "Up next in Xs", color is zone color, size is 11px. Fix: change threshold to `<= 3`, copy to `Starting {nextStep.label} in {secondsLeft}...`, color to `var(--color-warn)`, size to 14px regular. `DuringSessionScreen.tsx:278, 369-374`

3. **WARNING — Timer and type sizes violate the 40px Display slot** — Timer is `fontSize: 96` and session-complete elapsed time is `fontSize: 56`. Spec declares the Display slot at 40px/700 for both. These are uncontracted deviations that need explicit approval or correction. `DuringSessionScreen.tsx:338, 246`

---

## Detailed Findings

### Pillar 1: Copywriting (2/4)

**BLOCKER — Session complete heading wrong**
- Spec: `Session complete` (40px, weight 700, `--color-ink`)
- Actual: `Complete` rendered as a small uppercase badge (13px, `--color-zone-recovery` green, letter-spaced)
- `DuringSessionScreen.tsx:243-244`

**BLOCKER — Session complete stat label wrong**
- Spec: `{N} steps completed`
- Actual: `{steps.length} steps finished`
- `DuringSessionScreen.tsx:250`

**BLOCKER — Countdown warning copy not implemented**
- Spec: `Starting [step name] in 3...` / `in 2...` / `in 1...` at `--color-warn`
- Actual: `Up next in {N}s` with zone color
- `DuringSessionScreen.tsx:373`

**WARNING — ZWO modal session name separator**
- Spec: `{Session type} — {YYYY-MM-DD}` (em-dash per spec). CLAUDE.md bans em-dashes project-wide. The implementation uses a plain hyphen. Conflict requires resolution: update spec to use hyphen, or clarify em-dash ban applies only to prose, not code-generated strings.
- `ZwoExportModal.tsx:55`

**WARNING — ZWO FTP line wrong for no-FTP case**
- Spec: `FTP used: 100W (assumed — no estimate yet)`
- Actual: `FTP: not yet estimated — free-ride format` (wrong label, wrong message, contains em-dash)
- `ZwoExportModal.tsx:58`

**WARNING — ZWO step list separators**
- Spec: `Warmup — {N} min` etc. (em-dash). Actual uses plain hyphens. Same conflict as session name separator above.
- `ZwoExportModal.tsx:67-69`

**PASS — CTAs match spec**
- `Skip step`, `Back to today`, `Download .zwo`, `Close`, `Never mind`, `Start session`, `Ride anyway`, `How long will you ride?`, preset labels, `End session` — all correct.

---

### Pillar 2: Visuals (2/4)

**BLOCKER — ZWO export is an inline panel, not a Dialog modal**
- Spec: "Modal fetches session metadata... shadcn Dialog modal"
- Actual: `ZwoExportModal.tsx` renders a plain `<div>` inline in `SessionCard`. When `zwoOpen` is true, the panel appends below the action buttons in the same document flow — no dialog/portal.
- `SessionCard.tsx:254-261`

**WARNING — Session complete overlay uses wrong background token**
- Spec: `--color-bg-2` (#F6F6F7) for session complete background
- Actual: `--color-surface` (#FFFFFF) used on both active session screen and complete overlay
- `DuringSessionScreen.tsx:238, 285`

**WARNING — Timer hierarchy inversion**
- Spec: "Primary focal point: current step label (40px bold)... timer is the secondary focal point, positioned below."
- Actual: Step name is 18px/500 but timer at 96px dominates visually. Hierarchy is functionally inverted from the stated spec priority.
- `DuringSessionScreen.tsx:325-347`

**INFO — Zone badge not in spec**
- An unstyled zone badge renders between the step counter and step name. Additive — does not break any stated contract.

---

### Pillar 3: Color (3/4)

**WARNING — `--color-warn` never applied**
- Spec defines `--color-warn` (#9A6700) for countdown warning text. Countdown warning is not implemented, so this token has zero usage. Actual nearEnd label uses `zoneColor` instead.
- `DuringSessionScreen.tsx:369`

**WARNING — "Back to today" button uses `--color-ink` not `--color-blue-6`**
- Spec: accent `--color-blue-6` for primary action buttons
- Actual: `backgroundColor: 'var(--color-ink)'` (dark)
- `DuringSessionScreen.tsx:254-259`

**WARNING — `--color-ink-3` used at label sizes**
- `--color-ink-3` (#888C93) is declared "large muted text only — not body or label sizes." Used at 12px on step counter and as "Next" label color. Both are below the contrast threshold for this token on white.
- `DuringSessionScreen.tsx:304, 369`

**PASS — Zone color hex values match spec**
- Hardcoded hex values in `SessionCard.tsx:15-19` are identical to spec-defined values. Single source of truth is broken but not a contract violation.

---

### Pillar 4: Typography (2/4)

**BLOCKER — Timer font size 96px not in type scale**
- Spec declares Display slot at 40px. Timer at `fontSize: 96` is 2.4x the declared maximum. No type size above 40px exists in the spec.
- `DuringSessionScreen.tsx:338`

**WARNING — Session complete elapsed time at 56px not declared**
- Spec: session complete heading uses the 40px Display slot. Actual: time value is 56px.
- `DuringSessionScreen.tsx:246`

**WARNING — `font-semibold` (600) used; spec only declares 400/700**
- DurationPickerModal title, SessionCard objective, and ZwoExportModal title all use weight 600. Systematic deviation across Phase 5 components.
- `DurationPickerModal.tsx:99`

**WARNING — Session complete heading (40px/700) absent entirely**
- The text "Session complete" is never rendered at 40px/700 — replaced by the "Complete" badge. The Display slot is fully missing.

---

### Pillar 5: Spacing (3/4)

**WARNING — Side padding 28px vs spec 24px (`px-6`)**
- `paddingLeft: 28, paddingRight: 28` — off-scale by 4px.
- `DuringSessionScreen.tsx:299-300`

**WARNING — Step counter margin-bottom 20px off-scale**
- `marginBottom: 20` — 8-point scale is 4/8/16/24/32/48.
- `DuringSessionScreen.tsx:305`

**WARNING — Timer margin-bottom 14px off-scale**
- `marginBottom: 14` on timer block — not in the declared scale.
- `DuringSessionScreen.tsx:348`

**PASS — Modal spacing on-scale**
- DurationPickerModal: 24px container padding, 16px gaps, 8px preset gap — all on-scale.

---

### Pillar 6: Experience Design (3/4)

**BLOCKER — Countdown warning interaction contract not met**
- UI-SPEC requires 3-second warning at `elapsed >= stepDuration - 3`. Actual: `nearEnd = secondsLeft <= 5` (5-second trigger), wrong copy, wrong color.
- `DuringSessionScreen.tsx:278, 369-374`

**WARNING — Duration picker inline error requires blur first**
- Inline error only shows on blur or submit. Out-of-range values typed mid-field are not flagged until focus leaves. Minor — blur behavior is acceptable but not explicitly contracted.
- `DurationPickerModal.tsx:64-68`

**PASS — Error states present**
- ZWO: toast on failure, modal stays open for retry
- Loading state: spinner on DuringSessionScreen data load
- Empty state: "No session steps available" shown when steps array is empty

**PASS — Touch target minimums met**
- Skip step: `minHeight: 48` (exceeds 44px HIG min)
- End session: `minHeight: 44` (meets HIG min)

**PASS — End session has no confirmation (correct per spec)**
- Spec explicitly: "No confirmation dialog. Tapping immediately navigates to `/`." Correctly implemented.

---

## Files Audited

- `frontend/src/screens/DuringSessionScreen.tsx`
- `frontend/src/screens/TodayScreen.tsx`
- `frontend/src/components/session/ZwoExportModal.tsx`
- `frontend/src/components/session/SessionCard.tsx`
- `frontend/src/components/session/DurationPickerModal.tsx`
- `.planning/phases/05-during-session-and-zwo-export/05-UI-SPEC.md`
- `.planning/phases/05-during-session-and-zwo-export/05-CONTEXT.md`
