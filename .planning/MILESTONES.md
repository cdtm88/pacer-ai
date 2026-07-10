# Milestones

## v1.0 MVP (Shipped: 2026-07-10)

**Phases completed:** 13 phases, 94 plans, ~220 tasks
**Timeline:** 21 days (2026-06-19 → 2026-07-10)
**Git range:** a05b5b2 → 770c0f4 (552 files changed, ~19,400 LOC frontend TS/TSX + backend Python)

**Delivered:** An evidence-based, adaptive AI cycling coach that interviews a beginner cyclist with no FTP and no fitness history, generates a safe periodised plan, and adapts it automatically as real ride data arrives — end to end, verified by an independent milestone audit tracing real user-reachable wiring, not just passing unit tests.

**Key accomplishments:**

- Trust-anchored sports-science tool library (power/HR zones, TSS/NP/IF, PMC, passive FTP estimation via critical-power modelling) with a runtime trust scanner that structurally prevents the LLM from emitting any physiological number itself.
- Conversational onboarding producing a structured, periodised plan with full cold-start support (no FTP required at signup) and back-protective constraints for injury-flagged users.
- Complete FIT-upload → TSS/PMC → compliance loop, with adaptive re-planning (micro/macro, 30% shift guard) and in-chat transparency citing the data and principle behind every plan change.
- Web PWA (onboarding, Today, Agenda, Progress, Chat, Settings) plus an iOS-safe during-session stepper with wake lock and a server-side ZWO exporter, both Zwift-acceptance-tested.
- Ride Analysis Dashboard (per-second power/HR/cadence/speed/elevation charts, lap markers, time-in-zone breakdown) and a full athletic visual redesign (Zwift/Strava-register cockpit UI) unifying tokens, zone-color identity, and components across every screen.
- Closed a milestone-audit-surfaced integration gap (ADAPT-04/TRANSP-03): the weekly adaptation check and adaptation log had correct, tested backend implementations since Phase 3 but zero real callers — Phase 13 wired both to genuine user-reachable consumers and fixed a stale API contract plus a concurrency bug along the way.
- Deploy consolidated onto Vercel as the sole target (Railway decommissioned); CI (ruff + pytest + vitest) green on real GitHub Actions runs; trust-model hardening closed every laundering vector found during Phase 8's audit.

**Full per-plan accomplishment log:** see `.planning/milestones/v1.0-ROADMAP.md` (archived phase-by-phase detail) and individual `SUMMARY.md` files under each archived phase directory.

---
