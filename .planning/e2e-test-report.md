---
generated: 2026-06-21
source: Full E2E + UI Review (Playwright, desktop + mobile, two spec files)
status: findings-ready
for-gsd: true
---

# Full E2E + UI Test Report

## Scores

| Spec | Passed | Failed | Total | Duration |
|------|--------|--------|-------|----------|
| `phase4.spec.ts` (existing) | 25 | 9 | 34 | 4.6m |
| `full-uat.spec.ts` (new, added this session) | 44 | 24 | 68 | 8.2m |

Viewports: iPhone 14 (390×844) + Desktop (1440×900)  
Screens covered: Login, Today, Agenda, History, Chat, Settings, DuringSession, Onboarding

---

## Root Cause Map

All 33 failures fall into 4 categories:

| Category | Phase4 | Full-UAT | Total |
|----------|--------|----------|-------|
| A. Mock infrastructure bugs | 1 | 6 | 7 |
| B. App changed, tests stale | 7 | 15 | 22 |
| C. New test code bugs | 0 | 2 | 2 |
| D. New app finding | 0 | 1 | 1 |

---

## Category A — Mock Infrastructure Bugs

These are bugs in the test helper `mockBackendApis` that affect both specs.
Playwright registers routes **LIFO** (last-in, first-out), so specific routes must
be registered **after** general ones — or they'll be shadowed.

### A1 — Rides mock returns wrong JSON shape

`getRides()` expects `{ rides: Ride[] }` from the server.
The mock returns the raw array. Result: `data.rides` is `undefined` → always returns `[]`.

**Affected tests:** T12 (phase4), 4× History tests (full-uat)

```typescript
// Before (broken)
await page.route(/\/rides\//, (route) =>
  route.fulfill(respond(overrides.rides ?? fixtureRides)),
)

// After (fix)
await page.route(/\/rides\//, (route) =>
  route.fulfill(respond({ rides: overrides.rides ?? fixtureRides })),
)
```

### A2 — PMC Latest route shadowed by general PMC route

`/pmc_history\/latest` registered first, `/pmc_history\/` registered second.
LIFO → general route always wins → `getLatestPmc` receives `{ history: [] }` → no `date`
field → returns `null` → TSB chip never shows.

**Affected tests:** TSB "Fresh" test (full-uat), any test verifying PMC-gated UI

```typescript
// Fix: register specific route LAST (after general)
await page.route(/\/pmc_history\//, (route) => route.fulfill(respond({ history: [] })))
await page.route(/\/pmc_history\/latest/, (route) =>
  route.fulfill(respond(overrides.pmc ?? fixturePmcReady)),
)
```

### A3 — Calendar settings route shadowed by general calendar route

Same LIFO bug. `/calendar\/settings` registered first, `/calendar\/` second.
`getCalendarSettings` always receives `{}` → `connected` is falsy → "Connected" state
never renders in Settings.

**Affected tests:** Settings connected state test (full-uat)

```typescript
// Fix: register specific route LAST
await page.route(/\/calendar\//, (route) => route.fulfill(respond({})))
await page.route(/\/calendar\/settings/, (route) =>
  route.fulfill(respond(overrides.calendar ?? { connected: false })),
)
```

---

## Category B — App Changed, Tests Stale

### B1 — Export to Zwift Button Is Now Enabled

Commit `031f1ff` deliberately enabled the button and wired `ZwoExportModal`.
All tests asserting `toBeDisabled()` or a tooltip wrapper now fail.

**Affected tests:** T11 both (phase4), Export disabled tests (full-uat)

**Fix needed:** Rewrite T11 to verify modal opens on click:
- Button is enabled (not disabled)
- Clicking opens ZwoExportModal
- Modal shows ZWO preview content and download button

### B2 — DuringSession Screen Fully Redesigned

Commit `8377054` replaced static step list + "Timer activates in next phase" with:
- Live countdown timer per step (shows actual remaining seconds, not "00:00")
- Zone badge + power targets
- "Skip step" button
- "End session" button (only visible when steps exist)

Old assertions that fail:
- `getByText('00:00')` — timer now shows live countdown
- `getByText('Timer activates in next phase')` — caption removed
- `getByRole('button', { name: /End session/i })` — only renders when steps > 0

Additional issue: test fixtures use `structure: 'string'` but `parseSteps()` only handles
object structures. With a string, steps `[]` → screen shows `"No session steps available."`,
no End session button.

**Fix needed:**
- Use `fixtureSessionWithStructure` (object with warmup/main_set/cooldown)
- Assert live timer (e.g., `getByText(/\d{2}:\d{2}/)`)
- Assert step label (e.g., "Easy warm-up")
- Assert zone badge and "Skip step" button

### B3 — Login Screen Changed to Email+Password

Tests look for `"Send magic link"` button, OTP magic link flow.
Current UI: "Sign in" / "Create account" tabs, email + password form.

What still matches: `"PacerAI"`, `"Your adaptive cycling coach."`, `you@example.com` placeholder.
What changed: button label, validation flow, no magic link confirmation state.

**Fix needed:**
- Update button selector to `"Sign in"` / `"Create account"`
- Empty email error: `"Enter your email address"` still works
- Add: empty password error `"Enter your password"`
- Add: invalid credentials error `"Incorrect email or password."`
- Remove: OTP/magic link flow tests

