from PyQt5.QtCore import QRegExp
from PyQt5.QtGui import QRegExpValidator, QPalette, QColor
from PyQt5.QtWidgets import QDialog, QFileDialog, QMessageBox, QButtonGroup, QFrame
from pygui.grass_settings_gui import GrassSettings

import requests
from requests.exceptions import ConnectionError
from epsg_list import codelist
import json

from search_epsg import SearchEpsgDialog


class GrassConfigDialog(QDialog, GrassSettings):
    """docstring"""

    def __init__(self, parent=None):
        super().__init__()
        QDialog.__init__(self, parent)
        self.setupUi(self)
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
        print(self.grass_location_list.itemText(index))
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
        headers = {
            'accept': 'application/json',
        }

        params = {
            'location_name': self.grass_location_list2.currentText(),
            'mapset_name': self.new_mapset.text(),
            'gisdb': self.grass_gisdb.text(),
            'overwrite_mapset': 'false',
        }

        response = requests.get(
            f'{endpoint}/api/create_mapset', params=params, headers=headers)
        self.command_output.setText(json.dumps(
            response.json(), sort_keys=True, indent=4))
        self.set_status_color(response.json()['status'])
        return response.json()

    def get_location_list(self):
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
                f'{endpoint}/api/get_location_list', params=params, headers=headers)
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
        print('locationlist', locationlist)
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
            print(locationlist['status'])

    def create_new_grass_location(self):
        print('create new grass location')
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
        headers = {
            'accept': 'application/json',
        }

        params = {
            'location_name': self.new_location_name.text(),
            'mapset_name': 'PERMANENT',
            'gisdb': self.grass_gisdb.text(),
            'epsg_code': self.epsg_code.currentText(),
            'overwrite_location': 'false',
            'overwrite_mapset': 'false',
        }
        response = requests.get(
            f'{endpoint}/api/create_location_epsg', params=params, headers=headers)
        print(response.json())
        self.command_output.setText(json.dumps(
            response.json(), sort_keys=True, indent=4))
        self.set_status_color(response.json()['status'])
        return response.json()

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
            print(response.json())
            self.command_output.setText(json.dumps(
                response.json(), sort_keys=True, indent=4))
            self.set_status_color(response.json()['status'])
            return response.json()
        except FileNotFoundError as error:
            self.command_output.setText(json.dumps(
                {'status': 'FAILED', 'data': str(error)}, sort_keys=True, indent=4))
            self.set_status_color('FAILED')
            return {'status': 'FAILED', 'data': str(error)}

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
            print('set grass location')
            print(response.json())

            self.command_output.setText(json.dumps(
                response.json(), sort_keys=True, indent=4))
            self.set_status_color(response.json()['status'])
            if response.json()['status'] == 'SUCCESS':
                self.grassenabled = True
            else:
                self.update_location()
                self.grassenabled = False
            return response.json()
        except ConnectionError as error:
            self.grassenabled = False
            # self.update_location()
            return {'status': 'FAILED', 'data': error}

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
            print(fileName)
            # should first check if the file is a valid gereof file
            # try with gdal open?
            self.georef_file.setText(fileName)
