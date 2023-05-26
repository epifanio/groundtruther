from PyQt5.QtWidgets import QDialog, QWidget
from PyQt5.QtCore import QRunnable, pyqtSlot, QThreadPool, pyqtSignal, QObject, pyqtSlot
# from pygui.geomorphon_gui import GeoMorphon
from groundtruther.pygui.Ui_geomorphon_ui import Ui_geomorphon


import requests
from requests.exceptions import ConnectionError
import json

import random
from time import sleep

from qgis.core import (QgsApplication, QgsTask, QgsMessageLog, Qgis)
MESSAGE_CATEGORY = 'TaskFromFunction'

import requests
from qgis.core import (Qgis, QgsApplication, QgsMessageLog, QgsTask, QgsRasterLayer)
import uuid
from osgeo import gdal


class WorkerSignals(QObject):
    module_output = pyqtSignal(object)
    
class Worker(QRunnable):
    '''
    Worker thread
    '''

    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()
        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signal = WorkerSignals()
        # self.geomorphon_dialog = GeoMorphonDialog()

    @pyqtSlot()
    def run(self):
        '''
        Initialise the runner function with passed args, kwargs.
        '''
        returned_item = self.fn(*self.args, **self.kwargs)
        # print(returned_item)
        self.signal.module_output.emit(returned_item)

class GeoMorphonWidget(QWidget, Ui_geomorphon):
    """docstring"""

    def __init__(self, parent):
        self.parent = parent
        super(GeoMorphonWidget, self).__init__(parent)
        # QWidget.__init__(self, parent)
        self.threadpool = QThreadPool()
        print("Multithreading with maximum %d threads" %
              self.threadpool.maxThreadCount())
        self.setupUi(self)
        self.module_name = 'geomorphon'
        self.reload_layers.clicked.connect(self.get_rvr_list)
        #self.exit.clicked.connect(self.close)
        self.run.clicked.connect(self.exec_geomorphon)
        # self.get_rvr_list()
        # print(self.parent)
        
        
    def get_rvr_list(self):
        self.gisenv = self.parent.grass_dialog.set_grass_location()['data']['gisenv']
        headers = {
            'accept': 'application/json',
            'content-type': 'application/x-www-form-urlencoded',
            }
        params = {
            'location_name':  self.gisenv['LOCATION_NAME'],
            'mapset_name':  self.gisenv['MAPSET'],
            'gisdb':  self.gisenv['GISDBASE'],
        }

        response = requests.get('http://localhost/api/get_rvg_list', params=params, headers=headers)
        actual_item = self.elevation.currentText()
        self.elevation.clear()
        self.elevation.addItems(response.json()['data']['raster'])
        self.elevation.setCurrentText(actual_item)
  
    def exec_geomorphon(self):
        headers = {
            'accept': 'application/json',
            'content-type': 'application/x-www-form-urlencoded',
        }

        if self.derivatives.isChecked():
            derivatives = True
        else:
            derivatives = False
        if self.overwrite.isChecked():
            overwrite = True
        else:
            overwrite = False
        if self.flag_m.isChecked():
            flag_m = True
        else:
            flag_m = False
        if self.flag_e.isChecked():
            flag_e = True
        else:
            flag_e = False
        params = {
            'location_name':  self.gisenv['LOCATION_NAME'],
            'mapset_name': self.gisenv['MAPSET'],
            'gisdb': self.gisenv['GISDBASE'],
            'elevation': self.elevation.currentText(),
            # 'forms': self.forms.text(),
            'search': self.search.value(),
            'skip': self.skip.value(),
            'flat': self.flat.text(),
            'dist': self.dist.text(),
            'm': flag_m,
            'e': flag_e,
            'overwrite': overwrite,
            'predictors': derivatives,
            'output_suffix': self.output_suffix.text(),
        }
        if self.parent.region_response:
            params['region'] = (',').join([self.parent.region_response['north'], 
                                self.parent.region_response['south'], 
                                self.parent.region_response['west'], 
                                self.parent.region_response['east']])
        self.parent.grass_mdi.gis_tool_report.setHtml(str('... running ...'))
        self.worker = Worker(self.run_grassapi, headers, params)
        self.worker.signal.module_output.connect(self.show_module_output_mem)
        self.threadpool.start(self.worker)
        
    @pyqtSlot(dict)
    def show_module_output(self, module_output):
        self.parent.grass_mdi.gis_tool_report.setHtml(str(module_output))
        if self.add_output.isChecked():
            with open(f'{self.output_suffix.text()}.tif', 'wb') as f:
                f.write(self.response.content)
                f.flush()
                layer_name = str(uuid.uuid1())
                newsrc = f'/vsimem/newsrc_{layer_name}'
                ds = gdal.Warp(newsrc, f'{self.output_suffix.text()}.tif', format='GTiff',
                            dstSRS=f"EPSG:4326")
                
                rlayer = QgsRasterLayer(newsrc, layer_name, 'gdal')
                self.parent.project.instance().addMapLayer(rlayer)
        #self.parent.grass_mdi.gis_tool_report.setHtml(str(self.returned_item))
        
        
    @pyqtSlot(dict)
    def show_module_output_mem(self, module_output):
        #print(module_output)
        #print(self.parent)
        # print(self.parent.grass_dialog.set_grass_location())
        self.parent.grass_mdi.gis_tool_report.setHtml(str(module_output))
        if self.add_output.isChecked():
            layer_name = str(uuid.uuid1())
            newsrc = f'/vsimem/newsrc_{layer_name}'
            gdal.FileFromMemBuffer(newsrc, self.response.content)
            ds = gdal.Open(newsrc)
            layer_name_warp = str(uuid.uuid1())
            newsrc_warp = f'/vsimem/newsrc_{layer_name_warp}'
            gdal.Warp(newsrc_warp, ds, dstSRS=f"EPSG:4326")
            rlayer = QgsRasterLayer(newsrc_warp, layer_name_warp, 'gdal')
            gdal.Unlink(newsrc) 
            self.parent.project.instance().addMapLayer(rlayer)
        self.get_rvr_list()
            

        #self.parent.grass_mdi.gis_tool_report.setHtml(str(self.returned_item))
        
        
    def run_grassapi(self, headers, params):
        self.response = requests.post(f'http://localhost/api/{self.module_name}', params=params, headers=headers)
        try:
            self.returned_item = self.response.json()
        except:
            self.returned_item = {'status': 'SUCCESS'}
        return self.returned_item
        