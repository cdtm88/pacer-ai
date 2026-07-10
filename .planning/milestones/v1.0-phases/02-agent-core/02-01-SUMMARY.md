---
phase: 02-agent-core
plan: "01"
subsystem: backend-foundation
status: complete
tags: [deps, packaging, async, trust-boundary]
completed: "2026-06-20"
duration: "3 min"

dependency_graph:
  requires: []
  provides:
    - anthropic, fastapi, uvicorn, python-multipart installed in venv
    - agent/, api/, api/routes/, tests/agent/ package markers importable
    - async log_capability_gap via acreate_client (D-06, TRUST-05)
  affects:
    - All Phase 2 plans depend on agent/ and api/ packages existing
    - Plans 02-02, 02-03 import from agent/; Plan 02-04 imports from api/

tech_stack:
  added:
    - anthropic==0.67.0 (Anthropic SDK with native tool use)
    - fastapi==0.115.14 (async HTTP framework for SSE endpoint)
    - uvicorn==0.30.6 (ASGI server)
    - python-multipart==0.0.32 (FastAPI file upload dependency)
  patterns:
    - acreate_client/AsyncClient pattern for Supabase async writes
    - asyncio_mode=auto for pytest-asyncio; no explicit marks needed

key_files:
  created:
    - agent/__init__.py (transport-agnostic agentic loop package marker)
    - api/__init__.py (FastAPI HTTP transport package marker)
    - api/routes/__init__.py (route definitions package marker)
    - tests/agent/__init__.py (agent compliance test package marker)
  modified:
    - requirements.txt (added four Phase 2 deps)
    - sports_science/capability_gap.py (async upgrade: acreate_client)
    - tests/sports_science/test_capability_gap.py (async test conversions)
    - tests/sports_science/test_import_boundary.py (fastapi boundary test added)

decisions:
  - "Raw anthropic SDK (not claude-agent-sdk); proven absent from requirements.txt (AGENT-01)"
  - "Per-request acreate_client in Phase 2 (simpler); lifespan singleton deferred to Phase 3"
  - "MagicMock chain for sync Supabase table/insert calls; AsyncMock only for execute()"

metrics:
  duration: "3 min"
  tasks_completed: 3
  files_modified: 8
---

# Phase 02 Plan 01: Foundation and Async Upgrade Summary

Backend dependencies installed and claude-agent-sdk provably absent; agent/ and api/ packages importable; log_capability_gap upgraded to async coroutine backed by the Supabase AsyncClient with all GAP-02/GAP-03 guarantees and the sports_science trust boundary intact.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add Phase 2 backend dependencies | b0dad66 | requirements.txt |
| 2 | Create agent/ and api/ package skeleton | eb15fa5 | agent/__init__.py, api/__init__.py, api/routes/__init__.py, tests/agent/__init__.py |
| 3 (RED) | TDD: failing async tests for log_capability_gap | 5d235b9 | tests/sports_science/test_capability_gap.py |
| 3 (GREEN) | Upgrade log_capability_gap to async Supabase client | e086a83 | sports_science/capability_gap.py, tests/sports_science/test_capability_gap.py, tests/sports_science/test_import_boundary.py |

## Verification

- `.venv/bin/python -c "import anthropic, fastapi, uvicorn, multipart, agent, api, api.routes, tests.agent"` passes
- `grep -ci 'claude-agent-sdk' requirements.txt` returns 0 (T-02-01 gate cleared)
- `pytest tests/sports_science/ -x -q` passes (68 tests, including both import boundary tests)
- `log_capability_gap` is `async def` backed by `acreate_client`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Mocking chain for async Supabase client**
- **Found during:** Task 3 GREEN (test_supabase_insert_called_with_correct_fields)
- **Issue:** Using `AsyncMock()` for the whole client made `.table()` a coroutine call, breaking the insert chain assertion. Also `test_supabase_insert_called_with_correct_fields` and `test_db_error_returns_fallback_tool_result` needed `SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY` env vars set via monkeypatch, otherwise the EnvironmentError was silently swallowed (best-effort except) and the table was never called.
- **Fix:** Used `MagicMock` for the client/table/insert chain with `AsyncMock` only on `.execute()`; added `monkeypatch.setenv` for the two tests asserting the insert call occurred.
- **Files modified:** `tests/sports_science/test_capability_gap.py`
- **Commit:** e086a83

## Known Stubs

None. All package markers and the async implementation are complete and wired.

## Threat Flags

None. The `sports_science/` directory has zero anthropic and zero fastapi imports (verified by test suite). The `SUPABASE_SERVICE_ROLE_KEY` is read from env only, never returned in ToolResult.

## Self-Check: PASSED
