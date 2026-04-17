"""Video annotation editor panel for the GroundTruther video player.

Mirrors ``AnnotationEditorWidget`` (still-image editor) so both tools
share the same UX.  The panel is split vertically into two areas:

**Top — Annotated Frames list**
    A persistent, sorted list of every frame that carries at least one
    bounding box.  Each row shows the frame index, box count, and the
    first few species labels.  Clicking a row emits ``seek_requested``
    so the mixin can seek the video player to that frame.

**Bottom — Current Frame Annotations editor**
    Shows the bounding-box list for the frame that is currently displayed
    in the video player.  Provides Add / Edit / Delete controls identical
    to the still-image ``AnnotationEditorWidget``.

Key differences from the still-image editor:
* Takes a ``VideoPlayerWidget`` instead of a ``pg.ImageView``.
* Uses ``QRubberBand`` over the video ``QLabel`` for draw-mode preview.
* Coordinate mapping: QLabel widget coords → original frame pixel coords
  via ``_label_to_image_coords()``.
* Annotation format: ``{"bboxes": [[x0,y0,x1,y1], …], "species": […],
  "confidences": […]}`` (video_manager convention).
* ``load_frame()`` instead of ``load_image()``; ``save_all_to_csv()``
  delegates to ``gt.video_manager.save_video_annotations()``.
"""
from __future__ import annotations

import copy
import json

from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QListWidgetItem,
    QLabel, QInputDialog, QMessageBox, QFileDialog,
    QAbstractItemView, QSizePolicy,
    QComboBox, QLineEdit, QDoubleSpinBox, QFrame,
    QRubberBand, QSplitter, QGroupBox,
)
from qgis.PyQt.QtCore import Qt, pyqtSignal, QObject, QEvent, QRect, QSize, QPoint
from qgis.PyQt.QtGui import QColor

try:
    from qgis.core import Qgis, QgsMessageLog
    def _log(msg, level=Qgis.Info):
        QgsMessageLog.logMessage(msg, 'GroundTruther', level)
except ImportError:
    def _log(msg, level=None):
        print(msg)


# ---------------------------------------------------------------------------
# Event filter — identical in structure to the one in annotation_editor_gui
# ---------------------------------------------------------------------------

class _DrawEventFilter(QObject):
    """Event filter installed on the video QLabel for rubber-band drawing."""

    press   = pyqtSignal(object)
    move    = pyqtSignal(object)
    release = pyqtSignal(object)

    def __init__(self, parent: QObject = None):
        super().__init__(parent)
        self._active = False

    def eventFilter(self, obj, event):
        t = event.type()
        if t == QEvent.Type(2) and event.button() == Qt.MouseButton(1):
            self._active = True
            self.press.emit(event.pos())
            return True
        if t == QEvent.Type(5) and self._active:
            self.move.emit(event.pos())
            return True
        if t == QEvent.Type(3) and event.button() == Qt.MouseButton(1):
            if self._active:
                self._active = False
                self.release.emit(event.pos())
                return True
        return False


# ---------------------------------------------------------------------------
# Main widget
# ---------------------------------------------------------------------------

