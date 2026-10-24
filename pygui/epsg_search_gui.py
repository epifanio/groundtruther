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

"""EPSG code search widget (standalone / legacy utility).

``SearchEpsg`` applies the Designer-generated ``Ui_Form`` layout that lets
the user search for a coordinate reference system by EPSG code, parameter
string, or title.

"""
import sys

from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *

from groundtruther.pygui.Ui_epsg_ui import Ui_Form


class SearchEpsg(QWidget, Ui_Form):
    """Widget for searching EPSG/CRS records by code, parameters, or title."""

    def __init__(self, parent=None):
        super(SearchEpsg, self).__init__(parent)
        self.setupUi(self)
