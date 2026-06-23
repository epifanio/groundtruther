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

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import (
    QLabel, QHBoxLayout, QVBoxLayout, QWidget, QFormLayout,
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
# Stereo helpers — HabCam side-by-side pairs are L|R (e.g. 2720x1024)
# ---------------------------------------------------------------------------

def _is_stereo_pair(arr) -> bool:
    """True when *arr* looks like a side-by-side L|R stereo image.

    HabCam stereo frames are a single image with the two views concatenated
    horizontally (the canonical size is 2720x1024).  We detect "much wider than
    tall, with an even width" rather than hard-coding one size, so the split
    also works for other stereo resolutions; ordinary single frames (≈4:3) are
    left untouched.
    """
    if arr is None or getattr(arr, "ndim", 0) < 2:
        return False
    h, w = arr.shape[0], arr.shape[1]
    return w % 2 == 0 and h > 0 and (w / h) >= 2.0


def _split_stereo(arr, mode: str):
    """Return the ``full`` / ``left`` / ``right`` portion of a stereo *arr*."""
    if mode == "full" or not _is_stereo_pair(arr):
        return arr
    half = arr.shape[1] // 2
    if mode == "right":
        return arr[:, half:2 * half]
    return arr[:, :half]   # left is the disparity reference frame


def _decode_png_b64(b64: str):
    """Decode a base64 PNG into an RGBA uint8 ndarray, or ``None`` on failure."""
    import base64
    try:
        data = base64.b64decode(b64)
    except Exception as exc:  # noqa: BLE001
        log_exception("micro-DEM: base64 decode failed", exc, warn=True)
        return None
    try:
        from qgis.PyQt.QtGui import QImage
        qimg = QImage.fromData(data, "PNG")
        if qimg.isNull():
            return None
        qimg = qimg.convertToFormat(QImage.Format.Format_RGBA8888)
        w, h = qimg.width(), qimg.height()
        ptr = qimg.constBits()
        ptr.setsize(h * w * 4)
        return np.frombuffer(ptr, np.uint8).reshape(h, w, 4).copy()
    except Exception as exc:  # noqa: BLE001 — best-effort preview only
        log_exception("micro-DEM: PNG decode failed", exc, warn=True)
        return None


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

        # Stereo display mode: "full" | "left" | "right". Default "left" so
        # side-by-side pairs show the disparity-reference half (which the
        # returned micro-DEM registers to); single frames ignore this.
        self._stereo_display_mode = "left"
        self._micro_dem_item = None
        self._displayed_shape = None

        self.w.fwd.clicked.connect(self.increaseimageindex)
        self.w.rwd.clicked.connect(self.decreaseimageindex)
        self.w.ImageIndexSlider.valueChanged.connect(self.setValueImageIndexspinBox)
        self.w.ImageIndexspinBox.valueChanged.connect(self.setValueImageIndexSlider)
        self.w.ImageStepspinBox.valueChanged.connect(self.setImageIndexStepValue)
        self.w.ImageIndexSlider.valueChanged.connect(self.add_image)

        self.w.range.valueChanged.connect(self.setValuerangeSpinBox)
        # The zoom-to control is a map *scale* (1:N) selector — CRS-independent,
        # unlike the old project-unit buffer. Default QSpinBox max is 99, far too
        # small for a scale denominator, so widen the range here.
        self.w.range.setRange(50, 10_000_000)
        self.w.range.setSingleStep(500)
        self.w.range.setPrefix("1:")
        self.w.range.setToolTip(
            "Zoom-to map scale (1:N). Larger value = more zoomed out.")
        if self.w.range.value() < 50:
            self.w.range.setValue(2500)
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

    def _sampling_lonlat(self, record):
        """Return ``(lon, lat)`` for the current frame's sampling point.

        Uses the calibrated USBL seafloor fix (``Xutm + dx`` / ``Yutm + dy``)
        transformed from the survey CRS (``Roughness.epsg``, default 32619) to
        WGS-84, so the red cross, the roughness raster, and the substrate map all
        coincide.  Falls back to the ``habcam_lon``/``habcam_lat`` model when the
        USBL nav columns are missing or the transform fails.
        """
        # Prefer the usbl_lon/usbl_lat precomputed at load (one transform pass,
        # and the exact positions the KDTree image lookup was built on).
        try:
            if "usbl_lon" in record.index:
                return float(record["usbl_lon"]), float(record["usbl_lat"])
        except Exception:  # noqa: BLE001 — fall through to the per-record path
            pass
        from groundtruther.gt import roughness_geo
        easting, northing = roughness_geo.usbl_easting_northing(record)
        if easting is not None and northing is not None:
            try:
                lonlat = self._usbl_transform().transform(
                    QgsPointXY(easting, northing))
                return lonlat.x(), lonlat.y()
            except Exception as exc:  # noqa: BLE001 — degrade to the model position
                log_exception("sampling USBL transform", exc, warn=True)
        return float(record["habcam_lon"]), float(record["habcam_lat"])

    def _usbl_transform(self):
        """Cached survey-CRS → WGS-84 transform for the USBL sampling point."""
        try:
            epsg = int(((self.settings.get("Roughness") or {}).get("epsg")) or 32619)
        except Exception:  # noqa: BLE001
            epsg = 32619
        xform = getattr(self, "_usbl_xform", None)
        if xform is None or getattr(self, "_usbl_xform_epsg", None) != epsg:
            src = QgsCoordinateReferenceSystem(f"EPSG:{epsg}")
            dst = QgsCoordinateReferenceSystem("EPSG:4326")
            xform = QgsCoordinateTransform(src, dst, QgsProject.instance())
            self._usbl_xform = xform
            self._usbl_xform_epsg = epsg
        return xform

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

        self.w.statusbar.showMessage("System Status | Normal")

        if self.m1:
            self.canvas.scene().removeItem(self.m1)
        self.m1 = QgsVertexMarker(self.canvas)
        self.m1.setCenter(point)
        self.m1.setColor(QColor(255, 0, 0))
        self.m1.setIconSize(10)
        self.m1.setIconType(QgsVertexMarker.ICON_X)
        self.m1.setPenWidth(3)

        # Centre on the image and zoom by map scale (1:rangevalue). Using the
        # map scale is CRS-independent — unlike a buffer in project units, which
        # is microscopic in a metric CRS (metres) but huge in degrees.
        self.canvas.setCenter(point)
        scale = float(self.rangevalue)
        if scale > 0:
            self.canvas.zoomScale(scale)
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
        from groundtruther.mixins.ui_style import LABEL_CSS, VALUE_CSS
        self._meta_widgets = {}

        # Same look as the roughness / video metadata panels: a QFormLayout with
        # grey right-aligned labels and selectable value labels (bigger font).
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(5)
        form.setContentsMargins(8, 8, 8, 8)

        # Time row — DataFrame index is a datetime.
        time_lbl = QLabel("Time")
        time_lbl.setStyleSheet(LABEL_CSS)
        self._meta_time_widget = ExtendedDateTimeEdit()
        self._meta_time_widget.setReadOnly(True)
        self._meta_time_widget.setButtonSymbols(
            QtWidgets.QAbstractSpinBox.ButtonSymbols(2))
        self._meta_time_widget.setStyleSheet(VALUE_CSS)
        self._meta_time_widget.setMaximumWidth(250)
        form.addRow(time_lbl, self._meta_time_widget)

        for col in self.imageMetadata.columns:
            if col in ("usbl_lon", "usbl_lat"):
                continue          # internal USBL position columns, not metadata
            lbl = QLabel(col)
            lbl.setStyleSheet(LABEL_CSS)
            w = QLabel("—")
            w.setWordWrap(True)
            w.setStyleSheet(VALUE_CSS)
            if col == "Imagename":
                w.setOpenExternalLinks(True)
            else:
                w.setTextInteractionFlags(
                    Qt.TextInteractionFlag.TextSelectableByMouse)
            self._meta_widgets[col] = w
            form.addRow(lbl, w)

        container = QWidget()
        container.setLayout(form)
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
                    w.setText(
                        "\n".join(f"{s}: {c}" for s, c in counts.items()))
                else:
                    w.setText("")
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

        # A new frame invalidates any micro-DEM overlay from the previous one.
        self._clear_micro_dem_overlay()
        disp = _split_stereo(_cached_imread(img_path), self._stereo_display_mode)
        self._displayed_shape = getattr(disp, "shape", None)
        self.imv.setImage(disp)

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
            # Sampling-point position: the calibrated USBL fix (Xutm+dx, Yutm+dy)
            # so the red cross coincides with the roughness raster and the
            # substrate map; fall back to the habcam_lon/lat model if the USBL
            # nav columns are absent.
            lon, lat = self._sampling_lonlat(record)
            self.w.longitude.setText(str(round(lon, 8)))
            self.w.latitude.setText(str(round(lat, 8)))
            total = len(self.imageMetadata)
            self._image_counter_label.setText(f"{self.imageindex} / {total - 1}")
            if self.w.zoomto.isChecked():
                self.zoom_to()
            self.on_send()
            # Refresh the roughness panel for the new frame (no-op when hidden).
            if hasattr(self, "_on_frame_changed_roughness"):
                self._on_frame_changed_roughness()
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
    # Micro-DEM overlay (roughness preview)                                #
    # ------------------------------------------------------------------ #

    def _show_micro_dem_overlay(self, png_b64: str, extent_mm=None) -> None:
        """Overlay the micro-DEM preview on the displayed (left) reference image.

        The micro-DEM is computed from the left image of the stereo pair, so it
        registers to the left half currently shown — we map it onto that image's
        pixel rect and draw it semi-transparent on top.  Best-effort: any decode
        failure quietly skips the overlay.
        """
        arr = _decode_png_b64(png_b64)
        if arr is None:
            return
        self._clear_micro_dem_overlay()
        try:
            from qgis.PyQt.QtCore import QRectF
            item = pg.ImageItem(axisOrder="row-major")
            item.setImage(arr)
            item.setOpacity(0.5)
            item.setZValue(20)
            if self._displayed_shape is not None and len(self._displayed_shape) >= 2:
                h, w = self._displayed_shape[0], self._displayed_shape[1]
                item.setRect(QRectF(0, 0, w, h))
            self.imv.view.addItem(item)
            self._micro_dem_item = item
        except Exception as exc:  # noqa: BLE001 — preview only
            log_exception("micro-DEM overlay failed", exc, warn=True)

    def _show_image_overlay_rgba(self, rgba) -> None:
        """Overlay a ready RGBA array on the displayed image at identity.

        Used by the roughness 2-D height overlay (``height_left``), which is
        aligned 1:1 to the rectified-left pixel grid — i.e. the displayed JPG
        when it *is* the rectified left.  Mapped onto the displayed image's
        pixel rect.
        """
        self._clear_micro_dem_overlay()
        try:
            from qgis.PyQt.QtCore import QRectF
            item = pg.ImageItem(axisOrder="row-major")
            item.setImage(rgba)
            item.setZValue(20)
            if self._displayed_shape is not None and len(self._displayed_shape) >= 2:
                h, w = self._displayed_shape[0], self._displayed_shape[1]
                item.setRect(QRectF(0, 0, w, h))
            self.imv.view.addItem(item)
            self._micro_dem_item = item
        except Exception as exc:  # noqa: BLE001 — preview only
            log_exception("height overlay failed", exc, warn=True)

    def _clear_micro_dem_overlay(self) -> None:
        item = getattr(self, "_micro_dem_item", None)
        if item is None:
            return
        self._micro_dem_item = None
        try:
            self.imv.view.removeItem(item)
        except Exception:  # noqa: BLE001 — view may be gone on teardown
            pass

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
        * self.w.imageBrowsing (navigation controls) is detached from self.w and
          registered as a TOP-LEVEL QGIS dock (self._image_nav_dock) so it can be
          docked anywhere in QGIS / floated / placed next to the Query Builder —
          not confined to the inner image window.  Its visibility follows the
          Image Browser dock (_on_image_dock_visibility).  Safe because self.w is
          stripped of all its docks in init_ui, so this reparent leaves self.w's
          QMainWindowLayout empty (the old access-violation came from walking a
          non-empty self.w during dock moves).
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

        # Register the navigation controls (slider, spinbox, fwd/rwd, step,
        # zoom-to, range) as a TOP-LEVEL QGIS dock rather than nesting it inside
        # the image-browser inner window. That lets the user dock it anywhere in
        # QGIS (or float it / re-dock it next to the Query Builder) instead of
        # only back into the inner window. Its visibility follows the Image
        # Browser dock (see _on_image_dock_visibility).
        self.w.removeDockWidget(self.w.imageBrowsing)
        self._image_nav_dock = self.w.imageBrowsing
        self._image_nav_dock.setObjectName("GroundTrutherImageNavDock")
        self._image_nav_dock.setWindowTitle("Image Index")
        self._image_nav_dock.setAllowedAreas(Qt.DockWidgetArea(15))       # all areas
        self._image_nav_dock.setFeatures(
            QDockWidget.DockWidgetFeature(7))                             # C|M|F
        _iface.addDockWidget(
            Qt.DockWidgetArea.BottomDockWidgetArea, self._image_nav_dock)
        self._image_nav_dock.hide()

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

        # Independent toggle for the Image Index nav dock — fully decoupled from
        # the Image Browser, so the slider can be used (e.g. next to the Query
        # Builder) with or without the big image view open.
        self._image_nav_action = QAction(self)
        try:
            self._image_nav_action.setIcon(make_toggle_icon("forward.svg"))
        except Exception:
            self._image_nav_action.setText("Idx")
        self._image_nav_action.setCheckable(True)
        self._image_nav_action.setChecked(False)
        self._image_nav_action.setToolTip("Show / hide the Image Index navigator")
        self._image_nav_action.toggled.connect(self._toggle_nav_dock)
        self._image_nav_dock.visibilityChanged.connect(self._on_nav_dock_visibility)
        # Place it right after the Image Browser toggle.
        acts = self.w.toolBar.actions()
        after = acts[acts.index(self._image_dock_action) + 1] \
            if self._image_dock_action in acts \
            and acts.index(self._image_dock_action) + 1 < len(acts) else None
        self.w.toolBar.insertAction(after, self._image_nav_action)

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

        # Stereo display toggle: Full | Left | Right (exclusive). Hidden until a
        # stereo pair is shown would be ideal, but a static group is simpler and
        # harmless for single frames (split is a no-op there).
        from qgis.PyQt.QtWidgets import QActionGroup
        self._image_toolbar.addSeparator()
        self._stereo_group = QActionGroup(self._image_inner_window)
        self._stereo_group.setExclusive(True)
        self._stereo_actions = {}
        for mode, label in (("full", "Full"), ("left", "Left"), ("right", "Right")):
            act = QAction(label, self._image_inner_window)
            act.setCheckable(True)
            act.setChecked(mode == self._stereo_display_mode)
            act.setToolTip(f"Show the {label.lower()} portion of stereo pairs")
            act.triggered.connect(lambda _checked, m=mode: self._set_stereo_mode(m))
            self._stereo_group.addAction(act)
            self._image_toolbar.addAction(act)
            self._stereo_actions[mode] = act

        QgsMessageLog.logMessage(
            "Image browser dock created", "GroundTruther", Qgis.Info)

    def _set_stereo_mode(self, mode: str) -> None:
        """Switch Full/Left/Right and redraw the current frame."""
        if mode == getattr(self, "_stereo_display_mode", "left"):
            return
        self._stereo_display_mode = mode
        if self.imageMetadata is not None:
            self.add_image()

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
        """Remove the floating image browser dock + nav dock from QGIS."""
        from qgis.utils import iface as _iface
        # Remove the independent Image Index nav dock first (don't deleteLater —
        # it's a Designer child of self.w, torn down with it).
        nav = getattr(self, '_image_nav_dock', None)
        if nav is not None:
            self._image_nav_dock = None
            try:
                nav.hide()
                _iface.removeDockWidget(nav)
            except Exception:
                pass
        if not hasattr(self, '_image_dock') or self._image_dock is None:
            return
        dock = self._image_dock
        self._image_dock = None
        self._image_inner_window = None
        try:
            dock.hide()
            dock.setWidget(None)
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

    def _toggle_nav_dock(self, checked: bool) -> None:
        """Show/hide the Image Index nav dock (independent of the Image Browser)."""
        nav = getattr(self, '_image_nav_dock', None)
        if nav is None:
            return
        if checked:
            nav.show()
            nav.raise_()
        else:
            nav.hide()

    def _on_nav_dock_visibility(self, visible: bool) -> None:
        action = getattr(self, '_image_nav_action', None)
        if action is None:
            return
        action.blockSignals(True)
        action.setChecked(visible)
        action.blockSignals(False)

    def _on_image_dock_visibility(self, visible: bool) -> None:
        # NOTE: do NOT couple the Image Index nav dock here — visibilityChanged
        # also fires when the image dock is tabbed behind another panel, which
        # would wrongly hide the nav on focus loss. The nav follows the explicit
        # toggle in _toggle_image_dock instead.
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
