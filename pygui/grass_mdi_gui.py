#!/usr/bin/env python
import sys

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

from groundtruther.pygui.Ui_grass_mdi_ui import Ui_grass_mdi

from groundtruther.run_geomorphon_mdi import GeoMorphonWidget
from groundtruther.run_paramscale_mdi import ParamScaleWidget
from groundtruther.run_grm_lsi_mdi import GrmLsiWidget


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



        self.r_gemorphon = GeoMorphonWidget(self.parent)    
        self.r_gemorphon_window = QMdiSubWindow()
        self.r_gemorphon_window.setWindowTitle("r.geomorphon")
        self.r_gemorphon_window.setWidget(self.r_gemorphon)
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
        
        # self.setWindowTitle("MDI demo")
        # self.show()
        
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
            
            
