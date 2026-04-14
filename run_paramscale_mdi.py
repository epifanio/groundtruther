from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import QRunnable, pyqtSlot, QThreadPool, pyqtSignal, QObject
from groundtruther.pygui.Ui_paramscale_ui import Ui_paramscale

from qgis.core import Qgis, QgsMessageLog, QgsRasterLayer
from groundtruther.gt import grass_api
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
        QgsMessageLog.logMessage(
            f"ParamScale: thread pool ready ({self.threadpool.maxThreadCount()} threads)",
            'GroundTruther', Qgis.Info)
        self.setupUi(self)
        self.module_name = 'paramscale'
        self.reload_layers.clicked.connect(self.get_rvr_list)
        #self.exit.clicked.connect(self.close)
        self.run.clicked.connect(self.exec_paramscale)
        # self.get_rvr_list()
        # print(self.parent)
        
        
    def get_rvr_list(self):
        grass_settings = self.parent.grass_dialog.set_grass_location()
        if grass_settings.get('status') != 'SUCCESS':
            QgsMessageLog.logMessage(
                f"GRASS location unavailable: {grass_settings.get('data', '')}",
                'GroundTruther', Qgis.Warning,
            )
            return
        self.gisenv = grass_settings['data']['gisenv']
        endpoint = self.parent.settings['Processing']['grass_api_endpoint']
        raster_list = grass_api.get_raster_list(endpoint, self.gisenv)

        actual_item = self.input.currentText()
        self.input.clear()
        self.input.addItems(raster_list)
        self.input.setCurrentText(actual_item)
  
    def exec_paramscale(self):
        if not hasattr(self, 'gisenv'):
            QgsMessageLog.logMessage(
                "Click 'Reload' to load the raster list before running.",
                'GroundTruther', Qgis.Warning)
            return
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
        self.parent.grassWidgetContents.grass_mdi.gis_tool_report.setHtml(str('... running ...'))
        self.worker = Worker(self.run_grassapi, headers, params)
        self.worker.signal.module_output.connect(self.show_module_output_mem)
        self.threadpool.start(self.worker)
        
    @pyqtSlot(dict)
    def show_module_output(self, module_output):
        self.parent.grassWidgetContents.grass_mdi.gis_tool_report.setHtml(str(module_output))
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
        self.parent.grassWidgetContents.grass_mdi.gis_tool_report.setHtml(str(module_output))
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
        endpoint = self.parent.settings['Processing']['grass_api_endpoint']
        self.returned_item = grass_api.run_module(endpoint, self.module_name, params)
        return self.returned_item
        