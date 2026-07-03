---
phase: 6
slug: core-loop-persistence
status: draft
nyquist_compliant: false
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

*Filled by planner — see PLAN.md `<verify>` blocks. Populated from RESEARCH.md ## Validation Architecture.*

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | — | — | — | — | — | unit/integration | `.venv/bin/pytest tests/ -q` | ✅ | ⬜ pending |

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
