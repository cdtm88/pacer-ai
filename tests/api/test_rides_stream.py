# tests/api/test_rides_stream.py
"""
Backend parser/util tests for Phase 11 Wave 0 (RIDE-01, RIDE-02, RIDE-03), plus
GET /rides/{id}/stream endpoint integration tests (Phase 11 Plan 03, RIDE-05,
RIDE-12).

Covers:
  - detect_presence / downsample pure-function behavior (backend/routes/_stream_utils.py)
  - parse_fit_stream aligned per-second channel arrays + lap_bounds
    (backend/routes/rides.py::parse_fit_stream)
  - GET /{ride_id}/stream: IDOR scoping (T-11-01), missing/corrupt file
    handling (T-11-02, T-11-03), LTHR-gated hr_zone_distribution (Pitfall 3)

The parser/util tests are plain sync unit tests (no asyncio marker needed --
asyncio_mode=auto per pytest.ini, but parse_fit_stream/detect_presence/
downsample are all sync functions with no await inside them). The endpoint
tests are async (httpx.AsyncClient) and also rely on asyncio_mode=auto.
"""
import pathlib
from unittest.mock import AsyncMock, MagicMock

import httpx
from httpx import ASGITransport

from tests.api.conftest import TEST_JWT_SECRET, TEST_USER_ID, auth_headers

ZWIFT_FIXTURE_PATH = pathlib.Path(__file__).parents[1] / "fixtures" / "zwift_ride_30min.fit"
HILLY_FIXTURE_PATH = pathlib.Path(__file__).parents[1] / "fixtures" / "hilly_ride_30min.fit"

TEST_RIDE_ID = "11111111-1111-1111-1111-111111111111"


# ---------------------------------------------------------------------------
# detect_presence (D-11-03)
# ---------------------------------------------------------------------------


def test_detect_presence_rules():
    """
    D-11-03: a channel is 'present' iff it has more than one distinct
    non-null value.
    """
    from backend.routes._stream_utils import detect_presence

    assert detect_presence([]) is False
    assert detect_presence([5.0, 5.0, 5.0]) is False  # 1 distinct value
    assert detect_presence([None, None]) is False
    assert detect_presence([1.0, 2.0]) is True
    assert detect_presence([None, 3.0, 4.0]) is True


# ---------------------------------------------------------------------------
# downsample (D-11-04)
# ---------------------------------------------------------------------------


def test_downsample_caps_at_4000():
    """downsample of a 10000-row list returns <= 4000 rows."""
    from backend.routes._stream_utils import downsample

    series = [{"t": i} for i in range(10000)]
    result = downsample(series)

    assert len(result) <= 4000


def test_downsample_preserves_first_and_stride():
    """The first element of the input is the first element of the output
    (stride sampling preserves index 0); downsample([]) returns []."""
    from backend.routes._stream_utils import downsample

    series = [{"t": i} for i in range(10000)]
    result = downsample(series)
    assert result[0] == series[0]

    assert downsample([]) == []


def test_downsample_default_interval_1800_rows():
    """downsample of an 1800-row list at default target_interval_secs=3
    returns ~600 rows (stride 3), still <= 4000."""
    from backend.routes._stream_utils import downsample

    series = [{"t": i} for i in range(1800)]
    result = downsample(series)

    assert len(result) <= 4000
    # stride 3 over 1800 rows -> 600 rows
    assert len(result) == 600


# ---------------------------------------------------------------------------
# parse_fit_stream (RIDE-01)
# ---------------------------------------------------------------------------


def test_parse_stream_channels_aligned():
    """
    parse_fit_stream(zwift_ride_30min.fit bytes) returns a dict whose `series`
    rows all contain the same keys, and every channel array (derived by
    reading one key across all rows) has identical length equal to
    len(series).
    """
    from backend.routes.rides import parse_fit_stream

    assert ZWIFT_FIXTURE_PATH.exists(), f"Test fixture missing: {ZWIFT_FIXTURE_PATH}"
    file_bytes = ZWIFT_FIXTURE_PATH.read_bytes()

    parsed = parse_fit_stream(file_bytes)

    assert parsed is not None, "parse_fit_stream returned None for a valid .FIT file"
    series = parsed["series"]
    assert len(series) > 0, "Expected non-empty series"

    expected_keys = set(series[0].keys())
    for row in series:
        assert set(row.keys()) == expected_keys, (
            f"Row keys diverge from first row's keys: {row.keys()} != {expected_keys}"
        )

    for key in expected_keys:
        channel_values = [row[key] for row in series]
        assert len(channel_values) == len(series), (
            f"Channel {key!r} array length {len(channel_values)} != len(series) {len(series)}"
        )


