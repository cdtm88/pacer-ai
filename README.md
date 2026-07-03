# PacerAI

An evidence-based, adaptive AI cycling coach for a beginner returning to fitness. PacerAI interviews the user from zero knowledge, builds a structured periodised training plan, and re-plans intelligently as real ride data arrives as `.FIT` files. Web-first, mobile-responsive PWA.

**Core value:** A new user with no FTP and no fitness history can complete an interview and immediately receive a safe, structured plan with explicit per-session targets. That plan adapts automatically as real ride data arrives.

---

## Tech Stack

### Frontend (Vercel)

| Layer | Technology |
|---|---|
| Framework | React 19 + Vite 8 + TypeScript |
| Styles | Tailwind CSS v4 + shadcn/ui |
| Routing | React Router v8 |
| UI state | Zustand |
| Server state | TanStack Query v5 |
| Charts | Recharts |
| Auth client | Supabase JS |
| PWA | vite-plugin-pwa (iOS Safari safe) |
| Toasts | Sonner |

### Backend (Vercel Python Runtime)

| Layer | Technology |
|---|---|
| Runtime | Python 3.12 |
| Framework | FastAPI, served by Vercel's Python Runtime (ASGI `app` invoked directly -- no Docker, no Gunicorn/Uvicorn CLI) |
| LLM | Anthropic Python SDK, `claude-sonnet-4-5`, native tool use |
| FIT parsing | fitdecode (not fitparse, which is abandoned) |
| Sports science | numpy, scipy, pandas (PMC, NP, TSS, IF, FTP) |
| Database / auth | Supabase (managed Postgres + auth + storage), accessed via the `supabase` client and raw SQL migrations under `supabase/migrations/` -- no SQLAlchemy/Alembic |
| Calendar | Google Calendar API (OAuth2) |

---

## Architecture: Trust Model

The LLM owns judgement; a validated tool library owns numbers.

Every physiological figure (power zones, TSS, IF, NP, FTP estimates, CTL/ATL/TSB, load-progression targets) must come from a deterministic, unit-tested function in the sports-science tool library. That function also returns the named methodology it applied.

The LLM is forbidden from emitting any such number from its own reasoning. If a needed calculation has no tool, the agent logs a structured capability-gap entry, tells the user in chat, and falls back gracefully. It never fabricates a number. Any code path where the model places a self-derived physiological number into a plan is a defect, regardless of plausibility.

This constraint is enforced at code level and verifiable in logs (the `capability_gaps` table in Supabase).

---

## Screens

| Route | Screen |
|---|---|
| `/login` | Login (Supabase magic link) |
| `/auth/callback` | Auth callback (PKCE exchange) |
| `/onboarding` | LLM-led interview, builds user profile |
| `/` | Today (session card with zones, TSB, ZWO export) |
| `/agenda` | Upcoming sessions |
| `/history` | Ride list, CTL sparkline, `.FIT` upload |
| `/session` | During-session stepper (iOS-safe timer, wake lock) |
| `/chat` | Ongoing coaching conversation |
| `/settings` | Google Calendar connection |

---

## API Endpoints

The FastAPI backend exposes these route groups. In production, Vercel's root `vercel.json` rewrites `/api/(.*)` to the backend service and `api/index.py` mounts the FastAPI app at `/api`, so every path below is actually reached at `/api` + the path shown (e.g. `GET /chat/stream` is `GET /api/chat/stream`). In local dev, the Vite proxy strips this and forwards the bare paths shown below directly to `localhost:8000`.

- `GET /chat/stream` -- SSE streaming for coaching conversations (GET because the browser `EventSource` API can only issue GET requests)
- `POST /conversations/` -- create a new conversation
- `POST /onboarding/start` -- begin the onboarding interview
- `POST /rides/upload` -- ingest a `.FIT` file
- `GET /rides/` -- list uploaded rides
- `GET /adaptations/` -- list plan adaptations
- `POST /adaptations/check` -- trigger adaptive re-planning check
- `GET /sessions/today` -- today's planned session
- `GET /sessions/upcoming` -- upcoming session list
- `GET /pmc_history/latest` -- current PMC state (CTL/ATL/TSB)
- `GET /profiles/me` -- authenticated user profile
- `GET /calendar/auth` -- begin Google Calendar OAuth flow
- `GET /calendar/settings` -- calendar connection status
- `GET /health` -- liveness check

---

## Local Development

### Prerequisites

- Node.js 20+
- Python 3.12
- A Supabase project (for auth and database)
- An Anthropic API key

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local   # fill in VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY
npm run dev                   # http://localhost:5173
```

### Backend

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # fill in ANTHROPIC_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
uvicorn backend.main:app --reload --port 8000
```

