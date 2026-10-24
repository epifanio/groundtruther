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

from qgis.PyQt.QtWidgets import QDialog, QFileDialog, QMessageBox
from groundtruther.pygui.epsg_search_gui import SearchEpsg

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
