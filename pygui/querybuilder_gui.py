#!/usr/bin/env python
"""Backscatter / seafloor query builder panel.

``QueryBuilder`` is a ``QWidget`` tab embedded in the main dock.  It loads
a soundings CSV (configured in Settings), lets the user draw spatial
selection shapes (ellipse, rectangle, convex-hull polygon) on a 2-D scatter
plot, computes summary statistics, and renders 3-D scatter and distribution
plots.  Results (plot images, selected-point coordinates) can be forwarded
to the KML report builder via pyqtSignal.

GPU acceleration (cudf / cuspatial) is used automatically when available;
the code falls back to CPU (scipy / pandas) otherwise.
"""
import sys
import os
# import tempfile
import pathlib

# getting the name of the directory
# where the this file is present.
current = os.path.dirname(os.path.realpath(__file__))
 
# Getting the parent directory name
# where the current directory is present.
parent = os.path.dirname(current)
 
# adding the parent directory to
# the sys.path.
sys.path.append(parent)


from qgis.PyQt.QtCore import Qt, QSize, QSortFilterProxyModel, pyqtSignal, pyqtSlot
from qgis.PyQt.QtGui import QColor, QPixmap, QScreen
from qgis.PyQt.QtWidgets import (
    QWidget, QApplication, QFileDialog,
    QVBoxLayout, QHBoxLayout, QGridLayout,
    QSizePolicy, QSpacerItem,
    QPushButton, QLineEdit, QTextEdit,
    QGroupBox, QRadioButton, QLabel, QSlider,
)

from groundtruther.pygui.Ui_query_builder_ui import Ui_Form
from groundtruther.config.config import config
from groundtruther.configure import get_settings, error_message, log_exception
from groundtruther.gt.mbes_fields import detect_backscatter_fields
from groundtruther.pygui.reference_3d_view import Reference3DView
from ellipse import getEllipseCoords
from rectangle import getRectangleCoords
from pyproj import Proj
from scipy.spatial import ConvexHull
from scipy import stats
import numpy as np
# import cuspatial
try:
    import cudf
except ImportError:
    pass  # cudf not available – GPU acceleration disabled
import pandas as pd
from pyarrow.lib import ArrowInvalid

from qtpandas import pandasModel

# from qtpanel import QtVoila
import time
from random import randint
import pyqtgraph as pg
import pyqtgraph.opengl as gl
import pyqtgraph.exporters
import scipy as sp
import uuid

import random
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure



from plotnine import (
    ggplot,
    aes,
    after_stat,
    geom_density,
)

try:
    from pip_cuda import get_spatial_selection_gpu
except ImportError:
    pass  # cuspatial not available – GPU spatial selection disabled
from pip_cpu import get_spatial_selection_cpu
# self.send_image_path.connect(self.savekml.from_main_signal)

from qgis.core import (Qgis, QgsApplication, QgsMessageLog, QgsTask, QgsRasterLayer, QgsVectorLayer)
import uuid
from osgeo import ogr
import geojson


def _patch_pyopengl_context_lookup():
    """Make PyOpenGL tolerant of Qt6 GL contexts it can't introspect.

    pyqtgraph's GL items (``GLSurfacePlotItem``, ``GLGridItem``/``GLLinePlotItem``)
    paint with ``glVertexAttribPointer(..., None)``.  PyOpenGL's wrapper for that
    call stores a GC-anchor in per-context storage keyed by
    ``OpenGL.platform.GetCurrentContext()``.  Under QGIS/Qt6 that query can return
    NULL even while a context *is* current (Qt's EGL/GLX context is opaque to
    PyOpenGL), so ``contextdata.getContext`` raises *"Attempt to retrieve context
    when no valid context"* and **every** GL item fails to paint — the WGL 3-D
    viewer renders nothing (only "Error while drawing item ..." in the log).

    We wrap ``getContext`` to fall back to a shared bucket (``0``) when no live
    context is reported.  That only affects PyOpenGL's GC-anchor bookkeeping and
    leaves normal, context-detected behaviour untouched.
    """
    try:
        import OpenGL.contextdata as contextdata
        import OpenGL.platform as platform
    except ImportError:
        return  # PyOpenGL absent – GL viewer unavailable anyway
    if getattr(contextdata.getContext, "_gt_patched", False):
        return

    def getContext(context=None):
        if context is None:
            context = platform.GetCurrentContext()
            if not context:
                return 0
        return context

    getContext._gt_patched = True
    contextdata.getContext = getContext


_patch_pyopengl_context_lookup()


dpi = 72
size_inches = (11, 8)                                       # size in inches (for the plot)
size_px = int(size_inches[0]*dpi), int(size_inches[1]*dpi) 


class MplCanvas(FigureCanvas):

    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        super(MplCanvas, self).__init__(self.fig)
        
        
class Window(QWidget):
    def __init__(self, parent=None):
        super(Window, self).__init__(parent)

        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.toolbar = NavigationToolbar(self.canvas, self)
        self.data = None
        #self.button = QPushButton('Plot')
        #self.button.clicked.connect(self.plot)
        self.canvas.setMinimumSize(*size_px)
        layout = QVBoxLayout()
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)
        #layout.addWidget(self.button)
        self.setLayout(layout)
        self.bs_value = 'Corrected Backscatter Value'
        self.plot_hist_type = 'density_plot'
        self.plot()

    def plot(self):
        if self.data is not None:
            QgsMessageLog.logMessage(f"Window.plot data: {self.data}", 'GroundTruther', Qgis.Info)
            self.figure.clear()
            self.figure.clf()
            if self.plot_hist_type == 'density_plot':
                ff = (ggplot(self.data, aes(x=self.bs_value)) + geom_density())
            if self.plot_hist_type == 'density_plot_group_norm':
                ff = (ggplot(self.data, aes(x=self.bs_value, color='line', fill='line')) + geom_density(alpha=0.1))
            if self.plot_hist_type == 'density_plot_group_scaled':
                ff = (ggplot(self.data, aes(x=self.bs_value, color='line', fill='line')) + geom_density(aes(y=after_stat('count')), alpha=0.1))
                    
                    
                    
            fig = ff.draw()

            # update to the new figure
            self.canvas.figure = fig

            # refresh canvas
            self.canvas.draw()
            if os.getenv("HBC_DEBUG") and os.getenv("HBC_DEBUG") == 'VERBOSE':
                QgsMessageLog.logMessage(f"canvas attrs: {dir(self.canvas)}", 'GroundTruther', Qgis.Info)
                QgsMessageLog.logMessage(f"figure attrs: {dir(self.figure)}", 'GroundTruther', Qgis.Info)
            # close the figure so that we don't create too many figure instances
            plt.close(fig)
        
