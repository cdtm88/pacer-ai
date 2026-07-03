# tests/api/test_rides.py
"""
Ride upload route tests (Wave 3 / FIT-01 through FIT-06).

Tests cover:
  FIT-01: POST /rides/upload returns 200 with ride_id
  FIT-02: fitdecode WARN parse does not raise on a real file
  FIT-03: Missing HR/cadence fields handled gracefully (None, not crash)
  FIT-04: TSS computed in background task (captured via mocked DB)
  FIT-05: validate_session_vs_actual called when matched planned session exists
  FIT-06: Real Zwift .FIT acceptance test (TSS > 0)
  Extra: 422 on corrupt byte blob

All Supabase calls are mocked; no live DB connections are made.
asyncio_mode = auto (pytest.ini) -- no @pytest.mark.asyncio needed.
"""
import pathlib
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from httpx import ASGITransport

from tests.api.conftest import TEST_USER_ID, TEST_JWT_SECRET, auth_headers

FIXTURE_PATH = pathlib.Path(__file__).parents[1] / "fixtures" / "sample_zwift.fit"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_rides_mock(ride_id="test-ride-001"):
    """
    Create a mock Supabase client that:
    - Returns a ride row on INSERT (for the stub insert)
    - Returns no rows on SELECT (first-ride cold-start: no PMC history, no FTP)
    - Accepts UPDATE without error
    - Accepts UPSERT without error

    Captures: .insert() call args for assertion, .update() call args for assertion.
    """
    execute_insert_result = MagicMock()
    execute_insert_result.data = [{"id": ride_id}]

    execute_empty_result = MagicMock()
    execute_empty_result.data = []

    # For update/upsert, return empty data
    execute_update_result = MagicMock()
    execute_update_result.data = []

    # Track which table is being called to return the right result
    # We do this by making table() return table-specific mocks
    rides_mock = MagicMock()
    rides_mock.insert = MagicMock(return_value=rides_mock)
    rides_mock.update = MagicMock(return_value=rides_mock)
    rides_mock.upsert = MagicMock(return_value=rides_mock)
    rides_mock.select = MagicMock(return_value=rides_mock)
    rides_mock.eq = MagicMock(return_value=rides_mock)
    rides_mock.order = MagicMock(return_value=rides_mock)

    # Return different results depending on context
    _call_count = {"n": 0}

    async def execute_dispatch():
        _call_count["n"] += 1
        # First execute: content-hash dedup pre-check SELECT -> no existing row
        if _call_count["n"] == 1:
            return execute_empty_result
        # Second execute: rides INSERT -> returns ride_id
        if _call_count["n"] == 2:
            return execute_insert_result
        # All subsequent: empty (PMC history, training_sessions, rides SELECT, etc.)
        return execute_empty_result

    rides_mock.execute = execute_dispatch

    storage_mock = MagicMock()
    storage_mock.from_ = MagicMock(return_value=storage_mock)
    storage_mock.upload = AsyncMock(return_value=MagicMock())

    client_mock = MagicMock()
    client_mock.table = MagicMock(return_value=rides_mock)
    client_mock.storage = storage_mock

    return client_mock, rides_mock


def _make_background_mock(ride_id="test-ride-001"):
    """
    Create a mock for process_ride_background tracking with captured args.
    We track the last call's arguments.
    """
    captured = {"args": None, "called": False}

    async def _mock_bg(*args, **kwargs):
        captured["args"] = args
        captured["called"] = True

    return _mock_bg, captured


# ---------------------------------------------------------------------------
# FIT-01: Upload returns 200 with ride_id
# ---------------------------------------------------------------------------


async def test_upload_returns_200(monkeypatch):
    """
    FIT-01: POST /rides/upload with a valid .FIT file returns 200 with ride_id.
    The ride pipeline is mocked to avoid live DB calls.
    Phase 4: request requires a valid JWT; user_id is no longer a form field.
    Task 3: the pipeline is inline-awaited (Vercel-safe); the returned status
    is 'processed', not the old BackgroundTasks-era 'processing'.
    """
    from backend.main import app
    import backend.routes.rides as rides_module

    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    client_mock, _ = _make_rides_mock()
    monkeypatch.setattr(rides_module, "_get_async_supabase", AsyncMock(return_value=client_mock))
    monkeypatch.setattr(
        rides_module, "get_user_ftp", AsyncMock(return_value=(150.0, True))
    )
    mock_bg, captured = _make_background_mock()
    monkeypatch.setattr(rides_module, "process_ride_background", mock_bg)

    assert FIXTURE_PATH.exists(), f"Test fixture missing: {FIXTURE_PATH}"

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        with open(FIXTURE_PATH, "rb") as f:
            response = await client.post(
                "/rides/upload",
                files={"file": ("sample_zwift.fit", f, "application/octet-stream")},
                headers=auth_headers(),
            )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    body = response.json()
    assert "ride_id" in body, f"Expected 'ride_id' in response: {body}"
    assert body["status"] == "processed", f"Expected status='processed': {body}"
    assert captured["called"] is True, "Expected process_ride_background to have run inline"


