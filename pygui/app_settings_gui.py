#!/usr/bin/env python
import sys

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

from groundtruther.pygui.Ui_app_settings_ui import Ui_appsettings
import groundtruther.resources_rc

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
        print(self.image_path.text())

    def set_metadata_path(self):    
        options = QFileDialog.Options()
        fileName, _ = QFileDialog.getOpenFileName(self,
                "QFileDialog.getOpenFileName()", self.metadata_path.text(),
                "All Files (*);;Text Files (*.txt)", options=options)
        if fileName:
            self.metadata_path.setText(fileName)

    def set_image_path(self):    
        options = QFileDialog.DontResolveSymlinks | QFileDialog.ShowDirsOnly
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
