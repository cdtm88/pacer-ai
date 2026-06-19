# sports_science/constants.py

# Banister PMC time constants (days) -- D-05
CTL_TC: int = 42
ATL_TC: int = 7
PMC_MIN_DAYS: int = 28  # days before TSB is meaningful (D-06)

# Coggan/Allen 7-zone power model -- boundaries as % of FTP (decimal)
# Zone membership: >= lower AND < upper (except Z7: >= lower only) -- avoid dual membership (Pitfall 4)
POWER_ZONE_BOUNDARIES = [
    {"zone": 1, "name": "Active Recovery",    "lower": 0.00, "upper": 0.55},
    {"zone": 2, "name": "Endurance",          "lower": 0.55, "upper": 0.75},
    {"zone": 3, "name": "Tempo",              "lower": 0.75, "upper": 0.90},
    {"zone": 4, "name": "Threshold",          "lower": 0.90, "upper": 1.05},
    {"zone": 5, "name": "VO2max",             "lower": 1.05, "upper": 1.20},
    {"zone": 6, "name": "Anaerobic Capacity", "lower": 1.20, "upper": 1.50},
    {"zone": 7, "name": "Neuromuscular",      "lower": 1.50, "upper": None},
]

# NP spike filter (metrics.py) -- D-10 / Claude's Discretion
NP_SPIKE_MULTIPLIER: float = 3.0       # clip at FTP * 3
NP_SPIKE_FALLBACK_WATTS: float = 600.0  # cap when no FTP available
NP_MIN_DURATION_SECS: int = 600        # 10 minutes minimum for TSS

# Coggan/Allen HR zones from LTHR -- 5-zone model (TOOL-02)
# Zone membership: >= lower AND < upper (except Z5: >= lower only) -- mirrors power zone convention
HR_ZONE_BOUNDARIES = [
    {"zone": 1, "name": "Active Recovery", "lower": 0.00, "upper": 0.81},
    {"zone": 2, "name": "Aerobic",         "lower": 0.81, "upper": 0.90},
    {"zone": 3, "name": "Tempo",           "lower": 0.90, "upper": 0.94},
    {"zone": 4, "name": "Threshold",       "lower": 0.94, "upper": 1.00},
    {"zone": 5, "name": "VO2max",          "lower": 1.00, "upper": None},
]

# CP model quality-effort filter (ftp.py) -- D-03
QUALITY_EFFORT_MIN_DURATION_SECS: int = 180    # 3 minutes
QUALITY_EFFORT_MIN_POWER_RATIO: float = 0.85   # 85% of best FTP estimate
QUALITY_EFFORT_FALLBACK_WATTS: float = 150.0   # threshold when no FTP estimate
MIN_QUALITY_EFFORTS: int = 4
