"""GUI tests for the settings dialog (``configure.ConfigDialog``).

Runs under the Qt 'offscreen' platform. Skipped automatically if QGIS/Qt is not
importable (e.g. plain CI without QGIS on PYTHONPATH). To run:

    QT_QPA_PLATFORM=offscreen \
    PYTHONPATH=/usr/share/qgis/python \
    .venv/bin/pytest tests/gui -m gui

These exercise what unit tests cannot: that every key in the config model has a
widget, that the widgets round-trip through a real save, and that the save still
preserves sections/keys the dialog does not own.
"""
import importlib
import os
import sys

import pytest
import yaml

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Skip the whole module unless QGIS's Qt bindings are importable.
pytest.importorskip("qgis.PyQt.QtWidgets", reason="QGIS/Qt not available")

pytestmark = pytest.mark.gui

# conftest stubs `groundtruther.configure` so the Qt-free gt/ helpers can be
# imported without QGIS. This module needs the *real* one; swap it in, then put
# the stub back so the rest of the session is unaffected.
_stub = sys.modules.pop("groundtruther.configure", None)
configure = importlib.import_module("groundtruther.configure")
if _stub is not None:
    sys.modules["groundtruther.configure"] = _stub

from groundtruther.config_model import HabcamSettings          # noqa: E402
from groundtruther.gt import config_check                      # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from qgis.PyQt.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def config_file(tmp_path):
    """A complete config on disk, including a hand-edited Roughness section."""
    (tmp_path / "images").mkdir()
    (tmp_path / "meta.parquet").write_bytes(b"")
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump({
        "Filesystem": {"filemanager": "/usr/bin/nautilus"},
        "HabCam": {"imagepath": str(tmp_path / "images"),
                   "imagemetadata": str(tmp_path / "meta.parquet"),
                   "imageannotation": None},
        "Mbes": {"soundings": None, "reference_surface": None},
        "Export": {"kmldir": str(tmp_path)},
        "Processing": {"gpu_avaibility": False,
                       "grass_api_endpoint": "https://api.fastgis.eu",
                       "grass_api_key": "fgk_secret"},
        "Video": {"videofile": "/v.mp4", "videometadata": "/v.log",
                  "videoannotation": "/v_ann.csv"},
        "Session": {"groundtruther_project": str(tmp_path / "s.json")},
        "Roughness": {"georeference": True, "epsg": 32620, "res_mm": 3.0,
                      "mirror": True, "dem_max_side": 256, "dem_erode": 3,
                      "direct_url": "http://127.0.0.1:7871/roughness"},
    }, sort_keys=False), encoding="utf8")
    return path


@pytest.fixture
def dialog(qapp, config_file):
    dlg = configure.ConfigDialog()
    dlg.config = str(config_file)
    dlg._populate_fields()
    yield dlg
    # Destroy each dialog within the test that made it, rather than leaving a
    # pending deleteLater() for a later module's event loop to flush.
    dlg.close()
    dlg.setParent(None)
    dlg.deleteLater()
    qapp.processEvents()


def _saved(dialog):
    """Click Save and return the document that landed on disk."""
    dialog.write_config()
    with open(dialog.config, encoding="utf8") as fh:
        return yaml.safe_load(fh)


# ---------------------------------------------------------------------------
# Coverage — a config key with no widget can only be hand-edited in YAML
# ---------------------------------------------------------------------------

def test_dialog_covers_every_key_in_the_model(dialog):
    model_keys = set()
    for section, info in HabcamSettings.model_fields.items():
        nested = info.annotation
        for candidate in getattr(nested, "__args__", (nested,)):
            fields = getattr(candidate, "model_fields", None)
            if fields:
                model_keys |= {f"{section}.{name}" for name in fields}

    gui = dialog.get_gui_settings()
    gui_keys = {f"{section}.{name}"
                for section, values in gui.items() for name in values}
    assert model_keys - gui_keys == set()


def test_the_ui_is_built_exactly_once(dialog):
    """Regression: a cooperative ``super().__init__()`` ran setupUi twice.

    The duplicate widget set is what gets *shown* while the attribute
    references point at the newer one — so every other test here passes while
    the dialog on screen looks unpopulated and has none of the rows added
    programmatically. Counting the widgets is the only thing that catches it.
    """
    from qgis.PyQt.QtWidgets import QLineEdit
    for name in ("image_path", "metadata_path", "mbes_path", "kml_path",
                 "vrt_path", "video_path"):
        found = [w for w in dialog.findChildren(QLineEdit)
                 if w.objectName() == name]
        assert len(found) == 1, f"{name}: setupUi ran more than once"


def test_programmatic_rows_are_visible(dialog):
    """The rows built in code must really be in the shown widget tree."""
    for widget in (dialog.reference_surface_path, dialog.video_annotation_path,
                   dialog.roughness_config_box, dialog.vrt_path):
        assert widget.isVisibleTo(dialog), widget.objectName()


