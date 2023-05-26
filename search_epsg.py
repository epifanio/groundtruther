from PyQt5.QtCore import QRegExp
from PyQt5.QtGui import QRegExpValidator
from PyQt5.QtWidgets import QDialog, QFileDialog, QMessageBox
from pygui.epsg_search_gui import SearchEpsg

import os
from groundtruther.episg import *


class SearchEpsgDialog(QDialog, SearchEpsg):
    """docstring"""

    def __init__(self, parent=None):
        super().__init__()
        QDialog.__init__(self, parent)
        self.setupUi(self)

        self.epsgfile = os.path.join(
            os.path.abspath(os.path.dirname(__file__)), 'epsg')
        print("##############################")
        print("EPSG:", self.epsgfile)
        self.Search.clicked.connect(self.setinput)
        self.OutList.currentIndexChanged.connect(self.outinfo)

    def setinput(self):
        if self.Code_rb.isChecked():
            print('code')
            outlist = guioption(self.epsgfile, 'code')
            self.OutList.clear()
            self.OutList.addItems(outlist)
        if self.Title_rb.isChecked():
            print('title')
            outlist = guioption(self.epsgfile, 'title')
            self.OutList.clear()
            self.OutList.addItems(outlist)
        if self.Params_rb.isChecked():
            print('param')
            outlist = guioption(self.epsgfile, 'param')
            self.OutList.clear()
            self.OutList.addItems(outlist)

    def outinfo(self, index):
        if self.Code_rb.isChecked():
            if self.Code_cb.isChecked():
                lst = 'c'
            if self.Params_cb.isChecked():
                lst = 'p'
            if self.Title_cb.isChecked():
                lst = 't'
            if self.All_cb.isChecked():
                lst = 'a'
            typeout = self.OutList.itemText(index)
            try:
                output = rep3(self.epsgfile, 'code', str(typeout), lst)
            except UnboundLocalError:
                output = ''
            self.printout.setText(str(output))
        if self.Title_rb.isChecked():
            if self.Code_cb.isChecked():
                lst = 'c'
            if self.Params_cb.isChecked():
                lst = 'p'
            if self.Title_cb.isChecked():
                lst = 't'
            if self.All_cb.isChecked():
                lst = 'a'
            typeout = self.OutList.itemText(index)
            try:
                output = rep3(self.epsgfile, 'title', str(typeout), lst)
            except UnboundLocalError:
                output = ''
            self.printout.setText(str(output))
        if self.Params_rb.isChecked():
            if self.Code_cb.isChecked():
                lst = 'c'
            if self.Params_cb.isChecked():
                lst = 'p'
            if self.Title_cb.isChecked():
                lst = 't'
            if self.All_cb.isChecked():
                lst = 'a'
            typeout = self.OutList.itemText(index)
            output = rep3(self.epsgfile, 'param', str(typeout), lst)
            self.printout.setText(str(output))
