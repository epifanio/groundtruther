"""Unit tests for per-key config validation (``gt/config_check.py``).

Covers the reported failure chain: a stale ``HabCam.imagepath`` (an external
drive remounted under a different label) used to invalidate the *whole* config,
blank every path including ``Mbes.soundings``, and crash the plugin inside
``pd.read_parquet("")`` before any UI existed.
"""
import pytest

from groundtruther.config_model import HabcamSettings
from groundtruther.gt import config_check
from groundtruther.gt.config_check import (
    ERROR, WARNING, ConfigReport, Finding, check_settings, degrade,
    as_bool, as_float, as_int, as_path_str,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def good(tmp_path):
    """A fully valid settings dict backed by real files under *tmp_path*."""
    (tmp_path / "images").mkdir()
    for name in ("meta.parquet", "soundings.parquet", "annotations.csv",
                 "surface.tif", "video.mp4", "video.csv", "fm"):
        (tmp_path / name).write_bytes(b"")
    (tmp_path / "export").mkdir()
    return {
        "HabCam": {
            "imagepath": str(tmp_path / "images"),
            "imagemetadata": str(tmp_path / "meta.parquet"),
            "imageannotation": str(tmp_path / "annotations.csv"),
        },
        "Mbes": {
            "soundings": str(tmp_path / "soundings.parquet"),
            "reference_surface": str(tmp_path / "surface.tif"),
        },
        "Export": {"kmldir": str(tmp_path / "export")},
        "Processing": {
            "gpu_avaibility": False,
            "grass_api_endpoint": "https://api.fastgis.eu",
            "grass_api_key": "fgk_abc",
        },
        "Filesystem": {"filemanager": str(tmp_path / "fm")},
        "Video": {
            "videofile": str(tmp_path / "video.mp4"),
            "videometadata": str(tmp_path / "video.csv"),
            "videoannotation": None,
        },
        "Session": {"groundtruther_project": str(tmp_path / "session.json")},
        "Roughness": {"georeference": True, "epsg": 32619, "res_mm": 3.0},
    }


def _keys(findings):
    return [f.key for f in findings]


# ---------------------------------------------------------------------------
# Baseline
# ---------------------------------------------------------------------------

def test_valid_config_has_no_findings(good):
    report = check_settings(good)
    assert report.errors == []
    assert report.warnings == []
    assert report.ok
    assert report.message() == ""


def test_unset_optional_keys_are_silent(good):
    """The normal half-configured install must produce no noise."""
    for section, key in (("Mbes", "soundings"), ("Export", "kmldir"),
                         ("Filesystem", "filemanager"),
                         ("Processing", "grass_api_key")):
        good[section][key] = None
    good.pop("Video")
    good.pop("Roughness")
    report = check_settings(good)
    assert report.ok
    assert report.warnings == []


def test_spec_covers_exactly_the_pydantic_model():
    """SPEC and ``config_model`` must not silently drift apart."""
    model_keys = set()
    for section, info in HabcamSettings.model_fields.items():
        nested = info.annotation
        for candidate in getattr(nested, "__args__", (nested,)):
            fields = getattr(candidate, "model_fields", None)
            if fields:
                model_keys |= {f"{section}.{name}" for name in fields}
    spec_keys = {item.key for item in config_check.SPEC}
    assert spec_keys == model_keys


# ---------------------------------------------------------------------------
# Required keys → errors
# ---------------------------------------------------------------------------

def test_missing_imagepath_is_an_error(good, tmp_path):
    good["HabCam"]["imagepath"] = str(tmp_path / "does-not-exist")
    report = check_settings(good)
    assert _keys(report.errors) == ["HabCam.imagepath"]
    assert report.errors[0].severity == ERROR
    assert not report.ok
    assert "does not exist" in report.errors[0].reason


def test_unset_required_key_is_an_error(good):
    good["HabCam"]["imagemetadata"] = ""
    report = check_settings(good)
    assert _keys(report.errors) == ["HabCam.imagemetadata"]
    assert report.errors[0].reason == "not set"


def test_missing_habcam_section_errors_on_both_required_keys(good):
    good.pop("HabCam")
    report = check_settings(good)
    assert _keys(report.errors) == ["HabCam.imagepath", "HabCam.imagemetadata"]


def test_imagepath_pointing_at_a_file_is_an_error(good, tmp_path):
    good["HabCam"]["imagepath"] = str(tmp_path / "meta.parquet")
    report = check_settings(good)
    assert "not a directory" in report.errors[0].reason


def test_imagemetadata_pointing_at_a_directory_is_an_error(good, tmp_path):
    good["HabCam"]["imagemetadata"] = str(tmp_path)
    report = check_settings(good)
    assert "not a file" in report.errors[0].reason


def test_no_settings_at_all_is_an_error():
    report = check_settings(None)
    assert _keys(report.errors) == ["config"]
    assert not report.ok


def test_non_mapping_settings_is_an_error():
    report = check_settings("HabCam: /some/path")
    assert _keys(report.errors) == ["config"]


# ---------------------------------------------------------------------------
# Optional keys → warnings, one feature each
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("section,key", [
    ("HabCam", "imageannotation"),
    ("Mbes", "soundings"),
    ("Mbes", "reference_surface"),
    ("Export", "kmldir"),
    ("Filesystem", "filemanager"),
    ("Video", "videofile"),
    ("Video", "videometadata"),
])
def test_stale_optional_path_is_only_a_warning(good, tmp_path, section, key):
    good[section][key] = str(tmp_path / "gone")
    report = check_settings(good)
    assert report.ok, "an optional key must never block startup"
    assert _keys(report.warnings) == [f"{section}.{key}"]
    assert report.warnings[0].severity == WARNING


def test_bad_grass_endpoint_is_a_warning(good):
    good["Processing"]["grass_api_endpoint"] = "not a url"
    report = check_settings(good)
    assert report.ok
    assert _keys(report.warnings) == ["Processing.grass_api_endpoint"]
    assert "not a valid http(s) URL" in report.warnings[0].reason


def test_session_file_need_not_exist_but_its_directory_must(good, tmp_path):
    assert check_settings(good).ok             # session.json does not exist yet
    good["Session"]["groundtruther_project"] = str(tmp_path / "gone" / "s.json")
    report = check_settings(good)
    assert _keys(report.warnings) == ["Session.groundtruther_project"]
    assert "parent directory does not exist" in report.warnings[0].reason


def test_non_mapping_optional_section_is_a_warning(good):
    good["Roughness"] = "georeference: true"
    report = check_settings(good)
    assert report.ok
    assert _keys(report.warnings) == ["Roughness"]


# ---------------------------------------------------------------------------
# Numeric sanity (Roughness)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key,value", [
    ("epsg", "not-a-number"),
    ("epsg", 12),                 # below the EPSG code range
    ("res_mm", "3 mm"),
    ("n_water", -1.0),
    ("dem_max_side", 0),
    ("dem_trim_border", -1),
    ("dem_clip_sigma", "lots"),
    ("dem_erode", 1.5),
    ("georeference", "maybe"),
])
def test_bad_roughness_value_is_a_warning(good, key, value):
    good["Roughness"][key] = value
    report = check_settings(good)
    assert report.ok, "roughness settings must never block startup"
    assert _keys(report.warnings) == [f"Roughness.{key}"]


