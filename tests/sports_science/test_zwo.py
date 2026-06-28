# tests/sports_science/test_zwo.py
"""
Unit tests for api/sports_science/zwo.py (ZWO-01 through ZWO-04).

Plain pytest functions, no asyncio marker -- matches test_zones.py style.
"""

import xml.etree.ElementTree as ET

from backend.sports_science.zwo import generate_zwo


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_session() -> dict:
    """Minimal session dict with a 3-segment structure."""
    return {
        "type": "endurance",
        "scheduled_date": "2026-07-01",
        "objective": "Build aerobic base",
        "structure": {
            "warmup": {"duration_minutes": 10, "description": "Easy spin to warm up"},
            "main_set": {"duration_minutes": 30, "description": "Steady effort at zone 2"},
            "cooldown": {"duration_minutes": 5, "description": "Cool down easy"},
        },
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_zwo_basic_structure():
    """ZWO-01: root tag, sportType, author, name, and 3 SteadyState children."""
    session = _make_session()
    xml_bytes = generate_zwo(session, ftp_watts=185)
    root = ET.fromstring(xml_bytes)

    assert root.tag == "workout_file"

    sport_els = root.findall("sportType")
    assert len(sport_els) == 1
    assert sport_els[0].text == "bike"

    name_els = root.findall("name")
    assert len(name_els) == 1
    assert name_els[0].text  # non-empty

    author_els = root.findall("author")
    assert len(author_els) == 1
    assert author_els[0].text == "PacerAI"

    workout_el = root.find("workout")
    assert workout_el is not None

    steady_blocks = workout_el.findall("SteadyState")
    assert len(steady_blocks) == 3


def test_power_fraction_bounds():
    """ZWO-02: every SteadyState Power is a float in [0.0, 2.0] with a decimal point."""
    session = _make_session()
    xml_bytes = generate_zwo(session, ftp_watts=200)
    root = ET.fromstring(xml_bytes)
    workout_el = root.find("workout")

    steady_blocks = workout_el.findall("SteadyState")
    assert len(steady_blocks) > 0

    for block in steady_blocks:
        power_attr = block.get("Power")
        assert power_attr is not None, "Power attribute missing"
        assert "." in power_attr, f"Power '{power_attr}' is not a decimal string"
        power_val = float(power_attr)
        assert 0.0 <= power_val <= 2.0, f"Power fraction {power_val} out of [0.0, 2.0]"


def test_pre_ftp_uses_freeride():
    """ZWO-03/D-09: ftp_watts=None produces FreeRide+textevent blocks, zero SteadyState."""
    session = _make_session()
    xml_bytes = generate_zwo(session, ftp_watts=None)
    root = ET.fromstring(xml_bytes)
    workout_el = root.find("workout")

    steady_blocks = workout_el.findall("SteadyState")
    assert len(steady_blocks) == 0, "No SteadyState expected when FTP is None"

    free_ride_blocks = workout_el.findall("FreeRide")
    assert len(free_ride_blocks) == 3

    for block in free_ride_blocks:
        textevent_els = block.findall("textevent")
        assert len(textevent_els) == 1, "Each FreeRide must have exactly one textevent"
        te = textevent_els[0]
        assert te.get("timeoffset") == "0"
        assert te.get("message"), "textevent message must be non-empty"


def test_sport_type_and_cadence():
    """ZWO-01/ZWO-04: serialized XML contains bike sportType and no Cadence attribute."""
    session = _make_session()
    xml_bytes = generate_zwo(session, ftp_watts=185)
    text = xml_bytes.decode("utf-8")

    assert "<sportType>bike</sportType>" in text
    assert "Cadence" not in text, "Cadence attribute must never be emitted"
