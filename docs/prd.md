# PRD: PacerAI

> For `/gsd-new-project --auto @prd.md`. Capabilities below are written as
> discrete, testable statements so GSD can map each to a REQ-ID and into phases.
> The MVP / Phase 2 / Out-of-scope split is explicit. Read "Non-negotiable
> architecture" first; it must survive into PROJECT.md and the generated CLAUDE.md.

## Project description

PacerAI is an evidence-based, adaptive AI cycling coach for a beginner returning
to fitness (general fitness and weight loss; no event or competition). It
interviews the user from zero knowledge, builds a structured training plan, and
re-plans intelligently
as real ride data arrives as .FIT files. Web-first, mobile-responsive, with an
in-app chat. The user directs and designs but does not write code.

## Non-negotiable architecture (the trust model, must survive into PROJECT.md and CLAUDE.md)

The LLM owns judgement; a validated tool library owns numbers.

- An LLM agent (Anthropic API, tool use) makes every coaching decision:
  interviewing, designing plan structure, and adapting around missed sessions,
  holidays, fatigue, and performance.
- The LLM is forbidden from emitting any physiological number from its own
  reasoning. Every figure with a sports-science definition (training zones, TSS,
  IF, NP, FTP estimates, CTL/ATL/TSB, load-progression targets) must come from a
  validated function in the sports-science tool library, which also returns the
  named methodology it used.
- If a needed calculation has no tool, the agent does not improvise. It logs a
  structured entry to the application's runtime capability-gap log, tells the user
  in chat, and falls back to a validated method or qualitative reasoning with no
  fabricated number.

Any code path where the model could place a self-derived number into a plan is a
defect, regardless of how plausible the number looks.

## Users and context

- Primary user: beginner cyclist returning to fitness; goals are general fitness
  and weight loss. The system is user-agnostic and starts with zero knowledge.
- Injury status (including any back issues) is established through the interview,
  never assumed. When present, apply back-protective constraints (cap initial
  volume; avoid prolonged standing and sprint efforts early; flag load ramping too
  fast).
- Hardware available now: Wahoo Kickr Core 2 smart trainer plus Zwift, producing
  real power data from day one.
- Cold-start reality: the user has no FTP and cannot do a 20-minute or ramp test
  yet. This is a first-class supported case, not an error state.

## MVP capabilities (v1)

Each line is intended to become one requirement.

1. Conversational, LLM-led onboarding interview that establishes, from zero:
   self-reported baseline fitness, injury/medical status, equipment available,
   weekly time availability and schedule, and short- and long-term goals. Output is
   a persisted structured user profile.
2. Cold-start handling with no FTP: early sessions prescribed by RPE and heart rate
   (comfortable/conversational aerobic), not power targets; a working FTP is
   passively estimated from ride power data and introduced only as confidence grows;
   a formal test is offered, never forced.
3. Plan generation: the LLM produces a structured, periodised plan appropriate to a
   returning beginner (aerobic-base emphasis, sustainable progression,
   back-protective constraints surfaced in the interview). Every session has an
   explicit plan: objective, structure (warm-up / intervals / cool-down), targets
   (RPE/HR early, power later), and duration.
4. Sports-science tool library (the trusted core): deterministic, unit-tested
   functions, each citing its methodology:
   - calculate_power_zones(ftp) -> 7 Coggan/Allen zones
   - calculate_hr_zones(max_hr | lthr) -> HR zones
   - estimate_ftp_from_rides(rides) -> FTP estimate plus confidence (Critical Power /
     best-effort modelling; clearly labelled estimate)
   - compute_tss(ride) -> TSS, IF, NP (TrainingPeaks)
   - update_pmc(tss_history) -> CTL (fitness), ATL (fatigue), TSB (form)
     (Banister / PMC)
   - progress_load(current_ctl, target, constraints) -> safe weekly ramp targets
     (injury-aware caps)
   - validate_session_vs_actual(planned, actual) -> compliance %, deltas, flags
   Methodology sources to confirm at build time: Coggan/Allen power zones,
   TrainingPeaks PMC (Banister), ACSM training-load guidance, Seiler
   polarized-training research.
5. Agent enforces the trust model: every physiological number in any plan or message
   is traceable to a tool-library call (verifiable in logs); the agent never emits
   such numbers itself.
6. Runtime capability-gap logging: when the agent needs a quantitative method the
   tool library lacks, it appends a structured entry to the application's
   capability-gap log, surfaces a brief chat note, and falls back gracefully. This
   never expands what the agent can compute at runtime. (This is an application
   runtime artefact, distinct from GSD build planning.)
7. Manual .FIT file ingestion: user drags a .FIT file (Zwift or head unit) into the
   web app; the parser extracts power, HR, cadence, and duration; the system computes
   TSS/IF/NP and updates the PMC; the parsed ride feeds validate_session_vs_actual
   and the adaptive engine.
8. Adaptive re-planning: the plan adapts days and weeks ahead based on missed
   sessions, holidays/travel, actual performance, and accumulated training load;
   intensity and session type are decided dynamically (for example, swap threshold
   for recovery when fatigue is high).
9. Adaptation transparency: whenever the plan changes, the agent explains its
   reasoning by default in chat, citing the data and the principle behind the
   change. Every change is persisted to an adaptation log (trigger, reasoning shown,
   timestamp).
10. ZWO export: export a planned structured session as a valid .zwo workout file that
    Zwift can import, with power targets expressed correctly as % FTP and
    round-tripping cleanly into Zwift.
