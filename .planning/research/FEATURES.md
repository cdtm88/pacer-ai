# Features Research: PacerAI

**Domain:** Adaptive AI cycling coach (beginner, general fitness + weight loss, smart trainer + Zwift)
**Researched:** 2026-06-19
**Competitive context:** TrainingPeaks, Wahoo SYSTM, Zwift Training Plans, TrainerRoad, intervals.icu, Xert, Athletica.ai, JOIN

---

## Table Stakes

Features users expect from any serious training plan tool. Absence causes immediate abandonment.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Structured weekly plan with explicit session targets | Every competing app delivers this; no targets = "just ride" advice | Medium | Must be periodised (aerobic base emphasis for beginner) |
| Per-session intensity prescription | Users need to know what to do, not just when | Low | RPE + HR first, power targets once FTP estimated |
| Plan adapts when life disrupts it | The #1 churn driver: rigid plans that don't flex | High | Missed sessions, illness, schedule changes must trigger re-plan |
| Historical ride log / activity feed | Users need to see what they've done | Low | Simple list + per-ride TSS/IF/duration; no chart required for MVP |
| Explanation of why plan changed | Adaptive re-planning without explanation feels arbitrary and erodes trust | Medium | Must cite data point and principle used |
| Mobile-usable during session | Session view consumed on phone beside trainer; small text = unusable | Medium | Large-font stepper + timer; iOS Safari PWA constraints apply |
| Progress feedback | Beginner needs reassurance that effort is accumulating | Low-Medium | TSB/form readout is sufficient; full PMC chart is Phase 2 |
| Safe onboarding with no prior knowledge assumed | Competitor gap: most apps assume FTP or fitness history | Medium | Conversational interview; zero knowledge start is core value |
| ZWO export to Zwift | User's primary training environment is Zwift on Kickr Core | Medium | Power targets are FTP-relative; pre-FTP sessions export as RPE blocks with a flat low-power target |

**Cold-start handling is table stakes for this specific user.** Every competitor either forces a ramp test or requires importing history. Beginner who cannot do a 20-minute test and has no prior data will immediately leave any app that gates plan creation behind a test.

---

## Differentiators

Features that set PacerAI apart. Not universally expected, but create strong retention and word-of-mouth.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Conversational onboarding interview | Feels like a real coach intake; surfaces injury status, schedule, and motivation naturally | High | LLM-led; produces persisted user profile; back-protective constraints emerge here |
| Passive FTP estimation from ride data | No test anxiety; estimate improves silently as rides accumulate | High | CP model using maximal efforts from normal rides (Xert-style approach); needs at least 2-3 rides with hard efforts; must communicate uncertainty honestly |
| Adaptation transparency with cited principles | Agent explains every re-plan decision referencing a named sports-science principle + actual data | Medium | "Your ATL spiked to 68 TSS/day; ramp rate exceeds ACSM 10% guideline, so we dropped Thursday's threshold block" |
| In-app coaching chat | Asynchronous coaching Q&A; user asks "why am I tired?" and gets data-backed answer | High | Requires full session context window; agent must pull PMC state to answer load questions |
| Sports-science trust model | All physiological numbers traceable to deterministic tool-library calls; no LLM hallucination risk | High | Unique architectural guarantee; no competitor makes this claim explicitly; can be surfaced to user as "coach shows its work" |
| Back-protective constraint layer | Specific modifications for users with back issues; not just generic "take it easy" | Medium | Constraints established in interview; applied automatically: cap volume, flag sprint efforts, flag excess standing time in ZWO |
| Google Calendar sync | Plan lives where user already manages their week | Medium | OAuth2 push; update on re-plan; two-way (mark done via calendar event) is Phase 2 |
| FIT file upload without platform lock-in | Manual upload keeps Zwift as the training environment; no API dependency or Terms-of-Service risk | Low | Wahoo Kickr + Zwift = real power data from day one; fitparse/fitdecode handles the parsing |

---

## Anti-Features

Things to deliberately not build. Each is a complexity trap, scope creep risk, or user confusion source.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Forced FTP test at onboarding | Intimidating and impossible for true beginners; exact value is less important than getting started | Start with RPE/HR; estimate FTP passively from rides |
| Strava integration | API rate limits, Terms-of-Service fragility, OAuth maintenance burden; explicitly out of scope | Manual .FIT upload is sufficient and more reliable |
| Social / community features | Completely orthogonal to core value; beginner fitness goals are personal | Focus coaching quality; social features are a distraction |
| Full three-line CTL/ATL/TSB PMC chart | Correct implementation is non-trivial (42-day / 7-day EWA seeding); beginners find it confusing without coaching | Expose TSB as a single "form" number in text; full PMC chart is Phase 2 |
| Nutrition tracking / calorie counting | Different problem domain; requires dietitian-level accuracy to be responsible; scope creep | Acknowledge weight-loss goal in plan design (Zone 2 emphasis, fat-oxidation sessions) without calorie prescriptions |
| Live Bluetooth power echo during Zwift | Chromium-only Web Bluetooth API; conflicts with Zwift's trainer control; adds hardware debugging surface | Export ZWO; user runs Zwift as the execution environment |
| Dark mode | Design system complexity for no functional value in MVP | Light mode only; no pure blacks; revisit Phase 2 |
| Multi-sport support (running, swimming) | Completely different physiological models; dilutes the cycling coaching quality | Cycling only; Wahoo Kickr is the explicit hardware target |
| Garmin Connect / Wahoo Cloud direct pull | OAuth complexity, partner API agreements, data freshness issues | Manual .FIT upload; user exports from Zwift |
| Race / event periodisation | Peaks, tapers, and A/B/C event priority require fundamentally different plan structure | General fitness periodisation only; no event goal |
| Coaching marketplace / multiple coaches | Multi-tenancy, payment, coach interface; entirely different product | Single-user personal tool; no monetisation in MVP |

