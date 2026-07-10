# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — MVP

**Shipped:** 2026-07-10
**Phases:** 13 | **Plans:** 94 | **Sessions:** several (multi-session build across 21 days)

### What Was Built
- Trust-anchored sports-science tool library (power/HR zones, TSS/NP/IF, PMC, passive FTP via critical-power modelling) with a runtime trust scanner structurally preventing the LLM from emitting physiological numbers.
- Conversational onboarding → structured periodised plan generation, with first-class cold-start support (no FTP required) and back-protective constraints.
- Full FIT-upload → PMC/TSS → compliance → adaptive re-planning loop, with in-chat transparency citing data and principle for every plan change.
- Web PWA (onboarding, Today, Agenda, Progress, Chat, Settings), an iOS-safe during-session stepper with wake lock, and a server-side ZWO exporter — both Zwift-acceptance-tested.
- Ride Analysis Dashboard and a full athletic visual redesign (Zwift/Strava-register cockpit UI, unified tokens/zone-color system).
- Closed a milestone-audit-surfaced integration gap (ADAPT-04/TRANSP-03): backend-correct-but-uncalled endpoints since Phase 3 finally got real user-reachable callers in Phase 13.

### What Worked
- **Milestone-level integration auditing caught what phase-level verification missed.** Phase 3's VERIFICATION.md marked ADAPT-04/TRANSP-03 "SATISFIED" on endpoint existence + unit test alone. It took a dedicated cross-phase integration checker at the *milestone* level (not phase level) to discover neither had a real caller. This is the specific value milestone auditing adds over phase verification — a lesson worth repeating for any future milestone.
- **Re-verifying VERIFICATION.md claims against live source, not trusting the report, caught real bugs.** Multiple phases (11, 12, 13) had their own verifier independently grep the actual codebase for claimed fixes rather than trusting SUMMARY.md prose — this caught things like the Phase 13 contract-mismatch bug and confirmed all 4 code-review fixes actually landed, not just claimed.
- **Standard code review (not just gap-closure mode) found a genuine Critical bug in Phase 13**: a concurrency race in the new adaptation-check hook that unit tests alone hadn't caught. Running code review on every phase, not just when explicitly requested, paid for itself here.
- **Gap-closure phases (03-06, 08-08, 12-09, 13) consistently found and fixed real, live-reproduced defects** rather than rubber-stamping — the pattern of "re-verify against live source + real UAT, don't just re-read the plan" held across the whole milestone.
- **Wave-based parallel execution with worktree isolation** scaled cleanly even for a 4-plan, 2-wave phase (13) with cross-plan dependencies (Wave 2 both depending on Wave 1's contract fix) — the dependency-aware wave split avoided any merge conflict.

### What Was Inefficient
- **Two early-phase gap-closure rounds (03-06, 08-08) fixed defects that better phase-level integration checking might have caught the first time** — collision-prone date scheduling and an onboarding LTHR attribution gap were both live-reproduced bugs, not obscure edge cases.
- **REQUIREMENTS.md traceability drifted from reality for ~7 phases** (ADAPT-04/TRANSP-03 marked Phase 3/Complete despite having no real caller until Phase 13) before the milestone audit caught it — a smaller, more frequent integration check (even a lightweight one at every 2-3 phases) might have surfaced this sooner and cheaper than waiting for the full milestone-close audit.
- **The auto-generated MILESTONES.md entry from `milestone.complete` dumped all 94 raw per-plan one-liners verbatim** (including junk fragments like "DB migration" and "api/routes/adaptations.py") instead of a curated summary — required manual cleanup at milestone close. A future improvement: the CLI's accomplishment extraction should filter for substantive one-liners (or the workflow should curate before writing, not after).

### Patterns Established
- **Milestone completion re-audits before archiving, not just before shipping.** When the pre-close audit was found stale (predating the most recent gap-closure phase), re-running `/gsd-audit-milestone` fresh — rather than trusting a same-day-but-pre-fix audit file — is now the expected move whenever a phase closes between the last audit and milestone completion.
- **"Backend-correct + unit-tested" is explicitly NOT the same claim as "user-reachable."** This distinction, learned the hard way with ADAPT-04/TRANSP-03, should be an explicit phase-verification checklist item going forward: for every new endpoint/hook, name its real caller, not just its test.

### Key Lessons
1. Cross-phase / milestone-level integration checking is not redundant with phase-level verification — it catches an entirely different failure class (unreachable-but-tested code) that phase verification structurally cannot see.
2. When a milestone audit exists but a gap-closure phase has landed since it was written, treat the audit as stale and re-run it before completing the milestone — don't rely on a same-day timestamp as a freshness proxy.
3. Auto-generated summary artifacts (MILESTONES.md accomplishments) need a curation pass before being treated as the final record; raw per-plan extraction is noisy at 90+ plan scale.

### Cost Observations
- Model mix: opus for planning (higher-stakes task decomposition), sonnet for research/execution/verification/review (the bulk of the work).
- Sessions: multiple across 21 days, spanning the full app-review-driven hardening arc (Phases 6-10) plus feature phases (11-13).
- Notable: gap-closure phases were consistently cheap relative to the defects they fixed — each closed a genuine, live-reproduced bug in 1-2 plans rather than a full replan.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.0 | multiple | 13 | Established milestone-level integration auditing as a distinct, necessary gate beyond phase-level verification |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|---------------------|
| v1.0 | 166 frontend + 359 backend = 525 | Not formally measured (no coverage tool configured) | 0 — Phase 13's concurrency guard, cache invalidation, and format helpers were all hand-rolled against existing patterns rather than pulling in a new dependency |

### Top Lessons (Verified Across Milestones)

1. "Passes its own unit test" and "is reachable by a real user" are different claims — verify both, at different altitudes (phase vs. milestone).
