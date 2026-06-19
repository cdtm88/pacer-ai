---
status: partial
phase: "01"
iteration: 1
findings_in_scope: 11
fixed: 10
skipped: 1
fixed_at: "2026-06-19"
---

# Code Review Fix Report: Phase 01

**Fixed at:** 2026-06-19
**Source review:** .planning/phases/01-sports-science-foundation/01-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 11 (4 Critical, 7 Warning)
- Fixed: 10
- Skipped: 1 (WR-007: deferred to Phase 3 per architecture decision)

## Fixed Issues

### CR-001: compute_tss crashes with ZeroDivisionError when ftp=0

**Files modified:** `sports_science/metrics.py`, `tests/sports_science/test_metrics.py`
**Commit:** `982ee36` -- fix(01): CR-001 WR-004 guard ftp=0 in compute_tss; rename if key to intensity_factor
**Applied fix:** Added early-return `ToolResult(value=None)` guard before the duration check when `ftp <= 0`. Also bundled WR-004 in the same commit (see WR-004 below).

### CR-002: estimate_ftp_from_rides raises unhandled RuntimeError on convergence failure

**Files modified:** `sports_science/ftp.py`
**Commit:** `c8c8743` -- fix(01): CR-002 WR-001 wrap curve_fit in try/except; fix confidence docstring
**Applied fix:** Wrapped `curve_fit` call in `try/except (RuntimeError, ValueError)` that returns `ToolResult(value=None, confidence="insufficient_data")` instead of propagating the exception through the tool layer.

### CR-003: log_capability_gap raises KeyError on missing env vars

**Files modified:** `sports_science/capability_gap.py`
**Commit:** `41337e1` -- fix(01): CR-003 use os.environ.get in _get_supabase; wrap DB insert in try/except
**Applied fix:** Changed `os.environ["KEY"]` to `os.environ.get("KEY")` with an explicit `EnvironmentError` when either var is missing. Wrapped the entire `_get_supabase()` call and DB insert in `try/except Exception: pass` so gap logging is always best-effort and never blocks the fallback `ToolResult`.

### CR-004: messages RLS allows cross-conversation message injection

**Files modified:** `supabase/migrations/0001_initial_schema.sql`
**Commit:** `3f2bdc0` -- fix(01): CR-004 WR-003 WR-005 schema security and integrity constraints
**Applied fix:** Added `WITH CHECK (user_id = auth.uid() AND EXISTS (SELECT 1 FROM public.conversations c WHERE c.id = conversation_id AND c.user_id = auth.uid()))` to the messages RLS policy so INSERT is blocked unless the conversation belongs to the authenticated user.

### WR-001: Confidence docstring says medium: 7-12 but code produces high at n=12

**Files modified:** `sports_science/ftp.py`
**Commit:** `c8c8743` -- fix(01): CR-002 WR-001 wrap curve_fit in try/except; fix confidence docstring
**Applied fix:** Corrected docstring from `medium: 7-12 efforts` to `medium: 7-11 efforts` to match the `elif n < 12` boundary in code. Note: the active `best_ftp_estimate=None` call site (dead FTP-relative filter path) is a Phase 2 enhancement; documented in code comments and deferred.

### WR-002: progress_load stalls permanently when current_ctl=0 and back_issues=True

**Files modified:** `sports_science/load.py`
**Commit:** `a170bc2` -- fix(01): WR-002 add BACK_CONSTRAINT_MIN_INCREASE floor to prevent CTL=0 stall
**Applied fix:** Added `BACK_CONSTRAINT_MIN_INCREASE = 2.0` constant and changed `back_cap = current_ctl * ramp_threshold` to `back_cap = max(current_ctl * ramp_threshold, BACK_CONSTRAINT_MIN_INCREASE)` so new users starting at CTL=0 can always receive a non-zero weekly load target.

### WR-003: pmc_history has no UNIQUE(user_id, date) constraint

**Files modified:** `supabase/migrations/0001_initial_schema.sql`
**Commit:** `3f2bdc0` -- fix(01): CR-004 WR-003 WR-005 schema security and integrity constraints
**Applied fix:** Added `CONSTRAINT pmc_history_user_date_unique UNIQUE (user_id, date)` inline in the `pmc_history` table definition.

### WR-004: "if" dict key in TSS result is a Python reserved word

**Files modified:** `sports_science/metrics.py`, `tests/sports_science/test_metrics.py`
**Commit:** `982ee36` -- fix(01): CR-001 WR-004 guard ftp=0 in compute_tss; rename if key to intensity_factor
**Applied fix:** Renamed `"if"` to `"intensity_factor"` in both the `compute_tss` return dict (all three occurrences including the zero-NP path) and the corresponding test assertion.

### WR-005: sessions.status and messages.role missing CHECK constraints

**Files modified:** `supabase/migrations/0001_initial_schema.sql`
**Commit:** `3f2bdc0` -- fix(01): CR-004 WR-003 WR-005 schema security and integrity constraints
**Applied fix:** Added `CHECK (status IN ('planned', 'completed', 'skipped', 'partial'))` to `sessions.status` and `CHECK (role IN ('user', 'assistant', 'tool'))` to `messages.role`.

## Skipped Issues

### WR-007: google_tokens stores OAuth refresh tokens unencrypted

**File:** `supabase/migrations/0001_initial_schema.sql:13`
**Reason:** Skipped per architecture decision -- the column comment already marks this as "encrypted at app layer (Phase 3)". Adding a `google_connected: boolean` column now and deferring the tokens column to Phase 3 is the correct approach, but that schema change belongs in Phase 3 planning, not as a patch to Phase 1. No real OAuth tokens will be written before Phase 3 encryption is wired.
**Original issue:** Column accepts plaintext jsonb; Google OAuth refresh tokens stored without encryption before Phase 3 encryption is in place.

---

_Fixed: 2026-06-19_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
