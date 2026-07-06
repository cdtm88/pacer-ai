# tests/sports_science/conftest.py
import pytest


@pytest.fixture(autouse=True)
def _reset_capability_gap_client():
    """Reset capability_gap's module-level Supabase client cache before and
    after each test so a client cached by an earlier test never leaks into
    a later test's patched/raising client (gap closure 01-06)."""
    from backend.sports_science import capability_gap

    capability_gap._reset_client_for_tests()
    yield
    capability_gap._reset_client_for_tests()


@pytest.fixture
def sample_ftp():
    return 200.0


@pytest.fixture
def flat_power_array():
    """1 Hz data, 3600 samples (1 hour), constant 150W."""
    return [150.0] * 3600


@pytest.fixture
def variable_power_array():
    """1 Hz data with coasting zeros and peaks -- tests NP > AP."""
    return [0.0] * 300 + [250.0] * 300  # alternating coasting and effort


@pytest.fixture
def sample_quality_efforts():
    """4 efforts spanning 3-20 minute range for CP model."""
    return [
        {"duration_secs": 1200, "mean_power_watts": 210},
        {"duration_secs": 600,  "mean_power_watts": 240},
        {"duration_secs": 300,  "mean_power_watts": 270},
        {"duration_secs": 180,  "mean_power_watts": 290},
    ]
