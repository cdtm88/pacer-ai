---
phase: 03
slug: coaching-loop
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-20
---

# Phase 03 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 + pytest-asyncio 1.4.0 |
| **Config file** | `pytest.ini` (exists; `asyncio_mode = auto`, `testpaths = tests`) |
| **Quick run command** | `python -m pytest tests/ -x -q` |
| **Full suite command** | `python -m pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds (unit); ~60 seconds (with integration) |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-DB-01 | DB | 1 | ONBD-01..03, FIT-01..04 | — | N/A | migration | `supabase db push` | ❌ W0 | ⬜ pending |
| 03-ONBD-01 | onboarding | 1 | ONBD-01 | — | Interview collects 6 required fields | unit | `pytest tests/api/test_onboarding.py -x` | ❌ W0 | ⬜ pending |
| 03-ONBD-02 | onboarding | 1 | ONBD-02 | — | back_status persisted and applied | unit | `pytest tests/api/test_onboarding.py::test_back_status_constraint -x` | ❌ W0 | ⬜ pending |
| 03-ONBD-03 | onboarding | 1 | ONBD-03 | — | Profile row inserted in DB | integration | `pytest tests/api/test_onboarding.py::test_profile_persisted -x` | ❌ W0 | ⬜ pending |
| 03-ONBD-04 | onboarding | 1 | ONBD-04 | — | Confirmation gate blocks early generate_plan | unit | `pytest tests/api/test_onboarding.py::test_confirmation_gate -x` | ❌ W0 | ⬜ pending |
| 03-PLAN-01 | plan-gen | 1 | PLAN-01 | — | 4-week mesocycle generated | unit | `pytest tests/agent/test_tools_phase3.py::test_generate_plan -x` | ❌ W0 | ⬜ pending |
| 03-PLAN-02 | plan-gen | 1 | PLAN-02 | — | Cold-start uses HR zones only | unit | `pytest tests/agent/test_tools_phase3.py::test_cold_start_hr_only -x` | ❌ W0 | ⬜ pending |
| 03-PLAN-03 | plan-gen | 1 | PLAN-03 | — | Power targets absent when ftp_confidence=insufficient_data | unit | `pytest tests/agent/test_tools_phase3.py::test_power_targets_cold_start -x` | ❌ W0 | ⬜ pending |
| 03-PLAN-04 | plan-gen | 1 | PLAN-04 | — | Each session has objective+structure+targets+duration | unit | `pytest tests/agent/test_tools_phase3.py::test_session_schema -x` | ❌ W0 | ⬜ pending |
| 03-PLAN-05 | plan-gen | 1 | PLAN-05 | — | Back constraints applied in plan | unit | `pytest tests/agent/test_tools_phase3.py::test_back_constraints -x` | ❌ W0 | ⬜ pending |
| 03-PLAN-06 | plan-gen | 1 | PLAN-06 | — | Every number traced to tool call | compliance | `pytest tests/agent/test_trust_corpus.py -x` | ✅ extend | ⬜ pending |
| 03-FIT-01 | fit-ingest | 2 | FIT-01 | — | Upload endpoint returns 200 | integration | `pytest tests/api/test_rides.py::test_upload_returns_200 -x` | ❌ W0 | ⬜ pending |
| 03-FIT-02 | fit-ingest | 2 | FIT-02 | — | fitdecode with ErrorHandling.WARN | unit | `pytest tests/api/test_rides.py::test_fit_parse_warn -x` | ❌ W0 | ⬜ pending |
| 03-FIT-03 | fit-ingest | 2 | FIT-03 | — | Missing HR/cadence handled gracefully | unit | `pytest tests/api/test_rides.py::test_missing_fields -x` | ❌ W0 | ⬜ pending |
| 03-FIT-04 | fit-ingest | 2 | FIT-04 | — | TSS computed + PMC updated | integration | `pytest tests/api/test_rides.py::test_tss_computed -x` | ❌ W0 | ⬜ pending |
| 03-FIT-05 | fit-ingest | 2 | FIT-05 | — | validate_session_vs_actual called | unit | `pytest tests/api/test_rides.py::test_session_compliance -x` | ❌ W0 | ⬜ pending |
| 03-FIT-06 | fit-ingest | 2 | FIT-06 | — | Real Zwift .FIT acceptance test passes | integration | `pytest tests/api/test_rides.py::test_fit_upload_integration -x` | ❌ W0 | ⬜ pending |
| 03-ADAPT-01 | adapt | 3 | ADAPT-01 | — | Missed session detected | unit | `pytest tests/api/test_adaptations.py::test_missed_detection -x` | ❌ W0 | ⬜ pending |
| 03-ADAPT-02 | adapt | 3 | ADAPT-02 | — | Micro vs macro branch | unit | `pytest tests/api/test_adaptations.py::test_micro_macro_branch -x` | ❌ W0 | ⬜ pending |
| 03-ADAPT-03 | adapt | 3 | ADAPT-03 | — | 30% shift limit enforced | unit | `pytest tests/api/test_adaptations.py::test_shift_limit -x` | ❌ W0 | ⬜ pending |
| 03-ADAPT-04 | adapt | 3 | ADAPT-04 | — | Weekly check endpoint functional | unit | `pytest tests/api/test_adaptations.py::test_weekly_check -x` | ❌ W0 | ⬜ pending |
| 03-ADAPT-05 | adapt | 3 | ADAPT-05 | — | Intensity decided via tool results | unit | `pytest tests/api/test_adaptations.py::test_intensity_from_tools -x` | ❌ W0 | ⬜ pending |
| 03-TRANSP-01 | transparency | 3 | TRANSP-01 | — | Agent cites tool values in chat | compliance | `pytest tests/agent/test_trust_corpus.py -x` | ✅ extend | ⬜ pending |
| 03-TRANSP-02 | transparency | 3 | TRANSP-02 | — | Adaptation log persisted | unit | `pytest tests/api/test_adaptations.py::test_log_persisted -x` | ❌ W0 | ⬜ pending |
| 03-TRANSP-03 | transparency | 3 | TRANSP-03 | — | GET /adaptations returns log | unit | `pytest tests/api/test_adaptations.py::test_get_adaptations -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/api/__init__.py` — init file for new api test package
- [ ] `tests/api/conftest.py` — shared fixtures: test user_id, mock supabase client, mock background tasks
- [ ] `tests/api/test_onboarding.py` — stubs for ONBD-01 through ONBD-04
- [ ] `tests/api/test_rides.py` — stubs for FIT-01 through FIT-06
- [ ] `tests/api/test_adaptations.py` — stubs for ADAPT-01 through ADAPT-05, TRANSP-01 through TRANSP-03
- [ ] `tests/agent/test_tools_phase3.py` — stubs for PLAN-01 through PLAN-06 and new tool tests
- [ ] `tests/fixtures/sample_zwift.fit` — real Zwift .FIT file for FIT-06 acceptance test
- [ ] `fitdecode==0.11.0` added to `requirements.txt` — blocking dependency for FIT pipeline

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Claude SSE stream includes cited values | TRANSP-01 | LLM output non-deterministic | POST /chat/stream with ride debrief; verify TSS/CTL/ATL/TSB in response text |
| Confirmation summary readability | ONBD-04 | UX review | Run onboarding interview; verify confirmation summary is human-readable before approval |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
