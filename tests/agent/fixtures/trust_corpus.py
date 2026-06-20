# tests/agent/fixtures/trust_corpus.py
"""
Labelled representative corpus for trust scanner characterization (TRUST-03 / AGENT-06).

Three module-level constants:

  VIOLATIONS  list[str]              Each entry contains at least one UNSOURCED physiological
                                     number+unit. scan_buffer(text, set()) must return a
                                     TrustViolation for every entry (zero false negatives).
                                     Covers >= 8 examples spanning >= 5 PHYSIO_PATTERN unit
                                     families (watts/W, TSS, FTP, CTL, ATL, TSB, bpm, rpm,
                                     zone N, Z-N).

  QUALITATIVE list[str]              Representative coaching text with NO unsourced number+unit.
                                     scan_buffer(text, set()) must return None for every entry
                                     (zero false positives). Deliberately includes near-miss
                                     phrases that mention cycling concepts without a digit
                                     (e.g. "ride in your endurance zone today" -- no digit).

  ATTRIBUTED  list[tuple[str, set[str]]]
                                     Pairs (text, tool_result_values) where text contains a
                                     number+unit that was returned by a tool this turn and
                                     therefore appears verbatim as a substring of one of the
                                     tool_result_value strings.
                                     scan_buffer(text, values) must return None for every pair
                                     (Pitfall 1: tool-echoed values are attributed).

Minimum counts: >= 8 VIOLATIONS, >= 8 QUALITATIVE, >= 4 ATTRIBUTED.

This corpus is the durable evidence behind Phase 2 Success Criterion 5 and the
regression harness that lets the trust scanner regex (agent/trust.py PHYSIO_PATTERN_A /
PHYSIO_PATTERN_B) be tuned safely: any change that introduces a false negative or false
positive will fail the parametrized tests in tests/agent/test_trust_corpus.py.
"""

# ---------------------------------------------------------------------------
# VIOLATIONS: unsourced physiological numbers that scan_buffer must catch.
# Unit families covered:
#   watts/W  (1-3)  -- Pattern A: number + unit
#   bpm      (4)    -- Pattern A
#   rpm      (5)    -- Pattern A
#   TSS      (6)    -- Pattern B: unit + optional words + number
#   FTP      (7)    -- Pattern B
#   CTL      (8)    -- Pattern B
#   ATL      (9)    -- Pattern B
#   TSB      (10)   -- Pattern B (negative)
#   zone N   (11)   -- Pattern B
#   Z-N      (12)   -- Pattern B shorthand
# ---------------------------------------------------------------------------

VIOLATIONS: list[str] = [
    # --- watts / W family (Pattern A: number+unit) ---
    "Your FTP is 250 watts based on your previous rides.",          # unit family: watts (1)
    "Today's target power is 200W for the main set.",               # unit family: W (2)
    "I'd recommend keeping your watts at around 180 watts today.",  # unit family: watts (3)

    # --- bpm (Pattern A) ---
    "Keep your heart rate under 150 bpm during the climb.",         # unit family: bpm (4)

    # --- rpm (Pattern A) ---
    "Aim for a cadence of 90 rpm throughout this session.",         # unit family: rpm (5)

    # --- TSS (Pattern B: unit + optional words + number) ---
    "That ride was about 85 TSS, which is solid for a 90-minute effort.",   # unit family: TSS (6)
    "Your TSS today was 65.",                                        # unit family: TSS (alt)

    # --- FTP (Pattern B) ---
    "Based on your recent data your FTP is approximately 235.",      # unit family: FTP (7)

    # --- CTL (Pattern B) ---
    "Your CTL is around 42 right now, which is a good base.",       # unit family: CTL (8)

    # --- ATL (Pattern B) ---
    "ATL is 55 after that hard block, so fatigue is elevated.",     # unit family: ATL (9)

    # --- TSB (Pattern B, negative allowed) ---
    "Your form score TSB is -13 heading into Sunday.",              # unit family: TSB (10)

    # --- zone N (Pattern B) ---
    "Target Zone 4 today for the main set intervals.",              # unit family: zone N (11)

    # --- Z-N shorthand (Pattern B) ---
    "Keep the warm-up in Z2 before you push harder.",               # unit family: Z-N (12)
]


