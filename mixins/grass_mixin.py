"""GRASS GIS integration mixin."""
from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QColor
from qgis.utils import iface
from qgis.core import (
    Qgis, QgsMessageLog, QgsMapLayerType,
    QgsPointXY, QgsGeometry, QgsWkbTypes,
    QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject,
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

        self.action_import_raster = QAction(
            "Import selected layer into GRASS Server")
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
            "Import selected layer into GRASS Server")
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
        QgsMessageLog.logMessage(
            f"import_active_raster_layer_to_grass: layer={iface.activeLayer()}, "
            f"info={get_layer_info(iface.activeLayer())}",
            'GroundTruther', Qgis.Info)

    def import_active_vector_layer_to_grass(self):
        geojson = convert_to_geojson_using_gdal(iface.activeLayer().source())
        QgsMessageLog.logMessage(
            f"import_active_vector_layer_to_grass – geojson ready, "
            f"endpoint: {self.grass_api_endpoint}\n"
            f"{geojson[:200] if isinstance(geojson, str) else geojson}",
            'GroundTruther', Qgis.Info)

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
        """Set the GRASS computational region from WGS-84 bounds.

        The bounds (lon/lat, EPSG:4326) are reprojected to the active
        environment's native CRS with QGIS before calling the API (the FastGIS
        region endpoint expects native-CRS bounds).  Returns the region payload
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
        """Transform WGS-84 bbox corners to *target_crs*; return n, s, e, w."""
        src = QgsCoordinateReferenceSystem("EPSG:4326")
        xform = QgsCoordinateTransform(src, target_crs, QgsProject.instance())
        corners = [(minlon, minlat), (minlon, maxlat),
                   (maxlon, minlat), (maxlon, maxlat)]
        pts = [xform.transform(QgsPointXY(lon, lat)) for lon, lat in corners]
        xs = [p.x() for p in pts]
        ys = [p.y() for p in pts]
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
