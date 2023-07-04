#!/usr/bin/env python
import sys

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

from groundtruther.pygui.Ui_grass_mdi_ui import Ui_grass_mdi

from groundtruther.run_geomorphon_mdi import GeoMorphonWidget
from groundtruther.run_paramscale_mdi import ParamScaleWidget
from groundtruther.run_grm_lsi_mdi import GrmLsiWidget

from PyQt5.QtWidgets import QTableWidgetItem, QWidget, QCheckBox,  QMenu, QAction
import requests
class GrassLayerTableWidgetItem(QTableWidgetItem):
    def __init__(self, text, layer_enabled):
        super().__init__(text)
        self.layer_enabled = layer_enabled

class GrassMdi(QWidget, Ui_grass_mdi):
    def __init__(self, parent=None):
        super(GrassMdi, self).__init__(parent)
        self.setupUi(self)
        
        
class GrassTools(QMainWindow):
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
        
        self.mdi_view = QComboBox()
        self.moduleToolBar.addWidget(self.mdi_view)
        self.mdi_view.insertItems(1,["Tiled","Cascade","Minimize", "Close"])
        self.mdi_view.currentIndexChanged.connect(self.set_mdi_view)
        self.mdi_view.setToolTip("Change MDI view mode")
        
        self.grass_layers_view = QToolButton()
        grass_layers_view_icon = QIcon(":/icons/qtui/icons/table-list.svg")
        self.grass_layers_view.setToolTip("Show/Hide GRASS Layers")
        self.grass_layers_view.setIcon(grass_layers_view_icon)
        self.moduleToolBar.addWidget(self.grass_layers_view)
        self.grass_layers_view.clicked.connect(self.toggle_grass_layers_table)     



        self.r_gemorphon = GeoMorphonWidget(self.parent)    
        self.r_gemorphon_window = QMdiSubWindow()
        self.r_gemorphon_window.setWindowTitle("r.geomorphon")
        self.r_gemorphon_window.setWidget(self.r_gemorphon)
        self.r_gemorphon_window.setToolTip("r.geomorphon")
        self.grass_mdi.grassTools.addSubWindow(self.r_gemorphon_window)
        self.r_gemorphon_window.setWindowFlags(Qt.WindowMinimizeButtonHint|Qt.WindowMaximizeButtonHint)
        self.r_gemorphon_window.hide()
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
        self.r_paramscale_window = QMdiSubWindow()
        self.r_paramscale_window.setWindowTitle("r.param.scale")
        self.r_paramscale_window.setWidget(self.r_paramscale)
        self.r_paramscale_window.setToolTip("r.param.scale")
        self.grass_mdi.grassTools.addSubWindow(self.r_paramscale_window)
        self.r_paramscale_window.setWindowFlags(Qt.WindowMinimizeButtonHint|Qt.WindowMaximizeButtonHint)
        self.r_paramscale_window.hide()
        self.r_paramscale.exit.clicked.connect(self.view_r_paramscale)
        paramscale_icon_path = ':/icons/qtui/icons/element-cell.gif'
        paramscale_icon = QIcon(paramscale_icon_path)
        paramscale_action = QAction(paramscale_icon, self.tr(u'r.param.scale'), self)
        #
        paramscale_action.triggered.connect(self.view_r_paramscale)
        paramscale_action.setEnabled(True)
        paramscale_action.setCheckable(True)
        
        
        
        self.r_grm_lsi = GrmLsiWidget(self.parent)    
        self.r_grm_lsi_window = QMdiSubWindow()
        self.r_grm_lsi_window.setWindowTitle("r.grm.lsi")
        self.r_grm_lsi_window.setWidget(self.r_grm_lsi)
        self.r_grm_lsi_window.setToolTip("r.grm.lsi")
        self.grass_mdi.grassTools.addSubWindow(self.r_grm_lsi_window)
        #self.r_grm_lsi_window.setWindowTitle("r.grm.lsi")
        self.r_grm_lsi_window.setWindowFlags(Qt.WindowMinimizeButtonHint|Qt.WindowMaximizeButtonHint)
        self.r_grm_lsi_window.hide()
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
        # self.grassWidgetContents.addToolBar(Qt.LeftToolBarArea, helpToolBar)
        
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
        
        self.grass_mdi.grass_layers.setContextMenuPolicy(Qt.CustomContextMenu)
        self.grass_mdi.grass_layers.customContextMenuRequested.connect(self.show_context_menu)
        # self.grass_mdi.grass_layers.viewport().customContextMenuRequested.connect(self.show_context_menu)

        # self.setWindowTitle("MDI demo")
        # self.show()
        
    def show_context_menu(self, position):
        indexes = self.grass_mdi.grass_layers.selectedIndexes()
        if indexes:
            menu = QMenu(self)
            delete_action = QAction("Delete Row", self)
            delete_action.triggered.connect(self.delete_row)
            menu.addAction(delete_action)
            menu.exec_(self.grass_mdi.grass_layers.viewport().mapToGlobal(position))
            
    def delete_row(self):
        # this is a placeholder for now
        # I want to add the following actions:
        # 1.: zoom to selected layer
        # 2.: add selected layer to map
        # 3.: set the GRASS region for selected layer
        # 4.: delete selected layer from GRASS DB
        # 5.: get layer history / metadata
        indexes = self.grass_mdi.grass_layers.selectedIndexes()
        if indexes:
            rows = set()
            for index in indexes:
                rows.add(index.row())
            for row in sorted(rows, reverse=True):
                self.grass_mdi.grass_layers.removeRow(row)
            
    def toggle_grass_layers_table(self):
        self.grass_mdi.grass_layers.setVisible(not self.grass_mdi.grass_layers.isVisible())
        self.grass_mdi.reload_grass_layers.setVisible(not self.grass_mdi.reload_grass_layers.isVisible())        
        self.grass_mdi.filterLineEdit_label.setVisible(not self.grass_mdi.filterLineEdit_label.isVisible())
        self.grass_mdi.filterLineEdit.setVisible(not self.grass_mdi.filterLineEdit.isVisible())

        # self.get_grass_layers()
        
    def load_grass_layers(self):
        self.grass_mdi.grass_layers.clear()
        grass_layers = self.get_grass_layers()
        # self.grass_mdi.grass_layers.addItems(grass_layers)
        self.populate_table(grass_layers)
        
    def populate_table(self, items):
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
        print(f'i got {result}')
        result_dict = {}
        for dictionary in result:
            key = next(iter(dictionary))  # Get the key of the first level dictionary
            value = dictionary[key]  # Get the sub-dictionary as the value
            result_dict[key] = value  
        for row in range(self.grass_mdi.grass_layers.rowCount()):
            checkbox_item = self.grass_mdi.grass_layers.cellWidget(row, 0)
            if checkbox_item.text() in result_dict:
                value_cell = GrassLayerTableWidgetItem(result_dict[checkbox_item.text()]['value'], checkbox_item.property("layer_enabled") )
                self.grass_mdi.grass_layers.setItem(row, 1, value_cell)
            
    def get_checked_items(self):
        print('getting list of checked items')
        self.checked_layers = []
        for row in range(self.grass_mdi.grass_layers.rowCount()):
            checkbox_item = self.grass_mdi.grass_layers.cellWidget(row, 0)
            if isinstance(checkbox_item, QCheckBox) and checkbox_item.isChecked():
                item = checkbox_item.text()
                self.checked_layers.append(item)
                
    def filter_table(self):
        filter_text = self.grass_mdi.filterLineEdit.text().strip().lower()
        print(self.grass_mdi.grass_layers.rowCount())
        for row in range(self.grass_mdi.grass_layers.rowCount()):
            checkbox_item = self.grass_mdi.grass_layers.cellWidget(row, 0)
            item = checkbox_item.text()
            row_text = item.lower() if item else ""
            print(row_text)
            if filter_text in row_text:
                self.grass_mdi.grass_layers.setRowHidden(row, False)
            else:
                self.grass_mdi.grass_layers.setRowHidden(row, True)

        
    def get_grass_layers(self):
        self.grass_dialog = self.parent.grass_dialog
        grass_settings = self.grass_dialog.set_grass_location()
        self.settings = self.parent.settings
        self.grass_api_endpoint = self.settings["Processing"]["grass_api_endpoint"]
        if grass_settings['status'] == 'SUCCESS':
            grass_gisenv = grass_settings['data']['gisenv']
        headers = {
            'accept': 'application/json',
            'Content-Type': 'application/json',
        }
        params = {
            'location_name': grass_gisenv['LOCATION_NAME'],
            'mapset_name': grass_gisenv['MAPSET'],
            'gisdb': grass_gisenv['GISDBASE'],
            }
        # response = requests.get('https://grassapi.wps.met.no/api/get_rvg_list', params=params, headers=headers)
        response = requests.get(
            f'{self.grass_api_endpoint}/api/get_rvg_list',params=params, headers=headers, timeout=60)
        grass_layers = response.json()['data']['raster']
        print(grass_layers)
        return grass_layers    
        # print(self.settings, grass_settings)
        
        
    def reload_parent_objects(self):
        self.grass_dialog = self.parent.grass_dialog
        self.settings = self.parent.settings
        self.region_response = self.parent.region_response
        self.project = self.parent.project
        print('region_response:', self.region_response)
    
    def onZoomInClicked(self):
        self.grass_mdi.gis_tool_report.zoomIn(1)

    def onZoomOutClicked(self):
        self.grass_mdi.gis_tool_report.zoomOut(1)
    
    def onClearClicked(self):
        self.grass_mdi.gis_tool_report.clear()

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
        if self.mdi_view.itemText(index) == 'Cascade':
            self.grass_mdi.grassTools.cascadeSubWindows()
        if self.mdi_view.itemText(index) == 'Tiled':
            self.grass_mdi.grassTools.tileSubWindows()
        if self.mdi_view.itemText(index) == 'Minimize':
            for i in self.grass_mdi.grassTools.subWindowList():
                print(i)
                if i.isVisible():
                    #i.hide()
                    i.showMinimized()
        if self.mdi_view.itemText(index) == 'Close':
            for i in self.grass_mdi.grassTools.subWindowList():
                print(i)
                if i.isVisible():
                    i.hide()
            
            
