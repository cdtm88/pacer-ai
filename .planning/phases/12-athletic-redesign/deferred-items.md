# Deferred Items — Phase 12 (athletic-redesign)

Out-of-scope discoveries found during plan execution, logged per the executor's
scope-boundary rule (not fixed, since they predate the current plan's changes).

## 12-04: Pre-existing eslint react-hooks/refs + react-hooks/set-state-in-effect errors in DuringSessionScreen.tsx

- **Found during:** Task 3 verification (`npx eslint`), 12-04-PLAN.md.
- **What:** 7 eslint errors in `frontend/src/screens/DuringSessionScreen.tsx`, all inside the plan's FROZEN persistence boundary (lines <389, unrelated to this plan's render-layer-only changes):
  - `react-hooks/refs`: `useState(restoredRef.current.stepIndex)` and `useRef(restoredRef.current.sessionStartTimestamp)` read a ref's `.current` during render.
  - `react-hooks/set-state-in-effect`: the live-resume fast-forward effect calls `setCurrentIndex`/`setCompletedDurationSecs`/`setStepStartEpoch` synchronously inside a `useEffect` body.
- **Verified pre-existing:** confirmed by linting the file as it existed at commit `9c6ac2d` (pre-12-04) — identical 7 errors, same code, before any 12-04 edits.
- **Why not fixed:** 12-04-PLAN.md explicitly freezes this boundary ("do not edit, do not reorder, do not change hook call order") to protect iOS kill/reopen session persistence (T-12-04 threat mitigation). Fixing these lint rules would require restructuring `restoredRef`/the fast-forward effect, which is an architectural change outside this plan's render-layer-only scope (Rule 4 territory, not Rule 1-3 auto-fix).
- **Recommendation:** a future plan explicitly scoped to `DuringSessionScreen`'s persistence logic (not a render-only rebuild) should address these, with `session.test.tsx` as the regression gate.
