# Phase 4: UI and Calendar - Research

**Researched:** 2026-06-20
**Domain:** React PWA frontend, Supabase Auth, Google Calendar OAuth2, FastAPI JWT middleware
**Confidence:** MEDIUM

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Auth and User Identity**
- D-01: Supabase Auth with magic link (passwordless email). No password signup/login. User enters email, receives a magic link, clicks it to authenticate. Frontend uses `@supabase/supabase-js` client to handle the auth callback and session.
- D-02: On app load, check if the user has a profile row. If no profile exists, auto-redirect to `/onboarding`. After the interview completes and profile is saved, redirect to Today (`/`). This is the first-run gate.
- D-03: FastAPI JWT middleware (deferred from Phase 3) ships in Phase 4. Supabase JWT is verified on every API request using `python-jose`. The Supabase user_id flows through all API calls as the authenticated identity.

**Google Calendar Integration**
- D-04: Google Calendar connect lives on a dedicated Settings / Profile page, accessible from the nav (a settings icon or profile link). No inline prompt on Today.
- D-05: OAuth2 flow is server-side redirect: frontend links to `GET /calendar/auth` (FastAPI) which builds the Google authorization URL and redirects. Google returns to `GET /calendar/callback` (FastAPI), which stores the tokens encrypted in the DB, then redirects back to the frontend settings page.
- D-06: Settings page shows a "Google Calendar: Connected" chip with a disconnect button when connected. Sync failures show a non-blocking sonner toast; they do not disrupt the plan or chat.

**FIT File Upload UX**
- D-07: FIT upload lives on the History screen as a persistent drop zone or "Upload ride" button at the top of the list. Supports drag-and-drop and click-to-select. Calls the Phase 3 endpoint `POST /rides/upload`.
- D-08: After a successful upload: sonner success toast + History list auto-refetches to show the new ride row. No redirect; user stays on History.

**Phase 4 / Phase 5 Boundary**
- D-09: During-Session screen ships as a full visual layout (large-font current step, next step queued below, smaller later steps) with a static/non-ticking placeholder timer. "Start Session" on the Today screen navigates to `/session`. Phase 5 wires the real `Date.now()` delta timer, auto-advance logic, wake lock, and iOS Safari behavior.
- D-10: "Export to Zwift" button appears on the Today session card but is visually disabled with a tooltip ("Coming soon"). Phase 5 adds ZWO file generation and enables the button.

