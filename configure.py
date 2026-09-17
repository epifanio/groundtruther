""" Configuration loading, validation, and settings dialog for GroundTruther. """
import os
import traceback

import yaml

from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtWidgets import (
    QDialog, QFileDialog, QMessageBox,
    QHBoxLayout, QLabel, QLineEdit, QToolButton,
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
        super().__init__()
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
        self.gpu_avaibility.currentIndexChanged.connect(self._on_gpu_index_changed)
        self.setOption.clicked.connect(self.write_config)
        self.quit.clicked.connect(self.close)

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
                     "select_video_metadata_path", "select_vrt_path"):
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

        session = settings.get("Session", {}) or {}
        self.vrt_path.setText(_text(session.get("groundtruther_project")))

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
        """Return a settings dict built from the current form field values."""
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
            # No "videoannotation" key — the dialog has no widget for it, and
            # write_config merges this dict into the file on disk, so omitting
            # it preserves whatever the user hand-edited there.
            "Video": {
                "videofile": _opt(self.video_path.text()),
                "videometadata": _opt(self.video_metadata_path.text()),
            },
            "Session": {
                "groundtruther_project": _opt(self.vrt_path.text()),
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
