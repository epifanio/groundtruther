from qgis.core import *
from qgis.gui import *
from qgis.utils import *
from qgis.PyQt.QtCore import pyqtSignal as Signal, pyqtSlot as Slot
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *



class GRQueryTool(QgsMapTool):
    """
    Get the value for all raster layers loaded at the mouse position.  We filter out vector layers and any loaded
    WMS background layers.  Should just get surface layers
    """
    grass_raster_query = Signal(object)
    query_position = Signal(float, float)

    def __init__(self, parent):
        self.parent = parent
        QgsMapTool.__init__(self, self.parent)

    def canvasPressEvent(self, e):
        """
        On press we print out the tooltip text to the stdout
        """

        text = self._get_cursor_data(e)
        print('****************** GRASS query tool *************************')
        print(text)
        print('******************************************************')
        self.grass_raster_query.emit(text)
        lat, lon = self._get_cursor_position(e)
        self.query_position.emit(lat, lon)

    def canvasMoveEvent(self, e):
        """
        On moving the mouse, we get the new raster information at mouse position and show a new tooltip
        """

        text = self._get_cursor_data(e)
        QToolTip.showText(self.parent.mapToGlobal(self.parent.mouseLastXY()), text,
                                    self.parent, QtCore.QRect(), 1000000)

    def deactivate(self):
        """
        Deactivate the tool
        """

        QgsMapTool.deactivate(self)
        self.deactivated.emit()

    def _get_cursor_position(self, e):
        """
        Get the closest point to the selected location
        """
        x = e.pos().x()
        y = e.pos().y()
        point = self.parent.getCoordinateTransform().toMapCoordinates(x, y)
        return point.y(), point.x()
    
    def _get_cursor_data(self, e):
        """
        Get the mouse position, transform it to the map coordinates, build the text that feeds the tooltip and the
        print on mouseclick event.  Only query non-WMS raster layers.  WMS is background stuff, we don't care about those
        values.  If the raster layer is a virtual file system object (vsimem) we trim that part of the path off for display.
        """
        x = e.pos().x()
        y = e.pos().y()
        point = self.parent.getCoordinateTransform().toMapCoordinates(x, y)
        text = 'Latitude: {}, Longitude: {}'.format(
            round(point.y(), 9), round(point.x(), 9))

        # this is the Lat Lon to be used in the GRASS API
        # we neeed to have here the GRASS location details
        # can be the return of a call to the gisenv GRASS API
        return text


class GCRTool(QgsMapToolEmitPoint):
    """
    Allow the user to drag select a box and this tool will emit the corner coordinates using the grass_computational_region Signal.  We use
    this to set the bbox for the grass computational region.
    """
    # minlat, maxlat, minlon, maxlon in Map coordinates (WGS84 for Kluster)
    grass_computational_region = Signal(float, float, float, float)

    def __init__(self, canvas):
        self.canvas = canvas
        QgsMapToolEmitPoint.__init__(self, self.canvas)
        self.rubberBand = QgsRubberBand(self.canvas)
        self.rubberBand.setColor(QtCore.Qt.transparent)
        self.rubberBand.setFillColor(QColor(0, 0, 255, 50))

        self.start_point = None
        self.end_point = None
        self.reset()

    def reset(self):
        """
        Clear the rubberband obj and points
        """

        self.start_point = None
        self.end_point = None
        self.isEmittingPoint = False
        self.rubberBand.reset(QgsWkbTypes.PolygonGeometry)

    def canvasPressEvent(self, e):
        """
        Set the start position of the rectangle on click
        """

        self.start_point = self.toMapCoordinates(e.pos())
        self.end_point = self.start_point
        self.isEmittingPoint = True
        self.showRect(self.start_point, self.end_point)

    def canvasReleaseEvent(self, e):
        """
        Finish the rectangle and emit the corner coordinates in map coordinate system
        """

        self.isEmittingPoint = False
        r = self.rectangle()
        if r is not None:
            self.grass_computational_region.emit(r.yMinimum(), r.yMaximum(),
                                                 r.xMinimum(), r.xMaximum())
            print(r)
        self.reset()

    def canvasMoveEvent(self, e):
        """
        On move update the rectangle
        """

        if not self.isEmittingPoint:
            return
        self.end_point = self.toMapCoordinates(e.pos())
        self.showRect(self.start_point, self.end_point)

    def showRect(self, start_point: QgsPoint, end_point: QgsPoint):
        """
        Show the rubberband object from the provided start point to the end point.  Clear out any existing rect.

        Parameters
        ----------
        start_point
            QgsPoint for the start of the rect
        end_point
            QgsPoint for the end of the rect
        """

        self.rubberBand.reset(QgsWkbTypes.PolygonGeometry)
        if start_point.x() == end_point.x() or start_point.y() == end_point.y():
            return

        point1 = QgsPointXY(start_point.x(), start_point.y())
        point2 = QgsPointXY(start_point.x(), end_point.y())
        point3 = QgsPointXY(end_point.x(), end_point.y())
        point4 = QgsPointXY(end_point.x(), start_point.y())

        self.rubberBand.addPoint(point1, False)
        self.rubberBand.addPoint(point2, False)
        self.rubberBand.addPoint(point3, False)
        self.rubberBand.addPoint(point4, True)  # true to update canvas
        self.rubberBand.show()

    def rectangle(self):
        """
        Return the QgsRectangle object for the drawn start/end points
        """

        if self.start_point is None or self.end_point is None:
            return None
        elif self.start_point.x() == self.end_point.x() or self.start_point.y() == self.end_point.y():
            return None
        return QgsRectangle(self.start_point, self.end_point)

    def deactivate(self):
        """
        Turn off the tool
        """
        QgsMapTool.deactivate(self)
        self.deactivated.emit()
        
        
class QueryTool(QgsMapTool):
    """
    Get the value for selected vector feature
    """
    query_position = Signal(float, float)

    def __init__(self, parent):
        self.parent = parent
        QgsMapTool.__init__(self, self.parent)

    def canvasPressEvent(self, e):
        """
        On press we print out the tooltip text to the stdout
        """

        lat, lon = self._get_cursor_position(e)
        print('****************** Vector query tool *************************')
        print(lat, lon)
        print('******************************************************')
        self.query_position.emit(lat, lon)


    def deactivate(self):
        """
        Deactivate the tool
        """
        QgsMapTool.deactivate(self)
        self.deactivated.emit()


    def _get_cursor_position(self, e):
        """
        Get the closest point to the selected location
        """
        x = e.pos().x()
        y = e.pos().y()
        point = self.parent.getCoordinateTransform().toMapCoordinates(x, y)
        return point.y(), point.x()

