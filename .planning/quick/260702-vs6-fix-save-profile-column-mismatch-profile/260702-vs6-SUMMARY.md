---
phase: quick-260702-vs6
plan: 01
subsystem: database
tags: [supabase, postgres, profiles, save_profile]

requires: []
provides:
  - "save_profile upserts the real 'goals' column instead of the nonexistent 'fitness_goals' column"
affects: [onboarding, profiles]

tech-stack:
  added: []
  patterns: []

key-files:
  created: []
  modified:
    - backend/sports_science/profile.py

key-decisions:
  - "Renamed only the upsert dict key, not the function parameter (fitness_goals stays the Python API name) or the LLM tool-argument name in agent/tools.py — those are correct and unrelated to the DB column mismatch"

patterns-established: []

requirements-completed: [QUICK-260702-vs6]

coverage:
  - id: D1
    description: "save_profile's Supabase upsert sends key 'goals' (real column), never 'fitness_goals'"
    requirement: "QUICK-260702-vs6"
    verification:
      - kind: unit
        ref: "grep -c '\"goals\":' profile.py == 1; grep -c '\"fitness_goals\":' profile.py == 0"
        status: pass
    human_judgment: false
  - id: D2
    description: "Existing save_profile tests (test_tools_phase3.py, test_onboarding.py) pass unchanged"
    requirement: "QUICK-260702-vs6"
    verification:
      - kind: unit
        ref: "tests/agent/test_tools_phase3.py, tests/api/test_onboarding.py (12 passed)"
        status: pass
    human_judgment: false
  - id: D3
    description: "A real onboarding confirmation actually persists a profile row to public.profiles in production"
    requirement: "QUICK-260702-vs6"
    verification: []
    human_judgment: true
    rationale: "Not re-verified via a completed onboarding conversation from within this task — that requires multi-turn LLM interaction plus a second bug fix (trust scanner, quick task 260702-vsp) that was fixed in parallel. Confirmed separately via the ongoing Playwright E2E test session."

duration: 10min
completed: 2026-07-02
status: complete
---

# Quick Task 260702-vs6: Fix save_profile column mismatch Summary

**Renamed the save_profile upsert dict key from the nonexistent `fitness_goals` column to the real `goals` (jsonb) column — fixes a PGRST204 error that was rejecting every onboarding profile save in production.**

## Performance

- **Duration:** ~10 min
- **Tasks:** 2/2 complete
- **Files modified:** 1

## Accomplishments
- `backend/sports_science/profile.py:92`: `"fitness_goals": fitness_goals,` -> `"goals": fitness_goals,`
- Confirmed via grep this was the only site using the wrong key; `backend/agent/tools.py`'s LLM-facing tool-argument name `fitness_goals` and the function parameter of the same name are correct and untouched.
- 12 existing tests across `tests/agent/test_tools_phase3.py` and `tests/api/test_onboarding.py` pass unchanged — none had asserted the buggy DB key.
- Committed and pushed to `origin/main` (`b619864`), auto-deploying the Vercel Python function.

## Task Commits

1. **Task 1: Rename dict key + run tests** - included in `b619864`
2. **Task 2: Commit + push** - `b619864` (fix)

## Files Created/Modified
- `backend/sports_science/profile.py` - one-line dict key rename

## Decisions Made
- Left the function parameter name (`fitness_goals: str`) and the LLM tool-argument name in `agent/tools.py` unchanged — only the Supabase-facing dict key was wrong.

## Deviations from Plan
None — plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None.

## Next Phase Readiness
- Combined with the trust-scanner fix (260702-vsp, executed in the same session), the onboarding confirmation flow should now be able to complete end-to-end. Full live confirmation happens via the ongoing Playwright E2E test.

---
*Quick task: 260702-vs6*
*Completed: 2026-07-02*
</content>
