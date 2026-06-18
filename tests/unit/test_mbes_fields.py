"""Unit tests for gt.mbes_fields backscatter-column detection."""
from groundtruther.gt.mbes_fields import (
    detect_backscatter_fields,
    default_backscatter_field,
)

LEGACY = [
    "Ping Time", "Easting", "Northing", "Depth", "Longitude", "Latitude",
    "Backscatter Value", "Corrected Backscatter Value", "True Angle", "line",
]

MULTILEVEL = [
    "Ping Time", "Easting", "Northing", "Depth", "Longitude", "Latitude",
    "Nominal Angle", "True Angle", "Beam Flag",
    "BS_raw_dB", "BS_RL_dB", "BS_TL_dB", "BS_area_dB", "BS_AVG_dB", "line",
]


def test_legacy_schema():
    assert detect_backscatter_fields(LEGACY) == [
        "Corrected Backscatter Value", "Backscatter Value",
    ]
    # default preserves the historical choice
    assert default_backscatter_field(LEGACY) == "Corrected Backscatter Value"


def test_multilevel_schema():
    fields = detect_backscatter_fields(MULTILEVEL)
    assert fields == ["BS_AVG_dB", "BS_area_dB", "BS_TL_dB", "BS_RL_dB", "BS_raw_dB"]
    # BS_AVG_dB is the multi-level equivalent of the legacy corrected value
    assert default_backscatter_field(MULTILEVEL) == "BS_AVG_dB"


def test_no_backscatter_columns():
    assert detect_backscatter_fields(["Easting", "Northing", "Depth"]) == []
    assert default_backscatter_field(["Easting", "Northing"]) is None


def test_unknown_backscatter_columns_appended():
    # future-proofing: unrecognised BS_*/backscatter columns still surface
    cols = ["BS_AVG_dB", "BS_custom_dB", "My Backscatter Thing", "Depth"]
    fields = detect_backscatter_fields(cols)
    assert fields[0] == "BS_AVG_dB"
    assert "BS_custom_dB" in fields
    assert "My Backscatter Thing" in fields
    assert "Depth" not in fields
