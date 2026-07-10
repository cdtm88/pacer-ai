# Phase 03: Coaching Loop - Pattern Map

**Mapped:** 2026-06-20
**Files analyzed:** 11
**Analogs found:** 11 / 11

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `api/routes/onboarding.py` | route | request-response (SSE) | `api/routes/chat.py` | exact |
| `api/routes/rides.py` | route | file-I/O + background | `api/routes/chat.py` | role-match |
| `api/routes/adaptations.py` | route | CRUD | `api/routes/chat.py` | role-match |
| `sports_science/profile.py` | service | CRUD (async DB write) | `sports_science/capability_gap.py` | exact |
| `sports_science/plan.py` | service | transform (pure computation) | `sports_science/load.py` | exact |
| `agent/tools.py` | config (MODIFY) | — | `agent/tools.py` | self |
| `supabase/migrations/0002_phase3_schema.sql` | migration | — | `supabase/migrations/0001_initial_schema.sql` | exact |
| `tests/api/test_onboarding.py` | test | request-response | `tests/agent/test_sse.py` | exact |
| `tests/api/test_rides.py` | test | file-I/O | `tests/agent/test_sse.py` | role-match |
| `tests/api/test_adaptations.py` | test | CRUD | `tests/agent/test_sse.py` | role-match |
| `tests/agent/test_tools_phase3.py` | test | unit | `tests/agent/test_sse.py` | role-match |

---

## Pattern Assignments

### `api/routes/onboarding.py` (route, SSE)

**Analog:** `api/routes/chat.py`

**Imports pattern** (lines 1-10):
```python
import json
import os

import anthropic
from fastapi import APIRouter, Body
from fastapi.responses import StreamingResponse

from agent.loop import run_turn
from agent.trust import scan_buffer
```

**Core SSE pattern** — reuse `sse_generator` from `chat.py` verbatim (lines 58-80). The onboarding router calls the same generator with a different initial messages list and a different system prompt. Do NOT duplicate `sse_generator`; import it or extract it to `api/routes/_sse.py`.

**Router mount pattern** (lines 52, 83-84):
```python
router = APIRouter()

@router.post("/start")
async def onboarding_start(user_id: str = Body(...)):
    model = os.environ.get("ANTHROPIC_MODEL", _DEFAULT_MODEL)
    messages = [{"role": "user", "content": "I'd like to start my training interview."}]
    return StreamingResponse(
        sse_generator(messages, model, system_prompt=ONBOARDING_SYSTEM_PROMPT),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
```

**Dynamic system prompt pattern** — `run_turn` currently takes `system=SYSTEM_PROMPT` as a hardcoded string inside `sse_generator`. Phase 3 must accept an optional `system_prompt` param in `sse_generator`. The `agent/loop.py` already passes `system=SYSTEM_PROMPT` (line 92) — change `run_turn` to accept `system: str` as a parameter so the onboarding and coaching routers can inject the dynamic prompt per D-22.

**Conversation creation pattern:** Insert a row into `conversations` with `context_type='onboarding'` using the Supabase singleton pattern from `capability_gap.py` lines 28-50 (see below). Return the `conversation_id` in the initial response or embed it in the SSE stream as an `event: meta` frame before the first `event: token`.

**Conversation history load/save:** Replace the in-memory placeholder in `chat.py` lines 98-106 with:
```python
# Load last 20 messages from DB
messages = await load_conversation(conversation_id, limit=20)
# After run_turn completes, persist new messages:
await save_messages(conversation_id, user_id, new_messages)
```

---

### `api/routes/rides.py` (route, file-I/O + background)

**Analog:** `api/routes/chat.py` (structure) + RESEARCH.md pattern

**Imports pattern:**
```python
import asyncio

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
```

**File upload + background task pattern** (from RESEARCH.md D-11, D-12, D-15):
```python
router = APIRouter()

@router.post("/upload")
async def upload_fit(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    background_tasks: BackgroundTasks,
):
    file_bytes = await file.read()

    # CPU-bound parse in thread pool (D-12)
    parsed = await asyncio.to_thread(parse_fit_file, file_bytes)

    if parsed is None or parsed["duration_secs"] < 600:
        raise HTTPException(
            status_code=422,
            detail={"error": "fit_parse_failed", "detail": "File too short or unreadable"},
        )

    ride_id = await persist_ride_stub(user_id, parsed, storage_path)
    background_tasks.add_task(process_ride_background, ride_id, user_id, parsed)
    return {"ride_id": ride_id, "status": "processing"}
```

**Error response pattern** (D-14) — 422 with structured body matching `chat.py` error framing:
```python
raise HTTPException(status_code=422, detail={"error": "fit_parse_failed", "detail": str(exc)})
```

