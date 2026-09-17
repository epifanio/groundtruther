"""Regression test for #27 — the plugin must not publish itself under bare names.

``groundtruther.py`` used to run ``sys.path.append(os.path.dirname(__file__))`` at
import time (and ``querybuilder_gui`` / ``kmlsave_gui`` appended the plugin root
again).  Because every QGIS plugin in the process shares one ``sys.modules``, that
published ~19 plugin modules — ``gt``, ``mixins``, ``configure``, ``ioutils``,
``rectangle``, ``qtpandas``, … — as *top-level* names, and any module imported both
ways existed twice, with its module-level state duplicated.

The check has to happen in a subprocess: it is about the state of ``sys.path`` and
``sys.modules`` after a real plugin load, and ``tests/conftest.py`` has already
wired ``groundtruther`` up differently in the pytest process.

Run with::

    QT_QPA_PLATFORM=offscreen PYTHONPATH=/usr/share/qgis/python \
        .venv/bin/pytest tests/gui/test_import_hygiene.py -m gui
"""
import json
import os
import pathlib
import subprocess
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("qgis.PyQt.QtWidgets", reason="QGIS/Qt not available")
pytest.importorskip("qgis.utils", reason="QGIS/Qt not available")

pytestmark = pytest.mark.gui

ROOT = pathlib.Path(__file__).resolve().parents[2]

# Loads the plugin the way QGIS does, then reports what leaked into the
# top-level module namespace.  Printed as one JSON line on stdout.
PROBE = r'''
import importlib.util, json, os, pathlib, sys

PLUGINS = sys.argv[1]
PLUGIN_DIR = str(pathlib.Path(PLUGINS, "groundtruther").resolve())
sys.path.insert(0, PLUGINS)

from qgis.core import QgsApplication
QgsApplication.setPrefixPath(os.environ.get("QGIS_PREFIX_PATH", "/usr"), True)
app = QgsApplication([], False)
app.initQgis()

import qgis.utils
qgis.utils.plugin_paths = [PLUGINS]
loaded = qgis.utils.loadPlugin("groundtruther")

# classFactory() imports the plugin module; do the same, since that is where the
# sys.path mutation used to happen.
importlib.import_module("groundtruther.groundtruther")

leaked = {}
for entry in sorted(os.listdir(PLUGIN_DIR)):
    if entry.startswith((".", "__")):
        continue
    path = pathlib.Path(PLUGIN_DIR, entry)
    if path.is_file() and entry.endswith(".py"):
        name = entry[:-3]
    elif path.is_dir():
        name = entry
    else:
        continue
    if name == "groundtruther":          # the plugin package itself — expected
        continue
    try:
        spec = importlib.util.find_spec(name)
    except Exception:
        continue
    if spec is None:
        continue
    where = getattr(spec, "origin", None) or next(
        iter(getattr(spec, "submodule_search_locations", None) or []), "")
    if where and str(pathlib.Path(where).resolve()).startswith(PLUGIN_DIR):
        leaked[name] = where

print(json.dumps({
    "loaded": loaded,
    "plugin_dir_on_sys_path": PLUGIN_DIR in [
        str(pathlib.Path(p).resolve()) for p in sys.path if p],
    "leaked": leaked,
    # a bare spelling of a plugin module already resolved would sit in sys.modules
    "bare_in_sys_modules": sorted(
        n for n in sys.modules
        if n.split(".")[0] in ("gt", "mixins", "pygui", "ioutils", "configure",
                               "config_model", "maptools", "qtpandas", "ellipse",
                               "rectangle", "episg", "epsg_list", "grassconfig",
                               "search_epsg", "resources_rc", "pip_cpu", "pip_cuda",
                               "groundtruther_dockwidget")),
}))
'''


@pytest.fixture(scope="module")
def probe(tmp_path_factory):
    """Load the plugin in a subprocess and return its namespace report."""
    plugins = tmp_path_factory.mktemp("plugins")
    # QGIS imports a plugin by its directory name, which must be `groundtruther`.
    (plugins / "groundtruther").symlink_to(ROOT, target_is_directory=True)

    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    # Hand the child whatever makes `qgis` importable here — but never the repo
    # root itself: pytest puts it on sys.path, and that alone would make every
    # plugin module resolve under a bare name and the test vacuous.
    env["PYTHONPATH"] = os.pathsep.join(
        p for p in sys.path if p and pathlib.Path(p).resolve() != ROOT)
    # cwd matters: `python -c` prepends it to sys.path, and running from the repo
    # root would put the plugin directory back on the path behind our backs.  The
    # plugins directory is what QGIS itself has there.
    proc = subprocess.run(
        [sys.executable, "-c", PROBE, str(plugins)],
        capture_output=True, text=True, env=env, timeout=300, cwd=str(plugins),
    )
    if proc.returncode != 0:
        pytest.fail(f"plugin load probe failed:\n{proc.stdout}\n{proc.stderr}")
    # QGIS is chatty on stderr and can be on stdout too; the report is the last line.
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_the_plugin_loads(probe):
    assert probe["loaded"] is True


def test_the_plugin_directory_is_not_on_sys_path(probe):
    """Only the *plugins* directory belongs on sys.path, never the plugin's own."""
    assert probe["plugin_dir_on_sys_path"] is False


def test_no_plugin_module_resolves_under_a_bare_name(probe):
    """`import gt`, `import ioutils`, … must not reach into this plugin.

    A leak here means some module is importable both as ``groundtruther.X`` and as
    ``X``: two module objects from one file, duplicated module-level state, and a
    name that can collide with another plugin's.
    """
    assert probe["leaked"] == {}, (
        "these plugin-local modules leaked into the top-level namespace: "
        + ", ".join(sorted(probe["leaked"]))
    )


def test_no_bare_plugin_module_was_imported(probe):
    assert probe["bare_in_sys_modules"] == []
