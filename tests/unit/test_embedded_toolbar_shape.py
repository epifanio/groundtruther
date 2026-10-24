# GroundTruther — a toolset for seafloor characterization
#
# Copyright (C) 2023-2026 Massimo Di Stefano <epiesasha@me.com>
# https://github.com/epifanio/groundtruther
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Regression guard for the Qt6 dock-walk crash.

**The fault this pins down.** A ``QMainWindow`` that owns an
``addToolBar()``-registered toolbar must not sit inside a dock registered on the
QGIS main window.  ``addToolBar()`` — and every ``QToolBar.addWidget()`` call on
the result — creates a wrapper action, and Qt6 dereferences that action's widget
mapping in ``QToolBar::widgetForAction`` while walking the widget tree during a
dock move.  The result is an access violation that takes QGIS down with it; the
symptom is recorded in ``CLAUDE.md``'s CRITICAL list, and the fix that first
diagnosed it is ``9ffac03``, whose own comment says the cause was
"addToolBar()'s QToolBarWidgetAction bookkeeping, not dock reparenting itself".

Three ``QMainWindow``s are in that embedded position today: ``self.w`` (the
``.ui``-generated window inside the plugin's own dock), ``_image_inner_window``
and ``_video_inner_window``.  Each builds its toolbar as a plain ``QToolBar`` in a
``QVBoxLayout`` instead, and ``init_ui`` additionally strips ``self.w``'s
``.ui``-declared toolbar with ``removeToolBar``.  ``GrassTools``, which reaches
the ``gisTools`` dock through ``gisToolSplitter``, was the fourth until it stopped
being a ``QMainWindow`` at all — it is a plain ``QWidget`` now, which is why
``test_grasstools_is_a_plain_qwidget`` guards the base class as well.

**Why this test is source-level.** The crash is an access violation, not an
exception: it kills the interpreter, so a behavioural assertion reports nothing
at all — the same argument ``test_image_metadata_panel.py`` makes for the pandas
SIGSEGV.  It also needs a real QGIS main window and a window manager to walk,
neither of which CI has; measured offscreen in QGIS 4.2.3's own interpreter, the
dock-walk completes without crashing *whether or not* the bug is present.  So
the only thing CI can protect is the *shape of the call*, which is what this
does.  Proved non-vacuous: it fails on the pre-fix ``pygui/grass_mdi_gui.py``.
"""

import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]

# Files whose QMainWindow ends up inside a dock registered on the QGIS main window.
EMBEDDED_WINDOW_FILES = [
    "groundtruther_dockwidget.py",
    "pygui/grass_mdi_gui.py",
    "mixins/image_browser_mixin.py",
    "mixins/video_browser_mixin.py",
]


def _addtoolbar_calls(path):
    """Every ``<something>.addToolBar(...)`` in a file, except ``iface.addToolBar``.

    ``self.iface.addToolBar`` in ``groundtruther.py`` is the plugin's own toolbar in
    the QGIS main window — the supported API, and not what crashes.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != "addToolBar":
            continue
        receiver = func.value
        if isinstance(receiver, ast.Attribute) and receiver.attr == "iface":
            continue
        if isinstance(receiver, ast.Name) and receiver.id in ("iface", "_iface"):
            continue
        out.append(node.lineno)
    return out


@pytest.mark.parametrize("relpath", EMBEDDED_WINDOW_FILES)
def test_an_embedded_window_registers_no_toolbar(relpath):
    path = ROOT / relpath
    assert path.is_file(), f"{relpath} has moved — update EMBEDDED_WINDOW_FILES"
    lines = _addtoolbar_calls(path)
    assert not lines, (
        f"{relpath} calls addToolBar() at line(s) {lines}. That window is embedded in a "
        "dock registered on the QGIS main window, so the wrapper actions addToolBar() "
        "creates are what Qt6 dereferences in QToolBar::widgetForAction during a dock "
        "move — the crash in CLAUDE.md's CRITICAL list. Build the toolbar as a plain "
        "QToolBar in a QVBoxLayout instead, as the other three do."
    )


def test_the_grass_toolbar_is_a_plain_qtoolbar():
    """``GrassTools.moduleToolBar`` must be constructed, not registered.

    The positive half of the guard: deleting the ``addToolBar`` call is not enough,
    the toolbar still has to exist and still has to reach the layout.
    """
    src = (ROOT / "pygui/grass_mdi_gui.py").read_text(encoding="utf-8")
    assert "self.moduleToolBar = QToolBar()" in src, (
        "GrassTools.moduleToolBar is no longer built as a plain QToolBar()"
    )
    assert "addWidget(self.moduleToolBar)" in src, (
        "GrassTools.moduleToolBar is built but never added to a layout — it would "
        "not be shown at all"
    )


def test_grasstools_is_a_plain_qwidget():
    """``GrassTools`` must not go back to being a ``QMainWindow``.

    It uses no ``QMainWindow`` feature — no menu bar, no status bar, no docks and
    no registered toolbar — and being one is what made `addToolBar()` reachable in
    the first place.  A ``QWidget`` cannot call it.
    """
    src = (ROOT / "pygui/grass_mdi_gui.py").read_text(encoding="utf-8")
    assert "class GrassTools(QWidget):" in src, (
        "GrassTools is no longer a plain QWidget. It sits inside the gisTools dock "
        "registered on the QGIS main window, so making it a QMainWindow again puts "
        "addToolBar() and the dock-walk crash back within reach."
    )
    assert "class GrassTools(QMainWindow)" not in src
