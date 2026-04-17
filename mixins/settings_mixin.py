"""Settings mixin: configuration loading and dialog management."""
import os
from pathlib import Path

from qgis.core import Qgis, QgsMessageLog

from groundtruther.configure import get_settings, ConfigDialog, error_message, log_exception
from groundtruther.ioutils import parse_annotation
from groundtruther.gt import image_manager as img_mgr


class SettingsMixin:
    """Handles configuration loading, validation, and the settings dialog."""

    def _apply_settings(self):
        """Load settings from disk and refresh all data-dependent state.

        Safe to call at any time.  On success updates paths, reloads metadata,
        and rebuilds the KDTree.  If the metadata file is missing, logs a
        warning and shows a status-bar hint — no modal dialog is shown.
        The dialog is only ever opened explicitly by the user via the gear icon.
        """
        fresh = get_settings(self.config)
        if fresh:
            self.settings = fresh

        if not self.settings:
            return

        new_dirname = self.settings["HabCam"]["imagepath"]
        if new_dirname != self.dirname:
            # Image directory changed — discard cached decoded arrays.
            self._clear_image_cache()
        self.dirname = new_dirname
        self.metadatafile = self.settings["HabCam"]["imagemetadata"]
        self.imageannotationfile = self.settings["HabCam"]["imageannotation"]
        self.grass_api_endpoint = self.settings["Processing"]["grass_api_endpoint"]

        if not Path(self.metadatafile).is_file():
            QgsMessageLog.logMessage(
                f"_apply_settings: metadata file not found: {self.metadatafile!r} "
                "— open Settings to configure the correct path.",
                'GroundTruther', Qgis.Warning,
            )
            if hasattr(self, 'w'):
                self.w.statusbar.showMessage(
                    "Metadata file not found — open Settings (gear icon) to configure."
                )
            return

        try:
            self.imageMetadata = img_mgr.load_metadata(self.metadatafile)
            total = len(self.imageMetadata)
            self.w.ImageIndexspinBox.setMaximum(total - 1)
            self.w.ImageIndexSlider.setMaximum(total - 1)
            if hasattr(self, '_image_counter_label'):
                self._image_counter_label.setText(f"0 / {total - 1}")

            if os.getenv("HBC_DEBUG") == "VERBOSE":
                QgsMessageLog.logMessage(
                    f"image metadata columns: {self.imageMetadata.columns.tolist()}",
                    'GroundTruther', Qgis.Info,
                )

            self.imagemetadata_gui.metadata_scroll_area.setEnabled(True)

            if Path(self.imageannotationfile).is_file():
                QgsMessageLog.logMessage(
                    "Annotation file loaded", 'GroundTruther', Qgis.Info)
                self.w.actionAnnotation.setEnabled(True)
                annotations_by_image = parse_annotation(self.imageannotationfile)
                self.imageMetadata = img_mgr.attach_annotations(
                    self.imageMetadata, annotations_by_image
                )
                self._refresh_known_labels()
            else:
                self.w.actionAnnotation.setEnabled(False)

            self.kdt = img_mgr.build_kdtree(self.imageMetadata)
            self._build_metadata_panel()

        except OSError as exc:
            log_exception(
                f"_apply_settings: OS error reading {self.metadatafile}", exc, warn=True)
        except Exception as exc:
            log_exception(
                f"_apply_settings: failed to load {self.metadatafile}", exc)
            error_message(f"Error reading {self.metadatafile}:\n{exc}")
            self.imageMetadata = None

    def show_dialog(self):
        """Open the config dialog and apply settings when the user saves.

        Creates a fresh ``ConfigDialog`` each time so the form always reflects
        the current on-disk config.  Connects ``settings_saved`` so that
        applying new settings happens automatically without a plugin restart.
        """
        dialog = ConfigDialog()
        dialog.settings_saved.connect(self._apply_settings)
        dialog.settings_saved.connect(self._apply_video_settings)
        dialog.exec()

    def _open_config_dialog(self):
        """Open the config dialog without connecting to ``_apply_settings``.

        Used during ``__init__`` before the UI is fully constructed.
        The caller is responsible for re-reading settings afterwards.
        """
        dialog = ConfigDialog()
        dialog.exec()
