# Phase 8: Trust Model Integrity - Context

**Gathered:** 2026-07-04 (--auto)
**Status:** Ready for planning

<domain>
## Phase Boundary

Harden the trust model that Phase 2 built so it is actually airtight under real conversation load, not just in the corpus tests it originally passed. Seven concrete defects, all confirmed by direct code read (not just the review doc):

1. `audit_log` (TRUST-04) is built per-request in `backend/routes/_sse.py:75` and never written anywhere durable — "verifiable in application logs" is currently false.
2. Tool call **inputs** are never scanned — the LLM can hand a fabricated `current_ctl`/`ftp_watts`/`max_hr_or_lthr` straight into a tool call; the tool echoes it back in its result, and `scan_buffer` sees the number in `tool_result_values` and calls it "attributed."
3. Bare-number attribution in `backend/agent/trust.py:127-131,151-156` is a raw substring check ("250" matches inside "2500", "0.250", or any timestamp) — a near-bypass once any tool has run this turn.
4. `tool_result_values` is scoped to a single HTTP request (`loop.py`, `chat.py`) — on a stateless Vercel serverless function, a legitimate number from turn N-1 ("FTP is 190W") is gone by turn N and gets flagged as a trust violation on the model's own callback.
5. `calculate_hr_zones` is never called during onboarding (`backend/routes/onboarding.py`) — there is no LTHR/max-HR question at all — yet Phase 3's D-08 plan-generation order requires an HR-zones result before `generate_plan`. The LLM currently has no path except inventing a number.
6. `HR_ZONE_BOUNDARIES` in `backend/sports_science/constants.py:27-33` are Friel-style (81/90/94/100% of LTHR) but the docstring and tool description claim "Coggan/Allen" (whose real boundaries are ~68/83/94/105%). The mislabeled Zone 2 (81-90%) is also too hot for a deconditioned, back-flagged beginner.
7. `generate_plan`/`_build_sessions` in `backend/sports_science/plan.py:202-250,73-` accept `current_ctl` and `load_targets` as parameters and never read them (dead params); `preferred_days` does not exist as a parameter at all — days are always `_DEFAULT_DAYS` regardless of the user's profile. The back-protective load caps the roadmap promises don't actually constrain anything.

**In scope:** Fixing all 7 items above so TRUST-03/04/05 are genuinely enforced end-to-end, LTHR collection closes the onboarding gap, HR zone constants and Zone 2 targets are corrected, and `generate_plan` consumes the load/schedule signals it's already being handed.

**Out of scope:** CP model mean-max-effort fix, ZWO fixed-0.65-power bug, NaN propagation in metrics, and the other "misc" bullets under the review doc's Phase 8 heading — none of these are named in the ROADMAP.md Phase 8 goal or success criteria. Flagged under Deferred Ideas below rather than silently dropped.

</domain>

<decisions>
## Implementation Decisions

**Mode:** `--auto` — no interactive questions were asked. Every decision below is the recommended option, auto-selected and logged for audit. Two of the seven areas are already locked by the ROADMAP.md goal statement itself (not genuine gray areas); the rest were resolved by direct code inspection.

### Audit Log Persistence (TRUST-04)

- **D-01 (auto):** New `audit_log` Postgres table, written per tool dispatch inside `dispatch_tool` (same call sites that already do `audit_log.append(...)` in `backend/agent/tools.py:586,601,629,642`), following the exact async-Supabase-service-role pattern already proven in `backend/sports_science/capability_gap.py::log_capability_gap` (cached singleton client, best-effort insert, never blocks the tool result on write failure).
  - *Why not batch at end of turn:* a mid-turn SSE disconnect or serverless timeout would lose the whole turn's trail; per-call writes survive partial turns.
  - *Why not log-lines only:* the ROADMAP goal explicitly says "persisted," and `capability_gaps` already sets the DB-table precedent for this exact kind of audit record.

### Tool Input Scanning — Laundering Prevention

- **D-02 (auto):** Split enforcement by input provenance, mirroring the already-validated `user_id` server-side-injection fix (commit `b3fcf39`, 260702-wev):
  - Values that come from a prior trusted tool result (`current_ctl` from `update_pmc`, `ftp_watts`/`ftp_confidence` from `estimate_ftp_from_rides`, `load_targets` from `progress_load`) are **injected server-side** in `dispatch_tool` from the last verified DB/tool-result value, never taken from the LLM's tool-call arguments at all — the same trust boundary already applied to `user_id`.
  - Values the LLM must legitimately transcribe from the conversation (`max_hr_or_lthr` — self-reported by the user) are validated against a session-scoped "confirmed values" registry populated only from actual tool results and the onboarding profile, not accepted as free-form LLM input.

### Attribution Matching — Word-Boundary + Tolerance

- **D-03 (locked by ROADMAP goal, not a gray area):** Replace the substring check in `scan_buffer` with numeric-parse + tolerance (e.g. exact float compare within ~0.01) plus a word/token boundary requirement, so "250" can no longer match inside "2500" or a timestamp. This is stated as a required outcome in ROADMAP.md's Phase 8 goal text, not left open.

