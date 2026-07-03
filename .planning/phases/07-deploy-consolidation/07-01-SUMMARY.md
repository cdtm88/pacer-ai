---
phase: 07-deploy-consolidation
plan: 01
subsystem: infra
tags: [vercel, railway, docker, deploy-docs, requirements-txt]

# Dependency graph
requires:
  - phase: 06-core-loop-persistence
    provides: stable app state prior to deploy-target consolidation
provides:
  - Repository with no Railway/Docker deploy artifacts
  - requirements.txt without gunicorn (uvicorn retained for local dev)
  - README.md documenting Vercel as the sole deploy target with a corrected, complete backend env-var table
  - .claude/CLAUDE.md with Railway references removed/corrected
affects: [07-02-deploy-consolidation, 07-03-deploy-consolidation, 07-04-deploy-consolidation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Vercel Python runtime invokes the ASGI app object directly; no Docker/Gunicorn/process-manager layer"

key-files:
  created: []
  modified:
    - Dockerfile (deleted)
    - railway.toml (deleted)
    - requirements.txt
    - README.md
    - .claude/CLAUDE.md

key-decisions:
  - "Keep uvicorn in requirements.txt for local dev per RESEARCH.md Open Question 3; remove only gunicorn (Railway/Docker-only)"
  - "README backend deploy section describes the architecture model-agnostically (entrypoint api/index.py, static frontend, routing in root vercel.json) without hard-coding 'services', since plan 07-04 decides the exact vercel.json routing mechanism"

requirements-completed: [DEPLOY-RAIL-01, DEPLOY-DOC-01]

coverage:
  - id: D1
    description: "Dockerfile and railway.toml deleted from the repository"
    requirement: "DEPLOY-RAIL-01"
    verification:
      - kind: unit
        ref: "test ! -e Dockerfile && test ! -e railway.toml"
        status: pass
    human_judgment: false
  - id: D2
    description: "requirements.txt no longer lists gunicorn; uvicorn retained for local dev"
    requirement: "DEPLOY-RAIL-01"
    verification:
      - kind: unit
        ref: "grep -c '^gunicorn' requirements.txt returns 0; grep -c '^uvicorn' requirements.txt returns 1"
        status: pass
    human_judgment: false
  - id: D3
    description: "README documents Vercel as the sole deploy target with a corrected, complete backend env-var table (SUPABASE_SERVICE_ROLE_KEY, SUPABASE_JWT_SECRET, CALENDAR_FERNET_KEY, BACKEND_BASE_URL, ANTHROPIC_MODEL added; PORT removed; no Backend: Railway heading)"
    requirement: "DEPLOY-DOC-01"
    verification:
      - kind: unit
        ref: "grep checks in 07-01-PLAN.md Task 2 <verify> block"
        status: pass
    human_judgment: false
  - id: D4
    description: "README API endpoint list shows GET /chat/stream (not POST)"
    requirement: "DEPLOY-DOC-01"
    verification:
      - kind: unit
        ref: "grep -q 'GET /chat/stream' README.md"
        status: pass
    human_judgment: false
  - id: D5
    description: ".claude/CLAUDE.md describes Vercel-only deployment (no Railway or Gunicorn as active targets)"
    requirement: "DEPLOY-DOC-01"
    verification:
      - kind: unit
        ref: "! grep -qi 'railway' .claude/CLAUDE.md"
        status: pass
    human_judgment: false

# Metrics
duration: 12min
completed: 2026-07-03
status: complete
---

# Phase 7 Plan 01: Remove Railway artifacts and correct deploy docs Summary

**Deleted Dockerfile/railway.toml, dropped gunicorn from requirements.txt, and rewrote README.md + .claude/CLAUDE.md to describe Vercel as the sole deploy target with a corrected, complete backend env-var table.**

## Performance

- **Duration:** 12 min
- **Tasks:** 3 completed
- **Files modified:** 5 (2 deleted, 3 edited)

## Accomplishments
- Removed Railway/Docker deploy artifacts (`Dockerfile`, `railway.toml`) and the `gunicorn` dependency, keeping `uvicorn` for local dev
- Rewrote README's deployment section, API endpoint list (`GET /chat/stream`), and backend env-var table (fixed `SUPABASE_SERVICE_KEY` → `SUPABASE_SERVICE_ROLE_KEY`, dropped `PORT`, added the four previously-undocumented vars: `SUPABASE_JWT_SECRET`, `CALENDAR_FERNET_KEY`, `BACKEND_BASE_URL`, `ANTHROPIC_MODEL`)
- Corrected all 5 stale Railway references in `.claude/CLAUDE.md` (Tech Stack constraint, Uvicorn rationale row, Dev/Deploy table, PostgreSQL row, Confidence Notes row)

## Task Commits

Each task was committed atomically:

1. **Task 1: Delete Railway/Docker artifacts and remove gunicorn dependency** - `2787c86` (chore)
2. **Task 2: Rewrite README deploy, env-var, and endpoint sections for Vercel-only** - `1a68bea` (docs)
3. **Task 3: Correct Railway references in .claude/CLAUDE.md** - `21a04f9` (docs)

## Files Created/Modified
- `Dockerfile` - deleted (Railway/Docker-only build, unused by Vercel's Python runtime)
- `railway.toml` - deleted (Railway deploy config)
- `requirements.txt` - removed `gunicorn==22.*`; `uvicorn==0.30.*` retained for local dev
- `README.md` - rewrote `### Backend: Railway` → `### Backend: Vercel` deployment subsection; fixed `POST /chat/stream` → `GET /chat/stream` with EventSource rationale; renamed env-var table heading; fixed `SUPABASE_SERVICE_KEY` → `SUPABASE_SERVICE_ROLE_KEY` (both the local-dev `.env` comment and the env table); dropped `PORT` row; added `SUPABASE_JWT_SECRET`, `CALENDAR_FERNET_KEY`, `BACKEND_BASE_URL`, `ANTHROPIC_MODEL` rows; added a note that vars must be set in Vercel Project Settings
- `.claude/CLAUDE.md` - corrected 5 Railway references: Tech Stack constraint now reads `Vercel (frontend + backend)`; Uvicorn row rationale no longer mentions Gunicorn/Railway; Dev/Deploy table's Railway/Docker/Gunicorn rows replaced with a single Vercel Python Runtime row; PostgreSQL row simplified to `Supabase`; stale Railway confidence-notes row removed

## Decisions Made
- Kept `uvicorn` in `requirements.txt` per RESEARCH.md's resolved Open Question 3 (still used for the documented local-dev `uvicorn api.main:app --reload` command); removed only `gunicorn`
- Wrote the README backend deployment description at the architecture level (entrypoint `api/index.py`, static frontend build, routing in root `vercel.json`) without hard-coding the word "services", since plan 07-04 decides the exact vercel.json routing mechanism (single-function vs. Vercel `services` split) and this plan must stay accurate regardless of that outcome

## Deviations from Plan

None - plan executed exactly as written. All three tasks' automated `<verify>` checks passed on first attempt; no auto-fixes, blocking issues, or architectural questions arose.

## Issues Encountered
- Running the plan's overall `<verification>` step (`pytest tests/ -q`) surfaced 9 pre-existing test failures (`tests/agent/test_sse.py` — 8 tests; `tests/sports_science/test_capability_gap.py::test_supabase_insert_called_with_correct_fields` — 1 test). Confirmed via `git diff <plan-base>..HEAD --stat` that this plan touched only `Dockerfile`, `railway.toml`, `requirements.txt`, `README.md`, and `.claude/CLAUDE.md` — no Python source under `tests/`, `backend/`, or `api/` was modified, so these failures pre-date this plan and are out of scope per the executor's scope-boundary rule. Logged to `.planning/phases/07-deploy-consolidation/deferred-items.md` with a note that a later plan in this phase (07-02/07-03, which touch SSE/BackgroundTasks) is the natural place to investigate, since RESEARCH.md ties `test_sse.py` to this phase's own `DEPLOY-SSE-01` requirement.

## Known Stubs

None - this plan only removed dead deploy artifacts and corrected documentation; no new UI, data flow, or component was introduced.

## Threat Flags

None - no new network endpoints, auth paths, file access patterns, or schema changes were introduced. The threat register's `T-07-01-01` (docs must not leak real secret values) was verified: only variable names and one-line purposes were added to README.md's env-var table, no real `.env` values.

## User Setup Required

None - no external service configuration required by this plan. Note: RESEARCH.md's Runtime State Inventory flags that the live Railway project itself (if still provisioned in the Railway dashboard) is out-of-band and not deleted by this code-only change; decommissioning it is a manual step assigned to a later checkpoint in this phase (07-04), not this plan.

## Next Phase Readiness
- Repository is clean of Railway/Docker deploy artifacts; `requirements.txt`, `README.md`, and `.claude/CLAUDE.md` all describe Vercel as the sole deploy target with accurate env-var documentation
- Plans 07-02/07-03/07-04 (vercel.json routing restructure, BackgroundTasks → inline-await, DB indexing) are unblocked and can proceed independently of this plan's docs-only changes
- Pre-existing `test_sse.py`/`test_capability_gap.py` failures logged in `deferred-items.md` should be picked up by whichever later plan in this phase touches those code paths (see RESEARCH.md `DEPLOY-SSE-01`/`DEPLOY-BG-01`/`DEPLOY-BG-02` test map)

---
*Phase: 07-deploy-consolidation*
*Completed: 2026-07-03*
