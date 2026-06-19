# Stack Research: PacerAI

**Researched:** 2026-06-19
**Overall confidence:** MEDIUM (cross-referenced multiple sources; library version claims verified against PyPI/npm where possible)

---

## Recommended Stack

### Frontend

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| React | 19.x | UI component tree | Current stable; required for shadcn/ui v4 compat |
| Vite | 6.x | Build tool + dev server | Official React recommendation post-CRA deprecation (Feb 2025) |
| TypeScript | 5.x | Type safety | Non-negotiable for maintainability on a data-heavy app |
| Tailwind CSS | 4.x | Utility CSS | v4 stable (early 2025); CSS-first setup, no PostCSS config needed, @tailwindcss/vite plugin |
| shadcn/ui | latest (canary) | Component primitives | Tailwind v4 + React 19 support confirmed Feb 2025; headless, unstyled-friendly for custom design system |
| Recharts | 2.x | PMC and zone charts | Lightweight, React-native, no D3 dependency; sufficient for CTL/ATL/TSB line charts and zone bar charts |
| React Router | 7.x | Client-side routing | Standard; v7 aligns with React 19 concurrent features |
| Zustand | 5.x | Client state | Minimal boilerplate; sufficient for UI state (chat, FIT upload, session status) |
| React Query (TanStack Query) | 5.x | Server state / cache | SSE streaming + REST; reduces manual fetch boilerplate |
| vite-plugin-pwa | 0.21.x | PWA service worker + manifest | Zero-config for workbox; handles iOS apple-touch-icon, navigateFallback, precaching |
| sonner | latest | Toast notifications | shadcn/ui officially migrated from its own toast to sonner |

**iOS Safari PWA notes:**
- iOS Safari does not show an install prompt; users must use Share -> "Add to Home Screen" manually.
- Service worker runs on HTTPS only (localhost exempt).
- Add `apple-touch-icon.png` (180x180) to `/public/` alongside standard 192x192 and 512x512 icons.
- `vite-plugin-pwa` with `workbox.navigateFallback: '/index.html'` handles SPA routing in offline mode.
- Test on physical iOS device; iOS Simulator does not accurately represent Safari PWA behavior.

---

### Backend

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Python | 3.12 | Runtime | LTS, supports all required libraries |
| FastAPI | 0.115.x | HTTP framework | Native async, OpenAPI auto-docs, Pydantic v2 integration |
| Pydantic | 2.x | Data validation / models | Bundled with FastAPI; v2 is 5-20x faster than v1 |
| Uvicorn | 0.30.x | ASGI server | Standard FastAPI production server; pair with Gunicorn for Railway |
| python-multipart | latest | File upload parsing | Required for FastAPI file upload endpoints (.FIT ingestion) |
| httpx | 0.27.x | Async HTTP client | Used for Google Calendar API calls and any outbound requests |
| asyncpg | 0.29.x | Async Postgres driver | Fastest async Postgres driver; use with SQLAlchemy 2.x async or directly |
| SQLAlchemy | 2.x | ORM | Async-native in v2; supports asyncpg; alembic migrations |
| alembic | 1.x | DB migrations | Standard with SQLAlchemy; keep schema changes tracked |
| python-jose / PyJWT | latest | JWT verification | Verify Supabase JWTs in FastAPI auth middleware |

**FastAPI async patterns for this project:**
- Use `async def` on all route handlers; FIT parsing is CPU-bound so offload via `asyncio.get_event_loop().run_in_executor()`.
- Use `yield` dependencies for DB session lifecycle.
- SSE endpoint for streaming Claude responses: `fastapi.responses.StreamingResponse` with `media_type="text/event-stream"`.

---

### AI / LLM Layer

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| anthropic (Python SDK) | 0.67.x | Claude API client | Latest stable (Sep 2025); tool use GA since 0.27.0 |
| claude-sonnet-4-5 | current | Default model | Best cost/capability balance for multi-turn coaching agent |

**Tool-use agent loop pattern (explicit, PacerAI-specific):**

Use the lower-level `anthropic` package, NOT `claude-agent-sdk-python`. The Agent SDK executes tools autonomously; PacerAI requires explicit control so the sports-science tool library is the only authoritative source of physiological numbers.

```python
import anthropic

client = anthropic.Anthropic()

def run_agent_turn(messages: list, tools: list) -> str:
    while True:
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=4096,
            tools=tools,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            # Extract final text
            return next(b.text for b in response.content if hasattr(b, "text"))

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = dispatch_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(result),
                    })
            messages.append({"role": "user", "content": tool_results})
```

`dispatch_tool` routes to the sports-science tool library. Any `block.name` not in the library raises a capability-gap log entry and returns a structured error string -- never a fabricated number.

**Streaming variant:** Use `client.messages.stream()` context manager for SSE endpoints; yields text deltas as they arrive.

