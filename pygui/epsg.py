#!/usr/bin/env python
###############################################################################
#
#
# Project:
# Purpose:
#
#
# Author:   Massimo Di Stefano , epiesasha@me.com
#
###############################################################################
# Copyright (c) 2009, Massimo Di Stefano <epiesasha@me.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.
###############################################################################

__author__ = "Massimo Di Stefano"
__copyright__ = "Copyright 2009, gfoss.it"
__credits__ = [""]
__license__ = "GPL V3"
__version__ = "1.0.0"
__maintainer__ = "Massimo Di Stefano"
__email__ = "epiesasha@me.com"
__status__ = "Production"
__date__ = ""

import sys

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

from Ui_epsg_ui import Ui_Form
import os
from episg import *
apppath = os.path.abspath(os.path.dirname(sys.argv[0]))
epsgfile = str(apppath)+'/epsg'


class SearchEpsg(QWidget, Ui_Form):
    def __init__(self):
        QWidget.__init__(self)
        self.setupUi(self)
        self.Search.clicked.connect(self.setinput)
        self.OutList.currentIndexChanged.connect(self.outinfo)

    def setinput(self):
        if self.Code_rb.isChecked():
            print('code')
            outlist = guioption(epsgfile, 'code')
            self.OutList.clear()
            self.OutList.addItems(outlist)
        if self.Title_rb.isChecked():
            print('title')
            outlist = guioption(epsgfile, 'title')
            self.OutList.clear()
            self.OutList.addItems(outlist)
        if self.Params_rb.isChecked():
            print('param')
            outlist = guioption(epsgfile, 'param')
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
            output = rep3(epsgfile, 'code', str(typeout), lst)
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
            output = rep3(epsgfile, 'title', str(typeout), lst)
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
            output = rep3(epsgfile, 'param', str(typeout), lst)
            self.printout.setText(str(output))