# ---------------------------------------------------------------------------
# Task 2: content-hash dedup (T-06-06)
# ---------------------------------------------------------------------------


async def test_dedup_precheck_short_circuits(monkeypatch):
    """
    Task 2: A byte-identical re-upload is caught by the content-hash pre-check
    SELECT and returns duplicate=true with no second rides insert.
    """
    from backend.main import app
    import backend.routes.rides as rides_module

    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)

    existing_result = MagicMock()
    existing_result.data = [{"id": "existing-ride-001"}]

    rides_mock = MagicMock()
    rides_mock.select = MagicMock(return_value=rides_mock)
    rides_mock.eq = MagicMock(return_value=rides_mock)
    rides_mock.insert = MagicMock(return_value=rides_mock)
    rides_mock.execute = AsyncMock(return_value=existing_result)

    storage_mock = MagicMock()
    storage_mock.from_ = MagicMock(return_value=storage_mock)
    storage_mock.upload = AsyncMock(return_value=MagicMock())

    client_mock = MagicMock()
    client_mock.table = MagicMock(return_value=rides_mock)
    client_mock.storage = storage_mock

    monkeypatch.setattr(rides_module, "_get_async_supabase", AsyncMock(return_value=client_mock))
    monkeypatch.setattr(rides_module, "get_user_ftp", AsyncMock(return_value=(150.0, True)))
    mock_bg, _captured = _make_background_mock()
    monkeypatch.setattr(rides_module, "process_ride_background", mock_bg)

    assert FIXTURE_PATH.exists(), f"Test fixture missing: {FIXTURE_PATH}"

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        with open(FIXTURE_PATH, "rb") as f:
            response = await client.post(
                "/rides/upload",
                files={"file": ("sample_zwift.fit", f, "application/octet-stream")},
                headers=auth_headers(),
            )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    body = response.json()
    assert body.get("duplicate") is True, f"Expected duplicate=True: {body}"
    assert body.get("status") == "duplicate", f"Expected status='duplicate': {body}"
    assert body.get("ride_id") == "existing-ride-001", f"Expected existing ride_id echoed back: {body}"
    assert rides_mock.insert.call_count == 0, "Duplicate short-circuit must not call insert"


async def test_dedup_unique_violation_returns_duplicate(monkeypatch):
    """
    Task 2 (T-06-06): a concurrent-upload race that slips past the pre-check
    SELECT and hits the DB UNIQUE(user_id, content_hash) constraint at INSERT
    time is caught and returns the same duplicate=true response, not a 500.
    """
    from backend.main import app
    import backend.routes.rides as rides_module

    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)

    empty_result = MagicMock()
    empty_result.data = []

    existing_after_race = MagicMock()
    existing_after_race.data = [{"id": "raced-ride-001"}]

    class FakeUniqueViolation(Exception):
        code = "23505"

    call_state = {"n": 0}

    async def execute_dispatch():
        call_state["n"] += 1
        if call_state["n"] == 1:
            return empty_result  # pre-check: no duplicate found
        if call_state["n"] == 2:
            raise FakeUniqueViolation(
                'duplicate key value violates unique constraint "rides_user_content_hash_unique"'
            )
        return existing_after_race  # post-race re-check finds the row the other request inserted

    rides_mock = MagicMock()
    rides_mock.select = MagicMock(return_value=rides_mock)
    rides_mock.eq = MagicMock(return_value=rides_mock)
    rides_mock.insert = MagicMock(return_value=rides_mock)
    rides_mock.execute = execute_dispatch

    storage_mock = MagicMock()
    storage_mock.from_ = MagicMock(return_value=storage_mock)
    storage_mock.upload = AsyncMock(return_value=MagicMock())

    client_mock = MagicMock()
    client_mock.table = MagicMock(return_value=rides_mock)
    client_mock.storage = storage_mock

    monkeypatch.setattr(rides_module, "_get_async_supabase", AsyncMock(return_value=client_mock))
    monkeypatch.setattr(rides_module, "get_user_ftp", AsyncMock(return_value=(150.0, True)))
    mock_bg, _captured = _make_background_mock()
    monkeypatch.setattr(rides_module, "process_ride_background", mock_bg)

    assert FIXTURE_PATH.exists(), f"Test fixture missing: {FIXTURE_PATH}"

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        with open(FIXTURE_PATH, "rb") as f:
            response = await client.post(
                "/rides/upload",
                files={"file": ("sample_zwift.fit", f, "application/octet-stream")},
                headers=auth_headers(),
            )

    assert response.status_code == 200, (
        f"Expected 200 (duplicate), got {response.status_code}: {response.text}"
    )
    body = response.json()
    assert body.get("duplicate") is True, f"Expected duplicate=True after unique-violation race: {body}"
    assert body.get("ride_id") == "raced-ride-001", f"Expected raced ride_id echoed back: {body}"


