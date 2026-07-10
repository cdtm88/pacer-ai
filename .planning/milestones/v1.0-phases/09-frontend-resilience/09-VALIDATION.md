---
phase: 09
slug: frontend-resilience
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-07
---

# Phase 09 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Vitest 4.1.9 (`frontend/package.json`) |
| **Config file** | `frontend/vitest.config.ts` (jsdom environment, `src/tests/setup.ts`, glob `src/tests/**/*.{test,spec}.{ts,tsx}`) |
| **Quick run command** | `cd frontend && npx vitest run src/tests/<file>.test.tsx` |
| **Full suite command** | `cd frontend && npx vitest run` |
| **Estimated runtime** | ~30 seconds (full suite, existing baseline) |

---

## Sampling Rate

- **After every task commit:** Run the specific test file(s) touched by that task's fix (see Per-Task Verification Map)
- **After every plan wave:** `cd frontend && npx vitest run` (full suite)
- **Before `/gsd-verify-work`:** Full suite green, plus the manual-only items explicitly checked off
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

| Task ID | Item | Requirement | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|-------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | 1. Stale session hijack | D-06 | `PersistedSession` id/date mismatch discards stale entry silently | unit | `npx vitest run src/tests/session.test.tsx` | ✅ extend | ⬜ pending |
| TBD | 2. Chat SSE error bricks input | D-02 | Auto-retry then terminal error clears `activeStreamUrl`, re-enables input | unit | `npx vitest run src/tests/useSSEStream.test.ts src/tests/chat.test.tsx` | ✅ extend — rewrite stale "Reconnecting..." assertion | ⬜ pending |
| TBD | 3. Empty-done swallow | D-03 | Tool-only turn (done + empty content) clears stream state silently | unit | `npx vitest run src/tests/chat.test.tsx` | ✅ extend | ⬜ pending |
| TBD | 4. History reload on cache miss | D-04 | `['active-conversation']` GC'd → refetch existing conversation, not a new row | unit/integration | `npx vitest run src/tests/chat.test.tsx` | ⚠️ extend — verify `GET /conversations/{id}` read endpoint exists first | ⬜ pending |
| TBD | 5. Ride field mismatch | discretion | History displays real values, not "--" | unit | `npx vitest run src/tests/history.test.tsx` | ❌ W0 | ⬜ pending |
| TBD | 6. ZWO error shape | discretion | `session_not_found` branch reachable, correct toast | unit | new test | ❌ W0 | ⬜ pending |
| TBD | 7. iOS ZWO popup-block | discretion | Blob download works on iOS Safari | manual-only | — | N/A | ⬜ pending |
| TBD | 8. Live-resume overshoot | discretion | Multi-step background suspension fast-forwards correctly | unit | `npx vitest run src/tests/useSessionTimer.test.ts src/tests/session.test.tsx` | ✅ extend | ⬜ pending |
| TBD | 9. AppLayout scroll/pin | discretion | Chat input stays pinned, auto-scroll works | manual/visual | — | N/A | ⬜ pending |
| TBD | 10. Cross-account cache bleed | discretion | `queryClient.clear()` fires on `SIGNED_IN` | unit | `npx vitest run src/tests/auth.test.tsx` | ✅ extend | ⬜ pending |
| TBD | 11. Auth callback double-exchange | discretion | Single code-consumption path, no login bounce on valid session | unit | `npx vitest run src/tests/auth.test.tsx` | ✅ extend/rewrite | ⬜ pending |
| TBD | 12. Router error boundary | D-09/D-10 | Per-route crash renders fallback, nav shell stays mounted | unit/integration | new test | ❌ W0 | ⬜ pending |
| TBD | 13. Onboarding stuck spinner | D-05 | Server error/early close surfaces retry banner, not infinite spinner | unit | `npx vitest run src/tests/onboarding.test.tsx` | ✅ extend | ⬜ pending |
| TBD | 14. Upload progress/drag-drop/invalidation | discretion | Progress renders while uploading; drag-drop rejects non-.fit; success invalidates pmc/session queries | unit | `npx vitest run src/tests/FitUploadZone.test.tsx` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*Task IDs are TBD — the planner assigns actual `{padded_phase}-{NN}-PLAN.md` IDs; this table maps by item number until then.*

---

## Wave 0 Requirements

- [ ] `frontend/src/tests/history.test.tsx` (or `RideRow.test.tsx`) — covers item 5 (Ride field alignment)
- [ ] New test coverage for item 6 (ZWO export error-shape parsing)
- [ ] New test coverage for item 12 (router error boundary render + nav-shell-stays-mounted assertion)
- [ ] `frontend/src/tests/FitUploadZone.test.tsx` — covers item 14 (progress indicator, drag-drop validation, invalidation call list)
- [ ] Verify backend `GET /conversations/{id}` (or equivalent) read-endpoint contract exists before finalizing item 4's test plan — if missing, item 4 has a hidden backend sub-task

---

## Manual-Only Verifications

| Behavior | Item | Why Manual | Test Instructions |
|----------|------|------------|--------------------|
| iOS ZWO export downloads (not popup-blocked) | 7 | Requires physical iOS Safari — confirm whether `<a download>` on blob URLs is still blocked before committing to the exact fix shape (Open Question 2 in RESEARCH.md) | Export a .zwo file from a real iOS device after the fix; confirm file downloads without a blocked-popup prompt |
| AppLayout scroll/pin behaves correctly | 9 | Layout/CSS visual behavior, not easily unit-testable | Open Chat on mobile viewport; confirm input stays pinned to bottom and auto-scroll follows new messages |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (items 5, 6, 12, 14 + item 4's backend-endpoint check)
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
