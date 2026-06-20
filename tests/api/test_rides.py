# tests/api/test_rides.py
"""
Ride upload route tests (Wave 3).

Most tests are stubs (skipped) pending Wave 3 router implementation.
test_fixture_exists is NOT skipped -- it asserts the real Zwift .FIT
fixture exists so the gap is immediately visible if it's missing.

asyncio_mode = auto (pytest.ini) -- no @pytest.mark.asyncio needed.
"""
import pathlib

import pytest

from tests.api.conftest import TEST_USER_ID

FIXTURE_PATH = pathlib.Path(__file__).parents[1] / "fixtures" / "sample_zwift.fit"


# ---------------------------------------------------------------------------
# Non-skipped: fixture existence check
# ---------------------------------------------------------------------------


def test_fixture_exists():
    """
    FIT-06 prerequisite: the real Zwift .FIT fixture must exist at
    tests/fixtures/sample_zwift.fit before Wave 3 integration test runs.

    This test is NOT skipped -- a missing fixture is a visible failure,
    never a silent pass.
    """
    assert FIXTURE_PATH.exists(), (
        f"Real Zwift .FIT fixture missing at {FIXTURE_PATH}. "
        "Generate it with the script in tests/fixtures/ or acquire a sample from "
        "the Garmin FIT SDK. This fixture is required for FIT-06 acceptance test."
    )


# ---------------------------------------------------------------------------
# Wave 3 stubs (skipped until rides router is implemented)
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="Wave 3 implements: rides router not yet created")
async def test_upload_returns_200(monkeypatch):
    """
    Wave 3: POST /rides/upload with a valid .FIT file returns 200 with ride_id.
    """
    pass


@pytest.mark.skip(reason="Wave 3 implements: rides router not yet created")
async def test_fit_parse_warn(monkeypatch):
    """
    Wave 3: A .FIT file with missing fields returns 422 with error='fit_parse_failed'.
    """
    pass


@pytest.mark.skip(reason="Wave 3 implements: rides router not yet created")
async def test_missing_fields(monkeypatch):
    """
    Wave 3: A .FIT file missing required record fields (power) is handled gracefully.
    """
    pass


@pytest.mark.skip(reason="Wave 3 implements: rides router not yet created")
async def test_tss_computed(monkeypatch):
    """
    Wave 3: After upload, TSS is computed via compute_tss tool (not raw math in route).
    """
    pass


@pytest.mark.skip(reason="Wave 3 implements: rides router not yet created")
async def test_session_compliance(monkeypatch):
    """
    Wave 3: After upload, session compliance is evaluated via validate_session_vs_actual.
    """
    pass


@pytest.mark.skip(reason="Wave 3 implements: rides router + real Zwift .FIT fixture needed")
async def test_fit_upload_integration(monkeypatch):
    """
    Wave 3 / FIT-06: Full integration test -- upload real Zwift .FIT, assert TSS > 0.

    Fixture: tests/fixtures/sample_zwift.fit (must be a genuine parseable .FIT
    with power data stream; TSS > 0 is the acceptance criterion).
    """
    import httpx
    from httpx import ASGITransport
    from api.main import app

    assert FIXTURE_PATH.exists(), f"Test fixture missing: {FIXTURE_PATH}"

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        with open(FIXTURE_PATH, "rb") as f:
            response = await client.post(
                "/rides/upload",
                files={"file": ("sample_zwift.fit", f, "application/octet-stream")},
                data={"user_id": TEST_USER_ID},
            )

    assert response.status_code == 200
    assert "ride_id" in response.json()
