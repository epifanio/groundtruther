"""GRASS GIS integration mixin."""
from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QColor
from qgis.utils import iface
from qgis.core import (
    Qgis, QgsMessageLog, QgsMapLayerType,
    QgsPointXY, QgsGeometry, QgsWkbTypes,
    QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject,
    QgsVectorFileWriter,
)
from qgis.gui import QgsRubberBand

from groundtruther.configure import error_message, log_exception
from groundtruther.ioutils import get_layer_info, convert_to_geojson_using_gdal
from groundtruther.pygui.grass_mdi_gui import GrassTools
from groundtruther.gt import grass_api
from groundtruther.gt.grass_api import GrassApiError


class GrassIntegrationMixin:
    """Manages GRASS GIS connectivity, region setting, and map tools."""

    def _init_grass(self):
        """Create GRASS widgets and wire toolbar actions."""
        self.init_grass_ui()
        self.init_grass_toolbar()

    # ------------------------------------------------------------------ #
    # Setup                                                                #
    # ------------------------------------------------------------------ #

    def init_grass_ui(self):
        self.grassWidgetContents = GrassTools(self)
        self.grassWidgetContents.setObjectName("grassDockWidgetContents")
        self.w.gisToolSplitter.insertWidget(0, self.grassWidgetContents)

    def init_grass_toolbar(self):
        self.w.actiongrass_settings.triggered.connect(self.show_grass_dialog)

    def show_grass_dialog(self):
        self.grass_dialog.exec()
        QgsMessageLog.logMessage(
            f"GRASS dialog closed, grassenabled={self.grass_dialog.grassenabled}",
            'GroundTruther', Qgis.Info)
        if self.grass_dialog.grassenabled:
            self.init_grass_contextual_menu()

    def init_grass_contextual_menu(self):
        if not self.grass_dialog.grassenabled:
            return
        self.w.gisTools_logger.setText("GRASS GIS enabled")

        # Register the layer context-menu actions only once.
        if getattr(self, "_grass_ctx_added", False):
            return
        self._grass_ctx_added = True

        self.action_import_raster = QAction(
            "Send to active GRASS environment")
        self.action_import_raster.triggered.connect(
            self.import_active_raster_layer_to_grass)

        self.action_set_computational_region_from_raster = QAction(
            "Set GRASS Server Computational Region to layer extent")
        self.action_set_computational_region_from_raster.triggered.connect(
            self.set_grass_region_from_raster)

        iface.addCustomActionForLayerType(
            self.action_import_raster, 'GroundTruther',
            QgsMapLayerType.RasterLayer, True)
        iface.addCustomActionForLayerType(
            self.action_set_computational_region_from_raster, 'GroundTruther',
            QgsMapLayerType.RasterLayer, True)

        self.action_import_vector = QAction(
            "Send to active GRASS environment")
        self.action_import_vector.triggered.connect(
            self.import_active_vector_layer_to_grass)

        self.action_set_computational_region_from_vector = QAction(
            "Set GRASS Server Computational Region to layer extent")
        self.action_set_computational_region_from_vector.triggered.connect(
            self.set_grass_region_from_vector)

        iface.addCustomActionForLayerType(
            self.action_import_vector, 'GroundTruther',
            QgsMapLayerType.VectorLayer, True)
        iface.addCustomActionForLayerType(
            self.action_set_computational_region_from_vector, 'GroundTruther',
            QgsMapLayerType.VectorLayer, True)

        self.main_action = QAction("Custom Menu", iface.mainWindow())
        self.main_action.triggered.connect(
            lambda: self.show_custom_submenu(iface.activeLayer()))
        iface.addCustomActionForLayerType(
            self.main_action, 'My new Vector Menu',
            QgsMapLayerType.VectorLayer, True)

    # ------------------------------------------------------------------ #
    # Layer import / region helpers                                        #
    # ------------------------------------------------------------------ #

    def set_grass_region_from_raster(self):
        QgsMessageLog.logMessage(
            f"set_grass_region_from_raster: layer={iface.activeLayer()}, "
            f"info={get_layer_info(iface.activeLayer())}",
            'GroundTruther', Qgis.Info)

    def set_grass_region_from_vector(self):
        QgsMessageLog.logMessage(
            f"set_grass_region_from_vector: layer={iface.activeLayer()}, "
            f"info={get_layer_info(iface.activeLayer())}",
            'GroundTruther', Qgis.Info)
        layer = iface.activeLayer()
        if layer is None:
            return
        selected_features = layer.selectedFeatures()
        x_min, y_min, x_max, y_max = [], [], [], []
        for feature in selected_features:
            QgsMessageLog.logMessage(
                f"Feature ID: {feature.id()}, Geometry: {feature.geometry().asWkt()}, "
                f"Attributes: {feature.attributes()}",
                'GroundTruther', Qgis.Info)
            rect = feature.geometry().boundingBox()
            x_min.append(rect.xMinimum())
            y_min.append(rect.yMinimum())
            x_max.append(rect.xMaximum())
            y_max.append(rect.yMaximum())
        if not x_min:
            return
        bbox = [min(x_min), min(y_min), max(x_max), max(y_max)]
        QgsMessageLog.logMessage(
            f"bbox_selection: {bbox}", 'GroundTruther', Qgis.Info)

    def import_active_raster_layer_to_grass(self):
        """Context-menu action: send the active raster layer to the active env."""
        self._send_layer_to_grass(iface.activeLayer(), "raster")

    def import_active_vector_layer_to_grass(self):
        """Context-menu action: send the active vector layer to the active env."""
        self._send_layer_to_grass(iface.activeLayer(), "vector")

    @staticmethod
    def _grass_safe_name(name: str) -> str:
        """Sanitize a layer name into a valid GRASS map name."""
        import re
        safe = re.sub(r"[^A-Za-z0-9_]", "_", name or "")
        if safe and safe[0].isdigit():
            safe = "m_" + safe
        return safe or "layer"

    def _send_layer_to_grass(self, layer, kind: str):
        """Upload *layer*'s data to the active GRASS env, reprojecting if needed.

        The data is reprojected from the layer's CRS to the environment's native
        CRS (client-side, with GDAL/QGIS) before upload, so it lands in the
        location regardless of the project/layer CRS.
        """
        import os
        if layer is None:
            error_message("No active layer selected.")
            return
        endpoint, api_key, env_id = self.grass_dialog.connection()
        if not env_id:
            error_message(
                "No GRASS environment selected.\n"
                "Open GRASS settings and choose an environment.")
            return
        try:
            env_crs = self._env_crs(grass_api.projection(endpoint, api_key, env_id))
        except GrassApiError as exc:
            error_message(f"GRASS projection error: {exc}")
            return

        out_name = self._grass_safe_name(layer.name())
        tmp_path = None
        try:
            upload_path, tmp_path = self._prepare_layer_upload(layer, kind, env_crs)
            if not upload_path:
                error_message("Could not access the layer's data to send.")
                return
            if kind == "raster":
                res = grass_api.import_raster(
                    endpoint, api_key, env_id, file_path=upload_path,
                    output_name=out_name)
            else:
                res = grass_api.import_vector(
                    endpoint, api_key, env_id, file_path=upload_path,
                    output_name=out_name)
        except GrassApiError as exc:
            log_exception(f"send {kind} layer to GRASS", exc, warn=True)
            error_message(f"Send to GRASS failed: {exc}")
            return
        except Exception as exc:  # noqa: BLE001 — reprojection/export failures
            log_exception(f"send {kind} layer: reproject/export", exc)
            error_message(f"Could not prepare the layer for upload: {exc}")
            return
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

        QgsMessageLog.logMessage(
            f"sent '{layer.name()}' to env {env_id}: {res}", 'GroundTruther', Qgis.Info)
        iface.messageBar().pushMessage(
            "GroundTruther",
            f"Sent '{layer.name()}' to the active GRASS environment "
            f"as '{res.get('output', out_name)}'.",
            level=Qgis.Success, duration=5)
        try:
            self.grassWidgetContents.load_grass_layers()
        except Exception as exc:  # noqa: BLE001 — best-effort table refresh
            log_exception("send_layer: refresh GRASS layer table", exc, warn=True)

    def _prepare_layer_upload(self, layer, kind: str, env_crs):
        """Return ``(path_to_upload, temp_path_or_None)`` for *layer*.

        Reprojects to *env_crs* when the layer CRS differs.  Rasters are warped
        with GDAL; vectors are written to a temporary GeoPackage via QGIS.
        """
        import os
        import tempfile
        same_crs = layer.crs() == env_crs
        source = layer.source().split("|")[0]

        if kind == "raster":
            if same_crs and os.path.exists(source):
                return source, None
            from osgeo import gdal
            fd, tmp = tempfile.mkstemp(suffix=".tif")
            os.close(fd)
            dst_srs = env_crs.authid() or env_crs.toWkt()
            ds = gdal.Warp(tmp, source, dstSRS=dst_srs)
            ds = None  # flush/close
            return tmp, tmp

        # vector: write the loaded layer (reprojected if needed) to a temp GPKG
        fd, tmp = tempfile.mkstemp(suffix=".gpkg")
        os.close(fd)
        opts = QgsVectorFileWriter.SaveVectorOptions()
        opts.driverName = "GPKG"
        opts.layerName = self._grass_safe_name(layer.name())
        if not same_crs:
            opts.ct = QgsCoordinateTransform(layer.crs(), env_crs, QgsProject.instance())
        result = QgsVectorFileWriter.writeAsVectorFormatV3(
            layer, tmp, QgsProject.instance().transformContext(), opts)
        code = result[0] if isinstance(result, (tuple, list)) else result
        if code != QgsVectorFileWriter.WriterError.NoError:
            raise RuntimeError(f"vector export failed: {result}")
        return tmp, tmp

    # ------------------------------------------------------------------ #
    # GRASS region                                                         #
    # ------------------------------------------------------------------ #

    def set_grass_cpr(self, minlat, maxlat, minlon, maxlon):
        payload = self.set_grass_region(
            float(minlat), float(maxlat), float(minlon), float(maxlon))
        if payload is None:
            return
        self.region_response = payload.get("region")
        if self.r:
            self.canvas.scene().removeItem(self.r)
        self.r = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        points = [[
            QgsPointXY(maxlon, maxlat), QgsPointXY(minlon, maxlat),
            QgsPointXY(minlon, minlat), QgsPointXY(maxlon, minlat),
        ]]
        self.r.setToGeometry(QgsGeometry.fromPolygonXY(points), None)
        self.r.setWidth(3)
        self.r.setColor(QColor(255, 0, 0))
        self.r.setFillColor(QColor(0, 0, 0, 0))

    def set_grass_region(
        self, minlat: float, maxlat: float, minlon: float, maxlon: float
    ):
        """Set the GRASS computational region from a drawn bbox.

        The bounds arrive in the active *project* CRS (the region tool emits map
        coordinates) and are reprojected to the environment's native CRS with
        QGIS before calling the API (the FastGIS region endpoint expects
        native-CRS bounds).  Returns the region payload
        (``{"env_id", "region": {...}}``) on success, or ``None`` on any error.
        """
        endpoint, api_key, env_id = self.grass_dialog.connection()
        if not env_id:
            error_message(
                "No GRASS environment selected.\n"
                "Open GRASS settings and choose an environment.")
            return None
        try:
            proj = grass_api.projection(endpoint, api_key, env_id)
            target_crs = self._env_crs(proj)
            north, south, east, west = self._bounds_to_native(
                minlat, maxlat, minlon, maxlon, target_crs)
            return grass_api.set_region(
                endpoint, api_key, env_id,
                north=north, south=south, east=east, west=west)
        except GrassApiError as exc:
            log_exception("set_grass_region: API error", exc, warn=True)
            error_message(f"GRASS region error: {exc}")
            return None

    @staticmethod
    def _env_crs(proj: dict) -> QgsCoordinateReferenceSystem:
        """Build a QGIS CRS from a FastGIS projection dict (epsg or wkt)."""
        epsg = (proj or {}).get("epsg")
        if epsg:
            crs = QgsCoordinateReferenceSystem(f"EPSG:{epsg}")
            if crs.isValid():
                return crs
        wkt = (proj or {}).get("wkt")
        if wkt:
            crs = QgsCoordinateReferenceSystem.fromWkt(wkt)
            if crs.isValid():
                return crs
        return QgsCoordinateReferenceSystem("EPSG:4326")

    @staticmethod
    def _bounds_to_native(minlat, maxlat, minlon, maxlon, target_crs):
        """Reproject bbox corners from the project CRS to *target_crs*.

        The region box tool (``GCRTool``) emits corners in map/canvas (i.e.
        project) coordinates — eastings/northings, not lon/lat — so the source
        CRS is the active project CRS, not WGS-84.  ``minlon/maxlon`` are X
        (east), ``minlat/maxlat`` are Y (north).  Returns ``n, s, e, w`` in the
        env's native CRS.
        """
        corners = [(minlon, minlat), (minlon, maxlat),
                   (maxlon, minlat), (maxlon, maxlat)]  # (x, y)
        src = QgsProject.instance().crs()
        if not src.isValid():
            src = QgsCoordinateReferenceSystem("EPSG:4326")
        if src != target_crs:
            xform = QgsCoordinateTransform(src, target_crs, QgsProject.instance())
            corners = [(p.x(), p.y())
                       for p in (xform.transform(QgsPointXY(x, y))
                                 for x, y in corners)]
        xs = [c[0] for c in corners]
        ys = [c[1] for c in corners]
        return max(ys), min(ys), max(xs), min(xs)

    # ------------------------------------------------------------------ #
    # GRASS raster query                                                   #
    # ------------------------------------------------------------------ #

    def get_query_message(self, stringa):
        self.grassWidgetContents.grass_mdi.gis_tool_report.setHtml(stringa)

    def get_grass_query_data(self, lat: float, lon: float):
        report = self.grassWidgetContents.grass_mdi.gis_tool_report
        endpoint, api_key, env_id = self.grass_dialog.connection()
        if not env_id:
            report.setHtml(
                "<b>No GRASS environment selected.</b> "
                "Open GRASS settings and choose an environment.")
            return

        self.grassWidgetContents.get_checked_items()
        grass_layers = self.grassWidgetContents.checked_layers
        if not grass_layers:
            report.setHtml("No GRASS layers selected.")
            return

        # The query tool emits WGS-84 lon/lat; the API reprojects to native CRS.
        try:
            result = grass_api.sample(
                endpoint, api_key, env_id, layers=grass_layers,
                point={"x": lon, "y": lat}, crs="EPSG:4326")
        except GrassApiError as exc:
            log_exception("get_grass_query_data: sample failed", exc, warn=True)
            error_message(f"GRASS query error: {exc}")
            return

        rasters = (result or {}).get("results", {}).get("raster", [])
        rows = []
        for entry in rasters:
            samples = entry.get("samples") or []
            value = samples[0].get("value") if samples else None
            if value not in (None, "No data"):
                rows.append(f"{entry.get('layer')}: {value}")
        report.setHtml("<br>".join(rows) if rows else "No data at this location.")
        self.grassWidgetContents.add_query_result(rasters)

    # ------------------------------------------------------------------ #
    # MDI view helpers                                                     #
    # ------------------------------------------------------------------ #

    def onZoomInClicked(self):
        self.grassWidgetContents.grass_mdi.gis_tool_report.zoomIn(1)

    def onZoomOutClicked(self):
        self.grassWidgetContents.grass_mdi.gis_tool_report.zoomOut(1)

    def onClearClicked(self):
        self.grassWidgetContents.grass_mdi.gis_tool_report.clear()

    def view_r_gemorphon(self, module):
        if self.r_gemorphon_window.isVisible():
            self.r_gemorphon_window.hide()
        else:
            self.r_gemorphon.get_rvr_list()
            self.r_gemorphon_window.show()

    def view_r_paramscale(self, module):
        if self.r_paramscale_window.isVisible():
            self.r_paramscale_window.hide()
        else:
            self.r_paramscale.get_rvr_list()
            self.r_paramscale_window.show()

    def view_r_grm_lsi(self, module):
        if self.r_grm_lsi_window.isVisible():
            self.r_grm_lsi_window.hide()
        else:
            self.r_grm_lsi.get_rvr_list()
            self.r_grm_lsi_window.show()

    def set_mdi_view(self, index):
        text = self.mdi_view.itemText(index)
        subwindows = self.grassWidgetContents.grass_mdi.grassTools.subWindowList()
        if text == 'Cascade':
            self.grassWidgetContents.grass_mdi.grassTools.cascadeSubWindows()
        elif text == 'Tiled':
            self.grassWidgetContents.grass_mdi.grassTools.tileSubWindows()
        elif text == 'Minimize':
            for win in subwindows:
                if win.isVisible():
                    win.showMinimized()
        elif text == 'Close':
            for win in subwindows:
                if win.isVisible():
                    win.hide()
