"""Image browser mixin: navigation, display, metadata panel, annotation overlay."""
import os
from functools import lru_cache
from sys import platform

import numpy as np
import pandas as pd
import pyqtgraph as pg
from skimage.io import imread

from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import pyqtSignal
from qgis.core import (
    Qgis, QgsMessageLog,
    QgsPointXY, QgsRectangle, QgsProject,
    QgsCoordinateReferenceSystem, QgsCoordinateTransform,
)
from qgis.gui import QgsVertexMarker

from qgis.PyQt.QtCore import Qt, QSize
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import (
    QLabel, QLineEdit, QHBoxLayout, QVBoxLayout, QWidget,
    QSizePolicy, QSpacerItem, QTextEdit,
    QDockWidget, QMainWindow, QAction, QDoubleSpinBox, QToolBar,
)

from groundtruther.configure import log_exception
from groundtruther.pygui.image_metadata_gui import ExtendedDateTimeEdit
from groundtruther.gt import image_manager as img_mgr


# ---------------------------------------------------------------------------
# Module-level image cache — shared across the whole plugin process
# ---------------------------------------------------------------------------

@lru_cache(maxsize=5)
def _cached_imread(path: str) -> np.ndarray:
    """Read and decode an image, keeping the last 5 results in memory.

    The cache is keyed on the absolute file-path string.  Call
    ``_cached_imread.cache_clear()`` (via ``_clear_image_cache``) whenever
    the image directory changes so stale arrays are not returned.
    """
    return imread(path)


# ---------------------------------------------------------------------------
# Helper widget classes (kept here so the main dockwidget stays clean)
# ---------------------------------------------------------------------------

