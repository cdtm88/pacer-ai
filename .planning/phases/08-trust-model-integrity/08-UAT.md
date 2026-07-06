---
status: complete
phase: 08-trust-model-integrity
source: [08-VERIFICATION.md]
started: 2026-07-04T00:00:00Z
updated: 2026-07-06T00:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Live onboarding conversation exercises all 3 HR-baseline branches (ONBD-05)
expected: See above — three branches (direct LTHR / max-HR estimate / neither known), correct tool usage and profile persistence in each, no invented numbers.
result: issue
reported: "Branch A (user states LTHR directly, e.g. 'My LTHR is 165 bpm') deterministically fails: the trust scanner flags the LLM's own confirmation of the user's self-reported number as an unsourced trust_violation (no tool was called this turn, correctly, per D-05 Branch A design — so tool_result_values never contains the number). Exhausts all 3 retries, returns an empty assistant response. Reproduced twice, 100% deterministic, live against the real backend + real Claude model via direct API calls (conversation IDs 33afab79-b968-40bf-a80e-a793ffd062dc). Branch B (max HR only → estimate_lthr_from_max_hr tool, 166bpm from 190 max HR, correctly attributed and caveated) and Branch C (neither known → clean RPE-only fallback, no HR numbers mentioned) both work correctly, verified live in separate conversations (3b64e8e6-6e1a-44c6-8e72-534a419096ab and 0f174866-8a57-4dc1-9b94-d005044c1b55)."
severity: blocker

## Summary

total: 1
passed: 0
issues: 1
pending: 0
skipped: 0
blocked: 0

## Gaps

- truth: "User gives LTHR directly → it is used as-is, no tool call needed (D-05 Branch A)"
  status: failed
  reason: "Live test: trust scanner's attribution mechanism only recognizes tool-result-sourced numbers as legitimate. A user's own self-reported LTHR, echoed/confirmed by the LLM in the same or a later turn, has no attribution path since no tool call occurs for this branch (by design). scan_buffer flags it as an unattributed physiological number every time, exhausting retries and returning an empty response. This is a structural gap, not a flake: the branch is guaranteed to fail on every attempt, for every user who directly states their LTHR."
  severity: blocker
  test: 1
  artifacts: [backend/agent/trust.py, backend/routes/onboarding.py, backend/agent/loop.py]
  missing: ["A mechanism for scan_buffer / _is_attributed to recognize a number as sourced when it was self-reported by the user in the conversation (not computed by a tool), distinct from the LLM-invention case TRUST-03 exists to catch."]