# ---------------------------------------------------------------------------
# Task 1: get_user_ftp reads the correct 'ftp' key and writes back profiles.ftp
# ---------------------------------------------------------------------------


async def test_get_user_ftp_writeback(monkeypatch):
    """
    Task 1: get_user_ftp reads the estimated value from key 'ftp' (not the
    stale 'ftp_watts' key) and, when confidence is medium/high, writes the
    resolved value back to profiles.ftp filtered by user_id (T-06-08).
    """
    from backend.sports_science.types import ToolResult
    import backend.routes.rides as rides_module

    fake_result = ToolResult(
        value={"ftp": 245.3, "cp": 245.3, "wprime": 20000.0, "confidence": "medium"},
        unit="watts",
        methodology="test",
        inputs={"confidence": "medium"},
    )
    monkeypatch.setattr(rides_module, "estimate_ftp_from_rides", lambda efforts: fake_result)

    update_calls: list[dict] = []

    profiles_mock = MagicMock()

    def capture_profile_update(payload):
        update_calls.append(payload)
        return profiles_mock

    profiles_mock.update = MagicMock(side_effect=capture_profile_update)
    profiles_mock.eq = MagicMock(return_value=profiles_mock)
    profiles_mock.execute = AsyncMock(return_value=MagicMock(data=[]))

    rides_mock = MagicMock()
    rides_mock.select = MagicMock(return_value=rides_mock)
    rides_mock.eq = MagicMock(return_value=rides_mock)
    rides_mock.order = MagicMock(return_value=rides_mock)
    rides_mock.execute = AsyncMock(return_value=MagicMock(data=[]))

    def table_dispatch(name):
        return profiles_mock if name == "profiles" else rides_mock

    client_mock = MagicMock()
    client_mock.table = MagicMock(side_effect=table_dispatch)

    monkeypatch.setattr(rides_module, "_get_async_supabase", AsyncMock(return_value=client_mock))

    ftp, is_estimated = await rides_module.get_user_ftp(TEST_USER_ID)

    assert ftp == 245.3, f"Expected estimated FTP 245.3 read from key 'ftp', got {ftp}"
    assert is_estimated is False, "Expected is_estimated=False for a medium-confidence estimate"

    assert len(update_calls) == 1, (
        f"Expected exactly one profiles.ftp write-back call, got {update_calls}"
    )
    assert update_calls[0] == {"ftp": 245.3}, f"Unexpected profiles update payload: {update_calls[0]}"
    profiles_mock.eq.assert_called_with("user_id", TEST_USER_ID)


async def test_get_user_ftp_cold_start_unchanged(monkeypatch):
    """
    Task 1 regression guard: insufficient-data confidence still returns the
    cold-start placeholder with is_estimated=True and issues no profiles write.
    """
    from backend.sports_science.types import ToolResult
    import backend.routes.rides as rides_module

    fake_result = ToolResult(
        value=None,
        unit="watts",
        methodology="test",
        inputs={"confidence": "insufficient_data"},
    )
    monkeypatch.setattr(rides_module, "estimate_ftp_from_rides", lambda efforts: fake_result)

    rides_mock = MagicMock()
    rides_mock.select = MagicMock(return_value=rides_mock)
    rides_mock.eq = MagicMock(return_value=rides_mock)
    rides_mock.order = MagicMock(return_value=rides_mock)
    rides_mock.execute = AsyncMock(return_value=MagicMock(data=[]))

    client_mock = MagicMock()
    client_mock.table = MagicMock(return_value=rides_mock)

    monkeypatch.setattr(rides_module, "_get_async_supabase", AsyncMock(return_value=client_mock))

    ftp, is_estimated = await rides_module.get_user_ftp(TEST_USER_ID)

    assert ftp == rides_module.COLD_START_FTP
    assert is_estimated is True


