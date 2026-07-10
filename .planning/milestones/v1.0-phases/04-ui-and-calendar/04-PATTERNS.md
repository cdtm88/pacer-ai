# Phase 4: UI and Calendar - Pattern Map

**Mapped:** 2026-06-20
**Files analyzed:** 28 new/modified files
**Analogs found:** 28 / 28 (all backend analogs; no frontend code exists)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `api/auth.py` | middleware | request-response | `api/utils.py` (HTTPException pattern) + RESEARCH.md Pattern 1 | role-match |
| `api/routes/calendar.py` | route/controller | request-response | `api/routes/adaptations.py` (router pattern, Supabase singleton) | role-match |
| `supabase/migrations/0003_phase4_schema.sql` | migration | — | `supabase/migrations/0002_phase3_schema.sql` | exact |
| `frontend/vite.config.ts` | config | — | RESEARCH.md Pattern 7 | no-analog |
| `frontend/src/index.css` | config | — | RESEARCH.md Pattern 5 | no-analog |
| `frontend/src/main.tsx` | config/provider | — | RESEARCH.md Pattern 2 | no-analog |
| `frontend/src/router.tsx` | route/config | — | RESEARCH.md Pattern 2 | no-analog |
| `frontend/src/lib/supabase.ts` | utility | — | RESEARCH.md Pattern 1 | no-analog |
| `frontend/src/lib/api.ts` | utility | request-response | `api/routes/rides.py` (fetch shape) | partial |
| `frontend/src/stores/authStore.ts` | store | event-driven | RESEARCH.md Pattern 1 | no-analog |
| `frontend/src/stores/uiStore.ts` | store | — | no analog | no-analog |
| `frontend/src/hooks/useAuth.ts` | hook | event-driven | RESEARCH.md Pattern 1 | no-analog |
| `frontend/src/hooks/useSSEStream.ts` | hook | streaming | `api/routes/_sse.py` (SSE event schema) | partial |
| `frontend/src/hooks/useCalendarStatus.ts` | hook | request-response | `api/routes/adaptations.py` (GET endpoint) | partial |
| `frontend/src/components/AppLayout.tsx` | component | — | `api/main.py` (router structure) | partial |
| `frontend/src/components/nav/BottomTabBar.tsx` | component | — | no analog | no-analog |
| `frontend/src/components/nav/DesktopSidebar.tsx` | component | — | no analog | no-analog |
| `frontend/src/components/session/SessionCard.tsx` | component | request-response | `api/routes/adaptations.py` (sessions schema) | partial |
| `frontend/src/components/session/TsbChip.tsx` | component | — | `supabase/migrations/0001_initial_schema.sql` (pmc_history.tss_display_ready) | partial |
| `frontend/src/components/session/ZoneChip.tsx` | component | — | RESEARCH.md Pattern 5 (zone color tokens) | no-analog |
| `frontend/src/components/session/SessionStepList.tsx` | component | — | no analog (Phase 4 static) | no-analog |
| `frontend/src/components/chat/ChatBubble.tsx` | component | streaming | `api/routes/_sse.py` (SSE event schema) | partial |
| `frontend/src/components/chat/ChatInput.tsx` | component | request-response | `api/routes/onboarding.py` (OnboardingStartRequest) | partial |
| `frontend/src/components/history/FitUploadZone.tsx` | component | file-I/O | `api/routes/rides.py` (`POST /rides/upload` multipart) | exact |
| `frontend/src/components/history/RideRow.tsx` | component | CRUD | `api/routes/rides.py` (rides schema) | partial |
| `frontend/src/components/history/CtlSparkline.tsx` | component | CRUD | `supabase/migrations/0001_initial_schema.sql` (pmc_history) | partial |
| `frontend/src/components/pwa/IOSInstallBanner.tsx` | component | — | RESEARCH.md Pattern 6 | no-analog |
| `frontend/src/components/settings/CalendarStatus.tsx` | component | request-response | `api/routes/calendar.py` (new; RESEARCH.md Pattern 4) | no-analog |
| `frontend/src/screens/OnboardingScreen.tsx` | screen | streaming | `api/routes/onboarding.py` (SSE + OnboardingStartRequest) | partial |
| `frontend/src/screens/TodayScreen.tsx` | screen | CRUD | `api/routes/adaptations.py` (sessions table shape) | partial |
| `frontend/src/screens/AgendaScreen.tsx` | screen | CRUD | `api/routes/adaptations.py` (sessions table shape) | partial |
| `frontend/src/screens/HistoryScreen.tsx` | screen | file-I/O + CRUD | `api/routes/rides.py` | role-match |
| `frontend/src/screens/DuringSessionScreen.tsx` | screen | — | no analog (static Phase 4) | no-analog |
| `frontend/src/screens/ChatScreen.tsx` | screen | streaming | `api/routes/chat.py` + `api/routes/_sse.py` | partial |
| `frontend/src/screens/SettingsScreen.tsx` | screen | request-response | `api/routes/adaptations.py` (GET pattern) | partial |
| `tests/api/test_auth.py` | test | — | `tests/api/test_rides.py` | role-match |
| `tests/api/test_calendar.py` | test | — | `tests/api/test_adaptations.py` | role-match |

