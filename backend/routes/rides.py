# api/routes/rides.py
"""
FIT file ingestion pipeline for PacerAI (FIT-01 through FIT-06).

POST /rides/upload: accepts a multipart .FIT file upload, parses it with
fitdecode (ErrorHandling.WARN), runs the TSS/PMC pipeline in a background
task, and persists the result to rides and pmc_history.

Architecture decisions:
  - parse_fit_file is SYNC and runs under asyncio.to_thread (D-12: CPU-bound parse).
  - All Supabase calls in process_ride_background are ASYNC; never use to_thread
    for Supabase operations (Risk 4 in RESEARCH.md).
  - Cold-start FTP placeholder is 150W, recorded in rides.ftp_used for auditability
    and backfill (D-15, T-03-15).
  - Corrupt or too-short files return HTTP 422 with structured detail (D-14).
  - Filename is sanitized before use in Storage path (T-03-13: no path traversal).
  - Files > 25 MB are rejected before parsing (T-03-11: DoS guard).
  - process_ride_background triggers a ride_debrief conversation best-effort (D-23).

Threat mitigations applied:
  T-03-11: 25 MB size cap before parse
  T-03-12: fitdecode WARN + duration guard -> 422
  T-03-13: filename sanitized with os.path.basename + re.sub
  T-03-14: rides/pmc_history rows scoped to supplied user_id
  T-03-15: ftp_used column records 150.0 for cold-start estimation
"""
import asyncio
import hashlib
import io
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Optional

import fitdecode
import numpy as np
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile

from backend.auth import get_current_user
from backend.db import get_async_supabase as _get_async_supabase
from backend.pmc_recompute import recompute_pmc_for_user
from backend.utils import validate_uuid
from backend.sports_science.compliance import validate_session_vs_actual
from backend.sports_science.ftp import estimate_ftp_from_rides
from backend.sports_science.metrics import compute_tss

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB (T-03-11: DoS guard)
MIN_RIDE_DURATION_SECS = 600          # 10 minutes (NP_MIN_DURATION_SECS)
COLD_START_FTP = 150.0                # Placeholder FTP for new riders (D-15)

# UUID validation is provided by api.utils.validate_uuid (shared across all route modules).

# ---------------------------------------------------------------------------
# FIT parser (sync, runs under asyncio.to_thread)
# ---------------------------------------------------------------------------


