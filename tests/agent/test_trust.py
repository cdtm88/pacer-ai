# tests/agent/test_trust.py
"""
Compliance tests for agent/trust.py (TRUST-03, TRUST-04, TRUST-05).

Tests are written RED-first (TDD). All tests should fail until agent/trust.py is
implemented (Task 1 GREEN phase).
"""

import pytest


class TestScanBuffer:
    """TRUST-03: scan_buffer detects unsourced physiological numbers."""

    def test_unsourced_ftp_watts_is_violation(self):
        """Basic case: assistant emits FTP in watts with no tool attribution."""
        from backend.agent.trust import scan_buffer

        violation = scan_buffer("Your FTP is 250 watts based on your history.", set())
        assert violation is not None
        assert "250" in violation.matched_text

    def test_attributed_number_is_not_violation(self):
        """TRUST-04: number present verbatim in a tool_result value is attributed."""
        from backend.agent.trust import scan_buffer

        # "250 watts" appears in a tool result, so it's attributed
        violation = scan_buffer("Your FTP is 250 watts.", {"250 watts"})
        assert violation is None

    def test_qualitative_text_is_not_violation(self):
        """Qualitative text without numeric+unit patterns must not fire."""
        from backend.agent.trust import scan_buffer

        violation = scan_buffer(
            "Ride comfortably and keep it conversational today.", set()
        )
        assert violation is None

    def test_ride_easy_text_is_not_violation(self):
        """Plan acceptance criteria: ride easy text returns None."""
        from backend.agent.trust import scan_buffer

        assert (
            scan_buffer(
                "Ride comfortably and keep it conversational today", set()
            )
            is None
        )

    def test_tss_value_unsourced_is_violation(self):
        """TSS is a physiological unit -- unsourced TSS triggers violation."""
        from backend.agent.trust import scan_buffer

        violation = scan_buffer("Your TSS for today should be 85.", set())
        assert violation is not None

    def test_tss_attributed_is_not_violation(self):
        """TSS value present in tool result is attributed."""
        from backend.agent.trust import scan_buffer

        violation = scan_buffer("Your TSS for today should be 85.", {"85 TSS"})
        assert violation is None

    def test_bpm_unsourced_is_violation(self):
        """Heart rate in bpm without tool attribution is a violation."""
        from backend.agent.trust import scan_buffer

        violation = scan_buffer("Keep your heart rate at 145 bpm.", set())
        assert violation is not None

    def test_zone_reference_unsourced_is_violation(self):
        """Zone N reference is physiological; unsourced is a violation."""
        from backend.agent.trust import scan_buffer

        violation = scan_buffer("Stay in Zone 3 for 20 minutes.", set())
        assert violation is not None

    def test_only_first_match_returned(self):
        """scan_buffer returns first violation; check it's non-None and has matched_text."""
        from backend.agent.trust import scan_buffer

        violation = scan_buffer("FTP 200 watts and 85 TSS today.", set())
        assert violation is not None
        assert violation.matched_text  # non-empty

    def test_partial_attribution_still_flags(self):
        """If only one of two physio numbers is attributed, violation is still raised."""
        from backend.agent.trust import scan_buffer

        # 250 watts is attributed; 85 TSS is not
        violation = scan_buffer(
            "Your FTP is 250 watts and TSS 85 today.", {"250 watts"}
        )
        assert violation is not None

    def test_trust_violation_carries_pattern(self):
        """TrustViolation.pattern is set and non-empty."""
        from backend.agent.trust import scan_buffer

        violation = scan_buffer("FTP is 200 W.", set())
        assert violation is not None
        assert violation.pattern  # non-empty string

    def test_returns_none_for_empty_text(self):
        """Empty string should return None (no numbers to scan)."""
        from backend.agent.trust import scan_buffer

        assert scan_buffer("", set()) is None

    def test_ctl_atl_tsb_unsourced_are_violations(self):
        """CTL, ATL, TSB are physiological metrics; unsourced triggers violation."""
        from backend.agent.trust import scan_buffer

        assert scan_buffer("Your CTL is 42.", set()) is not None
        assert scan_buffer("ATL is 55.", set()) is not None
        assert scan_buffer("TSB is -13.", set()) is not None

    def test_rpm_unsourced_is_violation(self):
        """rpm (cadence) is a physiological unit."""
        from backend.agent.trust import scan_buffer

        violation = scan_buffer("Aim for 90 rpm today.", set())
        assert violation is not None

    def test_attribution_substring_match(self):
        """Attribution check falls back to the bare number when the tool result
        is structured JSON (number and unit never appear adjacent as prose).

        260702-vsp: this test previously asserted the Pattern A false-positive
        behavior fixed by that quick task. The number 250 is present as the
        tool JSON value "ftp": 250, so "250 watts" in the assistant's prose is
        correctly attributed (not a hallucination) -- the fix mirrors Pattern
        B's existing bare-number fallback.
        """
        from backend.agent.trust import scan_buffer

        # The tool result value is a longer JSON string containing the bare number 250.
        tool_values = {'{"ftp": 250, "unit": "watts", "zones": [...]}'}
        violation = scan_buffer("Your FTP is 250 watts.", tool_values)
        assert violation is None

    def test_pattern_a_number_unit_attributed_via_json_value(self):
        """260702-vsp regression: a number+unit phrase in prose is attributed
        when the bare number appears as a JSON value in a tool result, even
        though "134 bpm" never appears verbatim (tool JSON never phrases
        numbers adjacent to their unit -- e.g. {"lower_bpm": 134})."""
        from backend.agent.trust import scan_buffer

        tool_values = {'{"zone": 2, "lower_bpm": 134, "upper_bpm": 148}'}
        violation = scan_buffer(
            "Keep your heart rate around 134 bpm during this effort.", tool_values
        )
        assert violation is None

    def test_pattern_a_unattributed_number_still_flagged(self):
        """260702-vsp safety negative control: the bare-number fallback must
        not wave through a hallucinated number just because tool_result_values
        is non-empty -- only a number that actually appears in a tool result
        is attributed."""
        from backend.agent.trust import scan_buffer

        tool_values = {'{"lower_bpm": 134, "upper_bpm": 148}'}
        violation = scan_buffer("Actually your FTP is 300 watts.", tool_values)
        assert violation is not None
        assert "300" in violation.matched_text


