---
phase: "04"
phase_name: "ui-and-calendar"
status: "issues_found"
depth: "standard"
files_reviewed: 3
files_reviewed_list:
  - frontend/tests/e2e/phase4.spec.ts
  - frontend/src/components/history/FitUploadZone.tsx
  - frontend/src/components/session/TsbChip.tsx
findings:
  critical: 2
  warning: 4
  info: 3
  total: 9
reviewed_at: "2026-06-20"
---

# Phase 04 Gap-Closure: Code Review Report

**Reviewed:** 2026-06-20T00:00:00Z
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Three gap-closure files that fix E2E test failures and add a testid/label change. The two production source files (FitUploadZone.tsx and TsbChip.tsx) are small and mostly correct, but carry two behavioral bugs. The Playwright suite (phase4.spec.ts) is the main concern: it contains LIFO route-ordering bugs that will cause the wrong mock to answer network requests in tests where `mockBackendApis` is called and then a per-test override is registered, a hardcoded absolute URL that breaks if the port ever changes, unconditional `waitForTimeout` calls that are the standard source of CI flake, and a catch block that silently absorbs test failures rather than failing the test.

---

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: LIFO ordering inverted — `/rides/upload` and `/pmc_history/latest` overrides are shadowed by the general handlers

**File:** `frontend/tests/e2e/phase4.spec.ts:222-232`
**Issue:** The comment on line 221 says "Register general routes before specific ones — Playwright uses LIFO so the last registered handler wins; specific routes must be registered after the general ones." The registrations that follow do the opposite for two route pairs:

- Lines 222-224: `/pmc_history/` (general) is registered first, then `/pmc_history/latest` (specific) is registered second. In LIFO order the *last registered* handler wins, so `/pmc_history/latest` is correctly prioritised over `/pmc_history/`. This pair is fine.
- Lines 228-232: `/rides/` (general) is registered first, then `/rides/upload` (specific) is registered second. In LIFO order `/rides/upload` wins over `/rides/`. Also fine.

However, in T13 (lines 510-513) a per-test override for `/rides/upload` is registered *after* `setupAuthenticated` (which includes `mockBackendApis`). In LIFO order the per-test handler wins, which is the intended behaviour. But in T09 (lines 421-429) the per-session override for `/sessions/session-today-id` is registered *after* `setupAuthenticated` which already registered `/sessions/[^/]+$` (the broad catch-all, line 213). In LIFO the per-test specific handler wins — but `route.continue()` on line 426 (the GET branch) re-enters the handler stack; there is no handler lower in the stack that will answer the GET, so the request falls through to the network. In a fully-mocked test environment there is no real server, so the session GET for `session-today-id` will fail with a network error, likely causing the session card not to render and `patchCalled` to never be set.

Additionally the `sessions/[^/]+$` general handler (line 213) calls `route.fallback()` for non-PATCH requests. `route.fallback()` means "let another matching route handle this". Because the more specific `/sessions/today` and `/sessions/upcoming` are registered *before* (and therefore *lower* in the LIFO stack than) `/sessions/[^/]+$`, they will never receive the fallback — the fallback direction in LIFO is toward earlier-registered (lower-priority) handlers. The fallback comment on line 217 is misleading and the routing will never reach the specific handlers via fallback.

**Fix:** Register the general `sessions/[^/]+$` PATCH-only handler *before* the specific `/sessions/today` and `/sessions/upcoming` handlers so that it sits lower in the LIFO stack and the specific handlers win. Remove `route.fallback()` for the GET branch — add explicit `route.continue()` only if a real server is running, otherwise simply do nothing (the more specific routes already handle GET /sessions/today and GET /sessions/upcoming):
```typescript
// Register general (lower priority) first, then specific (higher priority last)
await page.route(/\/sessions\/[^/]+$/, (route) => {
  if (route.request().method() === 'PATCH') {
    route.fulfill(respond({ status: 'completed' }))
  }
  // GET requests: do nothing here — let the more specific handlers (registered after)
  // win via LIFO. Do not call route.fallback() as it goes toward lower-priority handlers.
})
await page.route(/\/sessions\/today/, ...)     // registered after → higher priority
await page.route(/\/sessions\/upcoming/, ...)  // registered after → higher priority
```

---

### CR-02: T09 uses `waitForTimeout(500)` to assert `patchCalled` — race condition that cannot be fixed by increasing the timeout

**File:** `frontend/tests/e2e/phase4.spec.ts:434-435`
**Issue:** The test for "Mark done triggers PATCH" sets `patchCalled = true` inside the route handler, then calls `await page.waitForTimeout(500)` and asserts `expect(patchCalled).toBe(true)`. This is a race condition: 500 ms is a fixed wall-clock delay that has no relationship to when the button click's async mutation resolves. On a slow CI machine the mutation may not have fired within 500 ms. On a fast machine the timeout is wasted. More critically, because the route-ordering bug in CR-01 means the session GET may fail, `patchCalled` may never be set even with an arbitrarily long timeout.

**Fix:** Replace the fixed timeout with `waitForRequest` or a DOM assertion that only resolves after the server interaction completes:
```typescript
const patchRequest = page.waitForRequest(
  (req) => /\/sessions\/session-today-id/.test(req.url()) && req.method() === 'PATCH',
  { timeout: 5000 },
)
await page.getByRole('button', { name: /Mark done/i }).click()
await patchRequest  // resolves as soon as the request is intercepted
expect(patchCalled).toBe(true)
```

---

## Warnings

### WR-01: Hardcoded absolute URL breaks test portability

