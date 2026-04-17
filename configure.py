""" Configuration loading, validation, and settings dialog for GroundTruther. """
import os
import traceback
from pathlib import Path

import yaml
from starlette.templating import Jinja2Templates

try:
    from pydantic.error_wrappers import ValidationError  # pydantic v1
except ImportError:
    from pydantic import ValidationError  # pydantic v2
from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtWidgets import QDialog, QFileDialog, QMessageBox

from groundtruther.pygui.app_settings_gui import AppSettings
from groundtruther.config_model import HabcamSettings
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


def validate_config(settings):
    """Validate *settings* against the Pydantic model.

    Returns a ``(is_valid: bool, error_message: str)`` tuple.
    Never shows any dialog – the caller decides how to present errors.
    """
    if not settings:
        return False, "No settings provided"
    try:
        # Video fields are all Optional[str] — nothing to validate pydantically.
        # Passing them to HabcamSettings triggers a pydantic v1 bug where a
        # field named "Video" with type Optional[VideoSettings] silently fails
        # coercion and reports "value is not None".  Validate only the fields
        # that have real constraints (paths, URLs, booleans).
        HabcamSettings(
            Mbes={"soundings": settings["Mbes"]["soundings"]},
            HabCam={
                "imagepath": settings["HabCam"]["imagepath"],
                "imagemetadata": settings["HabCam"]["imagemetadata"],
                "imageannotation": settings["HabCam"]["imageannotation"],
            },
            Export={"kmldir": settings["Export"]["kmldir"]},
            Processing={
                "gpu_avaibility": settings["Processing"]["gpu_avaibility"],
                "grass_api_endpoint": settings["Processing"]["grass_api_endpoint"],
            },
            Filesystem={"filemanager": settings["Filesystem"].get("filemanager") or None},
        )
        return True, ""
    except ValidationError as exc:
        lines = [
            f"  {'.'.join(str(l) for l in err['loc'])}: {err['msg']}"
            for err in exc.errors()
        ]
        return False, "Invalid settings:\n" + "\n".join(lines)
    except KeyError as exc:
        return False, f"Missing required config key: {exc}"


def get_settings(config_path):
    """Load *and* validate the config file at *config_path*.

    Returns the settings dict when valid, or ``None`` otherwise.
    Never shows any dialog – callers are responsible for user feedback.
    """
    settings = load_config(config_path)
    is_valid, _ = validate_config(settings)
    return settings if is_valid else None


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

        templates_path = Path(self.root_dir) / "config" / "templates"
        self.templates = Jinja2Templates(directory=str(templates_path))

        # Wire buttons
        self.select_image_path.clicked.connect(self.set_image_path)
        self.select_metadata_path.clicked.connect(self.set_metadata_path)
        self.select_imageannotation_path.clicked.connect(self.set_imageannotation_path)
        self.select_mbes_path.clicked.connect(self.set_mbes_path)
        self.select_kml_path.clicked.connect(self.set_kml_path)
        self.select_video_path.clicked.connect(self.set_video_path)
        self.select_video_metadata_path.clicked.connect(self.set_video_metadata_path)
        self.gpu_avaibility.currentIndexChanged.connect(self._on_gpu_index_changed)
        self.setOption.clicked.connect(self.write_config)
        self.quit.clicked.connect(self.close)

        # Populate fields from disk – silently, no validation dialogs
        self._populate_fields()

        # GPU toggle disabled until RAPIDS detection is implemented
        self.gpu_avaibility.setEnabled(False)
        self.vrt_label.hide()
        self.vrt_path.hide()
        self.select_vrt_path.hide()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _populate_fields(self):
        """Read the current config file and fill in the form fields.

        Uses ``load_config`` (no validation) so that a config with invalid
        paths can still be displayed and corrected by the user.
        """
        settings = load_config(self.config) or {}

        fs = settings.get("Filesystem", {})
        hbc = settings.get("HabCam", {})
        mbes = settings.get("Mbes", {})
        export = settings.get("Export", {})
        proc = settings.get("Processing", {})

        video = settings.get("Video", {}) or {}

        self.filemanager.setText(fs.get("filemanager", ""))
        self.image_path.setText(hbc.get("imagepath", ""))
        self.metadata_path.setText(hbc.get("imagemetadata", ""))
        self.imageannotation_path.setText(hbc.get("imageannotation", ""))
        self.mbes_path.setText(mbes.get("soundings", ""))
        self.kml_path.setText(export.get("kmldir", ""))

        gpu = proc.get("gpu_avaibility", False)
        self.gpu_avaibility_value = bool(gpu)
        self.gpu_avaibility.setCurrentText("Enabled" if gpu else "Disabled")
        self.grass_api_endpoint.setText(proc.get("grass_api_endpoint", ""))

        # Video fields (widgets are now always present via Ui_app_settings_ui)
        self.video_path.setText(video.get("videofile", ""))
        self.video_metadata_path.setText(video.get("videometadata", ""))

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
            "Mbes": {"soundings": _opt(self.mbes_path.text())},
            "Export": {"kmldir": _opt(self.kml_path.text())},
            "Processing": {
                "gpu_avaibility": self.gpu_avaibility_value,
                "grass_api_endpoint": _opt(self.grass_api_endpoint.text()),
            },
            "Video": {
                "videofile": _opt(self.video_path.text()),
                "videometadata": _opt(self.video_metadata_path.text()),
                "videoannotation": None,
            },
        }

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def write_config(self):
        """Validate the form and write the config file.

        Shows an error dialog if validation fails.  On success writes the
        YAML file, emits ``settings_saved``, and closes the dialog.
        """
        gui_settings = self.get_gui_settings()
        is_valid, err_msg = validate_config(gui_settings)
        if not is_valid:
            error_message(f"Cannot save – please fix the following:\n\n{err_msg}")
            return

        hbc_config = self.templates.get_template("config_template.yaml").render({
            "filemanager": self.filemanager.text(),
            "imagepath": self.image_path.text(),
            "imagemetadata": self.metadata_path.text(),
            "imageannotation": self.imageannotation_path.text(),
            "soundings": self.mbes_path.text(),
            "kmldir": self.kml_path.text(),
            "gpu_avaibility": self.gpu_avaibility_value,
            "grass_api_endpoint": self.grass_api_endpoint.text(),
            "videofile": self.video_path.text(),
            "videometadata": self.video_metadata_path.text(),
            "videoannotation": "",
        })
        with open(self.config, "w+", encoding="utf8") as yaml_file:
            yaml_file.write(hbc_config)

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
