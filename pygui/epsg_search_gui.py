#!/usr/bin/env python
import sys

from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *

from pygui.Ui_epsg_ui import Ui_Form


class SearchEpsg(QWidget, Ui_Form):
    def __init__(self, parent=None):
        super(SearchEpsg, self).__init__(parent)
        self.setupUi(self)
