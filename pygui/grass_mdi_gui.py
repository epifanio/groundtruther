#!/usr/bin/env python
"""GRASS GIS MDI panel — layer list, query results, and module launchers.

Key classes
-----------
GrassMdi
    The central widget (generated from ``Ui_grass_mdi``): contains the MDI
    sub-window area (``grassTools``), the query-result browser
    (``gis_tool_report``), and the layer table (``grass_layers``).

GrassLayerTableWidgetItem
    Lightweight QTableWidgetItem subclass that carries a ``layer_enabled``
    property alongside the display text.

GrassTools
    QMainWindow that owns the ``GrassMdi`` widget and provides the toolbar
    for controlling MDI layout and launching individual GRASS module panels
    (r.geomorphon, r.param.scale, r.grm.lsi).  Delegates zoom/clear actions
    to ``GrassIntegrationMixin`` methods on the parent dockwidget.
"""
import sys

from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *

from groundtruther.pygui.Ui_grass_mdi_ui import Ui_grass_mdi

from groundtruther.run_geomorphon_mdi import GeoMorphonWidget
from groundtruther.run_paramscale_mdi import ParamScaleWidget
from groundtruther.run_grm_lsi_mdi import GrmLsiWidget
from groundtruther.pygui.grass_module_runner import ModuleRunnerWidget

from qgis.PyQt.QtWidgets import (
    QTableWidgetItem, QWidget, QCheckBox, QMenu, QAction, QLineEdit, QCompleter,
    QLabel)
from qgis.PyQt.QtCore import QStringListModel, QEvent
from qgis.core import Qgis, QgsMessageLog, QgsProject, QgsRasterLayer
from groundtruther.configure import log_exception
from groundtruther.gt import grass_api
from groundtruther.gt.grass_api import GrassApiError
class GrassLayerTableWidgetItem(QTableWidgetItem):
    """QTableWidgetItem that also stores whether the GRASS layer is enabled."""

    def __init__(self, text, layer_enabled):
        super().__init__(text)
        self.layer_enabled = layer_enabled


class GrassMdi(QWidget, Ui_grass_mdi):
    """Central GRASS widget built from the Designer-generated Ui_grass_mdi layout."""

    def __init__(self, parent=None):
        super(GrassMdi, self).__init__(parent)
        self.setupUi(self)


