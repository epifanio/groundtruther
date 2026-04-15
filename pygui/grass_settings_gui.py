#!/usr/bin/env python
import sys

from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *

from groundtruther.pygui.Ui_grass_settings_ui import Ui_GRASSAPI


class GrassSettings(QWidget, Ui_GRASSAPI):
    def __init__(self, parent=None):
        super(GrassSettings, self).__init__(parent)
        self.setupUi(self)