#!/usr/bin/env python
"""Image metadata panel widget.

Contains two classes:

``ExtendedDateTimeEdit``
    A ``QDateTimeEdit`` subclass that displays millisecond precision and uses
    seconds as its step unit (instead of the default field-based stepping).
    Used in the metadata scroll panel to show the per-image timestamp.

``ImageMetadata``
    Tab widget built from the Designer layout (``Ui_imagemetadata``).  Acts
    as the outer container; the actual per-image fields are built dynamically
    at runtime by ``ImageBrowserMixin._build_metadata_panel()`` and mounted
    inside ``metadata_scroll_area``.
"""
import sys

from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *

from groundtruther.pygui.Ui_image_metadata_ui import Ui_imagemetadata
from qgis.core import Qgis, QgsMessageLog


class ExtendedDateTimeEdit(QDateTimeEdit):
    """QDateTimeEdit with millisecond display and second-granularity stepping."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setDisplayFormat("yyyy-MM-dd HH:mm:ss.zzz")

    def stepBy(self, steps):
        """Step by *steps* seconds (positive = forward, negative = backward)."""
        current_datetime = self.dateTime()
        updated_datetime = current_datetime.addSecs(steps)
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
        QgsMessageLog.logMessage("send_image_metadata_txt triggered", 'GroundTruther', Qgis.Info)

    def copy_image_metadata_txt(self):
        QgsMessageLog.logMessage("copy_image_metadata_txt triggered", 'GroundTruther', Qgis.Info)
