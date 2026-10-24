#!/usr/bin/env python
# GroundTruther — a toolset for seafloor characterization
#
# Copyright (C) 2023-2026 Massimo Di Stefano <epiesasha@me.com>
# https://github.com/epifanio/groundtruther
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Thin Qt adapter that exposes a pandas DataFrame as a QAbstractTableModel.

Usage::

    model = pandasModel(df)
    table_view.setModel(model)

Note: ``Qt.ItemDataRole(0)`` is ``DisplayRole``; ``Qt.Orientation(1)`` is
``Horizontal``.  The integer-constructor form is required because QGIS 4's
``qgis.PyQt`` bridge does not expose Qt enum inner-classes in the scoped
attribute form (e.g. ``Qt.ItemDataRole.DisplayRole`` fails at runtime).
"""
import sys

import pandas as pd
from qgis.PyQt.QtWidgets import QApplication, QTableView
from qgis.PyQt.QtCore import QAbstractTableModel, Qt, pyqtProperty


class pandasModel(QAbstractTableModel):
    """Read-only Qt table model backed by a pandas DataFrame.

    Only ``DisplayRole`` data is exposed; the model is not editable.
    """

    def __init__(self, data):
        """Initialise with a pandas DataFrame.

        Parameters
        ----------
        data:
            The DataFrame to display.  The model holds a reference — it does
            not copy the data.
        """
        QAbstractTableModel.__init__(self)
        self._data = data

    def rowCount(self, parent=None):
        """Return the number of rows (DataFrame rows)."""
        return self._data.shape[0]

    def columnCount(self, parnet=None):
        """Return the number of columns (DataFrame columns)."""
        return self._data.shape[1]

    def data(self, index, role=Qt.ItemDataRole(0)):
        """Return cell data as a string for DisplayRole; None otherwise."""
        if index.isValid():
            if role == Qt.ItemDataRole(0):
                return str(self._data.iloc[index.row(), index.column()])
        return None

    def headerData(self, col, orientation, role):
        """Return column names for the horizontal header; None otherwise."""
        if orientation == Qt.Orientation(1) and role == Qt.ItemDataRole(0):
            return self._data.columns[col]
        return None