def test_parse_stream_zwift_altitude_absent():
    """
    parse_fit_stream(zwift_ride_30min.fit bytes): detect_presence over the
    altitude column is False (indoor Zwift ride, no elevation sensor);
    detect_presence over the power column is True.
    """
    from backend.routes._stream_utils import detect_presence
    from backend.routes.rides import parse_fit_stream

    assert ZWIFT_FIXTURE_PATH.exists(), f"Test fixture missing: {ZWIFT_FIXTURE_PATH}"
    file_bytes = ZWIFT_FIXTURE_PATH.read_bytes()

    parsed = parse_fit_stream(file_bytes)
    assert parsed is not None

    altitude_values = [row["altitude"] for row in parsed["series"]]
    power_values = [row["power"] for row in parsed["series"]]

    assert detect_presence(altitude_values) is False, (
        "Expected altitude absent (Zwift indoor ride has no elevation sensor)"
    )
    assert detect_presence(power_values) is True, (
        "Expected power present (Zwift ride has a power meter)"
    )


def test_parse_stream_hilly_altitude_present():
    """
    parse_fit_stream(hilly_ride_30min.fit bytes): detect_presence over the
    altitude column is True (outdoor ride with real elevation data).
    """
    from backend.routes._stream_utils import detect_presence
    from backend.routes.rides import parse_fit_stream

    assert HILLY_FIXTURE_PATH.exists(), f"Test fixture missing: {HILLY_FIXTURE_PATH}"
    file_bytes = HILLY_FIXTURE_PATH.read_bytes()

    parsed = parse_fit_stream(file_bytes)
    assert parsed is not None

    altitude_values = [row["altitude"] for row in parsed["series"]]

    assert detect_presence(altitude_values) is True, (
        "Expected altitude present (hilly outdoor ride has elevation data)"
    )


def test_parse_stream_lap_bounds_six():
    """
    lap_bounds has length 6 for both fixtures (RESEARCH Pitfall 4 -- six
    laps, never seven).
    """
    from backend.routes.rides import parse_fit_stream

    for fixture_path in (ZWIFT_FIXTURE_PATH, HILLY_FIXTURE_PATH):
        assert fixture_path.exists(), f"Test fixture missing: {fixture_path}"
        file_bytes = fixture_path.read_bytes()

        parsed = parse_fit_stream(file_bytes)
        assert parsed is not None

        assert len(parsed["lap_bounds"]) == 6, (
            f"Expected 6 lap_bounds for {fixture_path.name}, got {len(parsed['lap_bounds'])}"
        )


def test_parse_stream_corrupt_returns_none():
    """
    parse_fit_stream(b"not a fit file") returns None (total parse failure
    contract mirrors parse_fit_file).
    """
    from backend.routes.rides import parse_fit_stream

    result = parse_fit_stream(b"not a fit file")

    assert result is None, "Expected None for corrupt/unreadable bytes"


# ---------------------------------------------------------------------------
# GET /rides/{id}/stream (RIDE-05, Phase 11 Plan 03)
# ---------------------------------------------------------------------------


def _make_stream_client_mock(
    ride_row: dict | None = None,
    profile_lthr_row: dict | None = None,
    download_bytes: bytes | None = None,
    download_raises: bool = False,
):
    """
    Build a mock Supabase client for GET /rides/{id}/stream tests.

    The route makes (at most) two `.table(...).select(...).eq(...).eq(...)
    .execute()` calls in sequence -- rides SELECT first, profiles SELECT
    second (only reached when the rides row is found and raw_fit_path is
    set) -- dispatched here by call order, mirroring _make_rides_mock's
    execute_dispatch pattern in test_rides.py. Storage download is a
    separate AsyncMock on client_mock.storage.from_("fits").download(...).

    Args:
        ride_row: dict for the rides SELECT result, or None for an empty
            result (IDOR miss / ride does not exist for this user).
        profile_lthr_row: dict (e.g. {"lthr": 160}) for the profiles SELECT
            result, or None for an empty result (no LTHR on file).
        download_bytes: bytes to return from storage.download(); ignored if
            download_raises is True.
        download_raises: if True, storage.download() raises an exception.
    """
    rides_result = MagicMock()
    rides_result.data = [ride_row] if ride_row is not None else []

    profile_result = MagicMock()
    profile_result.data = [profile_lthr_row] if profile_lthr_row is not None else []

    call_count = {"n": 0}

    async def execute_dispatch():
        call_count["n"] += 1
        if call_count["n"] == 1:
            return rides_result
        return profile_result

    chain_mock = MagicMock()
    chain_mock.select.return_value = chain_mock
    chain_mock.eq.return_value = chain_mock
    chain_mock.execute = execute_dispatch

    storage_mock = MagicMock()
    storage_mock.from_ = MagicMock(return_value=storage_mock)
    if download_raises:
        storage_mock.download = AsyncMock(side_effect=Exception("storage error"))
    else:
        storage_mock.download = AsyncMock(return_value=download_bytes)

    client_mock = MagicMock()
    client_mock.table = MagicMock(return_value=chain_mock)
    client_mock.storage = storage_mock

    return client_mock


