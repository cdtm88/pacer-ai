# Phase 1: Sports-Science Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-19
**Phase:** 1-Sports-Science Foundation
**Mode:** --auto (all areas auto-selected; recommended options chosen)
**Areas discussed:** Tool Return Contract, FTP Estimation Approach, PMC Time Constants, Supabase Setup Strategy, Back-Protective Constraint Model

---

## Tool Return Contract

| Option | Description | Selected |
|--------|-------------|----------|
| Typed dataclass (ToolResult) | `{value, unit, methodology, inputs}` as dataclass; type-safe, IDE support, JSON-serializable | ✓ |
| Plain dict | Simpler; no import needed; less overhead | |

**Auto-selected:** Typed dataclass (ToolResult)
**Notes:** [auto] consistent schema that the agent response parser can validate against; reduces ambiguity when multiple tools return different shapes.

---

## FTP Estimation Approach

| Option | Description | Selected |
|--------|-------------|----------|
| 2-parameter CP model | Morton (1996) Critical Power + W'; grounded in peer-reviewed methodology | ✓ |
| Best 20-min power proxy | Simpler; widely used heuristic (best 20-min * 0.95); less accurate with indoor smart trainer data | |

**Auto-selected:** 2-parameter CP model
**Notes:** [auto] matches PRD spec ("Critical Power / best-effort modelling"). Quality effort threshold: > 3 min, > 85% best estimate power. Minimum 4 quality efforts before any estimate emitted.

---

## PMC Time Constants and Cold-Start

| Option | Description | Selected |
|--------|-------------|----------|
| Module-level constants (CTL_TC=42, ATL_TC=7) | Standard Banister values; named constants in constants.py; configurable | ✓ |
| Hardcoded magic numbers | Simpler but not maintainable or testable | |
| Fully configurable per user | Personalization potential; but no evidence base for varying these for beginners | |

**Auto-selected:** Module-level constants with standard defaults
**Notes:** [auto] TSB display suppressed until 28+ days of data; `tss_display_ready` flag returned in ToolResult.

---

## Supabase Setup Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Cloud Supabase + CLI migrations | Hosted project; Supabase CLI for migration authoring; faster setup for solo project | ✓ |
| Local Supabase CLI (Docker) | Full local dev environment; more isolated; requires Docker | |

**Auto-selected:** Cloud Supabase + CLI migrations
**Notes:** [auto] avoids Docker dependency for a solo project; `supabase db push` applies migrations to cloud project; RLS enabled on all tables.

---

## Back-Protective Constraint Data Model

| Option | Description | Selected |
|--------|-------------|----------|
| JSONB constraint dict in profiles | Structured; queryable; explicit fields; extensible without schema migration | ✓ |
| Simple boolean flag | Minimal; but loses specificity (max hours, which effort types to avoid) | |

**Auto-selected:** JSONB constraint dict
**Notes:** [auto] fields: back_issues, max_initial_weekly_hours, no_standing_efforts, no_sprint_efforts, load_ramp_flag_threshold_pct. Default for no back issues: `{back_issues: false}`.

---

## Claude's Discretion

- NP spike filter threshold (clip power > FTP * 3, or > 600W if no FTP estimate)
- TSS null threshold (rides < 10 minutes)
- IF warning threshold (IF > 1.05 for rides > 60 minutes)

## Deferred Ideas

- Agent tool registry wiring: Phase 2
- FIT file parsing: Phase 3
- UI TSB display chip: Phase 4
