# tests/agent/test_trust_corpus.py
"""
Parametrized characterization of scan_buffer against the labelled trust corpus.

This file is the durable proof of Phase 2 Success Criterion 5:
  "The agent does not emit unsourced physiological numbers across a
   representative set of scenarios."

And answers RESEARCH.md Open Question 2 (false-positive rate) by asserting
aggregate false-positive count == 0 over the QUALITATIVE set.

All tests are synchronous (scan_buffer is pure/sync). No DB, no network, no
log_capability_gap call.
"""

import pytest

from api.agent.trust import scan_buffer
from tests.agent.fixtures.trust_corpus import ATTRIBUTED, QUALITATIVE, VIOLATIONS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _slug(text: str) -> str:
    """Create a stable pytest id from example text (first 40 chars, slug-safe)."""
    return text[:40].lower().replace(" ", "_").replace(".", "").replace(",", "")


# ---------------------------------------------------------------------------
# Parametrized: every VIOLATIONS entry must be flagged
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text", VIOLATIONS, ids=[_slug(t) for t in VIOLATIONS])
def test_violations_all_flagged(text: str) -> None:
    """
    TRUST-03 / zero false negatives: scan_buffer must return a TrustViolation
    for every unsourced-number example in the corpus.
    """
    result = scan_buffer(text, set())
    assert result is not None, (
        f"scan_buffer returned None (false negative) for VIOLATIONS entry:\n  {text!r}\n"
        f"Expected a TrustViolation but the scanner missed it."
    )


# ---------------------------------------------------------------------------
# Parametrized: every QUALITATIVE entry must pass (no false positives)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text", QUALITATIVE, ids=[_slug(t) for t in QUALITATIVE])
def test_qualitative_no_false_positive(text: str) -> None:
    """
    Zero false positives: scan_buffer must return None for every qualitative
    coaching example — no unsourced number+unit present.
    """
    result = scan_buffer(text, set())
    assert result is None, (
        f"scan_buffer raised a false positive for QUALITATIVE entry:\n  {text!r}\n"
        f"Unexpected match: {result.matched_text!r}"
    )


# ---------------------------------------------------------------------------
# Parametrized: every ATTRIBUTED pair must pass with correct tool_result_values
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text, values",
    ATTRIBUTED,
    ids=[_slug(t) for t, _ in ATTRIBUTED],
)
def test_attributed_passes(text: str, values: "set[str]") -> None:
    """
    Pitfall 1 (tool-result echo): scan_buffer must return None when the
    number+unit in the text is present verbatim in tool_result_values,
    meaning it is attributed to a tool call this turn.
    """
    result = scan_buffer(text, values)
    assert result is None, (
        f"scan_buffer raised a false positive (attribution failure) for ATTRIBUTED entry:\n"
        f"  text:   {text!r}\n"
        f"  values: {values!r}\n"
        f"Unexpected match: {result.matched_text!r}\n"
        f"The attribution check did not recognise this value as tool-sourced."
    )


# ---------------------------------------------------------------------------
# Aggregate: false-positive rate is zero across the whole QUALITATIVE set
# ---------------------------------------------------------------------------


def test_false_positive_rate_is_zero() -> None:
    """
    Aggregate proof for RESEARCH.md Open Question 2: the false-positive rate
    over the representative QUALITATIVE set is exactly zero.
    """
    false_positives = [
        text
        for text in QUALITATIVE
        if scan_buffer(text, set()) is not None
    ]
    assert false_positives == [], (
        f"scan_buffer produced {len(false_positives)} false positive(s) on QUALITATIVE set:\n"
        + "\n".join(f"  - {t!r}" for t in false_positives)
    )


# ---------------------------------------------------------------------------
# Aggregate: false-negative rate is zero across the whole VIOLATIONS set
# ---------------------------------------------------------------------------


def test_false_negative_rate_is_zero() -> None:
    """
    Aggregate proof for Phase 2 Success Criterion 5: every unsourced-number
    example in the VIOLATIONS corpus is caught (zero false negatives).
    """
    false_negatives = [
        text
        for text in VIOLATIONS
        if scan_buffer(text, set()) is None
    ]
    assert false_negatives == [], (
        f"scan_buffer missed {len(false_negatives)} violation(s) (false negative) on VIOLATIONS set:\n"
        + "\n".join(f"  - {t!r}" for t in false_negatives)
    )
