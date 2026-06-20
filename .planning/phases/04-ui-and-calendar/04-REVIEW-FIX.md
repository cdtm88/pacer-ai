---
phase: "04"
padded_phase: "04"
status: "all_fixed"
fix_scope: "critical_warning"
findings_in_scope: 9
fixed: 9
skipped: 0
iteration: 1
fixed_at: "2026-06-20"
---

# Phase 04: Code Review Fix Report

**Fixed at:** 2026-06-20
**Source review:** `.planning/phases/04-ui-and-calendar/04-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 9 (4 Critical, 5 Warning)
- Fixed: 9
- Skipped: 0

## Fixed Issues

### CR-01 -- getRides() never unwraps the rides response wrapper [FIXED]

**Files modified:** `frontend/src/lib/api.ts`
**Commit:** 5382556
**Applied fix:** Changed `return res.json() as Promise<Ride[]>` to `const data = await res.json() as { rides: Ride[] }; return data.rides ?? []`, matching the pattern already used by `getUpcomingSessions()`.

---

### CR-02 -- oauth_states table is never created in any migration [FIXED]

**Files modified:** `supabase/migrations/0003_phase4_schema.sql`
**Commit:** 8e33c1b
**Applied fix:** Added `CREATE TABLE IF NOT EXISTS public.oauth_states` block with `id`, `user_id` (FK to users ON DELETE CASCADE), `state` (UNIQUE), and `created_at` columns, plus `ENABLE ROW LEVEL SECURITY`. Appended to the existing Phase 4 migration.

---

### CR-03 -- CalendarSettings TypeScript interface declares fields the backend never returns [FIXED]

**Files modified:** `frontend/src/lib/api.ts`, `frontend/tests/e2e/phase4.spec.ts`
**Commit:** e0a751d
**Applied fix:** Removed `calendar_id: string | null` and `sync_enabled: boolean` from the `CalendarSettings` interface, leaving only `connected: boolean`. Updated the E2E mock default in `mockBackendApis` from `{ connected: false, calendar_id: null, sync_enabled: false }` to `{ connected: false }` to match the corrected shape.

---

### CR-04 -- check_shift_limit uses >= 1 boundary, blocking all macro replans [FIXED]

**Files modified:** `api/routes/adaptations.py`
**Commit:** 43f6f98
**Applied fix:** Changed `if delta_days >= 1:` to `if delta_days > 1:` in `check_shift_limit`, matching the docstring specification of "more than 1 day" and unblocking the 1-day-shift case that `apply_macro_replan` always produces.

---

### WR-01 -- SettingsScreen uses React.useState and React.useEffect before React is imported [FIXED]

**Files modified:** `frontend/src/screens/SettingsScreen.tsx`
**Commit:** 8df3452
**Applied fix:** Moved `import React from 'react'` from the bottom of the file (line 121) to line 1, and removed the trailing comment that accompanied it. All other imports follow in their existing order.

---

### WR-02 -- make_test_token produces JWTs without an exp claim [FIXED]

**Files modified:** `tests/api/conftest.py`
**Commit:** 8baba3e
**Applied fix:** Added `import time` at the top of conftest.py and added `"exp": int(time.time()) + 3600` to the JWT payload in `make_test_token`. Tokens now include a 1-hour expiry matching real Supabase JWT structure.

---

### WR-03 -- E2E adaptations routes registered in LIFO-wrong order [FIXED]

**Files modified:** `frontend/tests/e2e/phase4.spec.ts`
**Commit:** b8e646e
**Applied fix:** Swapped registration order so the general `/adaptations\/` handler is registered first and the specific `/adaptations/sessions/.../missed` handler is registered second. Playwright LIFO means the specific handler now wins for missed URLs. Added a comment clarifying the intent.

---

### WR-04 -- T18 hardcoded absolute URL breaks on any port other than 5174 [FIXED]

**Files modified:** `frontend/tests/e2e/phase4.spec.ts`
**Commit:** 6b95e9e
**Applied fix:** Replaced `await expect(page).toHaveURL('http://localhost:5174/')` with `await expect(page).toHaveURL('/')`. Playwright resolves relative paths against the configured `baseURL`, making the assertion port-agnostic.

---

### WR-05 -- test_calendar.py resets _supabase_client attribute that does not exist [FIXED]

**Files modified:** `tests/api/test_calendar.py`
**Commit:** 24a7893
**Applied fix:** Removed both `cal_mod._supabase_client = None` lines (one in the shared fixture, one in `test_auth_uses_prompt_consent`) along with the associated `import api.routes.calendar as cal_mod` statements where they existed only for this dead reset. The actual isolation is provided by the `_get_async_supabase` monkeypatch already in place.

---

_Fixed: 2026-06-20_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
