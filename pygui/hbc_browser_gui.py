#!/usr/bin/env python


from PyQt5 import QtWidgets
from groundtruther.pygui.Ui_hbc_browser_ui import Ui_MainWindow

class HBCBrowserGui(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self):
        QtWidgets.QMainWindow.__init__(self)
        self.setupUi(self)