12. Web UI, desktop and mobile adaptive (PWA), light mode only for MVP. Screens:
    - Onboarding/interview: full-screen conversational flow ending in a profile
      confirmation summary.
    - Today/Home: today's session as a prominent card (objective, structure, targets,
      duration) with actions Start session, Export to Zwift, Mark done/missed; a
      compact next-few-days view; a plain-language form chip (fresh / balanced /
      fatigued, derived from TSB).
    - Agenda: scrollable list grouped by week; rows show date, type, duration, status;
      tap to expand the full session plan; intensity shown via zone colours.
    - History: past sessions with planned-vs-actual compliance, a small fitness-trend
      sparkline (7-30 day CTL trend), and tap-through to parsed ride detail
      (power/HR curves, TSS).
    - During-session: a large-font stepper. The current step is shown in large type
      (target plus duration), the next step queued below, later steps smaller; a timer
      auto-advances the highlight with no trainer data required. Must work on iOS
      Safari.
    - Chat: a dedicated tab; persistent conversation with the agent where adaptation
      reasoning and capability-gap notes appear and where the user logs subjective
      feedback and requests changes.
    - Navigation: mobile bottom tab bar (Today / Agenda / History / Chat); desktop
      left sidebar with the same destinations and wider multi-column layouts.

## MVP acceptance criteria

- A new user with no data completes the interview and receives a structured plan
  with explicit per-session targets.
- Every physiological number in any plan or message is traceable to a tool-library
  call, never the LLM (verifiable in logs).
- When asked for a method the library lacks, the agent does not invent a number: it
  logs a structured capability-gap entry, tells the user in chat, and falls back
  gracefully.
- Uploading a real Zwift .FIT updates training load and produces a planned-vs-actual
  comparison.
- Missing a session, or adding a holiday, causes the agent to re-plan and explain the
  change in chat.
- A planned session exports to a .zwo that imports cleanly into Zwift.
- The web app is usable and clean on both a phone and a desktop browser.

## Phase 2 capabilities (post-MVP, not part of v1)

- Telegram bot reusing the agent layer (webhook plus hosting). Top Phase 2 priority.
- Optional live power/cadence echo in the during-session view via the Web Bluetooth
  API. Constraints to record: Chromium-only (no iOS Safari); a smart trainer pairs to
  one controlling app at a time, so a live echo generally cannot co-exist with Zwift
  controlling the same Kickr; most useful for app-driven sessions without Zwift.
- Dark mode (re-mapped palette variant; do not invert).
- A dedicated Fitness screen with the full three-line CTL/ATL/TSB PMC for users who
  want the depth.

## Out of scope (do not build; not on the roadmap)

- Strava integration of any kind.
- Any social, sharing, or community features.
- Garmin/Zwift direct auto-pull (manual .FIT upload only).

## Suggested stack (substitutable, but keep the agent/tool split)

- Frontend: React + Vite + Tailwind, responsive PWA.
- Backend: Python (FastAPI) preferred (eases FIT parsing and sports-science maths).
- LLM: Anthropic API, Claude, with native tool use.
- Database: Postgres (Supabase or Railway).
- FIT parsing: fitparse / fitdecode.
- Hosting: Vercel (frontend) plus Railway (API/DB).

## Build-order guidance (preferred phase shape)

1. Sports-science tool library plus unit tests (the trust anchor) before anything else.
2. Agent plus tool wiring, including the capability-gap rule; prove via logs that all
   numbers come from tools and gaps are logged, never improvised.
3. Interview -> profile -> first plan (cold-start, no FTP).
4. FIT upload -> training-load update -> adaptive re-planning loop.
5. Web UI (the screens above).
6. ZWO export for Zwift.
7. Phase 2 items.

## Design system (for the UI phase)

- Tone: warm and human but professional. No hand-drawn/sketchy styles, no Comic Sans
  or rounded "friendly" display fonts, no pastel-soft looks. Warmth from colour and
  copy. One clean contemporary sans (for example Inter) for UI and headings.
- Light mode only for MVP. No pure blacks anywhere.
- Primary blue scale (anchor blue-6 = #228BE6):
  blue-0 #E9F3FC, blue-1 #CEE5FA, blue-2 #ABD3F6, blue-3 #7FBCF0, blue-4 #53A5EC,
  blue-5 #3494E8, blue-6 #228BE6, blue-7 #1B73C0, blue-8 #155EA0, blue-9 #104C82.
- Neutrals (faint blue undertone, no pure black): --ink #1A2230 (primary text),
  --ink-2 #5F646E (secondary, body-safe), --ink-3 #888C93 (muted, large text only),
  --line #DFE0E2, --line-2 #EDEDEE, --surface #FFFFFF, --bg #F9F9FA, --bg-2 #F6F6F7.
- Warm accent and semantic: --warm #FF8A5C, --warm-soft #FFEDE7, --amber #F0A030,
  --zone-recovery/--good #2B8A5B, --zone-endurance #228BE6, --zone-tempo #F0A030,
  --zone-threshold #E8590C, --zone-vo2 #C92A2A, --warn #9A6700, --bad #C0341D.
- Contrast rules (verified, must follow): #228BE6 is 3.56:1 on white, so it is for
  large text, buttons, and fills only, never small body text; small blue text uses
  blue-7 #1B73C0 (4.95:1); body copy uses --ink or --ink-2. When dark mode arrives in
  Phase 2, re-map the palette to a dark variant; do not invert.

## House conventions

- No em dashes in any generated content or copy (use commas, semicolons, colons, or
  separate sentences).
- Write tests for the tool library and for the "numbers come only from tools"
  guarantee.
