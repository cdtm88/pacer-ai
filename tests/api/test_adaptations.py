# tests/api/test_adaptations.py
"""
Adaptations route tests (Wave 4).

All tests are stubs (skipped) pending Wave 4 router and signal detection
implementation.

asyncio_mode = auto (pytest.ini) -- no @pytest.mark.asyncio needed.
"""
import pytest

from tests.api.conftest import TEST_USER_ID


@pytest.mark.skip(reason="Wave 4 implements: adaptations router not yet created")
async def test_missed_detection(monkeypatch):
    """
    Wave 4: detect_signals identifies missed sessions from the sessions table.
    """
    pass


@pytest.mark.skip(reason="Wave 4 implements: adaptations router not yet created")
async def test_micro_macro_branch(monkeypatch):
    """
    Wave 4: Micro adaptations (session-level) vs macro adaptations (plan-level)
    are correctly branched in the signal detection logic.
    """
    pass


@pytest.mark.skip(reason="Wave 4 implements: adaptations router not yet created")
async def test_shift_limit(monkeypatch):
    """
    Wave 4: Session time shift is capped at the configured limit
    (no unbounded rescheduling).
    """
    pass


@pytest.mark.skip(reason="Wave 4 implements: adaptations router not yet created")
async def test_weekly_check(monkeypatch):
    """
    Wave 4: POST /adaptations/check returns signals with count for a given user.
    """
    pass


@pytest.mark.skip(reason="Wave 4 implements: adaptations router not yet created")
async def test_intensity_from_tools(monkeypatch):
    """
    Wave 4: Intensity adaptation suggestions come from tool calls (not LLM reasoning).
    """
    pass


@pytest.mark.skip(reason="Wave 4 implements: adaptations router not yet created")
async def test_log_persisted(monkeypatch):
    """
    Wave 4: Adaptation decisions are persisted to the adaptations table.
    """
    pass


@pytest.mark.skip(reason="Wave 4 implements: adaptations router not yet created")
async def test_get_adaptations(monkeypatch):
    """
    Wave 4: GET /adaptations/ returns list of adaptation records for the user.
    """
    pass