---

## Pattern Assignments

### `api/auth.py` (middleware, request-response)

**Analog:** `api/utils.py` (HTTPException pattern) + RESEARCH.md Pattern 1

This is a new file. No existing auth middleware exists. Copy the HTTPException pattern from `api/utils.py` and implement JWT verification per RESEARCH.md Pattern 1.

**HTTPException pattern from `api/utils.py` (lines 17-23):**
```python
from fastapi import HTTPException

def validate_uuid(value: str, field: str = "id") -> None:
    if not _UUID_RE.match(value):
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_id", "detail": f"{field} must be a valid UUID"},
        )
```

**Supabase singleton pattern to reuse** (from `api/routes/rides.py` lines 53-75):
```python
_supabase_client: Optional[AsyncClient] = None

async def _get_async_supabase() -> AsyncClient:
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise EnvironmentError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set"
        )
    _supabase_client = await acreate_client(url, key)
    return _supabase_client
```

**JWT dependency to implement** (RESEARCH.md Pattern 1, lines 378-408):
```python
# api/auth.py (new file)
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

SUPABASE_JWT_SECRET = os.environ["SUPABASE_JWT_SECRET"]

async def get_current_user(
    cred: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False)),
    token: str | None = Query(None),  # SSE fallback: ?token= query param
) -> dict:
    raw = cred.credentials if cred else token
    if not raw:
        raise HTTPException(status_code=401)
    try:
        payload = jwt.decode(
            raw,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
        return {"user_id": payload["sub"], "email": payload["email"]}
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

**Note:** Accept JWT from both `Authorization: Bearer` header AND `?token=` query param. The query param path is exclusively for SSE endpoints where EventSource cannot send headers (RESEARCH.md Pitfall 1 and Anti-Pattern section).

**Apply `get_current_user` to all existing routes by replacing the pattern:**
- `chat.py` line 69: `user_id: str = Query(...)` -> `current_user: dict = Depends(get_current_user)`, then `user_id = current_user["user_id"]`
- `onboarding.py` line 235: `user_id = request.user_id` -> `user_id = current_user["user_id"]`
- `rides.py` line 438: `user_id: str = Form(...)` -> extract from `Depends(get_current_user)`
- `adaptations.py` lines 621, 647, 679: all `user_id` params -> `Depends(get_current_user)`

---

### `api/routes/calendar.py` (route/controller, request-response)

**Analog:** `api/routes/adaptations.py`

**Router + Supabase singleton pattern** (copy from `adaptations.py` lines 50-75):
```python
import os
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from supabase import AsyncClient, acreate_client

_supabase_client: Optional[AsyncClient] = None

async def _get_async_supabase() -> AsyncClient:
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise EnvironmentError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    _supabase_client = await acreate_client(url, key)
    return _supabase_client

router = APIRouter()
```

**Google Calendar async-wrap pattern** (RESEARCH.md Pitfall 4 + rides.py line 477):
```python
# Google API is synchronous -- always wrap in asyncio.to_thread (same as fitdecode in rides.py)
import asyncio

