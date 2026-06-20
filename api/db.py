# api/db.py
"""
Shared async Supabase client singleton for PacerAI (WR-003).

Centralises the _supabase_client singleton that was previously duplicated
across six modules (adaptations, calendar, onboarding, rides, sessions,
calendar_sync). A single connection pool is more efficient and any change to
initialisation logic (pool limits, lifespan, service-role key rotation)
now only needs to be made here.

Test monkeypatching:
    import api.db as db_module
    db_module._supabase_client = my_mock_client
"""

import os
from typing import Optional

from supabase import AsyncClient, acreate_client

_supabase_client: Optional[AsyncClient] = None


async def get_async_supabase() -> AsyncClient:
    """
    Return a cached async Supabase client using the service-role key (bypasses RLS).

    Creates the client once and reuses it across calls to avoid leaking
    httpx connection pools. The singleton is process-level and is never
    explicitly closed (acceptable for a long-lived server process).

    Raises:
        EnvironmentError: When SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY are absent.
    """
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise EnvironmentError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set"
        )
    _supabase_client = await acreate_client(url, key)
    return _supabase_client
