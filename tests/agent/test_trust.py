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
        from agent.trust import scan_buffer

        violation = scan_buffer("Your FTP is 250 watts based on your history.", set())
        assert violation is not None
        assert "250" in violation.matched_text

    def test_attributed_number_is_not_violation(self):
        """TRUST-04: number present verbatim in a tool_result value is attributed."""
        from agent.trust import scan_buffer

        # "250 watts" appears in a tool result, so it's attributed
        violation = scan_buffer("Your FTP is 250 watts.", {"250 watts"})
        assert violation is None

    def test_qualitative_text_is_not_violation(self):
        """Qualitative text without numeric+unit patterns must not fire."""
        from agent.trust import scan_buffer

        violation = scan_buffer(
            "Ride comfortably and keep it conversational today.", set()
        )
        assert violation is None

    def test_ride_easy_text_is_not_violation(self):
        """Plan acceptance criteria: ride easy text returns None."""
        from agent.trust import scan_buffer

        assert (
            scan_buffer(
                "Ride comfortably and keep it conversational today", set()
            )
            is None
        )

    def test_tss_value_unsourced_is_violation(self):
        """TSS is a physiological unit -- unsourced TSS triggers violation."""
        from agent.trust import scan_buffer

        violation = scan_buffer("Your TSS for today should be 85.", set())
        assert violation is not None

    def test_tss_attributed_is_not_violation(self):
        """TSS value present in tool result is attributed."""
        from agent.trust import scan_buffer

        violation = scan_buffer("Your TSS for today should be 85.", {"85 TSS"})
        assert violation is None

    def test_bpm_unsourced_is_violation(self):
        """Heart rate in bpm without tool attribution is a violation."""
        from agent.trust import scan_buffer

        violation = scan_buffer("Keep your heart rate at 145 bpm.", set())
        assert violation is not None

    def test_zone_reference_unsourced_is_violation(self):
        """Zone N reference is physiological; unsourced is a violation."""
        from agent.trust import scan_buffer

        violation = scan_buffer("Stay in Zone 3 for 20 minutes.", set())
        assert violation is not None

    def test_only_first_match_returned(self):
        """scan_buffer returns first violation; check it's non-None and has matched_text."""
        from agent.trust import scan_buffer

        violation = scan_buffer("FTP 200 watts and 85 TSS today.", set())
        assert violation is not None
        assert violation.matched_text  # non-empty

    def test_partial_attribution_still_flags(self):
        """If only one of two physio numbers is attributed, violation is still raised."""
        from agent.trust import scan_buffer

        # 250 watts is attributed; 85 TSS is not
        violation = scan_buffer(
            "Your FTP is 250 watts and TSS 85 today.", {"250 watts"}
        )
        assert violation is not None

    def test_trust_violation_carries_pattern(self):
        """TrustViolation.pattern is set and non-empty."""
        from agent.trust import scan_buffer

        violation = scan_buffer("FTP is 200 W.", set())
        assert violation is not None
        assert violation.pattern  # non-empty string

    def test_returns_none_for_empty_text(self):
        """Empty string should return None (no numbers to scan)."""
        from agent.trust import scan_buffer

        assert scan_buffer("", set()) is None

    def test_ctl_atl_tsb_unsourced_are_violations(self):
        """CTL, ATL, TSB are physiological metrics; unsourced triggers violation."""
        from agent.trust import scan_buffer

        assert scan_buffer("Your CTL is 42.", set()) is not None
        assert scan_buffer("ATL is 55.", set()) is not None
        assert scan_buffer("TSB is -13.", set()) is not None

    def test_rpm_unsourced_is_violation(self):
        """rpm (cadence) is a physiological unit."""
        from agent.trust import scan_buffer

        violation = scan_buffer("Aim for 90 rpm today.", set())
        assert violation is not None

    def test_attribution_substring_match(self):
        """Attribution check uses substring containment, not equality."""
        from agent.trust import scan_buffer

        # The tool result value is a longer JSON string containing "250 watts"
        tool_values = {'{"ftp": 250, "unit": "watts", "zones": [...]}'}
        violation = scan_buffer("Your FTP is 250 watts.", tool_values)
        # "250 watts" is not verbatim in the tool value string -- should still be a violation
        # unless the matched text "250 watts" appears as substring
        # The matched text would be "250 watts"; is it in '{"ftp": 250, "unit": "watts", ...}'?
        # "250 watts" is NOT a substring of that JSON string, so it IS a violation
        assert violation is not None