**Design System (locked from PRD)**
- D-11: Inter for all UI text and headings. Blue-6 (#228BE6) for fills, buttons, and large text only (not small body text). Small blue text uses blue-7 (#1B73C0). Body copy uses --ink (#1A2230) or --ink-2 (#5F646E). Zone colors: recovery #2B8A5B, endurance #228BE6, tempo #F0A030, threshold #E8590C, vo2 #C92A2A.
- D-12: Light mode only, no pure blacks anywhere. Neutrals use a faint blue undertone (--bg #F9F9FA, --surface #FFFFFF, --line #DFE0E2).
- D-13: No em dashes in any copy or generated text. Use commas, semicolons, colons, or separate sentences.
- D-14: TSB form chip (fresh/balanced/fatigued) and CTL sparkline on History are rendered only after 28+ days of PMC data. Show nothing (no placeholder) before that threshold.

**Navigation**
- D-15: Mobile bottom tab bar with 4 tabs: Today / Agenda / History / Chat. Settings accessible via a gear or profile icon (not a fifth tab).
- D-16: Desktop layout: left sidebar with the same 4 destinations; wider multi-column layouts for Today and Agenda.

### Claude's Discretion

No discretion items explicitly listed. Component library choices (shadcn/ui primitives to use), state management split (what goes in Zustand vs TanStack Query), file structure within `src/`, and SSE chat integration implementation details are implementation decisions for the planner.

### Deferred Ideas (OUT OF SCOPE)

- ZWO file generation and Zwift import acceptance test (Phase 5)
- Live During-Session timer with `Date.now()` deltas, auto-advance, and wake lock (Phase 5)
- NoSleep.js fallback for iOS before 18.4 (Phase 5)
- Full PMC three-line CTL/ATL/TSB chart (Phase 2 post-MVP)
- Dark mode (Phase 2 post-MVP)
- Web Bluetooth live power echo (Phase 2 post-MVP)
- Telegram bot (Phase 2 post-MVP)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UI-01 | Onboarding screen: full-screen conversational flow with the interview agent, ending in a profile confirmation summary | SSE EventSource from `POST /onboarding/start`; TanStack Query mutation triggers stream; Zustand tracks onboarding state |
| UI-02 | Today/Home screen: today's session card with actions (Start Session, Export to Zwift disabled, Mark Done, Mark Missed); compact next-few-days view; TSB form chip only after 28+ days | TanStack Query fetches sessions; pmc_history.tss_display_ready gates TSB chip |
| UI-03 | Agenda screen: scrollable list grouped by week; intensity shown via zone colors from PRD | TanStack Query for sessions list; zone color tokens from design system |
| UI-04 | History screen: past rides with compliance; CTL sparkline after 28+ days; tap-through to ride detail | FIT upload drop zone; TanStack Query for rides + pmc_history |
| UI-05 | During-Session screen: large-font stepper, current/next/later steps, static placeholder timer in Phase 4 | Static component; Phase 5 adds live timer |
| UI-06 | Chat screen: persistent conversation with agent; adaptation reasoning appears here | SSE EventSource from `GET /chat/stream`; useEffect-based stream consumer |
| UI-07 | Navigation: mobile bottom tab bar (Today/Agenda/History/Chat); desktop left sidebar | React Router v7 layout route; Tailwind responsive breakpoints |
| UI-08 | Design system: Inter, blue-6 primary, neutrals per PRD; no pure black; no em dashes | CSS custom properties via Tailwind v4 @theme directive |
| UI-09 | PWA: installable on iOS/Android; offline during-session view; iOS install instructional banner | vite-plugin-pwa with workbox; custom iOS install banner component |
| UI-10 | Light mode only for MVP; no dark mode | No dark: variant classes; use --bg #F9F9FA not #000000 |
| CAL-01 | Planned sessions pushed to Google Calendar with session detail in event body | `GET /calendar/auth` + `GET /calendar/callback`; event body built from sessions row |
| CAL-02 | Plan changes trigger calendar event update/move/delete | calendar_event_id stored on sessions row; update/delete on adaptation events |
| CAL-03 | Production OAuth credentials; refresh token health checked before every call; tokens encrypted in DB | Fernet encryption; users.google_tokens jsonb column already exists |
| CAL-04 | Calendar sync failures surface gracefully; do not disrupt plan or chat | sonner toast on failure; fire-and-forget calendar calls in background tasks |
</phase_requirements>

---

## Summary

Phase 4 is a full-stack greenfield phase: the FastAPI backend exists and is fully built; Phase 4 adds a React PWA frontend wired to those endpoints. There is zero frontend code in the repo today. Everything in `src/` must be created from scratch.

The phase has two distinct tracks that can develop in parallel after Wave 0: the **React PWA** (all 6 screens + navigation + PWA manifest + Supabase Auth integration) and the **Google Calendar integration** (new FastAPI routes + DB migration + calendar sync hooks). A third concern cutting across both tracks is the **FastAPI JWT middleware** that was deferred from Phase 3 and must land in Phase 4 before any endpoint is exposed publicly.

The existing backend exposes all data the frontend needs: SSE streams via `GET /chat/stream` and `POST /onboarding/start`, session data via the `sessions` and `plans` tables (accessed via Supabase directly or a new `GET /sessions` endpoint the planner should add), ride history via `rides`, PMC data via `pmc_history`, and adaptation history via `GET /adaptations/`. The frontend uses `@supabase/supabase-js` exclusively for auth session management; all other data goes through FastAPI with the JWT in the Authorization header.

**Primary recommendation:** Scaffold the Vite + React + Tailwind v4 + shadcn/ui project first (Wave 0), establish the design token foundation and routing skeleton, then implement auth + first-run gate before any screen content. Google Calendar routes can be built in parallel with the UI screens after Wave 0.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Auth session management | Browser/Client | FastAPI (JWT validation) | Supabase Auth handles magic link flow and issues JWTs; FastAPI validates on each request |
| Screen rendering | Browser/Client (Vite/React SPA) | — | PWA is a client-side SPA deployed to Vercel CDN |
| Server-side data | API/Backend (FastAPI) | Supabase (Postgres + Storage) | All physiological data and coaching logic lives server-side |
| Google Calendar OAuth | API/Backend (FastAPI) | Browser (redirect initiation) | Tokens must never touch the browser; server-side redirect flow per D-05 |
| Calendar event sync | API/Backend (FastAPI) | — | Background task after plan changes; not triggered from browser |
| PWA service worker | Browser/Client | CDN (Vercel) | Workbox pre-caches the app shell; Vercel serves static assets |
| Offline during-session | Browser/Client (service worker cache) | — | Session plan data cached at session start; no network required |
| Navigation state | Browser/Client (React Router v7) | Zustand (active tab) | React Router owns routing; Zustand owns UI state like active tab highlight |
| Toast notifications | Browser/Client (Sonner) | — | Sonner Toaster at app root; triggered from mutation callbacks |

---

## Codebase Audit

### What Exists (Backend — Phases 1-3)

| Module | Path | Phase 4 Usage |
|--------|------|---------------|
| FastAPI app | `api/main.py` | Add `/calendar` router and JWT middleware here |
| SSE chat endpoint | `api/routes/chat.py` | Frontend EventSource consumer reads from `GET /chat/stream?conversation_id=&user_id=` |
| Onboarding start | `api/routes/onboarding.py` | Frontend `POST /onboarding/start` + SSE stream drives UI-01 |
| FIT upload | `api/routes/rides.py` | Frontend `POST /rides/upload` multipart from History screen (D-07) |
| Adaptations | `api/routes/adaptations.py` | Frontend reads `GET /adaptations/` for the Chat screen adaptation log |
| Supabase singleton pattern | All route modules | Reuse `_get_async_supabase()` pattern in new calendar route |
| DB schema | `supabase/migrations/` | `users.google_tokens` already exists; need new migration for `sessions.calendar_event_id` and `sessions.tss_target` |

**DB schema gaps for Phase 4:**
- `sessions` is missing `tss_target` (referenced in adaptations.py but not in the original migration — appears to be a naming inconsistency: `adaptations.py` queries `tss_target` but migration has no such column)
- `sessions` needs `calendar_event_id text` for CAL-02 update/delete
- `rides` needs `compliance_pct numeric` (used in rides.py but not in migration)

### What Does Not Exist (Frontend — all new)

- No `frontend/` or `src/` directory exists. The entire React app must be scaffolded.
- No `package.json` at root (Python project). Frontend scaffold goes in a `frontend/` subdirectory.
- No Vite config, Tailwind config, shadcn/ui setup, or test runner.

### Backend Security TODOs (Must Ship in Phase 4)

Every route module has a `# SECURITY TODO (Phase 4 — MUST fix before public exposure)` comment. These are blocking:
- `chat.py`: `user_id` is a query param with no auth — replace with JWT dependency
- `onboarding.py`: `user_id` is request body with no auth — replace with JWT dependency
- `rides.py`: `user_id` is form data with no auth — replace with JWT dependency
- `adaptations.py`: `user_id` is query param/body with no auth — replace with JWT dependency

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| React | 19.1.x | UI component tree | Current stable; required for shadcn/ui v4 compat |
| Vite | 6.x | Build tool | Official post-CRA recommendation |
| TypeScript | 5.x | Type safety | Non-negotiable for data-heavy app |
| Tailwind CSS | 4.x | Utility CSS | v4 CSS-first setup; @tailwindcss/vite plugin; no postcss config needed |
| shadcn/ui | latest (canary) | Component primitives | Tailwind v4 + React 19 confirmed |
| React Router | 8.0.1 | Routing | v7 — `createBrowserRouter` + nested layout routes |
| Zustand | 5.0.14 | Client state | Minimal boilerplate for UI state |
| TanStack Query | 5.101.0 | Server state | REST queries + SSE stream management |
| @supabase/supabase-js | 2.108.2 | Auth only | Magic link, session management; NOT used for data queries |
| sonner | 2.0.7 | Toasts | shadcn/ui migrated to sonner; used for sync failures and upload success |
| recharts | 3.8.1 | CTL sparkline | Lightweight, React-native; used for History sparkline after 28+ days |
| vite-plugin-pwa | 1.3.0 | PWA service worker | Zero-config workbox; handles iOS icons, navigateFallback |

[VERIFIED: npm registry] — versions from `npm view` run against current registry.

### Supporting (Backend additions)

| Library | Purpose | Notes |
|---------|---------|-------|
| google-api-python-client | Calendar API client | Official Google Python client; `build('calendar', 'v3', credentials=creds)` |
| google-auth-oauthlib | OAuth2 web server flow | `Flow.from_client_secrets_file()`; handles code exchange |
| google-auth-httplib2 | HTTP transport for google-auth | Required transport adapter |
| cryptography (Fernet) | Token encryption at app layer | Symmetric encryption for `google_tokens` jsonb in DB |
| PyJWT | Supabase JWT verification | Use `jwt.decode(token, supabase_jwt_secret, algorithms=['HS256'], audience='authenticated')` |

[ASSUMED] — Python package names and APIs confirmed from official Google documentation and community patterns, but not verified against PyPI registry in this session.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| TanStack Query for SSE | raw EventSource + useState | Query gives cache invalidation, refetch, error states; raw is simpler but no cache |
| Zustand | React Context | Zustand avoids prop drilling and context re-render issues; preferred for cross-screen state |
| shadcn/ui | Radix UI directly | shadcn/ui is Radix + Tailwind pre-composed; saves component wiring time |
| PyJWT | python-jose | Both work for HS256; PyJWT is lighter; CLAUDE.md lists both as options |

**Installation (frontend):**
```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install react-router @tanstack/react-query zustand @supabase/supabase-js sonner recharts vite-plugin-pwa
npx shadcn@canary init
```

**Installation (backend additions):**
```bash
pip install google-api-python-client google-auth-oauthlib google-auth-httplib2 cryptography PyJWT
```

---

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| react | npm | 10+ yrs | 145M/wk | github.com/facebook/react | OK (flagged too-new by seam — active release cycle, not suspicious) | Approved |
| vite | npm | 4+ yrs | 140M/wk | github.com/vitejs/vite | OK (too-new flag = active release) | Approved |
| react-router | npm | 10+ yrs | 48M/wk | github.com/remix-run/react-router | OK | Approved |
| @tanstack/react-query | npm | 4+ yrs | 57M/wk | github.com/TanStack/query | OK | Approved |
| zustand | npm | 5+ yrs | 42M/wk | github.com/pmndrs/zustand | OK | Approved |
| @supabase/supabase-js | npm | 3+ yrs | 21M/wk | github.com/supabase/supabase-js | OK | Approved |
| tailwindcss | npm | 6+ yrs | 120M/wk | github.com/tailwindlabs/tailwindcss | OK | Approved |
| @tailwindcss/vite | npm | 1+ yr | 37M/wk | github.com/tailwindlabs/tailwindcss | OK | Approved |
| vite-plugin-pwa | npm | 3+ yrs | 3.4M/wk | github.com/vite-pwa/vite-plugin-pwa | OK | Approved |
| sonner | npm | 2+ yrs | 45M/wk | github.com/emilkowalski/sonner | OK | Approved |
| recharts | npm | 7+ yrs | 52M/wk | github.com/recharts/recharts | OK | Approved |
| google-api-python-client | PyPI | 10+ yrs | official | github.com/googleapis | OK [ASSUMED] | Approved |
| google-auth-oauthlib | PyPI | 7+ yrs | official | github.com/googleapis | OK [ASSUMED] | Approved |
| cryptography | PyPI | 10+ yrs | official | github.com/pyca/cryptography | OK [ASSUMED] | Approved |
| PyJWT | PyPI | 10+ yrs | official | github.com/jpadilla/pyjwt | OK [ASSUMED] | Approved |

**Packages removed due to SLOP verdict:** none

**Packages flagged as suspicious SUS:** The seam flagged most packages as "too-new" because of recent patch releases — not because of any legitimacy concern. All have massive download volumes, official GitHub repos from known organizations, and years of history. Treat all as approved.

---

## Architecture Patterns

### System Architecture Diagram

```
Browser (React SPA / PWA)
│
├── Auth Layer
│   └── @supabase/supabase-js → Supabase Auth
│       signInWithOtp(email) → magic link email
│       onAuthStateChange → session.access_token (JWT)
│
├── HTTP Layer (all API calls carry Authorization: Bearer <JWT>)
│   └── TanStack Query + fetch → FastAPI
│       GET /sessions/today, GET /sessions/upcoming
│       GET /rides/, GET /pmc_history/latest
│       GET /adaptations/
│       POST /onboarding/start (SSE stream)
│       GET /chat/stream (SSE stream)
│       POST /rides/upload (multipart)
│       POST /adaptations/sessions/{id}/missed
│       GET /calendar/auth (redirect flow)
│       GET /calendar/settings (connected status)
│       POST /calendar/disconnect
│
├── Screen Layer (React Router v7 nested routes)
│   / (RootLayout: nav + auth gate)
│   ├── / (Today)
│   ├── /agenda (Agenda)
│   ├── /history (History)
│   ├── /chat (Chat)
│   ├── /session (During-Session static)
│   ├── /onboarding (full-screen, no nav)
│   └── /settings (Settings)
│
└── PWA Layer
    vite-plugin-pwa → service worker
    Pre-caches app shell
    Offline route: /session reads cached session data
    iOS install banner: custom component on first visit

FastAPI Backend (Railway)
│
├── JWT Middleware (NEW Phase 4)
│   HTTPBearer → PyJWT.decode(token, SUPABASE_JWT_SECRET, HS256, audience='authenticated')
│   → user_id extracted and injected as Depends(get_current_user)
│
├── Existing Routes (now auth-protected)
│   /chat/stream, /onboarding/start, /rides/upload, /adaptations/*
│
└── New Calendar Routes (Phase 4)
    GET /calendar/auth → build Google auth URL → 302 redirect to Google
    GET /calendar/callback → exchange code → encrypt tokens → store in users.google_tokens → redirect to /settings
    GET /calendar/settings → check token health → return {connected: bool}
    POST /calendar/disconnect → delete google_tokens

Calendar Sync Hooks (Background Tasks)
    After plan generation (generate_plan tool) → push all sessions to Google Calendar
    After adaptation (micro/macro replan) → update/delete affected events
    Uses sessions.calendar_event_id for idempotent update/delete
```

### Recommended Project Structure

```
frontend/
├── index.html
├── package.json
├── vite.config.ts           # VitePWA + @tailwindcss/vite plugins
├── tsconfig.json
├── src/
│   ├── main.tsx             # React root, QueryClientProvider, RouterProvider, Toaster
│   ├── router.tsx           # createBrowserRouter with all routes
│   ├── index.css            # @import "tailwindcss"; @theme { --color-primary: ... }
│   ├── lib/
│   │   ├── supabase.ts      # createClient singleton
│   │   └── api.ts           # fetch wrapper that injects Authorization: Bearer JWT
│   ├── stores/
│   │   ├── authStore.ts     # Zustand: { user, session, isLoading }
│   │   └── uiStore.ts       # Zustand: { activeTab, iOSBannerDismissed }
│   ├── hooks/
│   │   ├── useAuth.ts       # wraps authStore + supabase.auth.onAuthStateChange
│   │   ├── useSSEStream.ts  # EventSource consumer → token accumulation
│   │   └── useCalendarStatus.ts
│   ├── components/
│   │   ├── nav/
│   │   │   ├── BottomTabBar.tsx    # mobile 4-tab bar
│   │   │   └── DesktopSidebar.tsx  # desktop left sidebar
│   │   ├── session/
│   │   │   ├── SessionCard.tsx     # Today session card
│   │   │   └── SessionStepList.tsx # During-session stepper
│   │   ├── chat/
│   │   │   ├── ChatBubble.tsx
│   │   │   └── ChatInput.tsx
│   │   ├── history/
│   │   │   ├── FitUploadZone.tsx
│   │   │   └── RideRow.tsx
│   │   ├── pwa/
│   │   │   └── IOSInstallBanner.tsx
│   │   └── ui/              # shadcn/ui components (auto-generated by npx shadcn add)
│   └── screens/
│       ├── OnboardingScreen.tsx
│       ├── TodayScreen.tsx
│       ├── AgendaScreen.tsx
│       ├── HistoryScreen.tsx
│       ├── DuringSessionScreen.tsx
│       ├── ChatScreen.tsx
│       └── SettingsScreen.tsx
├── public/
│   ├── apple-touch-icon.png    # 180x180 — required for iOS PWA
│   ├── pwa-192x192.png
│   └── pwa-512x512.png
```

### Pattern 1: Supabase Auth + FastAPI JWT Guard

Frontend session management:
```typescript
// src/lib/supabase.ts
import { createClient } from '@supabase/supabase-js'
export const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY
)

// src/hooks/useAuth.ts
// [ASSUMED] — pattern from supabase docs and community articles
useEffect(() => {
  const { data: { subscription } } = supabase.auth.onAuthStateChange(
    async (event, session) => {
      authStore.setState({ session, user: session?.user ?? null, isLoading: false })
    }
  )
  return () => subscription.unsubscribe()
}, [])

// Magic link send:
await supabase.auth.signInWithOtp({ email })

// All API calls:
const { data: { session } } = await supabase.auth.getSession()
fetch('/api/sessions/today', {
  headers: { Authorization: `Bearer ${session.access_token}` }
})
```

FastAPI JWT middleware:
```python
# api/auth.py (new file)
# [CITED: dev.to/zwx00/validating-a-supabase-jwt-locally-with-python-and-fastapi-59jf]
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

SUPABASE_JWT_SECRET = os.environ["SUPABASE_JWT_SECRET"]

async def get_current_user(
    cred: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False)),
) -> dict:
    if cred is None:
        raise HTTPException(status_code=401)
    try:
        payload = jwt.decode(
            cred.credentials,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
        return {"user_id": payload["sub"], "email": payload["email"]}
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# Usage on any route:
@router.get("/stream")
async def chat_stream(
    conversation_id: str = Query(...),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    ...
```

### Pattern 2: React Router v7 Layout with Auth Gate

```typescript
// src/router.tsx
// [ASSUMED] — based on React Router v7 createBrowserRouter docs
import { createBrowserRouter, Outlet, Navigate } from 'react-router'
import { useAuthStore } from './stores/authStore'

function AuthGate() {
  const { session, isLoading } = useAuthStore()
  if (isLoading) return <Spinner />
  if (!session) return <Navigate to="/login" replace />
  return <Outlet />
}

function FirstRunGate() {
  // Check if profile exists; redirect to /onboarding if not
  const { data: profile } = useQuery({ queryKey: ['profile'], queryFn: fetchProfile })
  if (!profile) return <Navigate to="/onboarding" replace />
  return <Outlet />
}

export const router = createBrowserRouter([
  { path: '/login', Component: LoginScreen },
  { path: '/onboarding', Component: OnboardingScreen },  // no nav
  {
    path: '/',
    Component: AuthGate,
    children: [{
      path: '/',
      Component: FirstRunGate,
      children: [{
        Component: AppLayout,  // nav + outlet
        children: [
          { index: true, Component: TodayScreen },
          { path: 'agenda', Component: AgendaScreen },
          { path: 'history', Component: HistoryScreen },
          { path: 'chat', Component: ChatScreen },
          { path: 'session', Component: DuringSessionScreen },
          { path: 'settings', Component: SettingsScreen },
        ]
      }]
    }]
  }
])
```

### Pattern 3: SSE Chat Stream Consumer

The existing backend `GET /chat/stream` and `POST /onboarding/start` return SSE streams. TanStack Query is not ideal for SSE streaming — use a custom hook with EventSource directly:

```typescript
// src/hooks/useSSEStream.ts
// [ASSUMED] — standard EventSource pattern; not from official docs
export function useSSEStream(url: string | null) {
  const [tokens, setTokens] = useState<string[]>([])
  const [isDone, setIsDone] = useState(false)

  useEffect(() => {
    if (!url) return
    const es = new EventSource(url)
    es.addEventListener('token', (e) => {
      const { text } = JSON.parse(e.data)
      setTokens(prev => [...prev, text])
    })
    es.addEventListener('done', () => {
      setIsDone(true)
      es.close()
    })
    es.addEventListener('error', () => es.close())
    return () => es.close()
  }, [url])

  return { content: tokens.join(''), isDone }
}
```

Note: EventSource does not support custom headers, so the JWT cannot be passed via Authorization header. The SSE endpoints must accept the JWT via query param (`?token=...`) or use a pre-flight POST to establish a session token pattern. This is an architecture decision the planner must address — query param is simplest but leaks JWT in server logs.

### Pattern 4: Google Calendar OAuth2 Server-Side Flow

```python
# api/routes/calendar.py (new file)
# [CITED: developers.google.com/identity/protocols/oauth2/web-server]
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from cryptography.fernet import Fernet

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
FERNET_KEY = os.environ["CALENDAR_FERNET_KEY"]  # generate with Fernet.generate_key()
_fernet = Fernet(FERNET_KEY)

@router.get("/auth")
async def calendar_auth(current_user: dict = Depends(get_current_user)):
    flow = Flow.from_client_config(
        client_config=GOOGLE_CLIENT_CONFIG,  # loaded from env vars
        scopes=SCOPES,
        redirect_uri=f"{BACKEND_BASE_URL}/calendar/callback",
    )
    auth_url, state = flow.authorization_url(
        access_type="offline",
        prompt="consent",  # required to get refresh_token on repeat auth
        include_granted_scopes="true",
    )
    # Store state in Supabase keyed to user_id for CSRF check at callback
    ...
    return RedirectResponse(url=auth_url)

@router.get("/callback")
async def calendar_callback(code: str, state: str):
    # Verify state matches stored state for this user
    flow.fetch_token(code=code)
    credentials = flow.credentials
    encrypted = _fernet.encrypt(credentials.to_json().encode())
    # Upsert encrypted tokens to users.google_tokens
    ...
    return RedirectResponse(url=f"{FRONTEND_URL}/settings?calendar=connected")

# Calendar sync helper (called after plan changes):
async def push_session_to_calendar(user_id: str, session: dict) -> str | None:
    creds = _load_credentials(user_id)  # decrypt from DB, auto-refresh
    service = build("calendar", "v3", credentials=creds)
    event_body = {
        "summary": f"PacerAI: {session['objective']}",
        "description": _format_session_description(session),
        "start": {"date": session["scheduled_date"]},
        "end": {"date": session["scheduled_date"]},
    }
    result = service.events().insert(calendarId="primary", body=event_body).execute()
    return result.get("id")  # store this as sessions.calendar_event_id

async def update_calendar_event(user_id: str, event_id: str, session: dict) -> None:
    creds = _load_credentials(user_id)
    service = build("calendar", "v3", credentials=creds)
    service.events().update(
        calendarId="primary", eventId=event_id, body=_build_event_body(session)
    ).execute()

async def delete_calendar_event(user_id: str, event_id: str) -> None:
    creds = _load_credentials(user_id)
    service = build("calendar", "v3", credentials=creds)
    service.events().delete(calendarId="primary", eventId=event_id).execute()
```

### Pattern 5: Design Token Foundation (Tailwind v4)

```css
/* src/index.css */
/* [CITED: ui.shadcn.com/docs/tailwind-v4] */
@import "tailwindcss";

@theme {
  --color-primary: #228BE6;      /* blue-6: fills, buttons, large text */
  --color-primary-dark: #1B73C0; /* blue-7: small blue text (4.95:1) */
  --color-ink: #1A2230;          /* primary text */
  --color-ink-2: #5F646E;        /* secondary text */
  --color-ink-3: #888C93;        /* muted, large text only */
  --color-line: #DFE0E2;
  --color-line-2: #EDEDEE;
  --color-surface: #FFFFFF;
  --color-bg: #F9F9FA;
  --color-bg-2: #F6F6F7;
  --color-warm: #FF8A5C;
  --color-zone-recovery: #2B8A5B;
  --color-zone-endurance: #228BE6;
  --color-zone-tempo: #F0A030;
  --color-zone-threshold: #E8590C;
  --color-zone-vo2: #C92A2A;

  --font-family-sans: "Inter", ui-sans-serif, system-ui, sans-serif;
}
```

### Pattern 6: iOS PWA Install Banner

```typescript
// src/components/pwa/IOSInstallBanner.tsx
// [ASSUMED] — standard iOS PWA detection pattern
function isIOS(): boolean {
  return /iphone|ipad|ipod/i.test(navigator.userAgent)
}
function isInStandaloneMode(): boolean {
  return window.matchMedia('(display-mode: standalone)').matches
}

export function IOSInstallBanner() {
  const [show, setShow] = useState(false)

  useEffect(() => {
    const dismissed = localStorage.getItem('ios-banner-dismissed')
    if (isIOS() && !isInStandaloneMode() && !dismissed) {
      setShow(true)
    }
  }, [])

  if (!show) return null

  return (
    <div className="fixed bottom-16 inset-x-4 bg-surface border border-line rounded-xl p-4 shadow-lg z-50">
      <p className="text-sm text-ink">
        Install PacerAI: tap the Share button, then "Add to Home Screen".
      </p>
      <button onClick={() => {
        localStorage.setItem('ios-banner-dismissed', '1')
        setShow(false)
      }}>Dismiss</button>
    </div>
  )
}
```

### Pattern 7: vite-plugin-pwa Configuration

```typescript
// vite.config.ts
// [CITED: github.com/vite-pwa/vite-plugin-pwa]
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.ico', 'apple-touch-icon.png'],
      manifest: {
        name: 'PacerAI',
        short_name: 'PacerAI',
        theme_color: '#228BE6',
        background_color: '#F9F9FA',
        display: 'standalone',
        icons: [
          { src: 'pwa-192x192.png', sizes: '192x192', type: 'image/png' },
          { src: 'pwa-512x512.png', sizes: '512x512', type: 'image/png' },
        ],
      },
      workbox: {
        navigateFallback: '/index.html',
        runtimeCaching: [
          {
            urlPattern: /^https:\/\/.*\/api\/sessions\/session\/.*/i,
            handler: 'NetworkFirst',
            options: { cacheName: 'session-cache', expiration: { maxEntries: 5 } },
          },
        ],
      },
    }),
  ],
})
```

### Anti-Patterns to Avoid

- **EventSource + Authorization header:** EventSource does not support custom headers. JWT must be passed as a query param (`?token=`) or the backend must set a session cookie after a pre-flight auth. Do not try to use `fetch` with `ReadableStream` as a drop-in for EventSource — it works but adds complexity. Simplest path: pass JWT as query param for SSE endpoints only and add server-side logging suppression for that param.
- **`user_id` from form data/query params (pre-Phase 4 pattern):** Every route has a TODO to fix this. Do not add new routes using the old pattern. All Phase 4 routes use `Depends(get_current_user)`.
- **Storing Google tokens in browser storage:** Never put `google_tokens` in localStorage, sessionStorage, or React state. They live in Supabase Postgres only, encrypted with Fernet at rest.
- **Calling google-api-python-client from async FastAPI without thread offload:** `googleapiclient.discovery.build()` and service calls are synchronous. Wrap in `asyncio.to_thread()` in async routes (same pattern as fitdecode in rides.py).
- **Using `calendar` scope instead of `calendar.events`:** Request only `calendar.events` per least-privilege principle (Google's own recommendation).
- **TSB chip before 28+ days:** Never render the TSB chip or CTL sparkline without checking `pmc_history.tss_display_ready`. The field is set by `update_pmc` in sports_science/pmc.py and is `false` until 28 days.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JWT verification | Custom HMAC validation | PyJWT `jwt.decode()` with audience check | Handles expiry, signature, and claims atomically |
| Token encryption | Custom AES or XOR | `cryptography.fernet.Fernet` | Fernet is authenticated encryption; prevents ciphertext tampering |
| PWA service worker | Custom service worker JS | `vite-plugin-pwa` + Workbox | Pre-caching, update lifecycle, and manifest injection are complex; Workbox handles them |
| OAuth2 state/CSRF protection | UUID in memory | Session or Supabase row keyed to user | In-memory state dies on Railway restart; Supabase row survives |
| Google API auth refresh | Manual token refresh logic | `google.oauth2.credentials.Credentials` auto-refresh | google-auth handles expiry detection and refresh transparently |
| iOS install prompt | Device detection with complex logic | Custom hook with simple UA check + `display-mode` media query | Simple, no library needed; see Pattern 6 |
| Zone color rendering | Mapping type strings to hex in components | CSS custom property `--color-zone-*` applied via className | Single source of truth; no conditional rendering |
| FIT drag-and-drop | Custom drag event handlers | HTML5 `ondrop`/`ondragover` on a div | Sufficient for single-file upload; no library needed |
| Sparkline chart | SVG path calculation | `recharts` LineChart | Recharts handles responsive SVG; sparklines need responsive container |

---

## Common Pitfalls

### Pitfall 1: EventSource Cannot Send Authorization Headers

**What goes wrong:** Frontend tries to pass JWT via EventSource headers — EventSource API has no header support. Requests go to SSE endpoints without auth, hitting the JWT middleware and getting 401s.

**Why it happens:** The SSE pattern from Phase 3 used `user_id` as a query param (pre-auth). Phase 4 adds JWT middleware. EventSource is a browser primitive with no header API.

**How to avoid:** Pass the JWT as a query param (`?token=<jwt>`) for SSE endpoints specifically. In the JWT middleware, check both `Authorization: Bearer` header AND `?token=` query param. Suppress the token from server logs. Alternatively, implement a short-lived pre-auth endpoint that issues a one-use stream token and pass that instead.

### Pitfall 2: Google OAuth2 Refresh Token Only Sent Once

**What goes wrong:** The initial OAuth2 consent gives a refresh token. On subsequent re-authorizations (e.g., user disconnects and reconnects), Google does NOT re-send the refresh token unless `prompt='consent'` is included.

**Why it happens:** Google's OAuth2 server assumes the refresh token was persisted from the first consent.

**How to avoid:** Always include `prompt='consent'` in the authorization URL (implemented in Pattern 4 above). If `refresh_token` is missing from the stored credentials, force re-auth.

### Pitfall 3: `calendar_event_id` Missing from Sessions Table

**What goes wrong:** CAL-02 requires updating/deleting calendar events when the plan changes. Without `sessions.calendar_event_id`, there is no way to find the Google Calendar event to update.

**Why it happens:** The Phase 3 schema migration does not include `calendar_event_id` because Google Calendar was deferred.

**How to avoid:** Phase 4 must include a DB migration (0003_phase4_schema.sql) that adds `calendar_event_id text` to `sessions` and `rides.compliance_pct numeric`. Also add any other missing columns (`sessions.tss_target` — referenced in adaptations.py but not in the schema).

### Pitfall 4: `google-api-python-client` Sync Calls in Async FastAPI

**What goes wrong:** `service.events().insert().execute()` blocks the event loop, causing timeout issues under load.

**Why it happens:** `google-api-python-client` is built on the synchronous `httplib2` library.

**How to avoid:** Always wrap Calendar API calls in `await asyncio.to_thread(...)`. Same pattern used in rides.py for fitdecode (`asyncio.to_thread(parse_fit_file, ...)`).

### Pitfall 5: iOS PWA Banner Shown on Desktop Safari / Non-iOS

**What goes wrong:** The iOS install banner appears in Safari on Mac or other non-iOS browsers, cluttering the desktop UI.

**Why it happens:** UserAgent string checks are imprecise.

**How to avoid:** Check both `isIOS()` (UA string) AND `'ontouchstart' in window` to distinguish mobile iOS from Mac Safari. Show the banner only when both are true and the app is not already in standalone mode.

### Pitfall 6: Supabase JWT Secret vs. Anon Key

**What goes wrong:** Developer uses `SUPABASE_ANON_KEY` (public key) instead of `SUPABASE_JWT_SECRET` for JWT verification. The anon key is not the HMAC secret.

**Why it happens:** Confusion between Supabase's two keys. The anon key is for Supabase JS client; the JWT secret is in Project Settings > API > JWT Settings.

**How to avoid:** Add `SUPABASE_JWT_SECRET` to the `.env` file explicitly. It is a separate secret from `SUPABASE_ANON_KEY` and `SUPABASE_SERVICE_ROLE_KEY`. The JWT decode call uses `SUPABASE_JWT_SECRET` with HS256 and audience `"authenticated"`.

### Pitfall 7: Tailwind v4 CSS Variable Naming vs. Tailwind v3

**What goes wrong:** Copy-pasting v3 Tailwind config patterns into a v4 project fails — v4 uses `@theme` directive in CSS, not `tailwind.config.js`.

**Why it happens:** Most online examples are v3. shadcn/ui documentation has both v3 and v4 paths.

**How to avoid:** Use `npx shadcn@canary init` (not `npx shadcn-ui init`) which detects v4 and generates the correct CSS-based theme. Verify with `--css-variables` flag set to true in `components.json`.

### Pitfall 8: `sessions` Table Column Name Inconsistency

**What goes wrong:** `adaptations.py` queries `sessions.tss_target` and `sessions.duration_minutes`, but the Phase 3 migration added columns with different names (`sessions.rpe_target`, `sessions.duration_mins` from the original Phase 1 migration). This will cause silent failures when adaptations run.

**Why it happens:** Column names diverged between the migration SQL and the Python code.

**How to avoid:** The Phase 4 DB migration must reconcile these: either rename existing columns or add aliases. Audit the exact column names before writing any new queries against `sessions`.

---

## Runtime State Inventory

> Greenfield frontend phase — no rename/refactor in scope. This section documents the runtime state the FRONTEND must be aware of from prior phases.

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | Supabase: users, profiles, sessions, rides, pmc_history, conversations, messages, capability_gaps, plans, adaptations tables | Frontend queries via FastAPI; no migration needed for reads |
| Live service config | Supabase project linked (supabase/.temp/linked-project.json) | Phase 4 migration requires `supabase db push --linked --yes` |
| OS-registered state | None | None |
| Secrets/env vars | SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_ANON_KEY exist; SUPABASE_JWT_SECRET must be added; GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, CALENDAR_FERNET_KEY must be added | Add new env vars to Railway and Vercel |
| Build artifacts | No frontend build artifacts exist (no frontend/ directory yet) | Scaffold frontend as Wave 0 task |

---

## DB Migration Required (Phase 4)

Migration `0003_phase4_schema.sql` must add:

```sql
-- sessions: calendar event tracking (CAL-02)
ALTER TABLE public.sessions
  ADD COLUMN calendar_event_id text;  -- Google Calendar event ID for update/delete

-- sessions: fix column naming inconsistency (adaptations.py uses tss_target, schema has no such column)
ALTER TABLE public.sessions
  ADD COLUMN tss_target numeric;       -- target TSS for session (used by adaptations signal detection)
ALTER TABLE public.sessions
  ADD COLUMN duration_minutes int;     -- alias for duration_mins (adaptations.py uses duration_minutes)

-- rides: compliance tracking column
ALTER TABLE public.rides
  ADD COLUMN compliance_pct numeric;   -- from validate_session_vs_actual (rides.py line 334)

-- conversations: context_data column for ride_debrief (rides.py line 386)
ALTER TABLE public.conversations
  ADD COLUMN context_data text;        -- JSON string for debrief context (rides.py uses it already)
```

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js | Frontend build | Yes | v25.9.0 | — |
| npm | Frontend deps | Yes | 11.12.1 | — |
| Python | Backend | Yes | 3.14.4 | — |
| Supabase CLI | DB migrations | Assumed (was used in Phase 3) | — | `npx supabase` |
| Google Cloud project + credentials | CAL-01 through CAL-04 | Unknown — must be set up | — | No fallback; blocks CAL-* requirements |
| SUPABASE_JWT_SECRET | JWT middleware | Not in env yet | — | Blocks auth; get from Supabase Project Settings |
| CALENDAR_FERNET_KEY | Token encryption | Not in env yet | — | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |

**Missing dependencies with no fallback:**
- Google Cloud project with OAuth2 credentials and Calendar API enabled (blocks CAL-01 through CAL-04). Must be created in Google Cloud Console before the calendar router can be tested. CAL-03 specifies production credentials, not Testing mode.

**Missing dependencies with fallback:**
- `SUPABASE_JWT_SECRET`: available in Supabase dashboard under Project Settings > API > JWT Settings. Required before JWT middleware can be tested but does not block frontend development.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Backend framework | pytest + pytest-asyncio (already configured in `pytest.ini`) |
| Frontend framework | Vitest + React Testing Library (Wave 0 install) |
| Backend quick run | `pytest tests/api/ -x -q` |
| Backend full suite | `pytest tests/ -x -q` |
| Frontend quick run | `cd frontend && npm test -- --run` |
| Frontend full suite | `cd frontend && npm test` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UI-01 | Onboarding SSE stream renders tokens in chat | integration | `pytest tests/api/test_onboarding.py -x` | Partial (test_onboarding.py exists but may need UI extension) |
| UI-02 | Today screen shows TSB chip only when tss_display_ready=true | unit | `cd frontend && npm test -- TodayScreen` | Wave 0 |
| UI-03 | Agenda renders zone colors from session.type | unit | `cd frontend && npm test -- AgendaScreen` | Wave 0 |
| UI-04 | FIT upload drop zone calls POST /rides/upload | integration | `pytest tests/api/test_rides.py -x` | Exists |
| UI-09 | iOS install banner shows on iOS, not on non-iOS | unit | `cd frontend && npm test -- IOSInstallBanner` | Wave 0 |
| CAL-01 | Calendar event created after session is saved to DB | integration | `pytest tests/api/test_calendar.py -x` | Wave 0 |
| CAL-02 | Calendar event updated when session.scheduled_date changes | integration | `pytest tests/api/test_calendar.py::test_event_update -x` | Wave 0 |
| CAL-03 | Tokens stored as encrypted bytes, not plaintext JSON | unit | `pytest tests/api/test_calendar.py::test_token_encryption -x` | Wave 0 |
| CAL-04 | Calendar failure does not cause 500 on adaptation endpoint | integration | `pytest tests/api/test_calendar.py::test_sync_failure_graceful -x` | Wave 0 |
| JWT | Unauthenticated request returns 401 | unit | `pytest tests/api/test_auth.py -x` | Wave 0 |

### Wave 0 Gaps

- [ ] `frontend/` — entire React app scaffold (Vite + React + TypeScript + Tailwind + shadcn/ui)
- [ ] `frontend/src/tests/` — Vitest + React Testing Library setup
- [ ] `tests/api/test_calendar.py` — calendar route tests (mock Google API calls)
- [ ] `tests/api/test_auth.py` — JWT middleware tests
- [ ] `api/auth.py` — JWT middleware module
- [ ] `api/routes/calendar.py` — Google Calendar routes
- [ ] `supabase/migrations/0003_phase4_schema.sql` — new columns

---

## Security Domain

### Applicable ASVS Categories (Level 1)

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | Yes | Supabase Auth (magic link) + PyJWT verification in FastAPI |
| V3 Session Management | Yes | Supabase JWT sessions; access token expires per Supabase defaults (1hr); refresh handled by @supabase/supabase-js |
| V4 Access Control | Yes | `Depends(get_current_user)` on all routes; user_id from JWT, never from request body |
| V5 Input Validation | Yes | Pydantic models on all POST bodies; UUID validation via `api/utils.validate_uuid` |
| V6 Cryptography | Yes | Fernet (AESGCM) for Google token encryption; never store tokens as plaintext |
| V9 Communications | Yes | HTTPS enforced via Vercel (frontend) + Railway (backend); HTTP to HTTPS redirect |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| JWT forgery / replay | Spoofing | HS256 signature + audience='authenticated' check; SUPABASE_JWT_SECRET never leaves server |
| OAuth2 state CSRF | Spoofing | State parameter stored in Supabase, verified at callback before token exchange |
| Google token theft | Info Disclosure | Fernet encryption at rest; never in browser; never in logs |
| EventSource JWT leakage in logs | Info Disclosure | Pass short-lived stream token via query param; suppress from application logs |
| Path traversal on file upload | Tampering | Already mitigated in rides.py (`_sanitize_filename`); no new upload endpoints in Phase 4 |
| XSS via chat message rendering | Tampering | Never use `dangerouslySetInnerHTML` for chat content; use textContent / React's safe rendering |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Python package names `google-api-python-client`, `google-auth-oauthlib`, `google-auth-httplib2`, `cryptography`, `PyJWT` are installable from PyPI | Standard Stack | Wrong package name; install fails |
| A2 | Supabase JWT secret is available under Project Settings > API > JWT Settings in the Supabase dashboard | Security Domain | Auth middleware cannot be tested without this value |
| A3 | `sessions.tss_target` and `sessions.duration_minutes` column names are what adaptations.py expects but are not in the Phase 3 migration SQL | DB Migration | If columns do exist under different names, the migration will conflict |
| A4 | Google Calendar OAuth2 production credentials (not Testing mode) requires the app to be published in Google Cloud Console with OAuth verification for external users | CAL-03 | If app stays in Testing mode, only listed test users can connect; blocks real user testing |
| A5 | `EventSource` in modern iOS Safari (17+) supports the standard EventSource API | UI-01, UI-06 | If Safari has EventSource bugs, SSE chat will be unreliable on iOS |
| A6 | Supabase `@supabase/supabase-js` v2.108.2 `signInWithOtp()` and `onAuthStateChange()` API is stable | Auth Layer | Supabase may have changed magic link API in recent releases |

---

## Open Questions (RESOLVED)

1. **EventSource + JWT authentication strategy**
   - What we know: EventSource cannot send Authorization headers. SSE endpoints currently accept `user_id` as a query param (insecure).
   - What's unclear: Whether to (a) pass JWT as `?token=` query param for SSE endpoints specifically, (b) implement a short-lived stream token pre-flight, or (c) switch SSE endpoints to cookies.
   - Recommendation: Use `?token=<jwt>` query param for SSE endpoints only (simplest). The JWT middleware can accept tokens from both header and query param. Add `token` to server log suppression list.

2. **sessions.tss_target column name conflict**
   - What we know: `adaptations.py` queries `sessions.tss_target` but the migration SQL has no such column (original schema has `sessions.targets jsonb`).
   - What's unclear: Whether `tss_target` was added informally or if this is a bug in the adaptation code.
   - Recommendation: Check the live Supabase schema via `supabase db diff` before writing the Phase 4 migration. Add `tss_target` if missing.

3. **Google Calendar event for all-day vs timed sessions**
   - What we know: `sessions.scheduled_date` is a `date` (not a `datetime`). Google Calendar events can be all-day (using `date`) or timed (using `dateTime`).
   - What's unclear: Should sessions appear as all-day events or as timed events at a specific time of day?
   - Recommendation: Use all-day events (`start: {date: session.scheduled_date}`) by default. Users can move them to specific times in Google Calendar. Timed events would require collecting preferred time-of-day, which is not in the interview.

4. **Google Cloud OAuth app verification timeline**
   - What we know: CAL-03 specifies production credentials, not Testing mode. External user OAuth apps must go through Google verification for sensitive scopes.
   - What's unclear: `calendar.events` scope may or may not require Google verification (it is not listed as a restricted scope, but this should be verified).
   - Recommendation: Create the OAuth2 app and set it to production mode during Phase 4 Wave 0. Test with the real account first. If verification is required before external users can authenticate, this blocks real user testing but not development testing.

---

## Sources

### Primary (MEDIUM confidence)
- [CITED: dev.to/zwx00 — Supabase JWT validation in FastAPI] — PyJWT decode pattern with SUPABASE_JWT_SECRET, HS256, audience='authenticated'
- [CITED: developers.google.com/identity/protocols/oauth2/web-server] — Server-side OAuth2 web flow steps, authorization URL parameters, token exchange
- [CITED: developers.google.com/workspace/calendar/api/auth] — Calendar API OAuth scopes: `calendar.events` for CRUD; `calendar` for full access; `calendar.events.readonly` for read only
- [CITED: googleapis.github.io/google-api-python-client/docs/dyn/calendar_v3.events.html] — events().insert(), .update(), .patch(), .delete() method signatures
- [CITED: ui.shadcn.com/docs/tailwind-v4] — Tailwind v4 @theme directive, CSS variables pattern

### Secondary (LOW confidence)
- WebSearch: React Router v7 createBrowserRouter, nested routes, lazy loading patterns
- WebSearch: iOS PWA install banner detection (UA string + display-mode media query)
- WebSearch: vite-plugin-pwa workbox configuration for offline support
- WebSearch: TanStack Query v5 EventSource SSE streaming patterns

### Tertiary (codebase verification)
- Codebase audit: full read of api/main.py, api/routes/*.py, supabase/migrations/*.sql — HIGH confidence on existing API surface, DB schema, and Phase 3 patterns
- npm registry: version verification via `npm view` for all frontend packages — HIGH confidence on package versions

---

## Metadata

**Confidence breakdown:**
- Standard stack (frontend): HIGH — npm registry verified
- Standard stack (backend additions): LOW — PyPI not queried; package names from docs
- Architecture patterns: MEDIUM — patterns from official docs + codebase analysis
- DB schema gaps: HIGH — verified by reading actual migration SQL
- Google Calendar OAuth2 flow: MEDIUM — steps from official Google docs; Python code patterns assumed
- JWT middleware pattern: MEDIUM — cited from community article matching official Supabase pattern
- Pitfalls: HIGH — derived from reading actual Phase 3 code + known OAuth2 gotchas

**Research date:** 2026-06-20
**Valid until:** 2026-07-20 (30 days — stable ecosystem; Google OAuth2 API is stable)

---

## RESEARCH COMPLETE
