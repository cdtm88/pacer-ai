---
phase: 6
slug: core-loop-persistence
status: final
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-03
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio (backend), vitest 4.x (frontend) |
| **Config file** | pytest.ini (repo root), frontend/vitest.config.ts |
| **Quick run command** | `.venv/bin/pytest tests/ -q -x` |
| **Full suite command** | `.venv/bin/pytest tests/ -q && (cd frontend && npx vitest run)` |
| **Estimated runtime** | ~10 seconds backend, ~2 seconds frontend |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/ -q -x`
- **After every plan wave:** Run full suite
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | FIT-04, PLAN-04 | T-06-01 | UNIQUE(user_id, content_hash) prevents cross-user dedup collision | source | `grep -v '^--' supabase/migrations/0005_phase6_persistence.sql \| grep -c "content_hash"` | ✅ | ⬜ pending |
| 06-01-02 | 01 | 1 | schema push | — | N/A | CLI (BLOCKING) | `supabase db push --linked --yes` | ✅ | ⬜ pending |
| 06-02-01 | 02 | 2 | PLAN-01, PLAN-04 | T-06-02 | user_id from JWT injection, never tool input | unit | `.venv/bin/pytest tests/agent/test_tools_phase3.py -x -q` | ✅ | ⬜ pending |
| 06-02-02 | 02 | 2 | ONBD-04 | T-06-02 | same | unit | `.venv/bin/pytest tests/agent/test_tools_phase3.py -x -q` | ✅ | ⬜ pending |
| 06-02-03 | 02 | 2 | PLAN-04 | — | N/A | unit | `.venv/bin/pytest tests/sports_science/ -q` | ✅ | ⬜ pending |
| 06-03-01 | 03 | 2 | FIT-04, TOOL-05 | — | N/A | unit | `.venv/bin/pytest tests/test_pmc_recompute.py -x -q` | ❌ W0 | ⬜ pending |
| 06-03-02 | 03 | 2 | TOOL-05 | — | N/A | unit | `.venv/bin/pytest tests/test_pmc_recompute.py -x -q` | ❌ W0 | ⬜ pending |
| 06-04-01 | 04 | 2 | ADAPT-01..04 | — | N/A | integration | `.venv/bin/pytest tests/api/test_adaptations.py tests/sports_science/test_compliance.py -x -q` | ✅ | ⬜ pending |
| 06-04-02 | 04 | 2 | ADAPT-03 | — | N/A | integration | `.venv/bin/pytest tests/api/test_adaptations.py -x -q` | ✅ | ⬜ pending |
| 06-04-03 | 04 | 2 | ADAPT-04, TRANSP-02 | T-06-04 | /adaptations/{id}/confirm enforces id+user_id+status dual filter | integration | `.venv/bin/pytest tests/api/test_adaptations.py -x -q` | ✅ | ⬜ pending |
| 06-05-01 | 05 | 3 | TOOL-03 | — | N/A | integration | `.venv/bin/pytest tests/api/test_rides.py -x -q` | ✅ | ⬜ pending |
| 06-05-02 | 05 | 3 | FIT-04, FIT-05 | T-06-06 | content-hash dedup race caught, user-scoped | integration | `.venv/bin/pytest tests/api/test_rides.py -x -q` | ✅ | ⬜ pending |
| 06-05-03 | 05 | 3 | FIT-04 | T-06-07 | inline-await pipeline, JWT-scoped writes | integration | `.venv/bin/pytest tests/api/test_rides.py -x -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/api/test_rides.py` — extend with PMC recompute + dedup fixtures
- [ ] `tests/api/test_adaptations.py` — extend with idempotency fixtures
- [ ] `tests/sports_science/test_plan.py` — NEW (plan.py currently untested)

*Existing pytest/vitest infrastructure covers all phase requirements; no framework install needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Supabase migration applies cleanly to linked project | schema fixes | Requires live DB push | `supabase db push --linked` then verify columns via list_tables |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