# ---------------------------------------------------------------------------
# FIT-02: fitdecode WARN parse on real file (no exception raised)
# ---------------------------------------------------------------------------


def test_fit_parse_warn():
    """
    FIT-02: parse_fit_file on the real .FIT fixture returns a non-empty power_array
    and does not raise (ErrorHandling.WARN swallows bad frames).
    """
    from backend.routes.rides import parse_fit_file

    assert FIXTURE_PATH.exists(), f"Test fixture missing: {FIXTURE_PATH}"
    file_bytes = FIXTURE_PATH.read_bytes()

    result = parse_fit_file(file_bytes)

    assert result is not None, "parse_fit_file returned None for a valid .FIT file"
    assert len(result["power_array"]) > 0, (
        f"Expected non-empty power_array; got {len(result['power_array'])} samples"
    )
    assert result["duration_secs"] >= 600, (
        f"Expected >= 600 seconds duration; got {result['duration_secs']}"
    )


# ---------------------------------------------------------------------------
# FIT-03: Missing HR/cadence fields handled gracefully
# ---------------------------------------------------------------------------


def test_missing_fields():
    """
    FIT-03: When HR and cadence are missing from all record frames,
    parse_fit_file returns avg_hr=None and avg_cadence=None without raising.
    """
    import fitdecode
    from backend.routes.rides import parse_fit_file

    assert FIXTURE_PATH.exists(), f"Test fixture missing: {FIXTURE_PATH}"
    file_bytes = FIXTURE_PATH.read_bytes()

    # Patch fitdecode.FitDataMessage.get_value to return None for hr and cadence
    original_get_value = fitdecode.FitDataMessage.get_value

    def patched_get_value(self, field_name, *args, fallback=None, **kwargs):
        if field_name in ("heart_rate", "cadence"):
            return None
        return original_get_value(self, field_name, *args, fallback=fallback, **kwargs)

    fitdecode.FitDataMessage.get_value = patched_get_value
    try:
        result = parse_fit_file(file_bytes)
    finally:
        fitdecode.FitDataMessage.get_value = original_get_value

    assert result is not None, "parse_fit_file returned None unexpectedly"
    assert result["avg_hr"] is None, f"Expected avg_hr=None when HR missing, got {result['avg_hr']}"
    assert result["avg_cadence"] is None, (
        f"Expected avg_cadence=None when cadence missing, got {result['avg_cadence']}"
    )
    # Power array must still be populated
    assert len(result["power_array"]) > 0, "Power array empty when only HR/cadence patched out"


# ---------------------------------------------------------------------------
# FIT-04: TSS computed in background task
# ---------------------------------------------------------------------------


