# Phase 1: Sports-Science Foundation - Context

**Gathered:** 2026-06-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the deterministic, unit-tested sports-science tool library (`sports_science/` Python module) plus the database schema and Supabase project setup. This is the trust anchor: no downstream layer can be credible until these functions are verified correct and the code boundary (zero Anthropic imports in `sports_science/`) is enforced.

**In scope:** Tool library functions (7 public + log_capability_gap), unit tests, DB schema (8 tables), Supabase hosted project setup, Supabase CLI migrations.
**Out of scope:** Agent wiring, API endpoints, frontend, FIT parsing, plan generation — all Phase 2+.

</domain>

<decisions>
## Implementation Decisions

### Tool Return Contract

- **D-01:** All tool-library functions return a typed `ToolResult` dataclass (not a plain dict): `{value: Any, unit: str, methodology: str, inputs: dict}`. Serializes to JSON for the agent tool response. This gives type safety, IDE support, and a consistent schema the agent parser can validate.
- **D-02:** `methodology` is a human-readable string naming the source (e.g., `"Coggan/Allen 7-zone power model"`, `"Banister PMC EWMA CTL_TC=42 ATL_TC=7"`, `"2-parameter Critical Power model (Morton 1996)"`). Not a structured object — the agent surfaces it as-is in chat.

### FTP Estimation Approach

