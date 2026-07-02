---
phase: quick-260702-vsp
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/agent/trust.py
  - tests/agent/test_trust.py
autonomous: true
requirements: [TRUST-04, TRUST-03]
must_haves:
  truths:
    - "scan_buffer('...134 bpm...', {json blob containing 134}) returns None (Pattern A false positive fixed)"
    - "scan_buffer('...300 watts...', {json blob NOT containing 300}) still returns a TrustViolation (hallucinated number still caught)"
    - "All tests in tests/agent/test_trust_corpus.py still pass (zero false negatives / zero false positives preserved)"
    - "Every tests/agent/test_trust.py test passes; the one test that asserted the buggy behavior is updated with justification"
  artifacts:
    - backend/agent/trust.py
    - tests/agent/test_trust.py
  key_links:
    - "bare-number extraction from Pattern A matched text via re.match on the leading digits"
    - "Pattern A attribution candidate list [matched, bare_number] checked against tool_result_values, mirroring Pattern B's [full_match, synthetic, num]"
---

<objective>
Fix the trust scanner Pattern A false positive: physio number+unit matches (e.g. "134 bpm") can never attribute against tool_result JSON, because tool output serializes numbers as `"lower_bpm": 134`, never as the adjacent phrase "134 bpm". Add a bare-number attribution fallback to Pattern A in `scan_buffer`, mirroring Pattern B's existing `[full_match, synthetic, num]` fallback list.

Purpose: A live production Playwright E2E test proved that after `calculate_hr_zones` / `generate_plan` returned zone JSON containing `"lower_bpm": 134`, the agent's prose reference to "134 bpm" was flagged as a `TrustViolation` on every retry, hitting `max_retries (3) exceeded` and erroring the SSE stream — completely blocking the onboarding confirmation flow from ever completing. This is TRUST-04 (attributed numbers must not be flagged as violations).

Output: A surgical change to Pattern A's attribution check in `backend/agent/trust.py`, plus a locked-in regression test and a safety negative-control test in `tests/agent/test_trust.py`.
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
</execution_context>

<context>
@backend/agent/trust.py
@tests/agent/test_trust.py
@tests/agent/test_trust_corpus.py
@tests/agent/fixtures/trust_corpus.py