result = await asyncio.to_thread(
    service.events().insert(calendarId="primary", body=event_body).execute
)
```

**Calendar OAuth flow** (RESEARCH.md Pattern 4, lines 502-527):
```python
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from cryptography.fernet import Fernet

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
FERNET_KEY = os.environ["CALENDAR_FERNET_KEY"]
_fernet = Fernet(FERNET_KEY)

@router.get("/auth")
async def calendar_auth(current_user: dict = Depends(get_current_user)):
    flow = Flow.from_client_config(
        client_config=GOOGLE_CLIENT_CONFIG,
        scopes=SCOPES,
        redirect_uri=f"{BACKEND_BASE_URL}/calendar/callback",
    )
    auth_url, state = flow.authorization_url(
        access_type="offline",
        prompt="consent",  # required to get refresh_token on repeat auth (Pitfall 2)
        include_granted_scopes="true",
    )
    # Store state in Supabase keyed to user_id for CSRF check at callback
    return RedirectResponse(url=auth_url)

@router.get("/callback")
async def calendar_callback(code: str, state: str):
    # Verify state matches stored state for this user
    flow.fetch_token(code=code)
    credentials = flow.credentials
    encrypted = _fernet.encrypt(credentials.to_json().encode())
    # Upsert encrypted tokens to users.google_tokens
    return RedirectResponse(url=f"{FRONTEND_URL}/settings?calendar=connected")

@router.get("/settings")
async def calendar_settings(current_user: dict = Depends(get_current_user)) -> dict:
    # Return {"connected": bool}
    ...

@router.post("/disconnect")
async def calendar_disconnect(current_user: dict = Depends(get_current_user)) -> dict:
    # Delete google_tokens from users row
    ...
```

**Error handling pattern** (from `adaptations.py` lines 695-708):
```python
if not session_rows:
    raise HTTPException(
        status_code=404,
        detail={"error": "session_not_found", "detail": "..."},
    )
```

**Mount in `api/main.py`** (copy the include_router pattern from lines 36-48):
```python
from api.routes.calendar import router as calendar_router
app.include_router(calendar_router, prefix="/calendar", tags=["calendar"])
```

---

### `supabase/migrations/0003_phase4_schema.sql` (migration)

**Analog:** `supabase/migrations/0002_phase3_schema.sql`

**Pattern:** Every migration uses ALTER TABLE to add columns with constraints. FK constraints are checked against existing tables. RLS policies are added for new tables.

**From `0002_phase3_schema.sql` (ALTER pattern, lines 10-16):**
```sql
ALTER TABLE public.profiles
  ADD COLUMN back_status    text NOT NULL DEFAULT 'none'
                            CHECK (back_status IN ('none', 'mild', 'moderate')),
  ADD COLUMN weekly_hours   numeric,
  ADD COLUMN preferred_days text[],
  ADD COLUMN rpe_baseline   text,
  ADD COLUMN lthr_estimate  numeric;
```

**Phase 4 additions needed** (from RESEARCH.md DB Migration section):
```sql
-- sessions: calendar event tracking (CAL-02)
ALTER TABLE public.sessions
  ADD COLUMN calendar_event_id text;

-- sessions: fix column naming inconsistency
-- adaptations.py queries tss_target and duration_minutes; schema has rpe_target and duration_mins
ALTER TABLE public.sessions
  ADD COLUMN tss_target      numeric,
  ADD COLUMN duration_minutes int;

-- rides: compliance tracking (validate_session_vs_actual result)
ALTER TABLE public.rides
  ADD COLUMN compliance_pct numeric;

-- conversations: context_data for ride_debrief (rides.py line 386)
ALTER TABLE public.conversations
  ADD COLUMN context_data text;

-- rides: days_of_data needed by update_pmc (rides.py line 296)
-- (already tracked in pmc_history rows; no new column needed)
```

**Verify live schema before applying** using `supabase db diff` to avoid conflicts with RESEARCH.md Open Question 2.

---

### `frontend/vite.config.ts` (config)

**Analog:** RESEARCH.md Pattern 7

No existing Vite config in the repo. Copy directly from RESEARCH.md Pattern 7 (lines 624-659):
```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
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

---

### `frontend/src/index.css` (design token foundation)

**Analog:** RESEARCH.md Pattern 5 + UI-SPEC.md Color section