@pytest.mark.parametrize("value", [True, False, "yes", "off", 1, 0])
def test_yaml_boolean_spellings_are_accepted(good, value):
    good["Processing"]["gpu_avaibility"] = value
    assert check_settings(good).ok


# ---------------------------------------------------------------------------
# The removable-media hint — the reported failure
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("prefix", ["/run/media", "/media", "/mnt", "/Volumes"])
def test_removable_media_hint(good, prefix):
    good["HabCam"]["imagepath"] = f"{prefix}/epinux/ssd1/HBC/DATA/2015_stereo"
    report = check_settings(good)
    assert "the drive may not be mounted" in report.errors[0].reason


def test_no_hint_for_an_ordinary_path(good, tmp_path):
    good["HabCam"]["imagepath"] = str(tmp_path / "gone")
    assert "may not be mounted" not in check_settings(good).errors[0].reason


# ---------------------------------------------------------------------------
# Regression: the reported crash chain
# ---------------------------------------------------------------------------

def test_broken_imagepath_does_not_blank_the_soundings(good):
    """The reported bug: an unmounted image drive killed the MBES query builder.

    ``HabCam.imagepath`` fails, but ``Mbes.soundings`` was set correctly, so it
    must survive ``degrade`` — the query builder then loads the parquet instead
    of calling ``pd.read_parquet("")`` and raising ``FileNotFoundError`` out of
    the dock's constructor.
    """
    soundings = good["Mbes"]["soundings"]
    good["HabCam"]["imagepath"] = "/run/media/epinux/ssd1/HBC/DATA/2015_stereo"

    report = check_settings(good)
    degraded = degrade(good, report)

    assert _keys(report.errors) == ["HabCam.imagepath"]
    assert degraded["Mbes"]["soundings"] == soundings
    assert degraded["HabCam"]["imagepath"] == ""
    # Everything the user got right is untouched
    assert degraded["HabCam"]["imagemetadata"] == good["HabCam"]["imagemetadata"]
    assert degraded["Export"]["kmldir"] == good["Export"]["kmldir"]


