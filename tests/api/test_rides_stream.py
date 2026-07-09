# tests/api/test_rides_stream.py
"""
Backend parser/util tests for Phase 11 Wave 0 (RIDE-01, RIDE-02, RIDE-03).

Covers:
  - detect_presence / downsample pure-function behavior (backend/routes/_stream_utils.py)
  - parse_fit_stream aligned per-second channel arrays + lap_bounds
    (backend/routes/rides.py::parse_fit_stream)

These are plain sync unit tests (no asyncio marker needed -- asyncio_mode=auto
per pytest.ini, but parse_fit_stream/detect_presence/downsample are all sync
functions with no await inside them).

The stream-endpoint (GET /rides/{id}/stream) integration tests are appended
by plan 11-03; this file only covers the data layer.
"""
import pathlib

ZWIFT_FIXTURE_PATH = pathlib.Path(__file__).parents[1] / "fixtures" / "zwift_ride_30min.fit"
HILLY_FIXTURE_PATH = pathlib.Path(__file__).parents[1] / "fixtures" / "hilly_ride_30min.fit"


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
