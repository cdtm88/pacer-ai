# tests/sports_science/test_import_boundary.py
import subprocess


def test_sports_science_has_zero_anthropic_imports():
    """TRUST-01: sports_science/ must never import from anthropic SDK."""
    result = subprocess.run(
        ["grep", "-r", "anthropic", "backend/sports_science/"],
        capture_output=True,
        text=True,
    )
    # grep exit codes: 0 = match found (real violation, must fail), 1 = no
    # match (the real pass signal), 2 = usage/path error (tooling problem,
    # must fail loudly rather than be mistaken for a pass). Only == 1 is a
    # genuine pass; `!= 0` would incorrectly accept both 1 and 2.
    assert result.returncode == 1, (
        f"Expected grep exit code 1 (no match); got {result.returncode}. "
        f"0 means a forbidden import was found, 2 means grep errored "
        f"(e.g. bad path) -- both are failures.\n{result.stdout}"
    )


def test_sports_science_has_zero_fastapi_imports():
    """TRUST-boundary (Phase 2): sports_science/ must never import from fastapi.

    The async Supabase upgrade in Phase 2 must not smuggle web-layer imports
    into the sports_science trust anchor.
    """
    result = subprocess.run(
        ["grep", "-r", "fastapi", "backend/sports_science/"],
        capture_output=True,
        text=True,
    )
    # See test_sports_science_has_zero_anthropic_imports for the exit-code
    # rationale: only 1 (clean no-match) is a pass.
    assert result.returncode == 1, (
        f"Expected grep exit code 1 (no match); got {result.returncode}. "
        f"0 means a forbidden import was found, 2 means grep errored "
        f"(e.g. bad path) -- both are failures.\n{result.stdout}"
    )


def test_import_boundary_check_detects_violations(tmp_path):
    """Meta-test: proves the grep-based boundary check is non-vacuous.

    Seeds a throwaway file containing a forbidden import under a temp
    directory and asserts grep reports a real match (exit code 0). This
    directly answers the verifier's "a test that always passes is not
    verification" finding -- it locks in that the mechanism can actually
    catch a real violation, not just pass unconditionally.
    """
    violation_dir = tmp_path / "fake_sports_science"
    violation_dir.mkdir()
    violation_file = violation_dir / "bad_module.py"
    violation_file.write_text("import anthropic\n")

    result = subprocess.run(
        ["grep", "-r", "anthropic", str(violation_dir)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "Expected grep exit code 0 (match found) for a seeded forbidden "
        f"import; got {result.returncode}. The boundary check must be able "
        f"to detect a real violation.\n{result.stdout}"
    )
