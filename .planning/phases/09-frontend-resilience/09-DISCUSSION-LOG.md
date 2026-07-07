# Phase 9: Frontend Resilience - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-07
**Phase:** 09-frontend-resilience
**Areas discussed:** Review scope boundary, SSE / chat error recovery UX, Stale session recovery UX, Error boundary UX

---

## Review scope boundary

| Option | Description | Selected |
|--------|-------------|----------|
| Named 8 only | Stick exactly to ROADMAP.md's goal line; defer the other 6 to a future phase | |
| Full list (14 items) | Fix all Critical/Major findings from the app review, not just the named 8 | ✓ |
| Let me pick which extras | Review the 6 additional bugs one by one | |

**User's choice:** Full list (14 items) — Recommended
**Notes:** All 6 extras are in the same files/screens already being touched for the named 8; cheaper to fix together than a separate future pass. ROADMAP.md's goal text needs reconciling with this expanded scope.

---

## SSE / chat error recovery UX

### Chat SSE stream error

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-retry silently, then show banner | 1-2 automatic reconnects with backoff, then inline error + manual Retry | ✓ |
| Immediate error banner, no auto-retry | Show error immediately on first failure | |
| Silent auto-retry only, no banner | Keep retrying in background, no explicit failure state | |

**User's choice:** Auto-retry silently, then show banner — Recommended

### Empty-done-swallow (tool-only turns)

| Option | Description | Selected |
|--------|-------------|----------|
| Clear and unbrick silently | isDone with empty content treated as normal completion, no visible reply | ✓ |
| Show a fallback message | Generic "Done"/"Updated your plan" bubble | |

**User's choice:** Clear and unbrick silently — Recommended

### Conversation history reload

| Option | Description | Selected |
|--------|-------------|----------|
| Refetch on cache miss | Look up existing conversation from DB on revisit, show loading state | ✓ |
| Extend cache GC time instead | Bump gcTime so the miss happens less often | |
| Both | Refetch-on-miss plus longer gcTime | |

**User's choice:** Refetch on cache miss — Recommended

### Onboarding confirm-stream error handling

| Option | Description | Selected |
|--------|-------------|----------|
| Same pattern as chat | Clear stream state, inline error, manual retry button | ✓ |
| Different: reset to previous step | Bounce back to re-answer the last question | |

**User's choice:** Same pattern as chat — Recommended

---

## Stale session recovery UX

| Option | Description | Selected |
|--------|-------------|----------|
| Silently discard, reset to fresh Today | Clear stale localStorage entry, no dialog/toast | ✓ |
| Show a brief notice first | Toast explaining the previous session data was cleared | |

**User's choice:** Silently discard, reset to fresh Today — Recommended
**Notes:** Live-resume overshoot and cross-account cache bleed were checked in on but left as Claude's discretion — both have one obviously-correct fix (match the working reload-path pattern; clear cache on auth transitions).

---

## Error boundary UX

### Fallback content

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal: message + reload button | "Something went wrong" + reload, no detail | ✓ |
| Message + reload + error detail | Same plus collapsed technical detail | |

**User's choice:** Minimal: message + reload button — Recommended

### Boundary placement

| Option | Description | Selected |
|--------|-------------|----------|
| Per-route, inside AppLayout | Nav shell survives a screen crash; user can navigate away | ✓ |
| Single global boundary | Whole app falls back on any crash | |

**User's choice:** Per-route, inside AppLayout — Recommended

---

## Claude's Discretion

- Live-resume overshoot fast-forward fix (match reload path)
- Cross-account query cache clear on SIGNED_IN/sign-out
- Ride field mismatch (frontend field names vs. backend response shape)
- ZWO export error shape parsing fix
- iOS ZWO export popup-block (synchronous window.open before any await)
- Auth callback double-exchange (single code-consumption path)
- Upload query invalidation scope (extend beyond ['rides'])
- Upload progress indicator + drag-drop .fit validation
- AppLayout scroll/pin fix

## Deferred Ideas

None — discussion stayed within phase scope. Scope was explicitly expanded (not narrowed) to the full app-review list.
