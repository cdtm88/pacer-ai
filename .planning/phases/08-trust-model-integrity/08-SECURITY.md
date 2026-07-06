---
phase: 8
slug: trust-model-integrity
status: verified
threats_open: 0
asvs_level: 1
created: 2026-07-06
---

# Phase 8 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| agent code → Postgres (`audit_log`) | audit rows written with the service-role key; must be scoped so a read cannot cross tenants | tool name, inputs, result, user_id, conversation_id |
| client-supplied `conversation_id` → audit reload | a conversation_id belonging to another user must not surface that user's tool-result numbers | conversation_id (client input) |
| LLM assistant text → user display | numbers in assistant output must be provably sourced from a tool result before reaching the stream | free-text physiological claims |
| tool library → generated plan targets | HR zone boundaries and session durations feed plan intensity; a wrong value silently prescribes unsafe sessions | HR zone bpm values, session durations |
| user-reported max HR → derived LTHR | the derivation must originate in the tool library (methodology-tagged), never the LLM | max HR, estimated LTHR |
| LLM tool-call arguments → `generate_plan` | physiological facts the server already knows must never be transcribed by the LLM | current_ctl, ftp_watts, ftp_confidence, load_targets, preferred_days, hr_zones |
| serverless invocation N → invocation N+1 | cross-turn trust state must survive statelessly via Postgres, not an in-process cache | tool_result_values / audit trail |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-08-01 | Tampering | `generate_plan` input laundering via LLM tool-call arguments | high | mitigate | `dispatch_tool` discards all LLM-supplied values for `current_ctl`/`ftp_watts`/`ftp_confidence`/`load_targets`/`preferred_days`/`hr_zones` and re-injects from `pmc_history`/profile/same-turn `audit_log`; extended post-review (CR-01) to also cover `hr_zones`. Verified: `backend/agent/tools.py:344` comment + injection block. | closed |
| T-08-02 | Tampering / Spoofing (of trust attribution) | `scan_buffer` substring-attribution bypass | high | mitigate | Boundary-aware numeric-token regex (`_NUMERIC_TOKEN`) + `NUMERIC_TOLERANCE=0.01` float compare replaces raw substring match. Verified: `backend/agent/trust.py:100-175`; 5-case regression suite in `tests/agent/test_trust.py` + full corpus in `tests/agent/test_trust_corpus.py`. | closed |
| T-08-03 | Information Disclosure | `load_prior_audit_values` cross-tenant read | high | mitigate | RLS policy `user_id = auth.uid()` on `audit_log` PLUS app-layer `.eq('user_id', user_id)` re-enforcement (defence-in-depth, mirrors `onboarding.load_conversation`). Verified: `backend/agent/audit.py:86,111`. | closed |
| T-08-04 | Tampering (of trust state) | stale/incoherent in-process cache on stateless serverless | medium | mitigate | Cross-turn seeding reads Postgres per invocation (`load_prior_audit_values`); no in-memory cache introduced. Verified: `backend/agent/loop.py:32,102`. | closed |
| T-08-05 | Denial of Service | audit write failure blocking the tool result | medium | mitigate | `write_audit_entry` wraps the insert in `try/except: pass` — a DB outage degrades to "no audit row," never a failed tool call (D-14 best-effort). Verified: `backend/agent/audit.py:6,35-36`. | closed |
| T-08-06 | Tampering (of physiological safety) | `HR_ZONE_BOUNDARIES` mislabel / hot Zone 2 ceiling | high | mitigate | Corrected to true Coggan/Allen (0.68/0.83/0.94/1.05 of LTHR); Zone 2 ceiling drops from the mislabeled 0.90 to 0.83. Verified: `backend/sports_science/constants.py:27-35`; regression guard at `tests/sports_science/test_zones.py:113-121` asserting `upper_bpm == round(0.83 * LTHR)`. | closed |
| T-08-07 | Tampering (of physiological safety) | dead `current_ctl`/`load_targets` params → uncapped ramp for at-risk beginner | high | mitigate | `_is_true_beginner_ramp` flattens weeks 2-3 and tightens week 1 when low-base fitness + moderate back status; asserted by dedicated unit tests in `tests/sports_science/test_plan.py`. | closed |
| T-08-08 | Tampering (stale data) | `generate_plan` called out of D-08 order → missing same-turn ftp/load | medium | mitigate | Cold-start-safe fallback (`ftp_confidence` defaults to `"insufficient_data"`, `load_targets` defaults to `{"recommended_ctl_target": current_ctl}`) — never falls back to an LLM-supplied value. Verified: `backend/agent/tools.py:740,745`. | closed |
| T-08-09 | Tampering | LLM inventing an LTHR to satisfy the plan-order dependency | high | mitigate | Explicit three-branch onboarding prompt: Branch A (stated LTHR, used as-is), Branch B (max-HR routed through `estimate_lthr_from_max_hr`), Branch C (neither known → RPE-only fallback, `hr_zones_available=false`). Verified: `backend/routes/onboarding.py:77-95`. | closed |
| T-08-10 | Denial of Service (over-blocking) | numeric tolerance too tight/loose | medium | mitigate | `NUMERIC_TOLERANCE=0.01` validated against the zero-false-positive/zero-false-negative regression + full corpus suite (`tests/agent/test_trust_corpus.py`, 5 tests). | closed |
| T-08-11 | Repudiation | LTHR-from-max-HR estimate presented as measured | medium | mitigate | `estimate_lthr_from_max_hr` returns an explicit methodology string flagging it as a rough estimate; the number originates in the tool, not the LLM. Verified: `backend/sports_science/zones.py:56-70`. | closed |
| T-08-13 | Repudiation | max-HR-derived LTHR presented as measured (onboarding-side) | medium | mitigate | Onboarding prompt instructs the agent to state the value is an estimate, matching the tool's own methodology caveat. Verified: `backend/routes/onboarding.py:86`. | closed |
| T-08-12 | Denial of Service (over-conservative) | CTL-gap ramp threshold (0.5) too low → everyone gets a flat ramp | low | accept | Threshold fixed at 0.5 (RESEARCH A3); guarded by a near-target regression test proving non-beginners keep the full template. Below the `security_block_on: high` threshold — accepted at plan time (Plan 04). | closed |
| T-08-SC | Tampering | package/supply-chain integrity | low | accept | No new third-party packages introduced by any of the 7 plans — only stdlib (`re`, `json`) and already-vetted `supabase`/`backend.db` modules reused. Accepted across all plans (Plans 01-07). | closed |