**Supabase write pattern** — copy `_get_async_supabase()` singleton from `capability_gap.py` lines 28-50 for all DB writes inside `process_ride_background`. Use `SERVICE_ROLE_KEY` (never anon key) for backend inserts.

---

### `api/routes/adaptations.py` (route, CRUD)

**Analog:** `api/routes/chat.py` (structure)

**Imports pattern:**
```python
from fastapi import APIRouter, Body, Query
from fastapi.responses import JSONResponse
```

**GET endpoint pattern:**
```python
router = APIRouter()

@router.get("/")
async def list_adaptations(user_id: str = Query(...)):
    supabase = await _get_async_supabase()
    rows = await supabase.table("adaptations").select("*").eq("user_id", user_id)\
        .order("created_at", desc=True).execute()
    return rows.data

@router.post("/check")
async def check_adaptations(user_id: str = Body(...)):
    signals = await detect_signals(user_id)
    return {"signals": signals, "count": len(signals)}
```

**Router registration pattern** — add to `api/main.py` following the `chat_router` pattern (line 33):
```python
from api.routes.onboarding import router as onboarding_router
from api.routes.rides import router as rides_router
from api.routes.adaptations import router as adaptations_router

app.include_router(onboarding_router, prefix="/onboarding", tags=["onboarding"])
app.include_router(rides_router, prefix="/rides", tags=["rides"])
app.include_router(adaptations_router, prefix="/adaptations", tags=["adaptations"])
```

---

### `sports_science/profile.py` (service, async DB write)

**Analog:** `sports_science/capability_gap.py` — exact match (same async Supabase singleton + ToolResult return shape)

**Imports pattern** (lines 1-19 of `capability_gap.py`):
```python
import os
from typing import Optional
from supabase import acreate_client, AsyncClient
from .types import ToolResult

_supabase_client: Optional[AsyncClient] = None

async def _get_async_supabase() -> AsyncClient:
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise EnvironmentError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    _supabase_client = await acreate_client(url, key)
    return _supabase_client
```

**Core upsert pattern** (modeled after `capability_gap.py` lines 74-82):
```python
async def save_profile(
    user_id: str,
    fitness_goals: str,
    weekly_hours: float,
    preferred_days: list[str],
    back_status: str,
    equipment: dict,
    rpe_baseline: str,
    lthr_estimate: float | None,
) -> ToolResult:
    supabase = await _get_async_supabase()
    constraints = (
        {"back_issues": True, "load_ramp_flag_threshold_pct": 10}
        if back_status == "moderate"
        else {"back_issues": back_status == "mild"}
    )
    result = await supabase.table("profiles").upsert({
        "user_id": user_id,
        "fitness_goals": fitness_goals,
        "weekly_hours": weekly_hours,
        "preferred_days": preferred_days,
        "back_status": back_status,
        "equipment": equipment,
        "rpe_baseline": rpe_baseline,
        "lthr_estimate": lthr_estimate,
        "constraints": constraints,
    }, on_conflict="user_id").execute()

    return ToolResult(
        value={"profile_id": result.data[0]["id"], "saved": True},
        unit="",
        methodology="profile_persistence",
        inputs={"user_id": user_id, "back_status": back_status, "weekly_hours": weekly_hours},
    )
```

**ToolResult shape** must exactly match the `ToolResult(value, unit, methodology, inputs)` constructor from `sports_science/types.py` (line 6-18). `model_config = {"frozen": True}` means the object is immutable after construction.

---

### `sports_science/plan.py` (service, pure computation)

**Analog:** `sports_science/load.py` — exact match (sync function, no DB, returns ToolResult)

**Imports pattern** (`load.py` lines 1-2):
```python
from .types import ToolResult
```

**Sync function + ToolResult pattern** (`load.py` lines 8-45):
```python
def generate_plan(
    user_id: str,
    weekly_hours: float,
    back_status: str,
    current_ctl: float,
    load_targets: dict,
    hr_zones: list[dict],
    ftp_confidence: str,
    ftp_watts: float | None,
) -> ToolResult:
    # Pure computation — no DB calls, no imports of other tools (trust model)
    sessions = _build_sessions(weekly_hours, back_status, hr_zones, ftp_confidence, ftp_watts)
    return ToolResult(
        value={
            "plan_id": None,
            "mesocycle_weeks": 4,
            "sessions": sessions,
            "week4_volume_reduction_pct": 40,
            "constraints_applied": _applied_constraints(back_status),
            "methodology": "4-week base mesocycle; Week 1 conservative; Week 4 -40% recovery",
        },
        unit="",
        methodology="mesocycle_plan_generation",
        inputs={
            "user_id": user_id,
            "weekly_hours": weekly_hours,
            "back_status": back_status,
            "ftp_confidence": ftp_confidence,
        },
    )
```

