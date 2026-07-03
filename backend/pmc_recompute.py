# backend/pmc_recompute.py
"""
PMC day-series recompute orchestrator (TOOL-05, FIT-04).

Replaces the broken single-EWMA-step-per-upload model (which never decays
CTL/ATL on rest days, double-steps and overwrites tss on same-day re-uploads,
and corrupts the series on retroactive uploads). This module rebuilds the
entire canonical daily-TSS series -- grouped and summed by ride_date -- from
a user's earliest ride to today, walks every calendar day through the
existing pure `update_pmc` (backend/sports_science/pmc.py, unchanged and
untouched by this module), and bulk-upserts the resulting pmc_history rows
in a single round-trip.

This is called inline-awaited from the ride-upload pipeline (plan 06-05);
no BackgroundTasks (Vercel serverless constraint), no manual/admin recompute
endpoint (orchestrator decision, Phase 6 scope).

Threat mitigations applied:
  T-06-03: every rides read is scoped by .eq("user_id", user_id); the
           function never operates across users.
"""
import logging
from datetime import date, timedelta

from backend.sports_science.pmc import update_pmc

logger = logging.getLogger(__name__)


async def recompute_pmc_for_user(user_id: str, supabase) -> None:
    """
    Rebuild the full daily PMC series for a user from scratch and bulk-upsert it.

    Args:
        user_id: The user whose rides/pmc_history are recomputed. Every query
            is scoped to this user (T-06-03).
        supabase: An already-acquired async Supabase client (caller controls
            the singleton; tests inject a mock).

    Behavior:
        - Fetch all rides for the user with ride_date and tss; ignore rows
          missing either field.
        - Group-sum tss by calendar date (same-day rides summed, not
          overwritten).
        - Walk from the earliest ride date to date.today() inclusive, one
          calendar day at a time. days_of_data increments once per calendar
          day (not per upload/ride row).
        - Each day: tss_today is the summed tss for that date, or 0.0 for a
          gap day (drives CTL/ATL decay via the pure update_pmc step).
        - Single bulk upsert of all rows, on_conflict="user_id,date" (makes
          re-running idempotent).
        - No rides -> return without writing.

    A read or write failure is logged loudly (logger.error, not warning --
    the rest of the system depends on this write) but never raised out: the
    caller inline-awaits this from the upload path and a PMC failure must
    not fail the whole upload.
    """
    try:
        rides_resp = await (
            supabase.table("rides")
            .select("ride_date, tss")
            .eq("user_id", user_id)
            .execute()
        )
    except Exception as exc:
        logger.error("Failed to load rides for PMC recompute (user %s): %s", user_id, exc)
        return

    rides = [
        r
        for r in (rides_resp.data or [])
        if r.get("ride_date") and r.get("tss") is not None
    ]
    if not rides:
        return

    # Group-sum same-day rides (handles same-day double upload correctly).
    tss_by_day: dict = {}
    for r in rides:
        d = date.fromisoformat(r["ride_date"])
        tss_by_day[d] = tss_by_day.get(d, 0.0) + float(r["tss"])

    start = min(tss_by_day)
    today = date.today()

    prev_ctl = prev_atl = 0.0
    days_of_data = 0
    rows_to_upsert = []
    d = start
    while d <= today:
        days_of_data += 1  # calendar days elapsed, NOT upload count
        tss_today = tss_by_day.get(d, 0.0)  # zero-TSS gap fill (decay)
        result = update_pmc(prev_ctl, prev_atl, tss_today, days_of_data)
        v = result.value
        rows_to_upsert.append(
            {
                "user_id": user_id,
                "date": d.isoformat(),
                "ctl": v["ctl"],
                "atl": v["atl"],
                "tsb": v["tsb"],
                "tss": tss_today,
                "days_of_data": days_of_data,
                "tss_display_ready": v["tss_display_ready"],
            }
        )
        prev_ctl, prev_atl = v["ctl"], v["atl"]
        d += timedelta(days=1)

    try:
        await (
            supabase.table("pmc_history")
            .upsert(rows_to_upsert, on_conflict="user_id,date")
            .execute()
        )
    except Exception as exc:
        logger.error("Failed to bulk upsert pmc_history for user %s: %s", user_id, exc)
