""" Configuration loading, validation, and settings dialog for GroundTruther. """
import os
import traceback

import yaml

from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtWidgets import (
    QDialog, QFileDialog, QMessageBox,
    QCheckBox, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QSpinBox, QToolButton, QVBoxLayout,
)

from groundtruther.pygui.app_settings_gui import AppSettings
from groundtruther.gt import config_check
from groundtruther.gt.config_check import merge_settings, write_settings
from groundtruther.config.config import config as DEFAULT_CONFIG_PATH
import groundtruther.resources_rc  # noqa: F401 – registers Qt resources

root_dir = os.path.dirname(__file__)


# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------

def log_exception(context: str, exc: BaseException, warn: bool = False) -> None:
    """Log *exc* with its full traceback to the QGIS message log.

    Parameters
    ----------
    context:
        Short description of where the error occurred, e.g.
        ``"_apply_settings: reading parquet"``.
    exc:
        The caught exception instance.
    warn:
        If ``True``, log at ``Qgis.Warning`` (expected/recoverable errors
        such as a missing config file or network timeout).  Otherwise logs
        at ``Qgis.Critical`` for unexpected failures.
    """
    try:
        from qgis.core import Qgis, QgsMessageLog
        level = Qgis.Warning if warn else Qgis.Critical
    except ImportError:
        # Running outside QGIS (e.g. unit tests) – fall back to stdlib
        import logging
        logging.exception(context)
        return

    QgsMessageLog.logMessage(
        f"{context}: {type(exc).__name__}: {exc}\n{traceback.format_exc()}",
        'GroundTruther',
        level,
    )


# ---------------------------------------------------------------------------
# Low-level helpers – no GUI side-effects
# ---------------------------------------------------------------------------

def load_config(config_path):
    """Load YAML config from *config_path* without any validation.

    Returns the settings dict on success, or ``None`` if the file is missing
    or cannot be parsed.  Never shows any dialog.
    """
    try:
        with open(config_path, "r", encoding="utf8") as fh:
            return yaml.safe_load(fh)
    except FileNotFoundError as exc:
        log_exception(f"load_config({config_path}): file not found", exc, warn=True)
        return None
    except yaml.YAMLError as exc:
        log_exception(f"load_config({config_path}): YAML parse error", exc)
        return None


def check_config(settings):
    """Grade every config key individually – see :mod:`gt.config_check`.

    Returns a ``ConfigReport`` whose ``errors`` block startup and whose
    ``warnings`` disable a single feature each.  Never shows any dialog.
    """
    return config_check.check_settings(settings)


def validate_config(settings):
    """Validate *settings*, key by key.

    Returns a ``(is_valid: bool, error_message: str)`` tuple, kept for the
    callers that only need a yes/no answer (``ConfigDialog.write_config``,
    ``validate_config2``).  "Valid" now means **no errors** – a stale optional
    path yields a warning, not a veto, so one bad key can no longer invalidate
    the whole file.  Use :func:`check_config` when you need the detail.
    """
    if not settings:
        return False, "No settings provided"
    report = check_config(settings)
    if report.ok:
        return True, ""
    return False, "Invalid settings:\n" + report.summary(include_warnings=False)


def get_settings(config_path):
    """Load *and* validate the config file at *config_path*.

    Returns the settings dict when it has no *fatal* problems, or ``None``
    otherwise.  Never shows any dialog – callers are responsible for user
    feedback.  Prefer :func:`get_settings_checked` when you want to degrade
    per feature instead of all-or-nothing.
    """
    settings, report = get_settings_checked(config_path)
    return settings if report.ok else None


def get_settings_checked(config_path):
    """Load the config at *config_path* and grade it.

    Returns ``(settings, report)`` where *settings* is the raw dict as loaded
    (``None`` when the file is missing/unparseable) and *report* is a
    ``ConfigReport``.  Callers that want to keep running on a partly broken
    config pass both to ``config_check.degrade``.
    """
    settings = load_config(config_path)
    return settings, check_config(settings)


# ---------------------------------------------------------------------------
# GUI helper
# ---------------------------------------------------------------------------

def error_message(message):
    """Show a modal error message dialog."""
    alert = QMessageBox()
    alert.setText(message)
    alert.exec()


