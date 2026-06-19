# Pitfalls Research: PacerAI

**Domain:** Adaptive AI cycling coach web app
**Researched:** 2026-06-19
**Overall confidence:** MEDIUM (sports-science methodology from peer-reviewed sources; LLM/PWA from practitioner community)

---

## Sports-Science Accuracy

### CRITICAL: CP Model Gives Garbage with Sparse Beginner Data

**What goes wrong:** The 2-parameter Critical Power model (CP + W') requires multiple maximal efforts spanning 2-15 minutes across different sessions to produce a stable fit. A beginner with 1-3 rides has no maximal efforts at all. The model will still produce a number — it will just be nonsense. FTP and CP differ by up to 24W (±12W individual variation) even in trained populations, so the two constructs are not interchangeable.

**Why it happens:** Developers treat CP fitting as a black box: pass in power data, receive FTP estimate. The model does not raise an error when data is insufficient; it silently produces a wildly wrong estimate.

**Consequences:** Zones computed from a bad FTP estimate are wrong. A beginner prescribed Zone 2 at 140W when their real aerobic threshold is 90W will either be working anaerobically (overtraining) or feel like the prescription is impossible. Both outcomes destroy trust.

**Prevention:**
- Require a minimum of 4 efforts with meaningful variance before emitting an FTP estimate.
- Tag every FTP estimate with a confidence level: `low` (< 4 efforts), `medium` (4-8), `high` (8+ with good variance).
- Display confidence level in the UI alongside the FTP number — never show it bare.
- During cold start, prescribe sessions by RPE/HR only. Do not prescribe power targets until FTP confidence reaches `medium`.
- Never let the FTP estimate precision claim exceed ±15W in low-confidence state.

**Warning signs:** The FTP estimate changes by more than 20% between uploads without a corresponding major fitness event.

**Phase:** Sports-science tool library (Phase 1). Confidence metadata must be a first-class field on the FTP estimate return type from day one.

---

### CRITICAL: TSS/NP/IF Calculation Has Several Exact-Arithmetic Traps

**What goes wrong:**

1. **Zero inclusion.** The NP algorithm (30-second rolling average → 4th power → mean → 4th root) must INCLUDE zeros (coasting, stopped). Excluding zeros inflates average power and can produce paradoxical NP < average power, which breaks TSS.

2. **Power spikes from sensor dropouts.** A single corrupt record (e.g., 1500W spike from a Wahoo Kickr glitch) disproportionately inflates NP because of the 4th-power step. One 1-second spike at 1500W in a 1-hour ride adds roughly 3-5W to NP.

3. **Using average power instead of NP for TSS.** On variable-intensity rides, average power understates the physiological cost by 10-25%. TSS formula: `TSS = (duration_seconds × NP × IF) / (FTP × 3600) × 100`. Using average power here understates TSS significantly.

4. **Short rides where the 30-second window is meaningless.** Rides under 5 minutes produce unreliable NP. Do not compute TSS for rides under 10 minutes; return null with explanation.

5. **IF > 1.05 sanity check.** IF = NP / FTP. If IF > 1.05 for a ride longer than 1 hour, the FTP estimate is stale or the data is corrupt — flag it rather than silently accepting it.

**Prevention:**
- Implement NP with explicit zero-inclusion documented in code comments.
- Add a spike-detection pass before NP calculation: clip power values above `FTP × 3` to `FTP × 3` (or flag and discard the record).
- Unit-test NP with: all-zeros input, single-spike input, constant-power input (NP = AP), ramp input.
- Return `null` for TSS on rides shorter than 10 minutes.
- Validate IF range before persisting TSS.

**Warning signs:** NP lower than average power, IF > 1.1 on a long steady ride, TSS values that double or halve unexpectedly.

**Phase:** Sports-science tool library (Phase 1). These are unit-testable mathematical contracts.

---

### MODERATE: PMC Initialization Produces Misleading TSB During Cold Start

**What goes wrong:** CTL and ATL are exponentially-weighted averages with time constants of 42 and 7 days respectively. Starting both at zero is correct but produces systematically misleading TSB (TSB = CTL - ATL) for the first 6 weeks: TSB will be near-zero or positive because both values are growing together, masking accumulating fatigue.

**Why it happens:** Developers initialize CTL=0, ATL=0, and immediately display the TSB chart to users as if it's meaningful. The first 42 days are a model warm-up period, not real data.

**Consequences:** User sees TSB=+5 (nominally "fresh") on day 14 after training hard, feels fine ignoring fatigue warnings. Or they feel exhausted with TSB=0 and trust the number over their body, causing injury.

**Prevention:**
- Do not display TSB or the PMC chart until at least 28 days of data exists.
- Display a "building baseline" state for the first 28 days with a ride count and days-remaining indicator.
- CTL ramp rate guard: if weekly CTL increase exceeds 8 points, flag for load reduction regardless of TSB.
- For beginner returning to fitness (PacerAI's exact user), cap initial weekly TSS progression at a conservative ramp (10% per week) enforced at the tool layer, not just in coaching recommendations.

**Warning signs:** CTL line on PMC is a perfect exponential curve with no plateaus (indicates no rest weeks planned); TSB always positive in early weeks.

**Phase:** Sports-science tool library (Phase 1) for calculation; plan generation (Phase 3) for the ramp-rate guard.

---

### MODERATE: Coggan Zone Boundary Off-by-One and Recompute Failures

**What goes wrong:** The 7 Coggan zones use percentage-of-FTP thresholds. Common implementation mistakes:

1. **Boundary direction errors.** Zone 2 is 56-75% of FTP. Using `>= 56 and <= 75` means the boundary value (exactly 75W at 100W FTP) is in both Zone 2 and Zone 3. Use `>= lower and < upper` exclusively.

2. **Treating zone boundaries as exact.** Power zones are physiological guidelines with ±5% individual variation. Prescribing "ride at exactly 145W" to a beginner ignores this and creates anxiety when they hit 148W.

3. **Stale zones after FTP update.** Zones are derived from FTP. If FTP is updated (even a cold-start estimate revision) and zones are not recomputed, the agent prescribes the wrong targets. Stale zones are a silent error — the numbers look plausible.

4. **Zone 3 grey-zone trap.** Prescribing Zone 2 for aerobic base rides to a beginner who cannot hold the lower end leads them to drift into Zone 3. Zone 3 is physiologically suboptimal: too hard to recover from, too easy to drive adaptation. Aerobic base work for beginners should target Zone 2 with explicit upper-bound enforcement.

**Prevention:**
- Implement zone lookup as `zone_for_power(watts, ftp)` returning a zone enum; boundary logic in one place only.
- Store `ftp_used_for_zones` alongside zone config; recompute zones any time FTP changes.
- Prescribe zones as ranges (e.g., "140-155W, low Zone 3") not single values.
- For beginner aerobic base: upper bound hard-cap at Zone 2 ceiling (75% FTP).

**Warning signs:** Zone boundaries do not divide evenly across the power range, or zone labels disagree with TrainingPeaks for the same FTP value.

**Phase:** Sports-science tool library (Phase 1).

---

## LLM Trust-Model Violations

### CRITICAL: System Prompt Constraint Alone Does Not Prevent Number Emission

**What goes wrong:** Adding "never emit physiological numbers" to the system prompt reduces but does not eliminate hallucinated numbers. Models comply inconsistently, especially when the user asks directly ("what's my FTP?") or when the model is completing a long analytical chain that naturally arrives at a number. The model will emit the number because it looks correct to the model, not because the tool returned it.

**Why it happens:** The system prompt is a soft constraint. Models trained on sports content have strong prior knowledge of FTP values and will emit plausible numbers even when instructed otherwise, particularly when conversation context contains prior tool results that contain numbers.

**Consequences:** A hallucinated FTP of 180W (when real estimate is 140W) produces Zone 4 targets at what should be Zone 2. A beginner following this for two weeks accumulates dangerous fatigue.

**Prevention:**
- Enforce at the parsing layer, not just the prompt: after every assistant response, run a regex/NLP check for numeric patterns that match physiological quantities (e.g., `\d{2,3}W`, `FTP\s*[=:]\s*\d+`, `TSS\s*[=:]\s*\d+`). If found without a preceding `tool_result` block containing those values, reject the response and retry with an explicit correction injected.
- All physiological tool functions must return values in a structured schema that the agent references by interpolation, not by restating from memory.
- Add a compliance test suite: prompt the agent without any prior tool results and ask for FTP; assert the response contains a tool call, not a number.
- Log every agent response with a `has_unsourced_numbers: true/false` flag. Alert on any `true`.

**Warning signs:** Agent response contains a watt value that does not appear in any `tool_result` in the same conversation turn; response contains "approximately X watts" without attribution.

**Phase:** Agent core (Phase 2). Compliance test suite should gate Phase 2 completion.

---

### CRITICAL: Tool-Calling Loops — Infinite and Zombie Variants

**What goes wrong:** Two distinct failure modes:

1. **Infinite loop.** The agent calls a tool, gets an ambiguous result (e.g., "estimate_ftp: insufficient data"), and retries with the same arguments 137 times without adaptation. This burns API tokens, violates rate limits, and never terminates.

2. **Missing tool result.** The agent calls `compute_tss` but the tool throws an exception. The agent receives no `tool_result`. Without explicit handling, some agent frameworks pass `None` or an empty result back to the model, which then inverts and fabricates a result — exactly the trust-model violation above.

3. **Context bloat.** After 10+ tool calls in one conversation, the context fills with tool results. The model can no longer locate relevant prior outputs and begins contradicting earlier tool results or ignoring them.

**Prevention:**
- Max 3 retries per tool per conversation turn. After 3 failures, call `log_capability_gap(tool_name, reason)` and tell the user gracefully.
- All tool wrappers must return `{"status": "success"|"error"|"insufficient_data", "value": ..., "reason": ...}`. Never return bare values or throw unhandled exceptions to the agent.
- Tool call deduplication: maintain a `(tool_name, args_hash)` set per turn; if a call is a duplicate, short-circuit and return the cached result.
- Context summarization: after 8 tool calls in a conversation, inject a context summary message replacing stale tool results.
- Structured SUCCESS signal: all tool returns end with `"status": "success"` so the model has an unambiguous termination signal.

**Warning signs:** API spend per conversation exceeds 3x baseline; logs show the same `(tool_name, identical_args)` appearing more than twice in one turn.

**Phase:** Agent core (Phase 2). Retry logic and deduplication must be built before the agent handles real FIT data.

---

### MODERATE: Agent Fabricates Tool Outputs When Tool Is Slow or Absent

**What goes wrong:** If a tool call times out or returns an error, the model sometimes fabricates a plausible-looking tool result in its reasoning and proceeds. This is particularly risky for sports-science tools because FTP values, zone boundaries, and TSS are all "reasonable-sounding" numbers that a model can generate confidently and incorrectly.

**Prevention:**
- All tools in the sports-science library must return within 2 seconds. If an operation might exceed this, return a job ID and poll — never leave the tool call hanging.
- When a tool errors, the agent conversation must include the error explicitly: `tool_result: {"status": "error", "reason": "..."}`. Never suppress errors.
- Add an integration test that deliberately fails every tool and asserts the agent's response contains no numeric physiological data.

**Phase:** Agent core (Phase 2) + sports-science library (Phase 1) for the timeout contracts.

---

## FIT File Parsing

### CRITICAL: Zwift FIT Files Are Not Spec-Compliant

**What goes wrong:** Zwift produces FIT files that include manufacturer-specific developer data fields, non-standard message types, and in some cases records where the power field is absent (particularly for running activities uploaded by error, or early versions of the Zwift app). Additionally:

1. **Discrepancies vs Garmin.** When a Wahoo Kickr is paired to both Zwift and a Garmin, Zwift reports systematically higher average and normalized power with lower coasting time. This is a Zwift-side data processing difference, not a parsing error — but it means FTP estimates from Zwift FIT data are slightly inflated vs head-unit data.

2. **Truncated files.** If the user stops the upload mid-file (poor connection), fitparse crashes on CRC validation. fitdecode with `error_handling='warn'` recovers partial data; fitparse does not.

3. **Paused segments.** Zwift marks paused periods with power=0 (not as gaps). These must be detected and included in NP calculation (as zeros), not stripped.

4. **Missing GPS fields.** Indoor Zwift rides have no GPS. GPS-dependent fields (latitude, longitude, altitude) will be absent. Any code path that assumes GPS fields exist will KeyError.

5. **Manufacturer-specific fields.** Zwift adds developer data (e.g., `enhanced_avg_respiration_rate`, proprietary segment data). fitdecode returns these as unknown field names; do not crash on unknown fields.

**Prevention:**
- Use `fitdecode` not `fitparse` as the parsing library. Instantiate with `error_handling=fitdecode.ErrorHandling.WARN`.
- Never access power/HR/cadence fields without existence checks: `record.get_value('power', fallback=None)`.
- After parsing, validate: minimum record count (> 10), has at least some non-zero power values, duration > 60 seconds.
- Parse test suite must include: a real Zwift FIT file, a truncated FIT file, a FIT file with zero power throughout.

**Warning signs:** `KeyError` on GPS fields; CRC validation error crashing the upload; TSS=0 on a ride that clearly had effort.

**Phase:** FIT ingestion (Phase 3). The parse-and-validate pipeline must be built and tested against real Zwift files before the adaptive agent relies on it.

---

### MODERATE: Power Data Quality from Smart Trainers

**What goes wrong:** Smart trainers (Wahoo Kickr Core) have known power accuracy limitations:

1. **Calibration drift.** Kickr Core accuracy is ±2% when calibrated; can drift to ±5% between spin-downs. Two identical rides a week apart can show 8-10W difference due to calibration state, not fitness.

2. **ERG mode power spikes.** When ERG mode adjusts resistance, there is a brief overshoot spike (1-3 seconds at 2-3x target power). This inflates NP.

3. **Flywheel coast-down artifacts.** At the end of an interval when power drops, flywheel inertia maintains apparent power for 1-2 seconds before reading correctly.

**Prevention:**
- Spike filter: clip any power record that exceeds `previous_record × 3` or `FTP × 4` to the previous record value (or zero). Apply before NP calculation.
- Document calibration-drift uncertainty in FTP estimate confidence — if two rides produce estimates 10W+ apart, prefer the higher one (smart trainers are more likely to underread when under-calibrated).
- Surface calibration reminder to user after every 10 rides or 30 days.

**Phase:** Sports-science tool library (Phase 1) for the spike filter; UX hint in plan view (Phase 4).

---

## Adaptive Re-Planning

### CRITICAL: Single-Event Overreaction Destroys User Trust

**What goes wrong:** The agent replans the entire training schedule after one missed session or one unexpectedly hard ride. The user logs in Monday to find their entire week shifted, volume reduced by 30%, and next month's structure changed — because they skipped Sunday's ride.

**Why it happens:** The naive implementation triggers a full replan on every FIT upload. The replan algorithm optimizes for "correct load given current state" without distinguishing micro-signals (one data point) from macro-signals (trend over multiple sessions).

**Consequences:** Users feel the plan is unstable and cannot be relied upon. They stop following it or stop uploading data. Research from Athletica.ai shows this is the primary reason users abandon adaptive coaching tools.

**Prevention:**
- Distinguish micro-adjustments (next 1-3 sessions: adjust targets, mark missed session) from macro-replanning (restructure weeks or phases). Apply micro-adjustments on every upload; require a macro trigger.
- Macro replan triggers (require 2+ signals): (a) 3+ missed sessions in a rolling 14-day window, (b) FTP estimate changes by >10%, (c) PMC CTL ramp rate exceeds safe limits for 2+ consecutive weeks, (d) user explicitly requests a replan.
- Never change more than 30% of session positions in a single replan. If the optimal replan would change more, surface it as a proposal for user confirmation.
- Always explain the replan in chat before showing changes: "I noticed X and Y, so I'm suggesting Z. Here's what changes..."

**Warning signs:** The plan differs significantly each time the user opens the app without uploading new data (indicates over-sensitivity to stale data); user feedback mentions the plan being "all over the place."

**Phase:** Agent + plan generation (Phase 3). Replan trigger logic must be a named policy with unit tests.

---

### MODERATE: Underreaction — Plan Ignores Accumulating Fatigue

**What goes wrong:** The opposite failure: the agent applies only micro-adjustments and never restructures the plan even when the athlete is clearly accumulating fatigue over weeks. TSB becomes deeply negative, CTL ramp is unsustainable, but the plan continues as written because no single session triggered a macro replan.

**Prevention:**
- Weekly automated check (not tied to uploads): evaluate rolling 14-day CTL ramp rate and TSB trend. If CTL ramp > 8 points/week for 2 consecutive weeks, automatically insert a recovery week.
- If the user misses sessions for 5+ consecutive days with no explanation, prompt in chat — do not silently skip.

**Phase:** Agent + plan generation (Phase 3).

---

### MODERATE: Plan Instability from Cascading Reschedules

**What goes wrong:** The replan moves a session by 1 day. That shift conflicts with the next session. The next session moves. That session now falls on a rest day, which moves the rest day. Within one replan operation, 8 of 14 sessions have shifted dates. The plan looks completely different even though only one session needed adjusting.

**Prevention:**
- Replan algorithm must treat session anchors (user-declared fixed days) as hard constraints.
- Implement a "minimum disruption" objective: prefer solutions that preserve the greatest number of planned session dates.
- After generating a replan candidate, compute a disruption score (number of sessions that moved, total days shifted). If score exceeds a threshold, truncate to micro-adjustment only and queue the macro replan for user review.

**Phase:** Plan generation (Phase 3).

---

## Calendar and ZWO Integration

### CRITICAL: OAuth Refresh Token Expires After 7 Days in Testing Mode

**What goes wrong:** When the Google OAuth consent screen is in "Testing" (External, unverified) status — which is where every app starts — issued refresh tokens expire after 7 days. After day 7, all calendar operations silently fail with `invalid_grant`. The user's plan stops syncing to Google Calendar and they receive no notification.

**Why it happens:** Developers test OAuth flow once, it works, they move on. The token expires a week later during real use. Most developers don't notice because they never test the refresh path.

**Consequences:** Calendar events stop being created. User checks their Google Calendar for this week's sessions and sees nothing. They assume the app is broken.

**Prevention:**
- Move the OAuth app to "Production" status before any real user testing (even single-user). The verification process for a personal-use app with Calendar scope is minimal.
- Alternatively: add `access_type=offline` and `prompt=consent` to force token re-issuance on every auth, and store the new refresh token each time.
- Implement token health checks: before any Calendar API call, check token expiry; if < 5 minutes remaining or refresh fails, surface a re-auth prompt in the UI (never crash silently).
- Store refresh tokens encrypted in the database; never in browser local storage.
- Add an integration smoke test that calls the Calendar API with a stored token 8 days after issuance.

**Warning signs:** Calendar sync stops working exactly 7 days after a user connects Google Calendar; `invalid_grant` errors in backend logs.

**Phase:** Google Calendar integration (Phase 4). OAuth flow architecture must include the token lifecycle from day one.

---

### MODERATE: ZWO File Format Inconsistency Causes Silent Zwift Import Failure

**What goes wrong:** ZWO is XML with no formal schema. The Zwift importer is strict on some attributes and silently ignores others:

1. **Power values are ratios, not watts.** `Power="0.75"` means 75% of FTP, not 75 watts. Generating `Power="150"` for a 150W target causes Zwift to prescribe 15,000% of FTP.

2. **Missing `sportType` field.** Zwift silently rejects workout files where `<sportType>bike</sportType>` is missing or misspelled. No error is shown to the user.

3. **Cadence fields must be omitted, not zeroed.** Setting `Cadence="0"` causes Zwift to display a 0 rpm target. Omit the field entirely if no cadence target is intended.

4. **Inconsistent element casing.** ZWO element names mix StartCase and camelCase in the same file. Zwift's importer is case-sensitive on some elements. Use an existing validated ZWO template as the base, not a from-scratch XML builder.

5. **`ftpoverride` not universally honored.** Some Zwift versions ignore the `ftpoverride` element. Do not rely on it to embed the user's FTP in the exported file; always export using relative-FTP ratios.

**Prevention:**
- Maintain a validated ZWO template file. Generate new workouts by substituting values into the template, not by building XML from scratch.
- Unit test: parse the generated ZWO with an XML parser and assert all `Power` values are between 0.0 and 2.0 (ratios), `sportType` is present and equals `bike`.
- Validate exported ZWO against at least one Zwift import before shipping the feature. Real Zwift validation is required — schema validation alone is insufficient.

**Warning signs:** Zwift shows "workout not found" or imports with wildly wrong power targets; user reports cadence target of "0 rpm" during a session.

**Phase:** ZWO export (Phase 4).

---

## PWA and Mobile

### CRITICAL: Screen Wake Lock Broken in Installed iOS PWA Before iOS 18.4

**What goes wrong:** The Screen Wake Lock API (`navigator.wakeLock.request('screen')`) works in iOS Safari browser tabs from iOS 16.4+, but was broken in installed PWAs (added to home screen) until iOS 18.4. Before iOS 18.4, the API call returns success but the screen still sleeps. This is the exact deployment mode PacerAI targets for during-session use.

**Why it matters:** A beginner cyclist on a Wahoo Kickr glances at their phone for power targets. The screen locks after 30 seconds. They take their hand off the bars to unlock it. This is a safety issue, not just a UX annoyance.

**Consequences:** The during-session view becomes useless on iOS < 18.4 if no fallback exists.

**Prevention:**
- Detect iOS version on PWA launch. If < 18.4, use NoSleep.js (plays a silent audio loop to prevent sleep) as fallback.
- Display a one-time banner: "For best experience during sessions, keep your screen brightness on and screen timeout set to 'Never' in Settings."
- Test during-session view on an actual iOS device in installed PWA mode before shipping.
- Implement: attempt Wake Lock API, on failure or on iOS < 18.4 detection, activate NoSleep.js.

**Warning signs:** Screen locks during session on test device; Wake Lock API reports success but screen still dims.

**Phase:** During-session view (Phase 5). This must be in the acceptance criteria for that screen.

---

### MODERATE: Background Tab and Audio Suspension on iOS

**What goes wrong:** When the user switches away from the PacerAI PWA tab on iOS (e.g., to check a Zwift screenshot, or to receive a message), iOS Safari suspends JavaScript execution and all Web Audio. Any audio coaching cues, countdown timers, or real-time updates stop. When the user returns, the session clock may be wrong.

**Prevention:**
- The during-session view should be designed as "glanceable" — the user should not need to switch away from it. Display all relevant information (current interval, next interval, time remaining, power target) on one screen without requiring navigation.
- If using a session timer, use `Date.now()` deltas rather than counting intervals — this survives suspension.
- Use `visibilitychange` event to detect tab-hide/show and resync state on return.
- Audio coaching cues: acceptable to lose these on iOS background; document this limitation explicitly in UI.

**Warning signs:** Timer shows 5 minutes elapsed when only 2 minutes passed; audio cue plays at wrong time after returning to app.

**Phase:** During-session view (Phase 5).

---

### MINOR: PWA Install Prompt Not Available on iOS Safari

**What goes wrong:** On Android, the browser displays an "Add to Home Screen" install prompt automatically. iOS Safari provides no such prompt — users must manually navigate to Share > Add to Home Screen. Most users do not know this.

**Prevention:**
- On first visit from iOS Safari (detect via user-agent), display an in-app instructional banner: "For the best experience, add PacerAI to your Home Screen: tap Share then 'Add to Home Screen'."
- Suppress the banner after the user dismisses it or after 3 sessions.

**Phase:** Shell/PWA setup (Phase 1).

---

## Phase Mapping Summary

| Pitfall | Severity | Phase to Address |
|---------|----------|-----------------|
| CP model sparse data failure | CRITICAL | Phase 1: Sports-science library |
| TSS/NP zero-inclusion and spike corruption | CRITICAL | Phase 1: Sports-science library |
| PMC cold-start misleading TSB | MODERATE | Phase 1 (calculation) + Phase 3 (UX) |
| Coggan zone boundary and stale recompute | MODERATE | Phase 1: Sports-science library |
| LLM number emission — prompt constraint insufficient | CRITICAL | Phase 2: Agent core |
| Tool-calling infinite loops | CRITICAL | Phase 2: Agent core |
| Tool fabrication on timeout/error | MODERATE | Phase 1 (timeouts) + Phase 2 (agent) |
| Zwift FIT non-compliance (truncation, GPS, spikes) | CRITICAL | Phase 3: FIT ingestion |
| Smart trainer power accuracy/calibration drift | MODERATE | Phase 1 (spike filter) + Phase 4 (UX hint) |
| Single-event overreaction in replan | CRITICAL | Phase 3: Plan generation |
| Fatigue underreaction | MODERATE | Phase 3: Plan generation |
| Cascading reschedule instability | MODERATE | Phase 3: Plan generation |
| Google OAuth 7-day token expiry | CRITICAL | Phase 4: Calendar integration |
| ZWO power ratio vs watts confusion | CRITICAL | Phase 4: ZWO export |
| ZWO missing sportType field | MODERATE | Phase 4: ZWO export |
| iOS Wake Lock broken < 18.4 | CRITICAL | Phase 5: During-session view |
| Background tab suspension | MODERATE | Phase 5: During-session view |
| PWA install discoverability on iOS | MINOR | Phase 1: Shell setup |

---

## Sources

- [Frontiers: Relationship Between Critical Power Test and 20-min FTP Test](https://www.frontiersin.org/journals/physiology/articles/10.3389/fphys.2020.613151/full) (MEDIUM — peer reviewed)
- [TrainingPeaks: FTP vs Critical Power](https://www.trainingpeaks.com/coach-blog/ftp-vs-critical-power/) (MEDIUM — industry authority)
- [TrainingPeaks: Normalized Power](https://help.trainingpeaks.com/hc/en-us/articles/204071804-Normalized-Power) (MEDIUM — primary source)
- [Garmin Forums: NP Algorithm](https://forums.garmin.com/sports-fitness/cycling/f/edge-530/350537/algorithm-for-computing-the-normalized-power) (LOW — community)
- [TrainingPeaks: CTL/ATL/TSB Guide](https://www.trainingpeaks.com/coach-blog/a-coachs-guide-to-atl-ctl-tsb/) (MEDIUM — industry authority)
- [Medium: LLM Tool-Calling Infinite Loop](https://medium.com/@komalbaparmar007/llm-tool-calling-in-production-rate-limits-retries-and-the-infinite-loop-failure-mode-you-must-2a1e2a1e84c8) (LOW — practitioner)
- [ZenML: Agent Deployment Gap](https://www.zenml.io/blog/the-agent-deployment-gap-why-your-llm-loop-isnt-production-ready-and-what-to-do-about-it) (LOW — practitioner)
- [MagicBell: PWA iOS Limitations 2026](https://www.magicbell.com/blog/pwa-ios-limitations-safari-support-complete-guide) (LOW — industry blog)
- [Apple Developer Forums: iOS Audio Lockscreen PWA](https://developer.apple.com/forums/thread/762582) (MEDIUM — first-party)
- [Rene Saarsoo: Why the ZWO format sucks](https://nene.github.io/2021/01/14/zwo-sucks) (LOW — practitioner analysis)
- [Nango: Google OAuth invalid_grant](https://nango.dev/blog/google-oauth-invalid-grant-token-has-been-expired-or-revoked/) (LOW — practitioner)
- [Google Developers: OAuth2](https://developers.google.com/identity/protocols/oauth2) (HIGH — primary source)
- [fitdecode GitHub](https://github.com/polyvertex/fitdecode) (MEDIUM — primary source)
- [BMC Research Notes: AI exercise plan trust](https://bmcresnotes.biomedcentral.com/articles/10.1186/s13104-025-07172-9) (MEDIUM — peer reviewed)
- [Zwift Forums: FIT file power issues](https://forums.zwift.com/t/issue-with-power-data-recorded-in-zwift-fit-file/8267) (LOW — community)
