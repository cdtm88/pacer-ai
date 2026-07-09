---
phase: quick-260709-qw0
plan: 01
subsystem: ci
tags: [ruff, lint, ci, cleanup]

requires: []
provides:
  - "Green ruff lint gate in CI"
affects: [onboarding, tests]

tech-stack:
  added: []
  patterns: []

key-files:
  created: []
  modified:
    - backend/routes/onboarding.py
    - tests/api/test_adaptations.py

key-decisions:
  - "Deleted the import lines outright rather than adding # noqa suppressions -- both names were genuinely dead code orphaned by the Google Calendar removal (a174e47), not intentional unused references"

requirements-completed: [CI-RUFF-CLEAN]

coverage:
  - id: D1
    description: "ruff check . exits 0 with no F401 unused-import errors"
    requirement: "CI-RUFF-CLEAN"
    verification:
      - kind: unit
        ref: "ruff check . -- All checks passed!"
        status: pass
    human_judgment: false
  - id: D2
    description: "onboarding.py no longer imports get_current_user; docstring reference at line ~265 left untouched (prose only)"
    requirement: "CI-RUFF-CLEAN"
    verification:
      - kind: unit
        ref: "grep -n '^from backend.auth import get_current_user' backend/routes/onboarding.py -- no match"
        status: pass
    human_judgment: false
  - id: D3
    description: "test_adaptations.py no longer imports inspect; file still collects and all tests pass"
    requirement: "CI-RUFF-CLEAN"
    verification:
      - kind: unit
        ref: ".venv/bin/python -m pytest tests/api/test_adaptations.py -q -- 21 passed"
        status: pass
    human_judgment: false

duration: 10min
completed: 2026-07-09
status: complete
---

# Quick Task 260709-qw0: Fix ruff unused-import CI failure Summary

**Removed two dead imports (`get_current_user` in `backend/routes/onboarding.py`, `inspect` in `tests/api/test_adaptations.py`) orphaned by the Google Calendar removal commit, restoring a green `ruff check .` CI lint gate.**

## Performance

- **Duration:** ~10 min
- **Tasks:** 3/3 complete
- **Files modified:** 2

## Accomplishments
- Deleted `from backend.auth import get_current_user` at onboarding.py:41 — the route now exclusively uses `rate_limited_user`; the only other occurrence of the name was prose inside a docstring, left untouched.
- Deleted `import inspect` at test_adaptations.py:20 — had no other reference in the file.
- `ruff check .` (run from repo root, config at `./ruff.toml`) now exits 0 with `All checks passed!`.
- `.venv/bin/python -m pytest tests/api/test_adaptations.py -q` — 21 passed, confirming no ImportError from the removed `inspect`.
- Diff limited to exactly the two deleted lines; no other code touched.

## Task Commits

1. **Task 1: Remove unused get_current_user import from onboarding.py** - `a83932d`
2. **Task 2: Remove unused inspect import from test_adaptations.py** - `a83932d`
3. **Task 3: Verify ruff passes and affected tests still import cleanly** - verification only, no code change

## Files Created/Modified
- `backend/routes/onboarding.py` - removed unused `get_current_user` import
- `tests/api/test_adaptations.py` - removed unused `inspect` import

## Decisions Made
- Removed the imports outright instead of suppressing with `# noqa: F401` — both were genuinely dead code, not intentional module-scope references (unlike the adjacent `run_turn` import in the same file, which carries an explicit `noqa` for test-monkeypatching reasons).

## Deviations from Plan
None — plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None.

## Next Phase Readiness
CI lint gate is green. Pre-existing unrelated local changes on this branch (`.env.example`, `.planning/ROADMAP.md`, untracked `.planning/phases/12-athletic-redesign/`) were deliberately left untouched — out of scope for this task.

---
*Quick task: 260709-qw0*
*Completed: 2026-07-09*