async def test_tss_computed():
    """
    FIT-04: process_ride_background computes TSS and fires a rides UPDATE
    with tss > 0 when given a valid parsed dict from the real fixture.
    """
    from backend.routes.rides import parse_fit_file, process_ride_background

    assert FIXTURE_PATH.exists(), f"Test fixture missing: {FIXTURE_PATH}"
    file_bytes = FIXTURE_PATH.read_bytes()
    parsed = parse_fit_file(file_bytes)
    assert parsed is not None, "Fixture parse returned None"

    # Track all calls to the rides mock
    update_payloads: list[dict] = []
    upsert_payloads: list[dict] = []

    # Build a carefully tracked mock
    execute_result = MagicMock()
    execute_result.data = []  # empty for all queries (cold start, no history)

    chain_mock = MagicMock()
    chain_mock.select.return_value = chain_mock
    chain_mock.insert.return_value = chain_mock
    chain_mock.upsert.return_value = chain_mock
    chain_mock.update.return_value = chain_mock
    chain_mock.eq.return_value = chain_mock
    chain_mock.order.return_value = chain_mock
    chain_mock.limit.return_value = chain_mock
    chain_mock.execute = AsyncMock(return_value=execute_result)

    # Intercept update calls to capture payloads
    real_update = chain_mock.update

    def capture_update(payload):
        update_payloads.append(payload)
        return chain_mock

    chain_mock.update = capture_update

    def capture_upsert(payload, **kwargs):
        upsert_payloads.append(payload)
        return chain_mock

    chain_mock.upsert = capture_upsert

    client_mock = MagicMock()
    client_mock.table.return_value = chain_mock
    client_mock.storage = MagicMock()

    import backend.routes.rides as rides_module
    original_get = rides_module._get_async_supabase

    async def mock_get_supabase():
        return client_mock

    rides_module._get_async_supabase = mock_get_supabase
    try:
        await process_ride_background(
            ride_id="test-ride-tss-001",
            user_id=TEST_USER_ID,
            parsed=parsed,
            ftp_used=150.0,
            ride_date="2026-06-01",
        )
    finally:
        rides_module._get_async_supabase = original_get

    # Assert the rides UPDATE was called with tss > 0
    assert len(update_payloads) >= 1, (
        "Expected at least one rides UPDATE call; background task did not update the ride"
    )
    ride_payload = update_payloads[0]
    assert "tss" in ride_payload, f"rides UPDATE payload missing 'tss': {ride_payload}"
    assert ride_payload["tss"] is not None, "TSS is None in rides UPDATE payload"
    assert ride_payload["tss"] > 0, (
        f"Expected TSS > 0, got {ride_payload['tss']} (real fixture with ~154W power)"
    )
    assert "np_watts" in ride_payload, "rides UPDATE missing np_watts"
    assert "intensity_factor" in ride_payload, "rides UPDATE missing intensity_factor"

    # Assert a pmc_history UPSERT was attempted
    assert len(upsert_payloads) >= 1, (
        "Expected at least one pmc_history UPSERT; background task did not update PMC"
    )
    pmc_payload = upsert_payloads[0]
    assert "ctl" in pmc_payload, f"pmc_history UPSERT missing 'ctl': {pmc_payload}"
    assert "atl" in pmc_payload, f"pmc_history UPSERT missing 'atl': {pmc_payload}"


# ---------------------------------------------------------------------------
# FIT-05: validate_session_vs_actual called when planned session exists
# ---------------------------------------------------------------------------


async def test_session_compliance():
    """
    FIT-05: When a training_sessions row exists for today, process_ride_background
    calls validate_session_vs_actual and its compliance_pct is included in the
    rides UPDATE payload.
    """
    from backend.routes.rides import parse_fit_file, process_ride_background

    assert FIXTURE_PATH.exists(), f"Test fixture missing: {FIXTURE_PATH}"
    file_bytes = FIXTURE_PATH.read_bytes()
    parsed = parse_fit_file(file_bytes)
    assert parsed is not None

    # Build mock that returns a planned session on the training_sessions SELECT
    update_payloads: list[dict] = []
    upsert_payloads: list[dict] = []
    call_count = {"n": 0}

    planned_session_row = {"tss": 50.0, "session_type": "endurance"}

    execute_with_session = MagicMock()
    execute_with_session.data = [planned_session_row]

    execute_empty = MagicMock()
    execute_empty.data = []

    chain_mock = MagicMock()
    chain_mock.select.return_value = chain_mock
    chain_mock.insert.return_value = chain_mock
    chain_mock.eq.return_value = chain_mock
    chain_mock.order.return_value = chain_mock
    chain_mock.limit.return_value = chain_mock

    def capture_update(payload):
        update_payloads.append(payload)
        return chain_mock

    def capture_upsert(payload, **kwargs):
        upsert_payloads.append(payload)
        return chain_mock

    chain_mock.update = capture_update
    chain_mock.upsert = capture_upsert

    # Decide which result to return based on call count
    async def execute_dispatch():
        call_count["n"] += 1
        # First call: pmc_history SELECT -> empty (cold start)
        # Second call: sessions SELECT (ride_date + status='planned') -> planned session
        # All others: empty
        if call_count["n"] == 2:
            return execute_with_session
        return execute_empty

    chain_mock.execute = execute_dispatch

    client_mock = MagicMock()
    client_mock.table.return_value = chain_mock
    client_mock.storage = MagicMock()

    import backend.routes.rides as rides_module
    original_get = rides_module._get_async_supabase

    async def mock_get_supabase():
        return client_mock

    rides_module._get_async_supabase = mock_get_supabase
    try:
        await process_ride_background(
            ride_id="test-ride-compliance-001",
            user_id=TEST_USER_ID,
            parsed=parsed,
            ftp_used=150.0,
            ride_date="2026-06-01",
        )
    finally:
        rides_module._get_async_supabase = original_get

    # Assert rides UPDATE includes compliance_pct (validate_session_vs_actual was called).
    # Find the rides UPDATE payload (contains "tss") rather than assuming index 0, since
    # the session-flip UPDATE ({"status": "completed"}) may now be captured first.
    ride_payload = next((p for p in update_payloads if "tss" in p), None)
    assert ride_payload is not None, (
        f"Expected a rides UPDATE payload (containing 'tss'): {update_payloads}"
    )
    assert "compliance_pct" in ride_payload, (
        f"Expected 'compliance_pct' in rides UPDATE when planned session exists. "
        f"Got: {ride_payload}"
    )