# ---------------------------------------------------------------------------
# Settings dialog
# ---------------------------------------------------------------------------

class ConfigDialog(QDialog, AppSettings):
    """Dialog for editing the GroundTruther YAML configuration.

    Emits ``settings_saved`` after a valid configuration has been written to
    disk so that other widgets can react without needing a plugin restart.
    """

    settings_saved = pyqtSignal()

    def __init__(self, parent=None):
        # Initialise exactly one base, explicitly. Two traps here, both caught
        # by tests/gui/test_config_dialog.py:
        #   * `super().__init__()` followed by `QDialog.__init__(self, parent)`
        #     (what this used to do) runs the sip constructor twice and orphans
        #     the first C++ object — a segfault at teardown once several
        #     dialogs have been built.
        #   * `super().__init__(parent)` alone is worse: PyQt's cooperative
        #     multiple inheritance walks on to AppSettings.__init__, which
        #     calls setupUi() a *second* time. The attribute references then
        #     point at the newer widget set while the older one is what's
        #     actually shown — a dialog that looks unpopulated and is missing
        #     every programmatically added row.
        QDialog.__init__(self, parent)
        self.setupUi(self)

        self.root_dir = os.path.dirname(__file__)
        self.config = DEFAULT_CONFIG_PATH
        self.gpu_avaibility_value = False

        # Wire buttons
        self.select_image_path.clicked.connect(self.set_image_path)
        self.select_metadata_path.clicked.connect(self.set_metadata_path)
        self.select_imageannotation_path.clicked.connect(self.set_imageannotation_path)
        self.select_mbes_path.clicked.connect(self.set_mbes_path)
        # Add a "Reference surface (GeoTIFF)" row to the MBES box — programmatic
        # so the stale generated .ui is left untouched.
        self._add_reference_surface_row()
        self.select_kml_path.clicked.connect(self.set_kml_path)
        self.select_video_path.clicked.connect(self.set_video_path)
        self.select_video_metadata_path.clicked.connect(self.set_video_metadata_path)
        # The remaining config keys have no widgets in the generated UI, so they
        # are built here (same reason as the reference-surface row above).
        self._add_video_annotation_row()
        self._add_roughness_box()
        self.gpu_avaibility.currentIndexChanged.connect(self._on_gpu_index_changed)
        self.setOption.clicked.connect(self.write_config)
        self.quit.clicked.connect(self.close)
        # Runs last: every section, generated or programmatic, must already exist.
        self._make_sections_collapsible()

        # Repurpose the (otherwise unused) VRT row as the GroundTruther session
        # file picker — avoids regenerating the stale app-settings .ui.
        self.vrt_label.setText("GT session file")
        self.vrt_path.setToolTip(
            "JSON file storing GroundTruther UI/session state "
            "(image index, zoom, query selection, dock layout)")
        self.select_vrt_path.clicked.connect(self.set_session_path)

        # On-theme tinted icons (icon-only): folder picker "…" buttons + the
        # Save / Close actions.
        from groundtruther.mixins.toolbar_icons import iconize
        for name in ("select_image_path", "select_metadata_path",
                     "select_imageannotation_path", "select_mbes_path",
                     "select_kml_path", "select_video_path",
                     "select_video_metadata_path", "select_vrt_path",
                     "select_video_annotation_path"):
            btn = getattr(self, name, None)
            if btn is not None:
                iconize(btn, "folder-open.svg", "Browse…")
        if getattr(self, "setOption", None) is not None:
            iconize(self.setOption, "floppy-disk.svg", "Save settings")
        if getattr(self, "quit", None) is not None:
            iconize(self.quit, "circle-xmark.svg", "Close")

        # Populate fields from disk – silently, no validation dialogs
        self._populate_fields()

        # GPU toggle disabled until RAPIDS detection is implemented
        self.gpu_avaibility.setEnabled(False)

        # The generated UI sizes itself for the sections it knows about; the
        # roughness box roughly doubles the content, so open a bit taller.
        # Everything still lives in the .ui's scroll area.
        self.resize(620, 760)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _populate_fields(self):
        """Read the current config file and fill in the form fields.

        Uses ``load_config`` (no validation) so that a config with invalid
        paths can still be displayed and corrected by the user.
        """
        settings = load_config(self.config) or {}

        fs = settings.get("Filesystem") or {}
        hbc = settings.get("HabCam") or {}
        mbes = settings.get("Mbes") or {}
        export = settings.get("Export") or {}
        proc = settings.get("Processing") or {}

        video = settings.get("Video", {}) or {}

        # ``as_path_str`` (not ``.get(key, "")``) because a key present with an
        # empty YAML value reads back as ``None``, and ``setText(None)`` raises.
        _text = config_check.as_path_str

        self.filemanager.setText(_text(fs.get("filemanager")))
        self.image_path.setText(_text(hbc.get("imagepath")))
        self.metadata_path.setText(_text(hbc.get("imagemetadata")))
        self.imageannotation_path.setText(_text(hbc.get("imageannotation")))
        self.mbes_path.setText(_text(mbes.get("soundings")))
        self.reference_surface_path.setText(_text(mbes.get("reference_surface")))
        self.kml_path.setText(_text(export.get("kmldir")))

        gpu = config_check.as_bool(proc.get("gpu_avaibility"), False)
        self.gpu_avaibility_value = gpu
        self.gpu_avaibility.setCurrentText("Enabled" if gpu else "Disabled")
        self.grass_api_endpoint.setText(_text(proc.get("grass_api_endpoint")))
        self.grass_api_key.setText(_text(proc.get("grass_api_key")))

        # Video fields (widgets are now always present via Ui_app_settings_ui)
        self.video_path.setText(_text(video.get("videofile")))
        self.video_metadata_path.setText(_text(video.get("videometadata")))
        self.video_annotation_path.setText(_text(video.get("videoannotation")))

        session = settings.get("Session", {}) or {}
        self.vrt_path.setText(_text(session.get("groundtruther_project")))

        # Roughness — the defaults here mirror ``config_model.RoughnessSettings``;
        # the coercion helpers mean a junk YAML value shows as the default
        # rather than raising.
        rough = settings.get("Roughness") or {}
        self.roughness_base_url.setText(_text(rough.get("base_url")))
        self.roughness_route.setText(_text(rough.get("route")))
        self.roughness_direct_url.setText(_text(rough.get("direct_url")))
        self.roughness_res_mm.setValue(
            config_check.as_float(rough.get("res_mm"), 0.0))
        self.roughness_n_water.setValue(
            config_check.as_float(rough.get("n_water"), 0.0))
        self.roughness_dem_max_side.setValue(
            config_check.as_int(rough.get("dem_max_side"), 512))
        self.roughness_georeference.setChecked(
            config_check.as_bool(rough.get("georeference"), False))
        self.roughness_epsg.setValue(
            config_check.as_int(rough.get("epsg"), 32619))
        self.roughness_heading_offset.setValue(
            config_check.as_float(rough.get("heading_offset_deg"), 0.0))
        self.roughness_mirror.setChecked(
            config_check.as_bool(rough.get("mirror"), False))
        self.roughness_dem_trim_border.setValue(
            config_check.as_int(rough.get("dem_trim_border"), 2))
        self.roughness_dem_clip_sigma.setValue(
            config_check.as_float(rough.get("dem_clip_sigma"), 5.0))
        self.roughness_dem_erode.setValue(
            config_check.as_int(rough.get("dem_erode"), 1))

    def _on_gpu_index_changed(self, index):
        self.gpu_avaibility_value = self.gpu_avaibility.itemText(index) == "Enabled"

    # ------------------------------------------------------------------
    # File/directory pickers
    # ------------------------------------------------------------------

    def set_image_path(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Set HabCam image directory", self.image_path.text(),
            QFileDialog.Option.DontResolveSymlinks | QFileDialog.Option.ShowDirsOnly,
        )
        if directory:
            self.image_path.setText(directory)

    def set_metadata_path(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Set image metadata file", self.metadata_path.text(),
            "Parquet files (*.parquet);;All files (*)",
        )
        if file_name:
            self.metadata_path.setText(file_name)

    def set_imageannotation_path(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Set image annotation file", self.imageannotation_path.text(),
            "CSV files (*.csv);;All files (*)",
        )
        if file_name:
            self.imageannotation_path.setText(file_name)

    def set_mbes_path(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Set MBES soundings file", self.mbes_path.text(),
            "Parquet files (*.parquet);;All files (*)",
        )
        if file_name:
            self.mbes_path.setText(file_name)


    # ------------------------------------------------------------------ #
    # Collapsible sections                                                #
    # ------------------------------------------------------------------ #

    #: Sections that start collapsed for a first-run user. These are the ones
    #: most installs never touch — the transport defaults are correct and the
    #: mesh knobs are live-tunable on the dock itself. A saved state always
    #: wins over this, so it only affects the very first open.
    _COLLAPSED_BY_DEFAULT = ("filesystem_config_box", "roughness_config_box")

    def _make_sections_collapsible(self):
        """Give every settings section a collapsible header.

        The dialog carries all 27 keys in seven sections and is taller than many
        screens, so it opens scrolled and you hunt for the row you want. Each
        section can now be folded away, and remembers that between sessions.

        Each existing box is **wrapped** rather than converted: the sections come
        from the generated (and stale) app-settings UI, and moving a *widget*
        into another layout is safe where re-parenting its layout is not. The
        inner box is flattened and un-titled so the pair reads as one frame.
        """
        try:
            from qgis.gui import QgsCollapsibleGroupBox
        except Exception as exc:          # noqa: BLE001 - cosmetic only
            log_exception("settings: collapsible sections unavailable", exc, warn=True)
            return

        layout = self.scrollAreaWidgetContents.layout()
        if layout is None:
            return
        # Snapshot first: the loop mutates the layout it walks.
        boxes = []
        for i in range(layout.count()):
            w = layout.itemAt(i).widget()
            if isinstance(w, QGroupBox) and not isinstance(w, QgsCollapsibleGroupBox):
                boxes.append((i, w))

        for index, box in boxes:
            title = box.title()
            name = box.objectName() or f"section_{index}"
            wrapper = QgsCollapsibleGroupBox(title, self.scrollAreaWidgetContents)
            # The objectName is the key QgsCollapsibleGroupBox stores its
            # expanded/collapsed state under — without it nothing persists.
            wrapper.setObjectName(f"gt_section_{name}")
            wrapper.setSaveCollapsedState(True)
            inner = QVBoxLayout(wrapper)
            inner.setContentsMargins(0, 0, 0, 0)
            box.setTitle("")              # the wrapper shows it now
            box.setFlat(True)             # ... so drop the duplicate frame
            inner.addWidget(box)          # reparents `box` off the old layout
            layout.insertWidget(index, wrapper)
            if name in self._COLLAPSED_BY_DEFAULT:
                wrapper.setCollapsed(True)

    def _add_video_annotation_row(self):
        """Append the 'Annotations' row to the Video group box.

        ``Video.videoannotation`` is the last config key the generated UI never
        got a widget for; without one it could only be hand-edited in YAML.
        """
        self.video_annotation_path = QLineEdit()
        self.video_annotation_path.setToolTip(
            "CSV mapping frame indices to bounding-box annotations "
            "(columns: frame_index, bboxes, species, confidences).")
        self.select_video_annotation_path = QToolButton()
        self.select_video_annotation_path.setText("...")
        self.select_video_annotation_path.clicked.connect(
            self.set_video_annotation_path)
        row = QHBoxLayout()
        row.addWidget(QLabel("Annotations"))
        row.addWidget(self.video_annotation_path)
        row.addWidget(self.select_video_annotation_path)
        self.video_config_box.layout().addLayout(row)

    def _add_roughness_box(self):
        """Build the 'Seafloor roughness' group box (all ``Roughness.*`` keys).

        Inserted after the Video box, before the trailing spacer + buttons.
        These 13 keys previously existed only in YAML — and before the
        merge-based save they were silently deleted on every save (see
        ``PLANNING/config-validation-hardening.md``).
        """
        # Imported lazily: gt.roughness_client imports configure.log_exception,
        # so a module-level import here is a circular import.
        from groundtruther.gt.roughness_client import DEFAULT_ROUTE

        box = QGroupBox("Seafloor roughness")
        box.setObjectName("roughness_config_box")
        outer = QVBoxLayout(box)

        # --- service / transport ---
        service = QGroupBox("Service")
        form = QFormLayout(service)
        self.roughness_base_url = QLineEdit()
        self.roughness_base_url.setPlaceholderText(
            "(empty → use the GRASS API endpoint above)")
        self.roughness_base_url.setToolTip(
            "FastGIS base URL for the roughness route. Leave empty to reuse "
            "Processing.grass_api_endpoint and its API key.")
        form.addRow("Base URL", self.roughness_base_url)

        self.roughness_route = QLineEdit()
        self.roughness_route.setPlaceholderText(
            f"(empty → {DEFAULT_ROUTE})")
        self.roughness_route.setToolTip(
            "Route path appended to the base URL.")
        form.addRow("Route", self.roughness_route)

        self.roughness_direct_url = QLineEdit()
        self.roughness_direct_url.setPlaceholderText(
            "(empty → go through FastGIS)")
        self.roughness_direct_url.setToolTip(
            "On-host GPU service URL, e.g. http://127.0.0.1:7871/roughness. "
            "When set, GroundTruther POSTs here directly with no auth, "
            "skipping FastGIS — only useful when running on the GPU host.")
        form.addRow("Direct URL", self.roughness_direct_url)
        outer.addWidget(service)

        # --- computation knobs (0 = let the service decide) ---
        compute = QGroupBox("Computation")
        form = QFormLayout(compute)
        self.roughness_res_mm = self._make_double_spin(
            0.0, 100.0, 1, 0.5, " mm", special="service default",
            tooltip="DEM resolution requested from the service.")
        form.addRow("Resolution", self.roughness_res_mm)

        self.roughness_n_water = self._make_double_spin(
            0.0, 2.0, 3, 0.001, "", special="service default",
            tooltip="Refractive index of water. Leave at the service default "
                    "— the 2015 HabCam calibration is already in-water.")
        form.addRow("n water", self.roughness_n_water)

        self.roughness_dem_max_side = QSpinBox()
        self.roughness_dem_max_side.setRange(64, 4096)
        self.roughness_dem_max_side.setSingleStep(64)
        self.roughness_dem_max_side.setToolTip(
            "Cap on the longest side of the returned micro-DEM grid.")
        form.addRow("DEM max side", self.roughness_dem_max_side)
        outer.addWidget(compute)

        # --- georeferencing ---
        georef = QGroupBox("Georeferencing (defaults for new datasets)")
        georef.setToolTip(
            "The roughness panel's Georef tab saves its own calibration per "
            "dataset (QgsSettings) and that takes precedence — these values "
            "apply to datasets with no saved calibration yet.")
        form = QFormLayout(georef)
        self.roughness_georeference = QCheckBox("Write GeoTIFFs and add them to QGIS")
        form.addRow(self.roughness_georeference)

        self.roughness_epsg = QSpinBox()
        self.roughness_epsg.setRange(1024, 999999)
        self.roughness_epsg.setToolTip("Projected CRS EPSG (32619 = UTM 19N).")
        form.addRow("EPSG", self.roughness_epsg)

        self.roughness_heading_offset = self._make_double_spin(
            -180.0, 180.0, 2, 0.5, " °",
            tooltip="Residual heading fine-tune. The mount is known, so 0 is "
                    "correct out of the box.")
        form.addRow("Heading offset", self.roughness_heading_offset)

        self.roughness_mirror = QCheckBox("Mirror")
        self.roughness_mirror.setToolTip(
            "Escape hatch — enable only if a mosaic comes out "
            "port/starboard-flipped.")
        form.addRow(self.roughness_mirror)
        outer.addWidget(georef)

        # --- 3-D mesh edge-spike mitigation ---
        mesh = QGroupBox("3-D mesh edge-spike mitigation")
        mesh.setToolTip(
            "The stereo DEM is unreliable at the grid border and around "
            "no-data holes. These are the starting values for the live "
            "controls on the Micro-DEM 3D tab.")
        form = QFormLayout(mesh)
        self.roughness_dem_trim_border = QSpinBox()
        self.roughness_dem_trim_border.setRange(0, 10)
        self.roughness_dem_trim_border.setToolTip(
            "Drop N outer rings of the DEM grid.")
        form.addRow("Trim border", self.roughness_dem_trim_border)

        self.roughness_dem_clip_sigma = self._make_double_spin(
            0.0, 20.0, 1, 0.5, "", special="off",
            tooltip="Mask height outliers beyond N robust σ from the median. "
                    "Lower = more aggressive spike removal.")
        form.addRow("Clip σ", self.roughness_dem_clip_sigma)

        self.roughness_dem_erode = QSpinBox()
        self.roughness_dem_erode.setRange(0, 5)
        self.roughness_dem_erode.setToolTip(
            "Peel N rings off every no-data / outlier boundary "
            "(higher = fewer edge spikes, less coverage).")
        form.addRow("Erode", self.roughness_dem_erode)
        outer.addWidget(mesh)

        # Slot it in after the Video box rather than appending, so the trailing
        # spacer and the Save / Close buttons stay at the bottom.
        column = self.video_config_box.parentWidget().layout()
        column.insertWidget(column.indexOf(self.video_config_box) + 1, box)
        self.roughness_config_box = box

    @staticmethod
    def _make_double_spin(minimum, maximum, decimals, step, suffix,
                          special=None, tooltip=None):
        """A configured ``QDoubleSpinBox``.

        *special* labels the minimum value as "not set" (shown instead of the
        number); :meth:`get_gui_settings` maps it back to ``None``.
        """
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(decimals)
        spin.setSingleStep(step)
        if suffix:
            spin.setSuffix(suffix)
        if special is not None:
            spin.setSpecialValueText(special)
        if tooltip:
            spin.setToolTip(tooltip)
        return spin

    @staticmethod
    def _spin_value_or_none(spin):
        """The spin box's value, or ``None`` when it sits on its special value."""
        if spin.specialValueText() and spin.value() == spin.minimum():
            return None
        return spin.value()

    def set_video_annotation_path(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Set video annotation CSV", self.video_annotation_path.text(),
            "CSV files (*.csv);;All files (*)",
        )
        if file_name:
            self.video_annotation_path.setText(file_name)

    def _add_reference_surface_row(self):
        """Append a 'Reference surface (GeoTIFF)' row to the MBES group box."""
        row = QHBoxLayout()
        label = QLabel("Reference surface")
        self.reference_surface_path = QLineEdit()
        self.reference_surface_path.setToolTip(
            "Optional GeoTIFF DEM / bathymetry. When set, the 3-D viewer clips "
            "this raster to the sampling shape instead of gridding the soundings.")
        button = QToolButton(); button.setText("...")
        button.clicked.connect(self.set_reference_surface_path)
        from groundtruther.mixins.toolbar_icons import iconize
        iconize(button, "folder-open.svg", "Browse…")
        row.addWidget(label)
        row.addWidget(self.reference_surface_path)
        row.addWidget(button)
        self.mbes_config_box.layout().addLayout(row)

    def set_reference_surface_path(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Set reference-surface GeoTIFF", self.reference_surface_path.text(),
            "GeoTIFF (*.tif *.tiff);;All files (*)",
        )
        if file_name:
            self.reference_surface_path.setText(file_name)

    def set_kml_path(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Set KML export directory", self.kml_path.text(),
            QFileDialog.Option.DontResolveSymlinks | QFileDialog.Option.ShowDirsOnly,
        )
        if directory:
            self.kml_path.setText(directory)

    def set_vrt_path(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Set VRT export directory", self.vrt_path.text(),
            QFileDialog.Option.DontResolveSymlinks | QFileDialog.Option.ShowDirsOnly,
        )
        if directory:
            self.vrt_path.setText(directory)

    def set_video_path(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Set video file", self.video_path.text(),
            "Video files (*.mp4 *.avi *.mov *.mkv);;All files (*)",
        )
        if file_name:
            self.video_path.setText(file_name)

    def set_video_metadata_path(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Set video metadata CSV", self.video_metadata_path.text(),
            "CSV files (*.csv);;All files (*)",
        )
        if file_name:
            self.video_metadata_path.setText(file_name)

    def set_session_path(self):
        # getSaveFileName so the user can name a not-yet-existing session file.
        file_name, _ = QFileDialog.getSaveFileName(
            self, "Set GroundTruther session file", self.vrt_path.text(),
            "GroundTruther session (*.json);;All files (*)",
        )
        if file_name:
            self.vrt_path.setText(file_name)

    # ------------------------------------------------------------------
    # Settings read-back
    # ------------------------------------------------------------------

    def get_gui_settings(self):
        """Return a settings dict built from the current form field values.

        Covers every key in ``config_model.HabcamSettings``; ``write_config``
        still merges it into the document on disk, so an unknown section a
        future version adds is preserved rather than dropped.
        """
        def _opt(text):
            """Return None for empty/whitespace strings, else the stripped text."""
            return text.strip() or None

        return {
            "Filesystem": {"filemanager": _opt(self.filemanager.text())},
            "HabCam": {
                "imagepath": self.image_path.text().strip(),
                "imagemetadata": self.metadata_path.text().strip(),
                "imageannotation": _opt(self.imageannotation_path.text()),
            },
            "Mbes": {
                "soundings": _opt(self.mbes_path.text()),
                "reference_surface": _opt(self.reference_surface_path.text()),
            },
            "Export": {"kmldir": _opt(self.kml_path.text())},
            "Processing": {
                "gpu_avaibility": self.gpu_avaibility_value,
                "grass_api_endpoint": _opt(self.grass_api_endpoint.text()),
                "grass_api_key": _opt(self.grass_api_key.text()),
            },
            "Video": {
                "videofile": _opt(self.video_path.text()),
                "videometadata": _opt(self.video_metadata_path.text()),
                "videoannotation": _opt(self.video_annotation_path.text()),
            },
            "Session": {
                "groundtruther_project": _opt(self.vrt_path.text()),
            },
            "Roughness": {
                "base_url": _opt(self.roughness_base_url.text()),
                "route": _opt(self.roughness_route.text()),
                "direct_url": _opt(self.roughness_direct_url.text()),
                # None = "let the service decide" (the spin box's special value)
                "res_mm": self._spin_value_or_none(self.roughness_res_mm),
                "n_water": self._spin_value_or_none(self.roughness_n_water),
                "dem_max_side": self.roughness_dem_max_side.value(),
                "georeference": self.roughness_georeference.isChecked(),
                "epsg": self.roughness_epsg.value(),
                "heading_offset_deg": self.roughness_heading_offset.value(),
                "mirror": self.roughness_mirror.isChecked(),
                "dem_trim_border": self.roughness_dem_trim_border.value(),
                "dem_clip_sigma": self.roughness_dem_clip_sigma.value(),
                "dem_erode": self.roughness_dem_erode.value(),
            },
        }

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def write_config(self):
        """Validate the form and write the config file.

        Shows an error dialog if validation fails.  On success writes the
        YAML file, emits ``settings_saved``, and closes the dialog.

        The dialog only knows a subset of the config, so the new values are
        **merged into the document on disk** rather than re-rendered from a
        fixed template — that is what keeps hand-edited sections the dialog has
        no widgets for (``Roughness``, and any future section) from being
        silently deleted on every save.
        """
        gui_settings = self.get_gui_settings()
        is_valid, err_msg = validate_config(gui_settings)
        if not is_valid:
            error_message(f"Cannot save – please fix the following:\n\n{err_msg}")
            return

        merged = merge_settings(load_config(self.config), gui_settings)
        try:
            write_settings(self.config, merged)
        except OSError as exc:
            log_exception(f"write_config: writing {self.config}", exc)
            error_message(f"Could not write {self.config}:\n{exc}")
            return

        self.settings_saved.emit()
        self.close()


# ---------------------------------------------------------------------------
# Backward-compatibility shims
# ---------------------------------------------------------------------------

def validate_config2(settings, get_bad_keys=False):
    """Deprecated shim – use ``validate_config()`` instead.

    Returns ``True``/``False`` for valid/invalid settings.
    No longer shows any error dialog.
    """
    is_valid, _ = validate_config(settings)
    return is_valid


def get_settings2(config_path):
    """Deprecated shim – use ``load_config()`` instead."""
    return load_config(config_path)


def show_dialog():
    """Show a standalone configuration dialog (used outside the plugin)."""
    dialog = ConfigDialog()
    dialog.exec()
