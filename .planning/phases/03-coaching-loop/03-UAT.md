---
status: testing
phase: 03-coaching-loop
source: [03-VERIFICATION.md]
started: 2026-06-20T00:00:00Z
updated: 2026-06-20T00:00:00Z
---

## Current Test

number: 1
name: ONBD-04 Confirmation Gate — Live LLM Adherence
expected: |
  Run a full onboarding interview against the real API. Confirm that
  save_profile does NOT appear in the SSE stream before the user has
  sent an explicit approval message (e.g. "yes", "looks good", "correct")
  after the agent presents the "Here is what I have" summary.
awaiting: user response

## Tests

### 1. ONBD-04 Confirmation Gate — Live LLM Adherence

expected: |
  POST /onboarding/start → run the interview to completion.
  After the agent presents "Here is what I have" summary, do NOT
  send an approval yet — confirm no save_profile tool_start event
  appears in the stream. Then send "looks good" and confirm
  save_profile appears only after that approval message.
result: [pending]

## Summary

total: 1
passed: 0
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps
