# Requirements: PacerAI

**Defined:** 2026-06-19
**Core Value:** A beginner with no FTP and no history completes an interview and immediately receives a safe, structured cycling plan with explicit targets — that plan adapts automatically as real ride data arrives.

## v1 Requirements

### Sports-Science Tool Library

- [ ] **TOOL-01**: `calculate_power_zones(ftp)` returns 7 Coggan/Allen power zones with boundary values, zone names, and methodology string
- [ ] **TOOL-02**: `calculate_hr_zones(max_hr_or_lthr)` returns HR zones with boundary values and methodology string
- [ ] **TOOL-03**: `estimate_ftp_from_rides(rides)` returns FTP estimate, confidence level (low/medium/high), and methodology string; requires minimum 4 quality efforts before emitting any estimate
- [ ] **TOOL-04**: `compute_tss(ride)` returns TSS, IF, and NP for a ride; NP calculation includes zeros, applies spike filter (clip power > FTP*3), uses NP not average power; returns null for rides under 10 minutes
- [ ] **TOOL-05**: `update_pmc(tss_history)` returns CTL (fitness), ATL (fatigue), and TSB (form) using Banister/PMC EWMA model; cold-start guard: does not emit TSB values until 28+ days of data
- [ ] **TOOL-06**: `progress_load(current_ctl, target, constraints)` returns safe weekly ramp targets with injury-aware caps
- [ ] **TOOL-07**: `validate_session_vs_actual(planned, actual)` returns compliance percentage, deltas, and flags
- [ ] **TOOL-08**: `log_capability_gap(method_name, context)` logs a structured entry to the application capability-gap log and returns a user-facing fallback message; this is itself an Anthropic tool in the agent registry
- [ ] **TOOL-09**: All tool-library functions return a structured result containing value, unit, methodology name, and inputs used
- [ ] **TOOL-10**: Full unit test suite covering all tool-library functions, including edge cases (sparse data, zeros, spikes, cold-start, back-protective constraints)

### Trust Model Enforcement

- [ ] **TRUST-01**: The `sports_science/` module has zero Anthropic SDK imports; no path exists for the LLM to call physiological logic except through the tool registry
- [ ] **TRUST-02**: The agent tool registry maps only registered sports_science functions to Anthropic tool schemas; ad-hoc tool definitions are not permitted
- [ ] **TRUST-03**: Every assistant response is parsed before display; any response containing an unsourced physiological number (watts, zones, TSS, FTP, CTL/ATL/TSB values) triggers a retry and capability-gap log entry
- [ ] **TRUST-04**: Every physiological number in any plan or chat message is traceable to a tool-library call verifiable in application logs
- [ ] **TRUST-05**: When the agent needs a quantitative method the tool library lacks, it calls `log_capability_gap`, surfaces a brief chat note, and falls back to qualitative reasoning; it never improvises a number

### Agent Core

- [ ] **AGENT-01**: The agent loop uses the raw `anthropic` SDK (not claude-agent-sdk) with an explicit `stop_reason == "tool_use"` check; the Agent SDK is forbidden because it executes tools autonomously
- [ ] **AGENT-02**: The agent loop supports multi-turn conversations with `asyncio.gather` for parallel tool dispatch when Claude returns multiple tool_use blocks in one response
- [ ] **AGENT-03**: The agent loop enforces a maximum of 3 retries per tool call per turn; all tools return `{status, value, reason}`; failed tool calls are surfaced in chat, not silently swallowed
- [ ] **AGENT-04**: Tool calls are deduplicated by `(name, args_hash)` per turn to prevent zombie loops
- [ ] **AGENT-05**: Chat responses stream via SSE (Server-Sent Events); the frontend uses EventSource; WebSocket is not used
- [ ] **AGENT-06**: A compliance test suite verifies the trust model is maintained end-to-end (agent never emits unsourced physiological numbers across a representative set of scenarios)

### Onboarding Interview

- [ ] **ONBD-01**: A new user with zero prior data completes a conversational LLM-led interview that establishes: self-reported baseline fitness, injury and medical status (including back issues), equipment available, weekly time availability and schedule, and short- and long-term goals
- [ ] **ONBD-02**: Injury and back status established through the interview is persisted to the user profile and applied as back-protective plan constraints; it is never assumed or defaulted
- [ ] **ONBD-03**: The interview output is a persisted structured user profile stored in the database
- [ ] **ONBD-04**: The user sees a confirmation summary of their profile at the end of the interview before the plan is generated

### Plan Generation

- [ ] **PLAN-01**: The agent generates a structured, periodised training plan appropriate to a returning beginner (aerobic-base emphasis, sustainable progression)
- [ ] **PLAN-02**: Cold-start is a first-class supported case: early sessions are prescribed using RPE and heart rate targets (comfortable/conversational aerobic), not power targets
- [ ] **PLAN-03**: Power targets are introduced only after the FTP estimate reaches medium confidence (minimum 4 quality efforts); the plan does not fabricate power targets before this threshold
- [ ] **PLAN-04**: Every session has an explicit plan: objective, structure (warm-up / main set / cool-down), targets (RPE/HR early; power later), and duration
- [ ] **PLAN-05**: Back-protective constraints surfaced in the interview are reflected in the plan: initial volume cap, no prolonged standing efforts early, no sprint efforts early, and a flag if load ramps too fast
- [ ] **PLAN-06**: Every physiological number in a generated plan is traceable to a tool-library call (satisfies TRUST-04)

### FIT File Ingestion

- [ ] **FIT-01**: User can drag or select a .FIT file (Zwift or compatible head unit) in the web app to upload it
- [ ] **FIT-02**: The parser uses `fitdecode` with `error_handling=ErrorHandling.WARN`; all field access uses `get_value('field', fallback=None)`; GPS fields are not required (indoor rides)
- [ ] **FIT-03**: The parser extracts power, heart rate, cadence, and duration from the .FIT file; missing fields are handled gracefully with fallback to null
- [ ] **FIT-04**: After parsing, `compute_tss` is called on the ride data; `update_pmc` is called to update the PMC history; results are persisted to `rides` and `pmc_history` tables
- [ ] **FIT-05**: The parsed ride feeds `validate_session_vs_actual` to produce a compliance percentage, delta metrics, and flags
- [ ] **FIT-06**: A real Zwift .FIT file is used as an acceptance test before the FIT pipeline is considered production-ready

### Adaptive Re-Planning

- [ ] **ADAPT-01**: The plan adapts based on missed sessions, holidays/travel, actual performance, and accumulated training load
- [ ] **ADAPT-02**: Micro-adjustments (next 1-3 sessions) are distinguished from macro-replanning (structural changes to the week or block); macro replanning requires 2+ data signals, not a single event
- [ ] **ADAPT-03**: No macro replan shifts more than 30% of upcoming session positions without surfacing a change summary to the user
- [ ] **ADAPT-04**: A weekly automated check runs independently of upload events to catch accumulating fatigue that no single session triggers
- [ ] **ADAPT-05**: Intensity and session type are decided dynamically by the agent using tool-library results (for example: swap threshold for recovery when TSB indicates high fatigue)

### Adaptation Transparency

- [ ] **TRANSP-01**: Whenever the plan changes, the agent explains its reasoning in chat by default, citing the data (specific TSS/CTL/TSB/ATL values from tool calls) and the sports-science principle behind the change
- [ ] **TRANSP-02**: Every plan change is persisted to an adaptation log with: trigger event, reasoning shown to user, and timestamp
- [ ] **TRANSP-03**: The adaptation log is readable (not just a raw database table); the user can review past adaptation decisions

### Google Calendar Integration

- [ ] **CAL-01**: Planned sessions are pushed to the user's Google Calendar as events with the session detail in the event body (objective, structure, targets, duration)
- [ ] **CAL-02**: When the plan changes (sessions moved, added, or removed), the corresponding calendar events are updated, moved, or deleted to stay in sync
- [ ] **CAL-03**: Google Calendar OAuth uses production credentials (not Testing mode) before any real user testing; refresh token health is checked before every Calendar API call; tokens are stored encrypted in the database, never in browser storage
- [ ] **CAL-04**: Calendar sync failures are surfaced to the user gracefully; a failed sync does not disrupt the plan or chat

### ZWO Export

