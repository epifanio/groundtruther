"""GUI tests for the schema-driven module form (pygui/grass_module_form.py).

Runs under the Qt 'offscreen' platform. Skipped automatically if QGIS/Qt is not
importable (e.g. plain CI without QGIS on PYTHONPATH). To run:

    QT_QPA_PLATFORM=offscreen \
    PYTHONPATH=/usr/share/qgis/python \
    .venv/bin/pytest tests/gui -m gui
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Skip the whole module unless QGIS's Qt bindings are importable.
pytest.importorskip("qgis.PyQt.QtWidgets", reason="QGIS/Qt not available")

pytestmark = pytest.mark.gui


@pytest.fixture(scope="module")
def qapp():
    from qgis.PyQt.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def schema():
    return {
        "module": "r.geomorphon",
        "label": "Geomorphic features",
        "parameters": [
            {"name": "elevation", "type": "name", "required": True,
             "gisprompt": {"age": "old", "prompt": "raster"}},
            {"name": "forms", "type": "name", "required": False,
             "gisprompt": {"age": "new", "prompt": "raster"}},
            {"name": "search", "type": "integer", "required": False, "default": "3"},
            {"name": "comparison", "type": "string", "required": False,
             "options": ["forms", "anglev1"], "default": "forms"},
        ],
        "flags": [{"name": "m", "description": "meters"}, {"name": "overwrite"}],
    }


def test_pure_helpers():
    from groundtruther.pygui import grass_module_form as f
    assert f.param_kind({"options": ["a"]}) == "enum"
    assert f.param_kind({"gisprompt": {"age": "old", "prompt": "raster"}}) == "old"
    assert f.param_kind({"type": "integer"}) == "integer"
    assert f.param_kind({"type": "double"}) == "float"
    assert f.param_kind({"type": "string"}) == "text"
    assert f.build_args({"input": "dem", "size": "3"}, ["f", "overwrite"]) == \
        ["-f", "--overwrite", "input=dem", "size=3"]


def test_form_builds_and_collects(qapp, schema):
    from groundtruther.pygui.grass_module_form import GrassModuleForm
    form = GrassModuleForm(schema)

    # 'elevation' is an existing-raster gisprompt -> needs a g.list of rasters
    assert form.needed_gisprompt_types() == ["raster"]

    # required 'elevation' empty -> reported missing
    assert "elevation" in form.missing_required()

    # defaults are collected
    params, flags = form.collect_values()
    assert params.get("search") == "3"
    assert params.get("comparison") == "forms"
    assert flags == []

    # populate the existing-raster combo, then it should accept a value
    form.set_existing_items({"raster": ["dem", "bathy"]})
    params, _ = form.collect_values()  # still empty until user picks; just no crash
    assert isinstance(params, dict)


def test_build_args_roundtrip(qapp, schema):
    from groundtruther.pygui.grass_module_form import GrassModuleForm
    form = GrassModuleForm(schema)
    args = form.build_args()
    # defaults present, no flags checked
    assert "search=3" in args and "comparison=forms" in args
    assert not any(a.startswith("-") for a in args)