Key facts already established by planning analysis (do not re-derive):
- Pattern B (lines ~130-153 in trust.py) already has the correct fallback: it checks `[full_match, synthetic, num]` against each tool_result_value, where `num` is the bare number. Pattern A (lines ~121-127) only checks the full `matched` string — this asymmetry is the entire bug.
- Every VIOLATIONS entry in the corpus is scanned with `scan_buffer(text, set())` (empty tool_result_values). A bare-number fallback can therefore NEVER cause a corpus VIOLATION to stop being detected — the fallback has nothing to match against when the value set is empty. All corpus false-negative guarantees are unaffected.
- The QUALITATIVE and ATTRIBUTED corpus sets are likewise unaffected (QUALITATIVE has no number+unit; ATTRIBUTED already passes via verbatim phrase match, and the fallback only ever makes attribution MORE permissive on already-passing cases).
- Blast radius: the naive bare-number-in-blob fallback gives Pattern A EXACTLY the same attribution looseness Pattern B already has — not worse. Pattern B's pre-existing looseness (a bare digit coinciding in an unrelated JSON value) is a KNOWN, OUT-OF-SCOPE pre-existing risk per the task constraints. Do not attempt to tighten Pattern B, and do not introduce a more precise (unit-key-aware) fallback for Pattern A — it would be scope creep and is unnecessary because no corpus test requires it.
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add regression + safety tests to test_trust.py; correct the one test that asserts the bug (RED)</name>
  <files>tests/agent/test_trust.py</files>
  <behavior>
    - New test `test_pattern_a_number_unit_attributed_via_json_value` (in class TestScanBuffer): text "Keep your heart rate around 134 bpm during this effort." with tool_result_values `{'{"zone": 2, "lower_bpm": 134, "upper_bpm": 148}'}` must return None. This reproduces the exact live false positive: "134 bpm" is never a verbatim substring of the JSON, but the bare number 134 IS a tool_result value, so it is attributed. Currently FAILS (RED) — current code returns a violation.
    - New test `test_pattern_a_unattributed_number_still_flagged` (safety negative control, in TestScanBuffer): text "Actually your FTP is 300 watts." with tool_result_values `{'{"lower_bpm": 134, "upper_bpm": 148}'}` must return a TrustViolation whose matched_text contains "300". 300 appears nowhere in the tool values, so the bare-number fallback must NOT wave it through. Currently PASSES and must STAY green through the fix — this locks the safety property that a hallucinated number is still caught even with a non-empty value set.
    - UPDATE existing `test_attribution_substring_match` (lines ~126-137): its assertion currently encodes the buggy behavior (asserts `violation is not None` when 250 is present as the JSON value `"ftp": 250` but phrased as "250 watts"). This is the identical shape as the production bug. Invert it to assert `violation is None`, and rewrite the docstring/comments to state the corrected semantics: a number present as a JSON value in a tool result IS attributed even when the text phrases it as "number unit". Reference this fix (260702-vsp) in the docstring so the change is auditable. Currently the updated assertion FAILS (RED) on current code.
  </behavior>
  <action>
    Add the two new tests to the TestScanBuffer class in tests/agent/test_trust.py, following the existing style exactly (per-test local `from backend.agent.trust import scan_buffer`, plain asserts, concise docstring). Use the tool_result_values shapes given in <behavior> verbatim.

    Then update `test_attribution_substring_match`: change its assertion from `assert violation is not None` to `assert violation is None`, and replace its inline comments/docstring with a note that the number 250 is present as the tool JSON value `"ftp": 250` and is therefore correctly attributed (not a hallucination). Explicitly justify the change in the docstring: this test previously asserted the Pattern A false-positive behavior that quick task 260702-vsp fixes; the corrected expectation is that a JSON-valued number is attributed.

    Do NOT modify any other test in this file. Do NOT touch test_trust_corpus.py or the corpus fixtures.
  </action>
  <verify>
    <automated>.venv/bin/pytest tests/agent/test_trust.py -k "attributed_via_json_value or attribution_substring_match" -v</automated>
  </verify>
  <done>Both selected tests FAIL against the unmodified trust.py (RED), confirming they capture the bug. The rest of the file is unchanged. `test_pattern_a_unattributed_number_still_flagged` passes on current code.</done>
</task>

<task type="auto">
  <name>Task 2: Add bare-number attribution fallback to Pattern A in scan_buffer (GREEN)</name>
  <files>backend/agent/trust.py</files>
  <action>
    In `scan_buffer`, inside the Pattern A loop (currently lines ~121-127), after `matched = match.group(0).strip()`, extract the leading bare number from `matched` using `re.match(r"\d+(?:\.\d+)?", matched)` and take group 0; fall back to `matched` itself if (defensively) no leading-number match is found. Then replace the attribution condition `if not any(matched in val for val in tool_result_values):` with a check across a candidate list containing BOTH the full `matched` string AND the extracted bare number, mirroring Pattern B's `[full_match, synthetic, num]` construction at lines ~144-148 (e.g. `if not any(s in val for val in tool_result_values for s in (matched, bare_number)):`). Keep the returned `TrustViolation(matched_text=matched, pattern=PHYSIO_PATTERN_A.pattern)` unchanged so matched_text stays the tight number+unit string.

    Do NOT modify PHYSIO_PATTERN_A, PHYSIO_PATTERN_B, or PHYSIO_PATTERN — the detection regexes and their matched spans must be unchanged; only the attribution decision after a match is found changes. Do NOT touch Pattern B's loop, handle_violation, the module docstring beyond a one-line note if helpful, or any file outside backend/agent/trust.py. Do NOT edit backend/routes/onboarding.py or backend/agent/loop.py.

    Rationale to preserve: the bare-number fallback gives Pattern A the same attribution blast radius Pattern B already has (no worse). It cannot cause any corpus VIOLATION to be missed because every corpus VIOLATION is scanned with an empty tool_result_values set.
  </action>
  <verify>
    <automated>.venv/bin/pytest tests/agent/test_trust.py tests/agent/test_trust_corpus.py -v</automated>
  </verify>
  <done>All tests in both test_trust.py (including the two new tests and the updated test_attribution_substring_match) and test_trust_corpus.py pass (GREEN). No regression regex or Pattern B logic was touched.</done>
