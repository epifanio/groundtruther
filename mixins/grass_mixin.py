"""GRASS GIS integration mixin."""
import requests
from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QColor
from qgis.utils import iface
from qgis.core import (
    Qgis, QgsMessageLog, QgsMapLayerType,
    QgsPointXY, QgsGeometry, QgsWkbTypes,
)
from qgis.gui import QgsRubberBand

from groundtruther.configure import error_message, log_exception
from groundtruther.ioutils import get_layer_info, convert_to_geojson_using_gdal
from groundtruther.pygui.grass_mdi_gui import GrassTools


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
            'GroundTruther', Qgis.Information)
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
            'GroundTruther', Qgis.Information)

    def set_grass_region_from_vector(self):
        QgsMessageLog.logMessage(
            f"set_grass_region_from_vector: layer={iface.activeLayer()}, "
            f"info={get_layer_info(iface.activeLayer())}",
            'GroundTruther', Qgis.Information)
        layer = iface.activeLayer()
        if layer is None:
            return
        selected_features = layer.selectedFeatures()
        x_min, y_min, x_max, y_max = [], [], [], []
        for feature in selected_features:
            QgsMessageLog.logMessage(
                f"Feature ID: {feature.id()}, Geometry: {feature.geometry().asWkt()}, "
                f"Attributes: {feature.attributes()}",
                'GroundTruther', Qgis.Information)
            rect = feature.geometry().boundingBox()
            x_min.append(rect.xMinimum())
            y_min.append(rect.yMinimum())
            x_max.append(rect.xMaximum())
            y_max.append(rect.yMaximum())
        if not x_min:
            return
        bbox = [min(x_min), min(y_min), max(x_max), max(y_max)]
        QgsMessageLog.logMessage(
            f"bbox_selection: {bbox}", 'GroundTruther', Qgis.Information)

    def import_active_raster_layer_to_grass(self):
        QgsMessageLog.logMessage(
            f"import_active_raster_layer_to_grass: layer={iface.activeLayer()}, "
            f"info={get_layer_info(iface.activeLayer())}",
            'GroundTruther', Qgis.Information)

    def import_active_vector_layer_to_grass(self):
        geojson = convert_to_geojson_using_gdal(iface.activeLayer().source())
        QgsMessageLog.logMessage(
            f"import_active_vector_layer_to_grass – geojson ready, "
            f"endpoint: {self.grass_api_endpoint}\n"
            f"{geojson[:200] if isinstance(geojson, str) else geojson}",
            'GroundTruther', Qgis.Information)

    # ------------------------------------------------------------------ #
    # GRASS region                                                         #
    # ------------------------------------------------------------------ #

    def set_grass_cpr(self, minlat, maxlat, minlon, maxlon):
        payload = self.set_grass_region(
            float(minlat), float(maxlat), float(minlon), float(maxlon))
        if payload is None:
            return
        if payload.get("status") != "SUCCESS":
            error_message(f"GRASS region error: {payload}")
            return
        try:
            self.region_response = payload["data"]["region"]
        except KeyError as exc:
            log_exception(
                "set_grass_cpr: unexpected region response structure", exc)
            error_message(
                f"Unexpected GRASS region response structure: {exc}")
            return
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
        """Set the GRASS computational region.

        Returns the parsed JSON payload on success, or ``None`` on any error.
        """
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
        }

        if not self.grass_api_endpoint:
            error_message(
                "No GRASS API endpoint configured.\nSet the endpoint in Settings.")
            return None

        grass_settings = self.grass_dialog.set_grass_location()
        if grass_settings.get("status") != "SUCCESS":
            error_message(
                f"GRASS location error: {grass_settings.get('data', grass_settings)}")
            return None

        grass_gisenv = grass_settings["data"]["gisenv"]

        try:
            projection_code = int(
                grass_settings["data"]["region"]["projection"].split(" ")[0])
        except (KeyError, ValueError, IndexError) as exc:
            log_exception(
                "set_grass_region: could not parse projection code", exc, warn=True)
            projection_code = 0

        try:
            if projection_code == 1:
                proj_data = {
                    "location": {
                        "location_name": grass_gisenv["LOCATION_NAME"],
                        "mapset_name": grass_gisenv["MAPSET"],
                        "gisdb": grass_gisenv["GISDBASE"],
                    },
                    "coors": [[minlon, maxlat], [maxlon, minlat]],
                }
                proj_response = requests.post(
                    f"{self.grass_api_endpoint}/api/m_proj",
                    headers=headers, json=proj_data, timeout=60,
                )
                corners = proj_response.json()["data"]
            else:
                corners = [[minlon, maxlat], [maxlon, minlat]]

            region_data = {
                "location": {
                    "location_name": grass_gisenv["LOCATION_NAME"],
                    "mapset_name": grass_gisenv["MAPSET"],
                    "gisdb": grass_gisenv["GISDBASE"],
                },
                "bounds": {
                    "n": corners[0][1],
                    "s": corners[1][1],
                    "e": corners[1][0],
                    "w": corners[0][0],
                },
                "resolution": {"resolution": 0},
            }
            response = requests.post(
                f"{self.grass_api_endpoint}/api/set_region_bounds",
                headers=headers, json=region_data, timeout=60,
            )
            return response.json()

        except requests.exceptions.RequestException as exc:
            log_exception(
                "set_grass_region: API request failed", exc, warn=True)
            error_message(
                "Cannot reach the GRASS API server.\n"
                "Check the endpoint URL in Settings.")
            return None
        except (ValueError, KeyError) as exc:
            log_exception(
                "set_grass_region: unexpected API response structure", exc)
            error_message(f"Unexpected GRASS API response: {exc}")
            return None

    # ------------------------------------------------------------------ #
    # GRASS raster query                                                   #
    # ------------------------------------------------------------------ #

    def get_query_message(self, stringa):
        self.grassWidgetContents.grass_mdi.gis_tool_report.setHtml(stringa)

    def get_grass_query_data(self, lat: float, lon: float):
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
        }
        if not self.grass_api_endpoint:
            self.grassWidgetContents.grass_mdi.gis_tool_report.setHtml(
                "<b>No GRASS API endpoint configured.</b> "
                "Set the endpoint in Settings.")
            return

        grass_settings = self.grass_dialog.set_grass_location()
        if grass_settings.get("status") != "SUCCESS":
            self.grassWidgetContents.grass_mdi.gis_tool_report.setHtml(
                f"<b>GRASS location error:</b> {grass_settings}")
            return

        grass_gisenv = grass_settings["data"]["gisenv"]
        self.grassWidgetContents.get_checked_items()
        grass_layers = self.grassWidgetContents.checked_layers

        try:
            projection_code = int(
                grass_settings["data"]["region"]["projection"].split(" ")[0])
        except (KeyError, ValueError, IndexError) as exc:
            log_exception(
                "get_grass_query_data: could not parse projection code",
                exc, warn=True)
            projection_code = 0
        params = {"lonlat": "true" if projection_code == 1 else "false"}

        json_data = {
            "location": {
                "location_name": grass_gisenv["LOCATION_NAME"],
                "mapset_name": grass_gisenv["MAPSET"],
                "gisdb": grass_gisenv["GISDBASE"],
            },
            "coors": [lon, lat],
            "grass_layers": grass_layers,
        }

        try:
            response = requests.post(
                f"{self.grass_api_endpoint}/api/r_what",
                params=params, headers=headers, json=json_data, timeout=60,
            )
            payload = response.json()
        except requests.exceptions.RequestException as exc:
            log_exception(
                "get_grass_query_data: r_what request failed", exc, warn=True)
            error_message(
                "Cannot reach the GRASS API server.\n"
                "Check the endpoint URL in Settings.")
            return
        except ValueError as exc:
            log_exception(
                "get_grass_query_data: r_what non-JSON response", exc)
            error_message(
                "GRASS API returned an unexpected (non-JSON) response.")
            return

        if payload.get("status") == "SUCCESS":
            results = "<br>".join(
                f"{list(i.keys())[0]}: {i[list(i.keys())[0]]['value']}<br>"
                for i in payload["data"]
                if i[list(i.keys())[0]]["value"] != "No data"
            )
            self.grassWidgetContents.add_query_result(payload["data"])
        else:
            results = str(payload)
        self.grassWidgetContents.grass_mdi.gis_tool_report.setHtml(results)

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
