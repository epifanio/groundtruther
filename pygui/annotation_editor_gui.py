"""Annotation editor panel for the GroundTruther image browser.

Injected as a QDockWidget on the right side of the HBCBrowserGui
QMainWindow.  When visible it overlays pg.RectROI handles on the image
view so the user can:

  - select a bounding box from the list (or by clicking/dragging a ROI)
  - drag its corner/edge handles to reshape it
  - rename its label via a dialog
  - delete it
  - draw a completely new bounding box by clicking and dragging
  - save all annotations for the current session back to a CSV file

The widget never modifies the parent DataFrame directly; it emits
``annotation_changed(image_index)`` and the dockwidget commits the
edit into the DataFrame via ``commit()``.
"""
from __future__ import annotations

import copy
import csv
import json
import numpy as np

from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QListWidgetItem,
    QLabel, QInputDialog, QMessageBox, QFileDialog,
    QAbstractItemView, QSizePolicy,
    QComboBox, QLineEdit, QDoubleSpinBox, QFrame,
    QGraphicsRectItem,
)
from qgis.PyQt.QtCore import Qt, pyqtSignal, QObject, QEvent, QRectF
from qgis.PyQt.QtGui import QPen, QColor

import pyqtgraph as pg

try:
    from qgis.core import Qgis, QgsMessageLog
    def _log(msg, level=Qgis.Info):
        QgsMessageLog.logMessage(msg, 'GroundTruther', level)
except ImportError:
    def _log(msg, level=None):
        print(msg)


def _is_nan(value) -> bool:
    """Return True when *value* is NaN or None (no annotation)."""
    if value is None:
        return True
    try:
        return bool(np.isnan(value))
    except (TypeError, ValueError):
        return False


def _bbox_to_rect(coords: list) -> tuple[float, float, float, float]:
    """Return (x0, y0, x1, y1) from an 8-element bbox coord list."""
    xs = coords[0::2]
    ys = coords[1::2]
    return min(xs), min(ys), max(xs), max(ys)


def _rect_to_bbox(x0: float, y0: float, x1: float, y1: float) -> list:
    """Reconstruct the 8-element bbox format used by parse_annotation.

    Winding: [TL_x, BR_y, BR_x, BR_y, BR_x, TL_y, TL_x, TL_y]
    which matches build_box corner order (BL, BR, TR, TL).
    """
    return [x0, y1, x1, y1, x1, y0, x0, y0]


# ---------------------------------------------------------------------------
# Event filter for rubber-band drawing on the image view
# ---------------------------------------------------------------------------

class _DrawEventFilter(QObject):
    """Widget-level event filter installed on the ImageView's graphicsView.

    Captures left-button press/move/release events for drawing a new
    bounding box.  Returns True (consuming the event) so that pyqtgraph's
    pan/zoom behaviour does not interfere while drawing is active.
    """

    press   = pyqtSignal(object)   # QPoint in widget coordinates
    move    = pyqtSignal(object)   # QPoint in widget coordinates
    release = pyqtSignal(object)   # QPoint in widget coordinates

    def __init__(self, parent: QObject = None):
        super().__init__(parent)
        self._active = False

    def eventFilter(self, obj, event):
        t = event.type()
        if t == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            self._active = True
            self.press.emit(event.pos())
            return True
        if t == QEvent.MouseMove and self._active:
            self.move.emit(event.pos())
            return True
        if t == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
            if self._active:
                self._active = False
                self.release.emit(event.pos())
                return True
        return False


# ---------------------------------------------------------------------------
# Main editor widget
# ---------------------------------------------------------------------------

