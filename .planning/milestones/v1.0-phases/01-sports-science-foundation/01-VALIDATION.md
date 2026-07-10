---
phase: 1
slug: sports-science-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-19
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 + pytest-asyncio 1.4.0 |
| **Config file** | `pytest.ini` (Wave 0 creates it) |
| **Quick run command** | `pytest tests/sports_science/ -x -q` |
| **Full suite command** | `pytest tests/ -v --tb=short` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/sports_science/ -x -q`
- **After every plan wave:** Run `pytest tests/ -v --tb=short`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-T01 | 01 | 0 | TOOL-09 | — | ToolResult dataclass correct fields | unit | `pytest tests/sports_science/test_types.py -x` | ❌ W0 | ⬜ pending |
| 01-T02 | 01 | 0 | TOOL-01 | — | Power zones correct boundaries FTP=200 | unit | `pytest tests/sports_science/test_zones.py::test_power_zones_ftp200 -x` | ❌ W0 | ⬜ pending |
| 01-T03 | 01 | 0 | TOOL-02 | — | HR zones for LTHR=155 | unit | `pytest tests/sports_science/test_zones.py::test_hr_zones_lthr155 -x` | ❌ W0 | ⬜ pending |
| 01-T04 | 01 | 1 | TOOL-03 | T-1-05 | CP model refuses < 4 quality efforts | unit | `pytest tests/sports_science/test_ftp.py::test_insufficient_efforts_returns_none -x` | ❌ W0 | ⬜ pending |
| 01-T05 | 01 | 1 | TOOL-04 | T-1-05 | NP includes zeros, not filtered | unit | `pytest tests/sports_science/test_metrics.py::test_np_includes_zeros -x` | ❌ W0 | ⬜ pending |
| 01-T06 | 01 | 1 | TOOL-04 | — | NP spike filter clips at FTP*3 | unit | `pytest tests/sports_science/test_metrics.py::test_np_spike_filter -x` | ❌ W0 | ⬜ pending |
| 01-T07 | 01 | 1 | TOOL-04 | — | TSS returns None for ride < 10 min | unit | `pytest tests/sports_science/test_metrics.py::test_tss_short_ride_null -x` | ❌ W0 | ⬜ pending |
| 01-T08 | 01 | 1 | TOOL-05 | — | PMC EWMA values match manual calculation | unit | `pytest tests/sports_science/test_pmc.py::test_ewma_values -x` | ❌ W0 | ⬜ pending |
| 01-T09 | 01 | 1 | TOOL-05 | — | tss_display_ready=False before 28 days | unit | `pytest tests/sports_science/test_pmc.py::test_cold_start_guard -x` | ❌ W0 | ⬜ pending |
| 01-T10 | 01 | 1 | TOOL-06 | — | Back constraints apply weekly hour cap | unit | `pytest tests/sports_science/test_load.py::test_back_constraints_cap -x` | ❌ W0 | ⬜ pending |
| 01-T11 | 01 | 1 | TOOL-07 | — | Compliance percentage calculation correct | unit | `pytest tests/sports_science/test_compliance.py::test_compliance_pct -x` | ❌ W0 | ⬜ pending |
| 01-T12 | 01 | 1 | TOOL-08 | T-1-04 | log_capability_gap returns user-safe string | unit | `pytest tests/sports_science/test_capability_gap.py::test_user_message_no_method_name -x` | ❌ W0 | ⬜ pending |
| 01-T13 | 01 | 1 | TOOL-10 | — | Edge case: all-zero power array | unit | `pytest tests/sports_science/test_metrics.py::test_all_zeros -x` | ❌ W0 | ⬜ pending |
| 01-T14 | 01 | 1 | TOOL-01 | — | Zone boundary no dual membership | unit | `pytest tests/sports_science/test_zones.py::test_zone_boundary_no_overlap -x` | ❌ W0 | ⬜ pending |
| 01-T15 | 01 | 1 | TRUST-01 | T-1-01 | Zero anthropic imports in sports_science/ | unit | `pytest tests/sports_science/test_import_boundary.py -x` | ❌ W0 | ⬜ pending |
| 01-T16 | 01 | 2 | GAP-01 | T-1-04 | capability_gaps row inserted with correct user_id | integration | `pytest tests/sports_science/test_capability_gap.py::test_db_insert -x` | ❌ W0 | ⬜ pending |
| 01-T17 | 01 | 2 | TRUST-02 | T-1-02 | Tool schema registered in registry only | unit | `pytest tests/sports_science/test_tool_registry.py -x` | ❌ W0 | ⬜ pending |
| 01-T18 | 01 | 2 | GAP-02 | T-1-03 | Supabase 8-table schema migrated accessible | integration | `pytest tests/sports_science/test_db_schema.py -x` | ❌ W0 | ⬜ pending |
| 01-T19 | 01 | 2 | TOOL-09 | — | All functions return ToolResult with required fields | unit | `pytest tests/sports_science/ -k "test_returns_tool_result" -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `pytest.ini` — must exist before test discovery; set `asyncio_mode = auto` for pytest-asyncio 1.4.0
- [ ] `tests/__init__.py` and `tests/sports_science/__init__.py` — empty files for pytest discovery
- [ ] `tests/sports_science/conftest.py` — shared fixtures: sample power arrays, sample ride dicts, sample FTP values
- [ ] Install: `pip install pytest==9.1.1 pytest-asyncio==1.4.0 numpy scipy pydantic supabase`
- [ ] Install Supabase CLI: `brew install supabase/tap/supabase`
- [ ] Create Python 3.12 venv (local Python is 3.14; Railway targets 3.12)
- [ ] `requirements.txt` with all pinned versions
- [ ] Stub test files for all test modules listed above

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Supabase cloud project creation | GAP-02 | Requires user account + Supabase dashboard action | Navigate to supabase.com, create project, copy `SUPABASE_URL` and `SUPABASE_ANON_KEY` |
| RLS policies enforced in cloud (not just local) | GAP-02, GAP-03 | RLS enforcement varies between local and cloud | After migration, attempt insert with anon key; verify 403 response |
| Service role key not exposed in any frontend bundle | TRUST-02 | Static bundle analysis required | Run `grep -r SUPABASE_SERVICE_ROLE_KEY frontend/` → must return empty |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
