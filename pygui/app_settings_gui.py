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

"""Legacy application-settings widget (superseded by the YAML-based ConfigDialog).

``AppSettings`` is kept for reference but is not shown in the current UI.
The active settings dialog is ``configure.ConfigDialog``.
"""
import sys

from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *

from groundtruther.pygui.Ui_app_settings_ui import Ui_appsettings
import groundtruther.resources_rc
from qgis.core import Qgis, QgsMessageLog

class AppSettings(QWidget, Ui_appsettings):
    def __init__(self, parent=None):
        super(AppSettings, self).__init__(parent)
        self.setupUi(self)
        self.select_image_path.clicked.connect(self.set_image_path)
        self.select_metadata_path.clicked.connect(self.set_metadata_path)
        self.select_mbes_path.clicked.connect(self.set_mbes_path)
        self.setOption.clicked.connect(self.print_val)
        self.vrt_label.hide()
        self.vrt_path.hide()
        self.select_vrt_path.hide()
        

    def print_val(self):
        QgsMessageLog.logMessage(f"image_path: {self.image_path.text()}", 'GroundTruther', Qgis.Info)

    def set_metadata_path(self):    
        options = QFileDialog.Options()
        fileName, _ = QFileDialog.getOpenFileName(self,
                "QFileDialog.getOpenFileName()", self.metadata_path.text(),
                "All Files (*);;Text Files (*.txt)", options=options)
        if fileName:
            self.metadata_path.setText(fileName)

    def set_image_path(self):    
        options = QFileDialog.Option.DontResolveSymlinks | QFileDialog.Option.ShowDirsOnly
        directory = QFileDialog.getExistingDirectory(self,
                "QFileDialog.getExistingDirectory()",
                self.image_path.text(), options=options)
        if directory:
            self.image_path.setText(directory)
    
    def set_mbes_path(self):    
        options = QFileDialog.Options()
        fileName, _ = QFileDialog.getOpenFileName(self,
                "QFileDialog.getOpenFileName()", self.metadata_path.text(),
                "All Files (*);;Text Files (*.txt)", options=options)
        if fileName:
            self.mbes_path.setText(fileName)
