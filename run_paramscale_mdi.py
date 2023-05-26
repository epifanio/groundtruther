from PyQt5.QtWidgets import QDialog, QWidget
from PyQt5.QtCore import QRunnable, pyqtSlot, QThreadPool, pyqtSignal, QObject, pyqtSlot
# from pygui.geomorphon_gui import GeoMorphon
from groundtruther.pygui.Ui_paramscale_ui import Ui_paramscale


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

class ParamScaleWidget(QWidget, Ui_paramscale):
    """docstring"""

    def __init__(self, parent):
        self.parent = parent
        super(ParamScaleWidget, self).__init__(parent)
        # QWidget.__init__(self, parent)
        self.threadpool = QThreadPool()
        print("Multithreading with maximum %d threads" %
              self.threadpool.maxThreadCount())
        self.setupUi(self)
        self.module_name = 'paramscale'
        self.reload_layers.clicked.connect(self.get_rvr_list)
        #self.exit.clicked.connect(self.close)
        self.run.clicked.connect(self.exec_paramscale)
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
        actual_item = self.input.currentText()
        self.input.clear()
        self.input.addItems(response.json()['data']['raster'])
        self.input.setCurrentText(actual_item)
  
    def exec_paramscale(self):
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
        if self.flag_c.isChecked():
            flag_c = True
        else:
            flag_c = False
        params = {
            'location_name':  self.gisenv['LOCATION_NAME'],
            'mapset_name': self.gisenv['MAPSET'],
            'gisdb': self.gisenv['GISDBASE'],
            'input': self.input.currentText(),
            # 'forms': self.forms.text(),
            'slope_tolerance': self.slope_tolerance.text(),
            'curvature_tolerance': self.curvature_tolerance.text(),
            'size': self.size.value(),
            'exponent': self.exponent.text(),
            'zscale': self.zscale.text(),
            'c': flag_c,
            'overwrite': overwrite,
            'predictors': derivatives,
            'output': self.output_suffix.text(),
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
        