- [ ] **ZWO-01**: A planned structured session can be exported as a valid .zwo workout file that Zwift can import
- [ ] **ZWO-02**: Power targets in the .zwo file are expressed as FTP fractions (0.75 = 75% FTP), not watts; all Power values are validated to be between 0.0 and 2.0 before export
- [ ] **ZWO-03**: Pre-FTP sessions use a conservative assumed FTP with RPE text segments in the .zwo structure
- [ ] **ZWO-04**: The .zwo file includes `<sportType>bike</sportType>`; Cadence is omitted rather than set to 0 when not specified
- [ ] **ZWO-05**: A generated .zwo file is validated against a real Zwift import as an acceptance criterion before ZWO export is considered production-ready

### Web UI

- [ ] **UI-01**: Onboarding screen: full-screen conversational flow with the interview agent, ending in a profile confirmation summary
- [ ] **UI-02**: Today/Home screen: today's session as a prominent card (objective, structure, targets, duration) with actions: Start Session, Export to Zwift, Mark Done, Mark Missed; compact next-few-days view; a plain-language form chip (fresh/balanced/fatigued derived from TSB, shown only after 28+ days of data)
- [ ] **UI-03**: Agenda screen: scrollable list grouped by week; rows show date, type, duration, status; tap to expand full session plan; intensity shown via zone colours matching the PRD design system
- [ ] **UI-04**: History screen: past sessions with planned-vs-actual compliance; a small fitness-trend sparkline (7-30 day CTL trend, shown only after 28+ days of data); tap-through to parsed ride detail (power/HR data, TSS)
- [ ] **UI-05**: During-session screen: large-font stepper showing the current step (target + duration), next step queued below, later steps smaller; a timer auto-advances the highlight; no trainer data required; must work on iOS Safari
- [ ] **UI-06**: Chat screen: dedicated tab with persistent conversation with the agent; adaptation reasoning and capability-gap notes appear in chat; user can log subjective feedback and request plan changes
- [ ] **UI-07**: Navigation: mobile bottom tab bar (Today / Agenda / History / Chat); desktop left sidebar with the same destinations and wider multi-column layouts
- [ ] **UI-08**: Design system: Inter (or equivalent clean contemporary sans) for all UI and headings; primary blue scale anchored at blue-6 #228BE6; neutrals and semantic colours per PRD; no pure black; no em dashes in any copy; warm and professional tone
- [ ] **UI-09**: PWA: installable on iOS and Android; works offline for the during-session view; iOS install instructional banner on first visit
- [ ] **UI-10**: Light mode only for MVP; no dark mode

### iOS PWA During-Session

- [ ] **IOS-01**: Screen wake lock uses the Wake Lock API with a NoSleep.js fallback for iOS versions before 18.4 (wake lock was broken in installed PWAs before iOS 18.4)
- [ ] **IOS-02**: Session timer uses `Date.now()` deltas, not `setInterval` counts; a `visibilitychange` event listener resyncs the timer when the user returns from a background tab
- [ ] **IOS-03**: The during-session view is tested and functional on iOS Safari (not only Chromium)

### Capability-Gap Logging

- [ ] **GAP-01**: When the agent needs a quantitative method the tool library lacks, a structured entry is appended to the `capability_gaps` table with: method name, description of what was needed, timestamp, and conversation context
- [ ] **GAP-02**: The capability-gap log is an application runtime artefact; it never expands what the agent can compute at runtime
- [ ] **GAP-03**: Capability gaps surfaced in chat are brief and user-friendly; they do not expose internal method names

## v2 Requirements

### Telegram Bot

- **TELE-01**: Telegram bot reuses the agent layer via webhook; top Phase 2 priority
- **TELE-02**: Bot supports onboarding, plan viewing, session logging, and adaptation chat via Telegram messages

### Fitness Screen

- **FIT-SCR-01**: Full three-line CTL/ATL/TSB PMC chart for users who want training load depth
- **FIT-SCR-02**: Shown only after 28+ days of data

### Dark Mode

- **DARK-01**: Dark mode via re-mapped palette variant (do not invert); no pure black backgrounds

### Live Trainer Echo

- **LIVE-01**: Optional live power/cadence display during session via Web Bluetooth API
- **LIVE-02**: Chromium-only (no iOS Safari); shown only when Zwift is not controlling the trainer

## Out of Scope

