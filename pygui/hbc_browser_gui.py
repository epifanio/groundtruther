#!/usr/bin/env python
"""Main browser window widget for the GroundTruther dockwidget.

``HBCBrowserGui`` is a thin subclass of QMainWindow that applies the
Designer-generated ``Ui_MainWindow`` layout.  It acts as the top-level
container embedded in ``GroundTrutherDockWidget`` via ``setWidget()``.

All runtime state (lat/lon display, image index slider, toolbar actions,
etc.) is added programmatically in ``GroundTrutherDockWidget.init_ui()``.
"""

from qgis.PyQt import QtWidgets
from groundtruther.pygui.Ui_hbc_browser_ui import Ui_MainWindow


class HBCBrowserGui(QtWidgets.QMainWindow, Ui_MainWindow):
    """QMainWindow that provides the base layout for the image browser dock."""

    def __init__(self):
        QtWidgets.QMainWindow.__init__(self)
        self.setupUi(self)
        self._harmonize_action_icons()

    def _harmonize_action_icons(self):
        """Replace the Designer raster icons with on-theme tinted SVGs."""
        from groundtruther.mixins.toolbar_icons import iconize
        # Make the dialog-opening actions checkable so they highlight (blue
        # toggle-icon) while their (modal) window is open — the open handlers
        # toggle the checked state around exec().
        for name in ("actionWizard", "actiongrass_settings"):
            act = getattr(self, name, None)
            if act is not None:
                act.setCheckable(True)
        for name, svg, tip in (
            ("actionWizard", "screwdriver-wrench.svg", "Preferences / settings"),
            ("actionTools", "table-list.svg", "Tools"),
            ("actionQuit", "power-off.svg", "Quit"),
            ("actionAnnotation", "pen-to-square.svg", "Image annotation overlay"),
            ("actionGisTools", "GrassProperties.svg", "GIS Tools (GRASS)"),
            ("actionImageBrowser", "file-image.svg", "Image Browser"),
            ("actiongrass_settings", "grass_location.svg", "GRASS environment settings"),
        ):
            act = getattr(self, name, None)
            if act is not None:
                iconize(act, svg, tip)
