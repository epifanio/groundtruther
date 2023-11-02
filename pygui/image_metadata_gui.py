#!/usr/bin/env python
import sys

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

from groundtruther.pygui.Ui_image_metadata_ui import Ui_imagemetadata

class ExtendedDateTimeEdit(QDateTimeEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setDisplayFormat("yyyy-MM-dd HH:mm:ss.zzz")

    def stepBy(self, steps):
        current_datetime = self.dateTime()

        # Add or subtract the step value to the current datetime
        updated_datetime = current_datetime.addSecs(steps)

        # Update the QDateTimeEdit value
        self.setDateTime(updated_datetime)


class ImageMetadata(QWidget, Ui_imagemetadata):
    def __init__(self, parent=None):
        super(ImageMetadata, self).__init__(parent)
        self.setupUi(self)

        self.send_image_metadata.clicked.connect(self.send_image_metadata_txt)
        self.copy_image_metadata.clicked.connect(self.copy_image_metadata_txt)
        self.send_image_metadata.hide()
        self.copy_image_metadata.hide()

    def send_image_metadata_txt(self):
        print('called send_image_metadata_txt')

    def copy_image_metadata_txt(self):
        print('called copy_image_metadata_txt')