# ---------------------------------------------------------------------------
# Populate
# ---------------------------------------------------------------------------

def test_populate_reads_the_roughness_section(dialog):
    assert dialog.roughness_epsg.value() == 32620
    assert dialog.roughness_res_mm.value() == 3.0
    assert dialog.roughness_georeference.isChecked() is True
    assert dialog.roughness_mirror.isChecked() is True
    assert dialog.roughness_dem_max_side.value() == 256
    assert dialog.roughness_dem_erode.value() == 3
    assert dialog.roughness_direct_url.text() == "http://127.0.0.1:7871/roughness"
    # Keys absent from the file fall back to the model defaults
    assert dialog.roughness_dem_trim_border.value() == 2
    assert dialog.roughness_dem_clip_sigma.value() == 5.0
    assert dialog.roughness_base_url.text() == ""


def test_populate_reads_the_video_annotation(dialog):
    assert dialog.video_annotation_path.text() == "/v_ann.csv"


def test_populate_survives_junk_values(dialog, config_file):
    """A non-numeric epsg must show the default, not raise."""
    doc = yaml.safe_load(config_file.read_text())
    doc["Roughness"]["epsg"] = "not-a-number"
    doc["Roughness"]["georeference"] = "maybe"
    config_file.write_text(yaml.safe_dump(doc), encoding="utf8")
    dialog._populate_fields()
    assert dialog.roughness_epsg.value() == 32619
    assert dialog.roughness_georeference.isChecked() is False


def test_populate_survives_empty_yaml_values(dialog, config_file):
    """A key present with no value reads back as None; setText(None) raises."""
    config_file.write_text(
        "HabCam:\n  imagepath:\n  imagemetadata:\n"
        "Video:\n  videoannotation:\n", encoding="utf8")
    dialog._populate_fields()
    assert dialog.image_path.text() == ""
    assert dialog.video_annotation_path.text() == ""


# ---------------------------------------------------------------------------
# Round trip
# ---------------------------------------------------------------------------

def test_roughness_round_trips_through_a_save(dialog):
    dialog.roughness_epsg.setValue(32619)
    dialog.roughness_heading_offset.setValue(1.5)
    dialog.roughness_mirror.setChecked(False)
    dialog.roughness_dem_clip_sigma.setValue(3.5)
    dialog.roughness_base_url.setText("https://example.org")

    doc = _saved(dialog)

    assert doc["Roughness"]["epsg"] == 32619
    assert doc["Roughness"]["heading_offset_deg"] == 1.5
    assert doc["Roughness"]["mirror"] is False
    assert doc["Roughness"]["dem_clip_sigma"] == 3.5
    assert doc["Roughness"]["base_url"] == "https://example.org"
    # untouched fields keep the values loaded from disk
    assert doc["Roughness"]["dem_max_side"] == 256
    assert doc["Roughness"]["direct_url"] == "http://127.0.0.1:7871/roughness"


def test_video_annotation_round_trips(dialog):
    dialog.video_annotation_path.setText("/new_ann.csv")
    assert _saved(dialog)["Video"]["videoannotation"] == "/new_ann.csv"


def test_saving_an_unchanged_dialog_is_a_no_op(dialog, config_file):
    before = yaml.safe_load(config_file.read_text())
    after = _saved(dialog)
    for section, values in before.items():
        for key, value in values.items():
            assert after[section][key] == value, f"{section}.{key} changed"


def test_special_value_means_not_set(dialog):
    """The minimum of res_mm / n_water is 'service default', i.e. None."""
    dialog.roughness_res_mm.setValue(0.0)
    dialog.roughness_n_water.setValue(0.0)
    doc = _saved(dialog)
    assert doc["Roughness"]["res_mm"] is None
    assert doc["Roughness"]["n_water"] is None


def test_save_still_preserves_sections_the_dialog_does_not_own(dialog, config_file):
    doc = yaml.safe_load(config_file.read_text())
    doc["SomeFutureSection"] = {"knob": 1}
    config_file.write_text(yaml.safe_dump(doc), encoding="utf8")
    dialog._populate_fields()
    assert _saved(dialog)["SomeFutureSection"] == {"knob": 1}


def test_saved_document_passes_validation(dialog):
    report = config_check.check_settings(_saved(dialog))
    assert report.ok, report.summary()


def test_save_is_refused_when_a_required_path_is_broken(dialog, monkeypatch, tmp_path):
    shown = []
    monkeypatch.setattr(configure, "error_message", shown.append)
    dialog.image_path.setText(str(tmp_path / "does-not-exist"))
    before = dialog.config and open(dialog.config, encoding="utf8").read()

    dialog.write_config()

    assert shown and "HabCam.imagepath" in shown[0]
    assert open(dialog.config, encoding="utf8").read() == before, "file was written"
