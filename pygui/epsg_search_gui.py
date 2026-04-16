#!/usr/bin/env python
"""EPSG code search widget (standalone / legacy utility).

``SearchEpsg`` applies the Designer-generated ``Ui_Form`` layout that lets
the user search for a coordinate reference system by EPSG code, parameter
string, or title.

Note: this file uses a bare ``from pygui.Ui_epsg_ui import`` path which only
works when run standalone (not as part of the installed plugin).  Inside the
plugin the equivalent is ``groundtruther.pygui.search_epsg``.
"""
import sys

from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *

from pygui.Ui_epsg_ui import Ui_Form


class SearchEpsg(QWidget, Ui_Form):
    """Widget for searching EPSG/CRS records by code, parameters, or title."""

    def __init__(self, parent=None):
        super(SearchEpsg, self).__init__(parent)
        self.setupUi(self)
