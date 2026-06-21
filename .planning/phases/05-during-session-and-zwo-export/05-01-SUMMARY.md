---
phase: 05-during-session-and-zwo-export
plan: "01"
subsystem: backend-zwo-export
status: complete
tags: [zwo, xml, export, sports-science, fastapi, security]
dependency_graph:
  requires: []
  provides: [api/sports_science/zwo.py, GET /sessions/{id}/export.zwo]
  affects: [api/routes/sessions.py]
tech_stack:
  added: []
  patterns: [pure-xml-builder, dual-filter-idor, local-import-pattern]
key_files:
  created:
    - api/sports_science/zwo.py
    - tests/sports_science/test_zwo.py
  modified:
    - api/routes/sessions.py
decisions:
  - "ZWO XML generated server-side only (D-06); frontend never builds XML"
  - "Power values come exclusively from POWER_BY_SEGMENT constants (trust model); LLM never supplies watts"
  - "Local import of generate_zwo inside handler keeps module-level coupling minimal"
  - "defusedxml not used: ZWO pipeline is write-only (generate); XXE is a parser vulnerability, not a generator one"
metrics:
  duration: "2min"
  completed: "2026-06-21"
  tasks: 2
  files: 3
---

# Phase 05 Plan 01: ZWO Export Backend Summary

ZWO XML generator and FastAPI download endpoint with full IDOR guard, UUID validation, and pre-FTP FreeRide fallback path.

## What Was Built

### Task 1 - `api/sports_science/zwo.py` + `tests/sports_science/test_zwo.py`

`generate_zwo(session: dict, ftp_watts: int | None) -> bytes` is a pure XML builder with no DB calls and no imports of other sports_science tools. Module constant `POWER_BY_SEGMENT` supplies the only physiological numbers (warmup 0.50, main_set 0.65, cooldown 0.50 FTP fractions).

When `ftp_watts` is provided: emits `SteadyState` blocks with `Power` as a clamped decimal string (0.0-2.0 range), no `Cadence` attribute, `sportType` = `bike`.

When `ftp_watts` is `None`: emits `FreeRide` blocks each with a `textevent` RPE cue containing the segment description.

All four unit tests pass: `test_zwo_basic_structure`, `test_power_fraction_bounds`, `test_pre_ftp_uses_freeride`, `test_sport_type_and_cadence`.

### Task 2 - `GET /sessions/{session_id}/export.zwo` in `api/routes/sessions.py`

Route handler `export_session_zwo` follows the exact auth pattern from the PATCH handler:

1. `validate_uuid(session_id, "session_id")` before any DB call (T-05-02, V5)
2. Dual-filter sessions query `.eq("id", session_id).eq("user_id", user_id)` (T-05-01, IDOR)
3. Profile FTP fetch to determine SteadyState vs FreeRide path
4. Returns `Response(content=xml_bytes, media_type="application/xml")` with `Content-Disposition: attachment; filename="{YYYY-MM-DD}-{type}.zwo"` (D-05)

## Threat Coverage

| Threat | Mitigation | Verified |
|--------|-----------|---------|
| T-05-01 IDOR | Dual-filter .eq(id).eq(user_id) | Code review |
| T-05-02 UUID injection | validate_uuid before DB | Code review |
| T-05-03 XML injection | ET auto-escapes element text | stdlib guarantee |
| T-05-04 Power out-of-range | clamp to 0.0-2.0 in generate_zwo | test_power_fraction_bounds |
| T-05-05 Unauthenticated | Depends(get_current_user) | Module import |

## Verification Results

- `pytest tests/sports_science/test_zwo.py` - 4/4 passed
- `pytest tests/api/test_sessions.py` - 13/13 passed (no regression)
- `python -c "import api.main"` - exits 0
- `python -c "import api.routes.sessions"` - exits 0

## Deviations from Plan

None - plan executed exactly as written.

The security plugin flagged `defusedxml` for XXE protection. This was correctly assessed as not applicable: `defusedxml` protects XML *parsers* from malicious input; this module only *generates* XML output. `xml.etree.ElementTree.tostring()` is not a parser and is not vulnerable to XXE. No deviation applied.

## Known Stubs

None. ZWO generator is fully wired; power values come from `POWER_BY_SEGMENT` constants.

## Threat Flags

None beyond the plan's threat model.

## Self-Check: PASSED

- `/Users/christianmoore/ai/pacer-ai/api/sports_science/zwo.py` - FOUND
- `/Users/christianmoore/ai/pacer-ai/tests/sports_science/test_zwo.py` - FOUND
- `/Users/christianmoore/ai/pacer-ai/api/routes/sessions.py` - FOUND (modified)
- Commit `caa0090` (feat(05-01): ZWO XML generator) - FOUND
- Commit `4c2c195` (feat(05-01): export endpoint) - FOUND