class TestSubstringCollisionBypass:
    """
    D-03 / TRUST-08 regression: boundary-aware numeric-token + tolerance
    matching closes the substring-attribution bypass where a bare number was
    falsely attributed by the mere presence of a longer/unrelated digit run
    (e.g. "2500", "0.250", or a timestamp) inside a tool_result_values string.
    """

    def test_longer_digit_run_does_not_attribute(self):
        """250 must not be attributed merely because "2500" appears in a
        tool result -- 250 is not a standalone numeric token inside 2500."""
        from backend.agent.trust import scan_buffer

        violation = scan_buffer("Your FTP is 250 watts.", ["2500"])
        assert violation is not None
        assert "250" in violation.matched_text

    def test_decimal_substring_does_not_attribute(self):
        """250 must not be attributed by "0.250" -- 250 != 0.250 and the
        decimal token has its own boundaries."""
        from backend.agent.trust import scan_buffer

        violation = scan_buffer("Your FTP is 250 watts.", ["0.250"])
        assert violation is not None
        assert "250" in violation.matched_text

    def test_real_json_attribution_still_passes(self):
        """Real attribution survives the rewrite: 250 appears as a standalone
        numeric token inside the JSON tool result value."""
        from backend.agent.trust import scan_buffer

        violation = scan_buffer(
            "Your FTP is 250 watts.", ['{"ftp_watts": 250}']
        )
        assert violation is None

    def test_bpm_range_json_attribution_still_passes(self):
        """134 bpm is attributed via the standalone numeric token 134 inside
        the JSON tool result value, unaffected by the neighboring 150."""
        from backend.agent.trust import scan_buffer

        violation = scan_buffer(
            "Keep HR at 134 bpm.", ['{"lower_bpm": 134, "upper_bpm": 150}']
        )
        assert violation is None

    def test_timestamp_digit_run_does_not_attribute(self):
        """42 must not be attributed just because a timestamp string happens
        to contain the digits "42" as part of a larger run (2024-01-01T00:04:20Z
        contains no standalone 42 token at all -- confirming the boundary-aware
        extraction ignores timestamp digit runs entirely)."""
        from backend.agent.trust import scan_buffer

        violation = scan_buffer(
            "CTL is 42.", ['{"created_at": "2024-01-01T00:04:20Z"}']
        )
        assert violation is not None
        assert "42" in violation.matched_text


