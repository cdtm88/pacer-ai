# agent/trust.py
"""
Trust-model response scanner for PacerAI (TRUST-03, TRUST-04, TRUST-05, TRUST-08).

scan_buffer: Synchronous, pure (no I/O). Scans buffered assistant text for
unsourced physiological numbers using two complementary regex patterns:
  - PHYSIO_PATTERN_A: number followed by unit (core case: "250 watts", "85 TSS")
  - PHYSIO_PATTERN_B: unit followed by number ("Zone 4", "CTL 42", "TSS should be 85")

A number is considered attributed (not a violation) when it matches -- within
NUMERIC_TOLERANCE -- a boundary-aware numeric token extracted from a
tool_result_values string (values returned by tools this turn). This is a
numeric-token + tolerance compare (TRUST-08, D-03), not a raw substring check:
"250" is no longer attributed by the mere presence of "2500", "0.250", or a
timestamp digit run inside a tool result string.

handle_violation: Async hook called by the loop on a genuine violation. Awaits
log_capability_gap to satisfy TRUST-05. Does not surface the internal method_name
to the user -- GAP-03 is preserved by log_capability_gap itself.

Invariants:
  - scan_buffer is synchronous and pure; the DB-touching capability-gap call lives
    in the async handle_violation hook only.
  - matched_text in TrustViolation must never be echoed in an SSE data frame
    visible to the user -- only the loop's generic trust_violation error event
    (code: "trust_violation") should reach the stream.
  - PHYSIO_PATTERN_A runs before PHYSIO_PATTERN_B so number+unit matches have
    the tightest matched_text for attribution checking.
"""

import re
from dataclasses import dataclass
from typing import Optional, Any

from backend.sports_science.capability_gap import log_capability_gap


# ---------------------------------------------------------------------------
# Pattern A: number followed by physio unit (core detection case).
# Examples: "250 watts", "85 TSS", "145 bpm", "90 rpm", "200W"
# Design notes (D-09):
#   - W(?!\w) matches bare "W" not followed by a word character (e.g. "200W")
#     but not "Watts" or "Watt" (already handled by watts?).
#   - Case-insensitive so "WATTS", "Bpm", "TSS" all match.
# ---------------------------------------------------------------------------

PHYSIO_PATTERN_A = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:watts?|W(?!\w)|TSS\b|FTP\b|CTL\b|ATL\b|TSB\b|bpm\b|rpm\b)",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Pattern B: unit followed by number (secondary detection case).
# Examples: "Zone 4", "Z4", "CTL 42", "ATL is 55", "TSS for today should be 85"
# Separate from Pattern A so matched_text for Pattern A is always tight
# (number+unit) for cleaner attribution checking.
# ---------------------------------------------------------------------------

PHYSIO_PATTERN_B = re.compile(
    r"\b(?:"
    r"(zone)\s*(\d+)"                           # Zone 4
    r"|"
    r"(Z)(\d+)\b"                               # Z4 abbreviation
    r"|"
    r"(TSS|FTP|CTL|ATL|TSB)\b(?:\s+[a-zA-Z]\w*){0,4}\s*(-?\d+(?:\.\d+)?)"  # unit + optional words + number (incl. negative TSB)
    r")",
    re.IGNORECASE,
)

