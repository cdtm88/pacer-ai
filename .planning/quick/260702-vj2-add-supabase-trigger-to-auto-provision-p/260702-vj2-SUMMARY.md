---
phase: quick-260702-vj2
plan: 01
subsystem: database
tags: [supabase, postgres, trigger, auth, rls, migration]

requires: []
provides:
  - "public.users auto-provisioned via AFTER INSERT trigger on auth.users"
  - "Backfilled 2 orphaned auth.users rows into public.users"
affects: [onboarding, conversations, profiles, signup]

tech-stack:
  added: []
  patterns:
    - "SECURITY DEFINER trigger function with SET search_path = public for auth-schema-triggered writes into public schema"

key-files:
  created:
    - supabase/migrations/0004_auto_provision_users.sql
  modified: []

key-decisions:
  - "Fixed via a DB-level trigger (standard Supabase handle_new_user pattern) rather than backend upsert-on-request, so the guarantee holds regardless of which backend code path runs first and covers ALL public.users FK dependents (conversations, profiles, sessions, rides, plans, etc.), not just the one call site that surfaced the bug"
  - "Did not touch backend/routes/onboarding.py's silent except Exception: pass — explicitly out of scope for this task; the missing-row provisioning was the actual root cause, not the error handling"
  - "Executed directly in the main checkout rather than via a worktree-isolated executor, because supabase/.temp/project-ref (the CLI's link to the production project) is gitignored and would be absent in a fresh git worktree, breaking `supabase db push --linked`"

patterns-established:
  - "Supabase migrations that touch auth.users use SECURITY DEFINER + SET search_path = public to harden against search_path hijacking"

requirements-completed: [QUICK-260702-vj2]

coverage:
  - id: D1
    description: "public.users has a row for every auth.users row (3/3), including the 2 previously orphaned (christianmoore88+test1@gmail.com, e2e-test-260702@moorelabs.uk)"
    requirement: "QUICK-260702-vj2"
    verification:
      - kind: other
        ref: "supabase db query 'SELECT count(*) FROM public.users' --linked (returned 3) + email list query (both emails present)"
        status: pass
    human_judgment: false
  - id: D2
    description: "on_auth_user_created AFTER INSERT trigger exists on auth.users"
    requirement: "QUICK-260702-vj2"
    verification:
      - kind: other
        ref: "supabase db query \"SELECT tgname FROM pg_trigger WHERE tgname = 'on_auth_user_created'\" --linked (returned 1 row)"
        status: pass
    human_judgment: false
  - id: D3
    description: "New onboarding conversations no longer hit the 23503/409 FK violation for fresh signups"
    requirement: "QUICK-260702-vj2"
    verification: []
    human_judgment: true
    rationale: "Not re-verified live via a brand-new signup + onboarding turn in this task (that's the next step of the in-progress E2E test, done separately via browser automation) — trigger presence and backfill are proven at the DB level, but the end-to-end conversation-threading behavior needs a live confirmation."

duration: 8min
completed: 2026-07-02
status: complete
---

# Quick Task 260702-vj2: Auto-provision public.users on signup Summary

**Added a SECURITY DEFINER trigger that inserts a `public.users` row whenever Supabase Auth creates an `auth.users` row, and backfilled the 2 existing orphaned rows — fixes a silent 409 FK violation that was resetting onboarding conversations on every turn for new signups.**

## Performance

- **Duration:** ~8 min
- **Tasks:** 4/4 complete
- **Files modified:** 1 (new migration file)

## Accomplishments
- `supabase/migrations/0004_auto_provision_users.sql` created: `public.handle_new_user()` trigger function (SECURITY DEFINER, `SET search_path = public`), `on_auth_user_created AFTER INSERT ON auth.users` trigger, and an idempotent backfill INSERT.
- Applied to the linked production project (`pxdfmlvrqveofguyxxfo`) via `supabase db push --linked --yes`.
- Verified live: `public.users` now has 3/3 rows (was 1/3), including the 2 previously-missing accounts; trigger confirmed present in `pg_trigger`.

## Task Commits

1. **Task 1: Write migration file** - included in `db81032`
2. **Task 2: Apply to production** - `supabase db push --linked --yes` (no git commit; direct DB operation)
3. **Task 3: Verify live DB** - `supabase db query ... --linked` (no git commit; verification only)
4. **Task 4: Commit migration file** - `db81032` (fix)

**Plan metadata:** `62da0ab` (docs: pre-dispatch plan)

## Files Created/Modified
- `supabase/migrations/0004_auto_provision_users.sql` - trigger function + trigger + backfill, all idempotent/re-runnable

## Decisions Made
- Chose a DB-level trigger over a backend upsert-on-request because it's the standard, robust Supabase pattern: it guarantees provisioning regardless of which backend code path a user's first authenticated request hits, and covers every table with a `public.users` FK (conversations, profiles, sessions, rides, pmc_history, plans, adaptations, messages, capability_gaps) — not just the `conversations` insert that happened to surface the bug.
- Left `backend/routes/onboarding.py`'s bare `except Exception: pass` untouched — the missing-row provisioning was the actual defect; the silent-failure error handling is a separate visibility concern for a future task.
- Ran this quick task's execution directly in the main checkout (not via an isolated worktree agent) because `supabase/.temp/project-ref` — required for `supabase db push --linked` to know which project to target — is gitignored and would not exist in a fresh worktree, which would have made the migration-apply step fail silently on project detection.

## Deviations from Plan

None — plan executed exactly as written, except for the deviation noted above (direct execution instead of worktree-isolated executor), which was a necessary environment adaptation, not a scope change.

## Issues Encountered
- `supabase db push` emitted a Docker-daemon-not-running warning (`failed to cache migrations catalog`) — this only affects local migration-catalog caching for local dev, not the actual remote push, which completed successfully (confirmed via the Task 3 live-DB verification, not just the push command's exit message).

## User Setup Required
None — migration applied directly to production via the already-linked Supabase CLI; no dashboard or external configuration needed.

## Next Phase Readiness
- The E2E test in progress (signup → onboarding → plan → chat) can now resume: the existing test account (`e2e-test-260702@moorelabs.uk`) has a `public.users` row and can proceed with multi-turn onboarding without hitting the silent conversation-reset bug.
- Recommend a follow-up (not done here, out of scope): replace `onboarding.py`'s bare `except Exception: pass` around `create_conversation`/`load_conversation`/`save_messages` with at least structured logging, so a future regression in this area surfaces instead of failing silently again.

---
*Quick task: 260702-vj2*
*Completed: 2026-07-02*
</content>