---

### Data / Storage

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Supabase (managed Postgres) | latest | Primary DB + auth + storage | Managed Postgres, row-level security, built-in storage for FIT files, auth JWTs compatible with FastAPI |
| supabase-py-async | 2.5.x | Python async Supabase client | Async variant of supabase-py; designed for FastAPI lifespan pattern |
| Supabase Storage | - | FIT file object store | Store raw .FIT uploads before parsing; avoid bloating Postgres with binary blobs |
| numpy | 2.x | Numerical computation | Core dependency for all PMC math (EWMA), power calculations, zone derivation |
| pandas | 2.x | Time-series data frames | FIT file records -> DataFrame for TSS/NP/IF calculations; PMC history |
| scipy | 1.13.x | Signal processing | Smoothing, interpolation for power curves; CP modelling for passive FTP estimation |

**Supabase FastAPI integration pattern:**

```python
from contextlib import asynccontextmanager
from supabase._async.client import create_client, AsyncClient

supabase: AsyncClient | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global supabase
    supabase = await create_client(SUPABASE_URL, SUPABASE_KEY)
    yield
    # cleanup if needed

app = FastAPI(lifespan=lifespan)
```

Verify Supabase JWTs using `python-jose` in a FastAPI dependency to authenticate requests from the React frontend.

---

### Integrations

