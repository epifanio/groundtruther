#!/usr/bin/env python
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