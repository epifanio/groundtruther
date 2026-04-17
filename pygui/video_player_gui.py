"""Video player widget for the GroundTruther plugin.

``VideoPlayerWidget`` is a self-contained ``QWidget`` that:

* Decodes video frames with OpenCV (``cv2.VideoCapture``), driven by a
  ``QTimer`` for playback.
* Optionally uses GPU-accelerated decode when OpenCV is built with CUDA
  support; GPU availability is auto-detected at construction time and
  shown in a status label.  The user can disable GPU via
  :meth:`set_gpu_enabled`.
* Draws annotation bounding boxes + labels on top of each frame using
  ``QPainter`` on a ``QImage``.
* Displays a live metadata panel populated from the survey CSV so that
  position, depth, bottom type, and biology are always visible alongside
  the video.
* Exposes a geo-link checkbox (``geo_link_toggled`` signal) so the hosting
  mixin can pan the QGIS map canvas to the current frame's GPS position.
* Emits :attr:`frame_changed` whenever the displayed frame changes.

Design notes
------------
* OpenCV is the *only* decoder.  ``QMediaPlayer`` is **not** used here to
  avoid fighting two decode pipelines for seek state.
* Frame data flows as: ``cv2.VideoCapture`` → ``numpy.ndarray`` (BGR) →
  ``QImage`` (RGB) → ``QLabel`` (scaled to widget size).
* The metadata panel is a flat ``QGridLayout`` inside a ``QGroupBox``;
  the hosting mixin calls :meth:`set_frame_metadata` with a dict from
  :func:`~gt.video_manager.frame_position` on every ``frame_changed``.
"""
from __future__ import annotations

import numpy as np

try:
    import cv2
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False

from qgis.PyQt.QtCore import Qt, QTimer, pyqtSignal, QRectF
from qgis.PyQt.QtGui import QImage, QPainter, QColor, QFont, QPen, QPixmap
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSlider, QSpinBox, QDoubleSpinBox, QSizePolicy,
    QToolButton, QCheckBox, QGroupBox, QGridLayout, QToolBar,
)
from qgis.gui import QgsColorButton


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bgr_to_qimage(frame: np.ndarray) -> QImage:
    """Convert an OpenCV BGR ``ndarray`` to a self-contained RGB ``QImage``.

    Two correctness points:
    * ``QImage.Format(13)`` is ``Format_RGB888`` (3 bytes/pixel).
      ``Format(4)`` is ``Format_RGB32`` (4 bytes/pixel padded) — wrong for
      packed 3-channel data and produces a black/garbled image.
    * The ``QImage`` constructor that takes a bare pointer does **not** copy
      the buffer.  The numpy array would be freed by CPython's reference
      counter the moment this function returns, leaving Qt with a dangling
      pointer.  Calling ``.copy()`` makes the QImage own its pixel data.
    """
    h, w, ch = frame.shape
    rgb = frame[:, :, ::-1].copy()          # BGR → RGB; contiguous buffer
    qimg = QImage(rgb.data, w, h, ch * w, QImage.Format(13))  # Format_RGB888
    return qimg.copy()                      # deep-copy so buffer lifetime is Qt's problem


def _draw_annotations(image: QImage,
                      annotations: list[dict],
                      threshold: float = 0.0,
                      selected_index: int | None = None) -> QImage:
    """Paint bounding boxes and labels onto a copy of *image*.

    Parameters
    ----------
    image:
        The source ``QImage`` (not modified in place).
    annotations:
        List of dicts with keys ``bbox`` (``[x0,y0,x1,y1]``), ``species``
        (str), ``confidence`` (float), and optionally ``index`` (int, original
        position in the full annotation list — used for selection highlight).
    threshold:
        Entries below this confidence are skipped.
    selected_index:
        Original annotation index to highlight in yellow.  ``None`` means no
        selection.

    Returns
    -------
    A new ``QImage`` with annotations painted on top.
    """
    out = image.copy()
    painter = QPainter(out)

    font = QFont()
    font.setPointSize(8)
    painter.setFont(font)

    for ann in annotations:
        if ann.get("confidence", 1.0) < threshold:
            continue
        orig_idx = ann.get("index")
        is_selected = (selected_index is not None and orig_idx == selected_index)
        if is_selected:
            pen = QPen(QColor(255, 220, 0))   # yellow highlight
            pen.setWidth(3)
        else:
            pen = QPen(QColor(255, 64, 64))   # normal red
            pen.setWidth(2)
        painter.setPen(pen)
        x0, y0, x1, y1 = ann["bbox"]
        painter.drawRect(QRectF(x0, y0, x1 - x0, y1 - y0))
        label = f"{ann.get('species', '')} {ann.get('confidence', 0):.2f}"
        painter.drawText(QRectF(x0 + 2, y0 - 14, 300, 14), label)

    painter.end()
    return out


