#!/usr/bin/env python
import sys

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

from groundtruther.pygui.Ui_grass_mdi_ui import Ui_grass_mdi


class GrassMdi(QWidget, Ui_grass_mdi):
    def __init__(self, parent=None):
        super(GrassMdi, self).__init__(parent)
        self.setupUi(self)