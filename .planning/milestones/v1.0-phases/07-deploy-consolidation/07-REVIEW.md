---
phase: 07-deploy-consolidation
reviewed: 2026-07-03T00:00:00Z
depth: standard
files_reviewed: 12
files_reviewed_list:
  - .claude/CLAUDE.md
  - api/index.py
  - backend/calendar_sync.py
  - backend/routes/adaptations.py
  - backend/routes/onboarding.py
  - supabase/migrations/0007_repair_oauth_states.sql
  - supabase/migrations/0008_fk_indexes.sql
  - tests/api/test_adaptations.py
  - tests/api/test_onboarding.py
  - vercel.json
  - README.md
  - requirements.txt
findings:
  critical: 2
  warning: 8
  info: 2
  total: 12
status: issues_found
---

# Phase 7: Code Review Report

**Reviewed:** 2026-07-03T00:00:00Z
**Depth:** standard
**Files Reviewed:** 12
**Status:** issues_found

## Summary

Reviewed the Vercel-only deploy consolidation: three BackgroundTasks-to-inline-await calendar-sync
conversions, the two new migrations (`0007_repair_oauth_states.sql`, `0008_fk_indexes.sql`),
`vercel.json`'s new `services` model, and `api/index.py`'s mount. The migrations are sound
(idempotent `IF NOT EXISTS`, correctly ordered, no RLS/policy regressions). The routing/mount setup
in `api/index.py` + `vercel.json` is internally consistent with the stated live-tested fix.

Two BLOCKER-level defects were found in the inline-await conversion itself:

1. The calendar-sync helpers are now awaited sequentially, per session, with no concurrency bound
   and no aggregate time budget — for any realistically-sized training plan this risks exceeding
   the Vercel function's `maxDuration` and failing the HTTP response entirely. This is a direct,
   provable regression versus the prior fire-and-forget `BackgroundTasks` design.
2. `apply_micro_adjustment` and `apply_macro_replan` in `backend/routes/adaptations.py` never
   `SELECT` the `calendar_event_id` column, so the calendar-sync code added in this phase for
   `POST /adaptations/check` and `POST /adaptations/sessions/{id}/missed` is unreachable in
   production — `update_calendar_event` is called with `event_id=None` and always short-circuits.
   The tests for this behavior mock `apply_micro_adjustment`/`apply_macro_replan` directly, which
   is why this is not caught by the test suite.

Additional warnings cover a missing `user_id` dual-filter on two session UPDATE calls (inconsistent
with the dual-filter pattern used everywhere else in the same file), a dead/no-op date-parsing
branch, nondeterministic ordering of the adaptation's logged `trigger` field, a stale comment in
`api/index.py` that contradicts the actual `vercel.json` value it describes, and README.md drift
that was only partially fixed in this phase's diff.

## Critical Issues

### CR-01: Unbounded sequential inline-awaited Google Calendar calls risk function timeout

**File:** `backend/calendar_sync.py:255-288`, invoked from `backend/routes/onboarding.py:181-205` and (per-session, in a smaller but still unbounded loop) from `backend/routes/adaptations.py:759-771` and `backend/routes/adaptations.py:905-916`

**Issue:** `push_all_sessions_to_calendar` loops over *every* `status='planned'` session for the user
and calls `push_session_to_calendar` **sequentially**, each bounded by `CALENDAR_API_TIMEOUT_SECS =
8.0` (`backend/calendar_sync.py:44`). `POST /onboarding/plan-calendar-sync` (`backend/routes/onboarding.py:204`)
inline-awaits this helper before responding — there is no more `BackgroundTasks` to decouple this
work from the HTTP response, per this phase's own stated Vercel serverless constraint.

For a freshly onboarded user with even a modest multi-week periodised plan (the codebase's stated
core value — "immediately receive a...periodised cycling plan"), this is tens of sessions. Worst
case latency is `N * 8s` (e.g. 36 sessions -> up to 288s); even in the common case of healthy Google
API calls at 1-2s each, N=30-60 sessions is 30-120s sequential — very likely to exceed Vercel's
function `maxDuration` (10s Hobby / 60s Pro by default; `vercel.json` sets none explicitly for the
backend service). When the function times out mid-loop, the client gets a failed/timed-out request
even though some session updates already landed in Google Calendar and/or the DB, leaving
inconsistent partial state with no compensating retry.

The same unbounded-per-signal-set pattern exists (at smaller, but still uncapped, scale) in the
calendar-sync loops added to `check_adaptations` (`backend/routes/adaptations.py:759-771`) and
`mark_session_missed` (`backend/routes/adaptations.py:905-916`), which iterate `after_sessions`
with no concurrency and no aggregate timeout. (These two call sites are currently masked from firing
by CR-02 below, but will manifest as soon as CR-02 is fixed.)