```css
@import "tailwindcss";

@theme {
  /* Primary blue scale */
  --color-blue-0: #E9F3FC;
  --color-blue-1: #CEE5FA;
  --color-blue-6: #228BE6;   /* primary fills, buttons, large text */
  --color-blue-7: #1B73C0;   /* small blue text (4.95:1 on white) */

  /* Neutrals */
  --color-ink:    #1A2230;
  --color-ink-2:  #5F646E;
  --color-ink-3:  #888C93;
  --color-line:   #DFE0E2;
  --color-line-2: #EDEDEE;
  --color-surface: #FFFFFF;
  --color-bg:     #F9F9FA;
  --color-bg-2:   #F6F6F7;

  /* Semantic */
  --color-good:      #2B8A5B;
  --color-warn:      #9A6700;
  --color-bad:       #C0341D;
  --color-amber:     #F0A030;

  /* Zone colors (must match PRD exactly) */
  --color-zone-recovery:  #2B8A5B;
  --color-zone-endurance: #228BE6;
  --color-zone-tempo:     #F0A030;
  --color-zone-threshold: #E8590C;
  --color-zone-vo2:       #C92A2A;

  --font-family-sans: "Inter", ui-sans-serif, system-ui, sans-serif;
}
```

---

### `frontend/src/lib/api.ts` (utility, request-response)

**Analog:** None in codebase. Derived from backend endpoint shapes.

This file wraps all `fetch` calls and injects the JWT Authorization header. The API surface is defined by the existing backend routes:

**Endpoint inventory** (from reading all route files):
```typescript
// All calls follow this base pattern:
const BASE = import.meta.env.VITE_API_URL  // Railway backend URL

async function apiFetch(path: string, options: RequestInit = {}) {
  const { data: { session } } = await supabase.auth.getSession()
  return fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${session?.access_token ?? ''}`,
      ...options.headers,
    },
  })
}

// Endpoints (derived from backend routes):
// GET  /health
// GET  /chat/stream?conversation_id=&token=<jwt>     (SSE -- use ?token= not header)
// POST /onboarding/start                             { user_id } -> SSE
// POST /rides/upload                                 multipart/form-data file + NO user_id (JWT)
// GET  /rides/                                       (new endpoint needed; see below)
// GET  /adaptations/?                                (JWT replaces user_id query param)
// POST /adaptations/check
// POST /adaptations/sessions/{id}/missed
// GET  /calendar/auth                                (redirect; use window.location.href)
// GET  /calendar/settings
// POST /calendar/disconnect
```

**Note:** `GET /sessions/today`, `GET /sessions/upcoming`, `GET /rides/`, and `GET /pmc_history/latest` do NOT currently exist as endpoints. The planner must add these to FastAPI (they query the tables that already exist).

---

### `frontend/src/hooks/useSSEStream.ts` (hook, streaming)

**Analog:** `api/routes/_sse.py` (SSE event schema definition)

The backend emits these SSE event types (`_sse.py` lines 11-23):
```
event: token         data: {"text": "..."}
event: tool_start    data: {"name": "...", "tool_use_id": "toolu_..."}
event: tool_result   data: {"tool_use_id": "...", "name": "...", "value": ...}
event: done          data: {}
event: error         data: {"code": "...", "message": "..."}
```

Frontend hook must handle all five event types (RESEARCH.md Pattern 3, lines 462-484):
```typescript
export function useSSEStream(url: string | null) {
  const [tokens, setTokens] = useState<string[]>([])
  const [isDone, setIsDone] = useState(false)
  const [error, setError] = useState<string | null>(null)

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
    es.addEventListener('error', (e) => {
      setError(JSON.parse((e as MessageEvent).data)?.message ?? 'Stream error')
      es.close()
    })
    return () => es.close()
  }, [url])

  return { content: tokens.join(''), isDone, error }
}
```

**Critical:** URL must include `?token=<jwt>` for auth (RESEARCH.md Anti-Patterns, Pitfall 1). The middleware must accept `?token=` in addition to the `Authorization` header.

---

### `frontend/src/components/history/FitUploadZone.tsx` (component, file-I/O)

**Analog:** `api/routes/rides.py` (upload endpoint definition)

**Backend contract** (`rides.py` lines 434-544):
- Endpoint: `POST /rides/upload`
- Content-type: `multipart/form-data`
- Fields: `file` (UploadFile), `user_id` removed in Phase 4 (JWT supplies it)
- Response: `{"ride_id": str, "status": "processing"}`
- Errors: 400 (bad UUID), 422 (file too large >25MB or too short <10min), 500 (DB error)

**Frontend upload pattern:**
```typescript
const formData = new FormData()
formData.append('file', file)
// Do NOT append user_id -- JWT middleware extracts it
const response = await fetch(`${BASE}/rides/upload`, {
  method: 'POST',
  headers: { Authorization: `Bearer ${jwt}` },
  // Do NOT set Content-Type -- browser sets multipart boundary automatically
  body: formData,
})
```

**Drag-and-drop without library** (RESEARCH.md "Don't Hand-Roll" section):
```typescript
<div
  onDragOver={(e) => e.preventDefault()}
  onDrop={(e) => {
    e.preventDefault()
    const file = e.dataTransfer.files[0]
    if (file) handleUpload(file)
  }}
  onClick={() => inputRef.current?.click()}