# ---------------------------------------------------------------------------
# QUALITATIVE: coaching text with NO unsourced number+unit.
# These MUST all return None from scan_buffer(text, set()).
# Near-miss entries deliberately stress the false-positive boundary:
#   - "endurance zone" with no digit
#   - "comfortable cadence" with no digit
#   - "a few watts" with no digit directly before "watts"
#   - "Zone" appearing as part of a general phrase, no digit following
# ---------------------------------------------------------------------------

QUALITATIVE: list[str] = [
    # Clean coaching language (no digits at all)
    "Ride easy and keep it conversational today.",
    "Take it steady; this is a recovery spin.",
    "Build the effort gradually through the main set.",
    "Listen to your body and back off if your lower back complains.",
    "A solid aerobic session to bank some base fitness.",

    # Near-miss: mentions zones / units conceptually but without a digit
    "Ride in your endurance zone today -- no need to push.",
    "Keep cadence comfortable and avoid grinding a big gear.",
    "Adjust your perceived effort rather than chasing a specific number.",

    # Near-miss: "watts" appears but without a preceding digit
    "The power output will feel high in the mountains even at moderate watts.",
    "Focus on smooth pedalling rather than peak watts.",

    # Near-miss: "Zone" appears without a following digit
    "Stay in the aerobic zone and avoid lactate accumulation.",
    "This session is a Zone transition day, so keep things moderate.",

    # Near-miss: FTP and TSS appear as words in context, no number adjacent
    "Your FTP will improve naturally as aerobic fitness grows.",
    "The TSS from your long ride will accumulate over the week.",

    # Near-miss: numbers appear but NOT followed/preceded by a physio unit
    "The ride lasted about 3 hours and felt manageable.",
    "You completed 5 intervals before the weather turned.",
]


# ---------------------------------------------------------------------------
# ATTRIBUTED: (text, tool_result_values) pairs where the number+unit in text
# was returned by a tool this turn and therefore appears verbatim as a substring
# of a tool_result_value string.
# scan_buffer(text, values) must return None for every pair (Pitfall 1).
# ---------------------------------------------------------------------------

ATTRIBUTED: list[tuple[str, set[str]]] = [
    # Tool returned power zones; Claude echoes the zone boundary in text
    (
        "Your power zones put Zone 4 at 180-210 watts for your FTP.",
        {"180-210 watts", "Zone 4 at 180-210 watts"},
    ),

    # Tool returned FTP estimate; Claude reports it back
    (
        "Based on your recent rides, your FTP is 240 watts.",
        {"FTP is 240 watts", "240 watts"},
    ),

    # Tool returned TSS; Claude echoes it
    (
        "That effort generated 75 TSS according to the calculation.",
        {"75 TSS", "generated 75 TSS"},
    ),

    # Tool returned HR zone; Claude echoes bpm value
    (
        "Your heart rate should stay below 148 bpm for Zone 2 work.",
        {"148 bpm", "Zone 2", "stay below 148 bpm"},
    ),

    # Tool returned CTL value; Claude echoes it
    (
        "Your CTL is currently 38 based on the PMC calculation.",
        {"CTL is currently 38", "38"},
    ),

    # Tool returned rpm recommendation; Claude echoes it
    (
        "The tool suggests a cadence of 85 rpm for this sweet-spot interval.",
        {"85 rpm", "cadence of 85 rpm"},
    ),

    # TRANSP-01 / ADAPT-05: adaptation explanation echoes CTL and TSS from validate_session_vs_actual
    # and progress_load results. Numbers in explanation_text are tool-sourced (not LLM-invented).
    (
        "Micro-adjustment triggered by underperformance signal on session sess-007 "
        "(compliance: 45.0% of planned TSS from validate_session_vs_actual). "
        "Next 3 sessions reduced to 80% intensity.",
        {"compliance: 45.0%", "45.0%", "validate_session_vs_actual"},
    ),

    # TRANSP-01 / ADAPT-05: macro replan explanation echoes CTL and TSS values from progress_load
    (
        "Macro re-plan triggered by 2 signals (missed, underperformance) in a 7-day window. "
        "progress_load recommended CTL target 32.4 from current 36.0 (reduced capacity 90%). "
        "8 sessions rescheduled.",
        {"CTL target 32.4", "32.4", "36.0", "recommended CTL target 32.4 from current 36.0"},
    ),
]