def parse_fit_file(file_bytes: bytes) -> Optional[dict]:
    """
    Parse raw .FIT file bytes and extract power/HR/cadence arrays.

    SYNC -- must be called via asyncio.to_thread from the async endpoint (D-12).

    Uses fitdecode.ErrorHandling.WARN so malformed frames are logged rather
    than raising. Missing HR/cadence fields are handled gracefully via
    get_value fallback=None (FIT-03: missing fields never crash the parser).

    Logs the field names of the first record frame once so any Zwift-specific
    field-name differences surface immediately (RESEARCH Risk 3 / Open Question 3).

    Args:
        file_bytes: Raw bytes from the uploaded .FIT file.

    Returns:
        dict with keys: power_array, hr_array, cadence_array, duration_secs,
                        avg_power, avg_hr, avg_cadence.
        None if the file cannot be opened by fitdecode at all.
    """
    power_samples: list[float] = []
    hr_samples: list[float] = []
    cadence_samples: list[float] = []
    _first_record_logged = False
    # WR-009: capture ride start time from FIT session or first record timestamp
    # so we record the ride date the session occurred, not the upload date.
    ride_start_time: Optional[datetime] = None
    first_record_ts: Optional[datetime] = None
    # Track last record timestamp to compute accurate duration for non-1Hz files.
    # Smart-recording devices (Garmin, Wahoo) may emit fewer than 1 record/sec;
    # using (last - first) timestamp avoids undercounting duration.
    last_record_ts: Optional[datetime] = None

    try:
        with fitdecode.FitReader(
            io.BytesIO(file_bytes),
            error_handling=fitdecode.ErrorHandling.WARN,
        ) as reader:
            for frame in reader:
                if not isinstance(frame, fitdecode.FitDataMessage):
                    continue

                # Extract start_time from FIT session message (most reliable source).
                if frame.name == "session":
                    ts = frame.get_value("start_time", fallback=None)
                    if ts is not None and ride_start_time is None:
                        if isinstance(ts, datetime):
                            ride_start_time = ts
                    continue

                if frame.name != "record":
                    continue

                # Log field names of the very first record frame (Risk 3 / OQ-3 debug aid).
                if not _first_record_logged:
                    available_fields = [f.name for f in frame.fields]
                    logger.info(
                        "FIT first record fields: %s",
                        available_fields,
                    )
                    _first_record_logged = True

                power = frame.get_value("power", fallback=None)
                hr = frame.get_value("heart_rate", fallback=None)
                cadence = frame.get_value("cadence", fallback=None)
                ts = frame.get_value("timestamp", fallback=None)

                # Capture the earliest and latest record timestamps.
                # first_record_ts is used as fallback for ride date (WR-009).
                # last_record_ts is used for timestamp-based duration computation.
                if ts is not None and isinstance(ts, datetime):
                    if first_record_ts is None:
                        first_record_ts = ts
                    last_record_ts = ts

                # Power: zeros are valid (coasting still counts for NP). Convert None -> 0.
                power_samples.append(float(power) if power is not None else 0.0)

                # HR and cadence: only append when present (None means no sensor data).
                if hr is not None:
                    hr_samples.append(float(hr))
                if cadence is not None:
                    cadence_samples.append(float(cadence))

    except Exception as exc:
        logger.warning("fitdecode failed to open file: %s", exc)
        return None

    # Prefer timestamp-based duration (last minus first record) when both endpoints are
    # present. This correctly handles smart-recording devices that emit fewer than
    # 1 record/sec (e.g. Garmin auto-pause, Wahoo ELEMNT variable-rate recording).
    # Fall back to sample count only when timestamps are absent (legacy/synthetic files).
    if first_record_ts is not None and last_record_ts is not None and last_record_ts > first_record_ts:
        duration_secs = int((last_record_ts - first_record_ts).total_seconds()) + 1
        logger.info(
            "FIT duration from timestamps: %ds (first=%s, last=%s, samples=%d)",
            duration_secs, first_record_ts, last_record_ts, len(power_samples),
        )
    else:
        duration_secs = len(power_samples)
        logger.info(
            "FIT duration from sample count: %ds (no timestamps or single-point)",
            duration_secs,
        )

    # Compute averages; return None for sensors with no data.
    arr_power = np.array(power_samples, dtype=float)
    avg_power = float(np.mean(arr_power)) if len(arr_power) > 0 else None
    avg_hr = float(np.mean(np.array(hr_samples, dtype=float))) if hr_samples else None
    avg_cadence = (
        float(np.mean(np.array(cadence_samples, dtype=float))) if cadence_samples else None
    )

    # Prefer session start_time; fall back to earliest record timestamp; then None.
    start_time = ride_start_time or first_record_ts

    return {
        "power_array": power_samples,
        "hr_array": hr_samples,
        "cadence_array": cadence_samples,
        "duration_secs": duration_secs,
        "avg_power": avg_power,
        "avg_hr": avg_hr,
        "avg_cadence": avg_cadence,
        "start_time": start_time,
    }


# ---------------------------------------------------------------------------
# FTP resolution (cold-start safe)
# ---------------------------------------------------------------------------


async def get_user_ftp(user_id: str) -> tuple[float, bool]:
    """
    Return (ftp_watts, is_estimated) for the given user.

    Loads the user's recent rides from DB and runs estimate_ftp_from_rides.
    If the confidence is below 'medium' (insufficient data), returns the
    cold-start placeholder of 150W with is_estimated=True (D-15, T-03-15).

    Returns:
        (ftp, is_estimated) where is_estimated=True means 150W placeholder.
    """
    try:
        supabase = await _get_async_supabase()
        # Fetch recent rides with enough fields for CP model input
        result = await (
            supabase.table("rides")
            .select("duration_secs, avg_power, ftp_used")
            .eq("user_id", user_id)
            .order("ride_date", desc=True)
            .execute()
        )
        rides_data = result.data or []

        # Map rows into effort dicts expected by estimate_ftp_from_rides
        efforts = [
            {
                "duration_secs": row.get("duration_secs", 0),
                "mean_power_watts": row.get("avg_power") or 0,
            }
            for row in rides_data
        ]

        ftp_result = estimate_ftp_from_rides(efforts)
        confidence = (ftp_result.inputs or {}).get("confidence", "insufficient_data")
        ftp_value = ftp_result.value

        if ftp_value is not None and confidence in ("medium", "high"):
            resolved_ftp = float(ftp_value.get("ftp", COLD_START_FTP))  # ftp.py:100 returns "ftp"
            try:
                await (
                    supabase.table("profiles")
                    .update({"ftp": resolved_ftp})
                    .eq("user_id", user_id)
                    .execute()
                )
            except Exception as exc:
                logger.warning("profiles.ftp write-back failed (non-fatal): %s", exc)
            return (resolved_ftp, False)
    except Exception as exc:
        logger.warning("get_user_ftp failed, using cold-start placeholder: %s", exc)

    return (COLD_START_FTP, True)


