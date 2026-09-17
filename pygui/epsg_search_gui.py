#!/usr/bin/env python
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