- **D-03:** Use the 2-parameter Critical Power model (Critical Power + W'). Methodology string: `"2-parameter Critical Power model (Morton 1996)"`. Requires a minimum of 4 quality efforts before emitting any estimate. A "quality effort" is any interval > 3 minutes where mean power > 85% of the current best estimate (or > 150W if no estimate exists yet). Confidence levels: `low` (4-6 efforts), `medium` (7-12 efforts), `high` (12+ efforts with good variance).
- **D-04:** For truly sparse data (< 4 quality efforts), `estimate_ftp_from_rides` returns `{value: None, confidence: "insufficient_data", methodology: "...", inputs: {...}}` — never a fabricated number. The plan stays on RPE/HR targets until confidence reaches `medium`.

### PMC Time Constants and Cold-Start

- **D-05:** Standard Banister time constants as module-level constants: `CTL_TC = 42` (days), `ATL_TC = 7` (days). Not magic numbers — named constants in `sports_science/constants.py`. These are configurable at import time but default to the Banister/Coggan standard.
- **D-06:** `update_pmc` cold-start guard: initializes CTL=0, ATL=0 at first ride. Does not emit TSB values (and sets `tss_display_ready=False`) until 28+ days of data are present. Returns `tss_display_ready` flag in the ToolResult so the UI knows whether to show the TSB chip.

### Supabase Setup Strategy

- **D-07:** Cloud-first: create a hosted Supabase project (not local Docker). Use Supabase CLI for migration authoring and applying (`supabase db push`). Migrations live in `supabase/migrations/`. Row-Level Security (RLS) enabled on all 8 tables with `user_id = auth.uid()` policy.
- **D-08:** A `.env.example` is committed with all required environment variables (`SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`). Actual `.env` is gitignored.

### Back-Protective Constraint Data Model

- **D-09:** Back-protective constraints stored as a JSONB column (`constraints`) in the `profiles` table with this schema:
  ```json
  {
    "back_issues": true,
    "max_initial_weekly_hours": 3.5,
    "no_standing_efforts": true,
    "no_sprint_efforts": true,
    "load_ramp_flag_threshold_pct": 10
  }
  ```
  Default for users with no back issues: `{"back_issues": false}` (all other fields absent/ignored by planner). The `progress_load` tool accepts this constraints dict and applies injury-aware caps.

### Code Structure

- **D-10:** The `sports_science/` directory is a Python package with zero Anthropic SDK imports. Verified by a CI import-boundary test (`grep -r "anthropic" sports_science/` must return empty). Sub-modules: `zones.py`, `metrics.py` (NP/TSS/IF), `pmc.py` (CTL/ATL/TSB), `ftp.py` (CP model), `load.py` (progress_load), `compliance.py` (validate_session_vs_actual), `capability_gap.py`, `constants.py`, `types.py` (ToolResult dataclass).

### Claude's Discretion

- NP spike filter threshold: clip power > FTP * 3 before NP calculation (if no FTP estimate, clip at 600W). Researcher/planner can adjust if literature suggests otherwise.
- TSS null threshold: return null for rides under 10 minutes — standard practice.
- IF validation: flag IF > 1.05 for rides over 60 minutes as a data quality warning in the ToolResult.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements

- `.planning/REQUIREMENTS.md` §Sports-Science Tool Library (TOOL-01 to TOOL-10) — exact function signatures, return contract, edge cases
- `.planning/REQUIREMENTS.md` §Trust Model Enforcement (TRUST-01, TRUST-02) — code boundary and registry rules for Phase 1
- `.planning/REQUIREMENTS.md` §Capability-Gap Logging (GAP-01, GAP-02, GAP-03) — log_capability_gap DB contract

### Research Findings

- `.planning/research/STACK.md` — technology choices (fitdecode, numpy, supabase-py-async, Tailwind v4)
- `.planning/research/SUMMARY.md` §Critical Pitfalls — NP zeros, spike filter, CP model 4-effort minimum, PMC cold-start guard
- `.planning/research/ARCHITECTURE.md` §Components — sports_science/ module design, 8-table DB schema

### Project Context

- `.planning/PROJECT.md` §Non-Negotiable Architecture — trust model rules (LLM never emits physiological numbers)
- `.planning/PROJECT.md` §Key Decisions — stack decisions already locked (fastAPI, Supabase, numpy)

### External Methodology References (for methodology strings)

- Coggan/Allen power zones: 7-zone model boundaries (55/75/90/105/120/150%+ FTP)
- Banister PMC: CTL_TC=42, ATL_TC=7 standard values
- Morton (1996) 2-parameter CP model: the basis for `estimate_ftp_from_rides`
- TrainingPeaks TSS/IF/NP definitions: the basis for `compute_tss`

No external spec files yet (greenfield project).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- None yet (greenfield project — Phase 1 creates the foundation).

### Established Patterns

- None yet — this phase establishes the patterns all subsequent phases follow.

### Integration Points

- `sports_science/` exports will be imported by `agent/tools.py` (Phase 2) — the tool registry wraps each function as an Anthropic tool schema.
- `capability_gaps` table created here is written to by `log_capability_gap` (TOOL-08) and read by the adaptation transparency log (Phase 3).
- `supabase/migrations/` established here; Phase 2+ add migrations for sessions, rides, PMC, conversations tables.

</code_context>

<specifics>
## Specific Ideas

- The PRD specifies exact function names — use them verbatim: `calculate_power_zones`, `calculate_hr_zones`, `estimate_ftp_from_rides`, `compute_tss`, `update_pmc`, `progress_load`, `validate_session_vs_actual`, `log_capability_gap`.
- Power zone boundaries for 7-zone Coggan/Allen: Z1 <55%, Z2 56-75%, Z3 76-90%, Z4 91-105%, Z5 106-120%, Z6 121-150%, Z7 >150% FTP.
- The `capability_gaps` table schema (from ARCHITECTURE.md): `id`, `user_id`, `method_name`, `description`, `conversation_id`, `created_at`.

</specifics>

<deferred>
## Deferred Ideas

- Agent tool registry wiring (Phase 2) — this phase only builds the functions; wrapping them as Anthropic tool schemas happens in Phase 2.
- FIT file parsing (Phase 3) — `compute_tss` will receive parsed ride data; the parser itself is Phase 3.
- UI display of TSB "form chip" (Phase 4) — `tss_display_ready` flag is returned by `update_pmc` but consumed only when the UI is built.

</deferred>

---

*Phase: 1-Sports-Science Foundation*
*Context gathered: 2026-06-19*
