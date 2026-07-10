---
phase: 04-ui-and-calendar
plan: 20
subsystem: frontend/chat
tags: [bug-fix, sse, chat, api-client, gap-closure]
status: complete
requirements: [UI-06]
dependency_graph:
  requires: [04-13]
  provides: [chat-sse-flow-unblocked]
  affects: [ChatScreen, OnboardingScreen]
tech_stack:
  added: []
  patterns: [backend-shape-mapping, sse-url-separator]
key_files:
  modified:
    - frontend/src/lib/api.ts
decisions:
  - "Map backend conversation_id to Conversation.id at the api.ts boundary rather than touching ChatScreen — keeps the fix contained to the API layer"
  - "Derive sseUrl separator from path.includes('?') — simplest correct approach with no edge cases"
metrics:
  duration: "10 minutes"
  completed: "2026-06-21"
  tasks_completed: 1
  tasks_total: 1
  files_modified: 1
---

# Phase 04 Plan 20: Chat api.ts Bug Fixes Summary

**One-liner:** Fixed two api.ts bugs blocking Chat SSE flow: `createConversation` now maps `conversation_id` to `id`, and `sseUrl` picks `?` or `&` based on existing query string.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Map conversation_id to id in createConversation; fix sseUrl query-string separator | b60f37b | frontend/src/lib/api.ts |

## What Was Built

Two targeted edits to `frontend/src/lib/api.ts` closing UAT GAP 5 (Test 14: Chat "no response"):

**Edit 1 -- createConversation response mapping:**
The backend `POST /conversations/` returns `{conversation_id: "..."}` but the function was returning `res.json()` typed as `Conversation` unchanged. Since `Conversation.id` was therefore `undefined`, ChatScreen's `conversation?.id` guard was always falsy and `handleSend` bailed before any SSE request. The fix parses the JSON into a loosely-typed object and spreads it with `id` set to `data.conversation_id ?? data.id ?? ''`, preserving the `Conversation` return type while guaranteeing a defined `id`.

**Edit 2 -- sseUrl separator:**
`sseUrl` was always appending `?token=...` even when the path already contained a query string. ChatScreen passes `/chat/stream?conversation_id=...&message=...`, producing a double-`?` URL that browsers reject. The fix computes `sep = path.includes('?') ? '&' : '?'` so:
- `/onboarding/start` (bare path) -> `?token=...` (unchanged for OnboardingScreen)
- `/chat/stream?...` (has query) -> `&token=...` (valid single-`?` URL)

## Verification

- `grep -q "conversation_id" src/lib/api.ts` -- PASS
- `tsc --noEmit` -- PASS (no type errors)
- `npm run build` -- PASS (vite build succeeded, PWA assets generated)

## Deviations from Plan

None -- plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

None -- this plan only modifies client-side API helper functions; no new network endpoints or auth paths introduced.

## Self-Check: PASSED

- [x] `frontend/src/lib/api.ts` modified with both fixes
- [x] Commit b60f37b exists and contains the correct changes
- [x] No file deletions
- [x] tsc and build both passed