class QueryBuilder(QWidget, Ui_Form):
    send_2dgraph_path = pyqtSignal(str)
    send_3dgraph_path = pyqtSignal(str)
    send_selected_points_path = pyqtSignal(str)
    send_stats_html = pyqtSignal(str)
    send_sampling_html = pyqtSignal(str)
    # list of (image path, descriptive label) — one per histogram type
    send_histograms = pyqtSignal(object)
    # newline-joined list of absolute image paths in the current sampling shape
    send_imageselection_path = pyqtSignal(str)

    def __init__(self, parent=None):
        super(QueryBuilder, self).__init__(parent)
        self.setupUi(self)
        self.parent = parent
        #self.config = os.environ.get('HBC_CONFIG')
        #print(os.path.join(os.path.dirname(__file__), '../config/config.yaml'))
        #self.config = os.path.join(os.path.dirname(__file__), 'config/config.yaml')
        self.config = config
        self.image_index_label.hide()
        self.qb_imageindex.hide()
        self.image_buffer_label.hide()
        self.qb_imagebuffer.hide()
        # load settings
        # if point data is not available
        # disable all
        self.point_df = None
        self.image_df = None
        # Optional reference-surface GeoTIFF for the 3-D viewer (set in Settings).
        self.reference_surface = None
        # Last sampling polygon (lon/lat), so the Reference 3D tab can re-render
        # after the reference surface is (re)configured without a new draw.
        self._last_geom_array = None
        # Always defined so get_shape_geom() never raises AttributeError when
        # called before the user has picked a sampling shape (e.g. on session
        # restore, when the backscatter/shape combos are set programmatically).
        self.shape = "- - -"
        setattr(
            self.qb_pointdatasource,
            "allItems",
            lambda: [
                self.qb_pointdatasource.itemText(i)
                for i in range(self.qb_pointdatasource.count())
            ],
        )
        
        # The backscatter columns are discovered from the loaded soundings file
        # in refresh_settings(); these are only fallbacks before a file is read.
        self.set_backscatter_field.addItems(['Corrected Backscatter Value', 'Backscatter Value'])
        self.backscatter_field = 'Corrected Backscatter Value'
        self.refresh_settings()
        self.qb_ellipsemajoraxis.hide()
        self.qb_ellipseminoraxis.hide()
        self.qb_ellipseorientation.hide()
        self.qb_ellipseorientation_label.hide()
        self.qb_minoraxis_lablel.hide()
        self.qb_majoraxis_label.hide()
        self.qb_rectangle_l1_label.hide()
        self.qb_rectangle_l2_label.hide()
        self.qb_rectangle_l1.hide()
        self.qb_rectangle_l2.hide()
        self.qb_shapeselection.currentIndexChanged.connect(self.getshape)
        # self.clean_graph.clicked.connect(self.refresh_settings)
        self.reload_settings.clicked.connect(self.refresh_settings)
        self.add_graph.clicked.connect(self.grab_tab)
        # self.tabWidget.setEnabled(False)
        # get the settings
        # add the soundings as an entry to qb_pointdatasource
        # add a method to read the pcl
        # add a method to query the pcl based on the polygong
        # add plotting methods for the query results
        # build a list of images falling in the polygon
        # save the polygon as samplked area
        #
        self.qb_pointdatasource.currentIndexChanged.connect(self.get_point)
        self.set_backscatter_field.currentIndexChanged.connect(self.get_backscatter_field)
        self.draw_graph.clicked.connect(self.get_shape_geom)
        self.draw_graph.clicked.connect(self.plot_hist)

        self.graphicsView = pg.PlotWidget(self.tab_2)
        self.graphicsView.setObjectName("graphicsView")

        # self.GraphicsLayoutWidget = pg.GraphicsLayoutWidget(self.tab_2)
        # self.GraphicsLayoutWidget.setObjectName("GraphicsLayoutWidget")
        self.verticalLayout_11.addWidget(self.graphicsView)
        
        # self.verticalLayout_12.addWidget(self.GraphicsLayoutWidget)
        # pen = pg.mkPen(color=(255, 0, 0))
        # label = pg.LabelItem(justify="right")
        # self.graphicsView.addItem(label)
        self.scatterpoints = self.graphicsView.plot(
            [0], [0], pen=None, symbol="o")
        self.model_point = self.graphicsView.plot(
            [0], [0], pen=pg.mkPen("r", width=5))
        self.graphicsView.showGrid(x=True, y=True)
        # label = pg.LabelItem(justify="right")
        # self.graphicsView.addItem(label)
        # self.model_point = self.GraphicsLayoutWidget.addPlot(
        #    title="Plot Items example", x=[0], y=[0], pen=1.5
        # )
        # self.tabWidget.addTab(self.tab_2, "")
        #
        #
        self.tab_3 = QWidget()
        self.tab_3.setObjectName("tab 3")
        self.tabWidget.addTab(self.tab_3, "WGL")
        self.verticalLayout_wgl = QVBoxLayout(self.tab_3)
        self.verticalLayout_wgl.setObjectName("verticalLayout_wgl")
        self.glw = gl.GLViewWidget(
            self.tab_3, rotationMethod="euler")  # quaternion
        self.verticalLayout_wgl.addWidget(self.glw)
        self.glw.setCameraPosition(distance=150)
        self.p = None

        # "Reference 3D" tab — the reference-surface GeoTIFF clipped to the
        # sampling shape (separate from the WGL soundings surface above).
        self.tab_ref3d = QWidget()
        self.tab_ref3d.setObjectName("tab_ref3d")
        self.tabWidget.addTab(self.tab_ref3d, "Reference 3D")
        self.verticalLayout_ref3d = QVBoxLayout(self.tab_ref3d)
        self.ref3d_label = QLabel(
            "Set a 'Reference surface' GeoTIFF in Settings (MBES), then draw a "
            "sampling shape to view it clipped in 3-D here.")
        self.ref3d_label.setWordWrap(True)
        self.verticalLayout_ref3d.addWidget(self.ref3d_label)
        self.glw_ref = Reference3DView(self.tab_ref3d)
        # Let the 3-D view expand to fill the tab (controls/read-out stay at the
        # bottom) instead of leaving a large empty area below it.
        self.glw_ref.setSizePolicy(QSizePolicy.Policy(7), QSizePolicy.Policy(7))  # Expanding
        self.glw_ref.setMinimumHeight(320)
        self.verticalLayout_ref3d.addWidget(self.glw_ref, 1)

        # Controls + read-outs (cursor position, picking / measuring)
        ref3d_ctrl = QHBoxLayout()
        self.ref3d_measure = QPushButton("Measure")
        self.ref3d_measure.setCheckable(True)
        self.ref3d_measure.setToolTip(
            "Toggle measure mode, then click two points on the surface")
        self.ref3d_measure.toggled.connect(self.glw_ref.set_measure_mode)
        ref3d_ctrl.addWidget(self.ref3d_measure)
        self.ref3d_clear = QPushButton("Clear")
        self.ref3d_clear.clicked.connect(self.glw_ref.clear_measurement)
        ref3d_ctrl.addWidget(self.ref3d_clear)
        # Vertical exaggeration slider (1× … 20×)
        ref3d_ctrl.addWidget(QLabel("VE"))
        self.ref3d_ve = QSlider(Qt.Orientation.Horizontal)
        self.ref3d_ve.setMinimum(1)
        self.ref3d_ve.setMaximum(20)
        self.ref3d_ve.setValue(1)
        self.ref3d_ve.setFixedWidth(110)
        self.ref3d_ve.setToolTip("Vertical exaggeration of the 3-D surface")
        self.ref3d_ve_label = QLabel("1×")
        self.ref3d_ve.valueChanged.connect(self._on_ref3d_ve_changed)
        ref3d_ctrl.addWidget(self.ref3d_ve)
        ref3d_ctrl.addWidget(self.ref3d_ve_label)
        self.ref3d_cursor = QLabel("")          # live E / N / Z under the pointer
        ref3d_ctrl.addWidget(self.ref3d_cursor, 1)
        self.verticalLayout_ref3d.addLayout(ref3d_ctrl)
        self.ref3d_status = QLabel("")          # extent + measurement results
        self.verticalLayout_ref3d.addWidget(self.ref3d_status)

        self.glw_ref.cursor_text.connect(self.ref3d_cursor.setText)
        self.glw_ref.status_text.connect(self.ref3d_status.setText)
        self.p_ref = None
        # self.fitting_degree.valueChanged.connect(self.fit_data_plot)
        self.fitting_degree.valueChanged.connect(self.fit_data_plot)
        # self.fitting_degree.sliderPressed.connect(self.sldDisconnect)
        # self.fitting_degree.sliderReleased.connect(self.sldReconnect)
        self.raw_beam.toggled.connect(self.get_shape_geom)
        self.left_beam.toggled.connect(self.get_shape_geom)
        self.right_beam.toggled.connect(self.get_shape_geom)
        self.fold_beam.toggled.connect(self.get_shape_geom)
        
        # Histogram plotting

        self.plothist_opt = QHBoxLayout()
        self.plot_button = QPushButton('Refresh')
        self.plot_button.clicked.connect(self.plot_hist)
        self.plotnine_window = Window()
        self.plotting_widget = QWidget()
        self.plot_layout = QVBoxLayout()

        
        self.groupBox_hist_opts = QGroupBox(self.plotting_widget)
        self.groupBox_hist_opts.setObjectName("groupBox_hist_opts")
        self.groupBox_hist_opts.setMaximumSize(QSize(16777215, 80))
        self.verticalLayout_hist_opts = QVBoxLayout(self.groupBox_hist_opts)
        self.verticalLayout_hist_opts.setObjectName("verticalLayout_hist_opts")
        self.gridLayout_hist_opts = QGridLayout()
        self.gridLayout_hist_opts.setObjectName("gridLayout_hist_opts")
        self.density_plot = QRadioButton(self.groupBox_hist_opts)
        self.density_plot.setObjectName("density_plot")
        self.density_plot.setText('Density')
        self.gridLayout_hist_opts.addWidget(self.density_plot, 0, 1, 1, 1)
        self.density_plot_group_norm = QRadioButton(self.groupBox_hist_opts)
        self.density_plot_group_norm.setObjectName("density_plot_group_norm")
        self.density_plot_group_norm.setText('Density-Group norm')
        self.gridLayout_hist_opts.addWidget(self.density_plot_group_norm, 0, 2, 1, 1)
        self.density_plot_group_scaled = QRadioButton(self.groupBox_hist_opts)
        self.density_plot_group_scaled.setObjectName("density_plot_group_scaled")
        self.density_plot_group_scaled.setText('Density-Group scaled')
        self.gridLayout_hist_opts.addWidget(self.density_plot_group_scaled, 0, 3, 1, 1)
        
        #spacerItem5 = QSpacerItem(20, 40, QSizePolicy.Policy(1), QSizePolicy.Policy(7))
        #self.gridLayout_hist_opts.addItem(spacerItem5, 0, 4, 1, 1)
        
        self.gridLayout_hist_opts.addWidget(self.plot_button, 0, 4, 1, 1)
        self.verticalLayout_hist_opts.addLayout(self.gridLayout_hist_opts)
        self.plot_layout.addWidget(self.groupBox_hist_opts)
        self.density_plot.setChecked(True)
        
        self.plot_layout.addWidget(self.plotnine_window)
        self.plotting_widget.setLayout(self.plot_layout)
        self.tabWidget.addTab(self.plotting_widget, "Histogram")
        
        self.density_plot.toggled.connect(self.plot_hist)
        self.density_plot_group_norm.toggled.connect(self.plot_hist)
        self.density_plot_group_scaled.toggled.connect(self.plot_hist)
        self.image_selection = QTextEdit(self)
        self.tabWidget.addTab(self.image_selection, "Image Selection")

        
        
        
        # cross hair

    def add_image_link(self):
        image__path_selected = ''
        for i in self.image_selection_pd['Imagename']:
            image_path = os.path.join(self.dirname, i+".jpg")
            image__path_selected += f'<img src="{image_path}" alt="Smiley face" height="300"><br>'
                # link = self.textlink()
        self.image_selection.setHtml(image__path_selected)
        # self.description.append(str(link))

        #self.description.append(self.currentimagestring)
        self.image_selection.verticalScrollBar().setValue(
            self.image_selection.verticalScrollBar().maximum()
        ) 

    def plot_hist(self):
        # print(dir(self.sc))
        self.plot_layout.removeWidget(self.plotnine_window)
        #self.plot_layout.removeWidget(self.plot_toolbar)
        self.plotnine_window.deleteLater()
        # self.plot_toolbar.deleteLater()
        self.plotnine_window = None
        # self.plot_toolbar = None
        self.plotnine_window = Window()
        self.plotnine_window.bs_value = self.backscatter_field
        self.plotnine_window.data = self.point_selection_pd
        self.plot_layout.addWidget(self.plotnine_window)
        if self.density_plot.isChecked():
            self.plotnine_window.plot_hist_type = 'density_plot'
        if self.density_plot_group_norm.isChecked():
            self.plotnine_window.plot_hist_type = 'density_plot_group_norm'
        if self.density_plot_group_scaled.isChecked():
            self.plotnine_window.plot_hist_type = 'density_plot_group_scaled'
        self.plotnine_window.plot()


    def Disconnect(self):
        self.sender().valueChanged.disconnect()

    def sldReconnect(self):
        self.sender().valueChanged.connect(self.sliderChanged)
        self.sender().valueChanged.emit(self.sender().value())

    def validate_fields(self):
        available = list(self.point_df.keys())
        setting_fields = [
            self.logitude_field,
            self.latitude_field,
            self.xutm_field,
            self.yutm_field,
        ]
        check = all(item in available for item in setting_fields)
        if not check:
            missing = [f for f in setting_fields if f not in available]
            QgsMessageLog.logMessage(
                f"validate_fields: missing columns {missing} in {available}",
                'GroundTruther', Qgis.Warning)
        return check

    def populate_backscatter_fields(self, columns):
        """Repopulate the backscatter combo from the loaded soundings columns.

        Supports both the legacy schema (``Backscatter Value`` /
        ``Corrected Backscatter Value``) and the multi-level BSWG-2015 schema
        (``BS_raw_dB`` ... ``BS_AVG_dB``).  The current selection is preserved
        across reloads when the column still exists; otherwise the first
        detected field (most corrected) becomes the default.
        """
        fields = detect_backscatter_fields(columns)
        if not fields:
            QgsMessageLog.logMessage(
                f"no backscatter columns found in soundings; available: {list(columns)}",
                'GroundTruther', Qgis.Warning)
            return
        current = self.backscatter_field
        self.set_backscatter_field.blockSignals(True)
        self.set_backscatter_field.clear()
        self.set_backscatter_field.addItems(fields)
        if current in fields:
            self.set_backscatter_field.setCurrentIndex(fields.index(current))
        self.set_backscatter_field.blockSignals(False)
        self.backscatter_field = self.set_backscatter_field.currentText()
        QgsMessageLog.logMessage(
            f"backscatter fields: {fields} (selected '{self.backscatter_field}')",
            'GroundTruther', Qgis.Info)

    def refresh_settings(self):
        """Reload settings from disk and re-initialise data sources.

        Falls back to the parent dockwidget's already-validated settings when
        the config file cannot be read or fails validation.  Disables the
        query tools if no usable settings are available.
        """
        fresh = get_settings(self.config)
        if fresh:
            self.settings = fresh
        elif self.parent is not None and getattr(self.parent, "settings", None):
            # Parent (dockwidget) already has valid settings – reuse them
            self.settings = self.parent.settings

        if not self.settings:
            error_message(
                "No valid configuration found.\n"
                "Open Settings (wizard icon) to set the required paths."
            )
            self.query_builder_tools.setEnabled(False)
            self.draw_graph.setEnabled(False)
            return

        self.logitude_field = self.logitude.text()
        self.latitude_field = self.latitude.text()
        self.xutm_field = self.xutm.text()
        self.yutm_field = self.yutm.text()
        self.backscatter_field = self.set_backscatter_field.currentText()
        self.utmzone_string = int(self.utmzone.text())
        self.dirname = self.settings["HabCam"]["imagepath"]

        try:
            self.image_metadata = self.settings["HabCam"]["imagemetadata"]
            if self.image_df is not None:
                del self.image_df
            self.pointdatasource = self.settings["Mbes"]["soundings"]
            self.reference_surface = (self.settings.get("Mbes") or {}).get("reference_surface")
            if self.point_df is not None:
                del self.point_df

            if self.settings["Processing"]["gpu_avaibility"]:
                self.point_df = cudf.read_parquet(self.pointdatasource)
                self.image_df = cudf.read_parquet(self.image_metadata)
            else:
                self.point_df = pd.read_parquet(self.pointdatasource)
                self.image_df = pd.read_parquet(self.image_metadata)

            if self.pointdatasource not in self.qb_pointdatasource.allItems():
                self.qb_pointdatasource.addItem(self.pointdatasource)

            self.populate_backscatter_fields(self.point_df.keys())

            if self.validate_fields():
                self.query_builder_tools.setEnabled(True)
                self.draw_graph.setEnabled(True)
            else:
                self.draw_graph.setEnabled(False)
                error_message(
                    "MBES data fields do not match the configured field names.\n"
                    f"Available fields: {list(self.point_df.keys())}\n"
                    "Disabling plot widget."
                )

        except ArrowInvalid:
            error_message(
                "MBES data is not a valid Parquet file.\n"
                "Disabling query widget."
            )
            self.pointdatasource = None
            self.query_builder_tools.setEnabled(False)
            self.point_df = None
            self.image_df = None

        # Reference surface may have just changed — refresh the Reference 3D tab
        # for the current sampling shape (guarded: the GL tab and a prior draw
        # must already exist; not the case on the first call from __init__).
        if getattr(self, "glw_ref", None) is not None and self._last_geom_array is not None:
            try:
                self._render_reference_3d(self._last_geom_array)
            except Exception as exc:
                log_exception("refresh_settings: reference 3D re-render", exc, warn=True)

    def getshape(self, index):
        self.shape = self.qb_shapeselection.itemText(index)
        QgsMessageLog.logMessage(f"shape selected: {self.shape}", 'GroundTruther', Qgis.Info)
        self._apply_shape_field_visibility()
        try:
            self.polygonhandler = self.get_shape_geom()
            self.draw_graph.setEnabled(True)
            self.tabWidget.setEnabled(True)
        except ValueError:
            QgsMessageLog.logMessage("no data selected yet – reset shape selection", 'GroundTruther', Qgis.Warning)
            self.qb_shapeselection.setCurrentIndex(0)

    def _apply_shape_field_visibility(self):
        """Show only the parameter fields relevant to the current shape.

        Extracted so session-restore can re-apply the right field visibility
        without triggering a spatial recompute.
        """
        shape = getattr(self, "shape", "- - -")
        ellipse = shape == "Ellipse"
        rect = shape == "Rectangle"
        for widget in (self.qb_ellipsemajoraxis, self.qb_ellipseminoraxis,
                       self.qb_ellipseorientation, self.qb_ellipseorientation_label,
                       self.qb_minoraxis_lablel, self.qb_majoraxis_label):
            widget.setVisible(ellipse)
        for widget in (self.qb_rectangle_l1_label, self.qb_rectangle_l2_label,
                       self.qb_rectangle_l1, self.qb_rectangle_l2):
            widget.setVisible(rect)


    def get_images(self, index):
        if self.image_df is not None:
            del self.image_df
        if self.settings['Processing']['gpu_avaibility']:
            self.image_df = cudf.read_parquet(self.image_metadata)
        else:
            self.image_df = pd.read_parquet(self.image_metadata)

    def get_point(self, index):
        if self.point_df is not None:
            del self.point_df
        if self.settings['Processing']['gpu_avaibility']:
            self.point_df = cudf.read_parquet(self.pointdatasource)
        else:
            self.point_df = pd.read_parquet(self.pointdatasource)

    def get_backscatter_field(self, index):
        self.backscatter_field = self.set_backscatter_field.itemText(index)
        if self.tabWidget.isEnabled():
            self.get_shape_geom()
            self.plot_hist()
        # self.point_df = cudf.read_parquet(
        #    self.qb_pointdatasource.itemText(index))

    def update_crosshair(self, e):

        pos = e[0]
        if self.graphicsView.sceneBoundingRect().contains(pos):
            mousePoint = self.graphicsView.plotItem.vb.mapSceneToView(pos)
            index = int(mousePoint.x())
            if (
                index >= self.point_selection_pd["True Angle"].min()
                and index <= self.point_selection_pd["True Angle"].values.max()
            ):
                self.cursorlabel.setText(
                    str(f"{np.round(mousePoint.x(), 1)}, {np.round(mousePoint.y(), 1)}")
                )
                self.cursorlabel.setPos(mousePoint.x(), mousePoint.y())
                self.crosshair_v.setPos(mousePoint.x())
                self.crosshair_h.setPos(mousePoint.y())

    def send_shape_to_canvas(self, geom):
        # Create an in-memory OGR datasource
        # driver = ogr.GetDriverByName('Memory')
        # datasource = driver.CreateDataSource('/vsimem/polygon_data')
        # # Create a new layer in the datasource
        # layer = datasource.CreateLayer('polygon', geom_type=ogr.wkbPolygon)
        # # Create a feature and set the geometry
        # feature_defn = layer.GetLayerDefn()
        # feature = ogr.Feature(feature_defn)
        # geometry = ogr.Geometry(ogr.wkbPolygon)
        # ring = ogr.Geometry(ogr.wkbLinearRing)
        # for point in geom:
        #     ring.AddPoint(point[0], point[1])
        # ring.CloseRings()
        # geometry.AddGeometry(ring)
        # feature.SetGeometry(geometry)
        # # Add the feature to the layer
        # layer.CreateFeature(feature)
        # layer_name = str(uuid.uuid1())
        # Path to the GeoJSON file
        
        polygon = geojson.Polygon([geom])
        # Create a GeoJSON Feature
        feature = geojson.Feature(geometry=polygon, properties={})
        # Create a GeoJSON Feature Collection
        feature_collection = geojson.FeatureCollection([feature])
        # Write the GeoJSON to a file
        
        geojson_file_path = str(pathlib.Path(self.settings["Export"]["kmldir"]) / 'sampling_ellipse.geojson')
        QgsMessageLog.logMessage(f"writing sampling shape to: {geojson_file_path}", 'GroundTruther', Qgis.Info)
        # geojson_file_path = pathlib.Path(__file__).parent / 'tmp' / 'sampling_ellipse.geojson'
        with open(f"{geojson_file_path}", "w") as geojson_file:
            geojson.dump(feature, geojson_file)

        # geojson_file = f"{os.path.dirname(os.path.realpath(__file__))}/sampling_ellipse.geojson"
        
        # Create an in-memory OGR datasource
        # driver = ogr.GetDriverByName('Memory')
        # datasource = driver.CreateDataSource('/vsimem/geojson_data')

        # # Open the GeoJSON file
        # geojson_datasource = ogr.Open(geojson_file)

        # # Get the layer from the GeoJSON datasource
        # layer = geojson_datasource.GetLayer()

        # # Copy the layer to the in-memory datasource
        # driver.CopyDataSource(layer, datasource)
        try:
            layer_to_remove = self.parent.project.instance().mapLayersByName('GT sampling shape')[0]
            self.parent.project.instance().removeMapLayer(layer_to_remove)
        except IndexError:
            pass  # no existing sampling shape layer to remove
        vlayer = QgsVectorLayer(geojson_file_path, 'GT sampling shape', 'ogr')
        self.parent.project.instance().addMapLayer(vlayer)

    def get_shape_geom(self):
        # No valid sampling shape selected yet (e.g. the combo was just set
        # programmatically on session restore) — nothing to compute.
        shape = getattr(self, "shape", None)
        if shape not in ("Ellipse", "Rectangle"):
            return
        try:
            if shape == "Ellipse":
                geom = getEllipseCoords(
                    (float(self.qb_longitude.text()), float(self.qb_latitude.text())),
                    int(self.qb_ellipsemajoraxis.text()),
                    int(self.qb_ellipseminoraxis.text()),
                    int(self.qb_ellipseorientation.text()),
                    out_proj=4326,
                )  # 32619
                QgsMessageLog.logMessage(f"Ellipse geom type: {type(geom)}", 'GroundTruther', Qgis.Info)
            else:  # Rectangle
                geom_tuple = getRectangleCoords((float(self.qb_longitude.text()),
                                          float(self.qb_latitude.text())),
                                          float(self.qb_rectangle_l1.text()),
                                          float(self.qb_rectangle_l2.text()),
                                          in_proj=None, utmzone=self.utmzone_string)
                geom = [list(i) for i in zip(*geom_tuple)]
                geom.append(geom[0])
                QgsMessageLog.logMessage(f"Rectangle geom type: {type(geom)}", 'GroundTruther', Qgis.Info)
        except (ValueError, TypeError):
            # Empty / non-numeric shape parameters — wait until the user fills them.
            QgsMessageLog.logMessage(
                "get_shape_geom: incomplete sampling-shape parameters; skipping",
                'GroundTruther', Qgis.Warning)
            return
        geom_array = np.array(geom)
        self.send_shape_to_canvas(geom_array.tolist())
        pp = Proj(
            proj="utm", zone=self.utmzone_string, ellps="WGS84", preserve_units=False
        )
        xx, yy = pp(geom_array[:, 0], geom_array[:, 1])
        px = self.point_df[self.xutm_field].values
        py = self.point_df[self.yutm_field].values
        if self.settings['Processing']['gpu_avaibility']:
            point_selection_index = get_spatial_selection_gpu(px, py, xx, yy)
            self.point_selection = self.point_df[point_selection_index]
            self.point_selection_pd = self.point_selection.to_pandas()
        else:
            points = np.array([px, py]).T
            polygon = np.array([xx, yy]).T
            point_selection_index = get_spatial_selection_cpu(points, polygon)
            self.point_selection_pd = self.point_df[point_selection_index]
        QgsMessageLog.logMessage(f"point selection: {len(self.point_selection_pd)} points", 'GroundTruther', Qgis.Info)
        # self.image_df
        img_x = self.image_df['Xutm_adj'].values
        img_y = self.image_df['Yutm_adj'].values

        if self.settings['Processing']['gpu_avaibility']:
            image_selection_index = get_spatial_selection_gpu(img_x, img_y, xx, yy)
            self.image_selection_cudf = self.image_df[image_selection_index]
            self.image_selection_pd = self.image_selection_cudf.to_pandas()
        else:
            image_points = np.array([img_x, img_y]).T
            polygon = np.array([xx, yy]).T
            image_selection_index = get_spatial_selection_cpu(image_points, polygon)
            self.image_selection_pd = self.image_df[image_selection_index]
        # print(self.image_selection_pd.describe())
        # self.point_selection = self.point_df[point_selection_index]
        # print("length of image_selection ", len(self.image_selection_pd))
        self.add_image_link()
        # self.point_selection_pd = self.point_selection.to_pandas()

        # print(self.result)
        # get a simple describe on the dataframe
        # self.point_selection_pd = self.point_selection.to_pandas()
        self.set_table_view()
        # self.df_model = pandasModel(self.point_selection_pd.describe())
        # self.source_model = self.df_model
        # self.proxy_model = QSortFilterProxyModel(self.source_model)
        #
        # self.searchcommands = QLineEdit("")
        # self.searchcommands.setObjectName(u"searchcommands")
        # self.searchcommands.setAlignment(Qt.AlignmentFlag(1))
        #
        # self.proxy_model.setSourceModel(self.source_model)
        # self.tableView.verticalHeader().setVisible(False)
        # self.tableView.setModel(self.proxy_model)
        # self.tableView.setSortingEnabled(False)

        # Beam-angle view (mutually-exclusive radio buttons in groupBox_6):
        #   Raw  -> all beams (port + starboard), no change
        #   L    -> port only      (True Angle < 0)
        #   R    -> starboard only (True Angle > 0)
        #   Fold -> absolute value of the angle (overlay both sides)
        # The radio buttons re-trigger get_shape_geom via their `toggled` signal.
        angle = self.point_selection_pd["True Angle"]
        if self.left_beam.isChecked():
            self.point_selection_pd = self.point_selection_pd[angle < 0]
        elif self.right_beam.isChecked():
            self.point_selection_pd = self.point_selection_pd[angle > 0]
        elif self.fold_beam.isChecked():
            self.point_selection_pd = self.point_selection_pd.copy()
            self.point_selection_pd["True Angle"] = self.point_selection_pd[
                "True Angle"
            ].abs()
        # raw_beam (default): keep the full angular range unchanged

        self.graphicsView.clear()
        self.scatterpoints = self.graphicsView.plot(
            [0], [0], pen=None, symbol="o")
        self.model_point = self.graphicsView.plot(
            [0], [0], pen=pg.mkPen("r", width=5))
        self.graphicsView.showGrid(x=True, y=True)

        self.scatterpoints.setData(
            self.point_selection_pd["True Angle"].values,
            self.point_selection_pd[self.backscatter_field].values,
            
        )
        # self.point_selection_pd["Backscatter Value"].values,
        xx, yy = self.fit_xy()

        self.model_point.setData(xx, yy)

        self.cursor = Qt.CursorShape(2)  # CrossCursor
        self.graphicsView.setCursor(self.cursor)

        self.crosshair_v = pg.InfiniteLine(angle=90, movable=False)
        self.crosshair_h = pg.InfiniteLine(angle=0, movable=False)
        self.graphicsView.addItem(self.crosshair_v, ignoreBounds=True)
        self.graphicsView.addItem(self.crosshair_h, ignoreBounds=True)
        self.cursorlabel = pg.TextItem()
        self.graphicsView.addItem(self.cursorlabel)
        self.proxy = pg.SignalProxy(
            self.graphicsView.scene().sigMouseMoved,
            rateLimit=60,
            slot=self.update_crosshair,
        )
        self.mouse_x = None

        self.mouse_y = None
        
        self.glw.clear()
        self.glw.reset()
        self.glw.setCameraPosition(distance=150)

        # WGL tab: 3-D surface gridded from the selected soundings (point cloud).
        xx, yy, Z = self._soundings_surface_grid()
        self.p = gl.GLSurfacePlotItem(
            x=xx, y=yy, z=Z, shader="normalColor", smooth=True
        )
        self.p.translate(-xx.mean(), -yy.mean(), -np.nanmean(Z) + 10)
        self.glw.addItem(self.p)
        self.g = gl.GLGridItem()
        self.glw.addItem(self.g)

        # Separate "Reference 3D" tab: the reference-surface GeoTIFF clipped to
        # the same sampling shape (if one is configured).
        self._last_geom_array = geom_array
        self._render_reference_3d(geom_array)

        # QScreen.grabWindow(self.winId()).save("shot.jpg", "jpg")

    def _soundings_surface_grid(self):
        """Grid the selected soundings (Easting/Northing/-Depth) for the 3-D view.

        Returns ``(x, y, Z)`` with ``Z`` shaped ``(len(x), len(y))``.
        """
        x = self.point_selection_pd["Easting"].values
        y = self.point_selection_pd["Northing"].values
        z = self.point_selection_pd["Depth"].values * -1
        resampling_factor = 1.5
        xx = np.linspace(x.min(), x.max(), int((x.max() - x.min()) * resampling_factor))
        yy = np.linspace(y.min(), y.max(), int((y.max() - y.min()) * resampling_factor))
        X, Y = np.meshgrid(xx, yy)
        Z = sp.interpolate.griddata(
            (x, y), z, (X, Y), method="nearest", rescale=True, fill_value=0)
        return xx, yy, Z.T

    def _on_ref3d_ve_changed(self, value):
        self.ref3d_ve_label.setText(f"{value}×")
        self.glw_ref.set_vertical_exaggeration(value)

    def _render_reference_3d(self, geom_array):
        """Render the clipped reference-surface GeoTIFF into the 'Reference 3D' tab.

        Uses the same pyqtgraph GL surface as the WGL tab (the QGIS 3D engine's
        Qgs3DMapCanvas is a QWindow with no stable embed/settings API in this
        QGIS 4 build and no PyQt6 Qt3D bindings, so it isn't used here). When no
        reference surface is configured / it doesn't cover the area, a hint is
        shown instead.
        """
        def _show_hint(text):
            self.glw_ref.clear()
            self.glw_ref.clear_measurement()
            self.ref3d_measure.setChecked(False)
            self.ref3d_cursor.setText("")
            self.ref3d_status.setText("")
            self.ref3d_label.setText(text)
            self.ref3d_label.show()

        path = getattr(self, "reference_surface", None)
        if not path or not os.path.exists(str(path)):
            _show_hint("Set a 'Reference surface' GeoTIFF in Settings (MBES) to "
                       "view it clipped in 3-D here.")
            return
        xx, yy, Z = self._reference_surface_grid(geom_array)
        if xx is None:
            _show_hint("The reference surface doesn't cover this sampling shape "
                       "(or couldn't be read) — draw a shape within the GeoTIFF "
                       "extent.")
            return
        # Render with axes, labels, grid + enable cursor / pick / measure.
        self.ref3d_label.hide()
        self.glw_ref.set_surface(xx, yy, Z)

    def _reference_surface_grid(self, geom_array):
        """Clip the reference-surface GeoTIFF to the sampling shape, if configured.

        Returns ``(x, y, Z)`` for ``GLSurfacePlotItem`` on success, or
        ``(None, None, None)`` when no usable reference surface is available
        (caller then falls back to the soundings surface).
        """
        path = getattr(self, "reference_surface", None)
        if not path or not os.path.exists(path):
            return None, None, None
        try:
            from groundtruther.gt.reference_surface import clip_surface
            bbox = (float(np.min(geom_array[:, 0])), float(np.min(geom_array[:, 1])),
                    float(np.max(geom_array[:, 0])), float(np.max(geom_array[:, 1])))
            xx, yy, Z = clip_surface(path, bbox)
            QgsMessageLog.logMessage(
                f"3-D surface from reference GeoTIFF: {path} "
                f"({len(xx)}x{len(yy)} grid)", 'GroundTruther', Qgis.Info)
            return xx, yy, Z
        except Exception as exc:
            log_exception("reference-surface clip; falling back to soundings", exc, warn=True)
            return None, None, None

    def get_cuspatial_selection(self, xx, yy):
        try:
            result = cuspatial.point_in_polygon(
                self.point_df[self.xutm_field].values,
                self.point_df[self.yutm_field].values,
                cudf.Series([0], index=["geom"]),
                cudf.Series([0], name="r_pos", dtype="int32"),
                xx,
                yy,
            )
            self.point_selection = self.point_df[result["geom"]]
            QgsMessageLog.logMessage(f"point selection (GPU): {len(self.point_selection)} points", 'GroundTruther', Qgis.Info)
            self.point_selection_pd = self.point_selection.to_pandas()
        except KeyError:
            QgsMessageLog.logMessage(
                f"invalid field name for Easting/Northing – check xutm_field='{self.xutm_field}' yutm_field='{self.yutm_field}'",
                'GroundTruther', Qgis.Warning)
            self.point_selection = []

    def set_table_view(self):
        self.df_model = pandasModel(self.point_selection_pd.describe())
        self.source_model = self.df_model
        self.proxy_model = QSortFilterProxyModel(self.source_model)
        #
        # self.searchcommands = QLineEdit("")
        # self.searchcommands.setObjectName(u"searchcommands")
        # self.searchcommands.setAlignment(Qt.AlignmentFlag(1))
        #
        self.proxy_model.setSourceModel(self.source_model)
        self.tableView.verticalHeader().setVisible(False)
        self.tableView.setModel(self.proxy_model)
        self.tableView.setSortingEnabled(False)

    def set_scatterplot(self):
        pass

    def set_surfaceplot(self):
        pass

    def fit_data_plot(self):
        xx, yy = self.fit_xy()
        self.model_point.setData(xx, yy)

    def fit_xy(self):
        model = np.poly1d(
            np.polyfit(
                self.point_selection_pd["True Angle"].values,
                # self.point_selection_pd["Backscatter Value"].values,
                self.point_selection_pd[self.backscatter_field].values,
                self.fitting_degree.value(),
            )
        )
        xx = np.linspace(
            self.point_selection_pd["True Angle"].min(),
            self.point_selection_pd["True Angle"].max(),
            150,
        )
        yy = model(xx)
        return xx, yy

    def grid_xyz(self):
        pass

    @pyqtSlot()
    def grab_tab(self):
        
        self.screen = QApplication.primaryScreen()
        self.screenshot = self.screen.grabWindow(self.tabWidget.winId())
        # self.screenshot.save("shot.jpg", "jpg")
        # print(self.tabWidget.currentIndex())
        # self.screenshot_save()
        # TODO: check which tab is in use (self.tabWidget.currentindex() )
        # and use some logic to save the 2d or 3d plot
        # if self.tabWidget.currentIndex() == 1:
        exporter = pg.exporters.ImageExporter(self.graphicsView.plotItem)
        self.settings['Export']['kmldir']
        scatter_graph_path = f"{self.settings['Export']['kmldir']}/{uuid.uuid1()}.png"

        surface_graph_path = f"{self.settings['Export']['kmldir']}/{uuid.uuid1()}.png"

        exporter.export(f"{scatter_graph_path}")
        selected_points_path = f"{self.settings['Export']['kmldir']}/{uuid.uuid1()}.csv"
        self.point_selection_pd.to_csv(selected_points_path)
        
        # else:
        #    exporter = pg.exporters.ImageExporter(self.graphicsView.plotItem)
        #    exporter.export("/home/jovyan/hbc_browser/data/surface_now.png")

        self.glw.grabFramebuffer().save(f"{surface_graph_path}")
        # self.p.grabFrameBuffer().save("fileName2.png")
        self.send_2dgraph_path.emit(
            scatter_graph_path)
        self.send_3dgraph_path.emit(
            surface_graph_path)
        self.send_selected_points_path.emit(
            selected_points_path)

        # Additional query-builder products forwarded to the report builder.
        # Statistics and the sampling unit are sent as HTML tables (no file);
        # the histogram is saved to the export dir so it can be embedded.
        # A failure in one product must not block the others.
        kmldir = self.settings['Export']['kmldir']

        try:
            self.send_sampling_html.emit(self._sampling_unit_html())
        except Exception as exc:
            log_exception("grab_tab: sampling unit table", exc, warn=True)

        try:
            self.send_stats_html.emit(self._stats_html())
        except Exception as exc:
            log_exception("grab_tab: statistics table", exc, warn=True)

        try:
            histograms = self._save_all_histograms(kmldir)
            if histograms:
                self.send_histograms.emit(histograms)
        except Exception as exc:
            log_exception("grab_tab: histograms", exc, warn=True)

        try:
            image_paths = self._selected_image_paths()
            if image_paths:
                self.send_imageselection_path.emit("\n".join(image_paths))
            else:
                QgsMessageLog.logMessage(
                    "grab_tab: no selected images found on disk to forward",
                    'GroundTruther', Qgis.Warning)
        except Exception as exc:
            log_exception("grab_tab: image selection", exc, warn=True)

        del self.screen
        del self.screenshot

    def _stats_html(self):
        """Return the selection's ``describe()`` summary as an HTML table."""
        return self.point_selection_pd.describe().round(3).to_html(
            border=1, classes="gt-stats", justify="center")

    def _sampling_unit_html(self):
        """Return an HTML table describing the current sampling shape/unit."""
        shape = getattr(self, "shape", "")
        rows = [
            ("Shape", shape),
            ("Center longitude", self.qb_longitude.text()),
            ("Center latitude", self.qb_latitude.text()),
        ]
        if shape == "Ellipse":
            rows += [
                ("Major axis", self.qb_ellipsemajoraxis.text()),
                ("Minor axis", self.qb_ellipseminoraxis.text()),
                ("Orientation (deg)", self.qb_ellipseorientation.text()),
            ]
        elif shape == "Rectangle":
            rows += [
                ("Side L1", self.qb_rectangle_l1.text()),
                ("Side L2", self.qb_rectangle_l2.text()),
                ("UTM zone", str(self.utmzone_string)),
            ]
        body = "".join(
            f"<tr><td><b>{label}</b></td><td>{value}</td></tr>"
            for label, value in rows
        )
        return (
            '<table border="1" cellpadding="3" cellspacing="0" '
            f'class="gt-sampling">{body}</table>'
        )

    # The three histogram variants offered in the Histogram tab.
    _HISTOGRAM_KINDS = (
        ("density",      "Histogram — Density"),
        ("group_norm",   "Histogram — Group Norm Density"),
        ("group_scaled", "Histogram — Group Scaled Density"),
    )

    def _build_histogram_plot(self, kind):
        """Return the plotnine plot object for a given histogram *kind*."""
        data = self.point_selection_pd
        bs = self.backscatter_field
        if kind == "group_norm":
            return (ggplot(data, aes(x=bs, color='line', fill='line'))
                    + geom_density(alpha=0.1))
        if kind == "group_scaled":
            return (ggplot(data, aes(x=bs, color='line', fill='line'))
                    + geom_density(aes(y=after_stat('count')), alpha=0.1))
        return ggplot(data, aes(x=bs)) + geom_density()

    def _save_all_histograms(self, kmldir):
        """Render all three histogram types to PNGs.

        Returns a list of ``(path, label)`` for the variants that rendered, so
        the report builder can embed them all (like the image selection) rather
        than only the one currently shown.
        """
        out = []
        for kind, label in self._HISTOGRAM_KINDS:
            path = f"{kmldir}/{uuid.uuid1()}.png"
            try:
                self._build_histogram_plot(kind).save(
                    path, width=8, height=6, dpi=150, verbose=False)
                out.append((path, label))
                QgsMessageLog.logMessage(
                    f"saved histogram ({label}): {path}", 'GroundTruther', Qgis.Info)
            except Exception as exc:
                log_exception(f"grab_tab: histogram '{kind}'", exc, warn=True)
        return out

    def _selected_image_paths(self):
        """Absolute paths of the sampling-shape images that exist on disk."""
        paths = []
        for name in self.image_selection_pd['Imagename']:
            image_path = os.path.join(self.dirname, name + ".jpg")
            if os.path.exists(image_path):
                paths.append(image_path)
        return paths

    def screenshot_save(self):
        file = QFileDialog.getSaveFileName(self, "Save File")
        self.screenshot.save(file[0], "jpg")
        # file = open(name,'w')
        # text = self.textEdit.toPlainText()
        # file.write(text)
        # file.close()

    def get_xy(df, longitude="Longitude", latitude="Latitude"):
        if self.settings['Processing']['gpu_avaibility']:
            x = df[longitude].dropna().values.get()
            y = df[latitude].dropna().values.get()
        else:
            x = df[longitude].dropna().values
            y = df[latitude].dropna().values

        # x = df[longitude].dropna().values.get()
        # y = df[latitude].dropna().values.get()
        return (x, y)

    def getCH(x, y):
        points = np.vstack([x, y]).T
        hull = ConvexHull(points)
        ch_lon = points[hull.vertices, 0]
        ch_lat = points[hull.vertices, 1]
        # Create ring
        ring = ogr.Geometry(ogr.wkbLinearRing)
        for i, val in enumerate(ch_lat):
            ring.AddPoint(ch_lon[i], ch_lat[i])
        ring.AddPoint(ch_lon[0], ch_lat[0])
        # Create polygon
        poly = ogr.Geometry(ogr.wkbPolygon)
        poly.AddGeometry(ring)
        d = json.loads(poly.ExportToJson())
        g = GeoJSON(data=d)
        center = poly.Centroid().GetX(), poly.Centroid().GetY()
        return center[::-1], g
