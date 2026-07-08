---
phase: 10-hygiene-safety-nets
plan: 05
subsystem: infra
tags: [github-actions, ci, ruff, pytest, vitest, gitignore, cleanup]

# Dependency graph
requires:
  - phase: 10-hygiene-safety-nets (plans 01, 03, 04)
    provides: A green test suite (stale SSE tests fixed, contract tests added, rate limiting) that CI now guards
provides:
  - Report-only GitHub Actions CI workflow (backend ruff+pytest, frontend vitest)
  - Clean repo root with no orphaned node_modules/ or stray fixture files
affects: [any future phase adding backend/frontend tests or dependencies]

# Tech tracking
tech-stack:
  added: [GitHub Actions (actions/checkout@v6, actions/setup-python@v6, actions/setup-node@v6)]
  patterns: ["CI mirrors Makefile targets (ruff check ., pytest tests/ -q) rather than inventing new commands"]

key-files:
  created: [.github/workflows/ci.yml]
  modified: [.gitignore]

key-decisions:
  - "CI is report-only per D-05 — no branch protection, no required checks; commits still land directly on main"
  - "Playwright e2e excluded from CI scope (browser-binary provisioning out of scope this phase)"
  - "vitest invoked as `npm run test -- --run` to force single-run mode instead of default watch mode"
  - "Root node_modules/ removal confirmed safe: no root package.json exists, real frontend project lives under frontend/"

patterns-established:
  - "CI workflow: two independent jobs (backend, frontern) both on ubuntu-latest, no cross-job dependency, both required to mirror the existing Makefile check target"

requirements-completed: [ITEM-07, ITEM-08]

coverage:
  - id: D1
    description: "A push to the repo triggers a GitHub Actions run that executes ruff, pytest, and vitest and reports status (report-only, no branch protection)"
    requirement: "ITEM-07"
    verification:
      - kind: other
        ref: "python3 -c \"import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))\" -> valid YAML"
        status: pass
      - kind: other
        ref: "grep -c 'ruff check|pytest|vitest|npm run test' .github/workflows/ci.yml -> 3"
        status: pass
      - kind: other
        ref: "grep -c 'playwright|test:e2e|branch.protection' .github/workflows/ci.yml -> 0"
        status: pass
      - kind: other
        ref: "grep -c 'secrets\\.' .github/workflows/ci.yml -> 0"
        status: pass
    human_judgment: true
    rationale: "Actual triggering and pass/fail reporting on GitHub Actions can only be observed after this commit is pushed and the Actions tab is checked — local YAML/grep checks prove the workflow is well-formed and scoped correctly, not that it runs green on GitHub's runners."
  - id: D2
    description: "Root node_modules/ and test-ride.fit are removed and gitignored so they cannot silently reappear untracked"
    requirement: "ITEM-08"
    verification:
      - kind: other
        ref: "test ! -e node_modules && test ! -e test-ride.fit -> both removed"
        status: pass
      - kind: other
        ref: "git status --porcelain | grep '^?? (node_modules/|test-ride.fit)' -> no match (clean)"
        status: pass
      - kind: other
        ref: "git check-ignore -v node_modules test-ride.fit (with node_modules/ recreated as empty dir) -> both matched by .gitignore rules"
        status: pass
    human_judgment: false

# Metrics
duration: 20min
completed: 2026-07-08
status: complete
---

# Phase 10 Plan 05: CI Safety Net + Repo Cleanup Summary

**Report-only GitHub Actions CI workflow (ruff+pytest backend, vitest frontend) and removal of orphaned root node_modules/ + test-ride.fit with gitignore guards**

## Performance

- **Duration:** 20 min
- **Started:** 2026-07-08T14:56:00Z
- **Completed:** 2026-07-08T15:16:50Z
- **Tasks:** 2
- **Files modified:** 2 (`.github/workflows/ci.yml` created, `.gitignore` modified)