</task>

<task type="auto">
  <name>Task 3: Run broader backend suite, then commit and push trust.py + test file to main</name>
  <files>backend/agent/trust.py, tests/agent/test_trust.py</files>
  <action>
    Run the full backend test suite to catch any indirect breakage: `.venv/bin/pytest tests/ -q`. All tests must pass. If any unrelated pre-existing failure appears that is clearly not caused by this change, note it in the summary but do not fix it (out of scope).

    Then stage ONLY the two files this task changed — `backend/agent/trust.py` and `tests/agent/test_trust.py` — and commit. Do NOT stage or commit any other working-tree changes (.gitignore, .planning/PROJECT.md, node_modules/, test-ride.fit, docs/, .planning/ui-reviews/). Commit message: `fix(trust): attribute Pattern A number+unit via bare-number fallback (260702-vsp)`. Push directly to origin/main (pre-approved for this session — backend-only change, auto-deploys via the Vercel Python function). Confirm the commit reached origin/main.

    Do NOT attempt to drive a browser-based onboarding flow — live E2E verification of the deployed fix happens separately in an ongoing Playwright session after this deploy.
  </action>
  <verify>
    <automated>.venv/bin/pytest tests/ -q && git log origin/main -1 --oneline | grep -q 260702-vsp && echo PUSHED_OK</automated>
  </verify>
  <done>Full `tests/` suite passes; commit for 260702-vsp exists on origin/main containing only backend/agent/trust.py and tests/agent/test_trust.py; no unrelated working-tree files were staged.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| LLM-generated text → user (SSE stream) | `scan_buffer` is the enforcement gate ensuring no physiological number reaches the user unless it was produced by an authoritative tool this turn. This change modifies the gate's attribution decision. |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-vsp-01 | Spoofing | scan_buffer Pattern A attribution | high | mitigate | A hallucinated (LLM-invented) physio number must not be waved through by the new bare-number fallback. Mitigated by `test_pattern_a_unattributed_number_still_flagged` (Task 1): a number absent from tool_result_values is still flagged even with a non-empty value set. |
| T-vsp-02 | Tampering | attribution loosening blast radius | medium | accept | Naive bare-number-in-blob fallback can, in principle, attribute a hallucinated digit that coincidentally appears in an unrelated JSON value (e.g. a timestamp). Accepted because this is IDENTICAL to Pattern B's pre-existing behavior (out of scope per task constraints) — Pattern A's blast radius is made equal to, not worse than, Pattern B's. Corpus false-negative guarantee is unaffected (VIOLATIONS use empty value sets). |
| T-vsp-SC | Tampering | package installs | low | accept | No npm/pip/cargo installs in this task; no new dependencies. Supply-chain surface unchanged. |
</threat_model>

<verification>
- `.venv/bin/pytest tests/agent/test_trust.py tests/agent/test_trust_corpus.py -v` — all pass (unit + corpus, the ground truth for genuine-violation detection).
- `.venv/bin/pytest tests/ -q` — full backend suite passes (no indirect breakage).
- New regression test proves the 134-bpm-in-JSON false positive is fixed.
- Safety negative-control test proves a hallucinated 300 watts (absent from tool values) is still flagged.
- Commit for 260702-vsp on origin/main touches only backend/agent/trust.py and tests/agent/test_trust.py.
</verification>

<success_criteria>
- Pattern A attribution accepts a bare-number match against tool_result_values, mirroring Pattern B.
- No change to PHYSIO_PATTERN_A / PHYSIO_PATTERN_B / PHYSIO_PATTERN regexes, Pattern B's loop, or handle_violation.
- Both trust test suites pass; the single test that asserted the buggy behavior (`test_attribution_substring_match`) is updated with documented justification.
- Change committed and pushed to origin/main; only the two intended files staged.
</success_criteria>

<output>
Create `.planning/quick/260702-vsp-fix-trust-scanner-pattern-a-false-positi/260702-vsp-SUMMARY.md` when done.
</output>
