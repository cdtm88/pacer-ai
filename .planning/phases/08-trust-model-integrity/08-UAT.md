---
status: testing
phase: 08-trust-model-integrity
source: [08-VERIFICATION.md]
started: 2026-07-04T00:00:00Z
updated: 2026-07-04T00:00:00Z
---

## Current Test

number: 1
name: Live onboarding conversation exercises all 3 HR-baseline branches (ONBD-05)
expected: |
  Run a real onboarding interview three times (or three branches within the flow) and confirm:
  (a) User states LTHR directly → it is used as-is, no tool call needed.
  (b) User gives max HR only → the LLM calls `estimate_lthr_from_max_hr`, and the returned
      value (not an LLM-invented number) is what gets used for HR zones / persisted as
      `lthr_estimate`.
  (c) User knows neither LTHR nor max HR → `hr_zones_available = false` is persisted, no
      HR-zone-based targets appear in the resulting plan, and the RPE-only cold-start path
      is used instead.
  In all three cases, the LLM must never state a fabricated LTHR/HR-zone number in chat.
awaiting: user response

## Tests

### 1. Live onboarding conversation exercises all 3 HR-baseline branches (ONBD-05)
expected: See above — three branches (direct LTHR / max-HR estimate / neither known), correct tool usage and profile persistence in each, no invented numbers.
result: [pending]

## Summary

total: 1
passed: 0
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps
