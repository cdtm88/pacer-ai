# Project Research Summary: PacerAI

**Project:** PacerAI
**Domain:** Adaptive AI cycling coach (web PWA)
**Researched:** 2026-06-19
**Confidence:** MEDIUM

## Executive Summary

PacerAI is a three-tier web application: React PWA on Vercel, Python FastAPI on Railway, and Supabase Postgres as the data layer. The dominant architectural constraint is the trust model: Claude owns coaching judgement but is forbidden from emitting physiological numbers. Every physiological figure (watts, zones, TSS, CTL/ATL/TSB) must originate from a deterministic, unit-tested sports-science tool library. This constraint is enforced at three levels: code boundary (sports_science/ has zero Anthropic imports), tool schema enforcement (only registry functions become Anthropic tools), and a response-parsing layer that regex-rejects any assistant message containing unsourced numeric values. The trust model is also a product differentiator: "coach shows its work" is a unique and credible claim no competitor makes explicitly.

The recommended build order flows from the trust anchor outward: sports-science tool library first, then agent wiring, then FIT ingestion and plan generation, then UI, then integrations (ZWO, Google Calendar, during-session PWA view). Rushing UI before the tool library is tested is the single most likely way to ship a broken trust model from day one. The critical success path for MVP is narrow: interview -> plan (RPE/HR targets, no FTP required) -> FIT upload -> PMC update -> adaptive re-plan with cited explanation.

Key risks concentrate in three areas: sports-science arithmetic (NP zero-inclusion, spike filtering, CP model minimum 4 quality efforts), LLM trust-model drift (prompt constraints alone are insufficient; parsing layer is mandatory), and iOS PWA behaviour (screen wake lock broken before iOS 18.4; session timer must use Date.now() deltas). Google OAuth refresh token expiry in Testing mode is a near-certain production gotcha that must be addressed before any real user testing.

---

## Key Findings

### Stack

The stack is Python/FastAPI on the backend and React/Vite on the frontend, with Supabase for managed Postgres, auth, and FIT file storage. This combination is chosen because FIT parsing and sports-science maths (numpy, scipy) are Python-native with no credible JS equivalent.

**Core technologies:**
- `fitdecode` 0.10.x: FIT parsing — fitparse is abandoned (Snyk marks inactive Jan 2026); fitdecode handles chained Zwift FIT files and partial files via `error_handling='warn'`
- `anthropic` SDK 0.67.x (NOT `claude-agent-sdk`): the Agent SDK executes tools autonomously, violating the trust model; use raw SDK with an explicit stop_reason loop
- Tailwind CSS v4 + `@tailwindcss/vite` plugin: CSS-first, no `tailwind.config.js`; shadcn/ui confirmed compatible with Tailwind v4 + React 19 (Feb 2025)
- Custom `sports_science/` numpy module: PMC math (CTL/ATL EWMA), NP, TSS, IF, zone derivation; scikit-cycling abandoned 2019
- `xml.etree.ElementTree` (stdlib): ZWO file generation; community-documented XML format; no library needed
- Supabase: managed Postgres + RLS + auth JWTs + Storage bucket for raw FIT blobs; `supabase-py-async` 2.5.x
- `vite-plugin-pwa`: service worker, manifest, iOS apple-touch-icon, navigateFallback for SPA offline
- Recharts 2.x: PMC and zone charts; no D3 dependency

**What not to use:** fitparse, claude-agent-sdk, scikit-cycling, CRA, Tailwind v3, D3, Redux, SQLite, Strava API, Web Bluetooth (Phase 2), full PMC chart (Phase 2).

### Features: What Makes This Different

Cold-start handling (zero FTP, zero history) is table stakes for this specific user, not a differentiator. Every competitor forces a ramp test or requires imported history; PacerAI's baseline is RPE/HR targets from day one with passive FTP estimation accumulating silently.

**Must have (table stakes):**
- Structured weekly plan with explicit per-session targets (RPE/HR first; power after FTP reaches medium confidence)
- Plan adapts when life disrupts it (missed sessions, illness, schedule changes)
- Mobile-usable during session (large-font stepper + timer; iOS Safari PWA)
- Safe onboarding with zero prior knowledge assumed
- ZWO export (pre-FTP sessions: conservative flat target at 50-55% assumed FTP + RPE text segments)
- Explanation of why the plan changed (cited principle + actual data)
- Historical ride log and progress feedback (TSB as single "form" number; full PMC chart is Phase 2)

**Differentiators:**
- Conversational onboarding interview: LLM-led intake surfaces injury status, schedule, motivation; produces persisted profile with back-protective constraints
- Passive FTP estimation with explicit confidence level: CP model from normal ride maximal efforts; never emits estimate with fewer than 4 quality efforts
- Adaptation transparency with cited sports-science principles: "Your ATL spiked to 68 TSS/day; ramp rate exceeds ACSM 10% guideline, so we dropped Thursday's threshold block"
- Trust model surfaced to user ("coach shows its work"): every number traceable to a named tool call and methodology string
- Back-protective constraint layer: cap volume, flag sprint efforts, flag excess standing time in ZWO

**Defer to Phase 2+:** full PMC chart, Telegram bot, Web Bluetooth, dark mode, two-way Google Calendar sync, Strava, nutrition, multi-sport, social features.

### Architecture

Three-tier: React PWA (Vercel) over SSE + REST to FastAPI (Railway) backed by Supabase. Chat uses SSE (not WebSocket): turn-based pattern, EventSource is sufficient, avoids WebSocket lifecycle complexity. The agent loop is multi-turn with `asyncio.gather` for parallel tool dispatch.

**Major components:**
1. `sports_science/` - pure Python; zero Anthropic imports; every function returns `{value, unit, methodology, inputs}`; built and tested first, never bypassed
2. `agent/loop.py` - explicit stop_reason loop; streams text chunks via SSE; dispatches tool calls to sports_science registry; max 3 retries per tool per turn; calls `log_capability_gap` as structured fallback
3. `agent/tools.py` - tool registry; maps sports_science functions to Anthropic tool schemas; no physiology logic
4. `api/rides.py` - FIT upload pipeline: Supabase Storage, fitdecode parse, tool-library compute, PMC update, plan validation, re-plan trigger
5. `export/zwo.py` - pure data transformation; no LLM; Power values are FTP fractions (not watts)
6. React PWA - all physiological values arrive from backend as pre-computed strings; frontend does no sports-science math

**8-table schema:** `users`, `profiles`, `sessions`, `rides`, `pmc_history`, `conversations`, `messages`, `capability_gaps`

**Build order:** Layer 0 (tool library + DB schema + Supabase) -> Layer 1 (tool registry + FIT pipeline + agent loop) -> Layer 2 (FastAPI endpoints) -> Layer 3 (React PWA) -> Layer 4 (ZWO, Calendar, During-Session)

### Critical Pitfalls

1. **CP model emits garbage with fewer than 4 quality efforts** - tag every FTP estimate with confidence (`low`/`medium`/`high`); never emit power targets until confidence reaches `medium`; prescribe RPE/HR only during cold start
2. **NP/TSS arithmetic traps** - zeros MUST be included in NP; spike-filter mandatory before NP (clip power > FTP*3); use NP not average power for TSS; return null for rides under 10 minutes; validate IF < 1.05 for rides over 60 minutes
3. **PMC cold-start misleading TSB** - do NOT display CTL/ATL/TSB until 28+ days of data; show "building baseline" state with ride count and days remaining
4. **System prompt alone does not prevent LLM number emission** - enforce at parsing layer: regex-check every assistant response for unsourced numerics; reject and retry if found; `log_capability_gap` is itself a tool as the structured escape hatch
5. **Tool-calling loops: infinite and zombie variants** - max 3 retries per tool per turn; all tools return `{status, value, reason}`; deduplicate by `(name, args_hash)` per turn; context summarization after 8+ tool calls
6. **Google OAuth 7-day refresh token expiry in Testing mode** - move to Production before any real user testing; token health check before every Calendar API call; store encrypted in DB, never in browser storage
7. **ZWO Power is a ratio, not watts** - `Power="0.75"` means 75% FTP; validate all Power values between 0.0 and 2.0; `<sportType>bike</sportType>` mandatory; omit Cadence rather than setting to 0
8. **iOS wake lock broken before iOS 18.4 in installed PWA mode** - detect iOS version; if < 18.4, activate NoSleep.js; session timer must use `Date.now()` deltas; use `visibilitychange` to resync on return
9. **Single-event overreaction in adaptive re-planning** - distinguish micro-adjustments (next 1-3 sessions) from macro-replanning; require 2+ signals for macro replan; never change > 30% of session positions without user confirmation
10. **Zwift FIT files are not spec-compliant** - `error_handling=fitdecode.ErrorHandling.WARN`; `get_value('power', fallback=None)` on all fields; no GPS fields on indoor rides; test against real Zwift FIT file before agent depends on it

---

## Implications for Roadmap

### Phase 1: Sports-Science Foundation
**Rationale:** Trust anchor; all downstream phases depend on verified calculations.
**Delivers:** `sports_science/` module (NP, TSS, IF, CTL, ATL, TSB, FTP estimation, power zones, HR zones, load progression, capability-gap logger); full unit test suite; DB schema + migrations; Supabase setup; PWA shell with iOS install banner.
**Must avoid:** CP model emitting FTP with fewer than 4 efforts; NP excluding zeros; PMC without cold-start guard.

