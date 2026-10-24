"""GUI tests for dock-layout persistence (``mixins/layout_mixin.py``).

Runs under the Qt 'offscreen' platform. Skipped automatically if QGIS/Qt is not
importable. To run:

    QT_QPA_PLATFORM=offscreen \
    PYTHONPATH=/usr/share/qgis/python \
    .venv/bin/pytest tests/gui -m gui

**What these pin down.** The owner reported on 2026-10-24 that dragging the
plugin's panels around left them *"in the wrong place, or stay floating"*.
``_save_layout``/``_restore_layout`` stored a per-dock ``saveGeometry`` — a bare
rectangle, which cannot express "docked on the left", let alone tabbed or split —
so a docked panel came back floating. The sibling ``_capture_layout`` already
used ``QMainWindow.saveState()`` for exactly this reason and said so in its
docstring; these tests hold the everyday path to the same standard.

They use a real ``QMainWindow`` with real ``QDockWidget``s, a fake ``iface``, and
QSettings redirected into ``tmp_path`` — never the developer's own QGIS settings.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("qgis.PyQt.QtWidgets", reason="QGIS/Qt not available")

pytestmark = pytest.mark.gui

from qgis.PyQt.QtCore import QSettings, Qt                       # noqa: E402
from qgis.PyQt.QtWidgets import (                                # noqa: E402
    QApplication, QDockWidget, QMainWindow, QWidget)

from groundtruther.mixins.layout_mixin import (                  # noqa: E402
    _DEFAULTS, _KEY, _STATE_KEY, LayoutMixin)

LEFT = Qt.DockWidgetArea.LeftDockWidgetArea
RIGHT = Qt.DockWidgetArea.RightDockWidgetArea


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def settings_in_tmp(tmp_path, monkeypatch):
    """Point QSettings at tmp_path so the real QGIS settings are untouched."""
    monkeypatch.setattr(
        QSettings, "setDefaultFormat", QSettings.setDefaultFormat, raising=False)
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat,
                      QSettings.Scope.UserScope, str(tmp_path))
    QSettings().clear()
    yield
    QSettings().clear()


class _Host(LayoutMixin):
    """The smallest thing LayoutMixin needs: six named docks on a main window."""

    def __init__(self, mw):
        self._mw = mw
        for attr in _DEFAULTS:
            dock = QDockWidget(attr, mw)
            # An objectName is what restoreState matches on; the real docks all
            # set one, and without it Qt silently skips the dock.
            dock.setObjectName(f"GroundTruther{attr}")
            dock.setAllowedAreas(Qt.DockWidgetArea(15))
            dock.setWidget(QWidget())
            mw.addDockWidget(RIGHT, dock)
            dock.hide()
            setattr(self, attr, dock)


@pytest.fixture
def host(app, monkeypatch):
    import qgis.utils
    mw = QMainWindow()
    # The window must be shown, or every dock inside it reports isVisible()
    # False whatever we set — a child of a hidden parent is not visible. Under
    # the offscreen platform nothing is drawn.
    mw.show()
    monkeypatch.setattr(qgis.utils, "iface",
                        type("Iface", (), {"mainWindow": lambda _s: mw})(),
                        raising=False)
    host = _Host(mw)
    yield host, mw
    mw.close()


def _settle(app):
    """Let the deferred restoreState (QTimer.singleShot(0)) run."""
    app.processEvents()


def test_a_docked_panel_comes_back_docked(host, app):
    """The regression: dock on the left, save, disturb, restore → left again."""
    h, mw = host
    dock = h._image_dock
    mw.addDockWidget(LEFT, dock)
    dock.setVisible(True)
    assert not dock.isFloating()

    h._save_layout()

    # Disturb it the way dragging it out would.
    dock.setFloating(True)
    assert dock.isFloating()

    h._restore_layout()
    _settle(app)

    assert not dock.isFloating(), "the dock came back floating"
    assert mw.dockWidgetArea(dock) == LEFT, "the dock came back in the wrong area"


def test_the_arrangement_is_stored_as_a_state_blob(host):
    """Not just a rectangle: the whole-window state must be written."""
    h, mw = host
    h._image_dock.setVisible(True)
    h._save_layout()

    assert QSettings().contains(_STATE_KEY), (
        "no mainwindow_state written; per-dock geometry alone cannot express "
        "docked / tabbed / split placement"
    )
    # The per-dock keys stay, for a downgrade or an existing settings file.
    assert QSettings().contains(f"{_KEY}/_image_dock/floating")


def test_a_closed_panel_stays_closed(host, app):
    """restoreState must not re-open a dock the user had closed."""
    h, mw = host
    h._image_dock.setVisible(True)
    h._video_dock.setVisible(False)
    h._save_layout()

    h._image_dock.setVisible(False)
    h._video_dock.setVisible(True)

    h._restore_layout()
    _settle(app)

    assert h._image_dock.isVisible() is True
    assert h._video_dock.isVisible() is False


def test_first_run_leaves_every_dock_hidden(host, app):
    """With nothing saved, _restore_layout must not show anything."""
    h, mw = host
    assert not h._has_saved_layout()

    h._restore_layout()
    _settle(app)

    for attr in _DEFAULTS:
        assert not getattr(h, attr).isVisible(), attr


def test_has_saved_layout_sees_the_state_blob(host):
    """run() gates first-run positioning on this; a blob alone must count.

    Answering False while a blob exists would push the default arrangement over
    the layout just restored.
    """
    h, _ = host
    assert not h._has_saved_layout()
    h._save_layout()
    assert h._has_saved_layout()

    # …and it still counts when only the blob is present.
    s = QSettings()
    for attr in _DEFAULTS:
        for leaf in ("floating", "visible", "geometry", "area"):
            s.remove(f"{_KEY}/{attr}/{leaf}")
    assert s.contains(_STATE_KEY)
    assert h._has_saved_layout()


def test_reset_drops_the_stored_arrangement(host):
    """Otherwise a crash before close would resurrect the old layout."""
    h, mw = host
    h._image_dock.setVisible(True)
    h._save_layout()
    assert QSettings().contains(_STATE_KEY)

    h._reset_default_layout()

    assert not QSettings().contains(_STATE_KEY)
    for attr, default_area in _DEFAULTS.items():
        dock = getattr(h, attr)
        assert not dock.isFloating(), attr
        assert mw.dockWidgetArea(dock) == default_area, attr
