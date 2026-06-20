# api/utils.py
"""Shared validation helpers used across API route modules."""

import re

from fastapi import HTTPException

# UUID v4 format regex — used for defence-in-depth input validation on all
# user_id and session_id parameters before any DB or storage access.
# Phase 4 JWT auth will make this redundant, but until then it blocks
# path traversal and trivial IDOR via malformed IDs (see rides.py, adaptations.py).
_UUID_RE = re.compile(
    r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
)


def validate_uuid(value: str, field: str = "id") -> None:
    """Raise HTTP 400 if value is not a valid UUID string."""
    if not _UUID_RE.match(value):
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_id", "detail": f"{field} must be a valid UUID"},
        )