class GrassTools(QMainWindow):
    """QMainWindow container for GRASS module panels and the layer/query table.

    Layout overview:
    - Central widget: ``GrassMdi`` (MDI area + query result browser + layer table)
    - Toolbar: MDI-layout selector, layer-table toggle, module action buttons

    Module sub-windows (r.geomorphon, r.param.scale, r.grm.lsi) are created
    here and shown/hidden via their respective toolbar actions.  Query results
    and zoom/clear actions delegate to ``GrassIntegrationMixin`` via the
    parent dockwidget.
    """

    def __init__(self, parent=None):
        super(GrassTools, self).__init__(parent)
        self.parent = parent
        # self.grass_dialog = self.parent.grass_dialog
        # self.settings = self.parent.settings
        # self.region_response = self.parent.region_response
        # self.project = self.parent.project
        self.grass_mdi = GrassMdi()
        self.setCentralWidget(self.grass_mdi)
        
        # bar = self.menuBar()
        # file = bar.addMenu("File")
        # file.addAction("New")
        # file.addAction("cascade")
        # file.addAction("Tiled")
        # file.triggered[QAction].connect(self.windowaction)
        
        layout1 = QHBoxLayout()
        #layout2 = QVBoxLayout()
        #layout2.addWidget(self.gis_tool_report)
        layout1.addWidget(self.grass_mdi)
        #layout1.addLayout( layout2 )
        self.grass_widget = QWidget()
        self.grass_widget.setLayout(layout1)
        
        #self.grassWidgetContents.setCentralWidget(self.gis_tool_report)
        self.setCentralWidget(self.grass_widget)

        self.moduleToolBar = self.addToolBar("GrassModules")
        self.moduleToolBar.toggleViewAction().setEnabled(False)
        
        # On-the-fly module picker: type/autocomplete any GRASS module name and
        # open a dialog built from its interface schema (mirrors the FastGIS web
        # grass_runner). Catalog is loaded lazily on first focus.
        self._module_catalog_loaded = False
        self._module_windows = {}
        self.moduleToolBar.addWidget(QLabel(" Module: "))
        self.module_search = QLineEdit()
        self.module_search.setPlaceholderText("type a GRASS module… e.g. r.slope.aspect")
        self.module_search.setMinimumWidth(240)
        self._module_completer = QCompleter([], self)
        self._module_completer.setCaseSensitivity(Qt.CaseSensitivity(0))   # CaseInsensitive
        self._module_completer.setFilterMode(Qt.MatchFlag(1))              # MatchContains
        self._module_completer.setCompletionMode(QCompleter.CompletionMode(0))  # Popup
        self.module_search.setCompleter(self._module_completer)
        self.module_search.installEventFilter(self)
        self.module_search.returnPressed.connect(self.open_typed_module)
        self.moduleToolBar.addWidget(self.module_search)
        self.open_module_btn = QToolButton()
        self.open_module_btn.setText("Open")
        self.open_module_btn.setToolTip("Build & open a dialog for this GRASS module")
        self.open_module_btn.clicked.connect(self.open_typed_module)
        self.moduleToolBar.addWidget(self.open_module_btn)

        self.grass_layers_view = QToolButton()
        grass_layers_view_icon = QIcon(":/icons/qtui/icons/table-list.svg")
        self.grass_layers_view.setToolTip("Show/Hide GRASS Layers")
        self.grass_layers_view.setIcon(grass_layers_view_icon)
        self.moduleToolBar.addWidget(self.grass_layers_view)
        self.grass_layers_view.clicked.connect(self.toggle_grass_layers_table)

        # Import data into the active environment
        self.import_raster_btn = QToolButton()
        self.import_raster_btn.setText("Import Raster")
        self.import_raster_btn.setToolTip("Import a raster file into the active GRASS environment")
        self.import_raster_btn.clicked.connect(lambda: self.import_to_env("raster"))
        self.moduleToolBar.addWidget(self.import_raster_btn)

        self.import_vector_btn = QToolButton()
        self.import_vector_btn.setText("Import Vector")
        self.import_vector_btn.setToolTip("Import a vector file into the active GRASS environment")
        self.import_vector_btn.clicked.connect(lambda: self.import_to_env("vector"))
        self.moduleToolBar.addWidget(self.import_vector_btn)

        # Add the checked GRASS raster(s) from the table into the QGIS project
        self.add_to_qgis_btn = QToolButton()
        self.add_to_qgis_btn.setText("Add to QGIS")
        self.add_to_qgis_btn.setToolTip("Add the checked GRASS raster(s) to the QGIS project")
        self.add_to_qgis_btn.clicked.connect(self.add_selected_to_qgis)
        self.moduleToolBar.addWidget(self.add_to_qgis_btn)

        # Show/hide the active env's current computational region on the map
        self.show_region_btn = QToolButton()
        self.show_region_btn.setText("Region")
        self.show_region_btn.setCheckable(True)
        self.show_region_btn.setToolTip("Show/hide the active GRASS computational region on the map")
        self.show_region_btn.clicked.connect(self.parent.toggle_grass_region)
        self.moduleToolBar.addWidget(self.show_region_btn)

        # The MDI area is no longer used (modules open as top-level windows); hide it.
        self.grass_mdi.grassTools.hide()

        self.r_gemorphon = GeoMorphonWidget(self.parent)
        self._init_module_window(self.r_gemorphon, "r.geomorphon")
        self.r_gemorphon_window = self.r_gemorphon
        self.r_gemorphon.exit.clicked.connect(self.view_r_gemorphon)
        gemorphon_icon_path = ':/icons/qtui/icons/element-cell.gif'
        gemorphon_icon = QIcon(gemorphon_icon_path)
        gemorphon_action = QAction(gemorphon_icon, self.tr(u'r.gemorphon'), self)
        #
        gemorphon_action.triggered.connect(self.view_r_gemorphon)
        gemorphon_action.setEnabled(True)
        gemorphon_action.setCheckable(True)
        #
        self.moduleToolBar.addAction(gemorphon_action)
        
        
        
        self.r_paramscale = ParamScaleWidget(self.parent)
        self._init_module_window(self.r_paramscale, "r.param.scale")
        self.r_paramscale_window = self.r_paramscale
        self.r_paramscale.exit.clicked.connect(self.view_r_paramscale)
        paramscale_icon_path = ':/icons/qtui/icons/element-cell.gif'
        paramscale_icon = QIcon(paramscale_icon_path)
        paramscale_action = QAction(paramscale_icon, self.tr(u'r.param.scale'), self)
        #
        paramscale_action.triggered.connect(self.view_r_paramscale)
        paramscale_action.setEnabled(True)
        paramscale_action.setCheckable(True)
        
        
        
        self.r_grm_lsi = GrmLsiWidget(self.parent)
        self._init_module_window(self.r_grm_lsi, "grm_lsi")
        self.r_grm_lsi_window = self.r_grm_lsi
        self.r_grm_lsi.exit.clicked.connect(self.view_r_grm_lsi)
        grm_lsi_icon_path = ':/icons/qtui/icons/element-cell.gif'
        grm_lsi_icon = QIcon(grm_lsi_icon_path)
        grm_lsi_action = QAction(grm_lsi_icon, self.tr(u'r.grm.lsi'), self)
        #
        grm_lsi_action.triggered.connect(self.view_r_grm_lsi)
        grm_lsi_action.setEnabled(True)
        grm_lsi_action.setCheckable(True)

        #
        self.moduleToolBar.addAction(gemorphon_action)
        self.moduleToolBar.addAction(paramscale_action)
        self.moduleToolBar.addAction(grm_lsi_action)
        
        # Using a QToolBar object
        # editToolBar = QToolBar("Edit", self.grassWidgetContents)
        # self.grassWidgetContents.addToolBar(editToolBar)
        # Using a QToolBar object and a toolbar area
        # helpToolBar = QToolBar("Help", self.grassWidgetContents)
        # self.grassWidgetContents.addToolBar(Qt.ToolBarArea.LeftToolBarArea, helpToolBar)
        
        #
        # self.geomorphon_dialog = GeoMorphonDialog(self)
        self.grass_mdi.zoom_in.clicked.connect(self.onZoomInClicked)
        self.grass_mdi.zoom_out.clicked.connect(self.onZoomOutClicked)
        self.grass_mdi.copy.clicked.connect(self.grass_mdi.gis_tool_report.copy)
        self.grass_mdi.selectAll.clicked.connect(self.grass_mdi.gis_tool_report.selectAll)
        
        self.grass_mdi.clear.clicked.connect(self.onClearClicked)
        
        # self.grass_mdi.grass_layers.setHorizontalHeaderLabels(["Layer Name", "Value"])
        self.grass_mdi.grass_layers.hide()
        self.grass_mdi.reload_grass_layers.hide()
        # self.grass_mdi.show_hide_grass_layers.clicked.connect(self.toggle_grass_layers_table)
        self.grass_mdi.reload_grass_layers.clicked.connect(self.load_grass_layers)
        self.grass_mdi.filterLineEdit_label.hide()
        self.grass_mdi.filterLineEdit.hide()
        self.grass_mdi.filterLineEdit.setPlaceholderText("Filter...")
        self.grass_mdi.filterLineEdit.textChanged.connect(self.filter_table)
        
        self.grass_mdi.grass_layers.setContextMenuPolicy(Qt.ContextMenuPolicy(3))
        self.grass_mdi.grass_layers.customContextMenuRequested.connect(self.show_context_menu)
        # self.grass_mdi.grass_layers.viewport().customContextMenuRequested.connect(self.show_context_menu)

        # self.setWindowTitle("MDI demo")
        # self.show()
        
    def show_context_menu(self, position):
        """Show a right-click context menu on the layer table."""
        indexes = self.grass_mdi.grass_layers.selectedIndexes()
        if indexes:
            menu = QMenu(self)
            add_action = QAction("Add to QGIS", self)
            add_action.triggered.connect(self.add_selected_to_qgis)
            menu.addAction(add_action)
            delete_action = QAction("Delete Row", self)
            delete_action.triggered.connect(self.delete_row)
            menu.addAction(delete_action)
            menu.exec(self.grass_mdi.grass_layers.viewport().mapToGlobal(position))

    def delete_row(self):
        """Remove the selected row(s) from the layer table.

        Planned future actions (not yet implemented):
          1. Zoom to selected layer
          2. Add selected layer to QGIS map canvas
          3. Set the GRASS region for selected layer
          4. Delete selected layer from the GRASS database
          5. Show layer history / metadata
        """
        indexes = self.grass_mdi.grass_layers.selectedIndexes()
        if indexes:
            rows = set()
            for index in indexes:
                rows.add(index.row())
            for row in sorted(rows, reverse=True):
                self.grass_mdi.grass_layers.removeRow(row)
            
    def toggle_grass_layers_table(self):
        """Show or hide the GRASS layers table and its associated filter bar."""
        self.grass_mdi.grass_layers.setVisible(not self.grass_mdi.grass_layers.isVisible())
        self.grass_mdi.reload_grass_layers.setVisible(not self.grass_mdi.reload_grass_layers.isVisible())        
        self.grass_mdi.filterLineEdit_label.setVisible(not self.grass_mdi.filterLineEdit_label.isVisible())
        self.grass_mdi.filterLineEdit.setVisible(not self.grass_mdi.filterLineEdit.isVisible())

        # self.get_grass_layers()
        
    def load_grass_layers(self):
        """Fetch the raster layer list from the GRASS API and populate the table."""
        self.grass_mdi.grass_layers.clear()
        grass_layers = self.get_grass_layers()
        self.populate_table(grass_layers)

    def populate_table(self, items):
        """Populate the layer table with checkboxes for each GRASS raster layer."""
        self.grass_mdi.grass_layers.setRowCount(len(items))
        self.grass_mdi.grass_layers.setColumnCount(2)
        self.grass_mdi.grass_layers.setHorizontalHeaderLabels(["Layer Name", "Value"])
        for row, item in enumerate(items):
            checkbox = QCheckBox(item)
            checkbox.setProperty("layer_enabled", f"Custom Property for {item}")
            # empty_cell = GrassLayerTableWidgetItem("")
            empty_cell = GrassLayerTableWidgetItem("", checkbox.property("layer_enabled"))
            
            self.grass_mdi.grass_layers.setCellWidget(row, 0, checkbox)
            self.grass_mdi.grass_layers.setItem(row, 1, empty_cell)  
            
    def add_query_result(self, result):
        """Write sample results into the matching rows of the layer table.

        Parameters
        ----------
        result:
            The ``results.raster`` list from ``grass_api.sample``, i.e.
            ``[{"layer": "<name>", "samples": [{"value": ...}, ...]}, ...]``.
        """
        QgsMessageLog.logMessage(f"query result: {result}", 'GroundTruther', Qgis.Info)
        result_dict = {}
        for entry in result:
            name = entry.get("layer")
            samples = entry.get("samples") or []
            value = samples[0].get("value") if samples else None
            if name is not None:
                result_dict[name] = value
        for row in range(self.grass_mdi.grass_layers.rowCount()):
            checkbox_item = self.grass_mdi.grass_layers.cellWidget(row, 0)
            if checkbox_item.text() in result_dict:
                value_cell = GrassLayerTableWidgetItem(
                    str(result_dict[checkbox_item.text()]),
                    checkbox_item.property("layer_enabled"))
                self.grass_mdi.grass_layers.setItem(row, 1, value_cell)
            
    def get_checked_items(self):
        """Collect the names of checked layers into ``self.checked_layers``."""
        self.checked_layers = []
        for row in range(self.grass_mdi.grass_layers.rowCount()):
            checkbox_item = self.grass_mdi.grass_layers.cellWidget(row, 0)
            if isinstance(checkbox_item, QCheckBox) and checkbox_item.isChecked():
                item = checkbox_item.text()
                self.checked_layers.append(item)
                
    def filter_table(self):
        """Hide rows whose layer name does not contain the filter text."""
        filter_text = self.grass_mdi.filterLineEdit.text().strip().lower()
        for row in range(self.grass_mdi.grass_layers.rowCount()):
            checkbox_item = self.grass_mdi.grass_layers.cellWidget(row, 0)
            item = checkbox_item.text()
            row_text = item.lower() if item else ""
            if filter_text in row_text:
                self.grass_mdi.grass_layers.setRowHidden(row, False)
            else:
                self.grass_mdi.grass_layers.setRowHidden(row, True)

        
    def get_grass_layers(self):
        """Return the raster map names in the active GRASS environment.

        Uses the parent's ``grass_dialog`` connection (endpoint, API key,
        active ``env_id``) and ``g.list`` via ``grass_api.list_maps``.  Returns
        an empty list if no environment is active or on any API error.
        """
        self.grass_dialog = self.parent.grass_dialog
        endpoint, api_key, env_id = self.grass_dialog.connection()
        if not env_id:
            QgsMessageLog.logMessage(
                "get_grass_layers: no active GRASS environment",
                'GroundTruther', Qgis.Warning)
            return []
        try:
            grass_layers = grass_api.list_maps(endpoint, api_key, env_id, type="raster")
        except GrassApiError as exc:
            log_exception("get_grass_layers: list_maps failed", exc, warn=True)
            return []
        QgsMessageLog.logMessage(f"grass layers: {grass_layers}", 'GroundTruther', Qgis.Info)
        return grass_layers
        
        
    def reload_parent_objects(self):
        """Refresh references to parent-owned objects (dialog, settings, region)."""
        self.grass_dialog = self.parent.grass_dialog
        self.settings = self.parent.settings
        self.region_response = self.parent.region_response
        self.project = self.parent.project
        QgsMessageLog.logMessage(f"region_response: {self.region_response}", 'GroundTruther', Qgis.Info)
    
    def onZoomInClicked(self):
        self.grass_mdi.gis_tool_report.zoomIn(1)

    def onZoomOutClicked(self):
        self.grass_mdi.gis_tool_report.zoomOut(1)
    
    def onClearClicked(self):
        self.grass_mdi.gis_tool_report.clear()

    def import_to_env(self, kind: str):
        """Upload a raster/vector file into the active GRASS environment."""
        endpoint, api_key, env_id = self.parent.grass_dialog.connection()
        report = self.grass_mdi.gis_tool_report
        if not env_id:
            report.setHtml("<b>No GRASS environment selected.</b> "
                           "Open GRASS settings and choose an environment.")
            return
        if kind == "raster":
            filt = "Raster (*.tif *.tiff *.img *.vrt *.jp2 *.png *.asc);;All files (*)"
        else:
            filt = "Vector (*.shp *.gpkg *.geojson *.json *.zip);;All files (*)"
        path, _ = QFileDialog.getOpenFileName(
            self, f"Import {kind} into active environment", "", filt)
        if not path:
            return
        report.setHtml(f"… importing {kind} …")
        try:
            if kind == "raster":
                res = grass_api.import_raster(endpoint, api_key, env_id, file_path=path)
            else:
                res = grass_api.import_vector(endpoint, api_key, env_id, file_path=path)
        except GrassApiError as exc:
            log_exception(f"import_to_env({kind})", exc, warn=True)
            report.setHtml(f"<b>Import failed:</b> {exc}")
            return
        report.setHtml(f"<b>Imported {kind}:</b><pre>{res}</pre>")
        self.load_grass_layers()

    # ------------------------------------------------------------------ #
    # On-the-fly module picker                                            #
    # ------------------------------------------------------------------ #

    def eventFilter(self, obj, event):
        # Lazily load the module catalog the first time the search box is focused.
        if obj is getattr(self, "module_search", None) and event.type() == QEvent.Type(8):
            self._ensure_module_catalog()
        return super().eventFilter(obj, event)

    def _ensure_module_catalog(self):
        """Populate the module-name autocompleter from GET /grass/modules (once)."""
        if self._module_catalog_loaded:
            return
        endpoint, api_key, _env = self.parent.grass_dialog.connection()
        if not (endpoint and api_key):
            return
        try:
            mods = grass_api.list_modules(endpoint, api_key)
        except GrassApiError as exc:
            log_exception("load module catalog", exc, warn=True)
            return
        names = sorted({m.get("name") for m in mods if m.get("name")})
        self._module_completer.setModel(QStringListModel(names, self._module_completer))
        self._module_catalog_loaded = True

    def open_typed_module(self):
        """Open a dialog for the module name currently in the search box."""
        name = self.module_search.text().strip()
        if name:
            self.open_module_window(name)

    def open_module_window(self, name):
        """Build (once) and show a schema-driven runner window for *name*."""
        window = self._module_windows.get(name)
        if window is None:
            window = ModuleRunnerWidget(self.parent, name)
            self._init_module_window(window, name)
            window.exit.clicked.connect(window.hide)   # wire the Close button
            self._module_windows[name] = window
        window.get_rvr_list()
        window.show()
        window.raise_()
        window.activateWindow()

    # ------------------------------------------------------------------ #
    # Add GRASS rasters from the table into QGIS                          #
    # ------------------------------------------------------------------ #

    def add_selected_to_qgis(self):
        """Add the checked GRASS raster(s) (or the current row) to the project."""
        report = self.grass_mdi.gis_tool_report
        self.get_checked_items()
        names = list(self.checked_layers)
        if not names:
            row = self.grass_mdi.grass_layers.currentRow()
            if row >= 0:
                cb = self.grass_mdi.grass_layers.cellWidget(row, 0)
                if cb is not None:
                    names = [cb.text()]
        if not names:
            report.setHtml("Check one or more GRASS rasters in the table first.")
            return
        endpoint, api_key, env_id = self.parent.grass_dialog.connection()
        if not env_id:
            report.setHtml("<b>No GRASS environment selected.</b>")
            return
        added = self._add_rasters_to_qgis(endpoint, api_key, env_id, names)
        report.setHtml("Added to QGIS: " + (", ".join(added) if added else "(none)"))

    def _add_rasters_to_qgis(self, endpoint, api_key, env_id, names):
        """Download each named GRASS raster via WCS and add it to the project."""
        import os
        import tempfile
        out_dir = os.path.join(tempfile.gettempdir(), "groundtruther_grass")
        os.makedirs(out_dir, exist_ok=True)
        added = []
        for name in names:
            try:
                data = grass_api.wcs_geotiff(endpoint, api_key, env_id, name)
            except GrassApiError as exc:
                log_exception(f"add_to_qgis: fetch '{name}'", exc, warn=True)
                continue
            path = os.path.join(out_dir, f"{env_id[:8]}_{name}.tif")
            with open(path, "wb") as fh:
                fh.write(data)
            rlayer = QgsRasterLayer(path, name, "gdal")
            if rlayer.isValid():
                QgsProject.instance().addMapLayer(rlayer)
                added.append(name)
            else:
                QgsMessageLog.logMessage(
                    f"raster '{name}' downloaded but invalid: {path}",
                    'GroundTruther', Qgis.Warning)
        return added

    def _init_module_window(self, widget, title):
        """Present a module runner as an independent, movable, resizable window.

        Replaces the old QMdiSubWindow (frameless + trapped in the MDI area):
        a top-level Qt.Window has a title bar to drag, can be moved anywhere on
        screen, and resizes — while the runner's internal QScrollArea handles
        long module forms instead of overflowing the MDI border.
        """
        widget.setWindowFlags(Qt.WindowType(1))   # Qt.Window — top-level, framed
        widget.setWindowTitle(title)
        widget.resize(480, 640)
        widget.hide()

    @staticmethod
    def _toggle_window(window, refresh):
        if window.isVisible():
            window.hide()
        else:
            refresh()
            window.show()
            window.raise_()
            window.activateWindow()

    def view_r_gemorphon(self, module=None):
        self._toggle_window(self.r_gemorphon_window, self.r_gemorphon.get_rvr_list)

    def view_r_paramscale(self, module=None):
        self._toggle_window(self.r_paramscale_window, self.r_paramscale.get_rvr_list)

    def view_r_grm_lsi(self, module=None):
        self._toggle_window(self.r_grm_lsi_window, self.r_grm_lsi.get_rvr_list)
            
    
        
    def set_mdi_view(self, index):
        if self.mdi_view.itemText(index) == 'Cascade':
            self.grass_mdi.grassTools.cascadeSubWindows()
        if self.mdi_view.itemText(index) == 'Tiled':
            self.grass_mdi.grassTools.tileSubWindows()
        if self.mdi_view.itemText(index) == 'Minimize':
            for i in self.grass_mdi.grassTools.subWindowList():
                if i.isVisible():
                    i.showMinimized()
        if self.mdi_view.itemText(index) == 'Close':
            for i in self.grass_mdi.grassTools.subWindowList():
                if i.isVisible():
                    i.hide()
            
            
