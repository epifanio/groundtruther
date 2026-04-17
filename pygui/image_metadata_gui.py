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
    """Metadata panel widget.

    In image mode (default) the fixed grid fields show per-image sensor data
    (depth, altimeter, salinity, temperature, …).

    In video mode (:meth:`set_video_mode` ``(True)``) the same grid is
    relabelled and inapplicable fields are hidden.  Extra rows for
    Bottom type, Biology, and Comments are appended dynamically on first
    activation and reused on subsequent calls.  Call :meth:`set_video_mode`
    ``(False)`` to restore image labels.
    """

    def __init__(self, parent=None):
        super(ImageMetadata, self).__init__(parent)
        self.setupUi(self)

        self.send_image_metadata.clicked.connect(self.send_image_metadata_txt)
        self.copy_image_metadata.clicked.connect(self.copy_image_metadata_txt)
        self.send_image_metadata.hide()
        self.copy_image_metadata.hide()

        self._video_mode: bool = False
        # Extra QLineEdit widgets added for video-only fields
        self._video_extra_widgets: dict = {}

    # ------------------------------------------------------------------
    # Mode switching
    # ------------------------------------------------------------------

    def set_video_mode(self, enabled: bool) -> None:
        """Switch the panel between image metadata and video frame metadata.

        Parameters
        ----------
        enabled:
            ``True`` → relabel for video; ``False`` → restore image labels.
        """
        if enabled == self._video_mode:
            return
        self._video_mode = enabled

        if enabled:
            # Relabel fields that have video equivalents
            self.label_22.setText("Frame")
            self.timelabel.setText("Time")
            self.Lonlabel.setText("East (°)")
            self.Latlabel.setText("North (°)")
            self.Depthlabel.setText("Depth (m)")
            self.Rolllabel.setText("CP MeanAlt (m)")
            self.Pitchlabel.setText("CP Altitude (m)")
            self.Headinglabel.setText("Cruise")

            # Hide sensor fields not present in video metadata
            for w in (self.salinity, self.temperature, self.O2, self.CDOM,
                      self.chlorophyll, self.turbidity,
                      self.label_5, self.label_23, self.label_24,
                      self.label_25, self.label_26):
                w.hide()

            # Add extra rows for Bottom, Biology, Comments (once only)
            self._ensure_video_extra_rows()
        else:
            # Restore original labels
            self.label_22.setText("Image Name")
            self.timelabel.setText("Time")
            self.Lonlabel.setText("East")
            self.Latlabel.setText("North")
            self.Depthlabel.setText("Vehicle Depth")
            self.Rolllabel.setText("Water Depth")
            self.Pitchlabel.setText("Altimeter")
            self.Headinglabel.setText("Salinity")

            for w in (self.salinity, self.temperature, self.O2, self.CDOM,
                      self.chlorophyll, self.turbidity,
                      self.label_5, self.label_23, self.label_24,
                      self.label_25, self.label_26):
                w.show()

            for w in self._video_extra_widgets.values():
                w.hide()

    def _ensure_video_extra_rows(self) -> None:
        """Append Bottom / Biology / Comments rows to the grid (idempotent)."""
        if self._video_extra_widgets:
            for w in self._video_extra_widgets.values():
                w.show()
            return

        grid = self.gridLayout
        next_row = grid.rowCount()

        def _add_row(row: int, label_text: str, field_name: str) -> QLineEdit:
            lbl = QLabel(label_text, self.scrollAreaWidgetContents)
            lbl.setMaximumSize(100, 16777215)
            edit = QLineEdit(self.scrollAreaWidgetContents)
            edit.setReadOnly(True)
            edit.setFocusPolicy(Qt.FocusPolicy(0))
            grid.addWidget(lbl, row, 0)
            grid.addWidget(edit, row, 1)
            self._video_extra_widgets[f"_lbl_{field_name}"] = lbl
            return edit

        self._video_extra_widgets["station"]  = _add_row(next_row,     "Station",  "station")
        self._video_extra_widgets["bottom"]   = _add_row(next_row + 1, "Bottom",   "bottom")
        self._video_extra_widgets["biology"]  = _add_row(next_row + 2, "Biology",  "biology")
        self._video_extra_widgets["comments"] = _add_row(next_row + 3, "Comments", "comments")

    # ------------------------------------------------------------------
    # Data population
    # ------------------------------------------------------------------

    def show_video_frame_metadata(self, row: dict) -> None:
        """Populate the panel with data from a video metadata row.

        Parameters
        ----------
        row:
            Dict returned by :func:`~gt.video_manager.frame_position`,
            containing keys from the normalised survey DataFrame.
        """
        if not self._video_mode:
            self.set_video_mode(True)

        fidx = row.get("frame_index", "")
        self.linklabel.setText(f"<b>Frame {fidx}</b>")

        ts = row.get("timestamp")
        if ts is not None:
            try:
                from qgis.PyQt.QtCore import QDateTime
                self.dateTimeEdit.setDateTime(
                    QDateTime.fromString(
                        str(ts)[:19], "yyyy-MM-dd HH:mm:ss"))
            except Exception:
                pass

        lat = row.get("latitude")
        lon = row.get("longitude")
        self.imagenorth.setText(f"{lat:.6f}" if lat is not None else "")
        self.imageeast.setText(f"{lon:.6f}" if lon is not None else "")
        self.hbcdepth.setText(str(row.get("depth", "")))
        self.waterdepth.setText(str(row.get("cp_mean_alt", "")))
        self.altimeter.setText(str(row.get("cp_altitude", "")))
        self.salinity.setText("")   # hidden in video mode but clear anyway

        cruise = row.get("cruise", "")
        station = row.get("station", "")
        # "Cruise" label maps to the salinity field row (row 7, hidden label
        # was relabelled "Cruise") — but we use the extra station widget instead
        self._ensure_video_extra_rows()
        self._video_extra_widgets["station"].setText(
            f"{cruise} / {station}" if cruise else str(station))
        self._video_extra_widgets["bottom"].setText(str(row.get("bottom", "")))
        self._video_extra_widgets["biology"].setText(str(row.get("biology", "")))
        self._video_extra_widgets["comments"].setText(str(row.get("comments", "")))

    def send_image_metadata_txt(self):
        QgsMessageLog.logMessage("send_image_metadata_txt triggered", 'GroundTruther', Qgis.Info)

    def copy_image_metadata_txt(self):
        QgsMessageLog.logMessage("copy_image_metadata_txt triggered", 'GroundTruther', Qgis.Info)