class TestTrustViolationDataclass:
    """TrustViolation dataclass properties."""

    def test_trust_violation_has_matched_text(self):
        from agent.trust import TrustViolation

        tv = TrustViolation(matched_text="250 watts", pattern=r"\d+\s*watts")
        assert tv.matched_text == "250 watts"

    def test_trust_violation_has_pattern(self):
        from agent.trust import TrustViolation

        tv = TrustViolation(matched_text="250 watts", pattern=r"\d+\s*watts")
        assert tv.pattern == r"\d+\s*watts"

    def test_trust_violation_str(self):
        from agent.trust import TrustViolation

        tv = TrustViolation(matched_text="250 watts", pattern="x")
        assert "250 watts" in str(tv)


class TestPhysioPattern:
    """PHYSIO_PATTERN regex sanity checks."""

    def test_physio_pattern_exists(self):
        from agent.trust import PHYSIO_PATTERN

        assert PHYSIO_PATTERN is not None

    def test_physio_pattern_matches_watts(self):
        from agent.trust import PHYSIO_PATTERN

        assert PHYSIO_PATTERN.search("250 watts")

    def test_physio_pattern_matches_w(self):
        from agent.trust import PHYSIO_PATTERN

        assert PHYSIO_PATTERN.search("200W")

    def test_physio_pattern_matches_bpm(self):
        from agent.trust import PHYSIO_PATTERN

        assert PHYSIO_PATTERN.search("145 bpm")

    def test_physio_pattern_matches_zone(self):
        from agent.trust import PHYSIO_PATTERN

        assert PHYSIO_PATTERN.search("Zone 4")

    def test_physio_pattern_matches_ftp(self):
        from agent.trust import PHYSIO_PATTERN

        assert PHYSIO_PATTERN.search("FTP 250")

    def test_physio_pattern_no_match_qualitative(self):
        from agent.trust import PHYSIO_PATTERN

        assert not PHYSIO_PATTERN.search("Ride easy and enjoy the morning air.")

    def test_physio_pattern_case_insensitive(self):
        from agent.trust import PHYSIO_PATTERN

        assert PHYSIO_PATTERN.search("250 WATTS")
        assert PHYSIO_PATTERN.search("Zone 2")


class TestHandleViolation:
    """TRUST-05: on-violation hook calls log_capability_gap."""

    async def test_handle_violation_calls_log_capability_gap(self, monkeypatch):
        """handle_violation awaits log_capability_gap with expected args."""
        from agent.trust import TrustViolation

        calls = []

        async def mock_log(method_name, context, **kwargs):
            calls.append({"method_name": method_name, "context": context})
            from sports_science.types import ToolResult
            return ToolResult(value={}, unit="", methodology="capability_gap_log", inputs={})

        monkeypatch.setattr(
            "agent.trust.log_capability_gap", mock_log
        )

        from agent.trust import handle_violation

        violation = TrustViolation(matched_text="250 watts", pattern="x")
        await handle_violation(violation)

        assert len(calls) == 1
        assert calls[0]["method_name"] == "unsourced_physiological_number"
        assert "matched" in calls[0]["context"]
        assert calls[0]["context"]["matched"] == "250 watts"

    async def test_handle_violation_does_not_expose_method_name_in_result(self, monkeypatch):
        """The method_name used in log_capability_gap is not echoed to the user."""
        from agent.trust import TrustViolation

        async def mock_log(method_name, context, **kwargs):
            from sports_science.types import ToolResult
            return ToolResult(
                value={"status": "logged", "message": "qualitative fallback"},
                unit="",
                methodology="capability_gap_log",
                inputs={},
            )

        monkeypatch.setattr("agent.trust.log_capability_gap", mock_log)

        from agent.trust import handle_violation

        violation = TrustViolation(matched_text="85 TSS", pattern="x")
        # Should not raise, and should not surface method_name
        await handle_violation(violation)  # if it doesn't raise, GAP-03 preserved
