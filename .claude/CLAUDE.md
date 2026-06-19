<!-- GSD:project-start source:PROJECT.md -->

## Project

**PacerAI**

PacerAI is an evidence-based, adaptive AI cycling coach for a beginner returning to fitness (general fitness and weight loss; no event or competition). It interviews the user from zero knowledge, builds a structured training plan, and re-plans intelligently as real ride data arrives as .FIT files. Web-first, mobile-responsive PWA with an in-app chat interface.

**Core Value:** A new user with no FTP and no fitness history can complete an interview and immediately receive a safe, structured, periodised cycling plan with explicit per-session targets — and that plan adapts automatically as real ride data arrives.

### Constraints

- **Architecture**: LLM never emits physiological numbers directly — tool library is the only authoritative source for all sports-science calculations. Enforced at code level, verifiable in logs.
- **Tech Stack**: React + Vite + Tailwind (frontend), Python FastAPI (backend), Anthropic API with native tool use, Postgres/Supabase, fitparse/fitdecode for FIT parsing, Vercel (frontend) + Railway (API/DB)
- **PWA**: Web-first, mobile-responsive; During-session view must work on iOS Safari
- **Light mode only**: No pure blacks anywhere for MVP; design system from PRD applies
- **No em dashes**: In any generated content or copy — use commas, semicolons, colons, or separate sentences
- **Calendar**: Google Calendar API (OAuth2) for push/sync

<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->

## Technology Stack

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

- iOS Safari does not show an install prompt; users must use Share -> "Add to Home Screen" manually.
- Service worker runs on HTTPS only (localhost exempt).
- Add `apple-touch-icon.png` (180x180) to `/public/` alongside standard 192x192 and 512x512 icons.
- `vite-plugin-pwa` with `workbox.navigateFallback: '/index.html'` handles SPA routing in offline mode.
- Test on physical iOS device; iOS Simulator does not accurately represent Safari PWA behavior.

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

- Use `async def` on all route handlers; FIT parsing is CPU-bound so offload via `asyncio.get_event_loop().run_in_executor()`.
- Use `yield` dependencies for DB session lifecycle.
- SSE endpoint for streaming Claude responses: `fastapi.responses.StreamingResponse` with `media_type="text/event-stream"`.

### AI / LLM Layer

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| anthropic (Python SDK) | 0.67.x | Claude API client | Latest stable (Sep 2025); tool use GA since 0.27.0 |
| claude-sonnet-4-5 | current | Default model | Best cost/capability balance for multi-turn coaching agent |

### Data / Storage

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Supabase (managed Postgres) | latest | Primary DB + auth + storage | Managed Postgres, row-level security, built-in storage for FIT files, auth JWTs compatible with FastAPI |
| supabase-py-async | 2.5.x | Python async Supabase client | Async variant of supabase-py; designed for FastAPI lifespan pattern |
| Supabase Storage | - | FIT file object store | Store raw .FIT uploads before parsing; avoid bloating Postgres with binary blobs |
| numpy | 2.x | Numerical computation | Core dependency for all PMC math (EWMA), power calculations, zone derivation |
| pandas | 2.x | Time-series data frames | FIT file records -> DataFrame for TSS/NP/IF calculations; PMC history |
| scipy | 1.13.x | Signal processing | Smoothing, interpolation for power curves; CP modelling for passive FTP estimation |

### Integrations

| Technology | Purpose | Key Libraries |
|------------|---------|---------------|
| **fitdecode** (0.10.x) | .FIT file parsing | `fitdecode` (PyPI); NOT `fitparse` (inactive) |
| **ZWO export** | Zwift workout XML | Python stdlib `xml.etree.ElementTree`; no library needed |
| **Google Calendar API** | Push/sync sessions | `google-api-python-client`, `google-auth-oauthlib`, `google-auth-httplib2` |
| **PMC calculations** | CTL/ATL/TSB | Custom numpy EWMA; no third-party PMC library (they're either unmaintained or too opinionated) |

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

## Sports-Science Library Notes

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

## Installation Reference

### Frontend

### Backend

<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->

## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->

## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->

## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->

## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:

- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->

## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