class VideoAnnotationEditorWidget(QWidget):
    """Two-panel video annotation editor.

    Top panel: persistent list of all annotated frames — click to seek.
    Bottom panel: per-frame bbox editor for the currently displayed frame.

    Signals
    -------
    annotation_changed(int)
        Current frame index; emitted when the user modifies an annotation.
    draw_mode_exited()
        Emitted when draw mode ends so toolbar action can sync.
    frame_sync_needed(int)
        Emitted with the draw-frame index just before confirming a new
        annotation; the mixin responds by calling ``sync_frame_state`` so
        that previously committed boxes are not overwritten.
    seek_requested(int)
        Emitted when the user clicks an entry in the Annotated Frames list;
        the mixin forwards this to ``video_player.seek_to_frame``.
    """

    annotation_changed = pyqtSignal(int)
    draw_mode_exited   = pyqtSignal()
    frame_sync_needed  = pyqtSignal(int)
    seek_requested     = pyqtSignal(int)
    save_clicked       = pyqtSignal()
    load_clicked       = pyqtSignal()

    # ------------------------------------------------------------------ #
    # Construction                                                         #
    # ------------------------------------------------------------------ #

    def __init__(self, video_player, parent=None):
        super().__init__(parent)
        self._player = video_player

        self._annotation: dict | None = None
        self._frame_index: int = 0
        self._csv_path: str = ""
        self._dirty: bool = False

        self._known_labels: list[str] = []
        self._labels_path: str = ""

        # Parallel list: row index → frame_index for the annotated-frames panel
        self._annotated_frame_indices: list[int] = []

        # Draw-mode state
        self._draw_filter: _DrawEventFilter | None = None
        self._rubber_band: QRubberBand | None = None
        self._draw_start_widget: QPoint | None = None
        self._draw_start_image: tuple[float, float] | None = None
        self._draw_mode: bool = False

        # Pending new-annotation state
        self._pending_bbox: tuple[float, float, float, float] | None = None

        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        splitter = QSplitter(Qt.Orientation(2))   # Vertical
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter)

        splitter.addWidget(self._build_frames_panel())
        splitter.addWidget(self._build_editor_panel())

        # Give roughly equal initial heights
        splitter.setSizes([180, 300])

    # ------------------------------------------------------------------ #
    # Top panel — annotated frames list                                   #
    # ------------------------------------------------------------------ #

    def _build_frames_panel(self) -> QGroupBox:
        box = QGroupBox("Annotated Frames")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        self._frames_list = QListWidget()
        self._frames_list.setSelectionMode(QAbstractItemView.SelectionMode(1))
        self._frames_list.setSizePolicy(
            QSizePolicy.Policy(7), QSizePolicy.Policy(7))
        self._frames_list.setToolTip(
            "Click a frame to seek the video to that position")
        self._frames_list.currentRowChanged.connect(
            self._on_frames_list_row_changed)
        layout.addWidget(self._frames_list)

        btn_row = QHBoxLayout()
        self._btn_load = QPushButton("📂 Load")
        self._btn_load.setToolTip("Load annotations from a CSV file")
        self._btn_load.clicked.connect(self.load_clicked)
        btn_row.addWidget(self._btn_load)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        hint = QLabel("<small>Click a row to jump to that frame</small>")
        hint.setAlignment(Qt.AlignmentFlag(132))
        layout.addWidget(hint)

        return box

    # ------------------------------------------------------------------ #
    # Bottom panel — per-frame bbox editor                                #
    # ------------------------------------------------------------------ #

    def _build_editor_panel(self) -> QGroupBox:
        self._editor_box = QGroupBox("Frame — Annotations")
        layout = QVBoxLayout(self._editor_box)
        layout.setContentsMargins(4, 6, 4, 4)
        layout.setSpacing(4)

        # --- Bounding-box list ---
        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.SelectionMode(1))
        self._list.setSizePolicy(QSizePolicy.Policy(7), QSizePolicy.Policy(7))
        self._list.currentRowChanged.connect(self._on_row_changed)
        layout.addWidget(self._list)

        # --- Action buttons ---
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(4)

        self._btn_add = QPushButton("➕ Add new box")
        self._btn_add.setToolTip(
            "Click then drag on the video frame to draw a new bounding box")
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

        # --- Inline new-annotation form ---
        self._new_ann_frame = QFrame()
        self._new_ann_frame.setFrameShape(QFrame.Shape(6))
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
        self._new_cancel_btn  = QPushButton("✘ Cancel")
        btn_row2.addWidget(self._new_confirm_btn)
        btn_row2.addWidget(self._new_cancel_btn)
        new_layout.addLayout(btn_row2)

        self._new_confirm_btn.clicked.connect(self._confirm_new_annotation)
        self._new_cancel_btn.clicked.connect(self._cancel_new_annotation)
        self._new_ann_frame.setVisible(False)
        layout.addWidget(self._new_ann_frame)

        hint = QLabel(
            "<small>Draw mode: click and drag on the video frame.<br>"
            "Click a list row to highlight that box.</small>"
        )
        hint.setAlignment(Qt.AlignmentFlag(132))
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self._btn_save = QPushButton("💾 Save annotations")
        self._btn_save.setToolTip("Save all video annotation edits to CSV")
        self._btn_save.clicked.connect(self.save_clicked)
        layout.addWidget(self._btn_save)

        return self._editor_box

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def load_frame(self, frame_index: int, annotation,
                   interactive: bool = True) -> bool:
        """Switch the bottom panel to *frame_index*."""
        if self._dirty and interactive:
            _Yes    = QMessageBox.StandardButton.Yes
            _No     = QMessageBox.StandardButton.No
            _Cancel = QMessageBox.StandardButton.Cancel
            reply = QMessageBox.question(
                self, "Unsaved changes",
                "There are unsaved annotation changes.\n"
                "Commit them before switching frame?",
                _Yes | _No | _Cancel,
            )
            if reply == _Cancel:
                return False
            if reply == _Yes:
                self.annotation_changed.emit(self._frame_index)

        self._dismiss_pending(silent=True)
        if self._draw_mode:
            self._exit_draw_mode_internal()

        self._frame_index = frame_index
        self._dirty = False
        self._annotation = None if not annotation else copy.deepcopy(annotation)
        self._rebuild_list()
        self._player.set_selected_annotation_idx(None)
        self._update_editor_title()
        self._highlight_frame_in_list(frame_index)
        return True

    def sync_frame_state(self, frame_index: int, annotation) -> None:
        """Update frame state without touching draw mode.

        Called by the mixin just before confirming a new annotation so that
        ``_annotation`` has all previously committed boxes for this frame.
        """
        self._frame_index = frame_index
        self._annotation  = None if not annotation else copy.deepcopy(annotation)
        self._rebuild_list()
        self._update_editor_title()

    def update_annotated_frames(self, all_annotations: dict) -> None:
        """Rebuild the top-panel Annotated Frames list from *all_annotations*.

        Should be called by the mixin whenever an annotation is added,
        edited, or deleted.
        """
        self._frames_list.blockSignals(True)
        self._frames_list.clear()
        self._annotated_frame_indices = []

        for frame_idx in sorted(all_annotations.keys()):
            ann = all_annotations[frame_idx]
            n = len(ann.get("bboxes", []))
            if n == 0:
                continue
            species = ann.get("species", [])
            sp_str = ", ".join(str(s) for s in species[:3])
            if len(species) > 3:
                sp_str += f" +{len(species) - 3}"
            plural = "es" if n != 1 else ""
            item = QListWidgetItem(
                f"Frame {frame_idx}  [{n} box{plural}]  {sp_str}")
            self._frames_list.addItem(item)
            self._annotated_frame_indices.append(frame_idx)

        self._frames_list.blockSignals(False)
        self._highlight_frame_in_list(self._frame_index)

    def set_csv_path(self, path: str) -> None:
        """Set the annotation CSV path used by save_all_to_csv()."""
        if path != self._csv_path:
            self._csv_path = path
            if path:
                stem = path.rsplit(".", 1)[0] if "." in path else path
                self._labels_path = stem + "_labels.json"
                self._load_labels_file()

    def commit(self) -> dict | None:
        """Return a deep copy of the current (possibly edited) annotation."""
        return copy.deepcopy(self._annotation) if self._annotation else None

    def is_dirty(self) -> bool:
        return self._dirty

    def set_known_labels(self, labels: list[str]) -> None:
        """Refresh the pool of known label strings."""
        merged = sorted(set(self._known_labels) | set(labels))
        self._known_labels = merged
        self._save_labels_file()
        if self._new_ann_frame.isVisible():
            self._populate_new_label_combo()

    def start_draw_mode(self) -> None:
        """Enable rubber-band draw mode, pausing the video first."""
        if self._draw_mode:
            return
        if self._player._playing:
            self._player._stop_playback()
        self._draw_mode = True
        self._btn_add.setChecked(True)

        label = self._player._video_label
        label.setMouseTracking(True)

        self._draw_filter = _DrawEventFilter(self)
        self._draw_filter.press.connect(self._on_draw_press)
        self._draw_filter.move.connect(self._on_draw_move)
        self._draw_filter.release.connect(self._on_draw_release)
        label.installEventFilter(self._draw_filter)
        label.setCursor(Qt.CursorShape(2))

    def stop_draw_mode(self) -> None:
        """Disable rubber-band draw mode and restore normal cursor."""
        if not self._draw_mode:
            return
        self._exit_draw_mode_internal()
        self.draw_mode_exited.emit()

    def save_all_to_csv(self, all_annotations: dict, csv_path: str = "") -> bool:
        """Serialise *all_annotations* to the annotation CSV."""
        path = csv_path or self._csv_path
        if not path:
            path, _ = QFileDialog.getSaveFileName(
                self, "Save video annotations", "", "CSV files (*.csv)")
            if not path:
                return False
            self._csv_path = path

        try:
            from gt.video_manager import save_video_annotations
            save_video_annotations(all_annotations, path)
            self._dirty = False
            _log(f"Video annotations saved to {path}")
            return True
        except OSError as exc:
            _log(f"save_all_to_csv: {exc}", Qgis.Warning)
            QMessageBox.critical(self, "Save failed", str(exc))
            return False

    def cleanup(self) -> None:
        """Safe teardown — call before the parent widget is destroyed."""
        self._dismiss_pending(silent=True)
        if self._draw_mode:
            self._exit_draw_mode_internal()
        if self._rubber_band is not None:
            self._rubber_band.hide()
            self._rubber_band = None
        self._player.set_selected_annotation_idx(None)

    # ------------------------------------------------------------------ #
    # Internal helpers — UI updates                                        #
    # ------------------------------------------------------------------ #

    def _update_editor_title(self) -> None:
        """Update the bottom group-box title to show the current frame index."""
        self._editor_box.setTitle(f"Frame {self._frame_index} — Annotations")

    def _highlight_frame_in_list(self, frame_index: int) -> None:
        """Select the row for *frame_index* in the top panel (signals blocked)."""
        self._frames_list.blockSignals(True)
        try:
            row = self._annotated_frame_indices.index(frame_index)
            self._frames_list.setCurrentRow(row)
            self._frames_list.scrollToItem(self._frames_list.item(row))
        except ValueError:
            self._frames_list.clearSelection()
        finally:
            self._frames_list.blockSignals(False)

    # ------------------------------------------------------------------ #
    # Internal helpers — list management                                   #
    # ------------------------------------------------------------------ #

    def _rebuild_list(self):
        self._list.blockSignals(True)
        self._list.clear()
        if self._annotation:
            species_list = self._annotation.get("species", [])
            conf_list    = self._annotation.get("confidences", [])
            for i, species in enumerate(species_list):
                conf = conf_list[i] if i < len(conf_list) else 1.0
                try:
                    conf_str = f"{float(conf):.2f}"
                except (TypeError, ValueError):
                    conf_str = str(conf)
                item = QListWidgetItem(f"{i + 1}: {species}  ({conf_str})")
                self._list.addItem(item)
        self._list.blockSignals(False)

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
    # Internal helpers — coordinate mapping                                #
    # ------------------------------------------------------------------ #

    def _label_to_image_coords(self, widget_pos) -> tuple[float, float] | tuple[None, None]:
        """Map a QLabel widget position to original-frame pixel coords (clamped)."""
        label = self._player._video_label
        pm = label.pixmap()
        if pm is None or pm.isNull():
            return None, None
        lw, lh = label.width(), label.height()
        pw, ph = pm.width(), pm.height()
        if pw <= 0 or ph <= 0:
            return None, None
        fw = self._player.frame_width
        fh = self._player.frame_height
        if fw <= 0 or fh <= 0:
            return None, None
        ox = (lw - pw) / 2.0
        oy = (lh - ph) / 2.0
        px = max(0.0, min(float(widget_pos.x()) - ox, float(pw)))
        py = max(0.0, min(float(widget_pos.y()) - oy, float(ph)))
        return px * fw / pw, py * fh / ph

    # ------------------------------------------------------------------ #
    # Internal helpers — draw mode                                         #
    # ------------------------------------------------------------------ #

    def _exit_draw_mode_internal(self):
        self._draw_mode = False
        self._btn_add.setChecked(False)
        label = self._player._video_label
        if self._draw_filter is not None:
            label.removeEventFilter(self._draw_filter)
            self._draw_filter = None
        label.setCursor(Qt.CursorShape(0))
        if self._rubber_band is not None:
            self._rubber_band.hide()
        self._draw_start_widget = None
        self._draw_start_image  = None

    # ------------------------------------------------------------------ #
    # Internal helpers — inline new-annotation form                        #
    # ------------------------------------------------------------------ #

    def _populate_new_label_combo(self):
        self._new_label_combo.blockSignals(True)
        self._new_label_combo.clear()
        self._new_label_combo.addItem("")
        for lbl in self._known_labels:
            self._new_label_combo.addItem(lbl)
        self._new_label_combo.blockSignals(False)

    def _show_new_annotation_form(self, x0, y0, x1, y1):
        self._pending_bbox = (x0, y0, x1, y1)
        self._populate_new_label_combo()
        self._new_label_edit.clear()
        self._new_conf_spin.setValue(1.0)
        self._new_ann_frame.setVisible(True)
        self._new_label_edit.setFocus()

    def _dismiss_pending(self, silent: bool = False):
        self._pending_bbox = None
        self._new_ann_frame.setVisible(False)

    # ------------------------------------------------------------------ #
    # Internal helpers — add annotation                                    #
    # ------------------------------------------------------------------ #

    def _add_annotation(self, x0, y0, x1, y1, label, confidence=1.0):
        if self._annotation is None:
            self._annotation = {"bboxes": [], "species": [], "confidences": []}
        self._annotation["bboxes"].append([x0, y0, x1, y1])
        self._annotation["species"].append(label)
        self._annotation["confidences"].append(confidence)
        self._dirty = True
        self._register_label(label)
        self._rebuild_list()
        new_row = len(self._annotation["bboxes"]) - 1
        self._list.setCurrentRow(new_row)
        self._player.set_selected_annotation_idx(new_row)
        self.annotation_changed.emit(self._frame_index)
        _log(f"Video annotation added: label={label!r} "
             f"({x0:.1f},{y0:.1f})-({x1:.1f},{y1:.1f}) conf={confidence:.2f}")

    # ------------------------------------------------------------------ #
    # Slots — annotated frames list                                        #
    # ------------------------------------------------------------------ #

    def _on_frames_list_row_changed(self, row: int) -> None:
        """Seek the video to the frame the user clicked in the top panel."""
        if row < 0 or row >= len(self._annotated_frame_indices):
            return
        self.seek_requested.emit(self._annotated_frame_indices[row])

    # ------------------------------------------------------------------ #
    # Slots — per-frame list selection                                     #
    # ------------------------------------------------------------------ #

    def _on_row_changed(self, row: int):
        self._player.set_selected_annotation_idx(row if row >= 0 else None)

    # ------------------------------------------------------------------ #
    # Slots — edit / delete                                                #
    # ------------------------------------------------------------------ #

    def _edit_label(self):
        row = self._selected_row()
        if row < 0 or self._annotation is None:
            QMessageBox.information(self, "Select annotation",
                                    "Select an annotation in the list first.")
            return
        current = self._annotation["species"][row]
        new_label, ok = QInputDialog.getText(
            self, "Edit label", "Species / label:", text=current)
        if ok and new_label.strip():
            self._annotation["species"][row] = new_label.strip()
            self._register_label(new_label.strip())
            self._rebuild_list()
            self._list.setCurrentRow(row)
            self._dirty = True
            self.annotation_changed.emit(self._frame_index)

    def _delete_selected(self):
        row = self._selected_row()
        if row < 0 or self._annotation is None:
            QMessageBox.information(self, "Select annotation",
                                    "Select an annotation in the list first.")
            return
        species = self._annotation["species"][row]
        _Yes = QMessageBox.StandardButton.Yes
        _No  = QMessageBox.StandardButton.No
        reply = QMessageBox.question(
            self, "Delete annotation",
            f"Delete «{species}» (box {row + 1})?",
            _Yes | _No,
        )
        if reply != _Yes:
            return
        self._annotation["bboxes"].pop(row)
        self._annotation["species"].pop(row)
        self._annotation["confidences"].pop(row)
        if not self._annotation["bboxes"]:
            self._annotation = None
        self._dirty = True
        self._player.set_selected_annotation_idx(None)
        self._rebuild_list()
        self.annotation_changed.emit(self._frame_index)

    # ------------------------------------------------------------------ #
    # Slots — draw mode                                                    #
    # ------------------------------------------------------------------ #

    def _on_add_btn_clicked(self, checked: bool):
        if checked:
            self.start_draw_mode()
        else:
            self.stop_draw_mode()

    def _on_draw_press(self, widget_pos):
        self._frame_index = self._player.current_frame_index
        ix, iy = self._label_to_image_coords(widget_pos)
        if ix is None:
            return
        self._draw_start_widget = QPoint(widget_pos.x(), widget_pos.y())
        self._draw_start_image  = (ix, iy)
        if self._rubber_band is None:
            self._rubber_band = QRubberBand(
                QRubberBand.Shape(1), self._player._video_label)
        self._rubber_band.setGeometry(QRect(self._draw_start_widget, QSize()))
        self._rubber_band.show()

    def _on_draw_move(self, widget_pos):
        if self._draw_start_widget is None or self._rubber_band is None:
            return
        self._rubber_band.setGeometry(
            QRect(self._draw_start_widget, widget_pos).normalized())

    def _on_draw_release(self, widget_pos):
        if self._draw_start_image is None:
            return
        if self._rubber_band is not None:
            self._rubber_band.hide()
        ix1, iy1 = self._label_to_image_coords(widget_pos)
        if ix1 is None:
            self._draw_start_image = None
            self._draw_start_widget = None
            return
        ix0, iy0 = self._draw_start_image
        self._draw_start_image  = None
        self._draw_start_widget = None
        x0, x1 = min(ix0, ix1), max(ix0, ix1)
        y0, y1 = min(iy0, iy1), max(iy0, iy1)
        if (x1 - x0) < 3 or (y1 - y0) < 3:
            _log("Video draw mode: box too small, ignoring.")
            return
        self._show_new_annotation_form(x0, y0, x1, y1)

    # ------------------------------------------------------------------ #
    # Slots — inline new-annotation form                                   #
    # ------------------------------------------------------------------ #

    def _on_new_combo_changed(self, idx: int):
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
        # Sync with the mixin's canonical data right before appending so that
        # previously committed boxes for this frame are not overwritten.
        self.frame_sync_needed.emit(self._frame_index)
        self._dismiss_pending()
        self._add_annotation(x0, y0, x1, y1, label, confidence)

    def _cancel_new_annotation(self):
        self._dismiss_pending()
