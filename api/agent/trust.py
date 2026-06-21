# agent/trust.py
"""
Trust-model response scanner for PacerAI (TRUST-03, TRUST-04, TRUST-05).

scan_buffer: Synchronous, pure (no I/O). Scans buffered assistant text for
unsourced physiological numbers using two complementary regex patterns:
  - PHYSIO_PATTERN_A: number followed by unit (core case: "250 watts", "85 TSS")
  - PHYSIO_PATTERN_B: unit followed by number ("Zone 4", "CTL 42", "TSS should be 85")

Numbers that appear verbatim as a substring of any string in tool_result_values
(values returned by tools this turn) are considered attributed and NOT violations.

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

from api.sports_science.capability_gap import log_capability_gap


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
    A match is attributed (not a violation) if:
      - The full matched text is a substring of any tool_result_value string, OR
      - For Pattern B: the extracted number is a substring of any tool_result_value.

    This handles the common false-positive case where Claude echoes a tool result
    value in running text (RESEARCH.md Pitfall 1).

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
        if not any(matched in val for val in tool_result_values):
            return TrustViolation(
                matched_text=matched,
                pattern=PHYSIO_PATTERN_A.pattern,
            )

    # --- Pattern B: unit then number ---
    for match in PHYSIO_PATTERN_B.finditer(text):
        groups = match.groups()
        # Determine which sub-pattern matched and extract the number
        if groups[0] is not None:       # zone N
            unit, num = groups[0], groups[1]
        elif groups[2] is not None:     # Z4
            unit, num = groups[2], groups[3]
        else:                           # TSS|FTP|CTL|ATL|TSB + number
            unit, num = groups[4], groups[5]

        full_match = match.group(0).strip()
        synthetic = f"{num} {unit}"  # e.g. "42 CTL", "4 Zone"

        # Attribution: full match, synthetic number+unit, or bare number in tool results
        attributed = any(
            s in val
            for val in tool_result_values
            for s in [full_match, synthetic, num]
        )
        if not attributed:
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
