# tests/test_pmc_recompute.py
"""
Tests for backend/pmc_recompute.py::recompute_pmc_for_user (TOOL-05, FIT-04).

recompute_pmc_for_user rebuilds the entire daily PMC series from a user's
rides (grouped/summed by ride_date) through the pure update_pmc step, then
issues a single bulk upsert. These tests assert on the captured bulk-upsert
payload rather than a live DB, per RESEARCH Validation Architecture -k
selectors: gap_days, same_day_sum, days_of_data_calendar.
"""
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

from backend.pmc_recompute import recompute_pmc_for_user


def _mock_supabase(rides_rows: list) -> MagicMock:
    """
    Build a mock supabase client.

    - table(...).select(...).eq(...).execute() returns rides_rows in .data
      (this module only ever selects from "rides", so one fixture suffices).
    - table(...).upsert(rows, on_conflict=...).execute() is captured on
      mock_client.upsert.call_args so tests can assert on the exact row list
      built by the day-series logic under test, not a live DB.
    """
    execute_result = MagicMock()
    execute_result.data = rides_rows

    mock_client = MagicMock()
    mock_client.table.return_value = mock_client
    mock_client.select.return_value = mock_client
    mock_client.eq.return_value = mock_client
    mock_client.upsert.return_value = mock_client
    mock_client.execute = AsyncMock(return_value=execute_result)

    return mock_client


async def test_gap_days_produce_zero_tss_rows_and_ctl_decay():
    """Rides on day 1 and day 5 produce a 5-row series; days 2-4 are TSS=0.0
    gap-fill rows and CTL is strictly non-increasing across the gap (decay)."""
    today = date.today()
    first = today - timedelta(days=4)
    rides = [
        {"ride_date": first.isoformat(), "tss": 100.0},
        {"ride_date": today.isoformat(), "tss": 100.0},
    ]
    supabase = _mock_supabase(rides)

    await recompute_pmc_for_user("user-1", supabase)

    assert supabase.upsert.call_count == 1
    rows = supabase.upsert.call_args[0][0]
    assert len(rows) == 5

    gap_rows = rows[1:4]
    assert all(r["tss"] == 0.0 for r in gap_rows), gap_rows

    ctl_values = [r["ctl"] for r in rows]
    for i in range(1, 4):
        assert ctl_values[i] <= ctl_values[i - 1], (
            f"CTL should decay (non-increasing) across gap day {i}: {ctl_values}"
        )


async def test_same_day_sum_combines_two_rides_into_one_row():
    """Two rides on the same date with tss 50 and 30 produce a single row
    for that date whose tss equals 80 (summed, not overwritten)."""
    today = date.today()
    rides = [
        {"ride_date": today.isoformat(), "tss": 50.0},
        {"ride_date": today.isoformat(), "tss": 30.0},
    ]
    supabase = _mock_supabase(rides)

    await recompute_pmc_for_user("user-1", supabase)

    rows = supabase.upsert.call_args[0][0]
    assert len(rows) == 1
    assert rows[0]["tss"] == 80.0


async def test_days_of_data_calendar_counts_calendar_days_not_rides():
    """Row count equals the calendar-day span from first ride to today
    inclusive, and days_of_data on the last row equals that same count --
    not the number of rides (2 rides here, but a 10-day span)."""
    today = date.today()
    first = today - timedelta(days=9)
    mid = today - timedelta(days=5)
    rides = [
        {"ride_date": first.isoformat(), "tss": 60.0},
        {"ride_date": mid.isoformat(), "tss": 40.0},
    ]
    supabase = _mock_supabase(rides)

    await recompute_pmc_for_user("user-1", supabase)

    rows = supabase.upsert.call_args[0][0]
    expected_days = (today - first).days + 1
    assert len(rows) == expected_days
    assert rows[-1]["days_of_data"] == expected_days
    assert expected_days != len(rides)