# ---------------------------------------------------------------------------
# Task 2: ride-session link (Pattern 4) replaces "first session today" match
# ---------------------------------------------------------------------------


async def test_session_link_flips_planned_session_to_completed():
    """
    Task 2: process_ride_background matches a session scheduled on the ride's
    own ride_date with status 'planned', flips it to 'completed', and sets
    rides.session_id -- replacing the old "first session today" fuzzy match.
    """
    from backend.routes.rides import parse_fit_file, process_ride_background

    assert FIXTURE_PATH.exists(), f"Test fixture missing: {FIXTURE_PATH}"
    file_bytes = FIXTURE_PATH.read_bytes()
    parsed = parse_fit_file(file_bytes)
    assert parsed is not None

    ride_date = "2026-06-15"
    matched_session_row = {"id": "session-abc-001", "tss_target": 50.0, "type": "endurance"}

    eq_calls: list[tuple] = []
    update_payloads: list[dict] = []
    upsert_payloads: list[dict] = []

    execute_with_session = MagicMock()
    execute_with_session.data = [matched_session_row]
    execute_empty = MagicMock()
    execute_empty.data = []

    chain_mock = MagicMock()
    chain_mock.select.return_value = chain_mock
    chain_mock.insert.return_value = chain_mock
    chain_mock.order.return_value = chain_mock
    chain_mock.limit.return_value = chain_mock

    def capture_eq(*args):
        eq_calls.append(args)
        return chain_mock

    chain_mock.eq = MagicMock(side_effect=capture_eq)

    def capture_update(payload):
        update_payloads.append(payload)
        return chain_mock

    def capture_upsert(payload, **kwargs):
        upsert_payloads.append(payload)
        return chain_mock

    chain_mock.update = capture_update
    chain_mock.upsert = capture_upsert

    call_count = {"n": 0}

    async def execute_dispatch():
        call_count["n"] += 1
        # Call 1: pmc_history SELECT -> empty (cold start)
        # Call 2: sessions SELECT (ride_date + status='planned') -> matched session
        # All others: empty
        if call_count["n"] == 2:
            return execute_with_session
        return execute_empty

    chain_mock.execute = execute_dispatch

    client_mock = MagicMock()
    client_mock.table.return_value = chain_mock
    client_mock.storage = MagicMock()

    import backend.routes.rides as rides_module
    original_get = rides_module._get_async_supabase

    async def mock_get_supabase():
        return client_mock

    rides_module._get_async_supabase = mock_get_supabase
    try:
        await process_ride_background(
            ride_id="test-ride-session-link-001",
            user_id=TEST_USER_ID,
            parsed=parsed,
            ftp_used=150.0,
            ride_date=ride_date,
        )
    finally:
        rides_module._get_async_supabase = original_get

    # Assert the sessions query matched on the ride's own ride_date and status='planned'
    assert ("scheduled_date", ride_date) in eq_calls, (
        f"Expected sessions query filtered by scheduled_date={ride_date}: {eq_calls}"
    )
    assert ("status", "planned") in eq_calls, (
        f"Expected sessions query filtered by status='planned': {eq_calls}"
    )

    # Assert the matched session was flipped to completed
    assert {"status": "completed"} in update_payloads, (
        f"Expected a sessions UPDATE flipping status to 'completed': {update_payloads}"
    )

    # Assert rides.session_id is set on the rides UPDATE payload (contains "tss")
    ride_update_payload = next((p for p in update_payloads if "tss" in p), None)
    assert ride_update_payload is not None, "Expected a rides UPDATE payload containing tss"
    assert ride_update_payload.get("session_id") == "session-abc-001", (
        f"Expected rides UPDATE to set session_id: {ride_update_payload}"
    )


