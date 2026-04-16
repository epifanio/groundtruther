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