class CustomGraphItem(pg.GraphItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.custom_attribute = None

    def setCustomAttribute(self, value):
        self.custom_attribute = value

    def getCustomAttribute(self):
        return self.custom_attribute


class MyImageView(pg.ImageView):
    mousePressEventSignal = pyqtSignal(object)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plot_items = []

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton(1):
            pos_f = event.position()  # QPointF required by QRectF.contains() in Qt6
            for item in self.plot_items:
                if item.sceneBoundingRect().contains(pos_f):
                    QgsMessageLog.logMessage(
                        f"Mouse position intersects GraphItem: {item}",
                        'GroundTruther', Qgis.Info)
                    QgsMessageLog.logMessage(
                        f"GraphItem attribute: {item.getCustomAttribute()}",
                        'GroundTruther', Qgis.Info)
                    self.mousePressEventSignal.emit(item.getCustomAttribute())
                    item.setPen('w')
                else:
                    item.setPen('r')


# ---------------------------------------------------------------------------
# Mixin
# ---------------------------------------------------------------------------

class ImageBrowserMixin:
    """Image navigation, display, metadata panel, and annotation overlay."""

    def _init_image_browser(self):
        """Wire up all image-browser UI signals.

        Must be called after ``self.w`` and ``self.imv`` exist.
        """
        self.imageviewer_is_hidden = False

        self.w.fwd.clicked.connect(self.increaseimageindex)
        self.w.rwd.clicked.connect(self.decreaseimageindex)
        self.w.ImageIndexSlider.valueChanged.connect(self.setValueImageIndexspinBox)
        self.w.ImageIndexspinBox.valueChanged.connect(self.setValueImageIndexSlider)
        self.w.ImageStepspinBox.valueChanged.connect(self.setImageIndexStepValue)
        self.w.ImageIndexSlider.valueChanged.connect(self.add_image)

        self.w.range.valueChanged.connect(self.setValuerangeSpinBox)
        self.w.toolBar.removeAction(self.w.actionImageBrowser)
        self.w.annotation_confidence_spinBox.valueChanged.connect(
            self.setValue_annotation_confidence)
        self.w.actionAnnotation.triggered.connect(self.showAnnotationThreshold)
        self.w.annotation_confidence_spinBox.hide()
        self.w.annotation_confidence_spinBox_label.hide()

        # Image counter label — appended to the navigation button row so it
        # travels with the imageBrowsing dock.
        self._image_counter_label = QLabel("0 / 0")
        self._image_counter_label.setMinimumWidth(70)
        self.w.horizontalLayout_13.addWidget(self._image_counter_label)

        if platform == "darwin":
            self.w.fwd.hide()
            self.w.rwd.hide()

    def _clear_image_cache(self):
        """Discard all cached image arrays (call when the image directory changes)."""
        _cached_imread.cache_clear()

    # ------------------------------------------------------------------ #
    # Index navigation                                                     #
    # ------------------------------------------------------------------ #

    def setStausMessage(self, message):
        self.w.statusbar.showMessage(message)

    def decreaseimageindex(self):
        self.imageindex = self.imageindex - self.w.ImageStepspinBox.value()
        self.w.ImageIndexSlider.setValue(self.imageindex)
        self.w.ImageIndexspinBox.setValue(self.imageindex)
        self.w.ImageIndexspinBox.update()

    def increaseimageindex(self):
        self.imageindex = self.imageindex + self.w.ImageStepspinBox.value()
        self.w.ImageIndexSlider.setValue(self.imageindex)
        self.w.ImageIndexspinBox.setValue(self.imageindex)
        self.w.ImageIndexspinBox.update()

    def setValueImageIndexspinBox(self, z):
        self.imageindex = int(z)
        self.w.ImageIndexspinBox.setSingleStep(self.w.ImageStepspinBox.value())
        self.w.ImageIndexspinBox.setValue(self.imageindex)

    def setValueImageIndexSlider(self, z):
        self.imageindex = int(z)
        self.w.ImageIndexSlider.setSingleStep(self.w.ImageStepspinBox.value())
        self.w.ImageIndexSlider.setValue(self.imageindex)

    def setValuerangeSpinBox(self, r):
        self.rangevalue = int(r)
        self.w.range.setSingleStep(1)
        self.w.range.setValue(self.rangevalue)
        if self.w.zoomto.isChecked():
            self.zoom_to()

    def setImageIndexStepValue(self):
        self.w.ImageIndexspinBox.setSingleStep(self.w.ImageStepspinBox.value())
        self.w.ImageIndexSlider.setSingleStep(self.w.ImageStepspinBox.value())

    def close_pyqtgraph(self):
        self.querybuilder.close()

    # ------------------------------------------------------------------ #
    # Map canvas navigation                                                #
    # ------------------------------------------------------------------ #

    def get_query_position(self, lat, lon):
        self.set_image_index(lat, lon)

    def set_image_index(self, lat: float, lon: float):
        QgsMessageLog.logMessage(
            f"vquery at {lat}, {lon}", 'GroundTruther', Qgis.Info)
        index = self.getImageIndex(lon, lat)
        self.w.ImageIndexSlider.setValue(index)

    def getImageIndex(self, lon, lat):
        index, _distance = img_mgr.nearest_image_index(self.kdt, lon, lat)
        return index

    def zoom_to(self):
        """Pan and zoom the map canvas to the current image coordinates."""
        try:
            lon = float(self.w.longitude.text())
            lat = float(self.w.latitude.text())
        except ValueError:
            return

        wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
        project_crs = QgsProject.instance().crs()

        point = QgsPointXY(lon, lat)
        if project_crs != wgs84 and project_crs.isValid():
            transform = QgsCoordinateTransform(
                wgs84, project_crs, QgsProject.instance())
            try:
                point = transform.transform(point)
            except Exception as exc:
                log_exception(
                    "zoom_to: coordinate transform failed", exc, warn=True)
                return

        distance = float(self.rangevalue) / 10000
        self.w.statusbar.showMessage("System Status | Normal")

        rect = QgsRectangle(
            point.x() - distance, point.y() - distance,
            point.x() + distance, point.y() + distance,
        )
        if self.m1:
            self.canvas.scene().removeItem(self.m1)
        self.m1 = QgsVertexMarker(self.canvas)
        self.m1.setCenter(point)
        self.m1.setColor(QColor(255, 0, 0))
        self.m1.setIconSize(10)
        self.m1.setIconType(QgsVertexMarker.ICON_X)
        self.m1.setPenWidth(3)
        self.canvas.setExtent(rect)
        self.canvas.refresh()

    # ------------------------------------------------------------------ #
    # Annotation overlay (legacy graph-item bounding boxes)               #
    # ------------------------------------------------------------------ #

    def build_box(self, bbox):
        pos = np.array([
            [bbox[0], bbox[1]],
            [bbox[2], bbox[3]],
            [bbox[4], bbox[5]],
            [bbox[6], bbox[7]],
        ])
        adj = np.array([[0, 1], [1, 2], [2, 3], [3, 0]])
        symbols = ["o", "o", "o", "o"]
        lines = np.array(
            [(255, 0, 0, 255, self.annotation_box_linewidth)] * 4,
            dtype=[
                ("red", np.ubyte), ("green", np.ubyte), ("blue", np.ubyte),
                ("alpha", np.ubyte), ("width", float),
            ],
        )
        return pos, adj, lines, symbols

    def clear_image_annotation(self):
        for item in self.graph_items:
            item.setData(pos=[], adj=[], pen=[], size=1, pxMode=False)
            del item
        self.graph_items = []

    def add_image_annotation(self):
        annotation = self.imageMetadata["Annotation"].iloc[self.imageindex]
        if annotation is not np.nan:
            self.clear_image_annotation()
            for i, bbox in enumerate(annotation["bbox"]):
                if (float(annotation["Confidence"][i])
                        >= self.annotation_confidence_treshold):
                    QgsMessageLog.logMessage(
                        f"annotation bbox={bbox}, "
                        f"label={annotation['Species'][i]}, "
                        f"confidence={annotation['Confidence'][i]} "
                        f"(threshold={self.annotation_confidence_treshold})",
                        'GroundTruther', Qgis.Info)
                    g = CustomGraphItem()
                    g.setCustomAttribute(annotation["Species"][i])
                    pos, adj, lines, symbols = self.build_box(bbox["bbox"])
                    g.setData(
                        pos=pos, adj=adj, pen=lines,
                        size=15, symbol=symbols, pxMode=False,
                    )
                    self.imv.addItem(g)
                    self.imv.plot_items.append(g)
                    g.setZValue(10)
                    self.graph_items.append(g)
        else:
            QgsMessageLog.logMessage(
                "no annotation found for current image",
                'GroundTruther', Qgis.Info)
            self.clear_image_annotation()

    def count_string_occurrences(self, string_list):
        count_dict = {}
        for string in string_list:
            count_dict[string] = count_dict.get(string, 0) + 1
        return count_dict

    # ------------------------------------------------------------------ #
    # Metadata panel — build once, update values on each frame change     #
    # ------------------------------------------------------------------ #

    def _build_metadata_panel(self):
        """Build the metadata scroll-panel widget structure once.

        Called after ``imageMetadata`` is first loaded so the column set is
        known.  Stores widget references in ``_meta_widgets`` keyed by column
        name; ``_update_metadata_panel`` then only sets text values.
        """
        self._meta_widgets = {}

        main_layout = QVBoxLayout()
        main_layout.setSpacing(4)
        main_layout.setContentsMargins(4, 4, 4, 4)

        # Time row — DataFrame index is a datetime
        time_row = QHBoxLayout()
        time_row.addWidget(QLabel("Time"))
        time_row.addItem(
            QSpacerItem(20, 20, QSizePolicy.Policy(7), QSizePolicy.Policy(1)))
        self._meta_time_widget = ExtendedDateTimeEdit()
        self._meta_time_widget.setMaximumSize(QSize(250, 16777215))
        self._meta_time_widget.setMinimumWidth(160)
        self._meta_time_widget.setSizePolicy(
            QSizePolicy.Policy(3), QSizePolicy.Policy(5))
        self._meta_time_widget.setReadOnly(True)
        self._meta_time_widget.setButtonSymbols(
            QtWidgets.QAbstractSpinBox.ButtonSymbols(2))
        time_row.addWidget(self._meta_time_widget)
        main_layout.addLayout(time_row)

        for col in self.imageMetadata.columns:
            row = QHBoxLayout()
            row.addWidget(QLabel(col))
            row.addItem(
                QSpacerItem(20, 20, QSizePolicy.Policy(7), QSizePolicy.Policy(1)))
            if col == "Imagename":
                w = QLabel()
                w.setOpenExternalLinks(True)
            elif col == "Annotation":
                w = QTextEdit()
                w.setReadOnly(True)
                w.setFixedHeight(80)
            else:
                w = QLineEdit()
                w.setReadOnly(True)
            w.setMaximumWidth(250)
            w.setMinimumWidth(160)
            w.setSizePolicy(QSizePolicy.Policy(3), QSizePolicy.Policy(5))
            row.addWidget(w)
            main_layout.addLayout(row)
            self._meta_widgets[col] = w

        main_layout.addStretch()
        container = QWidget()
        container.setLayout(main_layout)
        self.imagemetadata_gui.metadata_scroll_area.setWidgetResizable(True)
        self.imagemetadata_gui.metadata_scroll_area.setWidget(container)

    def _update_metadata_panel(self, record):
        """Update metadata panel values in-place for the given DataFrame row.

        No widget allocation — only text/value changes.
        """
        if not self._meta_widgets:
            return

        if self._meta_time_widget is not None:
            try:
                self._meta_time_widget.setDateTime(record.name)
            except Exception:
                pass

        for col, w in self._meta_widgets.items():
            try:
                val = record[col]
            except KeyError:
                continue
            if col == "Imagename":
                link = os.path.join(self.dirname, str(val) + ".jpg")
                w.setText(f'<a href="file://{link}">{val}</a>')
            elif col == "Annotation":
                if isinstance(val, dict) and "Species" in val:
                    counts = self.count_string_occurrences(val["Species"])
                    w.setPlainText(
                        "\n".join(f"{s}: {c}" for s, c in counts.items()))
                else:
                    w.setPlainText("")
            else:
                w.setText(str(val))

    # ------------------------------------------------------------------ #
    # Main image display                                                   #
    # ------------------------------------------------------------------ #

    def add_image(self):
        """Load and display the image at the current index."""
        self.imv.clear()
        if self.imageMetadata is None:
            return

        img_path = os.path.join(
            self.dirname,
            self.imageMetadata["Imagename"].iloc[self.imageindex] + ".jpg",
        )
        self.imv.imageItem.axisOrder = "row-major"
        if self.w.actionImageBrowser.isChecked():
            self.imv.show()

        self.imv.setImage(_cached_imread(img_path))

        # Annotation editor dock takes priority if open
        ann_editor_open = (
            hasattr(self, 'annotation_editor_dock')
            and self.annotation_editor_dock.isVisible()
        )
        if ann_editor_open:
            annotation = self.imageMetadata["Annotation"].iloc[self.imageindex]
            imagename = self.imageMetadata["Imagename"].iloc[self.imageindex]
            self.annotation_editor.load_image(
                self.imageindex, imagename,
                annotation, self.imageannotationfile)
        elif self.w.actionAnnotation.isChecked():
            self.add_image_annotation()
        else:
            self.clear_image_annotation()

        record = self.imageMetadata.iloc[self.imageindex]
        self.imagemetadata_gui.metadata_scroll_area.setEnabled(True)

        if len(record) != 0:
            self._update_metadata_panel(record)
            self.w.longitude.setText(str(round(record["habcam_lon"], 8)))
            self.w.latitude.setText(str(round(record["habcam_lat"], 8)))
            total = len(self.imageMetadata)
            self._image_counter_label.setText(f"{self.imageindex} / {total - 1}")
            if self.w.zoomto.isChecked():
                self.zoom_to()
            self.on_send()
        else:
            QgsMessageLog.logMessage(
                f"record length {len(record)} for image index {self.imageindex}",
                'GroundTruther', Qgis.Warning)

    def on_send(self):
        """Emit image path and metadata string to connected widgets."""
        image_path = os.path.join(
            self.dirname,
            self.imageMetadata["Imagename"].iloc[self.imageindex] + ".jpg")
        self.send_image_path.emit(image_path)

        # Build a metadata HTML summary from whatever columns are available
        wanted_cols = [
            'Longitude', 'Latitude', 'V_Depth', 'Water_Depth',
            'Altimeter', 'Salinity', 'Temp', 'O2', 'Cdom',
            'Chlorophyll', 'Turb',
        ]
        available = [c for c in wanted_cols if c in self.imageMetadata.columns]
        if available:
            md_str = pd.DataFrame(
                [self.imageMetadata[available].iloc[self.imageindex]]
            ).to_html()
            self.send_imagemetadata_string.emit(md_str)

        if not self.savekml.lock_location.isChecked():
            self.savekml.longitude.setText(self.w.longitude.text())
            self.savekml.latitude.setText(self.w.latitude.text())
        if not self.querybuilder.lock_location.isChecked():
            self.querybuilder.qb_longitude.setText(self.w.longitude.text())
            self.querybuilder.qb_latitude.setText(self.w.latitude.text())

    # ------------------------------------------------------------------ #
    # UI toggles                                                           #
    # ------------------------------------------------------------------ #

    def _init_image_browser_dock(self) -> None:
        """Create the floating image browser dock containing self.imv.

        Mirrors _init_video_browser(): wraps self.imv in an inner QMainWindow
        (so the annotation editor can dock inside it) and floats the whole
        thing as a QDockWidget in the main QGIS window.  Must be called after
        self.imv exists and _init_image_browser() has wired all signals.

        Design notes
        ------------
        * self.w.imageBrowsing (navigation controls) intentionally stays in
          self.w.  Moving a Designer-generated dock between QMainWindows
          corrupts Qt's internal dock-layout state for self.w and causes
          access-violation crashes when mouse events route through self.w's
          toolbar/statusbar machinery.
        * self._image_toolbar is a plain QToolBar added to a VBox layout
          container, NOT via QMainWindow.addToolBar().  Using addToolBar()
          creates QToolBarWidgetAction wrappers that can dangle when the
          floating outer dock is moved or resized.  The plain-widget approach
          mirrors VideoPlayerWidget.player_toolbar.
        """
        from qgis.utils import iface as _iface

        # Inner QMainWindow (Widget flag): needed only for addDockWidget()
        self._image_inner_window = QMainWindow()
        self._image_inner_window.setWindowFlags(Qt.WindowType(1))   # Widget
        self._image_inner_window.statusBar().hide()
        self._image_inner_window.menuBar().hide()

        # Container: plain QWidget holding toolbar + optional conf row + image viewer.
        # Plain QToolBar in a layout is stable across floating/resize — avoids the
        # QMainWindow toolbar-widget bookkeeping that causes access violations.
        container = QWidget()
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        self._image_toolbar = QToolBar()
        self._image_toolbar.setMovable(False)
        vbox.addWidget(self._image_toolbar)

        # Detection-confidence row — hidden until actionAnnotation is checked.
        # Lives here instead of in self.w so it stays with the image viewer.
        self._image_conf_widget = QWidget()
        conf_row = QHBoxLayout(self._image_conf_widget)
        conf_row.setContentsMargins(6, 2, 6, 2)
        conf_row.setSpacing(6)
        conf_row.addWidget(QLabel("Detection Confidence"))
        self._image_conf_spinbox = QDoubleSpinBox()
        self._image_conf_spinbox.setRange(0.0, 1.0)
        self._image_conf_spinbox.setSingleStep(0.01)
        self._image_conf_spinbox.setDecimals(2)
        self._image_conf_spinbox.setValue(
            self.w.annotation_confidence_spinBox.value())
        self._image_conf_spinbox.setToolTip("Image annotation confidence threshold")
        self._image_conf_spinbox.setFixedWidth(80)
        self._image_conf_spinbox.valueChanged.connect(self._on_image_conf_changed)
        conf_row.addWidget(self._image_conf_spinbox)
        conf_row.addStretch()
        self._image_conf_widget.setVisible(False)
        vbox.addWidget(self._image_conf_widget)

        # Reparent imv from self.w into the container
        vbox.addWidget(self.imv)
        self._image_inner_window.setCentralWidget(container)
        # Clear self.w's central widget (imv has been reparented away)
        self.w.setCentralWidget(QWidget())

        # Move the navigation controls dock (slider, spinbox, fwd/rwd buttons,
        # step, zoom-to, range) from self.w into the image browser inner window.
        # Safe now that the inner window has no addToolBar() toolbar — the old
        # crash was caused by addToolBar()'s QToolBarWidgetAction bookkeeping,
        # not by dock reparenting itself.
        self.w.removeDockWidget(self.w.imageBrowsing)
        self._image_inner_window.addDockWidget(
            Qt.DockWidgetArea.BottomDockWidgetArea, self.w.imageBrowsing)
        self.w.imageBrowsing.show()

        # Outer floating dock in the main QGIS window
        self._image_dock = QDockWidget("Image Browser", _iface.mainWindow())
        self._image_dock.setObjectName("GroundTrutherImageDock")
        self._image_dock.setAllowedAreas(Qt.DockWidgetArea(15))       # AllDockWidgetAreas
        self._image_dock.setFeatures(
            QDockWidget.DockWidgetFeature(7))                         # Closable|Movable|Floatable
        self._image_dock.setWidget(self._image_inner_window)

        # Docked on the left side of QGIS by default.
        # DockWidgetFloatable is set in features so the user can detach it freely.
        _iface.addDockWidget(Qt.DockWidgetArea(2), self._image_dock)
        self._image_dock.hide()  # all plugin docks start hidden; user opens via toolbar

        # Toggle action in self.w toolbar so the user can re-open the dock
        from groundtruther.mixins.toolbar_icons import make_toggle_icon
        self._image_dock_action = QAction(self)
        self._image_dock_action.setIcon(make_toggle_icon("file-image.svg"))
        self._image_dock_action.setCheckable(True)
        self._image_dock_action.setChecked(False)
        self._image_dock_action.setToolTip("Show / hide the Image Browser")
        self._image_dock_action.toggled.connect(self._toggle_image_dock)
        self._image_dock.visibilityChanged.connect(self._on_image_dock_visibility)
        first = self.w.toolBar.actions()
        self.w.toolBar.insertAction(first[0] if first else None,
                                    self._image_dock_action)

        # Move actionAnnotation from self.w toolbar into the image browser toolbar
        self.w.toolBar.removeAction(self.w.actionAnnotation)
        self._image_toolbar.addAction(self.w.actionAnnotation)
        # Replace the old showAnnotationThreshold connection with one that
        # shows/hides the confidence row inside this dock
        try:
            self.w.actionAnnotation.triggered.disconnect(self.showAnnotationThreshold)
        except Exception:
            pass
        self.w.actionAnnotation.toggled.connect(
            lambda checked: self._image_conf_widget.setVisible(checked))
        # Permanently hide the originals in self.w (they have moved here)
        self.w.annotation_confidence_spinBox.hide()
        self.w.annotation_confidence_spinBox_label.hide()

        # Metadata side panel — docked on the left of the image browser inner window
        self._image_metadata_dock = QDockWidget("Image Metadata",
                                                self._image_inner_window)
        self._image_metadata_dock.setObjectName("GroundTrutherImageMetadataDock")
        self._image_metadata_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self._image_metadata_dock.setWidget(self.imagemetadata_gui)
        self._image_metadata_dock.hide()
        self._image_inner_window.addDockWidget(
            Qt.DockWidgetArea.LeftDockWidgetArea, self._image_metadata_dock)

        self._meta_panel_action = QAction("Metadata", self._image_inner_window)
        self._meta_panel_action.setCheckable(True)
        self._meta_panel_action.setToolTip("Show / hide the image metadata panel")
        self._meta_panel_action.toggled.connect(self._image_metadata_dock.setVisible)
        self._image_metadata_dock.visibilityChanged.connect(
            self._meta_panel_action.setChecked)
        self._image_toolbar.addSeparator()
        self._image_toolbar.addAction(self._meta_panel_action)

        QgsMessageLog.logMessage(
            "Image browser dock created", "GroundTruther", Qgis.Info)

    def _on_image_conf_changed(self, value: float) -> None:
        """Update the threshold and immediately redraw the annotation overlay."""
        self.annotation_confidence_treshold = value
        if self.imageMetadata is None:
            return
        # Skip redraw when the editor dock is open — it owns the ROI display
        ann_editor_open = (
            hasattr(self, 'annotation_editor_dock')
            and self.annotation_editor_dock.isVisible()
        )
        if self.w.actionAnnotation.isChecked() and not ann_editor_open:
            self.add_image_annotation()

    def _cleanup_image_browser_dock(self) -> None:
        """Remove the floating image browser dock from QGIS."""
        if not hasattr(self, '_image_dock') or self._image_dock is None:
            return
        dock = self._image_dock
        self._image_dock = None
        self._image_inner_window = None
        try:
            dock.hide()
            dock.setWidget(None)
            from qgis.utils import iface as _iface
            _iface.removeDockWidget(dock)
            dock.deleteLater()
        except Exception:
            pass

    def _toggle_image_dock(self, checked: bool) -> None:
        dock = getattr(self, '_image_dock', None)
        if dock is None:
            return
        if checked:
            dock.show()
            dock.raise_()
        else:
            dock.hide()

    def _on_image_dock_visibility(self, visible: bool) -> None:
        action = getattr(self, '_image_dock_action', None)
        if action is None:
            return
        action.blockSignals(True)
        action.setChecked(visible)
        action.blockSignals(False)

    def showImageViewer(self):
        dock = getattr(self, '_image_dock', None)
        if dock is None:
            # Fallback when dock hasn't been created yet or has been torn down
            try:
                if self.imv.isVisible():
                    self.imv.hide()
                    self.imageviewer_is_hidden = True
                else:
                    self.imv.show()
                    self.imageviewer_is_hidden = False
            except RuntimeError:
                pass
            return
        if dock.isVisible():
            dock.hide()
            self.imageviewer_is_hidden = True
            if hasattr(self, '_image_dock_action') and self._image_dock_action:
                self._image_dock_action.blockSignals(True)
                self._image_dock_action.setChecked(False)
                self._image_dock_action.blockSignals(False)
        else:
            dock.show()
            dock.raise_()
            self.imageviewer_is_hidden = False
            if hasattr(self, '_image_dock_action') and self._image_dock_action:
                self._image_dock_action.blockSignals(True)
                self._image_dock_action.setChecked(True)
                self._image_dock_action.blockSignals(False)

    def showImageBrowser(self):
        dock = getattr(self, '_image_dock', None)
        if dock is not None:
            if dock.isVisible():
                dock.hide()
                self.imageviewer_is_hidden = True
            else:
                dock.show()
                self.imageviewer_is_hidden = False
            return
        # Fallback
        if self.imv.isVisible():
            self.w.imageBrowsing.hide()
            self.imageviewer_is_hidden = True
        else:
            self.w.imageBrowsing.show()
            self.imageviewer_is_hidden = False

    def setValue_annotation_confidence(self):
        self.annotation_confidence_treshold = (
            self.w.annotation_confidence_spinBox.value()
        )

    def showAnnotationThreshold(self):
        if self.w.annotation_confidence_spinBox.isVisible():
            self.w.annotation_confidence_spinBox.hide()
            self.w.annotation_confidence_spinBox_label.hide()
        else:
            self.w.annotation_confidence_spinBox.show()
            self.w.annotation_confidence_spinBox_label.show()
