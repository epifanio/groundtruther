"""Floating panel docks: Report Builder and BS Query Builder."""
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QDockWidget, QAction
from qgis.core import Qgis, QgsMessageLog


def _make_dock(title: str, obj_name: str, widget, parent_window):
    """Create a standard floating-capable QDockWidget wrapping *widget*."""
    dock = QDockWidget(title, parent_window)
    dock.setObjectName(obj_name)
    dock.setAllowedAreas(Qt.DockWidgetArea(15))          # AllDockWidgetAreas
    dock.setFeatures(QDockWidget.DockWidgetFeature(7))   # Closable|Movable|Floatable
    dock.setWidget(widget)
    dock.hide()
    return dock


def _make_toggle_action(title: str, tooltip: str, toggle_slot, visibility_slot,
                        parent, icon_svg: str = None):
    """Create a checkable toolbar action wired to *toggle_slot*."""
    action = QAction(parent)
    if icon_svg:
        try:
            from groundtruther.mixins.toolbar_icons import make_toggle_icon
            action.setIcon(make_toggle_icon(icon_svg))
        except Exception:
            action.setText(title)
    else:
        action.setText(title)
    action.setCheckable(True)
    action.setChecked(False)
    action.setToolTip(tooltip)
    action.toggled.connect(toggle_slot)
    return action


class ReportDockMixin:
    """Manages the floating Report Builder and BS Query Builder docks."""

    # ------------------------------------------------------------------ #
    # Init / cleanup                                                       #
    # ------------------------------------------------------------------ #

    def _init_report_dock(self) -> None:
        """Wrap savekml and querybuilder in floating docks and add toolbar buttons."""
        from qgis.utils import iface as _iface
        mw = _iface.mainWindow()

        # --- Report Builder ---
        self._report_dock = _make_dock(
            "Report Builder", "GroundTrutherReportDock", self.savekml, mw)
        _iface.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._report_dock)
        self._report_dock.hide()  # addDockWidget shows the dock; hide it explicitly

        self._report_dock_action = _make_toggle_action(
            "Report Builder",
            "Show / hide the Report Builder",
            self._toggle_report_dock,
            self._on_report_dock_visibility,
            self,
            icon_svg="note-sticky.svg",
        )
        self._report_dock.visibilityChanged.connect(self._on_report_dock_visibility)
        self.w.toolBar.addAction(self._report_dock_action)

        # --- BS Query Builder ---
        self._query_dock = _make_dock(
            "BS Query Builder", "GroundTrutherQueryDock", self.querybuilder, mw)
        _iface.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._query_dock)
        self._query_dock.hide()  # addDockWidget shows the dock; hide it explicitly

        self._query_dock_action = _make_toggle_action(
            "BS Query Builder",
            "Show / hide the BS Query Builder",
            self._toggle_query_dock,
            self._on_query_dock_visibility,
            self,
            icon_svg="chart-line.svg",
        )
        self._query_dock.visibilityChanged.connect(self._on_query_dock_visibility)
        self.w.toolBar.addAction(self._query_dock_action)

        QgsMessageLog.logMessage(
            "Report Builder and Query Builder docks created", "GroundTruther", Qgis.Info)

    def _cleanup_report_dock(self) -> None:
        """Remove both panel docks from QGIS."""
        for attr in ('_report_dock', '_query_dock'):
            dock = getattr(self, attr, None)
            if dock is None:
                continue
            setattr(self, attr, None)
            try:
                dock.hide()
                dock.setWidget(None)
                from qgis.utils import iface as _iface
                _iface.removeDockWidget(dock)
                dock.deleteLater()
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    # Report Builder slots                                                 #
    # ------------------------------------------------------------------ #

    def _toggle_report_dock(self, checked: bool) -> None:
        dock = getattr(self, '_report_dock', None)
        if dock is None:
            return
        if checked:
            dock.show()
            dock.raise_()
        else:
            dock.hide()

    def _on_report_dock_visibility(self, visible: bool) -> None:
        action = getattr(self, '_report_dock_action', None)
        if action is None:
            return
        action.blockSignals(True)
        action.setChecked(visible)
        action.blockSignals(False)

    # ------------------------------------------------------------------ #
    # BS Query Builder slots                                               #
    # ------------------------------------------------------------------ #

    def _toggle_query_dock(self, checked: bool) -> None:
        dock = getattr(self, '_query_dock', None)
        if dock is None:
            return
        if checked:
            dock.show()
            dock.raise_()
        else:
            dock.hide()

    def _on_query_dock_visibility(self, visible: bool) -> None:
        action = getattr(self, '_query_dock_action', None)
        if action is None:
            return
        action.blockSignals(True)
        action.setChecked(visible)
        action.blockSignals(False)
