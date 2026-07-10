---
phase: 01-sports-science-foundation
plan: 01
subsystem: testing
tags: [python, pydantic, numpy, scipy, supabase, pytest, ruff]

requires: []
provides:
  - Python 3.12 venv with pinned deps (numpy, scipy, pydantic, supabase, pytest, pytest-asyncio, ruff)
  - Supabase CLI 2.107.0 installed via Homebrew
  - ToolResult pydantic BaseModel (frozen, value/unit/methodology/inputs, to_tool_response)
  - sports_science/constants.py with all physiological constants
  - Full test tree: test_types + test_import_boundary passing; 7 stub test files collecting cleanly
  - pytest.ini, ruff.toml, requirements.txt, .env.example, .gitignore
affects: [01-02, 01-03, 01-04, 01-05]

tech-stack:
  added:
    - numpy==2.4.6
    - scipy==1.17.1
    - pydantic==2.13.4
    - supabase==2.31.0
    - pytest==9.1.1
    - pytest-asyncio==1.4.0
    - ruff==0.15.18
    - supabase CLI 2.107.0
  patterns:
    - ToolResult pydantic BaseModel as universal tool-function return contract (D-01)
    - constants.py as single source of truth for all physiological constants (D-05, D-10)
    - pytestmark skip pattern for stub test files to prevent collection errors
    - TRUST-01 import boundary enforced via grep subprocess test

key-files:
  created:
    - requirements.txt
    - pytest.ini
    - ruff.toml
    - .env.example
    - .gitignore
    - sports_science/__init__.py
    - sports_science/types.py
    - sports_science/constants.py
    - tests/__init__.py
    - tests/sports_science/__init__.py
    - tests/sports_science/conftest.py
    - tests/sports_science/test_types.py
    - tests/sports_science/test_import_boundary.py
    - tests/sports_science/test_zones.py
    - tests/sports_science/test_metrics.py
    - tests/sports_science/test_pmc.py
    - tests/sports_science/test_ftp.py
    - tests/sports_science/test_load.py
    - tests/sports_science/test_compliance.py
    - tests/sports_science/test_capability_gap.py
  modified: []

key-decisions:
  - "ToolResult uses model_config = {'frozen': True} dict syntax (Pydantic v2); ConfigDict fallback not needed"
  - "stub test files use pytestmark = pytest.mark.skip at module level; deferred imports via pytest.importorskip to prevent collection errors"
  - "Supabase CLI 2.107.0 installed via Homebrew (Wave 0 requirement for Wave 2 migration apply)"

patterns-established:
  - "ToolResult: all public tool functions return ToolResult(value, unit, methodology, inputs) -- never raw dict or primitive"
  - "constants: no magic numbers anywhere; always import CTL_TC, ATL_TC, zone boundaries etc from constants.py"
  - "import boundary: sports_science/ must never import anthropic; enforced by test_import_boundary.py in every suite run"

requirements-completed: [TOOL-09]

duration: 4min
completed: 2026-06-19
status: complete
---

# Phase 1 Plan 01: Sports-Science Foundation Setup Summary

**Python 3.12 venv with pinned deps and Supabase CLI; ToolResult pydantic contract; constants module; 17-test collection (6 passing, 15 skipping, 0 errors)**

## Performance

- **Duration:** 4 min
- **Started:** 2026-06-19T13:16:23Z
- **Completed:** 2026-06-19T13:19:43Z
- **Tasks:** 4 (3 auto + 1 checkpoint auto-approved)
- **Files modified:** 21

## Accomplishments

- Python 3.12.10 venv created with all 7 pinned dependencies installed from requirements.txt
- Supabase CLI 2.107.0 installed via Homebrew; required for Wave 2 migration apply
- ToolResult frozen pydantic BaseModel established as the universal return contract for all tool functions (D-01, TOOL-09)
- sports_science/constants.py defines all physiological constants: CTL_TC=42, ATL_TC=7, PMC_MIN_DAYS=28, 7-zone POWER_ZONE_BOUNDARIES, NP/CP thresholds
- 5 test_types.py tests all passing; TRUST-01 import boundary test passing
- 7 stub test files with exact named functions per VALIDATION.md collect cleanly with zero errors (15 skipped)
- Checkpoint auto-approved: pytest suite clean, supabase CLI verified at 2.107.0

## Task Commits

1. **Task 1: Project scaffold, dependency environment, and config files** - `8f9437b` (feat)
2. **Task 2: ToolResult contract and constants module** - `b1ba313` (feat)
3. **Task 3: Stub all remaining test files and shared fixtures** - `088c382` (feat)
4. **Task 4: Checkpoint** - auto-approved (no commit; verification only)

## Files Created/Modified

- `requirements.txt` - 7 pinned deps (numpy, scipy, pydantic, supabase, pytest, pytest-asyncio, ruff)
- `pytest.ini` - asyncio_mode=auto, testpaths=tests
- `ruff.toml` - py312 target, line-length 100, E/F/I rules
- `.env.example` - SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY with backend-only warning
- `.gitignore` - .env, .venv/, __pycache__, *.pyc, .pytest_cache, .ruff_cache, .DS_Store
- `sports_science/__init__.py` - empty (exports added in plan 05 after all modules exist)
- `sports_science/types.py` - ToolResult(BaseModel) frozen with value, unit, methodology, inputs; to_tool_response()
- `sports_science/constants.py` - all physiological constants; single source of truth
- `tests/__init__.py` - empty package init
- `tests/sports_science/__init__.py` - empty package init
- `tests/sports_science/conftest.py` - sample_ftp, flat_power_array, variable_power_array, sample_quality_efforts fixtures
- `tests/sports_science/test_types.py` - 5 passing tests for ToolResult contract
- `tests/sports_science/test_import_boundary.py` - TRUST-01 fully implemented; passes
- `tests/sports_science/test_zones.py` - 3 stub tests (skip)
- `tests/sports_science/test_metrics.py` - 4 stub tests (skip)
- `tests/sports_science/test_pmc.py` - 2 stub tests (skip)
- `tests/sports_science/test_ftp.py` - 2 stub tests (skip)
- `tests/sports_science/test_load.py` - 1 stub test (skip)
- `tests/sports_science/test_compliance.py` - 1 stub test (skip)
- `tests/sports_science/test_capability_gap.py` - 2 stub tests (skip)

## Decisions Made

- Used `model_config = {"frozen": True}` dict syntax for ToolResult (Pydantic v2.13.4 confirmed working; ConfigDict form not needed)
- Stub test files use `pytestmark = pytest.mark.skip` at module level plus `pytest.importorskip` inside test bodies to prevent collection errors from missing modules
- Supabase CLI installed in Wave 0 per Pitfall 5; schema migration (plan 05) can now proceed without workarounds

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

Create a Supabase cloud project at https://supabase.com/dashboard (free tier sufficient for MVP) and copy the following values to a local `.env` file (gitignored):
- `SUPABASE_URL` from Project Settings -> Data API -> Project URL
- `SUPABASE_ANON_KEY` from Project Settings -> API Keys -> anon public
- `SUPABASE_SERVICE_ROLE_KEY` from Project Settings -> API Keys -> service_role (backend only -- never expose to frontend)

The schema migration (plan 05, Wave 2) requires the Supabase project to exist before it can apply migrations.

## Next Phase Readiness

- Plans 02, 03, 04 (Wave 1) can now proceed in parallel: ToolResult and constants are importable; test files with exact function names are in place
- Plan 05 (migration) needs a Supabase project to exist before it can run `supabase db push`
- No blockers for Wave 1

---
*Phase: 01-sports-science-foundation*
*Completed: 2026-06-19*