>
```

**Error response shape from rides.py** (lines 471-480):
```json
{ "detail": { "error": "fit_parse_failed", "detail": "File too short..." } }
```

---

### `frontend/src/screens/OnboardingScreen.tsx` (screen, streaming)

**Analog:** `api/routes/onboarding.py`

**Backend contract:**
- Endpoint: `POST /onboarding/start`
- Request body: `{"user_id": str}` -> PHASE 4 this becomes JWT; body may be empty
- Response: SSE stream (same event schema as chat)
- Conversation created automatically server-side; `conversation_id` returned in response headers or first SSE frame (planner must add)

**Onboarding system prompt reveals expected interview flow** (`onboarding.py` lines 61-87): 6 fields, confirmation gate "Here is what I have", then tool call sequence: save_profile -> progress_load -> calculate_hr_zones -> generate_plan.

**Profile confirmation detection:** Frontend must detect when agent response begins with "Here is what I have" and render the confirmation card + CTA change from text input to "This looks right" button.

**Post-confirmation redirect:** After the SSE stream ends following user confirmation, check if profile exists via `GET /profiles/` (new endpoint needed) and redirect to `/`.

---

### `frontend/src/screens/ChatScreen.tsx` (screen, streaming)

**Analog:** `api/routes/chat.py` + `api/routes/_sse.py`

**Backend contract** (`chat.py` lines 66-105):
- Endpoint: `GET /chat/stream?conversation_id=<uuid>&token=<jwt>`
- Response: SSE stream (token/tool_start/tool_result/done/error events)
- Conversation must exist before calling; create via `POST /conversations` (new endpoint needed)

**Opening message seed** (`chat.py` lines 60-63):
```python
_OPENING_MESSAGE = (
    "Hello! I'm ready to start my cycling training. "
    "What information do you need from me?"
)
```

**Conversation loading** (`onboarding.py` lines 141-178):
Messages are loaded from `messages` table: `role in ('user', 'assistant', 'tool')`, ordered by `created_at ASC`.

---

### `frontend/src/screens/TodayScreen.tsx` + `frontend/src/screens/AgendaScreen.tsx` (screens, CRUD)

**Analog:** `api/routes/adaptations.py` + `supabase/migrations/0001_initial_schema.sql` + `0002_phase3_schema.sql`

**Sessions table shape** (combined from both migrations):
```typescript
interface Session {
  id: string                // uuid
  user_id: string           // uuid
  objective: string | null
  structure: object | null  // jsonb
  targets: object | null    // jsonb (original)
  duration_mins: number | null   // original column name
  duration_minutes: number | null // added in 0003 migration
  status: 'planned' | 'completed' | 'skipped' | 'partial'
  scheduled_date: string    // date ISO "YYYY-MM-DD"
  plan_id: string | null
  type: 'endurance' | 'recovery' | 'strength' | 'interval' | null
  zone_targets: object | null
  power_targets: object | null
  week_num: number | null
  rpe_target: number | null
  tss_target: number | null  // added in 0003 migration
  calendar_event_id: string | null // added in 0003 migration
}
```

**TSB gate** (`supabase/migrations/0001_initial_schema.sql` line 96):
```typescript
// pmc_history.tss_display_ready field gates TSB chip and CTL sparkline
interface PmcHistory {
  tss_display_ready: boolean  // false until 28+ days of data
  ctl: number
  atl: number
  tsb: number
  date: string
}
// Never render TsbChip or CtlSparkline when tss_display_ready is false
```

**Mark missed endpoint** (`adaptations.py` lines 675-728):
```typescript
// POST /adaptations/sessions/{session_id}/missed
// Body: {} (JWT provides user_id in Phase 4)
// Response: { session_id, marked_missed, signals, scope, result }
```

---

### `frontend/src/screens/HistoryScreen.tsx` (screen, file-I/O + CRUD)

**Analog:** `api/routes/rides.py`

**Rides table shape** (both migrations combined):
```typescript
interface Ride {
  id: string
  user_id: string
  tss: number | null
  np_watts: number | null
  intensity_factor: number | null
  duration_secs: number
  raw_fit_path: string | null
  ride_date: string | null          // "YYYY-MM-DD"
  avg_power: number | null
  avg_hr: number | null
  avg_cadence: number | null
  ftp_used: number | null
  session_id: string | null
  compliance_pct: number | null     // added in 0003 migration
}
```

**Compliance chip logic** (derived from `rides.py` line 334 and `adaptations.py` lines 192-204):
```typescript
// compliance_pct < 60: "72% on target" in --color-warn
// compliance_pct >= 60 and < 90: "72% on target" in --color-warn
// compliance_pct >= 90: "95% on target" in --color-good
// compliance_pct null: "Unmatched" in --color-ink-3
```

---

### `frontend/src/screens/SettingsScreen.tsx` (screen, request-response)

**Analog:** `api/routes/adaptations.py` (GET endpoint pattern for calendar status)

**Calendar settings endpoint** (new, from RESEARCH.md Pattern 4):
```typescript
// GET /calendar/settings -> { connected: boolean }
// POST /calendar/disconnect -> {}
// GET /calendar/auth -> redirect (use window.location.href = `${BASE}/calendar/auth?token=<jwt>`)
```

**Supabase magic link re-send:**
```typescript
// NOT an API call -- use supabase.auth.signInWithOtp({ email }) directly
```

**Sign out:**
```typescript
await supabase.auth.signOut()
// Clear authStore; navigate to /login
```

---

### `tests/api/test_auth.py` (test)

**Analog:** `tests/api/test_rides.py` (AsyncClient pattern)

Read `tests/api/conftest.py` to get the `AsyncClient` fixture. Copy the request pattern from `test_rides.py` for unauthenticated 401 tests and authenticated success tests.

---

### `tests/api/test_calendar.py` (test)

**Analog:** `tests/api/test_adaptations.py`

**Pattern:** Mock the Google API calls using `unittest.mock.patch` or `respx`. Test:
- Token encryption (assert stored bytes != plaintext JSON)
- Calendar failure does not cause 500 on adaptation endpoint (background task isolation)
- OAuth callback stores encrypted tokens in users.google_tokens

---

## Shared Patterns

### Supabase Async Singleton (WR-04)
**Source:** `api/routes/rides.py` lines 53-75 (identical copy in `onboarding.py` and `adaptations.py`)
**Apply to:** `api/routes/calendar.py` (new)
```python
_supabase_client: Optional[AsyncClient] = None

