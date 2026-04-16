#!/usr/bin/env python
"""GRASS API settings form widget.

``GrassSettings`` applies the Designer-generated ``Ui_GRASSAPI`` layout that
lets the user configure the GRASS REST API connection parameters (server URL,
location, mapset, GISDBASE).

Note: the active GRASS configuration dialog used at runtime is
``grassconfig.GrassConfigDialog``; ``GrassSettings`` is instantiated inside
the dockwidget as a helper container for the form fields.
"""
import sys

from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *

from groundtruther.pygui.Ui_grass_settings_ui import Ui_GRASSAPI


class GrassSettings(QWidget, Ui_GRASSAPI):
    """Widget that displays the GRASS API connection fields (server, location, mapset)."""

    def __init__(self, parent=None):
        super(GrassSettings, self).__init__(parent)
        self.setupUi(self)