# PHYSIO_PATTERN: combined pattern (union of A and B) for external references
# and greppability (plan acceptance criteria: grep -c 'PHYSIO_PATTERN' agent/trust.py).
# scan_buffer applies both sub-patterns independently for accurate matched_text extraction.
PHYSIO_PATTERN = re.compile(
    r"\b(?:"
    r"\d+(?:\.\d+)?\s*(?:watts?|W(?!\w)|TSS\b|FTP\b|CTL\b|ATL\b|TSB\b|bpm\b|rpm\b)"
    r"|"
    r"zone\s*\d+"
    r"|"
    r"Z\d+\b"
    r"|"
    r"(?:TSS|FTP|CTL|ATL|TSB)\b(?:\s+[a-zA-Z]\w*){0,4}\s*-?\d+(?:\.\d+)?"
    r")",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Numeric-token extraction with tolerance (D-03 / TRUST-08).
#
# Replaces raw substring membership (`s in val`) for attribution checks. The
# boundary-aware lookaround -- (?<![\d.]) ... (?!\d) -- prevents "25" from
# matching inside "2500" or "0.250": each extracted token must stand on its
# own numeric boundaries, not be a substring of a larger digit run. Combined
# with a float-tolerance compare, this closes the substring-collision bypass
# where any tool result containing an unrelated number (or a timestamp digit
# run) could "attribute" an unrelated hallucinated value.
# ---------------------------------------------------------------------------

_NUMERIC_TOKEN = re.compile(r"(?<![\d.])-?\d+(?:\.\d+)?(?!\d)")
NUMERIC_TOLERANCE = 0.01


def _is_attributed(candidate_str: str, tool_result_values: "list[str]") -> bool:
    """
    Return True iff candidate_str parses as a float and matches -- within
    NUMERIC_TOLERANCE -- a boundary-aware numeric token found in any
    tool_result_values string.

    Pure/synchronous: no I/O, no side effects. Unparseable candidates or
    tokens are ignored (treated as non-matching), never raised.
    """
    try:
        candidate = float(candidate_str)
    except ValueError:
        return False
    for val in tool_result_values:
        for token_match in _NUMERIC_TOKEN.finditer(val):
            try:
                if abs(candidate - float(token_match.group(0))) <= NUMERIC_TOLERANCE:
                    return True
            except ValueError:
                continue
    return False


@dataclass
class TrustViolation:
    """Represents an unsourced physiological number detected by scan_buffer."""

    matched_text: str   # the matched substring (number+unit or unit+number)
    pattern: str        # pattern string for traceability

    def __str__(self) -> str:
        return f"TrustViolation(matched_text={self.matched_text!r})"


def scan_buffer(
    text: str,
    tool_result_values: "list[str]",
) -> Optional[TrustViolation]:
    """
    Scan assistant text for unsourced physiological numbers.

    Runs Pattern A (number+unit) first, then Pattern B (unit+number).
    A match is attributed (not a violation) if the bare numeric candidate
    (Pattern A's leading number, Pattern B's extracted number group) matches
    -- within NUMERIC_TOLERANCE -- a boundary-aware numeric token found in any
    tool_result_values string (see _is_attributed / TRUST-08).

    This handles the common false-positive case where Claude echoes a tool result
    value in running text (RESEARCH.md Pitfall 1), while closing the substring-
    collision bypass where an unrelated digit run (e.g. "2500", "0.250", or a
    timestamp) could falsely attribute a different number (D-03).

    Args:
        text:               Full buffered assistant text for this turn.
        tool_result_values: Set of string values returned by tools this turn.
                            Should include string representations of all tool
                            result content (e.g. JSON serialised tool outputs).

    Returns:
        First TrustViolation found with an unattributed number+unit, or None.

    Pure/synchronous: no I/O, no side effects.
    """
    # --- Pattern A: number then unit ---
    for match in PHYSIO_PATTERN_A.finditer(text):
        matched = match.group(0).strip()
        # Tool results are structured JSON (e.g. {"lower_bpm": 134}), so a
        # number+unit phrase like "134 bpm" never appears verbatim in a tool
        # result string. Extract the bare leading number and check attribution
        # via numeric-token + tolerance match (260702-vsp bare-number fallback,
        # D-03/TRUST-08 boundary-aware rewrite).
        number_match = re.match(r"\d+(?:\.\d+)?", matched)
        bare_number = number_match.group(0) if number_match else matched
        if not _is_attributed(bare_number, tool_result_values):
            return TrustViolation(
                matched_text=matched,
                pattern=PHYSIO_PATTERN_A.pattern,
            )

    # --- Pattern B: unit then number ---
    for match in PHYSIO_PATTERN_B.finditer(text):
        groups = match.groups()
        # Determine which sub-pattern matched and extract the number
        if groups[0] is not None:       # zone N
            num = groups[1]
        elif groups[2] is not None:     # Z4
            num = groups[3]
        else:                           # TSS|FTP|CTL|ATL|TSB + number
            num = groups[5]

        full_match = match.group(0).strip()

        # Attribution: extracted number matched via numeric-token + tolerance
        # compare against tool_result_values (D-03/TRUST-08).
        if not _is_attributed(num, tool_result_values):
            return TrustViolation(
                matched_text=full_match,
                pattern=PHYSIO_PATTERN_B.pattern,
            )

    return None


async def handle_violation(
    violation: TrustViolation,
    context_extra: Optional[dict] = None,
) -> None:
    """
    Async on-violation hook (TRUST-05).

    Awaits log_capability_gap with method_name="unsourced_physiological_number"
    and a context dict containing the matched text. Satisfies TRUST-05 by firing
    the capability-gap log on every TRUST-03 detection.

    GAP-03 note: log_capability_gap itself ensures the internal method_name is
    never surfaced in its user-facing message. This function must never be called
    in a way that would echo method_name or matched_text to the user.

    Args:
        violation:     TrustViolation detected by scan_buffer.
        context_extra: Optional additional context to merge into the DB log entry.
    """
    context: dict[str, Any] = {"matched": violation.matched_text}
    if context_extra:
        context.update(context_extra)

    # TRUST-05: log_capability_gap fires on every TRUST-03 catch.
    # Best-effort: log_capability_gap itself swallows DB errors.
    await log_capability_gap(
        method_name="unsourced_physiological_number",
        context=context,
    )
