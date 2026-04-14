from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import QRunnable, pyqtSlot, QThreadPool, pyqtSignal, QObject
from groundtruther.pygui.Ui_grm_lsi_ui import Ui_grm_lsi

import requests
from qgis.core import Qgis, QgsMessageLog, QgsTask, QgsRasterLayer
from groundtruther.configure import log_exception
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

class GrmLsiWidget(QWidget, Ui_grm_lsi):
    """docstring"""

    def __init__(self, parent):
        self.parent = parent
        super(GrmLsiWidget, self).__init__(parent)
        # QWidget.__init__(self, parent)
        self.threadpool = QThreadPool()
        QgsMessageLog.logMessage(
            f"GrmLsi: thread pool ready ({self.threadpool.maxThreadCount()} threads)",
            'GroundTruther', Qgis.Info)
        self.setupUi(self)
        self.add_output.hide()
        self.module_name = 'GRMLSI'
        self.reload_layers.clicked.connect(self.get_rvr_list)
        #self.exit.clicked.connect(self.close)
        self.run.clicked.connect(self.exec_grm)
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

        headers = {
            'accept': 'application/json',
            'content-type': 'application/x-www-form-urlencoded',
        }
        params = {
            'location_name': self.gisenv['LOCATION_NAME'],
            'mapset_name':   self.gisenv['MAPSET'],
            'gisdb':         self.gisenv['GISDBASE'],
        }
        endpoint = self.parent.settings['Processing']['grass_api_endpoint']
        try:
            response = requests.get(
                f'{endpoint}/api/get_rvg_list', params=params, headers=headers, timeout=30)
            raster_list = response.json().get('data', {}).get('raster', [])
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
            QgsMessageLog.logMessage(
                f"GRASS API unreachable: {exc}", 'GroundTruther', Qgis.Warning)
            return
        except (ValueError, KeyError) as exc:
            QgsMessageLog.logMessage(
                f"Unexpected GRASS API response in get_rvr_list: {exc}",
                'GroundTruther', Qgis.Warning)
            return

        actual_item = self.elevation.currentText()
        self.elevation.clear()
        self.elevation.addItems(raster_list)
        self.elevation.setCurrentText(actual_item)
  
    def exec_grm(self):
        if not hasattr(self, 'gisenv'):
            QgsMessageLog.logMessage(
                "Click 'Reload' to load the raster list before running.",
                'GroundTruther', Qgis.Warning)
            return
        headers = {
            'accept': 'application/json',
            'content-type': 'application/x-www-form-urlencoded',
        }

        params = {
            'location_name': self.gisenv['LOCATION_NAME'],
            'mapset_name': self.gisenv['MAPSET'],
            'gisdb': self.gisenv['GISDBASE'],
            'elevation': self.elevation.currentText(),
            'swc_search': self.swc_search.value(),
            'swc_skip': self.swc_skip.value(),
            'swc_flat': self.swc_flat.text(),
            'swc_dist': self.swc_dist.text(),
            'iter_thin': self.iter_thin.text(),
            'swc_area_lesser': self.swc_area_lesser.text(),
            'generalize_method': self.generalize_method.currentText(),
            'generalize_threshold': self.generalize_threshold.text(),
            'sw_search': self.sw_search.value(),
            'sw_skip': self.sw_skip.value(),
            'sw_flat': self.sw_flat.text(),
            'sw_dist': self.sw_dist.text(),
            'sw_area_lesser': self.sw_area_lesser.text(),
            'buffer_distance': self.buffer_distance.text(),
            'transect_split_length': self.transect_split_length.text(),
            'point_dmax': self.point_dmax.text(),
            'clean': 'false',
            'vclean_rmdangle_threshold': self.vclean_rmdangle_threshold.text(),
            'vclean_rmarea_threshold': self.vclean_rmarea_threshold.text(),
            'transect_side_distances': self.transect_side_distances.text()
        }

        if self.parent.region_response:
            params['region'] = (',').join([self.parent.region_response['north'], 
                                self.parent.region_response['south'], 
                                self.parent.region_response['west'], 
                                self.parent.region_response['east']])
        self.parent.grassWidgetContents.grass_mdi.gis_tool_report.setHtml(str('... running ...'))
        # print(headers, params)
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
        if module_output.get('status') == 'FAILED':
            self.parent.grassWidgetContents.grass_mdi.gis_tool_report.setHtml(
                f"<b>GRASS module failed:</b> {module_output.get('data', module_output)}"
            )
            return
        # dict_keys(['max_dist',
        #            'max_3d_dist', 
        #            'H', 
        #            'W', 
        #            'side_a', 
        #            'side_b', 
        #            'mean_displacement', 
        #            'encoded_profile_string', 
        #            'encoded_profiles_string', 
        #            'encoded_swc_string', 
        #            'img_profile_map'])
        #self.parent.grass_mdi.gis_tool_report.setHtml(str(f"""<img src="data:image/png;base64, {module_output['img_profile_map']}">"""))
        self.parent.grassWidgetContents.grass_mdi.gis_tool_report.setHtml(f"""<table>
            <tbody>
                <tr>
                <th>Length</th>
                <td>{module_output['max_dist']}</td>
                </tr>
                <tr>  
                <th>Length 3D</th>
                <td>{module_output['max_3d_dist']}</td>
                </tr>
                <tr>  
                <th>Heigth</th>
                <td>{module_output['H']}</td>
                </tr>
                <tr>  
                <th>Width</th>
                <td>{module_output['W']}</td>
                </tr>
                <tr>  
                <th>mean_displacement</th>
                <td>{module_output['mean_displacement']}</td>
                </tr>
            </tbody>
            </table>
            <br>
            <img src="data:image/png;base64, {module_output["encoded_profile_string"]}">
            <br>
            <img src="data:image/png;base64, {module_output["encoded_profiles_string"]}">
            <br>
            <img src="data:image/png;base64, {module_output["encoded_swc_string"]}">
            <br>
            <img src="data:image/png;base64, {module_output["img_profile_map"]}">""")
        if self.add_output.isChecked():
            layer_name = str(uuid.uuid1())
            newsrc = f'/vsimem/newsrc_{layer_name}'
            # print("self.response.content : ", self.response.content.keys())
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
        try:
            self.response = requests.post(
                f'{endpoint}/api/{self.module_name}',
                headers=headers, params=params, timeout=300)
            self.returned_item = self.response.json()
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
            log_exception(f"run_grassapi({self.module_name}): network error", exc, warn=True)
            self.returned_item = {'status': 'FAILED', 'data': str(exc)}
        except ValueError as exc:
            log_exception(f"run_grassapi({self.module_name}): non-JSON response", exc, warn=True)
            self.returned_item = {'status': 'SUCCESS'}
        return self.returned_item
        