class AnnotationEditorWidget(QWidget):
    """Side-panel editor for per-image annotation bounding boxes.

    Parameters
    ----------
    image_view:
        The ``MyImageView`` (pg.ImageView subclass) that displays the
        current frame.  ROIs are added to / removed from its ViewBox.
    parent:
        Optional Qt parent.

    Signals
    -------
    annotation_changed(int)
        Emitted with the current image index whenever the user modifies
        an annotation so the parent dockwidget can push the change into
        the DataFrame and refresh the image overlay.
    draw_mode_exited()
        Emitted when draw mode is stopped so the parent toolbar action
        can update its checked state.
    """

    annotation_changed = pyqtSignal(int)
    draw_mode_exited   = pyqtSignal()

    # ------------------------------------------------------------------ #
    # Construction                                                         #
    # ------------------------------------------------------------------ #

    def __init__(self, image_view: pg.ImageView, parent=None):
        super().__init__(parent)
        self._imv = image_view
        self._rois: list[pg.RectROI] = []
        self._annotation: dict | None = None   # deep-copy of current frame
        self._image_index: int = 0
        self._imagename: str = ""
        self._csv_path: str = ""
        self._dirty: bool = False

        # Known labels (built from CSV + persisted in sidecar JSON)
        self._known_labels: list[str] = []
        self._labels_path: str = ""

        # Draw-mode state
        self._draw_filter: _DrawEventFilter | None = None
        self._draw_start: tuple[float, float] | None = None
        self._preview_item: QGraphicsRectItem | None = None
        self._draw_mode: bool = False

        # Pending new-annotation state (box drawn, waiting for label input)
        self._pending_bbox: tuple[float, float, float, float] | None = None
        self._pending_item: QGraphicsRectItem | None = None

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        title = QLabel("<b>Annotation Editor</b>")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # --- Bounding-box list ---
        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._list.currentRowChanged.connect(self._on_row_changed)
        layout.addWidget(self._list)

        # --- Action buttons ---
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(4)

        self._btn_add = QPushButton("➕ Add new box")
        self._btn_add.setToolTip(
            "Click then drag on the image to draw a new bounding box")
        self._btn_add.setCheckable(True)
        self._btn_add.clicked.connect(self._on_add_btn_clicked)
        btn_layout.addWidget(self._btn_add)

        self._btn_label = QPushButton("Edit label…")
        self._btn_label.setToolTip("Rename the selected annotation label")
        self._btn_label.clicked.connect(self._edit_label)
        btn_layout.addWidget(self._btn_label)

        self._btn_delete = QPushButton("Delete selected")
        self._btn_delete.setToolTip("Remove the selected bounding box")
        self._btn_delete.clicked.connect(self._delete_selected)
        btn_layout.addWidget(self._btn_delete)

        layout.addLayout(btn_layout)

        # --- Inline new-annotation form (hidden until box is drawn) ---
        self._new_ann_frame = QFrame()
        self._new_ann_frame.setFrameShape(QFrame.Shape.StyledPanel)
        new_layout = QVBoxLayout(self._new_ann_frame)
        new_layout.setContentsMargins(4, 4, 4, 4)
        new_layout.setSpacing(4)

        new_layout.addWidget(QLabel("<b>New annotation</b>"))

        new_layout.addWidget(QLabel("Existing label:"))
        self._new_label_combo = QComboBox()
        self._new_label_combo.currentIndexChanged.connect(
            self._on_new_combo_changed)
        new_layout.addWidget(self._new_label_combo)

        new_layout.addWidget(QLabel("Or type new label:"))
        self._new_label_edit = QLineEdit()
        self._new_label_edit.setPlaceholderText("Label…")
        new_layout.addWidget(self._new_label_edit)

        conf_row = QHBoxLayout()
        conf_row.addWidget(QLabel("Confidence:"))
        self._new_conf_spin = QDoubleSpinBox()
        self._new_conf_spin.setRange(0.0, 1.0)
        self._new_conf_spin.setValue(1.0)
        self._new_conf_spin.setDecimals(2)
        self._new_conf_spin.setSingleStep(0.05)
        conf_row.addWidget(self._new_conf_spin)
        new_layout.addLayout(conf_row)

        btn_row2 = QHBoxLayout()
        self._new_confirm_btn = QPushButton("✔ Add")
        self._new_cancel_btn = QPushButton("✘ Cancel")
        btn_row2.addWidget(self._new_confirm_btn)
        btn_row2.addWidget(self._new_cancel_btn)
        new_layout.addLayout(btn_row2)

        self._new_confirm_btn.clicked.connect(self._confirm_new_annotation)
        self._new_cancel_btn.clicked.connect(self._cancel_new_annotation)
        self._new_ann_frame.setVisible(False)
        layout.addWidget(self._new_ann_frame)

        # Hint text
        hint = QLabel(
            "<small>Draw mode: click and drag<br>"
            "on the image to create a box.<br>"
            "Drag a ROI or its handles to resize.<br>"
            "Click a ROI to select it in the list.</small>"
        )
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.setMinimumWidth(180)
        self.setMaximumWidth(300)

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def load_image(self, image_index: int, imagename: str,
                   annotation, csv_path: str = "") -> bool:
        """Switch to a new image frame."""
        if self._dirty:
            reply = QMessageBox.question(
                self, "Unsaved changes",
                "There are unsaved annotation changes.\n"
                "Commit them before switching image?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            )
            if reply == QMessageBox.Cancel:
                return False
            if reply == QMessageBox.Yes:
                self.annotation_changed.emit(self._image_index)

        # Cancel pending new annotation silently
        self._dismiss_pending(silent=True)

        # Exit draw mode silently when switching images
        if self._draw_mode:
            self._exit_draw_mode_internal()

        self._remove_rois()
        self._image_index = image_index
        self._imagename = imagename
        if csv_path:
            old_csv = self._csv_path
            self._csv_path = csv_path
            if csv_path != old_csv:
                stem = csv_path.rsplit(".", 1)[0] if "." in csv_path else csv_path
                self._labels_path = stem + "_labels.json"
                self._load_labels_file()
        self._dirty = False
        self._annotation = None if _is_nan(annotation) else copy.deepcopy(annotation)

        self._rebuild_list()
        self._rebuild_rois()
        return True

    def commit(self) -> dict | None:
        """Return a deep copy of the current (possibly edited) annotation."""
        return copy.deepcopy(self._annotation) if self._annotation else None

    def is_dirty(self) -> bool:
        return self._dirty

    def set_known_labels(self, labels: list[str]):
        """Set (or refresh) the pool of known label strings."""
        merged = sorted(set(self._known_labels) | set(labels))
        self._known_labels = merged
        self._save_labels_file()
        if self._new_ann_frame.isVisible():
            self._populate_new_label_combo()

    def cleanup(self):
        """Safe full teardown — call before the parent widget is destroyed.

        Removes all ROIs, cancels any pending annotation, exits draw mode,
        and releases the mouse grab so no dangling C++ references remain.
        """
        self._dismiss_pending(silent=True)
        if self._draw_mode:
            self._exit_draw_mode_internal()
        self._remove_preview()
        self._remove_rois()

    def start_draw_mode(self):
        """Enable rubber-band draw mode on the image view."""
        if self._draw_mode:
            return
        self._draw_mode = True
        self._btn_add.setChecked(True)

        gv = self._imv.ui.graphicsView
        gv.setMouseTracking(True)

        self._draw_filter = _DrawEventFilter(self)
        self._draw_filter.press.connect(self._on_draw_press)
        self._draw_filter.move.connect(self._on_draw_move)
        self._draw_filter.release.connect(self._on_draw_release)
        gv.installEventFilter(self._draw_filter)
        gv.setCursor(Qt.CursorShape.CrossCursor)

    def stop_draw_mode(self):
        """Disable rubber-band draw mode and restore normal navigation."""
        if not self._draw_mode:
            return
        self._exit_draw_mode_internal()
        self.draw_mode_exited.emit()

    def save_all_to_csv(self, image_metadata, csv_path: str = "") -> bool:
        """Write the full edited annotation set to a CSV file."""
        path = csv_path or self._csv_path
        if not path:
            path, _ = QFileDialog.getSaveFileName(
                self, "Save annotations", "", "CSV files (*.csv)")
            if not path:
                return False
            self._csv_path = path

        rows = []
        for _, row in image_metadata.iterrows():
            ann = row.get("Annotation")
            if _is_nan(ann):
                continue
            imagename = str(row["Imagename"]) + ".jpg"
            for i, bbox_wrapper in enumerate(ann.get("bbox", [])):
                coords = bbox_wrapper["bbox"]
                x0, y0, x1, y1 = _bbox_to_rect(coords)
                rows.append({
                    "Detection": "",
                    "Imagename": imagename,
                    "Frame_Identifier": "",
                    "TL_x": x0,
                    "TL_y": y0,
                    "BR_x": x1,
                    "BR_y": y1,
                    "detection_Confidence": "",
                    "Target_Length": "",
                    "Species": ann["Species"][i],
                    "Confidence": ann["Confidence"][i],
                })

        fieldnames = [
            "Detection", "Imagename", "Frame_Identifier",
            "TL_x", "TL_y", "BR_x", "BR_y",
            "detection_Confidence", "Target_Length",
            "Species", "Confidence",
        ]
        try:
            with open(path, "w", newline="") as fh:
                fh.write("\n\n")
                writer = csv.DictWriter(fh, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            self._dirty = False
            _log(f"Annotations saved to {path}")
            return True
        except OSError as exc:
            _log(f"save_all_to_csv: {exc}")
            QMessageBox.critical(self, "Save failed", str(exc))
            return False

    # ------------------------------------------------------------------ #
    # Internal helpers — ROI / list management                            #
    # ------------------------------------------------------------------ #

    def _rebuild_list(self):
        self._list.blockSignals(True)
        self._list.clear()
        if self._annotation:
            for i, species in enumerate(self._annotation.get("Species", [])):
                conf = self._annotation["Confidence"][i]
                try:
                    conf_str = f"{float(conf):.2f}"
                except (TypeError, ValueError):
                    conf_str = str(conf)
                item = QListWidgetItem(f"{i+1}: {species}  ({conf_str})")
                self._list.addItem(item)
        self._list.blockSignals(False)

    def _rebuild_rois(self):
        """Replace any existing ROIs with one RectROI per bbox."""
        self._remove_rois()
        if not self._annotation:
            return
        view = self._imv.getView()
        for i, bbox_wrapper in enumerate(self._annotation.get("bbox", [])):
            coords = bbox_wrapper["bbox"]
            x0, y0, x1, y1 = _bbox_to_rect(coords)
            roi = pg.RectROI(
                pos=[x0, y0],
                size=[x1 - x0, y1 - y0],
                pen=pg.mkPen("r", width=2),
                handlePen=pg.mkPen("y", width=2),
                movable=True,
            )
            roi.handleSize = 10
            roi._gt_index = i
            # Dragging a ROI selects it in the list
            roi.sigRegionChangeStarted.connect(
                lambda _r, idx=i: self._list.setCurrentRow(idx)
            )
            roi.sigRegionChangeFinished.connect(self._on_roi_changed)
            view.addItem(roi)
            self._rois.append(roi)

    def _remove_rois(self):
        view = self._imv.getView()
        for roi in self._rois:
            # Disconnect signals first to prevent callbacks firing on a
            # partially-destroyed ROI after removeItem().
            try:
                roi.sigRegionChangeStarted.disconnect()
            except Exception:
                pass
            try:
                roi.sigRegionChangeFinished.disconnect()
            except Exception:
                pass
            try:
                view.removeItem(roi)
            except Exception:
                pass
        self._rois.clear()

    def _highlight_roi(self, index: int):
        for i, roi in enumerate(self._rois):
            color = "w" if i == index else "r"
            roi.setPen(pg.mkPen(color, width=2))

    def _selected_row(self) -> int:
        return self._list.currentRow()

    # ------------------------------------------------------------------ #
    # Internal helpers — label persistence                                 #
    # ------------------------------------------------------------------ #

    def _load_labels_file(self):
        if not self._labels_path:
            return
        try:
            with open(self._labels_path) as fh:
                data = json.load(fh)
                saved = data.get("labels", [])
                self._known_labels = sorted(set(self._known_labels) | set(saved))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass

    def _save_labels_file(self):
        if not self._labels_path:
            return
        try:
            with open(self._labels_path, "w") as fh:
                json.dump({"labels": sorted(self._known_labels)}, fh, indent=2)
        except OSError as exc:
            _log(f"_save_labels_file: {exc}")

    def _register_label(self, label: str):
        if label not in self._known_labels:
            self._known_labels = sorted(set(self._known_labels) | {label})
            self._save_labels_file()

    # ------------------------------------------------------------------ #
    # Internal helpers — draw mode                                         #
    # ------------------------------------------------------------------ #

    def _exit_draw_mode_internal(self):
        """Core draw-mode teardown (no signal emitted)."""
        self._draw_mode = False
        self._btn_add.setChecked(False)

        gv = self._imv.ui.graphicsView
        if self._draw_filter is not None:
            gv.removeEventFilter(self._draw_filter)
            self._draw_filter = None
        # Safety: release mouse grab if it was left active
        try:
            gv.releaseMouse()
        except Exception:
            pass
        gv.setCursor(Qt.CursorShape.ArrowCursor)

        self._remove_preview()
        self._draw_start = None

    def _remove_preview(self):
        """Remove the rubber-band preview rectangle from the ViewBox."""
        if self._preview_item is not None:
            try:
                self._imv.getView().removeItem(self._preview_item)
            except Exception:
                pass
            self._preview_item = None

    def _widget_to_view(self, widget_pos) -> tuple[float, float]:
        """Convert a widget-space QPoint to image/view coordinates."""
        gv = self._imv.ui.graphicsView
        scene_pos = gv.mapToScene(widget_pos)
        view_pos = self._imv.getView().mapSceneToView(scene_pos)
        return view_pos.x(), view_pos.y()

    # ------------------------------------------------------------------ #
    # Internal helpers — inline new-annotation form                        #
    # ------------------------------------------------------------------ #

    def _populate_new_label_combo(self):
        self._new_label_combo.blockSignals(True)
        self._new_label_combo.clear()
        self._new_label_combo.addItem("")          # blank placeholder
        for lbl in self._known_labels:
            self._new_label_combo.addItem(lbl)
        self._new_label_combo.blockSignals(False)

    def _show_new_annotation_form(self, x0: float, y0: float,
                                   x1: float, y1: float):
        """Show the inline label form and a green preview of the drawn box."""
        self._pending_bbox = (x0, y0, x1, y1)

        # Green non-interactive rectangle in image coordinates
        self._dismiss_pending_item()
        self._pending_item = QGraphicsRectItem(
            QRectF(x0, y0, x1 - x0, y1 - y0))
        pen = QPen(QColor("lime"))
        pen.setCosmetic(True)
        pen.setWidth(2)
        self._pending_item.setPen(pen)
        self._imv.getView().addItem(self._pending_item)

        self._populate_new_label_combo()
        self._new_label_edit.clear()
        self._new_conf_spin.setValue(1.0)
        self._new_ann_frame.setVisible(True)
        self._new_label_edit.setFocus()

    def _dismiss_pending_item(self):
        """Remove the pending preview rectangle from the ViewBox."""
        if self._pending_item is not None:
            try:
                self._imv.getView().removeItem(self._pending_item)
            except Exception:
                pass
            self._pending_item = None

    def _dismiss_pending(self, silent: bool = False):
        """Cancel the pending new annotation (item + form)."""
        self._dismiss_pending_item()
        self._pending_bbox = None
        self._new_ann_frame.setVisible(False)

    # ------------------------------------------------------------------ #
    # Internal helpers — add annotation                                    #
    # ------------------------------------------------------------------ #

    def _add_annotation(self, x0: float, y0: float,
                         x1: float, y1: float,
                         label: str, confidence: float = 1.0):
        """Append a new bbox entry and refresh the ROI list."""
        if self._annotation is None:
            self._annotation = {"bbox": [], "Species": [], "Confidence": []}
        new_bbox = {"bbox": _rect_to_bbox(x0, y0, x1, y1)}
        self._annotation["bbox"].append(new_bbox)
        self._annotation["Species"].append(label)
        self._annotation["Confidence"].append(confidence)
        self._dirty = True
        self._register_label(label)
        self._rebuild_list()
        self._rebuild_rois()
        self._list.setCurrentRow(len(self._annotation["bbox"]) - 1)
        self.annotation_changed.emit(self._image_index)
        _log(
            f"New annotation added: label={label!r} "
            f"({x0:.1f},{y0:.1f})-({x1:.1f},{y1:.1f}) "
            f"conf={confidence:.2f}"
        )

    # ------------------------------------------------------------------ #
    # Slots — existing ROI / list interaction                              #
    # ------------------------------------------------------------------ #

    def _on_row_changed(self, row: int):
        self._highlight_roi(row)

    def _on_roi_changed(self, roi: pg.RectROI):
        """Sync in-memory bbox when the user finishes dragging a handle."""
        idx = roi._gt_index
        if self._annotation is None or idx >= len(self._annotation["bbox"]):
            return
        pos = roi.pos()
        size = roi.size()
        x0, y0 = pos.x(), pos.y()
        x1, y1 = x0 + size.x(), y0 + size.y()
        self._annotation["bbox"][idx]["bbox"] = _rect_to_bbox(x0, y0, x1, y1)
        self._dirty = True
        _log(f"Annotation {idx} resized to ({x0:.1f},{y0:.1f})-({x1:.1f},{y1:.1f})")
        self.annotation_changed.emit(self._image_index)

    def _edit_label(self):
        row = self._selected_row()
        if row < 0 or self._annotation is None:
            QMessageBox.information(self, "Select annotation",
                                    "Select an annotation in the list first.")
            return
        current = self._annotation["Species"][row]
        new_label, ok = QInputDialog.getText(
            self, "Edit label", "Species / label:", text=current)
        if ok and new_label.strip():
            self._annotation["Species"][row] = new_label.strip()
            self._register_label(new_label.strip())
            self._rebuild_list()
            self._list.setCurrentRow(row)
            self._dirty = True
            self.annotation_changed.emit(self._image_index)

    def _delete_selected(self):
        row = self._selected_row()
        if row < 0 or self._annotation is None:
            QMessageBox.information(self, "Select annotation",
                                    "Select an annotation in the list first.")
            return
        species = self._annotation["Species"][row]
        reply = QMessageBox.question(
            self, "Delete annotation",
            f"Delete «{species}» (box {row + 1})?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        self._annotation["bbox"].pop(row)
        self._annotation["Species"].pop(row)
        self._annotation["Confidence"].pop(row)
        if not self._annotation["bbox"]:
            self._annotation = None
        self._dirty = True
        self._rebuild_list()
        self._rebuild_rois()
        self.annotation_changed.emit(self._image_index)

    # ------------------------------------------------------------------ #
    # Slots — "Add box" button and draw-mode events                        #
    # ------------------------------------------------------------------ #

    def _on_add_btn_clicked(self, checked: bool):
        if checked:
            self.start_draw_mode()
        else:
            self.stop_draw_mode()

    def _on_draw_press(self, widget_pos):
        """Record the start corner of the new box in image coordinates."""
        vx, vy = self._widget_to_view(widget_pos)
        self._draw_start = (vx, vy)

        self._remove_preview()
        self._preview_item = QGraphicsRectItem(QRectF(vx, vy, 0.1, 0.1))
        pen = QPen(QColor("lime"))
        pen.setCosmetic(True)
        pen.setWidth(2)
        self._preview_item.setPen(pen)
        self._imv.getView().addItem(self._preview_item)

        # Grab mouse so move/release are delivered even if cursor drifts out
        self._imv.ui.graphicsView.grabMouse()

    def _on_draw_move(self, widget_pos):
        """Resize the rubber-band preview as the mouse moves."""
        if self._draw_start is None or self._preview_item is None:
            return
        vx1, vy1 = self._widget_to_view(widget_pos)
        vx0, vy0 = self._draw_start
        self._preview_item.setRect(QRectF(
            min(vx0, vx1), min(vy0, vy1),
            abs(vx1 - vx0), abs(vy1 - vy0),
        ))

    def _on_draw_release(self, widget_pos):
        """Finalise the drawn box and show the inline label form."""
        if self._draw_start is None:
            return
        self._imv.ui.graphicsView.releaseMouse()

        vx1, vy1 = self._widget_to_view(widget_pos)
        vx0, vy0 = self._draw_start
        self._remove_preview()
        self._draw_start = None

        rx0, rx1 = min(vx0, vx1), max(vx0, vx1)
        ry0, ry1 = min(vy0, vy1), max(vy0, vy1)

        if (rx1 - rx0) < 3 or (ry1 - ry0) < 3:
            _log("Draw mode: box too small, ignoring.")
            return

        self._show_new_annotation_form(rx0, ry0, rx1, ry1)

    # ------------------------------------------------------------------ #
    # Slots — inline new-annotation form                                   #
    # ------------------------------------------------------------------ #

    def _on_new_combo_changed(self, idx: int):
        """Copy the selected label into the text field."""
        if idx > 0:
            self._new_label_edit.setText(self._new_label_combo.currentText())

    def _confirm_new_annotation(self):
        if self._pending_bbox is None:
            return
        label = self._new_label_edit.text().strip()
        if not label:
            QMessageBox.warning(self, "No label",
                                "Please enter or select a label.")
            return
        confidence = self._new_conf_spin.value()
        x0, y0, x1, y1 = self._pending_bbox
        self._dismiss_pending()
        self._add_annotation(x0, y0, x1, y1, label, confidence)

    def _cancel_new_annotation(self):
        self._dismiss_pending()