| Technology | Purpose | Key Libraries |
|------------|---------|---------------|
| **fitdecode** (0.10.x) | .FIT file parsing | `fitdecode` (PyPI); NOT `fitparse` (inactive) |
| **ZWO export** | Zwift workout XML | Python stdlib `xml.etree.ElementTree`; no library needed |
| **Google Calendar API** | Push/sync sessions | `google-api-python-client`, `google-auth-oauthlib`, `google-auth-httplib2` |
| **PMC calculations** | CTL/ATL/TSB | Custom numpy EWMA; no third-party PMC library (they're either unmaintained or too opinionated) |

**fitdecode vs fitparse decision (DEFINITIVE):**

Use `fitdecode`. fitparse (python-fitparse on PyPI) is effectively abandoned: no releases in 12+ months as of Jan 2026, maintainer seeking handoff, and Snyk rates it inactive. The fitparse maintainer himself directs users to fitdecode. fitdecode supports chained FIT files (Garmin devices produce these), is thread-safe, and gives binary-level access if needed.

```python
import fitdecode

with fitdecode.FitReader("ride.fit") as fit:
    for frame in fit:
        if isinstance(frame, fitdecode.FitDataMessage):
            if frame.name == "record":
                power = frame.get_value("power")
                hr = frame.get_value("heart_rate")
                cadence = frame.get_value("cadence")
                timestamp = frame.get_value("timestamp")
```

**ZWO file format:**

Plain XML; no library required. Structure: `<workout_file><author/><name/><description/><sportType/><workout>` containing segments: `<SteadyState Duration="" Power=""/>`, `<Ramp Duration="" PowerLow="" PowerHigh=""/>`, `<IntervalsT Repeat="" OnDuration="" OffDuration="" OnPower="" OffPower=""/>`. Power values are expressed as FTP multipliers (e.g., 0.75 = 75% FTP). Use `xml.etree.ElementTree` to build and serialize.

**Google Calendar OAuth2 pattern:**

User-facing OAuth2 (not service account). Flow:
1. Backend generates OAuth2 auth URL using `google_auth_oauthlib.flow.Flow`.
2. Frontend redirects user to Google consent.
3. Google redirects to backend callback; exchange code for tokens.
4. Store refresh token in Supabase (encrypted at rest).
5. Use `google.oauth2.credentials.Credentials` with stored refresh token to push/update events via `googleapiclient.discovery.build("calendar", "v3")`.

Required scopes: `https://www.googleapis.com/auth/calendar.events`

---

### Dev / Deploy

| Technology | Purpose | Notes |
|------------|---------|-------|
| Vercel | Frontend hosting | Zero-config for Vite; automatic HTTPS; edge CDN |
| Railway | FastAPI + Uvicorn hosting | Official FastAPI guide; supports Docker; managed env vars |
| Docker | Backend containerization | `python:3.12-slim` base; multi-stage build for smaller image |
| Gunicorn + Uvicorn workers | Production ASGI | `gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app` |
| PostgreSQL | Railway or Supabase | Use Supabase managed Postgres; Railway can reference external DB |
| pytest + pytest-asyncio | Backend testing | Standard for FastAPI async; use `httpx.AsyncClient` as test client |
| Vitest + React Testing Library | Frontend testing | Native Vite test runner; faster than Jest for Vite projects |
| Ruff | Python linting/formatting | Replaces black + flake8 + isort; 100x faster |
| ESLint + Prettier | JS/TS linting | Standard; Vite scaffolds with ESLint config |

**Railway deployment:**

Railway supports direct GitHub deploy or Docker. For FastAPI with file processing (FIT uploads), use Docker to control the runtime precisely:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000", "main:app"]
```

**Note on Railway for long-running tasks:** FIT file parsing and PMC recalculation are brief CPU bursts, not persistent long-running jobs, so Railway is appropriate. If background job processing (e.g., async re-plan triggers) grows complex, add a Redis + ARQ (async task queue) layer later.

---

## What NOT to Use

| Rejected | Reason |
|----------|--------|
| `fitparse` (python-fitparse) | Abandoned — no releases since 2023, maintainer seeking handoff, Snyk marks inactive Jan 2026 |
| `claude-agent-sdk-python` | Autonomous tool execution conflicts with PacerAI trust model — LLM must not self-execute physiological calculations |
| `scikit-cycling` | Unmaintained; last meaningful commit 2019; use numpy/pandas directly with documented formulas |
| `Create React App` | Officially deprecated Feb 2025 |
| Tailwind CSS v3 | Start on v4; no reason to carry v3 migration debt on a greenfield project |
| Node.js backend | FastAPI chosen because fitdecode + numpy/scipy are Python-native; Node would require child processes or microservice split |
| Strava API | Explicitly out of scope per PROJECT.md |
| Web Bluetooth | Phase 2 only; Chromium-only, conflicts with Zwift trainer control |
| D3.js | Overkill for PMC charts; Recharts covers all chart types needed |
| SQLite | Single-file DB has no concurrent write story; Supabase Postgres is already the decision |
| Redux | Zustand is sufficient; Redux adds ceremony with no benefit at this scale |

---

## Sports-Science Library Notes

No single Python library covers all required calculations correctly for this project. Build a custom `sports_science/` module backed by numpy:

| Calculation | Implementation |
|-------------|---------------|
| Power zones (Coggan 7-zone) | Pure Python dict from FTP multipliers; no library needed |
| HR zones | Same pattern from LTHR |
| NP (Normalized Power) | 30s rolling average -> 4th power -> mean -> ^0.25; numpy vectorized |
| IF (Intensity Factor) | NP / FTP |
| TSS | `(duration_seconds * NP * IF) / (FTP * 3600) * 100` |
| CTL (42-day EWMA) | `numpy` exponentially weighted mean with alpha = `1 - exp(-1/42)` |
| ATL (7-day EWMA) | Same with alpha = `1 - exp(-1/7)` |
| TSB | CTL - ATL |
| Passive FTP estimation | Critical Power model via `scipy.optimize.curve_fit` on (duration, mean_max_power) data |

All functions must be deterministic, unit-tested, and return both the result and the named methodology string (e.g., `"Coggan 7-zone"`, `"Banister impulse-response"`).

---

## Confidence Notes

| Area | Confidence | Basis |
|------|------------|-------|
| FIT parsing library choice (fitdecode) | HIGH | Snyk maintenance data + maintainer's own recommendation; cross-verified |
| Anthropic SDK version + tool-use loop pattern | MEDIUM | PyPI release confirmed; pattern from official docs and community |
| Tailwind v4 + shadcn/ui Tailwind v4 compat | HIGH | Official shadcn/ui changelog Feb 2025 is authoritative |
| FastAPI + Supabase async pattern | MEDIUM | supabase-py-async 2.5.6 confirmed on PyPI; lifespan pattern from community |
| Google Calendar OAuth2 | MEDIUM | Official Google docs pattern; standard OAuth2 flow |
| Railway for FastAPI | MEDIUM | Official Railway FastAPI guide exists; Docker deploy confirmed |
| PMC math formulas | HIGH | Published in Coggan/Allen "Training and Racing with a Power Meter"; TrainingPeaks blog confirms |
| ZWO file format | MEDIUM | Community-reverse-engineered reference (h4l/zwift-workout-file-reference); no official Zwift schema published |
| vite-plugin-pwa + iOS Safari | MEDIUM | Plugin docs + community; iOS PWA limitations are well-documented |

---

## Installation Reference

### Frontend
```bash
npm create vite@latest pacer-ai-web -- --template react-ts
cd pacer-ai-web
npm install tailwindcss @tailwindcss/vite
npm install @tanstack/react-query zustand react-router-dom recharts sonner
npm install -D vite-plugin-pwa vitest @testing-library/react
npx shadcn@canary init
```

### Backend
```bash
pip install fastapi==0.115.* uvicorn[standard] gunicorn pydantic
pip install anthropic==0.67.*
pip install fitdecode asyncpg sqlalchemy[asyncio] alembic
pip install supabase-py-async httpx python-multipart
pip install google-api-python-client google-auth-oauthlib
pip install numpy pandas scipy
pip install python-jose[cryptography]
pip install -D pytest pytest-asyncio ruff
```
