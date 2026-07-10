# Phase 5: During-Session and ZWO Export - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-21
**Phase:** 05-during-session-and-zwo-export
**Areas discussed:** Step advance behavior, ZWO export flow, Pre-FTP ZWO handling, Session data routing

---

## Step Advance Behavior

### Q1: Auto or manual advance when timer hits 0?

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-advance | Timer hits 0, brief 3-second countdown warning, then next step starts automatically. Keeps hands-free use on the bike. | ✓ |
| Manual tap only | Timer shows 0 and stays; user taps "Next step" to advance. No surprise transitions mid-effort. | |
| Auto with cancel | Auto-advances after 5 seconds with a visible "Cancel" tap area. | |

**User's choice:** Auto-advance (recommended)
**Notes:** 3-second countdown warning before transition.

### Q2: Should users be able to manually skip ahead?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, tap-to-advance | Tapping current step or a "Skip" button advances immediately. | ✓ |
| No manual skip | Timer only — no skipping. | |

**User's choice:** Yes, tap-to-advance

### Q3: What happens after the last step?

| Option | Description | Selected |
|--------|-------------|----------|
| Session complete screen | Brief completion view (total time, steps done) + "Done" navigates to Today. | ✓ |
| Navigate directly to Today | Auto-navigate immediately, no intermediate screen. | |

**User's choice:** Show a "Session complete" screen

---

## ZWO Export Flow

### Q1: One-click download or two-step with preview?

| Option | Description | Selected |
|--------|-------------|----------|
| One-click download | Tap triggers GET endpoint; browser downloads .zwo immediately. | |
| Two-step with preview | Modal shows session name, FTP used, step summary; then Download button. | ✓ |

**User's choice:** Two-step with preview

### Q2: File naming convention?

| Option | Description | Selected |
|--------|-------------|----------|
| Date + type | e.g. 2026-06-21-endurance.zwo | ✓ |
| Session objective | Slugified from objective field (long, inconsistent). | |

**User's choice:** Date + type

### Q3: Backend or frontend ZWO generation?

| Option | Description | Selected |
|--------|-------------|----------|
| Backend FastAPI endpoint | GET /sessions/{id}/export.zwo, Python XML, easy to test. | ✓ |
| Frontend only | Generate XML in browser from loaded data. Avoids round-trip but less testable. | |

**User's choice:** Backend FastAPI endpoint

---

## Pre-FTP ZWO Handling

### Q1: What FTP to assume when no estimate exists?

| Option | Description | Selected |
|--------|-------------|----------|
| Fixed 100W | Very conservative; all fractions safe for any beginner. | ✓ |
| Fixed 150W | Slightly more typical but higher risk of targets feeling wrong. | |
| Block export | Disable button until FTP is estimated. | |

**User's choice:** Fixed 100W

### Q2: Pre-FTP workout structure in .zwo?

| Option | Description | Selected |
|--------|-------------|----------|
| FreeRide + TextEvents | FreeRide segments with RPE text cues at interval start. Accurate to early session intent. | ✓ |
| SteadyState at assumed fraction | Concrete power target using 100W FTP, but fictional watt values. | |

**User's choice:** FreeRide segments + TextEvents

---

## Session Data Routing

### Q1: How does DuringSessionScreen load the session?

| Option | Description | Selected |
|--------|-------------|----------|
| Always load today | getSessionToday() called independently on mount, no URL param. | ✓ + extension |
| ID via URL param | Today passes /session/:id; DuringSessionScreen fetches that session. | |

**User's choice:** Always load today, but also include an option for when no session is scheduled but user wants to ride.
**Notes:** User extended the answer — needs a "Ride anyway" path for rest days.

### Q2: For unscheduled free rides, what flow?

| Option | Description | Selected |
|--------|-------------|----------|
| Ride anyway + generic steps | Rest-day empty state gets "Ride anyway" button → fixed 3-step placeholders. | |
| Duration picker before start | "Ride anyway" opens modal: pick 30/45/60 or custom → proportional steps generated. | ✓ |
| Out of scope for Phase 5 | Only planned session path in Phase 5. | |

**User's choice:** Duration picker before start

### Q3: How does session structure map to steps?

| Option | Description | Selected |
|--------|-------------|----------|
| 3 steps (warmup/main/cooldown) | Simple 1:1 mapping, fits current plan generator output. | deferred |
| Expand main_set into intervals | Richer but requires schema changes — main_set has no sub-intervals currently. | preferred |

**Notes:** User preferred interval expansion but agreed to defer when informed main_set has no sub-interval structure yet. 3-step mapping used for Phase 5; interval sub-structure deferred to future phase.

---

## Claude's Discretion

None — all gray areas had explicit user decisions.

## Deferred Ideas

- Interval sub-structure in plan.py (main_set expanded into multiple timed intervals) — deferred to future phase
- ZWO export for Agenda/historical sessions — Phase 5 only covers today's session
