from PyQt5.QtCore import QRegExp
from PyQt5.QtGui import QRegExpValidator, QPalette, QColor
from PyQt5.QtWidgets import QDialog, QFileDialog, QMessageBox, QButtonGroup, QFrame
from pygui.grass_settings_gui import GrassSettings

import requests
from requests.exceptions import ConnectionError
from epsg_list import codelist
import json

from qgis.core import Qgis, QgsMessageLog

from search_epsg import SearchEpsgDialog

# from configure import get_settings
from groundtruther.config.config import config

from groundtruther.configure import load_config, log_exception

class GrassConfigDialog(QDialog, GrassSettings):
    """docstring"""

    def __init__(self, parent=None):
        super().__init__()
        QDialog.__init__(self, parent)
        self.setupUi(self)
        self.parent = parent
        # access to the settings
        self.config = config
        # Use load_config (no validation) so init never triggers error dialogs.
        # GrassConfigDialog only needs the endpoint URL, not file-path fields.
        self.settings = load_config(self.config) or {}
        endpoint = self.settings.get("Processing", {}).get("grass_api_endpoint", "")
        self.grass_api_endpoint.setText(endpoint)
        #
        self.searchepsg_dialog = SearchEpsgDialog()
        self.search_epsg.clicked.connect(self.show_searchepsg_dialog)
        self.command_output.hide()
        self.grass_new_location_groupbox.hide()
        self.grass_new_mapset_groupbox.hide()
        self.new_grass_location_dialog.clicked.connect(
            self.show_hide_new_grass_location)

        self.show_output_log.clicked.connect(
            self.show_hide_output_log)

        self.set_location.clicked.connect(self.set_grass_location)
        self.set_georef_file.clicked.connect(self.openFileNameDialog)
        self.reload.clicked.connect(self.update_location)
        self.create_location.clicked.connect(self.create_new_grass_location)
        self.create_mapset.clicked.connect(self.create_new_grass_mapset)
        self.exit.clicked.connect(self.close)
        self.update_location()
        self.epsg_code.addItems(codelist)
        self.button_group = QButtonGroup(self)                     # <---
        self.button_group.setExclusive(True)
        self.button_group.addButton(self.choice_epsg)
        self.button_group.addButton(self.choice_georef)
        # connect item change to update location
        self.grass_location_list.currentIndexChanged.connect(
            self.update_mapset)
        self.choice_epsg.toggled.connect(self.enable_widget)
        self.choice_georef.toggled.connect(self.enable_widget)
        self.update_location()
        
        self.grassenabled = False

        # connect update mapset

    def show_searchepsg_dialog(self):
        """docstring"""
        self.searchepsg_dialog.exec_()

    def set_status_color(self, status):
        if status == "SUCCESS":
            self.frame.setStyleSheet("""
                QFrame {
                    border: 1px solid black;
                    border-radius: 1px;
                    background-color: rgb(51, 209, 122);
                    }
                """)
        else:
            self.frame.setStyleSheet("""
                QFrame {
                    border: 1px solid black;
                    border-radius: 1px;
                    background-color: rgb(237, 51, 59);
                    }
                """)

    def enable_widget(self):
        if self.choice_epsg.isChecked():
            self.georef_file.setEnabled(False)
            self.set_georef_file.setEnabled(False)
            self.epsg_code.setEnabled(True)
        if self.choice_georef.isChecked():
            self.epsg_code.setEnabled(False)
            self.georef_file.setEnabled(True)
            self.set_georef_file.setEnabled(True)

    def update_mapset(self, index):
        QgsMessageLog.logMessage(f"update_mapset: {self.grass_location_list.itemText(index)}", 'GroundTruther', Qgis.Info)
        locationlist = self.get_location_list()
        if locationlist['status'] == 'SUCCESS':
            try:
                self.location_mapset_list.clear()
                self.location_mapset_list.addItems(
                    list(locationlist['data'][self.grass_location_list.itemText(index)]))
            except KeyError:
                pass
            # update mapset based on current index in location as key

    def create_new_grass_mapset(self):
        endpoint = self.grass_api_endpoint.text()
        headers = {'accept': 'application/json'}
        params = {
            'location_name': self.grass_location_list2.currentText(),
            'mapset_name': self.new_mapset.text(),
            'gisdb': self.grass_gisdb.text(),
            'overwrite_mapset': 'false',
        }
        try:
            response = requests.get(
                f'{endpoint}/api/create_mapset', params=params, headers=headers, timeout=30)
            payload = response.json()
        except ConnectionError as exc:
            log_exception("create_new_grass_mapset: connection error", exc, warn=True)
            payload = {'status': 'FAILED', 'data': str(exc)}
        except requests.exceptions.Timeout as exc:
            log_exception("create_new_grass_mapset: timeout", exc, warn=True)
            payload = {'status': 'FAILED', 'data': 'Request timed out'}
        except ValueError as exc:
            log_exception("create_new_grass_mapset: invalid JSON response", exc)
            payload = {'status': 'FAILED', 'data': 'Invalid JSON response'}
        self.command_output.setText(json.dumps(payload, sort_keys=True, indent=4))
        self.set_status_color(payload['status'])
        return payload

    def get_location_list(self):
        """_summary_
         get the list of locations from the grass api
        Returns:
            _type_: _description_
        """
        endpoint = self.grass_api_endpoint.text()
        grass_gisdb = self.grass_gisdb.text()
        headers = {
            'accept': 'application/json',
        }
        params = {
            'gisdb': grass_gisdb,
        }
        try:
            response = requests.get(
                f'{endpoint}/api/get_location_list', params=params, headers=headers, timeout=30)
            self.command_output.setText(json.dumps(
                response.json(), sort_keys=True, indent=4))
            self.set_status_color(response.json()['status'])
            return response.json()
        except ConnectionError as error:
            self.command_output.setText(json.dumps(
                {'status': 'FAILED', 'data': str(error)}, sort_keys=True, indent=4))
            self.set_status_color('FAILED')
            return {'status': 'FAILED', 'data': str(error)}

    def update_location(self):
        locationlist = self.get_location_list()
        if locationlist['status'] == 'SUCCESS':
            self.grass_location_list.clear()
            self.grass_location_list.addItems(
                list(locationlist['data'].keys()))
            self.grass_location_list2.clear()
            self.grass_location_list2.addItems(
                list(locationlist['data'].keys()))
        else:
            self.grass_location_list.clear()
            self.grass_location_list2.clear()
            QgsMessageLog.logMessage(f"update_location failed: {locationlist['status']}", 'GroundTruther', Qgis.Warning)

    def create_new_grass_location(self):
        QgsMessageLog.logMessage("create_new_grass_location triggered", 'GroundTruther', Qgis.Info)
        if self.choice_epsg.isChecked():
            results = self.create_location_epsg()
        else:
            results = self.create_location_georef()
        if results['status'] == 'SUCCESS':
            self.update_location()
        # check if one of the two option is satisfied [epsg code or georef]
        # and that the name and gisdb are assigned correctly
        # run the api to create a location
        # if success, add new entry to the combo box

    def create_location_epsg(self):
        endpoint = self.grass_api_endpoint.text()
        headers = {'accept': 'application/json'}
        params = {
            'location_name': self.new_location_name.text(),
            'mapset_name': 'PERMANENT',
            'gisdb': self.grass_gisdb.text(),
            'epsg_code': self.epsg_code.currentText(),
            'overwrite_location': 'false',
            'overwrite_mapset': 'false',
        }
        try:
            response = requests.get(
                f'{endpoint}/api/create_location_epsg', params=params, headers=headers, timeout=60)
            payload = response.json()
        except ConnectionError as exc:
            log_exception("create_location_epsg: connection error", exc, warn=True)
            payload = {'status': 'FAILED', 'data': str(exc)}
        except requests.exceptions.Timeout as exc:
            log_exception("create_location_epsg: timeout", exc, warn=True)
            payload = {'status': 'FAILED', 'data': 'Request timed out'}
        except ValueError as exc:
            log_exception("create_location_epsg: invalid JSON response", exc)
            payload = {'status': 'FAILED', 'data': 'Invalid JSON response'}
        self.command_output.setText(json.dumps(payload, sort_keys=True, indent=4))
        self.set_status_color(payload['status'])
        return payload

    def create_location_georef(self):
        endpoint = self.grass_api_endpoint.text()
        headers = {
            'accept': 'application/json',
            # requests won't add a boundary if this header is set when you pass files=
            # 'Content-Type': 'multipart/form-data',
        }
        params = {
            'location_name': self.new_location_name.text(),
            'mapset_name': 'PERMANENT',
            'gisdb': self.grass_gisdb.text(),
            'overwrite_location': 'false',
            'overwrite_mapset': 'false',
            'output_raster_layer': self.layer_name.text(),
        }
        try:
            files = {
                'georef': open(self.georef_file.text(), 'rb'),
            }
            response = requests.post(
                f'{endpoint}/api/create_location_file', params=params, headers=headers, files=files)
            QgsMessageLog.logMessage(f"create_location_georef response: {response.json()}", 'GroundTruther', Qgis.Info)
            self.command_output.setText(json.dumps(
                response.json(), sort_keys=True, indent=4))
            self.set_status_color(response.json()['status'])
            return response.json()
        except FileNotFoundError as exc:
            log_exception("create_location_georef: georef file not found", exc, warn=True)
            self.command_output.setText(json.dumps(
                {'status': 'FAILED', 'data': str(exc)}, sort_keys=True, indent=4))
            self.set_status_color('FAILED')
            return {'status': 'FAILED', 'data': str(exc)}

    def set_grass_location(self):
        endpoint = self.grass_api_endpoint.text()
        headers = {
            'accept': 'application/json',
        }

        params = {
            'location_name': self.grass_location_list.currentText(),
            'mapset_name': self.location_mapset_list.currentText(),
            'gisdb': self.grass_gisdb.text(),
        }
        try:
            response = requests.get(
                f'{endpoint}/api/gisenv', params=params, headers=headers)
            QgsMessageLog.logMessage(f"set_grass_location response: {response.json()}", 'GroundTruther', Qgis.Info)

            self.command_output.setText(json.dumps(
                response.json(), sort_keys=True, indent=4))
            self.set_status_color(response.json()['status'])
            if response.json()['status'] == 'SUCCESS':
                self.grassenabled = True
            else:
                self.update_location()
                self.grassenabled = False
            return response.json()
        except (ConnectionError, requests.exceptions.Timeout) as error:
            self.grassenabled = False
            return {'status': 'FAILED', 'data': str(error)}

    def show_hide_output_log(self):
        """docstring"""
        if self.command_output.isVisible():
            self.command_output.hide()
        else:
            self.command_output.show()

    def show_hide_new_grass_location(self):
        """docstring"""
        if self.grass_new_location_groupbox.isVisible():
            self.grass_new_location_groupbox.hide()
            self.grass_new_mapset_groupbox.hide()
        else:
            self.grass_new_location_groupbox.show()
            self.grass_new_mapset_groupbox.show()

    def openFileNameDialog(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        fileName, _ = QFileDialog.getOpenFileName(
            self, "QFileDialog.getOpenFileName()", "", "All Files (*);;Tif Files (*.tif)", options=options)
        if fileName:
            QgsMessageLog.logMessage(f"georef file selected: {fileName}", 'GroundTruther', Qgis.Info)
            # should first check if the file is a valid gereof file
            # try with gdal open?
            self.georef_file.setText(fileName)
