# Phase 8: Trust Model Integrity - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-04
**Phase:** 08-trust-model-integrity
**Mode:** `--auto` (no interactive questions; recommended option auto-selected for every area, logged here for audit)
**Areas discussed:** Audit log persistence, Tool input scanning, Attribution matching, Prior-turn seeding, LTHR collection, HR zone correction, generate_plan wiring

---

## Audit Log Persistence (TRUST-04)

| Option | Description | Selected |
|--------|-------------|----------|
| New `audit_log` table, per-tool-dispatch write | Mirrors `capability_gap.py` async-Supabase-service-role pattern; survives partial/interrupted turns | ✓ |
| Structured log lines only, no DB | Cheaper, but doesn't satisfy "persisted" per ROADMAP goal, no query/grep parity with capability_gaps | |
| Batch-write full `audit_log` list at end of turn | Simpler, but loses the whole turn's trail on mid-turn SSE disconnect or serverless timeout | |

**[auto] Selected:** New `audit_log` table, per-call write (recommended default — matches existing `capability_gaps` precedent and dispatch_tool call sites).
**Notes:** `_sse.py:75` currently builds `audit_log: list = []` per-request and it is never persisted anywhere. Confirmed via direct grep of `backend/db*` and `supabase/migrations/` — no audit table exists today.

---

## Tool Input Scanning — Laundering Prevention

| Option | Description | Selected |
|--------|-------------|----------|
| Server-side injection for tool-result-derived values + confirmed-values registry for user-reported values | Mirrors the proven `user_id` injection fix (260702-wev); LLM never supplies `current_ctl`/`ftp_watts`/`load_targets` as raw tool-call args | ✓ |
| Log-only warning, no enforcement | Doesn't close the laundering hole the roadmap goal names | |
| Whitelist tools that may accept LLM-supplied numeric inputs at all | Coarser; doesn't distinguish "value the LLM must transcribe" (max_hr_or_lthr) from "value that must come from a prior tool result" | |

**[auto] Selected:** Split by provenance — server-side injection for tool-derived values, confirmed-values registry for user-reported values.
**Notes:** Confirmed via `backend/agent/tools.py` `generate_plan` schema (line ~314) that `current_ctl` and `load_targets` are currently LLM-suppliable tool-call arguments, not server-injected.

---

## Attribution Matching — Word-Boundary + Tolerance

**Not discussed as a gray area** — already locked by ROADMAP.md's Phase 8 goal text ("bare-number attribution uses word-boundary and tolerance matching instead of substring"). Confirmed the underlying bug directly in `backend/agent/trust.py:127-131,151-156` (bare-digit substring fallback added in 260702-vsp/260702-w52 can match "250" inside "2500").

---

## Prior-Turn Number Seeding — Cross-Turn False Positives

| Option | Description | Selected |
|--------|-------------|----------|
| Reload `tool_result_values` from persisted `messages` table at start of each turn | Consistent with Phase 7's stateless-serverless architecture decision; reuses existing `load_conversation` pattern | ✓ |
| In-memory/process-level cache keyed by conversation_id | Invisible across Vercel serverless invocations — wrong fit post-Phase-7 | |
| New DB table for "confirmed numeric facts" per conversation | Viable but heavier than reusing already-persisted tool-result content blocks | |

**[auto] Selected:** Reload from persisted `messages` table.
**Notes:** `loop.py`/`chat.py` currently reset `tool_result_values` per HTTP request — directly confirmed by grep. Ties to the Phase 7 decision (Vercel serverless, no in-process state survives between requests).

---

## LTHR Collection in Onboarding

| Option | Description | Selected |
|--------|-------------|----------|
| Direct onboarding question with 3 explicit outcomes (LTHR / max-HR-estimate / RPE-only fallback flag) | Matches ROADMAP wording exactly; reuses Phase 3's existing cold-start RPE path | ✓ |
| Silent default assumption, no question | Contradicts "explicit RPE-only fallback" requirement | |
| Auto-estimate LTHR from ride HR data only | Doesn't help before any rides exist (cold start is the primary case this system is built for) | |

**[auto] Selected:** Direct question with 3 explicit outcomes.
**Notes:** Confirmed `backend/routes/onboarding.py` never asks for LTHR/max HR (grep for "lthr"/"LTHR" returns zero question-flow hits). Phase 3's D-08 requires `calculate_hr_zones` before `generate_plan`, so today the LLM has no path except inventing a number.

---

## HR Zone Constants + Zone 2 Beginner Safety

| Option | Description | Selected |
|--------|-------------|----------|
| Correct `HR_ZONE_BOUNDARIES` to true Coggan/Allen values (~68/83/94/105%) | Fixes methodology-honesty bug AND independently produces a safer, lower Zone 2 ceiling for beginners — one fix, two roadmap concerns resolved | ✓ |
| Keep current (Friel-style) boundaries, rename methodology string to "Friel" | Honest about methodology but doesn't address beginner-safety half of the goal | |
| Add a separate bespoke "beginner Zone 2" ceiling on top of either model | Solves safety but introduces a third unnamed model; unnecessary given option 1 | |

**[auto] Selected:** Correct constants to true Coggan/Allen boundaries.
**Notes:** Verified `constants.py:24-33` — current boundaries (81/90/94/100%) are Friel-style; docstring and `calculate_hr_zones` tool description both claim "Coggan/Allen." `calculate_power_zones` (7-zone, from FTP) already correctly implements the real Coggan/Allen model — used as reference.

---

## generate_plan Wiring — current_ctl / load_targets / preferred_days

| Option | Description | Selected |
|--------|-------------|----------|
| Add `preferred_days` param + wire `current_ctl`/`load_targets` into real per-week progression and Week-1 cap logic | Satisfies the roadmap's stated success condition ("back-protective caps actually constrain sessions") | ✓ |
| Wire `preferred_days` only, leave `current_ctl`/`load_targets` cosmetic | Partial fix, doesn't meet the stated goal | |
| Delete the unused params (honesty-only, no new behavior) | Doesn't meet the stated goal at all | |

**[auto] Selected:** Full wiring (days + load-aware progression).
**Notes:** Confirmed directly in `plan.py:202-250` (`generate_plan`) and `plan.py:73-` (`_build_sessions`) — `current_ctl`/`load_targets` are accepted parameters never referenced in the function body; `_DEFAULT_DAYS[:n_sessions]` is used unconditionally regardless of any user day preference.

---

## Claude's Discretion

- Exact numeric tolerance for the attribution float-compare (D-03).
- Exact %-of-max-HR formula for estimating LTHR when only max HR is known (D-05).
- Exact shape of the load-aware progression multiplier in `generate_plan` (D-07) — direction locked, curve left to planning/research.

## Deferred Ideas

- CP model quality-filter bug (`ftp.py:46`, dead `best_ftp_estimate`, no 0.95 discount) — found under the review doc's "Phase 8" heading but not in ROADMAP.md's actual Phase 8 scope. Flagged for roadmap backlog.
- ZWO fixed-0.65-FTP export bug (`zwo.py:22-26,97`) — same situation, flagged for backlog.
- NaN propagation in metrics and the review doc's remaining "misc" bullet list — same situation, flagged for backlog, not silently dropped.