**Week 1 policy (hardcoded):** zone 2 aerobic only, max 45-min sessions, `rpe_target <= 3`, `power_targets = None`. Week 4: multiply all `duration_minutes` by 0.6. Session count from `weekly_hours`: 1h -> 2, 2-3h -> 3, 4h+ -> 4.

**Back-status constraints:** When `back_status == "moderate"`, cap weeks 1-2 sessions at 30 minutes, no `type == "strength"` until week 3, `rpe_target <= 6` in week 1.

**`dispatch_tool` routing:** `generate_plan` is sync (no `async def`), so `dispatch_tool` will run it via `asyncio.to_thread` (line 327 of `tools.py`). Do NOT add `async`.

---

### `agent/tools.py` (MODIFY — add 2 tools)

**Analog:** self — add entries following the exact existing pattern

**Import additions** (after line 35):
```python
from sports_science.profile import save_profile
from sports_science.plan import generate_plan
```

**TOOL_REGISTRY additions** (after line 50, before closing brace):
```python
    "save_profile": save_profile,
    "generate_plan": generate_plan,
```

**TOOL_SCHEMAS additions** — each schema dict must follow the exact shape of existing entries (lines 57-255). Key fields: `name`, `description`, `input_schema.type = "object"`, `input_schema.properties`, `input_schema.required`. Example for `save_profile`:
```python
{
    "name": "save_profile",
    "description": (
        "Persists the user's onboarding interview data to the profiles table. "
        "Call this ONLY after the user has explicitly approved the summary (D-03 gate). "
        "Never call before receiving user confirmation."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "user_id": {"type": "string", "description": "User UUID."},
            "fitness_goals": {"type": "string"},
            "weekly_hours": {"type": "number"},
            "preferred_days": {"type": "array", "items": {"type": "string"}},
            "back_status": {"type": "string", "enum": ["none", "mild", "moderate"]},
            "equipment": {"type": "object"},
            "rpe_baseline": {"type": "string"},
            "lthr_estimate": {"type": "number"},
        },
        "required": ["user_id", "fitness_goals", "weekly_hours", "preferred_days",
                     "back_status", "equipment", "rpe_baseline"],
    },
},
```

**TRUST-02 invariant** (lines 263-269): The import-time assertion `_schema_names != _registry_names` will raise `RuntimeError` if the sets differ. Both additions MUST be in the same edit. After the change, `len(TOOL_REGISTRY) == 10` and `len(TOOL_SCHEMAS) == 10`.

**`save_profile` is async** — `dispatch_tool` already handles async functions via `asyncio.iscoroutinefunction(fn)` branch (line 322). No changes needed to `dispatch_tool`.

---

### `supabase/migrations/0002_phase3_schema.sql` (migration)

**Analog:** `supabase/migrations/0001_initial_schema.sql` — exact structure match

**File header pattern** (lines 1-5 of `0001_initial_schema.sql`):
```sql
-- PacerAI: Phase 3 schema additions
-- Migration: 0002_phase3_schema
-- Applied via: supabase db push
-- RLS strategy: user-owns-row (user_id = auth.uid()) on all tables
-- New tables use SERVICE_ROLE_KEY for backend inserts (same as capability_gaps)
```

**RLS block pattern** for new tables (lines 291-308 of RESEARCH.md):
```sql
CREATE TABLE public.plans (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid NOT NULL REFERENCES public.users ON DELETE CASCADE,
    ...
    created_at      timestamptz DEFAULT now() NOT NULL
);

ALTER TABLE public.plans ENABLE ROW LEVEL SECURITY;
CREATE POLICY "plans: own row" ON public.plans USING (user_id = auth.uid());
```

**ALTER TABLE pattern** — add columns to existing tables before creating new tables (to avoid FK ordering issues). Order: `profiles` additions, `sessions` additions, `rides` additions, `conversations` additions, then `CREATE TABLE plans`, then `CREATE TABLE adaptations`.

**Upsert constraint** — `profiles` needs `ADD CONSTRAINT profiles_user_id_unique UNIQUE (user_id)` to support the `ON CONFLICT (user_id) DO UPDATE` upsert in `save_profile`.

**`plans` FK before `sessions.plan_id`** — `plans` table must be created before the `ALTER TABLE sessions ADD COLUMN plan_id uuid REFERENCES public.plans` line.

---

### `tests/api/test_onboarding.py` (test, SSE)