async def _get_async_supabase() -> AsyncClient:
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise EnvironmentError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    _supabase_client = await acreate_client(url, key)
    return _supabase_client
```

### FastAPI HTTPException Error Shape
**Source:** `api/routes/rides.py` lines 471-475 and `api/utils.py` lines 18-23
**Apply to:** `api/routes/calendar.py`, `api/auth.py`
```python
raise HTTPException(
    status_code=4xx,
    detail={"error": "snake_case_code", "detail": "Human-readable message"},
)
```

### asyncio.to_thread for Sync Libraries
**Source:** `api/routes/rides.py` line 477
**Apply to:** `api/routes/calendar.py` (Google Calendar API calls)
```python
result = await asyncio.to_thread(parse_fit_file, file_bytes)
# -> calendar equivalent:
result = await asyncio.to_thread(service.events().insert(...).execute)
```

### StreamingResponse SSE Headers
**Source:** `api/routes/chat.py` lines 97-105 and `api/routes/onboarding.py` lines 250-258
**Apply to:** Any future SSE endpoint
```python
return StreamingResponse(
    sse_generator(messages, model, ...),
    media_type="text/event-stream",
    headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    },
)
```

### Pydantic Request Body Model
**Source:** `api/routes/onboarding.py` lines 53-55 and `api/routes/adaptations.py` lines 605-611
**Apply to:** All new POST endpoints in `api/routes/calendar.py`
```python
class MyRequest(BaseModel):
    """JSON body for POST /my-endpoint."""
    field: str