# ---------------------------------------------------------------------------
# Metadata panel helper
# ---------------------------------------------------------------------------

# Fields shown in the metadata panel: (dict_key, display_label, row, col_pair)
# col_pair 0 → columns 0-1 (left),  col_pair 1 → columns 2-3 (right)
_META_FIELDS: list[tuple[str, str, int, int]] = [
    ("frame_index",  "Sequence",  0, 0),
    ("timestamp",    "Date/Time", 0, 1),
    ("latitude",     "Latitude",  1, 0),
    ("longitude",    "Longitude", 1, 1),
    ("depth",        "Depth (m)", 2, 0),
    ("cp_mean_alt",  "Altitude",  2, 1),
    ("bottom",       "Bottom",    3, 0),
    ("biology",      "Biology",   3, 1),
    ("cruise",       "Cruise",    4, 0),
    ("station",      "Station",   4, 1),
    ("comments",     "Comments",  5, 0),
]


# ---------------------------------------------------------------------------
# Main widget
# ---------------------------------------------------------------------------

class VideoPlayerWidget(QWidget):
    """Self-contained video player with metadata panel and geo-link control.

    Signals
    -------
    frame_changed(int)
        Emitted whenever the displayed frame index changes.
    geo_link_toggled(bool)
        Emitted when the user toggles the geo-link checkbox.
    """

    frame_changed            = pyqtSignal(int)
    geo_link_toggled         = pyqtSignal(bool)
    zoom_changed             = pyqtSignal(int)
    track_visibility_changed = pyqtSignal(bool)
    track_color_changed      = pyqtSignal(object)   # QColor
    track_width_changed      = pyqtSignal(float)

    _FALLBACK_FPS:   float = 25.0
    _MIN_INTERVAL_MS: int  = 10

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._cap: "cv2.VideoCapture | None" = None
        self._total_frames: int = 0
        self._current_frame: int = 0
        self._fps: float = self._FALLBACK_FPS
        self._gpu_available: bool = False
        self._gpu_enabled: bool = False
        self._annotations: dict[int, dict] = {}
        self._confidence_threshold: float = 0.0
        self._playing: bool = False
        self._selected_ann_idx: int | None = None

        # Holds QLabel widgets for each metadata value cell
        self._meta_values: dict[str, QLabel] = {}

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timer_tick)

        self._detect_gpu()
        self._build_ui()

    # ------------------------------------------------------------------ #
    # GPU detection                                                        #
    # ------------------------------------------------------------------ #

    def _detect_gpu(self) -> None:
        """Auto-detect OpenCV CUDA support and set :attr:`_gpu_available`."""
        if not _CV2_AVAILABLE:
            self._gpu_available = False
            return
        try:
            count = cv2.cuda.getCudaEnabledDeviceCount()
            self._gpu_available = count > 0
            self._gpu_enabled = self._gpu_available
        except AttributeError:
            self._gpu_available = False
            self._gpu_enabled = False

    # ------------------------------------------------------------------ #
    # UI construction                                                      #
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        """Construct all child widgets and wire signals/slots."""
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        # --- Player toolbar (actions added by VideoAnnotationMixin) ---
        self._player_toolbar = QToolBar()
        self._player_toolbar.setMovable(False)
        self._player_toolbar.setIconSize(self._player_toolbar.iconSize())
        root.addWidget(self._player_toolbar)

        # --- Video display ---
        self._video_label = QLabel("No video loaded")
        self._video_label.setAlignment(Qt.AlignmentFlag(132))   # AlignCenter
        self._video_label.setMinimumSize(320, 240)
        self._video_label.setSizePolicy(
            QSizePolicy.Policy(7), QSizePolicy.Policy(7))        # Expanding
        self._video_label.setStyleSheet("background: #111;")
        root.addWidget(self._video_label)

        # --- Status bar (GPU indicator + frame info) ---
        status_bar = QHBoxLayout()

        self._gpu_label = QLabel(self._gpu_status_text())
        self._gpu_label.setStyleSheet(self._gpu_label_style())
        status_bar.addWidget(self._gpu_label)

        self._gpu_checkbox = QCheckBox("GPU decode")
        self._gpu_checkbox.setChecked(self._gpu_enabled)
        self._gpu_checkbox.setEnabled(self._gpu_available)
        self._gpu_checkbox.stateChanged.connect(self._on_gpu_checkbox)
        status_bar.addWidget(self._gpu_checkbox)

        status_bar.addStretch()

        self._frame_info_label = QLabel("Frame: —")
        status_bar.addWidget(self._frame_info_label)
        root.addLayout(status_bar)

        # --- Frame slider ---
        self._slider = QSlider(Qt.Orientation(1))   # Horizontal
        self._slider.setMinimum(0)
        self._slider.setMaximum(0)
        self._slider.valueChanged.connect(self._on_slider_changed)
        root.addWidget(self._slider)

        # --- Playback controls ---
        controls = QHBoxLayout()

        self._btn_prev = QToolButton()
        self._btn_prev.setText("◀◀")
        self._btn_prev.setToolTip("Step back one frame")
        self._btn_prev.clicked.connect(self.step_backward)
        controls.addWidget(self._btn_prev)

        self._btn_play = QPushButton("▶  Play")
        self._btn_play.setCheckable(True)
        self._btn_play.toggled.connect(self._on_play_toggled)
        controls.addWidget(self._btn_play)

        self._btn_next = QToolButton()
        self._btn_next.setText("▶▶")
        self._btn_next.setToolTip("Step forward one frame")
        self._btn_next.clicked.connect(self.step_forward)
        controls.addWidget(self._btn_next)

        controls.addStretch()

        controls.addWidget(QLabel("Speed:"))
        self._speed_spinbox = QDoubleSpinBox()
        self._speed_spinbox.setRange(0.5, 10.0)
        self._speed_spinbox.setSingleStep(0.5)
        self._speed_spinbox.setValue(1.0)
        self._speed_spinbox.setDecimals(1)
        self._speed_spinbox.setSuffix("×")
        self._speed_spinbox.setFixedWidth(64)
        self._speed_spinbox.setToolTip("Playback speed multiplier")
        self._speed_spinbox.valueChanged.connect(self._on_speed_changed)
        controls.addWidget(self._speed_spinbox)

        controls.addWidget(QLabel("Frame:"))
        self._frame_spinbox = QSpinBox()
        self._frame_spinbox.setMinimum(0)
        self._frame_spinbox.setMaximum(0)
        self._frame_spinbox.valueChanged.connect(self._on_spinbox_changed)
        controls.addWidget(self._frame_spinbox)

        root.addLayout(controls)

        # --- Metadata panel ---
        root.addWidget(self._build_metadata_panel())

        # --- Geo-link row (checkbox + zoom spinbox) ---
        geo_row = QHBoxLayout()

        self._geo_link_checkbox = QCheckBox("Geo-link to map canvas")
        self._geo_link_checkbox.setChecked(False)
        self._geo_link_checkbox.setToolTip(
            "Zoom the map canvas to the GPS position of the current frame")
        self._geo_link_checkbox.toggled.connect(self.geo_link_toggled)
        geo_row.addWidget(self._geo_link_checkbox)

        geo_row.addStretch()

        geo_row.addWidget(QLabel("Zoom level:"))
        self._zoom_spinbox = QSpinBox()
        self._zoom_spinbox.setMinimum(1)
        self._zoom_spinbox.setMaximum(10000)
        self._zoom_spinbox.setValue(50)
        self._zoom_spinbox.setToolTip(
            "Half-extent of the map view in map-unit × 10⁻⁴  (same scale as the image browser range spinner)")
        self._zoom_spinbox.setFixedWidth(70)
        self._zoom_spinbox.valueChanged.connect(self.zoom_changed)
        geo_row.addWidget(self._zoom_spinbox)

        root.addLayout(geo_row)

        # --- Track style controls ---
        root.addWidget(self._build_track_panel())

    def _build_metadata_panel(self) -> QGroupBox:
        """Build the frame-metadata group box and return it."""
        box = QGroupBox("Frame Metadata")
        grid = QGridLayout(box)
        grid.setSpacing(2)
        grid.setContentsMargins(4, 4, 4, 4)

        # Column stretch: label columns are fixed, value columns expand
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

        label_style = "color: #888; font-size: 10px;"
        value_style = "font-size: 10px;"

        for key, display, row, col_pair in _META_FIELDS:
            base_col = col_pair * 2   # 0 or 2

            lbl = QLabel(display + ":")
            lbl.setStyleSheet(label_style)
            lbl.setAlignment(Qt.AlignmentFlag(130))   # AlignRight | AlignVCenter
            grid.addWidget(lbl, row, base_col)

            val = QLabel("—")
            val.setStyleSheet(value_style)
            val.setTextInteractionFlags(Qt.TextInteractionFlag(1))  # TextSelectableByMouse
            grid.addWidget(val, row, base_col + 1)

            self._meta_values[key] = val

        # Comments spans the full width of right half (or whole row if alone)
        # already placed at row 5, col 0-1; extend it across all 4 columns
        if "comments" in self._meta_values:
            # Remove and re-add spanning 4 columns
            val_widget = self._meta_values["comments"]
            grid.removeWidget(val_widget)
            grid.addWidget(val_widget, 5, 1, 1, 3)

        return box

    def _build_track_panel(self) -> QGroupBox:
        """Build the track-style group box and return it."""
        box = QGroupBox("Track")
        row = QHBoxLayout(box)
        row.setSpacing(6)

        self._track_checkbox = QCheckBox("Show on map")
        self._track_checkbox.setChecked(False)
        self._track_checkbox.setToolTip(
            "Add / remove the GPS track line from the QGIS map canvas")
        self._track_checkbox.toggled.connect(self.track_visibility_changed)
        row.addWidget(self._track_checkbox)

        row.addStretch()

        row.addWidget(QLabel("Color:"))
        self._track_color_btn = QgsColorButton()
        self._track_color_btn.setColor(QColor(0, 180, 255))
        self._track_color_btn.setFixedWidth(48)
        self._track_color_btn.setToolTip("Track line colour")
        self._track_color_btn.colorChanged.connect(
            lambda c: self.track_color_changed.emit(c))
        row.addWidget(self._track_color_btn)

        row.addWidget(QLabel("Width:"))
        self._track_width_spin = QDoubleSpinBox()
        self._track_width_spin.setRange(0.1, 10.0)
        self._track_width_spin.setSingleStep(0.1)
        self._track_width_spin.setValue(0.5)
        self._track_width_spin.setDecimals(1)
        self._track_width_spin.setSuffix(" mm")
        self._track_width_spin.setFixedWidth(72)
        self._track_width_spin.setToolTip("Track line width in millimetres")
        self._track_width_spin.valueChanged.connect(
            lambda v: self.track_width_changed.emit(v))
        row.addWidget(self._track_width_spin)

        return box

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def load_video(self, video_path: str) -> bool:
        """Open *video_path* with OpenCV and seek to frame 0.

        Returns ``True`` on success, ``False`` if the file cannot be opened.
        """
        self._stop_playback()
        if self._cap is not None:
            self._cap.release()
            self._cap = None

        if not _CV2_AVAILABLE:
            self._video_label.setText("cv2 not available — cannot load video")
            return False

        backend = cv2.CAP_ANY
        if self._gpu_enabled and self._gpu_available:
            backend = cv2.CAP_CUDA if hasattr(cv2, "CAP_CUDA") else cv2.CAP_ANY

        cap = cv2.VideoCapture(video_path, backend)
        if not cap.isOpened():
            self._video_label.setText(f"Cannot open: {video_path}")
            return False

        self._cap = cap
        self._total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        self._fps = fps if fps > 0 else self._FALLBACK_FPS

        max_frame = max(0, self._total_frames - 1)
        self._slider.setMaximum(max_frame)
        self._frame_spinbox.setMaximum(max_frame)

        self.seek_to_frame(0)
        return True

    def set_annotations(self, annotations: dict[int, dict]) -> None:
        """Replace the annotation data and redraw the current frame."""
        self._annotations = annotations
        self._redraw_current_frame()

    def set_confidence_threshold(self, threshold: float) -> None:
        """Set the minimum confidence for visible annotation boxes."""
        self._confidence_threshold = threshold
        self._redraw_current_frame()

    def set_selected_annotation_idx(self, idx: int | None) -> None:
        """Highlight the annotation at *idx* (original list position) in yellow.

        Pass ``None`` to clear the selection.  When a selection is active the
        frame is rendered with all annotations visible (threshold 0) so that
        the selected box is always shown even when it would otherwise be
        filtered out.
        """
        self._selected_ann_idx = idx
        self._redraw_current_frame()

    def set_gpu_enabled(self, enabled: bool) -> None:
        """Enable or disable GPU decode (no-op when GPU is unavailable)."""
        if not self._gpu_available:
            return
        self._gpu_enabled = enabled
        self._gpu_checkbox.setChecked(enabled)
        self._gpu_label.setText(self._gpu_status_text())
        self._gpu_label.setStyleSheet(self._gpu_label_style())

    def set_geo_link_enabled(self, enabled: bool) -> None:
        """Set the geo-link checkbox state without emitting the signal."""
        self._geo_link_checkbox.blockSignals(True)
        self._geo_link_checkbox.setChecked(enabled)
        self._geo_link_checkbox.blockSignals(False)

    def set_frame_metadata(self, row: dict) -> None:
        """Populate the metadata panel from a frame-position dict.

        Parameters
        ----------
        row:
            Dict returned by :func:`~gt.video_manager.frame_position`.
            Missing keys are shown as ``—``.
        """
        def _fmt(key: str, decimals: int = 6) -> str:
            val = row.get(key)
            if val is None or (isinstance(val, float) and val != val):  # NaN
                return "—"
            if key in ("latitude", "longitude"):
                return f"{float(val):.{decimals}f}°"
            if key in ("depth", "cp_mean_alt"):
                return f"{float(val):.2f} m"
            if key == "timestamp":
                return str(val)[:19]   # trim microseconds
            return str(val).strip() or "—"

        for key, widget in self._meta_values.items():
            widget.setText(_fmt(key))

    def seek_to_frame(self, frame_index: int) -> None:
        """Seek the VideoCapture to *frame_index* and display it."""
        if self._cap is None:
            return
        frame_index = max(0, min(frame_index, self._total_frames - 1))
        self._cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ret, bgr = self._cap.read()
        if not ret:
            return
        self._current_frame = frame_index
        self._display_frame(bgr)
        self._update_controls_silently(frame_index)
        self.frame_changed.emit(frame_index)

    def step_forward(self) -> None:
        """Advance one frame."""
        self.seek_to_frame(self._current_frame + 1)

    def step_backward(self) -> None:
        """Go back one frame."""
        self.seek_to_frame(self._current_frame - 1)

    @property
    def current_frame_index(self) -> int:
        """The index of the currently displayed frame."""
        return self._current_frame

    @property
    def total_frames(self) -> int:
        """Total number of frames reported by the video file."""
        return self._total_frames

    @property
    def geo_link_enabled(self) -> bool:
        """Current state of the geo-link checkbox."""
        return self._geo_link_checkbox.isChecked()

    @property
    def zoom_level(self) -> int:
        """Zoom-level spinbox value (half-extent = value / 10 000 map units)."""
        return self._zoom_spinbox.value()

    @property
    def track_visible(self) -> bool:
        """Whether the 'Show on map' checkbox is checked."""
        return self._track_checkbox.isChecked()

    @property
    def track_color(self) -> QColor:
        """Current track line colour."""
        return self._track_color_btn.color()

    @property
    def track_width(self) -> float:
        """Current track line width in millimetres."""
        return self._track_width_spin.value()

    @property
    def player_toolbar(self) -> QToolBar:
        """Toolbar embedded at the top of the video player widget."""
        return self._player_toolbar

    @property
    def frame_width(self) -> int:
        """Original video frame width in pixels (0 when no video is loaded)."""
        if self._cap is None:
            return 0
        return int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))

    @property
    def frame_height(self) -> int:
        """Original video frame height in pixels (0 when no video is loaded)."""
        if self._cap is None:
            return 0
        return int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    def cleanup(self) -> None:
        """Release OpenCV resources.  Call before destroying the widget."""
        self._stop_playback()
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _gpu_status_text(self) -> str:
        if not _CV2_AVAILABLE:
            return "cv2 unavailable"
        if self._gpu_available and self._gpu_enabled:
            return "GPU: active"
        if self._gpu_available and not self._gpu_enabled:
            return "GPU: disabled"
        return "GPU: not available"

    def _gpu_label_style(self) -> str:
        if self._gpu_available and self._gpu_enabled:
            return "color: #22cc44; font-weight: bold;"
        if self._gpu_available:
            return "color: #aaaaaa;"
        return "color: #888888;"

    def _display_frame(self, bgr: np.ndarray) -> None:
        """Convert *bgr* to QImage, overlay annotations, paint into label."""
        qimg = _bgr_to_qimage(bgr)
        ann = self._annotations.get(self._current_frame)
        if ann:
            from gt.video_manager import filter_annotations_by_confidence
            if self._selected_ann_idx is not None:
                # Editor active: show all boxes so the selected one is always visible
                filtered = filter_annotations_by_confidence(ann, 0.0)
                qimg = _draw_annotations(qimg, filtered, 0.0, self._selected_ann_idx)
            else:
                filtered = filter_annotations_by_confidence(ann, self._confidence_threshold)
                if filtered:
                    qimg = _draw_annotations(qimg, filtered, self._confidence_threshold)
        pixmap_size = self._video_label.size()
        pixmap = QPixmap.fromImage(qimg).scaled(
            pixmap_size,
            Qt.AspectRatioMode(1),     # KeepAspectRatio
            Qt.TransformationMode(0),  # FastTransformation
        )
        self._video_label.setPixmap(pixmap)
        self._frame_info_label.setText(
            f"Frame: {self._current_frame} / {self._total_frames - 1}")

    def _redraw_current_frame(self) -> None:
        """Re-read and re-display the current frame."""
        if self._cap is None:
            return
        self._cap.set(cv2.CAP_PROP_POS_FRAMES, self._current_frame)
        ret, bgr = self._cap.read()
        if ret:
            self._display_frame(bgr)

    def _update_controls_silently(self, frame_index: int) -> None:
        """Update slider and spinbox without triggering their valueChanged signals."""
        self._slider.blockSignals(True)
        self._frame_spinbox.blockSignals(True)
        self._slider.setValue(frame_index)
        self._frame_spinbox.setValue(frame_index)
        self._slider.blockSignals(False)
        self._frame_spinbox.blockSignals(False)

    def _stop_playback(self) -> None:
        self._timer.stop()
        self._playing = False
        self._btn_play.blockSignals(True)
        self._btn_play.setChecked(False)
        self._btn_play.setText("▶  Play")
        self._btn_play.blockSignals(False)

    # ------------------------------------------------------------------ #
    # Slots                                                                #
    # ------------------------------------------------------------------ #

    def _timer_interval(self) -> int:
        """Return the QTimer interval in ms for the current fps × speed."""
        speed = self._speed_spinbox.value() if hasattr(self, "_speed_spinbox") else 1.0
        return max(self._MIN_INTERVAL_MS, int(1000 / (self._fps * speed)))

    def _on_play_toggled(self, checked: bool) -> None:
        if checked:
            self._playing = True
            self._btn_play.setText("⏸  Pause")
            self._timer.start(self._timer_interval())
        else:
            self._stop_playback()

    def _on_speed_changed(self, _value: float) -> None:
        """Adjust the timer interval immediately if playback is active."""
        if self._playing:
            self._timer.start(self._timer_interval())

    def _on_timer_tick(self) -> None:
        if self._cap is None or self._current_frame >= self._total_frames - 1:
            self._stop_playback()
            return
        ret, bgr = self._cap.read()
        if not ret:
            self._stop_playback()
            return
        self._current_frame += 1
        self._display_frame(bgr)
        self._update_controls_silently(self._current_frame)
        self.frame_changed.emit(self._current_frame)

    def _on_slider_changed(self, value: int) -> None:
        if value != self._current_frame:
            self.seek_to_frame(value)

    def _on_spinbox_changed(self, value: int) -> None:
        if value != self._current_frame:
            self.seek_to_frame(value)

    def _on_gpu_checkbox(self, state: int) -> None:
        self._gpu_enabled = bool(state)
        self._gpu_label.setText(self._gpu_status_text())
        self._gpu_label.setStyleSheet(self._gpu_label_style())
        # Change takes effect on the next load_video() call — VideoCapture
        # does not expose its source path, so we cannot cheaply reopen here.