The Vite dev server proxies all `/api/*` routes (`/api/chat`, `/api/sessions`, `/api/rides`, etc.) to `localhost:8000`, stripping the `/api` prefix before forwarding -- matching the production routing scheme (see API Endpoints below).

### Tests

```bash
# Python unit tests (64 sports-science tests)
pytest

# Python lint
ruff check api/

# Frontend unit tests (Vitest)
cd frontend && npm test

# Frontend build check
cd frontend && npm run build
```

---

## Deployment

Vercel is the sole deploy target. Both frontend and backend deploy from `main` as a single Vercel project, configured by the root `vercel.json`.

### Frontend: Vercel

Auto-deploys from `main`. Builds to a static bundle:

- Build command: `cd frontend && npm install && npm run build`
- Output directory: `frontend/dist`
- SPA fallback rewrite: all non-API routes -> `/index.html`

### Backend: Vercel

The FastAPI app runs as a Vercel Python Function, entrypoint `api/index.py`. Vercel's Python runtime invokes the ASGI `app` object directly, no Docker image or process manager (Gunicorn/Uvicorn CLI) is involved. Request routing between the static frontend and the Python function is configured in the root `vercel.json`.

---

## Environment Variables

### Frontend (`frontend/.env.local`)

| Variable | Description |
|---|---|
| `VITE_SUPABASE_URL` | Supabase project URL |
| `VITE_SUPABASE_ANON_KEY` | Supabase anon/public key |
| `VITE_API_URL` | Backend API URL (blank = same-origin proxy in dev) |

### Backend (`.env` or Vercel env vars)

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key |
| `SUPABASE_JWT_SECRET` | Secret used to verify Supabase-issued JWTs |
| `CALENDAR_FERNET_KEY` | Symmetric key for encrypting/decrypting stored Google Calendar OAuth tokens |
| `BACKEND_BASE_URL` | Publicly reachable base URL of the backend (used to build OAuth redirect URIs) |
| `ANTHROPIC_MODEL` | Claude model identifier used by the coaching agent |
| `FRONTEND_URL` | Deployed frontend URL (used for CORS) |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID (for calendar) |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |

These vars must be set in Vercel Project Settings -> Environment Variables (per environment) for production.

---

## Sports-Science Implementation

All calculations use custom numpy/scipy implementations against published methodology (Coggan/Allen, TrainingPeaks PMC, ACSM).

| Calculation | Method |
|---|---|
| Power zones | Coggan 7-zone model from FTP multipliers |
| HR zones | LTHR percentage bands |
| NP (Normalized Power) | 30s rolling mean to 4th power, mean, then `^0.25` |
| IF (Intensity Factor) | `NP / FTP` |
| TSS | `(duration_s * NP * IF) / (FTP * 3600) * 100` |
| CTL (fitness) | 42-day numpy EWMA: `alpha = 1 - exp(-1/42)` |
| ATL (fatigue) | 7-day numpy EWMA: `alpha = 1 - exp(-1/7)` |
| TSB (form) | `CTL - ATL` |
| Passive FTP estimate | Critical Power model via `scipy.optimize.curve_fit` on (duration, mean-max power) pairs |

Cold-start is a first-class supported case. Users with no FTP receive sessions prescribed by RPE/HR. FTP is estimated passively after four or more quality efforts.

---

## Development Process

The project was built with an AI-assisted workflow across 5 sequential phases. Planning artifacts live in `.planning/`.

| Phase | Scope |
|---|---|
| 01: Sports Science Foundation | Tool library with 64 unit tests (power zones, HR zones, FTP estimation, TSS/IF/NP, PMC, load progression) |
| 02: Agent Core | Anthropic tool-use loop, trust-model enforcement, capability-gap logging |
| 03: Coaching Loop | Onboarding interview, plan generation, `.FIT` ingestion, adaptive re-planning |
| 04: UI + Calendar | Full React UI (all screens), Supabase auth, Google Calendar integration |
| 05: During-session + ZWO Export | iOS-safe session stepper, wake lock, ZWO file export for Zwift |

Current status is in `.planning/PROJECT.md`. The roadmap is in `.planning/ROADMAP.md`.

---

## Key Constraints

- No em dashes in any generated content or copy (use commas, colons, semicolons, or separate sentences)
- Light mode only for MVP; no pure blacks in the design system
- LLM trust model enforced at code level and verifiable in logs
- FIT parsing uses `fitdecode` only (`fitparse` is abandoned)
- No Strava integration (out of scope)
- ZWO files are generated server-side only; the LLM never touches power values

---

## Out of Scope (v1)

- Strava integration
- Garmin/Zwift direct auto-pull (manual `.FIT` upload only)
- Social, sharing, or community features
- Dark mode
- Web Bluetooth live power echo (Chromium-only, conflicts with Zwift trainer control)
- Full CTL/ATL/TSB PMC screen
- Telegram bot (planned for Phase 2 post-MVP)