```

### JWT Auth Replacement Pattern
**Source:** `api/routes/adaptations.py` lines 619-640 (pattern to replace in all 4 existing routes)
**Apply to:** All existing routes as part of Phase 4 auth migration
```python
# BEFORE (Phase 3 insecure pattern):
@router.get("/")
async def list_adaptations(user_id: str = Query(...)):
    validate_uuid(user_id, "user_id")
    ...

# AFTER (Phase 4 pattern):
@router.get("/")
async def list_adaptations(current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    ...
```

---

## New Backend Endpoints Required (Frontend Cannot Function Without These)

These endpoints are implied by the frontend requirements but do not exist in the codebase:

| Endpoint | Method | Purpose | Add To |
|----------|--------|---------|--------|
| `/sessions/today` | GET | Today screen session card | new `api/routes/sessions.py` |
| `/sessions/upcoming` | GET | Today next-few-days strip + Agenda | new `api/routes/sessions.py` |
| `/rides/` | GET | History screen ride list | `api/routes/rides.py` |
| `/pmc_history/latest` | GET | TSB chip + CTL sparkline gate | new `api/routes/sessions.py` or `rides.py` |
| `/profiles/me` | GET | First-run gate check + Settings display | new `api/routes/sessions.py` or inline |
| `/conversations/` | POST | Create new chat conversation | `api/routes/chat.py` or onboarding |

Planner must add these in the same router file style as existing routes, using `get_current_user` Dependency (not query param) since they are Phase 4 routes.

---

## No Analog Found (Frontend-Specific, No Codebase Reference)

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `frontend/src/main.tsx` | provider/root | — | Greenfield React app; no frontend exists |
| `frontend/src/router.tsx` | route/config | — | Greenfield |
| `frontend/src/lib/supabase.ts` | utility | — | Greenfield; use RESEARCH.md Pattern 1 |
| `frontend/src/stores/authStore.ts` | store | event-driven | Greenfield; use Zustand 5 pattern |
| `frontend/src/stores/uiStore.ts` | store | — | Greenfield |
| `frontend/src/hooks/useAuth.ts` | hook | event-driven | Greenfield |
| `frontend/src/hooks/useCalendarStatus.ts` | hook | request-response | Greenfield |
| `frontend/src/components/nav/BottomTabBar.tsx` | component | — | Greenfield; UI-SPEC.md §Navigation |
| `frontend/src/components/nav/DesktopSidebar.tsx` | component | — | Greenfield; UI-SPEC.md §Navigation |
| `frontend/src/components/session/ZoneChip.tsx` | component | — | Greenfield; zone colors from index.css |
| `frontend/src/components/session/SessionStepList.tsx` | component | — | Greenfield; static Phase 4 layout |
| `frontend/src/components/pwa/IOSInstallBanner.tsx` | component | — | Greenfield; RESEARCH.md Pattern 6 |
| `frontend/src/components/settings/CalendarStatus.tsx` | component | — | Greenfield; UI-SPEC.md §Settings |
| `frontend/src/screens/DuringSessionScreen.tsx` | screen | — | Greenfield; static Phase 4; no behavior |

---

## Metadata

**Analog search scope:** `api/`, `api/routes/`, `supabase/migrations/`, `sports_science/`, `tests/api/`
**Files read:** 12 backend files + 4 planning docs
**Pattern extraction date:** 2026-06-20
