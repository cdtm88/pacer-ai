# tests/sports_science/conftest.py
import pytest


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
