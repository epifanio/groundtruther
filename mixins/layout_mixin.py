"""Dock-layout persistence and default-layout reset."""
from qgis.PyQt.QtCore import QSettings, Qt
from qgis.PyQt.QtWidgets import QAction, QDockWidget

_KEY = "GroundTruther/layout"

# Default dock areas for each managed dock (attribute name → Qt area value)
_DEFAULTS = {
    "_image_dock":     Qt.DockWidgetArea.RightDockWidgetArea,
    "_image_nav_dock": Qt.DockWidgetArea.BottomDockWidgetArea,
    "_video_dock":     Qt.DockWidgetArea.RightDockWidgetArea,
    "_report_dock":    Qt.DockWidgetArea.RightDockWidgetArea,
    "_query_dock":     Qt.DockWidgetArea.RightDockWidgetArea,
    "_roughness_dock": Qt.DockWidgetArea.RightDockWidgetArea,
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

            # Never float a non-floatable dock (e.g. the 3-D-GL docks): doing so
            # programmatically re-triggers the QOpenGLWidget reparent that wedges
            # the UI. Such a dock is restored to its dock area instead.
            floatable = bool(dock.features()
                             & QDockWidget.DockWidgetFeature.DockWidgetFloatable)
            if floating and floatable:
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

    def _capture_layout(self) -> dict:
        """Return a JSON-serialisable snapshot of the whole dock arrangement.

        Uses ``QMainWindow.saveState()`` (base64-encoded) which — unlike per-dock
        ``saveGeometry`` — faithfully records docked / tabbed / split positions
        and sizes, so they restore as docked rather than floating. Per-dock
        visibility is kept as a human-readable fallback for older files.
        """
        from qgis.utils import iface as _iface
        mw = _iface.mainWindow()
        out = {"mainwindow_state": bytes(mw.saveState().toBase64()).decode("ascii")}
        for attr in _DEFAULTS:
            dock = getattr(self, attr, None)
            if dock is None:
                continue
            try:
                out[attr] = {
                    "geometry": bytes(dock.saveGeometry().toBase64()).decode("ascii"),
                    "floating": bool(dock.isFloating()),
                    "visible": bool(dock.isVisible()),
                }
            except Exception:
                continue
        return out

    def _apply_layout(self, layout: dict) -> None:
        """Restore a dock arrangement produced by ``_capture_layout``.

        When a ``mainwindow_state`` blob is present we restore it via
        ``QMainWindow.restoreState`` — but deferred to the next event-loop pass,
        because restoreState only restores docks already present in the window
        and the main GroundTruther dock is added in ``run()`` *after* this dock
        widget is constructed. Falls back to per-dock placement for older files.
        """
        from qgis.utils import iface as _iface
        from qgis.PyQt.QtCore import QByteArray, QTimer
        mw = _iface.mainWindow()

        blob = (layout or {}).get("mainwindow_state")
        if blob:
            state = QByteArray.fromBase64(blob.encode("ascii"))
            QTimer.singleShot(0, lambda: mw.restoreState(state))
            return

        # --- legacy per-dock fallback (session files saved before saveState) ---
        for attr, default_area in _DEFAULTS.items():
            dock = getattr(self, attr, None)
            if dock is None or not layout or attr not in layout:
                continue
            entry = layout[attr] or {}
            geom_b64 = entry.get("geometry")
            geom = (QByteArray.fromBase64(geom_b64.encode("ascii"))
                    if geom_b64 else None)
            if entry.get("floating"):
                dock.setFloating(True)
                if geom is not None:
                    dock.restoreGeometry(geom)
            else:
                area_int = entry.get("area")
                dock_area = Qt.DockWidgetArea(int(area_int)) if area_int else default_area
                mw.addDockWidget(dock_area, dock)
                dock.setFloating(False)
            dock.setVisible(bool(entry.get("visible")))

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
