# agent/trust.py
"""
Trust-model response scanner for PacerAI (TRUST-03, TRUST-04, TRUST-05, TRUST-08).

scan_buffer: Synchronous, pure (no I/O). Scans buffered assistant text for
unsourced physiological numbers using two complementary regex patterns:
  - PHYSIO_PATTERN_A: number followed by unit (core case: "250 watts", "85 TSS")
  - PHYSIO_PATTERN_B: unit followed by number ("Zone 4", "CTL 42", "TSS should be 85")

A number is considered attributed (not a violation) when it matches -- within
NUMERIC_TOLERANCE -- a boundary-aware numeric token extracted from EITHER of
two distinct attribution channels:
  - tool_result_values: values returned by tools this turn (or seeded from a
    prior turn's persisted audit trail, TRUST-09/D-04).
  - self_reported_values (08-08 / D-02 / D-05): the user's OWN chat messages
    this turn, extracted by collect_self_reported_values. This is the missing
    "onboarding profile / self-report" half of D-02's original "confirmed
    values registry" design -- it lets the assistant restate a physiological
    number (e.g. a self-reported LTHR in the D-03 confirmation-gate summary)
    that the user themselves typed, WITHOUT a tool call, without opening a
    laundering loophole for numbers the LLM merely invented.

Both channels are resolved by the SAME _is_attributed numeric-token +
NUMERIC_TOLERANCE compare (TRUST-08, D-03) -- this is a numeric-token +
tolerance compare, not a raw substring check: "250" is no longer attributed by
the mere presence of "2500", "0.250", or a timestamp digit run inside either
channel's source string. The two channels are kept structurally distinct (two
separate _is_attributed calls, never merged into one list) so the security
narrative for each stays explicit: self_reported_values governs ONLY what the
scanner permits the assistant to RESTATE in chat; it never reaches a tool's
computed-output fields (current_ctl / ftp_watts / load_targets), which remain
server-side-injected in dispatch_tool (D-02 / Plan 06) regardless of what a
user claims in chat.

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

import json
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


def _collect_numeric_leaves(obj: Any) -> "list[float]":
    """
    WR-04: recursively collect numeric LEAF values from a parsed JSON
    structure (dict/list/int/float/bool/str/None), ignoring string values
    entirely.

    tool_result_values entries are JSON-serialised tool outputs (dicts with
    dict/list/scalar values). A JSON string value (e.g. a date/timestamp such
    as "2024-01-01T00:04:20Z") is never walked into for digit extraction here
    -- only genuine JSON number literals are collected -- which structurally
    prevents an unrelated digit run embedded in a date/timestamp string from
    ever being treated as an attributable physiological number (closing the
    general class of collision the prior raw-regex-over-the-whole-string
    approach was vulnerable to, not just the one timestamp shape a prior
    regression test happened to cover).

    bool is excluded explicitly since bool is a subclass of int in Python and
    would otherwise be misidentified as a numeric leaf.
    """
    numbers: list[float] = []
    if isinstance(obj, dict):
        for v in obj.values():
            numbers.extend(_collect_numeric_leaves(v))
    elif isinstance(obj, list):
        for item in obj:
            numbers.extend(_collect_numeric_leaves(item))
    elif isinstance(obj, bool):
        pass  # bool is a subclass of int -- never a physiological number
    elif isinstance(obj, (int, float)):
        numbers.append(float(obj))
    return numbers


def _is_attributed(candidate_str: str, tool_result_values: "list[str]") -> bool:
    """
    Return True iff candidate_str parses as a float and matches -- within
    NUMERIC_TOLERANCE -- a numeric value found in any tool_result_values
    string.

    WR-04: each tool_result_values string is first tried as JSON. When it
    parses, only genuine JSON number leaves are compared against (see
    _collect_numeric_leaves) -- digits embedded inside a JSON string value
    (e.g. a date/timestamp) are structurally invisible to this comparison,
    since they live inside a str leaf, not a number leaf. When a value is not
    valid JSON (e.g. a bare prose string like "250 watts" from older/simpler
    call sites), attribution falls back to the previous boundary-aware
    numeric-token regex extraction over the raw string (D-03/TRUST-08),
    preserving existing behavior for non-JSON inputs.

    Pure/synchronous: no I/O, no side effects. Unparseable candidates or
    tokens are ignored (treated as non-matching), never raised.
    """
    try:
        candidate = float(candidate_str)
    except ValueError:
        return False
    for val in tool_result_values:
        try:
            parsed = json.loads(val)
        except (ValueError, TypeError):
            parsed = None

        if parsed is not None:
            for number in _collect_numeric_leaves(parsed):
                if abs(candidate - number) <= NUMERIC_TOLERANCE:
                    return True
            continue

        # Fallback: val is not valid JSON -- legacy boundary-aware token scan.
        for token_match in _NUMERIC_TOKEN.finditer(val):
            try:
                if abs(candidate - float(token_match.group(0))) <= NUMERIC_TOLERANCE:
                    return True
            except ValueError:
                continue
    return False


def collect_self_reported_values(messages: "list[dict]") -> "list[str]":
    """
    Extract genuine user-authored chat strings as a distinct attribution
    channel (08-08 / D-02 / D-05 -- the "onboarding profile / self-report"
    half of the confirmed-values registry that D-04/TRUST-09 never built).

    Returns each message's content where role == "user" AND content is a str
    instance. Assistant-role messages are always excluded -- an assistant's
    own (now-permitted) echo of a number must never become an attribution
    source on a later turn, which would reopen an echo->source laundering
    chain (T-08-08-03). Non-string user content (e.g. tool-result content-
    block lists appended after a tool dispatch) is also excluded, since that
    content did not originate from the user typing in chat.

    Pure/synchronous: no I/O, no side effects. Guards against malformed input
    (non-list messages, missing "role"/"content" keys) by returning an empty
    list rather than raising, matching the never-raises posture of
    backend/agent/audit.py's load_prior_audit_values.
    """
    if not isinstance(messages, list):
        return []

    collected: list[str] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        if message.get("role") != "user":
            continue
        content = message.get("content")
        if isinstance(content, str):
            collected.append(content)
    return collected


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
    self_reported_values: "Optional[list[str]]" = None,
) -> Optional[TrustViolation]:
    """
    Scan assistant text for unsourced physiological numbers.

    Runs Pattern A (number+unit) first, then Pattern B (unit+number).
    A match is attributed (not a violation) if the bare numeric candidate
    (Pattern A's leading number, Pattern B's extracted number group) matches
    -- within NUMERIC_TOLERANCE -- a boundary-aware numeric token found in
    EITHER of two distinct channels (see _is_attributed / TRUST-08):
      - tool_result_values: values returned by tools this turn.
      - self_reported_values (08-08 / D-02 / D-05): numbers the user
        themselves stated in chat this turn (Branch A onboarding self-report,
        e.g. a directly-stated LTHR). Distinct allowlist from
        tool_result_values, resolved by the same numeric-token +
        NUMERIC_TOLERANCE compare -- it only governs what the scanner permits
        the assistant to restate; it never authorizes a tool's computed-output
        fields (those remain server-side-injected per D-02 / Plan 06).

    This handles the common false-positive case where Claude echoes a tool result
    value in running text (RESEARCH.md Pitfall 1), while closing the substring-
    collision bypass where an unrelated digit run (e.g. "2500", "0.250", or a
    timestamp) could falsely attribute a different number (D-03).

    Args:
        text:                  Full buffered assistant text for this turn.
        tool_result_values:    Set of string values returned by tools this
                                turn. Should include string representations of
                                all tool result content (e.g. JSON serialised
                                tool outputs).
        self_reported_values:  Optional list of genuine user-authored chat
                                strings this turn (see collect_self_reported_
                                values). Defaults to None, which is treated as
                                an empty channel -- every pre-existing
                                2-argument call site keeps identical behavior.

    Returns:
        First TrustViolation found with a number unattributed by BOTH
        channels, or None.

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
        # Two distinct channels checked separately (never merged into one
        # list) so the two attribution sources stay explicit in code (08-08).
        if not _is_attributed(bare_number, tool_result_values) and not _is_attributed(
            bare_number, self_reported_values or []
        ):
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
        # compare against EITHER tool_result_values OR self_reported_values
        # (D-03/TRUST-08, 08-08).
        if not _is_attributed(num, tool_result_values) and not _is_attributed(
            num, self_reported_values or []
        ):
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