### Prior-Turn Number Seeding — Cross-Turn False Positives

- **D-04 (auto):** Seed `tool_result_values` at the start of each turn by reloading prior tool-result content blocks from the persisted `messages` table for the current `conversation_id` (already loaded via the existing `load_conversation` pattern from Phase 4's onboarding multi-turn work), not an in-memory/process cache.
  - *Why:* Phase 7 already established this backend runs as stateless Vercel serverless functions — any in-process cache is invisible to the next invocation. Reloading from the DB is the only mechanism consistent with that architecture.

### LTHR Collection in Onboarding

- **D-05 (auto):** Add a direct onboarding question (e.g. "Do you know your lactate threshold heart rate, or your resting/max HR?") with three explicit outcomes stored on the profile:
  1. User gives LTHR directly → used as-is.
  2. User gives max HR only → LTHR estimated via a documented %-of-max-HR heuristic (new or existing tool call, methodology-tagged like every other number in this system).
  3. User knows neither → explicit `hr_zones_available: false` (or equivalent flag) stored on the profile; `calculate_hr_zones` and `generate_plan`'s HR-based targets are **skipped entirely**, falling back to the RPE-only cold-start path Phase 3 already built (D-07 in `03-CONTEXT.md`).
  - *Why:* matches the ROADMAP wording exactly ("LTHR or explicit RPE-only fallback") and reuses the existing cold-start RPE path instead of inventing a new one.

### HR Zone Constants + Zone 2 Beginner Safety

- **D-06 (auto):** Correct `HR_ZONE_BOUNDARIES` in `constants.py` to true Coggan/Allen boundaries (~68/83/94/105% of LTHR) rather than the current Friel-style values, and keep the methodology string as "Coggan/Allen" (now honestly true instead of falsely claimed).
  - *Why this also fixes Zone 2 safety:* real Coggan Zone 2 (~69-83% LTHR) is a materially gentler ceiling than the current mislabeled 81-90%, so correcting the methodology bug and satisfying "Zone 2 targets safe for a returning beginner" are the same fix — no need for a third bespoke "beginner zone" model.
  - Rejected alternative: keep current boundaries and rename the methodology string to "Friel" — this doesn't address the beginner-safety half of the roadmap goal.

### generate_plan Wiring — current_ctl / load_targets / preferred_days

- **D-07 (auto):** 
  - Add `preferred_days` as a real parameter sourced from the user's profile, replacing the hardcoded `_DEFAULT_DAYS[:n_sessions]` slice in `_build_sessions`.
  - Wire `current_ctl` and `load_targets["recommended_ctl_target"]` into an actual per-week progression decision: when `current_ctl` is far below the recommended target (true beginner, low base fitness), keep week-over-week volume flat/conservative rather than the current fixed 4-week template regardless of starting fitness; combine with `back_status == "moderate"` to cap Week 1 duration further when both signals indicate an at-risk beginner.
  - Rejected: deleting the unused params without wiring behavior (honesty-only, doesn't satisfy "so back-protective caps actually constrain sessions" — the roadmap's stated success condition).

### Claude's Discretion

- Exact numeric tolerance for D-03's float comparison, exact %-of-max-HR formula for D-05's LTHR estimate, and the precise progression-multiplier curve for D-07 are left to planning/research — the direction is locked, the constants are not.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements and Roadmap

- `.planning/REQUIREMENTS.md` — TRUST-03, TRUST-04, TRUST-05 (all currently marked "Complete" from Phase 2; this phase re-verifies and hardens them under real-world load, not first implementation), TOOL-02, PLAN-06.
- `.planning/ROADMAP.md` §"Phase 8: Trust Model Integrity" — goal statement and success criteria (still TBD count; plan phase should assign explicit requirement IDs, likely TRUST-06+ for the new hardening behaviors).
- `.planning/research/APP-REVIEW-260703.md` §"Phase 8 — Trust Model Integrity" — the full source finding list this CONTEXT.md is derived from; includes file:line references for every defect.

### Prior Phase Context (decisions this phase must not contradict)

- `.planning/phases/03-coaching-loop/03-CONTEXT.md` D-07/D-08 — cold-start RPE-only path and the tool-call order (`progress_load` → `calculate_hr_zones` → `generate_plan`) that D-05/D-07 above build on.
- `.planning/phases/02-agent-core` phase (no CONTEXT.md; SUMMARY/REVIEW files under that phase dir) — original trust-scanner and audit-log implementation this phase hardens.

### Existing Source Files to Read Before Implementing

- `backend/agent/trust.py` — `scan_buffer`, `PHYSIO_PATTERN_A/B`, `handle_violation`; the substring-attribution bug (D-03) and where injected input validation (D-02) must hook in.
- `backend/agent/tools.py` — `TOOL_REGISTRY`, `TOOL_SCHEMAS`, `dispatch_tool` (audit_log.append call sites, generate_plan tool schema at line ~314).
- `backend/agent/loop.py` — turn loop, `tool_result_values` accumulation, where cross-turn seeding (D-04) must be added.
- `backend/routes/_sse.py` — `audit_log: list = []` (line 75), where per-request scoping currently loses everything.
- `backend/routes/chat.py`, `backend/routes/onboarding.py` — conversation/message persistence pattern to reuse for D-04's reload and D-05's new onboarding question.
- `backend/sports_science/capability_gap.py` — the exact async-Supabase-service-role pattern D-01's `audit_log` table write should mirror.
- `backend/sports_science/constants.py` (`HR_ZONE_BOUNDARIES`, lines 24-33), `backend/sports_science/zones.py` (`calculate_hr_zones`) — D-06's correction target.
- `backend/sports_science/plan.py` (`generate_plan` lines 202-250, `_build_sessions` lines 73-`, `_DEFAULT_DAYS`) — D-07's wiring target.
- `.planning/quick/260702-wev-inject-authenticated-user-id-server-side/` — the prior server-side-injection fix D-02 explicitly mirrors.

### Migration Pattern Reference

- `supabase/migrations/` — existing migration files (e.g. `0006_pmc_unique_and_fits_bucket.sql`) as the pattern for the new `audit_log` table migration D-01 requires.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `log_capability_gap` pattern (`backend/sports_science/capability_gap.py`) — cached async Supabase singleton, service-role key, best-effort insert that never blocks the caller. Reuse verbatim for the new audit-log writer.
- Existing `messages`/conversation persistence and `load_conversation` (Phase 4 onboarding multi-turn work) — reuse for D-04's cross-turn reload instead of building a new cache layer.
- Existing cold-start RPE-only session path (Phase 3 D-07) — reuse for D-05's "neither LTHR nor max HR known" fallback instead of inventing a parallel path.
- `calculate_power_zones` (7-zone, from FTP) already correctly labeled and implemented — use as the working reference implementation when correcting `calculate_hr_zones`'s constants and methodology string in D-06.

### Established Patterns

- Server-side injection of trust-sensitive values instead of trusting LLM tool-call arguments (the `user_id` fix, 260702-wev) — D-02 extends this exact pattern to `current_ctl`/`ftp_watts`/`load_targets`.
- All physiological tools return `ToolResult` with `value`, `unit`, `methodology`, `inputs` — any new tool (e.g. an LTHR-from-max-HR estimator for D-05) must follow this shape.
- DB writes from backend tool/agent code always use `SUPABASE_SERVICE_ROLE_KEY`, never the anon key — applies to the new `audit_log` table writes.

### Integration Points

- `dispatch_tool` (`backend/agent/tools.py:559`) is the single choke point for both D-01 (audit write) and D-02 (input provenance enforcement) — both changes land here.
- `backend/agent/loop.py`'s per-turn `tool_result_values` construction is where D-04's cross-turn seeding must be added, before `scan_buffer` is first called each turn.
- `backend/routes/onboarding.py` interview question flow is where D-05's new LTHR question is inserted; must precede the point where `calculate_hr_zones` is called (per Phase 3 D-08 ordering).

</code_context>

<specifics>
## Specific Ideas

- All defects above were independently confirmed by direct source reads during this discussion (not taken solely from the review doc) — line numbers cited are current as of 2026-07-04.
- The Zone 2 fix (D-06) is a single-constants-table correction that resolves two separately-stated roadmap concerns (methodology honesty + beginner safety) — no need to design a third HR model.

</specifics>

<deferred>
## Deferred Ideas

- **CP model quality-filter bug** (`ftp.py:46` — `best_ftp_estimate` always `None`, dead code; fed whole-ride duration/avg-power instead of mean-max efforts; FTP=CP with no 0.95 discount, unsafe overestimate direction) — found in `APP-REVIEW-260703.md` under its "Phase 8" heading but not named in ROADMAP.md's actual Phase 8 goal/success criteria. Not acted on here; flag for roadmap backlog (likely belongs with Phase 6's other CP/PMC fixes, or a new hygiene phase).
- **ZWO fixed-0.65-FTP bug** (`zwo.py:22-26,97` — recovery sessions export as a 65% steady-state ride regardless of session type/power_targets) — same situation: mentioned in the review doc's Phase 8 section, not in ROADMAP.md's Phase 8 scope. Flag for backlog.
- **NaN propagation in metrics** (`np.clip` passes NaN through; NP/IF/TSS can become NaN and break JSON serialization) and the review doc's "misc" bullet list (zone input validation, 0.56/0.55 boundary duplication, week-4 duration overflow, `weekly_hours=0` still scheduling sessions, `load.py` mild/moderate distinction erased, `zwo.py` None-duration TypeError) — same situation, flagged for backlog rather than silently dropped.
- None of the above block Phase 8's stated goal; they're orphaned findings that need a roadmap decision on where they land, not a phase-8 discussion decision.

</deferred>

---

*Phase: 08-trust-model-integrity*
*Context gathered: 2026-07-04*