---

## Feature Complexity Notes

### Cold-Start FTP Estimation (HIGH complexity, HIGH priority)
Requires accumulating maximal efforts from normal rides to fit a power-duration curve. Xert-style: extract CP and W' from efforts exceeding MPA threshold. Minimum viable: 2-3 rides with at least one near-maximal effort. Must:
- Communicate uncertainty ("estimated, not tested") throughout
- Fall back to RPE-only targets when confidence is LOW
- Update zones silently and notify user via chat when estimate changes
- Refuse to emit a number if insufficient data exists (capability-gap log)

### Adaptive Re-Planning (HIGH complexity, HIGH priority)
Triggers: missed session, uploaded ride significantly over/under target, user reports illness in chat, schedule change. Each trigger type needs a distinct re-planning heuristic:
- Missed session: redistribute or drop depending on position in block
- Over-performance: may advance a progression level
- Under-performance: assess whether systemic fatigue or one-off
- Schedule disruption: shift block, not individual session

### ZWO Export for Pre-FTP Sessions (MEDIUM complexity)
ZWO format uses power targets as FTP multiples. For sessions before FTP is known:
- Use a conservative flat target (e.g. 50-55% of estimated/assumed FTP)
- Include text description segments with RPE cues
- Document the assumed FTP used in the export so user can re-export after estimation

### During-Session View on iOS Safari (MEDIUM complexity)
PWA on iOS Safari has meaningful constraints:
- No background sync; session state must be checkpointed on tab focus events
- No reliable push notifications; next-interval alerts use visible countdown
- Screen must stay on: use `NoSleep.js` or the Screen Wake Lock API (Safari 16.4+)
- Large-font targets readable glancing from a trainer at 2 feet

### Google Calendar OAuth (MEDIUM complexity)
Google Calendar API requires OAuth2 consent flow. Key implementation details:
- Store refresh tokens securely (Supabase secrets); never in client
- On re-plan, update existing events (PATCH) rather than delete+create to preserve user edits
- Mark sessions as done by updating event color/description when FIT file arrives
- Scopes needed: `calendar.events` (not full `calendar` access)

### In-App Chat with Coaching Agent (HIGH complexity)
Chat is not cosmetic; it is the primary coaching surface. The agent must:
- Pull current PMC state, plan state, and user profile into context for every message
- Route numerical questions to tool library, never answer from LLM reasoning
- Log capability gaps when a user asks something outside the tool library
- Handle "I feel terrible today" → assess ATL/TSB and suggest recovery or adaptation

---

## Dependencies Between Features

```
Conversational onboarding interview
  → User profile (injury status, schedule, goals)
    → Plan generation (periodised, back-protective constraints)
      → ZWO export (per session)
      → Google Calendar sync (per session)

.FIT file upload (manual)
  → FIT parsing (power/HR/cadence/duration)
    → TSS/NP/IF computation (tool library)
      → PMC update (CTL/ATL/TSB)
        → Adaptive re-planning trigger
        → Passive FTP estimation (accumulates over rides)
          → Power zone recalculation
            → ZWO export (updated targets)

In-app chat
  → Requires: PMC state, plan state, user profile, tool library access
  → Feeds: adaptive re-planning (user-reported changes)
  → Feeds: capability-gap log (when agent cannot compute)

During-session view
  → Requires: session ZWO/plan data (read-only)
  → Optional: mark session complete (writes to history)
```

**Critical path for MVP success metric** (user completes interview → receives plan → uploads first FIT → plan adapts):

1. Onboarding interview + user profile persistence
2. Plan generation with RPE/HR targets (no FTP required)
3. FIT upload + TSS computation + PMC seeding
4. Adaptive re-planning with explanation

ZWO export and Google Calendar are high-value but not on the critical success path; they can be deferred one phase without breaking the core loop.

---

## Sports-Science Accuracy Requirements

All numbers below must come from the validated tool library. The LLM never emits these from its own reasoning.

| Metric | Standard | Failure Mode if Wrong |
|--------|----------|-----------------------|
| Power zones | Coggan/Allen 7-zone model | Under/over-training; injury |
| TSS | `(seconds × NP × IF) / (FTP × 3600) × 100` | PMC drift; bad load recommendations |
| NP | 30-second rolling average → ^4 → mean → ^(1/4) | Underestimates high-intensity work |
| CTL | 42-day exponentially-weighted average | Fitness trend wrong; false confidence |
| ATL | 7-day exponentially-weighted average | Fatigue wrong; overreaching risk |
| TSB | CTL(yesterday) - ATL(yesterday) | Form wrong; race-readiness calls wrong |
| FTP estimate | CP model (power-duration regression on maximal efforts) | All zones wrong; over/under-targeting |
| Load progression | ACSM ≤10% weekly TSS increase for beginners | Injury, overreaching, dropout |

The trust model is itself a differentiator. Surface it lightly in the UI ("Coach shows its work") to build confidence with a user who is scientifically curious but not an expert.
