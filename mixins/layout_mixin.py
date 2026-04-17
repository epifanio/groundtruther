"""Dock-layout persistence and default-layout reset."""
from qgis.PyQt.QtCore import QSettings, Qt
from qgis.PyQt.QtWidgets import QAction

_KEY = "GroundTruther/layout"

# Default dock areas for each managed dock (attribute name → Qt area value)
_DEFAULTS = {
    "_image_dock":  Qt.DockWidgetArea.RightDockWidgetArea,
    "_video_dock":  Qt.DockWidgetArea.RightDockWidgetArea,
    "_report_dock": Qt.DockWidgetArea.RightDockWidgetArea,
    "_query_dock":  Qt.DockWidgetArea.RightDockWidgetArea,
}


class LayoutMixin:
    """Saves / restores floating-dock geometry and wires the reset action."""

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def _init_layout(self) -> None:
        """Add 'Restore Default Layout' action and restore saved layout.

        Must be called after all dock-creating _init_* methods so that every
        managed dock already exists.
        """
        self._restore_layout()
        self._add_layout_menu_action()

    def _save_layout(self) -> None:
        """Persist current dock geometry / state to QSettings."""
        from qgis.utils import iface as _iface
        mw = _iface.mainWindow()
        s = QSettings()
        for attr in _DEFAULTS:
            dock = getattr(self, attr, None)
            if dock is None:
                continue
            prefix = f"{_KEY}/{attr}"
            s.setValue(f"{prefix}/geometry", dock.saveGeometry())
            # Store as explicit "true"/"false" strings — avoids PyQt6 type-coercion
            # surprises when reading back with s.value(..., type=bool).
            s.setValue(f"{prefix}/floating", "true" if dock.isFloating() else "false")
            s.setValue(f"{prefix}/visible",  "true" if dock.isVisible()  else "false")
            if not dock.isFloating():
                s.setValue(f"{prefix}/area", int(mw.dockWidgetArea(dock)))

    def _restore_layout(self) -> None:
        """Apply previously saved dock geometry, position and visibility from QSettings.

        On first run (no saved state) all docks remain hidden.  On subsequent
        loads the last-session visibility is restored so docks re-open where the
        user left them.  Toolbar toggle actions are synced automatically via
        each dock's visibilityChanged signal.
        """
        from qgis.utils import iface as _iface
        mw = _iface.mainWindow()
        s = QSettings()
        for attr, default_area in _DEFAULTS.items():
            dock = getattr(self, attr, None)
            if dock is None:
                continue
            prefix = f"{_KEY}/{attr}"

            # Use s.contains() to distinguish "not yet saved" from a False value.
            if not s.contains(f"{prefix}/floating"):
                continue  # first run — keep hidden at default position

            floating = s.value(f"{prefix}/floating") in (True, "true", "1", 1)
            visible_raw = s.value(f"{prefix}/visible")
            visible = visible_raw in (True, "true", "1", 1) if visible_raw is not None else False
            geom = s.value(f"{prefix}/geometry")
            area_raw = s.value(f"{prefix}/area")
            area_int = int(area_raw) if area_raw is not None else None

            if floating:
                dock.setFloating(True)
                if geom is not None:
                    dock.restoreGeometry(geom)
            else:
                dock_area = Qt.DockWidgetArea(area_int) if area_int else default_area
                mw.addDockWidget(dock_area, dock)
                dock.setFloating(False)
                if geom is not None:
                    dock.restoreGeometry(geom)

            # Restore visibility last — fires visibilityChanged which syncs toolbar actions.
            dock.setVisible(visible)

    def _reset_default_layout(self) -> None:
        """Move all managed docks back to their default positions."""
        from qgis.utils import iface as _iface
        mw = _iface.mainWindow()
        for attr, default_area in _DEFAULTS.items():
            dock = getattr(self, attr, None)
            if dock is None:
                continue
            dock.setFloating(False)
            mw.addDockWidget(default_area, dock)
        for attr in ('_image_dock', '_video_dock', '_report_dock', '_query_dock'):
            dock = getattr(self, attr, None)
            if dock is not None:
                dock.hide()

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    def _has_saved_layout(self) -> bool:
        """Return True if at least one dock has a persisted position."""
        s = QSettings()
        return any(
            s.contains(f"{_KEY}/{attr}/floating") for attr in _DEFAULTS
        )

    def _position_child_docks_below(self) -> None:
        """Split each child dock below the main GroundTruther dock (first-run only).

        Must be called after the main dock has been added to the QGIS main window,
        i.e. from groundtruther.py run() — not during __init__.
        """
        from qgis.utils import iface as _iface
        mw = _iface.mainWindow()
        for attr in _DEFAULTS:
            dock = getattr(self, attr, None)
            if dock is None:
                continue
            mw.splitDockWidget(self, dock, Qt.Orientation.Vertical)

    def _add_layout_menu_action(self) -> None:
        from groundtruther.mixins.toolbar_icons import make_icon
        action = QAction(self)
        action.setIcon(make_icon("arrows-rotate.svg"))
        action.setToolTip("Restore default layout")
        action.triggered.connect(self._reset_default_layout)
        self.w.toolBar.addSeparator()
        self.w.toolBar.addAction(action)
