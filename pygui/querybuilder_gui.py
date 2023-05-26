#!/usr/bin/env python
import sys
import os

# getting the name of the directory
# where the this file is present.
current = os.path.dirname(os.path.realpath(__file__))
 
# Getting the parent directory name
# where the current directory is present.
parent = os.path.dirname(current)
 
# adding the parent directory to
# the sys.path.
sys.path.append(parent)


from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

from groundtruther.pygui.Ui_query_builder_ui import Ui_Form
from groundtruther.config.config import config
from configure import get_settings, error_message
from ellipse import getEllipseCoords
from rectangle import getRectangleCoords
from pyproj import Proj
from scipy.spatial import ConvexHull
from scipy import stats
import numpy as np
import sip
# import cuspatial
try:
    import cudf
except ImportError:
    print('no gpu')
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
from PyQt5.QtGui import QPixmap, QScreen
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
    print('cuspatial not available')
from pip_cpu import get_spatial_selection_cpu
# self.send_image_path.connect(self.savekml.from_main_signal)

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
            print(self.data)
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
                print(dir(self.canvas))
                print(dir(self.figure))
            # close the figure so that we don't create too many figure instances
            plt.close(fig)
        
class QueryBuilder(QWidget, Ui_Form):
    send_2dgraph_path = pyqtSignal(str)
    send_3dgraph_path = pyqtSignal(str)
    send_selected_points_path = pyqtSignal(str)

    def __init__(self, parent=None):
        super(QueryBuilder, self).__init__(parent)
        self.setupUi(self)
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
        setattr(
            self.qb_pointdatasource,
            "allItems",
            lambda: [
                self.qb_pointdatasource.itemText(i)
                for i in range(self.qb_pointdatasource.count())
            ],
        )
        
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
        
        #spacerItem5 = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
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
        sip.delete(self.plotnine_window)
        # sip.delete(self.plot_toolbar)
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
        print(list(self.point_df.keys()))
        setting_fields = [
            self.logitude_field,
            self.latitude_field,
            self.xutm_field,
            self.yutm_field,
        ]
        print(setting_fields)
        check = all(item in list(self.point_df.keys())
                    for item in setting_fields)
        print(check)
        return check

    def refresh_settings(self):
        self.settings = get_settings(self.config)
        self.logitude_field = self.logitude.text()
        self.latitude_field = self.latitude.text()
        self.xutm_field = self.xutm.text()
        self.yutm_field = self.yutm.text()
        self.backscatter_field = self.set_backscatter_field.currentText()
        self.utmzone_string = int(self.utmzone.text())
        self.dirname = self.settings["HabCam"]["imagepath"]
        try:
            print(self.settings["HabCam"]["imagemetadata"])
            self.image_metadata = self.settings["HabCam"]["imagemetadata"]
            if self.image_df is not None:
                del self.image_df
            print(self.settings["Mbes"]["soundings"])
            self.pointdatasource = self.settings["Mbes"]["soundings"]
            if self.point_df is not None:
                del self.point_df
            if self.settings['Processing']['GPU']:
                print('############## USE GPU #################')
                self.point_df = cudf.read_parquet(self.pointdatasource)
                self.image_df = cudf.read_parquet(self.image_metadata)
            else:
                print('############## USE CPU #################')
                self.point_df = pd.read_parquet(self.pointdatasource)
                self.image_df = pd.read_parquet(self.image_metadata)

            # validate MBES data
            if self.pointdatasource not in self.qb_pointdatasource.allItems():
                self.qb_pointdatasource.addItem(self.pointdatasource)
                
            if self.validate_fields() == True:
                self.query_builder_tools.setEnabled(True)
                self.draw_graph.setEnabled(True)
            else:
                print("tell the fields are not correct")
                self.draw_graph.setEnabled(False)
                error_message(
                    f"error fields in the MBES data not match \n"
                    + str(f"available fieds are:  \n {list(self.point_df.keys())} \n")
                    + str("disabling plot widget")
                )        
        except ArrowInvalid:
            error_message(
                f"error MBES data not a valid parquet file \n"
                + str("disabling query widget")
            )
            self.pointdatasource = None
            self.query_builder_tools.setEnabled(False)
            self.point_df = None
            self.image_df = None
        # at this point we load the image metadata 
        # lat and lon which we will use to query images in the fiven elliptical shape
        # try:
        #     print(self.settings["HabCam"]["imagemetadata"])
        #     self.image_metadata = self.settings["HabCam"]["imagemetadata"]
        #     if self.image_df is not None:
        #         del self.image_df
        #     if self.settings['Processing']['GPU']:
        #         print('############## USE GPU #################')
        #         self.image_df = cudf.read_parquet(self.image_metadata)
        #     else:
        #         print('############## USE CPU #################')
        #         self.image_df = pd.read_parquet(self.image_metadata)
        # except ArrowInvalid:
        #     error_message(
        #         f"error Image metadata not a valid parquet file \n"
        #         + str("disabling query widget")
        #     )
        #     self.image_metadata = None
        #     self.query_builder_tools.setEnabled(False)
        #     self.image_df = None
        print(self.settings)
        

    def getshape(self, index):
        self.shape = self.qb_shapeselection.itemText(index)
        print(self.shape)
        if self.shape == "Ellipse":
            self.qb_ellipsemajoraxis.show()
            self.qb_ellipseminoraxis.show()
            self.qb_ellipseorientation.show()

            self.qb_ellipseorientation_label.show()
            self.qb_minoraxis_lablel.show()
            self.qb_majoraxis_label.show()

            self.qb_rectangle_l1_label.hide()
            self.qb_rectangle_l2_label.hide()
            self.qb_rectangle_l1.hide()
            self.qb_rectangle_l2.hide()
        if self.shape == "Rectangle":
            self.qb_rectangle_l1_label.show()
            self.qb_rectangle_l2_label.show()
            self.qb_rectangle_l1.show()
            self.qb_rectangle_l2.show()

            self.qb_ellipsemajoraxis.hide()
            self.qb_ellipseminoraxis.hide()
            self.qb_ellipseorientation.hide()
            self.qb_ellipseorientation_label.hide()
            self.qb_minoraxis_lablel.hide()
            self.qb_majoraxis_label.hide()
        if self.shape == "- - -":
            print("presente")
            self.qb_rectangle_l1_label.hide()
            self.qb_rectangle_l2_label.hide()
            self.qb_rectangle_l1.hide()
            self.qb_rectangle_l2.hide()

            self.qb_ellipsemajoraxis.hide()
            self.qb_ellipseminoraxis.hide()
            self.qb_ellipseorientation.hide()
            self.qb_ellipseorientation_label.hide()
            self.qb_minoraxis_lablel.hide()
            self.qb_majoraxis_label.hide()
        try:
            self.polygonhandler = self.get_shape_geom()
            self.draw_graph.setEnabled(True)
            self.tabWidget.setEnabled(True)
        except ValueError:
            print("no data selected yet")
            self.qb_shapeselection.setCurrentIndex(0)
        

    def get_images(self, index):
        if self.image_df is not None:
            del self.image_df
        if self.settings['Processing']['GPU']:
            print('############## USE GPU #################')
            self.image_df = cudf.read_parquet(self.image_metadata)
        else:
            print('############## USE CPU #################')
            self.image_df = pd.read_parquet(self.image_metadata)    


    def get_point(self, index):
        if self.point_df is not None:
            del self.point_df
        if self.settings['Processing']['GPU']:
            print('############## USE GPU #################')
            self.point_df = cudf.read_parquet(self.pointdatasource)
        else:
            print('############## USE CPU #################')
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

    def get_shape_geom(self):
        if self.shape == "Ellipse":
            geom = getEllipseCoords(
                (float(self.qb_longitude.text()), float(self.qb_latitude.text())),
                int(self.qb_ellipsemajoraxis.text()),
                int(self.qb_ellipseminoraxis.text()),
                int(self.qb_ellipseorientation.text()),
                out_proj=4326,
            )  # 32619
        print(self.shape)
        if self.shape == "Rectangle":
            print('calling it')
            geom = getRectangleCoords((float(self.qb_longitude.text()), 
                                      float(self.qb_latitude.text())),
                                      float(self.qb_rectangle_l1.text()), 
                                      float(self.qb_rectangle_l2.text()),
                                      in_proj=None, utmzone=self.utmzone_string)
            print(geom)
        geom_array = np.array(geom)
        pp = Proj(
            proj="utm", zone=self.utmzone_string, ellps="WGS84", preserve_units=False
        )
        xx, yy = pp(geom_array[:, 0], geom_array[:, 1])
        px = self.point_df[self.xutm_field].values
        py = self.point_df[self.yutm_field].values
        if self.settings['Processing']['GPU']:
            print('############## USE GPU #################')
            point_selection_index = get_spatial_selection_gpu(px, py, xx, yy)
            self.point_selection = self.point_df[point_selection_index]
            self.point_selection_pd = self.point_selection.to_pandas()
        else:
            print('############## USE CPU #################')
            points = np.array([px, py]).T
            polygon = np.array([xx, yy]).T
            point_selection_index = get_spatial_selection_cpu(
                points, polygon)
            self.point_selection_pd = self.point_df[point_selection_index]
        print("length of point_selection ", len(self.point_selection_pd))
        # self.image_df
        img_x = self.image_df['Xutm_adj'].values
        img_y = self.image_df['Yutm_adj'].values
        
        if self.settings['Processing']['GPU']:
            print('############## USE GPU #################')
            image_selection_index = get_spatial_selection_gpu(img_x, img_y, xx, yy)
            self.image_selection_cudf = self.image_df[image_selection_index]
            self.image_selection_pd = self.image_selection_cudf.to_pandas()
        else:
            print('############## USE CPU #################')
            image_points = np.array([img_x, img_y]).T
            polygon = np.array([xx, yy]).T
            image_selection_index = get_spatial_selection_cpu(
                image_points, polygon)
            self.image_selection_pd = self.image_df[image_selection_index]
        print(self.image_selection_pd.describe())
        # self.point_selection = self.point_df[point_selection_index]
        print("length of image_selection ", len(self.image_selection_pd))
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
        # self.searchcommands.setAlignment(Qt.AlignLeft)
        #
        # self.proxy_model.setSourceModel(self.source_model)
        # self.tableView.verticalHeader().setVisible(False)
        # self.tableView.setModel(self.proxy_model)
        # self.tableView.setSortingEnabled(False)

        if self.raw_beam.isChecked():
            print("do nothing")
        if self.left_beam.isChecked():
            print("remove positive angles from the df")
        if self.right_beam.isChecked():
            print("remove negative angles from df")
        if self.fold_beam.isChecked():
            print("multiply by -1 negative angles")
            self.point_selection_pd["True Angle"] = self.point_selection_pd[
                "True Angle"
            ].abs()
        # add a reload of this method if the radiobuttons status changes
        
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

        self.cursor = Qt.CrossCursor
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
        x = self.point_selection_pd["Easting"].values
        y = self.point_selection_pd["Northing"].values
        z = self.point_selection_pd["Depth"].values * -1
        resampling_factor = 1.5
        xx = np.linspace(x.min(), x.max(), int(
            (x.max() - x.min()) * resampling_factor))
        yy = np.linspace(y.min(), y.max(), int(
            (y.max() - y.min()) * resampling_factor))
        print(
            f"x spacing: {int((x.max() - x.min()) * resampling_factor)}, \n y spacing: {int((y.max() - y.min()) * resampling_factor)}"
        )
        X, Y = np.meshgrid(xx, yy)
        Z = sp.interpolate.griddata(
            (x, y), z, (X, Y), method="nearest", rescale=True, fill_value=0
        )
        self.p = gl.GLSurfacePlotItem(
            x=xx, y=yy, z=Z.T, shader="normalColor", smooth=True
        )
        self.p.translate(-xx.mean(), -yy.mean(), -Z.mean() + 10)
        self.glw.addItem(self.p)
        # print(self.glw.cameraPosition())
        # self.glw.opts["center"] += QVector3D(xx[0], yy[0], Z[0][0])
        print(self.glw.cameraPosition())
        self.g = gl.GLGridItem()
        self.glw.addItem(self.g)

        # QScreen.grabWindow(self.winId()).save("shot.jpg", "jpg")

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
            print("length of point_selection ", len(self.point_selection))
            self.point_selection_pd = self.point_selection.to_pandas()
        except KeyError:
            print("invalid field name for Easting/Northing parameters")
            self.point_selection = []



    def set_table_view(self):
        self.df_model = pandasModel(self.point_selection_pd.describe())
        self.source_model = self.df_model
        self.proxy_model = QSortFilterProxyModel(self.source_model)
        #
        # self.searchcommands = QLineEdit("")
        # self.searchcommands.setObjectName(u"searchcommands")
        # self.searchcommands.setAlignment(Qt.AlignLeft)
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
        print(self.tabWidget.currentIndex())
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
        
        del self.screen
        del self.screenshot

    def screenshot_save(self):
        file = QFileDialog.getSaveFileName(self, "Save File")
        self.screenshot.save(file[0], "jpg")
        # file = open(name,'w')
        # text = self.textEdit.toPlainText()
        # file.write(text)
        # file.close()

    def get_xy(df, longitude="Longitude", latitude="Latitude"):
        if self.settings['Processing']['GPU']:
            print('############## USE GPU #################')
            x = df[longitude].dropna().values.get()
            y = df[latitude].dropna().values.get()
        else:
            print('############## USE CPU #################')
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