async def test_stream_happy_zwift_altitude_absent(monkeypatch):
    """
    Happy path (zwift_ride_30min.fit, profiles.lthr=160): 200; body has
    series/channels/laps/hr_zone_distribution; channels["altitude"] is
    False (indoor Zwift ride, no elevation sensor); channels["power"] is
    True; len(laps) == 6 (RESEARCH Pitfall 4); hr_zone_distribution is a
    non-empty list of 5 zone rows.
    """
    import backend.routes.rides as rides_module
    from backend.main import app

    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    assert ZWIFT_FIXTURE_PATH.exists(), f"Test fixture missing: {ZWIFT_FIXTURE_PATH}"

    client_mock = _make_stream_client_mock(
        ride_row={
            "id": TEST_RIDE_ID,
            "user_id": TEST_USER_ID,
            "raw_fit_path": f"{TEST_USER_ID}/zwift_ride_30min.fit",
        },
        profile_lthr_row={"lthr": 160},
        download_bytes=ZWIFT_FIXTURE_PATH.read_bytes(),
    )
    monkeypatch.setattr(rides_module, "_get_async_supabase", AsyncMock(return_value=client_mock))

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            f"/rides/{TEST_RIDE_ID}/stream",
            headers=auth_headers(),
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body.keys()) == {"series", "channels", "laps", "hr_zone_distribution"}
    assert body["channels"]["altitude"] is False
    assert body["channels"]["power"] is True
    assert len(body["laps"]) == 6
    assert isinstance(body["hr_zone_distribution"], list)
    assert len(body["hr_zone_distribution"]) == 5
    assert len(body["hr_zone_distribution"]) > 0


async def test_stream_happy_hilly_altitude_present(monkeypatch):
    """
    Same happy path but with hilly_ride_30min.fit bytes: channels["altitude"]
    is True (outdoor ride with real elevation data).
    """
    import backend.routes.rides as rides_module
    from backend.main import app

    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    assert HILLY_FIXTURE_PATH.exists(), f"Test fixture missing: {HILLY_FIXTURE_PATH}"

    client_mock = _make_stream_client_mock(
        ride_row={
            "id": TEST_RIDE_ID,
            "user_id": TEST_USER_ID,
            "raw_fit_path": f"{TEST_USER_ID}/hilly_ride_30min.fit",
        },
        profile_lthr_row={"lthr": 160},
        download_bytes=HILLY_FIXTURE_PATH.read_bytes(),
    )
    monkeypatch.setattr(rides_module, "_get_async_supabase", AsyncMock(return_value=client_mock))

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            f"/rides/{TEST_RIDE_ID}/stream",
            headers=auth_headers(),
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["channels"]["altitude"] is True


async def test_stream_no_lthr_distribution_null(monkeypatch):
    """
    profiles.lthr is None (Branch C user) with a ride that HAS heart_rate ->
    hr_zone_distribution is null (RESEARCH Pitfall 3 / A3). Never estimated
    from max_hr -- the route only reads profiles.lthr.
    """
    import backend.routes.rides as rides_module
    from backend.main import app

    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    assert ZWIFT_FIXTURE_PATH.exists(), f"Test fixture missing: {ZWIFT_FIXTURE_PATH}"

    client_mock = _make_stream_client_mock(
        ride_row={
            "id": TEST_RIDE_ID,
            "user_id": TEST_USER_ID,
            "raw_fit_path": f"{TEST_USER_ID}/zwift_ride_30min.fit",
        },
        profile_lthr_row=None,  # no LTHR on file
        download_bytes=ZWIFT_FIXTURE_PATH.read_bytes(),
    )
    monkeypatch.setattr(rides_module, "_get_async_supabase", AsyncMock(return_value=client_mock))

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            f"/rides/{TEST_RIDE_ID}/stream",
            headers=auth_headers(),
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["channels"]["heart_rate"] is True
    assert body["hr_zone_distribution"] is None