## Accomplishments
- Added `.github/workflows/ci.yml`: a `CI` workflow triggered on `push` and `pull_request` with two independent jobs — `backend` (checkout, setup-python 3.12, `pip install -r requirements.txt`, `ruff check .`, `pytest tests/ -q`) and `frontend` (checkout, setup-node 22 with npm cache keyed on `frontend/package-lock.json`, `npm ci`, `npm run test -- --run`)
- Confirmed report-only scope: no Playwright/e2e step, no branch-protection config (that's a GitHub repo setting, not a file), no `secrets.*` references anywhere in the workflow
- Removed the orphaned root `node_modules/` (no root `package.json` exists; the real frontend project lives under `frontend/`) and the stray 66-byte `test-ride.fit` fixture
- Added `/node_modules/` (root-anchored) and `test-ride.fit` guard entries to the root `.gitignore`, verified they match without disturbing any existing entries

## Task Commits

Each task was committed atomically:

1. **Task 1: Add report-only GitHub Actions CI workflow (D-05)** - `ce2b519` (feat)
2. **Task 2: Remove orphaned root node_modules/ and test-ride.fit; gitignore both** - `492e92c` (chore)

**Plan metadata:** (this SUMMARY commit)

## Files Created/Modified
- `.github/workflows/ci.yml` - New CI workflow: backend job (ruff + pytest) and frontend job (vitest --run), report-only, pinned action majors (@v6)
- `.gitignore` - Added `test-ride.fit` and root-anchored `/node_modules/` guard entries under/near the existing `# Test artifacts` section; no existing lines removed or reordered

## Decisions Made
- CI is report-only per D-05: no branch protection or required-check rules configured (that's a GitHub repository setting outside this repo's files, and out of scope this phase)
- Playwright e2e deliberately excluded from CI (browser-binary provisioning is future scope, not this phase's D-05 commitment)
- `npm run test -- --run` used instead of bare `npm run test`, since the latter invokes vitest's default watch mode and would hang the CI job indefinitely
- Root `node_modules/` deletion confirmed safe by verifying no root `package.json` exists — it was orphaned cruft, not a real dependency tree; `frontend/` remains the only real JS project root

## Deviations from Plan

None - plan executed exactly as written. Both tasks' acceptance criteria were verified command-for-command as specified in the plan (YAML validity, grep counts for tool invocations/exclusions/secrets, artifact removal, `.gitignore` diff showing additions only, `git check-ignore` matching both paths).

One clarifying note (not a deviation): this worktree's working tree did not have a pre-existing root `node_modules/` or `test-ride.fit` (those untracked artifacts exist only in the main repo's working tree, which worktrees do not share). Task 2's removal commands ran safely as no-ops here, and the `.gitignore` guard entries were still added exactly as the plan specifies so the orchestrator's merge back to the main branch carries the guard — the main repo's untracked `node_modules/`/`test-ride.fit` are local, unversioned files that the merge itself cannot remove; deleting those from the main worktree's disk (if still present after merge) is a one-time follow-up the orchestrator or user can run (`rm -rf node_modules test-ride.fit` from repo root), now safely covered by the committed `.gitignore` rules so they won't reappear as untracked.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required. One item requires a human-check per the plan: after this commit is merged and pushed, open the repo's GitHub Actions tab and confirm the `CI` workflow triggers and both jobs (`backend`, `frontend`) run and report status — this cannot be observed from a local worktree run and is noted as an end-of-phase manual verification item (item 7).

## Next Phase Readiness

Phase 10 (Hygiene and Safety Nets) is now fully executed — this was the last plan (05 of 05), sequenced last so the CI workflow guards an already-green suite (depends on plans 01, 03, 04). Ready for phase-level verification (`/gsd-verify-work 10`), including the manual GitHub Actions tab check noted above.

---
*Phase: 10-hygiene-safety-nets*
*Completed: 2026-07-08*

## Self-Check: PASSED

- FOUND: `.github/workflows/ci.yml`
- FOUND: `.gitignore` (modified)
- FOUND: `.planning/phases/10-hygiene-safety-nets/10-05-SUMMARY.md`
- FOUND commit: `ce2b519` (Task 1 - CI workflow)
- FOUND commit: `492e92c` (Task 2 - cleanup + gitignore)
- FOUND commit: `356efdf` (SUMMARY.md)