### Phase 2: Agent Core
**Rationale:** Agent wiring requires working tool registry; SSE trust-enforcement layer must be proven before UI is built on it.
**Delivers:** `agent/loop.py` (multi-turn, 3-retry, deduplication); `agent/tools.py` (tool registry); SSE streaming endpoint; response-parsing trust layer; compliance test suite.
**Must avoid:** claude-agent-sdk; infinite loops; system prompt as only trust enforcement.

### Phase 3: FIT Ingestion and Plan Generation
**Rationale:** Core coaching loop (upload -> compute -> adapt) is the MVP critical path.
**Delivers:** FIT upload pipeline (fitdecode, metrics via tool library, PMC upsert, re-plan trigger); plan generation (RPE/HR, no FTP required); onboarding interview endpoint; adaptive re-plan with micro vs macro distinction; chat explanation with cited principles.
**Must avoid:** GPS field KeyErrors; single-event overreaction; TSB display before 28 days.

### Phase 4: UI + Integrations
**Rationale:** React PWA built on working endpoints; Google Calendar ships here.
**Delivers:** All screens (Onboarding, Today, Agenda, Session Detail, History, Chat); SSE chat with tool-called skeleton cards; FIT upload flow; ZWO download; Google Calendar OAuth + push; Vercel deployment.
**Must avoid:** Frontend physiological math; dark mode; Google OAuth in Testing mode.

### Phase 5: During-Session View and ZWO Export
**Rationale:** Independent from core coaching loop; iOS-specific complexity warrants its own phase.
**Delivers:** During-session stepper + timer (large-font, glanceable); wake lock with NoSleep.js fallback for iOS < 18.4; Date.now() delta timer; visibilitychange state resync; ZWO template-based XML generator with ratio validation.
**Must avoid:** ZWO built from scratch rather than validated template; Power values in watts; wake lock without fallback.

### Phase Ordering Rationale
- Layer 0 before everything: sports_science/ is the trust anchor; nothing else is credible without it
- Agent before UI: UI on an untested agent loop appears to work but may silently fabricate numbers
- FIT ingestion before plan adaptation: adaptive re-plan trigger depends on PMC data from real rides
- ZWO and Calendar can ship alongside or after UI; not on critical success path
- During-session view has iOS-specific complexity warranting its own phase and acceptance criteria

### Research Flags

**Needs deeper research during planning:**
- Phase 2 (Agent Core): response-parsing trust-enforcement layer is custom; validate with working prototype before committing
- Phase 3 (Adaptive Re-planning): micro vs macro trigger policy is a custom heuristic with no reference implementation; spike/prototype recommended
- Phase 5 (ZWO Export): community-documented format only; validate generated files against real Zwift import before shipping

**Standard patterns (skip research-phase):**
- Phase 1 (Sports-science library): formulas published in Coggan/Allen; numpy/scipy implementation is straightforward
- Phase 4 (UI): React + Vite + Tailwind v4 + shadcn/ui is well-documented; SSE EventSource is standard

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | fitdecode choice verified against maintainer recommendation + Snyk; Tailwind v4 + shadcn/ui compat from official Feb 2025 changelog; PMC formulas from Coggan/Allen primary source |
| Features | HIGH | Competitive landscape well-understood; table stakes vs differentiator grounded in direct competitor comparison |
| Architecture | MEDIUM | Tool-use loop from official Anthropic docs; SSE standard; ZWO format community-reverse-engineered only |
| Pitfalls | MEDIUM | Sports-science from peer-reviewed sources; LLM/PWA from practitioner community; iOS wake lock from Apple Developer Forums |

**Overall confidence:** MEDIUM

### Gaps to Address

- **ZWO Zwift validation**: real Zwift import test required before Phase 5 ships; flag as acceptance criterion
- **Google OAuth Production**: must move to Production before any external user testing; Phase 4 pre-launch checklist item
- **Adaptive re-plan trigger thresholds**: specific values (TSB < -30, CTL ramp > 8 pts/week) are informed estimates; treat as configurable constants from the start
- **CP model effort quality detection**: "4 quality efforts with meaningful variance" needs a working definition; plan a brief spike during Phase 1

---

## Sources

- .planning/research/STACK.md
- .planning/research/FEATURES.md
- .planning/research/ARCHITECTURE.md
- .planning/research/PITFALLS.md

---
*Research completed: 2026-06-19*
*Ready for roadmap: yes*