**Analog:** `tests/agent/test_sse.py` — exact pattern

**Imports pattern** (`test_sse.py` lines 1-8):
```python
import json
import pytest
import httpx
from httpx import ASGITransport
```

**App import + monkeypatch pattern** (`test_sse.py` lines 110-123):
```python
async def test_onboarding_returns_sse(monkeypatch):
    from api.main import app
    import api.routes.onboarding as onboarding_module

    monkeypatch.setattr(onboarding_module, "run_turn", _mock_interview_run_turn)

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post("/onboarding/start", json={"user_id": "test-user-001"})

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
```

**Mock run_turn pattern** (`test_sse.py` lines 77-99):
```python
async def _mock_interview_run_turn(messages, client, model, trust_scanner, audit_log):
    yield {"event": "token", "data": {"text": "What are your fitness goals?"}}
    yield {"event": "tool_start", "data": {"name": "save_profile", "tool_use_id": "t1"}}
    yield {"event": "tool_result", "data": {"tool_use_id": "t1", "name": "save_profile",
                                             "value": '{"saved": true}'}}
    yield {"event": "done", "data": {}}
```

**`parse_sse_frames` helper** — copy verbatim from `test_sse.py` lines 33-69. Do not reimplement.

**No `@pytest.mark.asyncio` needed** — `pytest.ini` has `asyncio_mode = auto` (confirmed in RESEARCH.md).

---

### `tests/api/test_rides.py` (test, file-I/O)

**Analog:** `tests/agent/test_sse.py` (structure) + RESEARCH.md FIT-06 pattern

**Fixture path pattern** (RESEARCH.md lines 733-734):
```python
import pathlib
FIXTURE_PATH = pathlib.Path(__file__).parents[1] / "fixtures" / "sample_zwift.fit"
```

**File upload test pattern** (RESEARCH.md lines 743-758):
```python
async def test_fit_upload_integration():
    assert FIXTURE_PATH.exists(), f"Test fixture missing: {FIXTURE_PATH}"

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        with open(FIXTURE_PATH, "rb") as f:
            response = await client.post(
                "/rides/upload",
                files={"file": ("sample_zwift.fit", f, "application/octet-stream")},
                data={"user_id": TEST_USER_ID},
            )

    assert response.status_code == 200
    assert "ride_id" in response.json()
```

**Supabase mock pattern** — use `monkeypatch` to replace `_get_async_supabase` with a mock that captures inserts, same pattern as the `monkeypatch.setattr(onboarding_module, "run_turn", ...)` idiom from `test_sse.py`.

**422 error test pattern:**
```python
async def test_corrupt_fit_returns_422():
    async with httpx.AsyncClient(...) as client:
        response = await client.post("/rides/upload",
            files={"file": ("bad.fit", b"not a fit file", "application/octet-stream")},
            data={"user_id": TEST_USER_ID})
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "fit_parse_failed"
```

---

### `tests/api/test_adaptations.py` (test, CRUD)

**Analog:** `tests/agent/test_sse.py` (structure)

**Query param pattern** (matching `test_sse.py` `test_sse_requires_conversation_id` lines 291-308):
```python
async def test_get_adaptations_requires_user_id():
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/adaptations/")
    assert response.status_code == 422  # missing required query param

async def test_get_adaptations_returns_list(monkeypatch):
    import api.routes.adaptations as adapt_module
    monkeypatch.setattr(adapt_module, "_get_async_supabase", mock_supabase_factory([]))
    async with httpx.AsyncClient(...) as client:
        response = await client.get("/adaptations/", params={"user_id": TEST_USER_ID})
    assert response.status_code == 200
    assert isinstance(response.json(), list)
```

**Signal detection unit tests** — test `detect_signals` directly (not via HTTP) by mocking the DB calls. Pattern: import the function, monkeypatch the Supabase calls, assert return shape.

---

### `tests/agent/test_tools_phase3.py` (test, unit)

**Analog:** existing tool tests pattern (inferred from `tests/agent/conftest.py` structure)

**TRUST-02 test** (critical — must be first test):
```python
def test_trust02_still_passes_after_new_tools():
    """TRUST-02: TOOL_REGISTRY and TOOL_SCHEMAS must have exactly the same names."""
    from agent.tools import TOOL_REGISTRY, TOOL_SCHEMAS
    schema_names = {s["name"] for s in TOOL_SCHEMAS}
    registry_names = set(TOOL_REGISTRY)
    assert schema_names == registry_names
    assert len(TOOL_REGISTRY) == 10  # 8 original + save_profile + generate_plan
```