# ---------------------------------------------------------------------------
# FIT-06: Real Zwift .FIT acceptance test (TSS > 0)
# ---------------------------------------------------------------------------


async def test_fit_upload_integration(monkeypatch):
    """
    FIT-06 / D-13: Upload the real Zwift .FIT fixture end-to-end.

    Asserts:
    - HTTP 200 with ride_id
    - No 422 parse error
    - The ride pipeline (mocked, inline-awaited per Task 3) produces TSS > 0

    DB is mocked to avoid live Supabase connections.
    """
    from backend.main import app
    import backend.routes.rides as rides_module

    assert FIXTURE_PATH.exists(), (
        f"Real Zwift .FIT fixture missing at {FIXTURE_PATH}. "
        "This test requires tests/fixtures/sample_zwift.fit (generated in Plan 03-02). "
        "TSS > 0 assertion cannot be weakened -- fixture must be present."
    )

    # Track inline-awaited pipeline args to assert TSS > 0 after driving it
    bg_args: dict = {}

    async def capture_bg(ride_id, user_id, parsed, ftp_used, ride_date):
        bg_args["ride_id"] = ride_id
        bg_args["parsed"] = parsed
        bg_args["ftp_used"] = ftp_used
        bg_args["ride_date"] = ride_date

    client_mock, _ = _make_rides_mock(ride_id="integration-ride-001")
    monkeypatch.setattr(rides_module, "_get_async_supabase", AsyncMock(return_value=client_mock))
    monkeypatch.setattr(
        rides_module, "get_user_ftp", AsyncMock(return_value=(150.0, True))
    )
    monkeypatch.setattr(rides_module, "process_ride_background", capture_bg)

    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        with open(FIXTURE_PATH, "rb") as f:
            response = await client.post(
                "/rides/upload",
                files={"file": ("sample_zwift.fit", f, "application/octet-stream")},
                headers=auth_headers(),
            )

    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text}"
    )
    body = response.json()
    assert "ride_id" in body, f"Expected 'ride_id' in body: {body}"
    assert body.get("status") == "processed", f"Expected status='processed': {body}"

    # Drive TSS computation directly from the captured parsed dict (FIT-06 core assertion)
    from backend.sports_science.metrics import compute_tss

    assert "parsed" in bg_args, "Background task was not invoked with parsed FIT data"
    parsed = bg_args["parsed"]
    ftp_used = bg_args.get("ftp_used", 150.0)

    tss_result = compute_tss(parsed["power_array"], parsed["duration_secs"], ftp_used)
    assert tss_result.value is not None, (
        f"compute_tss returned None value for real fixture. "
        f"duration_secs={parsed['duration_secs']}, power_records={len(parsed['power_array'])}"
    )
    tss = tss_result.value["tss"]
    assert tss > 0, (
        f"FIT-06 FAILED: TSS must be > 0 for real Zwift fixture. Got TSS={tss}. "
        f"Fixture: {FIXTURE_PATH}, duration_secs={parsed['duration_secs']}, "
        f"avg_power={parsed.get('avg_power')}"
    )


# ---------------------------------------------------------------------------
# 422 on corrupt bytes
# ---------------------------------------------------------------------------


async def test_corrupt_fit_returns_422(monkeypatch):
    """
    D-14: Sending non-FIT bytes returns HTTP 422 with error='fit_parse_failed'.
    Phase 4: a valid JWT is required; auth runs before file parsing so we must
    include the Authorization header to exercise the 422 parse-error path.
    """
    from backend.main import app
    import backend.routes.rides as rides_module

    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)

    # No Supabase mock needed -- 422 is returned before any DB call
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/rides/upload",
            files={"file": ("bad.fit", b"not a fit file at all", "application/octet-stream")},
            headers=auth_headers(),
        )

    assert response.status_code == 422, (
        f"Expected 422 for corrupt FIT bytes, got {response.status_code}: {response.text}"
    )
    detail = response.json().get("detail", {})
    assert isinstance(detail, dict), f"Expected dict detail, got: {detail}"
    assert detail.get("error") == "fit_parse_failed", (
        f"Expected error='fit_parse_failed', got: {detail}"
    )


# ---------------------------------------------------------------------------
# Non-skipped: fixture existence check (preserved from Wave 0)
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
