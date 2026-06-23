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

            # Put the image lookup on the calibrated USBL fix (Xutm+dx/Yutm+dy)
            # so map-click → nearest image agrees with the red marker, the
            # sampling-shape centre, and the roughness raster. Falls back to the
            # habcam_lon/lat model if the USBL nav columns are unavailable.
            self._attach_usbl_lonlat()
            lon_col, lat_col = (
                ("usbl_lon", "usbl_lat")
                if "usbl_lon" in self.imageMetadata.columns
                else ("habcam_lon", "habcam_lat"))
            self.kdt = img_mgr.build_kdtree(
                self.imageMetadata, lon_col=lon_col, lat_col=lat_col)
            self._build_metadata_panel()

        except OSError as exc:
            log_exception(
                f"_apply_settings: OS error reading {self.metadatafile}", exc, warn=True)
        except Exception as exc:
            log_exception(
                f"_apply_settings: failed to load {self.metadatafile}", exc)
            error_message(f"Error reading {self.metadatafile}:\n{exc}")
            self.imageMetadata = None

    def _attach_usbl_lonlat(self) -> None:
        """Add ``usbl_lon``/``usbl_lat`` columns = WGS-84 of the USBL fix.

        The calibrated USBL seafloor position is ``Xutm + dx`` / ``Yutm + dy`` in
        the survey CRS (``Roughness.epsg``, default 32619); projected to WGS-84
        here so the KDTree image lookup and the red marker share one position
        with the geo request.  Best-effort: any failure leaves the columns absent
        and the caller falls back to ``habcam_lon``/``habcam_lat``.
        """
        try:
            import numpy as np
            from osgeo import osr
            from groundtruther.gt import roughness_geo
            east, north = roughness_geo.usbl_xy(self.imageMetadata)
            if east is None:
                return
            try:
                epsg = int(((self.settings.get("Roughness") or {}).get("epsg"))
                           or 32619)
            except Exception:  # noqa: BLE001
                epsg = 32619
            # Batched transform (one C++ call) — avoids a per-row Python loop.
            src = osr.SpatialReference()
            src.ImportFromEPSG(epsg)
            dst = osr.SpatialReference()
            dst.ImportFromEPSG(4326)
            try:                       # GDAL ≥3 defaults to authority axis order
                src.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
                dst.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
            except Exception:  # noqa: BLE001 — older GDAL
                pass
            ct = osr.CoordinateTransformation(src, dst)
            pts = np.asarray(ct.TransformPoints(
                np.column_stack([east, north]).tolist()))   # (N, 3): lon, lat, z
            self.imageMetadata["usbl_lon"] = pts[:, 0]
            self.imageMetadata["usbl_lat"] = pts[:, 1]
        except Exception as exc:  # noqa: BLE001 — degrade to the model position
            log_exception("_attach_usbl_lonlat", exc, warn=True)

    def show_dialog(self):
        """Open the config dialog and apply settings when the user saves.

        Creates a fresh ``ConfigDialog`` each time so the form always reflects
        the current on-disk config.  Connects ``settings_saved`` so that
        applying new settings happens automatically without a plugin restart.
        """
        dialog = ConfigDialog()
        dialog.settings_saved.connect(self._apply_settings)
        # Re-evaluate cloud-service availability after settings change (so adding
        # the FastGIS endpoint + key re-enables GRASS / roughness without a
        # restart). Runs after _apply_settings, which reloads self.settings.
        if hasattr(self, "_apply_cloud_availability"):
            dialog.settings_saved.connect(self._apply_cloud_availability)
        dialog.settings_saved.connect(self._apply_video_settings)
        # Let the query builder pick up changed data sources (soundings,
        # reference-surface GeoTIFF, …) without a plugin restart.
        if getattr(self, "querybuilder", None) is not None:
            dialog.settings_saved.connect(self.querybuilder.refresh_settings)
        dialog.exec()

    def _open_config_dialog(self):
        """Open the config dialog without connecting to ``_apply_settings``.

        Used during ``__init__`` before the UI is fully constructed.
        The caller is responsible for re-reading settings afterwards.
        """
        dialog = ConfigDialog()
        dialog.exec()
