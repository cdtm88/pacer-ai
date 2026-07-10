# Phase 13: Close gap: ADAPT-04/TRANSP-03 — wire weekly adaptation check + adaptation log UI - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-10
**Phase:** 13-close-gap-adapt-04-transp-03-wire-weekly-adaptation-check-ad
**Areas discussed:** Weekly check trigger mechanism, Adaptation log UI placement, Log content/format
**Mode:** `--auto` (fully autonomous — no user prompts; Claude selected the recommended option for every question, logged below for audit)

---

## Weekly check trigger mechanism (ADAPT-04)

| Option | Description | Selected |
|--------|-------------|----------|
| Client-triggered lazy check (AppLayout mount, localStorage throttle) | Fire `POST /adaptations/check` from the root layout once per ~7 days, tracked via a localStorage timestamp; no new backend infra | ✓ |
| Vercel Cron (`vercel.json` crons block) | Scheduled serverless invocation; requires a shared-secret auth bypass around `get_current_user` since crons don't carry a user JWT | |
| Check on every chat/onboarding turn | Simplest to wire but runs the detection far more often than "weekly" implies, noisy | |

**Selected:** Client-triggered lazy check.
**Notes:** Matches the original design intent already on record in 03-RESEARCH.md ("checked lazily when the user next opens a conversation"), broadened to "next opens the app" (AppLayout, not just Chat) so it doesn't depend on which screen the user opens first. This is a single-user personal app — a scheduled cron adds auth-bypass complexity for no material benefit over a client-side throttle. On fetch failure, don't update the throttle timestamp so the check retries on the next app open rather than being skipped for a full week.

---

## Adaptation log UI placement (TRANSP-03)

| Option | Description | Selected |
|--------|-------------|----------|
| New section inside ProgressScreen.tsx | Reuse existing `SectionLabel` pattern, placed after the ride log | ✓ |
| New dedicated screen/nav tab | Adds a 5th bottom-tab nav item for a low-frequency log | |
| Modal/panel from Settings or Today | Log becomes a secondary, harder-to-discover surface | |

**Selected:** New section inside ProgressScreen.tsx.
**Notes:** ProgressScreen is documented in its own header comment as "the emotional core: am I getting fitter?" — the adaptation log answers "why did my plan change," which fits that narrative directly. A new nav tab is disproportionate for a log a user checks rarely.

---

## Log content/format

| Option | Description | Selected |
|--------|-------------|----------|
| Full reverse-chronological list, no pagination | Show everything `getAdaptations()` returns; personal-app volume is inherently low | ✓ |
| Paginated / "load more" | Unnecessary complexity for expected volume | |
| Collapsed/expandable rows | Adds interaction complexity not needed for short description text | |

**Selected:** Full reverse-chronological list, no pagination.
**Notes:** Row shows humanized `adaptation_type`, the `description` text as-is (already human-readable per `log_adaptation`), and a formatted `created_at`. Empty state is a plain sentence ("No adaptations yet — your plan hasn't needed adjustment."), matching the app's existing empty-state tone rather than a skeleton or illustration.

---

## Claude's Discretion

- Exact visual styling of the new Adaptations section — follow ProgressScreen's existing visual language (tokens, colors, spacing) rather than inventing new patterns.
- Whether to extract adaptation-type humanization into a `lib/format.ts` helper or inline it.
- Whether the throttle check lives in a small extracted hook (e.g. `useAdaptationCheck`) or inline in `AppLayout`.

## Deferred Ideas

- A notifications/toast system for proactively surfacing adaptation results (e.g. "Your plan changed" banner) — new capability, not on the roadmap, not needed since TRANSP-01/02 (chat) and the new log (this phase) already surface results.
- Deleting the dead `HistoryScreen.tsx` + its orphaned test (noted as tech debt in the milestone audit) — unrelated to this phase's two gaps, belongs in its own cleanup task.
- Server-side `last_checked_at` persistence instead of localStorage — more robust across devices but unnecessary complexity for a single-user personal app.