This is exactly the risk this phase's own `calendar_sync.py` docstring/timeout comments call out
("a hanging or stalled call...could otherwise stall the HTTP response up to the function's
maxDuration") — the per-call timeout was bounded, but the *aggregate* n-call timeout across a loop
was not.

**Fix:** Bound total latency, not just per-call latency. Run the per-session pushes concurrently
with a semaphore instead of sequentially, and/or wrap the whole batch in an outer `asyncio.wait_for`
so the function fails fast instead of stacking N * 8s:

```python
async def push_all_sessions_to_calendar(user_id: str) -> None:
    try:
        supabase = await _get_async_supabase()
        result = await (
            supabase.table("sessions")
            .select("id, scheduled_date, objective, structure, targets, duration_minutes")
            .eq("user_id", user_id)
            .eq("status", "planned")
            .execute()
        )
        sessions = result.data or []

        sem = asyncio.Semaphore(5)  # bound concurrency against Google API rate limits

        async def _push_one(session):
            async with sem:
                event_id = await push_session_to_calendar(user_id, session)
                if event_id:
                    await (
                        supabase.table("sessions")
                        .update({"calendar_event_id": event_id})
                        .eq("id", session["id"])
                        .execute()
                    )

        await asyncio.gather(*(_push_one(s) for s in sessions), return_exceptions=True)
    except Exception:
        logger.warning("push_all_sessions_to_calendar failed for user %s", user_id, exc_info=True)
```

Also set an explicit `functions.maxDuration` for the backend service in `vercel.json` so the budget
is a known, deliberate value rather than the platform default.

---

### CR-02: `calendar_event_id` never selected in adaptations.py — `update_calendar_event` is dead code

**File:** `backend/routes/adaptations.py:399-407` (`apply_micro_adjustment`), `backend/routes/adaptations.py:519-527` (`apply_macro_replan`)

**Issue:** Both `apply_micro_adjustment` and `apply_macro_replan` fetch sessions with:

```python
.select("id, scheduled_date, tss_target, duration_minutes, status")
```

`calendar_event_id` is not in the column list. `after_sessions` is built via `{**session, ...}` from
these rows, so it never carries `calendar_event_id` either. Downstream, `check_adaptations`
(`backend/routes/adaptations.py:761-771`) and `mark_session_missed`
(`backend/routes/adaptations.py:907-916`) do:

```python
event_id = session.get("calendar_event_id") or before_by_id.get(session["id"], {}).get("calendar_event_id")
if event_id:
    await update_calendar_event(user_id, event_id, session)
```

`event_id` is always `None` for every real (non-mocked) call, so `update_calendar_event` never
actually fires when a micro or macro adaptation runs. This silently breaks CAL-02 ("calendar sync
after sessions change") for every adaptation the app makes after the initial onboarding push — a
user's Google Calendar entries go stale the first time their plan adapts, with no error surfaced
anywhere (by design, per CAL-04, but here it's a data-completeness bug rather than a genuine
downstream failure being swallowed).

This is not caught by `tests/api/test_adaptations.py::test_check_adaptations_inline_awaits_calendar_update`
or `test_mark_missed_inline_awaits_calendar_update` because both tests monkeypatch
`apply_micro_adjustment`/`apply_macro_replan` wholesale and hand back a synthetic dict that already
contains `calendar_event_id` — the real `SELECT` statement is never exercised by either test.

**Fix:** Add `calendar_event_id` to both select statements:

```python
.select("id, scheduled_date, tss_target, duration_minutes, status, calendar_event_id")
```

in both `apply_micro_adjustment` (line 401) and `apply_macro_replan` (line 521). Then add a
regression test that calls the real `apply_micro_adjustment`/`apply_macro_replan` (not mocked) with
a Supabase mock returning a row that includes `calendar_event_id`, and asserts the returned
`after_sessions` entries retain it — this is the gap that let CR-01/CR-02 both ship unnoticed.

## Warnings

### WR-01: `confirm_macro_replan` never syncs the calendar

**File:** `backend/routes/adaptations.py:780-842`

**Issue:** `POST /adaptations/{adaptation_id}/confirm` applies the stored `after_snapshot` sessions
to the DB but, unlike `check_adaptations` and `mark_session_missed`, never calls
`update_calendar_event`. Once CR-02 is fixed, this endpoint will remain the one path where an
applied macro replan's calendar entries are never updated — inconsistent with the CAL-02 intent
applied elsewhere in the same file.

**Fix:** After the per-session `UPDATE` loop, mirror the calendar-sync block used in
`check_adaptations`, using `proposed_sessions` (once it carries `calendar_event_id`, see CR-02) to
locate event ids to update.

### WR-02: Missing `user_id` dual-filter on two session UPDATE calls

**File:** `backend/routes/adaptations.py:440`, `backend/routes/adaptations.py:649`

**Issue:** Every other session-mutating write in this file is explicitly dual-filtered by `id` and
`user_id` "for defence-in-depth" (see `backend/routes/adaptations.py:462-468`, `655-660`, `822-832`).
These two calls are not:

```python
await supabase.table("sessions").update(update_payload).eq("id", session["id"]).execute()
```

(`apply_micro_adjustment`, line 440, and the apply-branch of `apply_macro_replan`, line 649). The
`id` values are currently only ever sourced from a prior `user_id`-scoped `SELECT`, so this is not
exploitable via attacker-controlled input today, but it silently breaks the file's own stated
security pattern and would become exploitable the moment either function is refactored to accept an
externally-supplied session id.

**Fix:**

```python
await (
    supabase.table("sessions")
    .update(update_payload)
    .eq("id", session["id"])
    .eq("user_id", user_id)
    .execute()
)
```

at both sites.

### WR-03: `_parse_date`'s strptime loop is dead/no-op logic, masked only by the fallback

**File:** `backend/routes/adaptations.py:58-78`

**Issue:**

```python
for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
    try:
        return datetime.strptime(val[:len(fmt)], fmt).date()
    except ValueError:
        continue
```

`len(fmt)` is the length of the *format string*, not the length of a value that format would
produce. `len("%Y-%m-%d") == 8`, so for a real `"2026-07-03"` value this slices to `"2026-07-"`
(missing the day digits) and `strptime` always raises — verified directly:

```
>>> "2026-07-03"[:len("%Y-%m-%d")]
'2026-07-'
```

All three format attempts fail for every realistic input; the function only returns a correct value
because of the final fallback (`datetime.fromisoformat(val.replace("Z", "+00:00")).date()`). The
loop currently does nothing except add three guaranteed `ValueError`s to every call. If the fallback
is ever changed or removed, date parsing silently breaks (returns `None`, causing the calling code
to skip the session with no error).

**Fix:** Drop the broken strptime loop and rely on the fallback directly (or fix the slice to use
the correct fixed lengths per format: 10, 19, 20):

```python
def _parse_date(val) -> Optional[date]:
    if val is None:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, str):
        try:
            return datetime.fromisoformat(val.replace("Z", "+00:00")).date()
        except ValueError:
            return None
    return None
```

### WR-04: Nondeterministic `primary_trigger` / `signal_types` ordering

**File:** `backend/routes/adaptations.py:598`, `backend/routes/adaptations.py:663`

**Issue:**

```python
signal_types = list({s.get("type") for s in signals})
primary_trigger = signal_types[0] if signal_types else "underperformance"
```

Iterating a Python `set` of strings has hash-randomization-dependent order (`PYTHONHASHSEED` is
randomized per process by default). When a macro replan is triggered by a mix of `"missed"` and
`"underperformance"` signals, `primary_trigger` — which is persisted to `adaptations.trigger`
(TRANSP-02 audit field) and used to build the user-facing `explanation_text` — is not deterministic
across process restarts/cold starts, even for identical input. This undermines the "readable
adaptation log" guarantee (TRANSP-03).

**Fix:** Preserve first-seen order instead of using a `set`:

```python
signal_types = list(dict.fromkeys(s.get("type") for s in signals))
```

### WR-05: Stale comment in `api/index.py` contradicts the actual `vercel.json` entrypoint

**File:** `api/index.py:9-11`

**Issue:** The comment reads:

```python
# Vercel `services` entry point for the backend service (vercel.json
# services.backend.entrypoint = "index:app"). Per Vercel's services routing
```

but `vercel.json:10` actually sets `"entrypoint": "api.index:app"`. Given the task context that this
exact backend-root-scoping/entrypoint value was the subject of a live-tested bug fix, a comment that
still cites the old/wrong value is exactly the kind of drift likely to mislead the next person
debugging a deploy routing issue.

**Fix:** Update the comment to match the actual value: `services.backend.entrypoint = "api.index:app"`.

### WR-06: README.md "Tech Stack" table and local dev instructions were not updated to match the "Deployment" section changed in this same diff

**File:** `README.md:25-36`, `README.md:114`

**Issue:** This phase's diff correctly rewrote the "Deployment" section (removed Railway/Docker/
Gunicorn, added the Vercel Python Runtime description) and the backend env-var table, but left the
"Tech Stack" summary table near the top of the same file unchanged:

```
### Backend (Railway via Docker)
...
| Framework | FastAPI + Uvicorn/Gunicorn |
...
| ORM / migrations | SQLAlchemy 2.x + Alembic |
```

`requirements.txt` contains no `sqlalchemy`, `alembic`, or `asyncpg` — the project uses the
`supabase` client and raw SQL files under `supabase/migrations/`. The document now directly
contradicts itself between its own top table and its own Deployment section.

Separately, the local dev command at `README.md:114`:

```
uvicorn api.main:app --reload --port 8000
```

references a module that does not exist (`ls api/` shows only `index.py`; the FastAPI app lives at
`backend/main.py`). A new developer following this instruction verbatim gets
`ModuleNotFoundError: No module named 'api.main'`.

**Fix:** Update the "Tech Stack" table to match the Deployment section (Vercel Python Runtime, no
Docker/Gunicorn/Railway, `supabase` client + raw SQL migrations, no SQLAlchemy/Alembic), and correct
the uvicorn command to `uvicorn backend.main:app --reload --port 8000`.

### WR-07: README.md's API endpoint list is missing the `/api` prefix required by the new routing scheme

**File:** `README.md:70-85`

**Issue:** `vercel.json` (`services.backend`, this phase's change) only rewrites `/api/(.*)` to the
backend service; everything else falls through to the frontend static service. `api/index.py`
correspondingly mounts the FastAPI app at `/api` (`app.mount("/api", _backend_app)`), meaning every
production route documented in the README (`GET /chat/stream`, `POST /rides/upload`,
`GET /adaptations/`, `GET /health`, etc.) actually lives at `/api/chat/stream`, `/api/rides/upload`,
etc. The README's endpoint list, as written, would 404 (fall through to the SPA) if used against the
deployed app.

**Fix:** Either prefix every route in the README's endpoint list with `/api`, or add a note clarifying
that the listed paths are the FastAPI-internal paths and that Vercel routes `/api/*` to them.

### WR-08: `onboarding_start` accepts a client-supplied `conversation_id` without ownership or format validation

**File:** `backend/routes/onboarding.py:246-264`

**Issue:** `body.conversation_id` is taken directly from the request body and used as-is; unlike
every other route in `backend/routes/adaptations.py` (which calls `validate_uuid(...)` on any
client-supplied id), there is no format check here. `load_conversation` does filter reads by
`.eq("user_id", user_id)`, so a foreign or malformed `conversation_id` correctly returns zero prior
turns — but the code then proceeds to treat `conversation_id` as valid for the *write* path
(`save_messages(conversation_id, user_id, new_turns)` at line 293), inserting new message rows tied
to a `conversation_id` that may belong to a different user (or be syntactically invalid, in which
case the insert silently fails inside the blanket `except Exception: pass` at line 294-295). This
does not leak data cross-user (reads stay `user_id`-scoped), but it does allow orphaned/mismatched
rows to be written and silently drops messages on a malformed id with no error surfaced anywhere.

**Fix:** Validate `conversation_id` format (reuse `backend.utils.validate_uuid`) and verify ownership
via a lightweight existence check (`select id from conversations where id=... and user_id=...`)
before treating it as resumable; fall back to creating a new conversation when the check fails,
matching the "when absent, a new conversation is created" behavior already documented for the
missing-id case.

## Info

### IN-01: No `.vercelignore` alongside the backend service's repo-root scoping

**File:** `vercel.json:8-11`

**Issue:** `services.backend.root` is now `"."` (the fix for the sibling-package exclusion bug), but
there is no `.vercelignore` in the repo. Without one, the backend function's build context is only as
narrow as whatever `.gitignore` already excludes (env files, caches, etc.) — `.planning/`,
`docs/`, test fixtures like `test-ride.fit`, and other repo-root content are not excluded from
whatever gets bundled for the Python function.

**Fix:** Add a `.vercelignore` scoping the backend build to what it actually needs (`backend/`,
`api/`, `requirements.txt`, `supabase/` if needed at runtime), excluding `frontend/`, `.planning/`,
`docs/`, and test fixtures.

### IN-02: Duplicated `signal_types` computation in `apply_macro_replan`

**File:** `backend/routes/adaptations.py:598`, `backend/routes/adaptations.py:663`

**Issue:** The same `signal_types = list({s.get("type") for s in signals})` expression (see WR-04)
appears twice — once in the `needs_confirmation` branch, once in the apply branch — with no shared
helper.

**Fix:** Compute `signal_types` once near the top of `apply_macro_replan` and reuse it in both
branches, alongside the WR-04 fix.

---

_Reviewed: 2026-07-03T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