# ---------------------------------------------------------------------------
# Background pipeline (D-15)
# ---------------------------------------------------------------------------


async def process_ride_background(
    ride_id: str,
    user_id: str,
    parsed: dict,
    ftp_used: float,
    ride_date: str,
) -> None:
    """
    Background pipeline: compute TSS, link the ride's session, persist results,
    recompute the full PMC series, trigger debrief.

    Task 3: inline-awaited from upload_fit (Vercel serverless constraint --
    no BackgroundTasks, which Vercel freezes after the response is sent).
    All DB operations use the async Supabase singleton with SERVICE_ROLE_KEY.

    Steps:
    1. compute_tss from power_array + ftp_used
    2. Ride-session link (Pattern 4): match a planned session scheduled on the
       ride's own ride_date (not upload date), flip it to 'completed', link
       rides.session_id, and run validate_session_vs_actual (FIT-05)
    3. UPDATE rides row with computed values
    4. recompute_pmc_for_user: rebuild the user's full daily PMC series from
       scratch (replaces the old single-EWMA-step-per-upload model, which
       could not represent gap-day decay or same-day summation; FIT-04, TOOL-05)
    5. Trigger ride_debrief conversation (D-23, best-effort)
    """
    try:
        supabase = await _get_async_supabase()

        # --- Step 1: TSS ---
        tss_result = compute_tss(
            parsed["power_array"],
            parsed["duration_secs"],
            ftp_used,
        )
        tss = None
        np_watts = None
        intensity_factor = None
        if tss_result.value is not None:
            tss = tss_result.value.get("tss")
            np_watts = tss_result.value.get("np_watts")
            intensity_factor = tss_result.value.get("intensity_factor")

        # --- Step 2: Ride-session link (Pattern 4, FIT-05, best-effort) ---
        # Match on the ride's own ride_date (not upload date) and status='planned'
        # only -- an already-consumed session can never match twice.
        compliance_result = None
        matched_session_id: Optional[str] = None
        try:
            session_result = await (
                supabase.table("sessions")
                .select("id, tss_target, type")
                .eq("user_id", user_id)
                .eq("scheduled_date", ride_date)
                .eq("status", "planned")
                # WR-02: deterministic tiebreak if multiple planned sessions
                # ever share a date -- never let the DB pick arbitrarily.
                .order("id", desc=False)
                .limit(1)
                .execute()
            )
            if session_result.data:
                matched_session = session_result.data[0]
                compliance_result = validate_session_vs_actual(
                    planned={"tss": matched_session.get("tss_target", 0)},
                    actual={"tss": tss if tss is not None else 0.0},
                )
                await (
                    supabase.table("sessions")
                    .update({"status": "completed"})
                    .eq("id", matched_session["id"])
                    .eq("user_id", user_id)
                    .execute()
                )
                matched_session_id = matched_session["id"]
        except Exception as exc:
            logger.info("Session compliance check skipped: %s", exc)

        # --- Step 3: UPDATE rides row ---
        ride_update: dict = {
            "tss": tss,
            "np_watts": np_watts,
            "intensity_factor": intensity_factor,
            "avg_power": parsed.get("avg_power"),
            "avg_hr": parsed.get("avg_hr"),
            "avg_cadence": parsed.get("avg_cadence"),
            "ftp_used": ftp_used,
        }
        if compliance_result and compliance_result.value:
            ride_update["compliance_pct"] = compliance_result.value.get("compliance_pct")
        if matched_session_id is not None:
            ride_update["session_id"] = matched_session_id

        try:
            await (
                supabase.table("rides")
                .update(ride_update)
                .eq("id", ride_id)
                .execute()
            )
        except Exception as exc:
            logger.error("Failed to update rides row %s: %s", ride_id, exc)

        # --- Step 4: Full PMC day-series recompute (FIT-04, TOOL-05) ---
        # Replaces the old single-EWMA-step-per-upload model; recompute_pmc_for_user
        # never raises (logs loudly and returns), so a PMC failure cannot fail this
        # ride's upload.
        await recompute_pmc_for_user(user_id, supabase)

        # --- Step 5: Trigger ride debrief conversation (D-23, best-effort) ---
        try:
            target_tss = None
            if compliance_result and compliance_result.value:
                # Compute target from delta: actual - delta = planned
                delta = compliance_result.value.get("delta_tss", 0)
                if tss is not None:
                    target_tss = tss - delta

            debrief_msg = (
                f"Your ride is complete. "
                f"TSS: {round(tss, 1) if tss is not None else 'N/A'}"
            )
            if target_tss is not None and tss is not None:
                debrief_msg += f" (target: {round(target_tss, 1)})"

            await (
                supabase.table("conversations")
                .insert(
                    {
                        "user_id": user_id,
                        "context_type": "ride_debrief",
                        "context_data": json.dumps(
                            {
                                "ride_id": ride_id,
                                "tss": tss,
                                "ftp_used": ftp_used,
                            }
                        ),
                    }
                )
                .execute()
            )
            logger.info("Ride debrief conversation created for ride %s", ride_id)
        except Exception as exc:
            logger.warning("Ride debrief conversation creation failed (best-effort): %s", exc)

    except Exception as exc:
        logger.error(
            "process_ride_background failed for ride %s: %s", ride_id, exc
        )


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter()