*Status: open · closed · open — below `high` threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above `workflow.security_block_on` (currently `high`) count toward `threats_open`*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

**Post-review widening note:** T-08-01's mitigation as originally scoped in Plan 06 covered only 5 keys (`current_ctl`/`ftp_watts`/`ftp_confidence`/`load_targets`/`preferred_days`). The code-review pass on this phase (`08-REVIEW.md`, CR-01 and CR-02) found the scope drawn too narrow — `hr_zones` (generate_plan) and `lthr_estimate` (save_profile) were two more number-laundering paths left open by the same threat class. Both were closed in the fix pass (commits `dc2cf7c`, `d3fb62a`) and are reflected in T-08-01's mitigation above. This SECURITY.md reflects the post-fix state, not the initial plan-time scope.

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-08-01 | T-08-12 | CTL-gap ramp threshold fixed at 0.5 rather than tunable; a DoS-class over-conservatism risk (all users get a flattened ramp) is bounded by a regression test proving normal-fitness users are unaffected, and is below the `high` block threshold | Plan 04 (planner) | 2026-07-04 |
| AR-08-02 | T-08-SC | No new third-party packages introduced this phase; supply-chain risk surface unchanged from pre-Phase-8 state | Plans 01-07 (planner) | 2026-07-04 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-06 | 14 | 14 | 0 | Claude (gsd-secure-phase, ASVS L1 grep-depth verification against live source; register authored at plan time across all 7 PLAN.md threat_model blocks) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-07-06