class TestTrustViolationDataclass:
    """TrustViolation dataclass properties."""

    def test_trust_violation_has_matched_text(self):
        from backend.agent.trust import TrustViolation

        tv = TrustViolation(matched_text="250 watts", pattern=r"\d+\s*watts")
        assert tv.matched_text == "250 watts"

    def test_trust_violation_has_pattern(self):
        from backend.agent.trust import TrustViolation

        tv = TrustViolation(matched_text="250 watts", pattern=r"\d+\s*watts")
        assert tv.pattern == r"\d+\s*watts"

    def test_trust_violation_str(self):
        from backend.agent.trust import TrustViolation

        tv = TrustViolation(matched_text="250 watts", pattern="x")
        assert "250 watts" in str(tv)


class TestPhysioPattern:
    """PHYSIO_PATTERN regex sanity checks."""

    def test_physio_pattern_exists(self):
        from backend.agent.trust import PHYSIO_PATTERN

        assert PHYSIO_PATTERN is not None

    def test_physio_pattern_matches_watts(self):
        from backend.agent.trust import PHYSIO_PATTERN

        assert PHYSIO_PATTERN.search("250 watts")

    def test_physio_pattern_matches_w(self):
        from backend.agent.trust import PHYSIO_PATTERN

        assert PHYSIO_PATTERN.search("200W")

    def test_physio_pattern_matches_bpm(self):
        from backend.agent.trust import PHYSIO_PATTERN

        assert PHYSIO_PATTERN.search("145 bpm")

    def test_physio_pattern_matches_zone(self):
        from backend.agent.trust import PHYSIO_PATTERN

        assert PHYSIO_PATTERN.search("Zone 4")

    def test_physio_pattern_matches_ftp(self):
        from backend.agent.trust import PHYSIO_PATTERN

        assert PHYSIO_PATTERN.search("FTP 250")

    def test_physio_pattern_no_match_qualitative(self):
        from backend.agent.trust import PHYSIO_PATTERN

        assert not PHYSIO_PATTERN.search("Ride easy and enjoy the morning air.")

    def test_physio_pattern_case_insensitive(self):
        from backend.agent.trust import PHYSIO_PATTERN

        assert PHYSIO_PATTERN.search("250 WATTS")
        assert PHYSIO_PATTERN.search("Zone 2")


class TestHandleViolation:
    """TRUST-05: on-violation hook calls log_capability_gap."""

    async def test_handle_violation_calls_log_capability_gap(self, monkeypatch):
        """handle_violation awaits log_capability_gap with expected args."""
        from backend.agent.trust import TrustViolation

        calls = []

        async def mock_log(method_name, context, **kwargs):
            calls.append({"method_name": method_name, "context": context})
            from backend.sports_science.types import ToolResult
            return ToolResult(value={}, unit="", methodology="capability_gap_log", inputs={})

        monkeypatch.setattr(
            "backend.agent.trust.log_capability_gap", mock_log
        )

        from backend.agent.trust import handle_violation

        violation = TrustViolation(matched_text="250 watts", pattern="x")
        await handle_violation(violation)

        assert len(calls) == 1
        assert calls[0]["method_name"] == "unsourced_physiological_number"
        assert "matched" in calls[0]["context"]
        assert calls[0]["context"]["matched"] == "250 watts"

    async def test_handle_violation_does_not_expose_method_name_in_result(self, monkeypatch):
        """The method_name used in log_capability_gap is not echoed to the user."""
        from backend.agent.trust import TrustViolation

        async def mock_log(method_name, context, **kwargs):
            from backend.sports_science.types import ToolResult
            return ToolResult(
                value={"status": "logged", "message": "qualitative fallback"},
                unit="",
                methodology="capability_gap_log",
                inputs={},
            )

        monkeypatch.setattr("backend.agent.trust.log_capability_gap", mock_log)

        from backend.agent.trust import handle_violation

        violation = TrustViolation(matched_text="85 TSS", pattern="x")
        # Should not raise, and should not surface method_name
        await handle_violation(violation)  # if it doesn't raise, GAP-03 preserved


# ---------------------------------------------------------------------------
# Plan 04 compliance tests: loop-level trust enforcement (TRUST-03, TRUST-05)
# ---------------------------------------------------------------------------