**`generate_plan` unit tests** — call the sync function directly, no mocking needed:
```python
def test_generate_plan_cold_start_no_power_targets():
    from sports_science.plan import generate_plan
    result = generate_plan(
        user_id="u1", weekly_hours=3.0, back_status="none",
        current_ctl=0.0, load_targets={"recommended_ctl_target": 8.0},
        hr_zones=[{"zone": 2, "lower_bpm": 120, "upper_bpm": 145}],
        ftp_confidence="insufficient_data", ftp_watts=None,
    )
    assert result.value["mesocycle_weeks"] == 4
    for session in result.value["sessions"]:
        assert session["power_targets"] is None
```

**`save_profile` unit test** — mock `_get_async_supabase`:
```python
async def test_save_profile_upserts(monkeypatch):
    import sports_science.profile as profile_module
    mock_client = AsyncMock()
    mock_client.table.return_value.upsert.return_value.execute = AsyncMock(
        return_value=MagicMock(data=[{"id": "profile-uuid-001"}])
    )
    monkeypatch.setattr(profile_module, "_supabase_client", mock_client)
    from sports_science.profile import save_profile
    result = await save_profile(
        user_id="u1", fitness_goals="weight loss", weekly_hours=3.0,
        preferred_days=["Tuesday", "Thursday", "Saturday"], back_status="none",
        equipment={"trainer": "Wahoo Kickr Core", "platform": "Zwift"},
        rpe_baseline="beginner", lthr_estimate=None,
    )
    assert result.value["saved"] is True
```

---

## Shared Patterns

### Supabase Async Singleton
**Source:** `sports_science/capability_gap.py` lines 21-50
**Apply to:** `sports_science/profile.py`, `api/routes/rides.py`, `api/routes/adaptations.py`
```python
_supabase_client: Optional[AsyncClient] = None

async def _get_async_supabase() -> AsyncClient:
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise EnvironmentError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    _supabase_client = await acreate_client(url, key)
    return _supabase_client
```

### ToolResult Return Shape
**Source:** `sports_science/types.py` lines 6-18, `sports_science/load.py` lines 32-45
**Apply to:** `sports_science/profile.py`, `sports_science/plan.py`
```python
return ToolResult(
    value={...},      # the actual data; shape varies per tool
    unit="",          # empty string for non-numeric results
    methodology="...",  # human-readable description of the method
    inputs={...},     # key-value of inputs (never secrets)
)
```

### SSE StreamingResponse Headers
**Source:** `api/routes/chat.py` lines 108-114
**Apply to:** `api/routes/onboarding.py`
```python
return StreamingResponse(
    sse_generator(messages, model),
    media_type="text/event-stream",
    headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    },
)
```

### Error Handling in Routes
**Source:** `api/routes/chat.py` lines 78-80 (sse_generator exception catch)
**Apply to:** `api/routes/rides.py`, `api/routes/adaptations.py`
```python
except Exception as exc:
    error_data = json.dumps({"code": "server_error", "message": str(exc)})
    yield f"event: error\ndata: {error_data}\n\n"
```
For non-SSE routes: `raise HTTPException(status_code=422, detail={"error": "...", "detail": str(exc)})`.

### DB Insert with SERVICE_ROLE_KEY
**Source:** `sports_science/capability_gap.py` lines 73-82
**Apply to:** All backend DB writes in `rides.py`, `adaptations.py`, `profile.py`
```python
# Best-effort pattern for non-critical writes
try:
    supabase = await _get_async_supabase()
    await supabase.table("table_name").insert({...}).execute()
except Exception:
    pass  # best-effort; log but do not block response
```
For critical writes (plan creation, ride persistence): let exceptions propagate; wrap caller in try/except with 500 response.

### Test Monkeypatch + ASGITransport
**Source:** `tests/agent/test_sse.py` lines 110-123
**Apply to:** All `tests/api/` test files
```python
from api.main import app
import api.routes.<module> as route_module

monkeypatch.setattr(route_module, "run_turn", mock_fn)

async with httpx.AsyncClient(
    transport=ASGITransport(app=app),
    base_url="http://test",
) as client:
    response = await client.post("/route", ...)
```

### `parse_sse_frames` Helper
**Source:** `tests/agent/test_sse.py` lines 33-69
**Apply to:** `tests/api/test_onboarding.py` — copy verbatim, do not reimplement.

---

## No Analog Found

All files have close analogs. No files need to rely solely on RESEARCH.md patterns.

---

## Metadata

**Analog search scope:** `api/`, `agent/`, `sports_science/`, `tests/`, `supabase/migrations/`
**Files read:** 12 source files
**Pattern extraction date:** 2026-06-20