async def test_stream_idor_returns_404(monkeypatch):
    """
    rides SELECT returns [] (ride not owned by caller / does not exist) ->
    404 with detail error "ride_not_found"; the response never contains
    series (T-11-01, IDOR).
    """
    import backend.routes.rides as rides_module
    from backend.main import app

    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)

    client_mock = _make_stream_client_mock(ride_row=None)
    monkeypatch.setattr(rides_module, "_get_async_supabase", AsyncMock(return_value=client_mock))

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            f"/rides/{TEST_RIDE_ID}/stream",
            headers=auth_headers(),
        )

    assert response.status_code == 404, response.text
    body = response.json()
    assert "series" not in body
    detail = body.get("detail", body)
    assert detail.get("error") == "ride_not_found"


async def test_stream_missing_raw_fit_path_404(monkeypatch):
    """rides row exists but raw_fit_path is None -> 404 (T-11-02)."""
    import backend.routes.rides as rides_module
    from backend.main import app

    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)

    client_mock = _make_stream_client_mock(
        ride_row={"id": TEST_RIDE_ID, "user_id": TEST_USER_ID, "raw_fit_path": None},
    )
    monkeypatch.setattr(rides_module, "_get_async_supabase", AsyncMock(return_value=client_mock))

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            f"/rides/{TEST_RIDE_ID}/stream",
            headers=auth_headers(),
        )

    assert response.status_code == 404, response.text
    detail = response.json().get("detail", {})
    assert detail.get("error") == "ride_not_found"


async def test_stream_storage_download_fails_404(monkeypatch):
    """storage.download raises -> 404 (T-11-02)."""
    import backend.routes.rides as rides_module
    from backend.main import app

    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)

    client_mock = _make_stream_client_mock(
        ride_row={
            "id": TEST_RIDE_ID,
            "user_id": TEST_USER_ID,
            "raw_fit_path": f"{TEST_USER_ID}/zwift_ride_30min.fit",
        },
        download_raises=True,
    )
    monkeypatch.setattr(rides_module, "_get_async_supabase", AsyncMock(return_value=client_mock))

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            f"/rides/{TEST_RIDE_ID}/stream",
            headers=auth_headers(),
        )

    assert response.status_code == 404, response.text
    detail = response.json().get("detail", {})
    assert detail.get("error") == "ride_not_found"


async def test_stream_corrupt_file_422(monkeypatch):
    """
    storage.download returns b"garbage" so parse_fit_stream returns None ->
    422 with error "fit_parse_failed" (T-11-03).
    """
    import backend.routes.rides as rides_module
    from backend.main import app

    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)

    client_mock = _make_stream_client_mock(
        ride_row={
            "id": TEST_RIDE_ID,
            "user_id": TEST_USER_ID,
            "raw_fit_path": f"{TEST_USER_ID}/zwift_ride_30min.fit",
        },
        download_bytes=b"garbage",
    )
    monkeypatch.setattr(rides_module, "_get_async_supabase", AsyncMock(return_value=client_mock))

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            f"/rides/{TEST_RIDE_ID}/stream",
            headers=auth_headers(),
        )

    assert response.status_code == 422, response.text
    detail = response.json().get("detail", {})
    assert detail.get("error") == "fit_parse_failed"


async def test_stream_bad_uuid_400(monkeypatch):
    """A malformed ride_id that is not a UUID -> 400 (validate_uuid) before
    any DB call."""
    import backend.routes.rides as rides_module
    from backend.main import app

    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)

    # No DB call should ever be made -- if it were, this mock would raise
    # AttributeError since it has no configured chain, surfacing a test bug.
    monkeypatch.setattr(
        rides_module,
        "_get_async_supabase",
        AsyncMock(side_effect=AssertionError("DB should not be called for a bad UUID")),
    )

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/rides/not-a-uuid/stream",
            headers=auth_headers(),
        )

    assert response.status_code == 400, response.text
    detail = response.json().get("detail", {})
    assert detail.get("error") == "invalid_id"
