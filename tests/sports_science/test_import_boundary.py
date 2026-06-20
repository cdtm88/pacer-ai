# tests/sports_science/test_import_boundary.py
import subprocess


def test_sports_science_has_zero_anthropic_imports():
    """TRUST-01: sports_science/ must never import from anthropic SDK."""
    result = subprocess.run(
        ["grep", "-r", "anthropic", "sports_science/"],
        capture_output=True,
        text=True,
    )
    # grep returncode 1 = no matches = test passes
    assert result.returncode != 0, (
        f"Found anthropic import in sports_science/:\n{result.stdout}"
    )


def test_sports_science_has_zero_fastapi_imports():
    """TRUST-boundary (Phase 2): sports_science/ must never import from fastapi.

    The async Supabase upgrade in Phase 2 must not smuggle web-layer imports
    into the sports_science trust anchor.
    """
    result = subprocess.run(
        ["grep", "-r", "fastapi", "sports_science/"],
        capture_output=True,
        text=True,
    )
    # grep returncode 1 = no matches = test passes
    assert result.returncode != 0, (
        f"Found fastapi import in sports_science/:\n{result.stdout}"
    )