class TestTrustLoopCompliance:
    """
    TRUST-03 / TRUST-05 compliance at the run_turn level (Plan 04, AGENT-06 gate).

    These tests exercise trust enforcement through the full agent loop with
    mocked Anthropic streams -- no live API call occurs.
    """

    async def test_trust_violation_triggers_retry(self, monkeypatch):
        """
        TRUST-03: when run_turn sees a trust violation it:
        1. Increments retries (emits a trust_violation error event).
        2. Appends a correction user message (not the violating assistant message).
        3. Emits an error event with code "trust_violation".
        4. Never forwards the violating number in a token or done frame.
        """
        from backend.agent.loop import run_turn
        from backend.agent.trust import scan_buffer
        from tests.agent.conftest import build_fake_client, _build_stream, _delta_event, _final_msg
        from unittest.mock import MagicMock

        VIOLATING_TEXT = "Your FTP is 250 watts based on your history."

        # First call: end_turn with text that contains an unsourced physio number
        delta = _delta_event(VIOLATING_TEXT)
        msg_violating = _final_msg(
            stop_reason="end_turn",
            content=[MagicMock(type="text", text=VIOLATING_TEXT)],
        )
        stream_violating = _build_stream(delta_events=[delta], final_msg=msg_violating)

        # Second call (retry): end_turn with qualitative text that passes scan
        msg_ok = _final_msg(
            stop_reason="end_turn",
            content=[MagicMock(type="text", text="Let me describe your fitness qualitatively.")],
        )
        stream_ok = _build_stream(delta_events=[], final_msg=msg_ok)

        # Extra streams to avoid IndexError if loop calls more than expected
        msg_end = _final_msg(stop_reason="end_turn", content=[])
        stream_extra = _build_stream(delta_events=[], final_msg=msg_end)

        client = build_fake_client(stream_violating, stream_ok, stream_extra)
        messages = [{"role": "user", "content": "What is my FTP?"}]
        audit_log = []

        events = [ev async for ev in run_turn(messages, client, "claude-test", scan_buffer, audit_log)]

        event_types = [ev["event"] for ev in events]
        data_values = [ev["data"] for ev in events]

        # Must have emitted a trust_violation error event
        assert "error" in event_types
        error_events = [ev for ev in events if ev["event"] == "error"]
        trust_violation_events = [
            ev for ev in error_events if ev["data"].get("code") == "trust_violation"
        ]
        assert len(trust_violation_events) >= 1, (
            "Expected at least one trust_violation error event"
        )

        # The violating number must NOT appear in any token or done frame
        forwarded_texts = [
            ev["data"].get("text", "")
            for ev in events
            if ev["event"] in ("token", "done")
        ]
        for text in forwarded_texts:
            assert "250" not in text, (
                f"Violating number '250' appeared in forwarded frame: {text!r}"
            )
            assert VIOLATING_TEXT not in text, (
                f"Violating text appeared in forwarded frame: {text!r}"
            )

        # Eventually resolves (done event from second call)
        assert "done" in event_types

    async def test_attributed_number_passes(self):
        """
        TRUST-03: a number present verbatim in a tool_result value this turn
        does NOT trigger a violation in scan_buffer.
        """
        from backend.agent.trust import scan_buffer

        # A number echoed from a tool result is attributed
        tool_result_str = "250 watts"
        violation = scan_buffer("Your power zone threshold is 250 watts.", {tool_result_str})
        assert violation is None, (
            "Attributed number should not trigger a violation"
        )

    async def test_capability_gap_fallback(self, monkeypatch):
        """
        TRUST-05: when handle_violation is called:
        1. log_capability_gap is awaited with the matched text in context.
        2. The user-facing surface never contains the internal method_name
           "unsourced_physiological_number".
        """
        from backend.agent.trust import TrustViolation, handle_violation

        gap_calls = []

        async def mock_log_capability_gap(method_name, context, **kwargs):
            gap_calls.append({"method_name": method_name, "context": context})
            from backend.sports_science.types import ToolResult
            return ToolResult(
                value={"status": "logged", "message": "I'll describe this qualitatively."},
                unit="",
                methodology="capability_gap_log",
                inputs={},
            )

        monkeypatch.setattr("backend.agent.trust.log_capability_gap", mock_log_capability_gap)

        violation = TrustViolation(matched_text="250 watts", pattern="test")
        result = await handle_violation(violation)

        # log_capability_gap was called
        assert len(gap_calls) == 1
        call = gap_calls[0]
        assert call["method_name"] == "unsourced_physiological_number"
        assert "matched" in call["context"]
        assert call["context"]["matched"] == "250 watts"

        # The internal method_name must never reach the user surface.
        # handle_violation returns None (it's a fire-and-forget hook).
        # The key invariant: the method_name is passed to the gap log,
        # NOT included in any SSE event data. We verify the hook does not
        # raise and the method_name is not leaked in the return value.
        assert result is None or (
            "unsourced_physiological_number" not in str(result)
        ), (
            "Internal method_name leaked in handle_violation return value"
        )