| Feature | Reason |
|---------|--------|
| Strava integration | Explicitly excluded in PRD; ToS fragility; not on roadmap |
| Social / sharing / community features | Not on roadmap; wrong product direction |
| Garmin/Zwift direct auto-pull | Manual .FIT upload only; API access complexity not worth it for MVP |
| Nutrition tracking | Wrong domain; out of scope by design |
| Multi-sport coaching | Cycling-only for MVP |
| Event or competition goal planning | Target user has no event goal; general fitness only |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| TOOL-01 | Phase 1 | Pending |
| TOOL-02 | Phase 1 | Pending |
| TOOL-03 | Phase 1 | Pending |
| TOOL-04 | Phase 1 | Pending |
| TOOL-05 | Phase 1 | Pending |
| TOOL-06 | Phase 1 | Pending |
| TOOL-07 | Phase 1 | Pending |
| TOOL-08 | Phase 1 | Pending |
| TOOL-09 | Phase 1 | Pending |
| TOOL-10 | Phase 1 | Pending |
| TRUST-01 | Phase 1 | Pending |
| TRUST-02 | Phase 1 | Pending |
| TRUST-03 | Phase 2 | Pending |
| TRUST-04 | Phase 2 | Pending |
| TRUST-05 | Phase 2 | Pending |
| AGENT-01 | Phase 2 | Pending |
| AGENT-02 | Phase 2 | Pending |
| AGENT-03 | Phase 2 | Pending |
| AGENT-04 | Phase 2 | Pending |
| AGENT-05 | Phase 2 | Pending |
| AGENT-06 | Phase 2 | Pending |
| ONBD-01 | Phase 3 | Pending |
| ONBD-02 | Phase 3 | Pending |
| ONBD-03 | Phase 3 | Pending |
| ONBD-04 | Phase 3 | Pending |
| PLAN-01 | Phase 3 | Pending |
| PLAN-02 | Phase 3 | Pending |
| PLAN-03 | Phase 3 | Pending |
| PLAN-04 | Phase 3 | Pending |
| PLAN-05 | Phase 3 | Pending |
| PLAN-06 | Phase 3 | Pending |
| FIT-01 | Phase 3 | Pending |
| FIT-02 | Phase 3 | Pending |
| FIT-03 | Phase 3 | Pending |
| FIT-04 | Phase 3 | Pending |
| FIT-05 | Phase 3 | Pending |
| FIT-06 | Phase 3 | Pending |
| ADAPT-01 | Phase 3 | Pending |
| ADAPT-02 | Phase 3 | Pending |
| ADAPT-03 | Phase 3 | Pending |
| ADAPT-04 | Phase 3 | Pending |
| ADAPT-05 | Phase 3 | Pending |
| TRANSP-01 | Phase 3 | Pending |
| TRANSP-02 | Phase 3 | Pending |
| TRANSP-03 | Phase 3 | Pending |
| GAP-01 | Phase 1 | Pending |
| GAP-02 | Phase 1 | Pending |
| GAP-03 | Phase 1 | Pending |
| CAL-01 | Phase 4 | Pending |
| CAL-02 | Phase 4 | Pending |
| CAL-03 | Phase 4 | Pending |
| CAL-04 | Phase 4 | Pending |
| UI-01 | Phase 4 | Pending |
| UI-02 | Phase 4 | Pending |
| UI-03 | Phase 4 | Pending |
| UI-04 | Phase 4 | Pending |
| UI-05 | Phase 4 | Pending |
| UI-06 | Phase 4 | Pending |
| UI-07 | Phase 4 | Pending |
| UI-08 | Phase 4 | Pending |
| UI-09 | Phase 4 | Pending |
| UI-10 | Phase 4 | Pending |
| ZWO-01 | Phase 5 | Pending |
| ZWO-02 | Phase 5 | Pending |
| ZWO-03 | Phase 5 | Pending |
| ZWO-04 | Phase 5 | Pending |
| ZWO-05 | Phase 5 | Pending |
| IOS-01 | Phase 5 | Pending |
| IOS-02 | Phase 5 | Pending |
| IOS-03 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 63 total
- Mapped to phases: 63
- Unmapped: 0 ✓

---
*Requirements defined: 2026-06-19*
*Last updated: 2026-06-19 after roadmap creation*
