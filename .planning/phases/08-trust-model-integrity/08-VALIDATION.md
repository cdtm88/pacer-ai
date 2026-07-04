---
phase: 8
slug: trust-model-integrity
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-04
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio (`asyncio_mode = auto`) |
| **Config file** | `pytest.ini` (repo root) |
| **Quick run command** | `.venv/bin/python -m pytest tests/agent/test_trust.py tests/agent/test_loop.py tests/agent/test_tools_phase3.py tests/sports_science/test_zones.py -q` |
| **Full suite command** | `.venv/bin/python -m pytest tests/ -q` |
| **Estimated runtime** | ~30 seconds (full suite; quick subset is a few seconds) |

**Baseline (confirmed by running the full suite in the research session, before any Phase 8 change):** `9 failed, 250 passed`. The 9 failures are pre-existing and unrelated (`tests/agent/test_sse.py` x8 — stale auth expectations; `tests/sports_science/test_capability_gap.py::test_supabase_insert_called_with_correct_fields` x1 — test-order state leak; both already documented in prior quick-task summaries and in `.planning/research/APP-REVIEW-260703.md` Phase 10 section). Treat this exact count as the pre-Phase-8 baseline — any NEW failures beyond these 9 identities are regressions introduced by this phase's work.

---

## Sampling Rate

- **After every task commit:** Run the quick run command above.
- **After every plan wave:** Run the full suite command.
- **Before `/gsd-verify-work`:** Full suite must be green (9 pre-existing failures only — no new failures).
- **Max feedback latency:** ~30 seconds.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 1 | TRUST-06 | T-08-01 | `audit_log` row written per tool dispatch, queryable by user_id+conversation_id | unit | `pytest tests/agent/test_audit.py -x` | ❌ W0 | ⬜ pending |
| 08-01-02 | 01 | 1 | TRUST-06 | T-08-01 | `conversation_id` threaded through `run_turn`/`sse_generator`/`dispatch_tool` alongside existing `user_id` | unit | `pytest tests/agent/test_loop.py -x` | ✅ (extend) | ⬜ pending |
| 08-02-01 | 02 | 2 | TRUST-07 | T-08-02 | `generate_plan`'s current_ctl/ftp_watts/ftp_confidence/load_targets/preferred_days are server-injected from `pmc_history`/profile, LLM-supplied values discarded | unit | `pytest tests/agent/test_tools_phase3.py -k generate_plan_injection -x` | ❌ W0 (extend existing file) | ⬜ pending |
| 08-03-01 | 03 | 2 | TRUST-08 | T-08-03 | `scan_buffer` uses numeric-token + tolerance matching, not substring; "250" no longer matches inside "2500"/"0.250" | unit | `pytest tests/agent/test_trust.py -x` | ✅ (extend) | ⬜ pending |
| 08-03-02 | 03 | 2 | TRUST-09 | T-08-03 | `tool_result_values` seeded from persisted audit trail at start of turn; legit prior-turn number no longer flagged as violation | unit | `pytest tests/agent/test_loop.py -k cross_turn_seed -x` | ❌ W0 (extend existing file) | ⬜ pending |
| 08-04-01 | 04 | 2 | ONBD-05 | — | Onboarding collects LTHR, or max-HR-derived estimate, or explicit `hr_zones_available=false` with RPE-only fallback | unit + manual | `pytest tests/api/test_onboarding.py -x` | ✅ (extend) | ⬜ pending |
| 08-05-01 | 05 | 1 | amends TOOL-02 | — | `HR_ZONE_BOUNDARIES` match true Coggan/Allen 68/83/94/105%; Zone 2 ceiling drops from 90% to 83% | unit | `pytest tests/sports_science/test_zones.py -x` | ✅ (extend) | ⬜ pending |
| 08-06-01 | 06 | 2 | PLAN-07 | — | `generate_plan` consumes current_ctl/load_targets/preferred_days; back-protective + CTL-gap caps actually constrain sessions | unit | `pytest tests/sports_science/test_plan.py -x` | ❌ W0 (new file) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*Task IDs above are provisional — the planner assigns final plan/task numbering; this table exists to guarantee every proposed requirement has an automated test mapped before execution starts.*

---

## Wave 0 Requirements

- [ ] `tests/agent/test_audit.py` — stubs for TRUST-06 (new `audit_log` writer + reload function), mocking `backend.db.get_async_supabase` the same way `tests/sports_science/test_capability_gap.py` mocks `acreate_client`.
- [ ] `tests/sports_science/test_plan.py` — extract `generate_plan`'s inline tests out of `test_tools_phase3.py` into a dedicated file (matching the `test_zones.py`/`test_load.py` per-module convention used elsewhere in `tests/sports_science/`), and add the PLAN-07 CTL-gap-ramp + preferred_days cases.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| End-to-end onboarding conversation actually asks the new LTHR/max-HR/RPE-only question at the right point in the interview flow | ONBD-05 | LLM-driven conversational flow — the exact wording/timing of the question depends on live model behavior, not just unit-testable state transitions | Run a real onboarding conversation (dev environment), confirm the question appears before any plan/HR-zone tool call, and confirm all three branches (LTHR given / max-HR given / neither given) produce the expected profile state |
| `supabase db push --linked --yes` succeeds for the new `audit_log` migration against the real linked project | TRUST-06 | Requires live Supabase connectivity, not available in an isolated test run | Run the migration against the linked Supabase project per the existing pattern documented in STATE.md ("Migration applied via supabase db push --linked") |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (`test_audit.py`, `test_plan.py`)
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