### B4 — Accordion Trigger Attribute Changed

Tests use `[data-radix-accordion-trigger]` selector which doesn't exist in Radix UI v1.6.0.
Result: accordion expand/collapse tests time out.

**Fix needed:** Use role-based or text-based selector instead:
```typescript
// Replace
const firstTrigger = page.locator('[data-radix-accordion-trigger]').first()

// With
const firstTrigger = page.locator('[data-state="closed"], [data-state="open"]').first()
// or
const firstTrigger = page.getByRole('button').filter({ hasText: /tempo|recovery/i }).first()
```

---

## Category C — New Test Code Bugs

### C1 — Zone Accent Bar: Hex Color vs RGB

Test: `expect(style).toContain('#228BE6')` — fails because browser converts hex to
`rgb(34, 139, 230)` in computed style attributes.

```typescript
// Fix
expect(style).toMatch(/#228BE6|rgb\(34,\s*139,\s*230\)/)
```

### C2 — Mark Missed: Monitors Wrong Endpoint

`markSessionMissed` calls **POST** `/adaptations/sessions/{id}/missed`.
Test monitors PATCH `/sessions/{id}` and checks `patchCalled`. Always false.

```typescript
// Fix: intercept the correct endpoint
let missedCalled = false
await page.route(/\/adaptations\/sessions\/session-today-id\/missed/, (route) => {
  missedCalled = true
  route.fulfill({ status: 200, contentType: 'application/json', body: '{}' })
})
// ... assert missedCalled = true
```

---

## Category D — New App Finding

### D1 — Wake Lock Permission Error on Session Screen (Headless Only)

`useWakeLock()` in DuringSessionScreen calls `navigator.wakeLock.request('screen')`.
Headless Chromium denies this permission → fires two `pageerror` events:
`"Wake Lock permission request denied"`.

**Impact:** Not a bug in production (iOS Safari grants Wake Lock on a real device).
But the error appears in test console output and fails strict error-checking tests.

**Recommendation:** Either:
- Suppress Wake Lock errors in headless test environment via `permissions` grant
- Or scope the console error test to exclude Wake Lock errors:
  ```typescript
  const errors = errors.filter(msg => !msg.includes('Wake Lock'))
  ```

---

## What Passes — Confirmed Working

### Navigation & Auth
- Unauthenticated redirects to /login (all protected routes)
- Bottom tab bar (mobile): Today, Agenda, History, Chat — all 4 clickable
- Desktop sidebar (1440px): all 4 links clickable and navigate correctly
- Settings gear → /settings → back to Today works
- Sign out → /login (T16)

### Today Screen
- SessionCard shows objective + action buttons (4 stacked)
- No session empty state shows "No session today"
- Upcoming sessions strip visible
- No em-dashes

### Mark Actions
- Mark missed dialog opens with correct copy
- "Keep it" cancel closes dialog
- No em-dashes in dialog
- Mark done fires correct API call (T09)

### Agenda
- Sessions grouped by week header
- Empty state "No sessions planned yet"
- Renders on desktop

### History
- FIT upload zone present ("Drop a .FIT file here, or tap to upload")
- Empty state "No rides yet"
- No em-dashes

### Chat
- Input and send button visible (mobile + desktop)
- Empty state copy visible
- Text input accepts typing

### Settings
- All three sections visible (Profile, Google Calendar, Account)
- "Connect Google Calendar" button when not connected
- Sign out button visible
- No em-dashes

### DuringSession (with correct fixture)
- End session navigates to /
- Step information shows (warmup, main set, cool-down labels)
- No em-dashes

### Design System
- No pure black backgrounds (`rgb(0,0,0)`) across all screens
- Console clean on Today screen (zero JS errors)

---

## Fix Priority for GSD

| Pri | Fix | File | Effort |
|-----|-----|------|--------|
| 1 | Fix rides mock shape `{ rides: [...] }` | `tests/e2e/phase4.spec.ts` + `full-uat.spec.ts` | XS |
| 1 | Fix PMC route LIFO ordering | both specs | XS |
| 1 | Fix calendar route LIFO ordering | both specs | XS |
| 2 | Rewrite T11 Export tests (modal flow) | phase4.spec.ts + full-uat.spec.ts | S |
| 2 | Rewrite T18 DuringSession tests (live timer) | both | S |
| 2 | Update Login tests for email+password | both | S |
| 3 | Fix accordion selector | full-uat.spec.ts | XS |
| 3 | Fix zone accent bar hex vs rgb | full-uat.spec.ts | XS |
| 3 | Fix markMissed endpoint monitoring | full-uat.spec.ts | XS |
| 3 | Handle Wake Lock in headless env | full-uat.spec.ts | XS |
| 4 | DuringSession zero-steps: add navigation button | DuringSessionScreen.tsx | S |

---

## Artefacts

- New E2E spec: `frontend/tests/e2e/full-uat.spec.ts` (68 tests, desktop + mobile)
- Screenshots: `screenshots/login-desktop.png`, `screenshots/login-mobile.png`
- Test results: `frontend/test-results/` (39 failure artifacts with snapshots + error contexts)