**File:** `frontend/tests/e2e/phase4.spec.ts:640`
**Issue:** `await expect(page).toHaveURL('http://localhost:5174/')` asserts on the full absolute URL including host and port. The playwright.config.ts `baseURL` is `http://localhost:5174`, so if the port is ever changed in the config (or the test is run in a CI environment that randomises ports), this assertion will fail while the navigation itself succeeded. Every other URL assertion in the file correctly uses a relative regex `/\/login/` or `/\/onboarding/`.

**Fix:**
```typescript
await expect(page).toHaveURL(/\/$/)
// or use the baseURL-relative form:
await expect(page).toHaveURL('/')
```

---

### WR-02: T13 catch block silently passes the test on upload-zone failure

**File:** `frontend/tests/e2e/phase4.spec.ts:537-542`
**Issue:** The outer `try/catch` around the file chooser interaction catches all errors and logs a message with `console.log` instead of failing the test or calling `test.skip()`. If the `data-testid="fit-upload-zone"` element is present (it is, after the fix in FitUploadZone.tsx), the click should open a file chooser. If it does not — for any reason including a broken component, wrong testid, or an unhandled exception — the catch block swallows the failure and the test reports green with `uploadCalled === false`. The `expect(uploadCalled).toBe(true)` on line 536 is inside the `try` block and is never reached if the file chooser throws.

**Fix:** Use `test.skip()` for the known-unsupported case, and let unexpected errors propagate:
```typescript
try {
  const fileChooser = await fileChooserPromise
  await fileChooser.setFiles({ name: 'test.fit', mimeType: 'application/octet-stream', buffer: Buffer.from('FIT') })
  await page.waitForRequest((req) => /\/rides\/upload/.test(req.url()), { timeout: 3000 })
  expect(uploadCalled).toBe(true)
} catch (err) {
  if (err instanceof Error && err.message.includes('file chooser')) {
    test.skip(true, 'Upload zone does not open file chooser via click; drag-drop only')
  }
  throw err  // re-throw unexpected errors so the test fails
}
```

---

### WR-03: T15 onboarding render assertion is vacuously true

**File:** `frontend/tests/e2e/phase4.spec.ts:585-588`
**Issue:** The assertion is:
```typescript
await expect(
  page.locator('progress, [role="progressbar"], .progress').or(page.locator('main, [data-testid="onboarding"]')).first(),
).toBeTruthy()
```
`locator.toBeTruthy()` is not a valid Playwright assertion — `locator` objects are always truthy JavaScript objects regardless of whether the element exists on the page. The correct assertion would be `.toBeVisible()` or `.toBeAttached()`. As written, this test always passes and verifies nothing about the onboarding screen's actual rendered content.

**Fix:**
```typescript
await expect(
  page.locator('progress, [role="progressbar"], .progress').or(page.locator('main, [data-testid="onboarding"]')).first(),
).toBeVisible()
```

---

### WR-04: `handleFileChange` resets `inputRef.current.value` before the upload completes

**File:** `frontend/src/components/history/FitUploadZone.tsx:60-67`
**Issue:** `handleFileChange` calls `void handleUpload(file)` (fire-and-forget) and immediately resets `inputRef.current.value = ''` on the next line. The reset is intended to allow re-uploading the same file. However, because `handleUpload` is async and `void` suppresses the await, the reset runs synchronously while the upload is in flight. On some browsers the `File` object obtained from `inputRef.current.files[0]` on line 61 is a live reference that may be invalidated when the input value is cleared, potentially causing the upload to fail mid-stream or send an empty file.

**Fix:** Reset the value after the upload settles, inside `handleUpload`'s `finally` block, so the file reference is never cleared while the upload is in progress:
```typescript
function handleFileChange() {
  const file = inputRef.current?.files?.[0]
  if (file) {
    handleUpload(file).finally(() => {
      if (inputRef.current) inputRef.current.value = ''
    })
  }
}
```
Remove the `void` keyword and the explicit `value = ''` reset from `handleFileChange`.

---

## Info

### IN-01: T13 uses `waitForTimeout(500)` as the upload-success synchronisation point

**File:** `frontend/tests/e2e/phase4.spec.ts:535`
**Issue:** After setting files on the file chooser, the test calls `await page.waitForTimeout(500)` before asserting `uploadCalled`. This is an arbitrary delay that contributes to CI flakiness and should be replaced with `page.waitForRequest` or `page.waitForResponse` as shown in the WR-02 fix suggestion.

---

### IN-02: `console.log` debug artifact in T13

**File:** `frontend/tests/e2e/phase4.spec.ts:540`
**Issue:** `console.log('File chooser not triggered via click; upload zone may require drag-drop')` is debug output in the test suite. In CI it will appear in test output and confuse readers when the test actually passes.

**Fix:** Replace with `test.skip(...)` (see WR-02) or remove entirely.

---

### IN-03: TSB classification boundary creates unintuitive dead-zone around zero

**File:** `frontend/src/components/session/TsbChip.tsx:16-19`
**Issue:** `classifyTsb` returns `'balanced'` for TSB in the range `(-10, 5]` inclusive. A TSB of 0 (perfectly neutral) and a TSB of 4.9 (approaching fresh) both show "Balanced". The thresholds are documented as intentional per the spec comment, but the boundary of `tsb > 5` (strictly greater than) means a TSB of exactly 5 shows "Balanced" rather than "Fresh". If the spec intends 5 to be the "fresh" threshold, the condition should be `tsb >= 5`.

**Fix:** Clarify with the spec owner whether the boundary is exclusive or inclusive. If 5 should show "Fresh":
```typescript
if (tsb >= 5) return 'fresh'
if (tsb <= -10) return 'fatigued'
```

---

_Reviewed: 2026-06-20T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