def _sanitize_filename(raw_filename: str) -> str:
    """
    Strip path components and replace unsafe characters in a filename.

    Prevents path traversal attacks in Storage paths (T-03-13).
    Keeps only alphanumeric, dash, underscore, dot characters.
    """
    # os.path.basename handles both / and \\ separators
    base = os.path.basename(raw_filename or "upload.fit")
    # Replace anything not in safe set with underscore
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", base)
    # Prevent hidden files and ensure non-empty
    safe = safe.lstrip(".") or "upload.fit"
    return safe


def _is_unique_violation(exc: Exception) -> bool:
    """
    Best-effort detection of a Postgres unique-constraint violation (SQLSTATE
    23505) surfaced through the Supabase/postgrest client. The exact exception
    class/shape varies across supabase-py versions, so this checks both a
    `.code` attribute (if present) and the string representation (T-06-06).
    """
    text = str(exc)
    code = getattr(exc, "code", None)
    return (
        code == "23505"
        or "23505" in text
        or "duplicate key value violates unique constraint" in text
    )


@router.post("/upload")
async def upload_fit(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """
    POST /rides/upload

    Accepts a multipart/form-data .FIT file upload. user_id is sourced from the
    verified JWT (Authorization: Bearer header). Do NOT include user_id in the form
    data -- the frontend sends only the file field.

    The ride pipeline (TSS, session link, PMC recompute, debrief) is inline-awaited
    before responding (Vercel serverless constraint: no BackgroundTasks, which
    Vercel freezes/kills after the response is sent).

    Returns: {"ride_id": str, "status": "processed"}
             or {"ride_id": str, "status": "duplicate", "duplicate": true} for a
             byte-identical re-upload (T-06-06).

    Errors:
        401 if JWT is missing or invalid
        422 if file > 25 MB (T-03-11: DoS size cap)
        422 if file is corrupt or < 600 seconds of data (D-14, T-03-12)
    """
    user_id = current_user["user_id"]
    # JWT sub is a valid Supabase UUID; validate_uuid kept as defence-in-depth
    # against malformed tokens that somehow bypass jwt.decode's sub claim check.
    validate_uuid(user_id, "user_id")

    # --- Size cap (T-03-11): read at most MAX_UPLOAD_BYTES+1 so we never load
    #     the full body of an oversized file into memory before rejecting it. ---
    file_bytes = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "fit_parse_failed",
                "detail": f"File too large: max {MAX_UPLOAD_BYTES // (1024*1024)} MB",
            },
        )

    # --- Parse in thread pool (D-12: CPU-bound, never block the event loop) ---
    parsed = await asyncio.to_thread(parse_fit_file, file_bytes)

    if parsed is None or parsed["duration_secs"] < MIN_RIDE_DURATION_SECS:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "fit_parse_failed",
                "detail": "File too short or unreadable (minimum 10 minutes of data required)",
            },
        )

    # --- Content-hash dedup pre-check (T-06-06): compute before further processing
    #     so a byte-identical re-upload short-circuits without wasting FTP/storage/
    #     insert work. The authoritative guard is the DB UNIQUE(user_id, content_hash)
    #     constraint (caught below at insert time to close the concurrent-upload race). ---
    content_hash = hashlib.sha256(file_bytes).hexdigest()
    supabase = await _get_async_supabase()
    try:
        existing = await (
            supabase.table("rides")
            .select("id")
            .eq("user_id", user_id)
            .eq("content_hash", content_hash)
            .execute()
        )
        if existing.data:
            return {
                "ride_id": existing.data[0]["id"],
                "status": "duplicate",
                "duplicate": True,
            }
    except Exception as exc:
        logger.warning("Content-hash dedup pre-check failed (non-fatal, proceeding): %s", exc)

    # --- Resolve FTP (cold-start: 150W, is_estimated=True) ---
    ftp_used, is_estimated = await get_user_ftp(user_id)

    # --- Content-addressed Storage path (T-06-12): identical content always maps to
    #     the same object, removing filename-collision/overwrite surprises. ---
    storage_path = f"fits/{user_id}/{content_hash}.fit"

    # --- Upload raw bytes to Supabase Storage (best-effort) ---
    try:
        supabase = await _get_async_supabase()
        await supabase.storage.from_("fits").upload(
            path=f"{user_id}/{content_hash}.fit",
            file=file_bytes,
            file_options={"content-type": "application/octet-stream"},
        )
    except Exception as exc:
        logger.warning("Storage upload failed (best-effort): %s", exc)
        storage_path = None  # type: ignore[assignment]

    # --- INSERT stub rides row ---
    # WR-009: use the ride's actual start_time from the FIT file so retroactive
    # uploads are recorded on the day the ride occurred, not the upload date.
    # Fall back to today only when no timestamp is present in the file.
    fit_start_time: Optional[datetime] = parsed.get("start_time")
    if fit_start_time is not None:
        # Ensure timezone-aware for consistent isoformat output.
        if fit_start_time.tzinfo is None:
            fit_start_time = fit_start_time.replace(tzinfo=timezone.utc)
        ride_date = fit_start_time.date().isoformat()
    else:
        ride_date = datetime.now(timezone.utc).date().isoformat()

    try:
        supabase = await _get_async_supabase()
        result = await (
            supabase.table("rides")
            .insert(
                {
                    "user_id": user_id,
                    "raw_fit_path": storage_path,
                    "ride_date": ride_date,
                    "duration_secs": parsed["duration_secs"],
                    "ftp_used": ftp_used,
                    "content_hash": content_hash,
                }
            )
            .execute()
        )
        ride_id: str = result.data[0]["id"]
    except Exception as exc:
        # T-06-06: a concurrent upload of the same content can race the pre-check
        # SELECT above; the DB UNIQUE(user_id, content_hash) constraint is the
        # authoritative guard -- catch its violation and fall back to duplicate=True
        # instead of a 500.
        if _is_unique_violation(exc):
            logger.info("Duplicate content_hash race caught at insert for user %s", user_id)
            try:
                existing_after_race = await (
                    supabase.table("rides")
                    .select("id")
                    .eq("user_id", user_id)
                    .eq("content_hash", content_hash)
                    .execute()
                )
                if existing_after_race.data:
                    return {
                        "ride_id": existing_after_race.data[0]["id"],
                        "status": "duplicate",
                        "duplicate": True,
                    }
            except Exception as lookup_exc:
                logger.warning(
                    "Post-race duplicate lookup failed (non-fatal): %s", lookup_exc
                )
        logger.error("Failed to insert rides row: %s", exc)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "db_insert_failed",
                "detail": "Could not persist ride record",
            },
        ) from exc

    # --- Run the ride pipeline inline-awaited (Vercel serverless constraint: no
    #     BackgroundTasks, which Vercel freezes/kills after the response is sent) ---
    await process_ride_background(
        ride_id,
        user_id,
        parsed,
        ftp_used,
        ride_date,
    )

    return {"ride_id": ride_id, "status": "processed"}


@router.get("/")
async def list_rides(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    GET /rides/

    Returns the authenticated user's ride history, newest first, limited to 50.
    user_id is sourced from the verified JWT sub claim (T-04-01).
    Rides are scoped to the requesting user (T-04-03 defence-in-depth).

    Returns: {"rides": [...]}
    """
    user_id = current_user["user_id"]
    supabase = await _get_async_supabase()

    result = await (
        supabase.table("rides")
        .select(
            "id, user_id, tss, np_watts, intensity_factor, duration_secs, "
            "ride_date, avg_power, avg_hr, avg_cadence, ftp_used, "
            "session_id, compliance_pct"
        )
        .eq("user_id", user_id)
        .order("ride_date", desc=True, nullsfirst=False)
        .limit(50)
        .execute()
    )

    return {"rides": result.data}
