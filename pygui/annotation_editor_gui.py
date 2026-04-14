"""Annotation editor panel for the GroundTruther image browser.

Injected as a QDockWidget on the right side of the HBCBrowserGui
QMainWindow.  When visible it overlays pg.RectROI handles on the image
view so the user can:

  - select a bounding box from the list
  - drag its corner/edge handles to reshape it
  - rename its label via a dialog
  - delete it
  - save all annotations for the current session back to a CSV file

The widget never modifies the parent DataFrame directly; it emits
``annotation_changed(image_index)`` and the dockwidget commits the
edit into the DataFrame via ``commit()``.
"""
from __future__ import annotations

import copy
import csv
import numpy as np

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QListWidgetItem,
    QLabel, QInputDialog, QMessageBox, QFileDialog,
    QAbstractItemView, QSizePolicy,
)
from PyQt5.QtCore import Qt, pyqtSignal

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
    """

    annotation_changed = pyqtSignal(int)

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

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        title = QLabel("<b>Annotation Editor</b>")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._list.currentRowChanged.connect(self._on_row_changed)
        layout.addWidget(self._list)

        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(4)

        self._btn_label = QPushButton("Edit label…")
        self._btn_label.setToolTip("Rename the selected annotation label")
        self._btn_label.clicked.connect(self._edit_label)
        btn_layout.addWidget(self._btn_label)

        self._btn_delete = QPushButton("Delete selected")
        self._btn_delete.setToolTip("Remove the selected bounding box")
        self._btn_delete.clicked.connect(self._delete_selected)
        btn_layout.addWidget(self._btn_delete)

        layout.addLayout(btn_layout)

        # Hint text
        hint = QLabel(
            "<small>Drag the yellow handles<br>to resize a box.</small>"
        )
        hint.setAlignment(Qt.AlignCenter)
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.setMinimumWidth(170)
        self.setMaximumWidth(260)

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def load_image(self, image_index: int, imagename: str,
                   annotation, csv_path: str = "") -> bool:
        """Switch to a new image frame.

        Parameters
        ----------
        image_index:
            Row index into the imageMetadata DataFrame.
        imagename:
            The ``Imagename`` value for the current row (used when saving).
        annotation:
            ``imageMetadata["Annotation"].iloc[image_index]`` — a dict or
            ``np.nan`` / ``None`` when no annotation exists.
        csv_path:
            Path to the annotation CSV file for Save operations.

        Returns
        -------
        bool
            False if the user cancelled a "save before switching" dialog,
            True otherwise.
        """
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
                # Parent will pick up the commit via annotation_changed
                self.annotation_changed.emit(self._image_index)

        self._remove_rois()
        self._image_index = image_index
        self._imagename = imagename
        if csv_path:
            self._csv_path = csv_path
        self._dirty = False
        self._annotation = None if _is_nan(annotation) else copy.deepcopy(annotation)

        self._rebuild_list()
        self._rebuild_rois()
        return True

    def commit(self) -> dict | None:
        """Return a deep copy of the current (possibly edited) annotation.

        Call this from the parent after receiving ``annotation_changed``
        to get the value to write back into the DataFrame.
        """
        return copy.deepcopy(self._annotation) if self._annotation else None

    def is_dirty(self) -> bool:
        return self._dirty

    def save_all_to_csv(self, image_metadata, csv_path: str = "") -> bool:
        """Write the full edited annotation set to a CSV file.

        Parameters
        ----------
        image_metadata:
            The ``imageMetadata`` pandas DataFrame from the dockwidget
            (must have ``Imagename`` and ``Annotation`` columns).
        csv_path:
            Destination path.  If empty a Save dialog is shown.

        Returns
        -------
        bool
            True on success, False if the user cancelled.
        """
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
                # Two blank header rows to match the original CSV format
                fh.write("\n\n")
                writer = csv.DictWriter(fh, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            self._dirty = False
            _log(f"Annotations saved to {path}")
            return True
        except OSError as exc:
            _log(f"save_all_to_csv: {exc}", Qgis.Critical)
            QMessageBox.critical(self, "Save failed", str(exc))
            return False

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _rebuild_list(self):
        self._list.blockSignals(True)
        self._list.clear()
        if self._annotation:
            for i, species in enumerate(self._annotation.get("Species", [])):
                conf = self._annotation["Confidence"][i]
                item = QListWidgetItem(f"{i+1}: {species}  ({conf:.2f})")
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
                handleSize=10,
                movable=True,
            )
            roi._gt_index = i
            roi.sigRegionChangeFinished.connect(self._on_roi_changed)
            view.addItem(roi)
            self._rois.append(roi)

    def _remove_rois(self):
        view = self._imv.getView()
        for roi in self._rois:
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
    # Slots                                                                #
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
        _log(
            f"Annotation {idx} resized to "
            f"({x0:.1f},{y0:.1f})-({x1:.1f},{y1:.1f})",
        )
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
