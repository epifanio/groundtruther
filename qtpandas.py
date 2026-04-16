#!/usr/bin/env python
import sys


import sys
import pandas as pd
from qgis.PyQt.QtWidgets import QApplication, QTableView
from qgis.PyQt.QtCore import QAbstractTableModel, Qt, pyqtProperty


class pandasModel(QAbstractTableModel):
    def __init__(self, data):
        QAbstractTableModel.__init__(self)
        self._data = data

    def rowCount(self, parent=None):
        return self._data.shape[0]

    def columnCount(self, parnet=None):
        return self._data.shape[1]

    def data(self, index, role=Qt.ItemDataRole(0)):
        if index.isValid():
            if role == Qt.ItemDataRole(0):
                return str(self._data.iloc[index.row(), index.column()])
        return None

    def headerData(self, col, orientation, role):
        if orientation == Qt.Orientation(1) and role == Qt.ItemDataRole(0):
            return self._data.columns[col]
        return None
