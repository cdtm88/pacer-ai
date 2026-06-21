# sports_science/zwo.py
"""
ZWO export: pure XML builder for Zwift structured workout files (ZWO-01 through ZWO-04).

This module is pure computation: no DB calls, no imports of other sports_science tools.
All physiological numbers come exclusively from POWER_BY_SEGMENT constants or the
caller-supplied ftp_watts argument (trust model). The LLM never supplies power values.

Usage:
    from api.sports_science.zwo import generate_zwo
    xml_bytes = generate_zwo(session_dict, ftp_watts=200)
    xml_bytes = generate_zwo(session_dict, ftp_watts=None)  # pre-FTP: FreeRide blocks
"""

import xml.etree.ElementTree as ET

# ---------------------------------------------------------------------------
# Module-level constant: FTP fractions per segment (ZWO-02, trust model)
# Values are clamped to 0.0-2.0 before use; no Cadence attribute is emitted (ZWO-04).
# ---------------------------------------------------------------------------

POWER_BY_SEGMENT: dict[str, float] = {
    "warmup": 0.50,
    "main_set": 0.65,
    "cooldown": 0.50,
}

# Fixed segment order matching structured session shape from plan.py
_SEGMENT_ORDER = ("warmup", "main_set", "cooldown")


def generate_zwo(session: dict, ftp_watts: int | None) -> bytes:
    """Build a conformant Zwift .zwo XML file from a session dict.

    Args:
        session: Session row dict containing at least:
                 - type (str): session type label, e.g. "endurance"
                 - scheduled_date (str): ISO date string YYYY-MM-DD
                 - objective (str): session goal text used as description
                 - structure (dict): keys warmup/main_set/cooldown each with
                   duration_minutes (float) and description (str)
        ftp_watts: User's FTP in watts from the profile table, or None when
                   FTP has not yet been established (ZWO-03, D-09).
                   When None, all segments emit FreeRide blocks with textevent
                   RPE cues instead of SteadyState power blocks.

    Returns:
        UTF-8 encoded bytes with XML declaration (ZWO-01).

    Design constraints:
        - Power values are FTP fractions from POWER_BY_SEGMENT only, clamped
          0.0-2.0, rendered as decimal strings (ZWO-02).
        - Cadence attribute is never emitted (ZWO-04).
        - sportType is exactly "bike" (ZWO-01).
        - No em dashes in any string output.
    """
    session_type = (session.get("type") or "workout").title()
    scheduled_date = session.get("scheduled_date", "")
    objective = session.get("objective") or ""
    structure = session.get("structure") or {}

    use_free_ride = ftp_watts is None

    # Build root element
    root = ET.Element("workout_file")

    name_el = ET.SubElement(root, "name")
    name_el.text = f"{session_type}: {scheduled_date}"

    author_el = ET.SubElement(root, "author")
    author_el.text = "PacerAI"

    description_el = ET.SubElement(root, "description")
    description_el.text = objective

    sport_el = ET.SubElement(root, "sportType")
    sport_el.text = "bike"

    workout_el = ET.SubElement(root, "workout")

    for key in _SEGMENT_ORDER:
        seg = structure.get(key) or {}
        duration_secs = int(seg.get("duration_minutes", 5) * 60)
        description = seg.get("description", "")

        if use_free_ride:
            # Pre-FTP path: FreeRide blocks with RPE cue textevent (ZWO-03, D-09)
            block = ET.SubElement(workout_el, "FreeRide")
            block.set("Duration", str(duration_secs))
            block.set("FlatRoad", "0")
            textevent = ET.SubElement(block, "textevent")
            textevent.set("timeoffset", "0")
            textevent.set("message", description)
            textevent.set("duration", "10")
        else:
            # With-FTP path: SteadyState power block (ZWO-01, ZWO-02)
            raw_fraction = POWER_BY_SEGMENT[key]
            power = round(max(0.0, min(2.0, raw_fraction)), 4)
            block = ET.SubElement(workout_el, "SteadyState")
            block.set("Duration", str(duration_secs))
            block.set("Power", str(power))
            # Cadence attribute intentionally omitted (ZWO-04, D-08)

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)