def test_degrade_blanks_only_the_failed_keys(good, tmp_path):
    good["Mbes"]["soundings"] = str(tmp_path / "gone.parquet")
    good["Export"]["kmldir"] = "/run/media/nope"
    report = check_settings(good)
    degraded = degrade(good, report)
    assert degraded["Mbes"]["soundings"] == ""
    assert degraded["Export"]["kmldir"] == ""
    assert degraded["HabCam"]["imagepath"] == good["HabCam"]["imagepath"]


def test_degrade_fills_every_section(good):
    good.pop("Video")
    good.pop("Roughness")
    good.pop("Session")
    degraded = degrade(good, check_settings(good))
    for section in config_check.SECTIONS:
        assert section in degraded
    # No KeyError for the lookups the dock does during __init__
    assert degraded["Video"]["videofile"] == ""
    assert degraded["Session"]["groundtruther_project"] == ""
    assert degraded["Processing"]["gpu_avaibility"] is False


def test_degrade_of_nothing_is_still_usable():
    degraded = degrade(None, check_settings(None))
    assert degraded["HabCam"]["imagepath"] == ""
    assert degraded["Mbes"]["soundings"] == ""
    assert degraded["Processing"]["gpu_avaibility"] is False


def test_degrade_does_not_mutate_the_input(good, tmp_path):
    good["Mbes"]["soundings"] = str(tmp_path / "gone.parquet")
    before = dict(good["Mbes"])
    degrade(good, check_settings(good))
    assert good["Mbes"] == before


def test_bad_section_blanks_only_that_section(good):
    good["Roughness"] = "not a mapping"
    degraded = degrade(good, check_settings(good))
    assert degraded["Roughness"]["epsg"] is None
    assert degraded["HabCam"]["imagepath"] == good["HabCam"]["imagepath"]


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------

def test_summary_names_the_key_and_the_value(good):
    good["HabCam"]["imagepath"] = "/run/media/epinux/ssd1/HBC/DATA/2015_stereo"
    summary = check_settings(good).summary()
    assert "HabCam.imagepath" in summary
    assert "/run/media/epinux/ssd1/HBC/DATA/2015_stereo" in summary
    assert "the drive may not be mounted" in summary


def test_message_separates_errors_from_warnings(good, tmp_path):
    good["HabCam"]["imagepath"] = str(tmp_path / "gone")
    good["Mbes"]["soundings"] = str(tmp_path / "gone.parquet")
    message = check_settings(good).message()
    assert "cannot start" in message
    assert "HabCam.imagepath" in message
    assert "Mbes.soundings" in message


def test_summary_can_hide_warnings(good, tmp_path):
    good["HabCam"]["imagepath"] = str(tmp_path / "gone")
    good["Mbes"]["soundings"] = str(tmp_path / "gone.parquet")
    errors_only = check_settings(good).summary(include_warnings=False)
    assert "HabCam.imagepath" in errors_only
    assert "Mbes.soundings" not in errors_only


def test_bad_keys_lists_errors_first(good, tmp_path):
    good["HabCam"]["imagepath"] = str(tmp_path / "gone")
    good["Mbes"]["soundings"] = str(tmp_path / "gone.parquet")
    assert check_settings(good).bad_keys() == [
        "HabCam.imagepath", "Mbes.soundings"]


def test_finding_str_is_key_colon_reason():
    finding = Finding("Mbes.soundings", "", "not set", WARNING)
    assert str(finding) == "Mbes.soundings: not set"
    assert ConfigReport(warnings=[finding]).ok


# ---------------------------------------------------------------------------
# Coercion helpers used by the consumers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    (32619, 32619), ("32619", 32619), (32619.0, 32619), ("32619.0", 32619),
    (None, 999), ("", 999), ("  ", 999), ("abc", 999), ([], 999), (True, 999),
])
def test_as_int(value, expected):
    assert as_int(value, 999) == expected


@pytest.mark.parametrize("value,expected", [
    (3.0, 3.0), ("3.0", 3.0), (3, 3.0), (None, 9.9), ("", 9.9), ("3 mm", 9.9),
])
def test_as_float(value, expected):
    assert as_float(value, 9.9) == expected


def test_as_int_and_as_float_default_to_none():
    assert as_int("junk") is None
    assert as_float("junk") is None


@pytest.mark.parametrize("value,expected", [
    (True, True), (False, False), ("true", True), ("Yes", True), ("on", True),
    ("1", True), ("false", False), ("no", False), ("off", False), ("0", False),
    (1, True), (0, False), (None, False), ("nonsense", False),
])
def test_as_bool(value, expected):
    assert as_bool(value, False) is expected


def test_as_bool_falls_back_to_the_given_default():
    assert as_bool("nonsense", True) is True
    assert as_bool(None, True) is True


@pytest.mark.parametrize("value,expected", [
    (None, ""), ("", ""), ("  ", ""), ("/a/b", "/a/b"), ("  /a/b  ", "/a/b"),
])
def test_as_path_str(value, expected):
    """Guards ``Path(None)`` and ``f"{None}/file.png"`` at the call sites."""
    assert as_path_str(value) == expected


# ---------------------------------------------------------------------------
# Lossless save — the Settings dialog used to delete whole sections
# ---------------------------------------------------------------------------

def _roundtrip(tmp_path, existing, updates):
    """Write *existing*, merge *updates* over it, write back, read back."""
    import yaml
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(existing, sort_keys=False), encoding="utf8")
    loaded = yaml.safe_load(path.read_text(encoding="utf8"))
    config_check.write_settings(path, config_check.merge_settings(loaded, updates))
    return yaml.safe_load(path.read_text(encoding="utf8"))


def test_save_preserves_the_roughness_section(tmp_path):
    """The dialog has no Roughness widgets; saving must not delete the section.

    Regression for the second defect found in the audit — ``write_config`` used
    to re-render the whole file from a fixed Jinja template that had no
    ``Roughness:`` block, so every save silently wiped it.
    """
    existing = {
        "HabCam": {"imagepath": "/data/images",
                   "imagemetadata": "/data/meta.parquet"},
        "Roughness": {"georeference": True, "epsg": 32619, "res_mm": 3.0,
                      "direct_url": "http://127.0.0.1:7871/roughness"},
    }
    # What the Settings dialog knows about — note: no Roughness at all.
    updates = {"HabCam": {"imagepath": "/data/images2",
                          "imagemetadata": "/data/meta.parquet"}}

    result = _roundtrip(tmp_path, existing, updates)

    assert result["Roughness"] == existing["Roughness"]
    assert result["HabCam"]["imagepath"] == "/data/images2"


def test_save_preserves_unknown_sections_and_keys(tmp_path):
    existing = {
        "HabCam": {"imagepath": "/a", "imagemetadata": "/b"},
        "Video": {"videofile": "/v.mp4", "videoannotation": "/v.csv"},
        "SomeFutureSection": {"knob": 1},
    }
    updates = {"Video": {"videofile": "/v2.mp4"}}   # no videoannotation widget

    result = _roundtrip(tmp_path, existing, updates)

    assert result["Video"] == {"videofile": "/v2.mp4", "videoannotation": "/v.csv"}
    assert result["SomeFutureSection"] == {"knob": 1}


def test_save_quotes_values_that_would_break_raw_yaml(tmp_path):
    """The old ``key: {{value}}`` template emitted invalid YAML for these."""
    tricky = "/data/dive: 2015 #1/images"
    result = _roundtrip(
        tmp_path, {}, {"HabCam": {"imagepath": tricky, "imagemetadata": "/b"}})
    assert result["HabCam"]["imagepath"] == tricky


def test_merge_settings_tolerates_no_existing_file():
    updates = {"HabCam": {"imagepath": "/a"}}
    assert config_check.merge_settings(None, updates) == updates


def test_merge_settings_does_not_mutate_the_loaded_document():
    existing = {"HabCam": {"imagepath": "/a", "imagemetadata": "/b"}}
    config_check.merge_settings(existing, {"HabCam": {"imagepath": "/c"}})
    assert existing["HabCam"]["imagepath"] == "/a"


def test_merge_settings_replaces_a_non_mapping_section():
    existing = {"Roughness": "oops"}
    merged = config_check.merge_settings(existing, {"Roughness": {"epsg": 1}})
    assert merged["Roughness"] == {"epsg": 1}
