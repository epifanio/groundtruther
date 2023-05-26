#!/usr/bin/env python
import sys

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtPrintSupport import QPrinter
from groundtruther.pygui.Ui_kmlsave_ui import Ui_Form
import os
import zipfile
import subprocess

import sys

 
# getting the name of the directory
# where the this file is present.
current = os.path.dirname(os.path.realpath(__file__))
 
# Getting the parent directory name
# where the current directory is present.
parent = os.path.dirname(current)
 
# adding the parent directory to
# the sys.path.
sys.path.append(parent)

from configure import get_settings

# from xml.dom import minidom
import codecs
import simplekml
from pathlib import Path
import pathlib
import re

iconpath = ""
extrudetype = ""
AltitudeMode = ""
VectorLineColorName = ""
VectorLabelColorName = ""
VectorPolygonColorName = ""

apppath = os.path.abspath(os.path.dirname(sys.argv[0]))
imagepath = "%s/qtui/icons/" % (apppath)
filem = "%s/conf/filem.conf" % (apppath)
# configfile = "%s/conf/conf.xml" % (apppath)

# from redox import MapDisplay
# from wordprocessor import TextEditor
from groundtruther.config.config import config

class SaveKml(QWidget, Ui_Form):
    # procDone = pyqtSignal(str)
    def __init__(self, parent=None):
        super(SaveKml, self).__init__(parent)
        self.config =config # os.environ.get('HBC_CONFIG')
        self.settings = get_settings(self.config)
        self.setupUi(self)
        self.lon = 0
        self.lat = 0
        self.Rollchange = 0
        self.Pitchchange = 0
        self.Headchange = 0
        self.Zoomchange = 0
        self.Rangechange = 0
        self.description.undoAvailablen = True
        # self.neweditor = TextEditor(self.groupBox_2)
        self.linecolor.clicked.connect(self.setVectorLineColor)
        self.labelcolor.clicked.connect(self.setVectorLabelColor)
        self.polygoncolor.clicked.connect(self.setVectorPolygonColor)
        self.LabelAlpha.valueChanged.connect(self.SetLabelAlpha)
        self.LineAlpha.valueChanged.connect(self.SetLineAlpha)
        self.PolygonAlpha.valueChanged.connect(self.SetPolygonAlpha)
        self.LineWidth.valueChanged.connect(self.SetLineWidth)
        self.Offset.valueChanged.connect(self.SetOffset)
        self.save.clicked.connect(self.savekml)
        self.SelectIcon.currentIndexChanged.connect(self.GetIcon)
        self.altitudeMode.currentIndexChanged.connect(self.get_altitude)
        self.update.clicked.connect(self.aggiorna)
        # uncomment if running in docker ?
        # self.opendir.hide()
        self.opendir.clicked.connect(self.filemanager)
        # TODO: create link widget
        # self.addlink.clicked.connect(self.addlink)
        self.addlink.hide()
        self.clean.clicked.connect(self.cleantext)
        self.addimage.clicked.connect(self.addlinkf)
        self.addimage.clicked.connect(self.addImageMetadata)

        # self.addimage.clicked.connect(self.description.cut)
        # self.save.clicked.connect(self.description.paste)
        self.editor_copy.clicked.connect(self.description.copy)
        self.editor_cut.clicked.connect(self.description.cut)
        self.editor_paste.clicked.connect(self.description.paste)
        self.editor_undo.clicked.connect(self.description.undo)
        self.editor_redo.clicked.connect(self.description.redo)
        self.editor_select_all.clicked.connect(self.description.selectAll)
        self.editor_bold.clicked.connect(self.bold_text)
        self.editor_italic.clicked.connect(self.italic_text)
        self.editor_underline.clicked.connect(self.underline_text)
        self.editor_align_left.clicked.connect(self.align_left)
        self.editor_align_right.clicked.connect(self.align_right)
        self.editor_align_center.clicked.connect(self.align_center)
        self.editor_align_justify.clicked.connect(self.align_justify)
        self.fontsize.valueChanged.connect(self.font_size)
        self.fontComboBox.currentFontChanged.connect(
            self.description.setCurrentFont)
        self.get_2dgraph.clicked.connect(self.get_graph2d_path)
        self.get_3dgraph.clicked.connect(self.get_graph3d_path)
        self.get_selected_points.clicked.connect(self.get_selected_points_path)
        # icon = self.SelectIcon.itemText(index)
        self.iconpath = imagepath + \
            str(self.SelectIcon.itemText(1)) + str(".png")
        self.altitude_mode = simplekml.AltitudeMode.relativetoground
        # self.update.clicked.connect(self.from_main_signal)
        self.image_files_path = []
        # self.neweditor.show()
        self.graph2d_path = ""
        self.graph3d_path = ""
        self.selected_points_path = ""
        self.graph2d_string = "None"
        self.graph3d_string = "None"
        self.selected_points_string = "None"
        
        self.editor_save.clicked.connect(self.SavetoPDF)

    def SavetoPDF(self):
        filename = QFileDialog.getSaveFileName(self, 'Save to PDF')
        if filename:
            print('filename:', filename)
            printer = QPrinter(QPrinter.HighResolution)
            printer.setPageSize(QPrinter.A4)
            printer.setColorMode(QPrinter.Color)
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setOutputFileName(filename[0])
            self.description.document().print_(printer)

    def get_graph2d_path(self):
        self.image_files_path.append(self.graph2d_path)
        self.description.append(self.graph2d_string)
        self.description.verticalScrollBar().setValue(
            self.description.verticalScrollBar().maximum()
        )

    def get_graph3d_path(self):
        self.image_files_path.append(self.graph3d_path)
        self.description.append(self.graph3d_string)
        self.description.verticalScrollBar().setValue(
            self.description.verticalScrollBar().maximum()
        )

    def get_selected_points_path(self):
        # self.image_files_path.append(self.selected_points_path)
        # self.description.append(self.selected_points_path)
        #self.description.verticalScrollBar().setValue(
        #    self.description.verticalScrollBar().maximum()
        #)
        print(self.selected_points_path, self.selected_points_string)
        pass

    def font_size(self):
        self.description.setFontPointSize(float(self.fontsize.value()))

    def bold_text(self):
        # print(dir(self.description)) 50 57 75
        if self.description.fontWeight() == 75:
            self.description.setFontWeight(QFont.Normal)
        else:
            self.description.setFontWeight(QFont.Bold)

    def italic_text(self):
        if self.description.fontItalic() == False:
            self.description.setFontItalic(True)
        else:
            self.description.setFontItalic(False)

    def underline_text(self):
        if self.description.fontUnderline() == False:
            self.description.setFontUnderline(True)
        else:
            self.description.setFontUnderline(False)

    def align_left(self):
        self.description.setAlignment(Qt.AlignLeft)

    def align_right(self):
        self.description.setAlignment(Qt.AlignRight)

    def align_center(self):
        self.description.setAlignment(Qt.AlignCenter)

    def align_justify(self):
        self.description.setAlignment(Qt.AlignJustify)

    @pyqtSlot(str)
    def from_main_imagepath_signal(self, image_path):
        # self.currentimagestring = message
        # image_pathlib = Path(image_path)
        # self.currentimagestring = (
        #    f'<img src="files/{image_pathlib.name}" alt="Smiley face" height="300"><br>'
        # )
        self.currentimagestring = (
            f'<img src="{image_path}" alt="Smiley face" height="300"><br>'
        )
        self.image_path = image_path

    @pyqtSlot(str)
    def from_main_imagemetadata_signal(self, imagemetadata_string):
        self.currentimagemetadatastring = (
            f'<br>{imagemetadata_string}<br>'
        )
        self.imagemetadata_string = imagemetadata_string

    @pyqtSlot(str)
    def from_querybuilder_2dplot_signal(self, graph2d_path):
        self.graph2d_string = (
            f'<img src="{graph2d_path}" alt="Smiley face" height="300"><br>'
        )
        self.graph2d_path = graph2d_path

    @pyqtSlot(str)
    def from_querybuilder_3dplot_signal(self, graph3d_path):
        self.graph3d_string = (
            f'<img src="{graph3d_path}" alt="Smiley face" height="300"><br>'
        )
        self.graph3d_path = graph3d_path
        
    @pyqtSlot(str)
    def from_querybuilder_selected_points_signal(self, selected_points_path):
        self.selected_points_string = (
            f'<img src="{selected_points_path}" alt="Smiley face" height="300"><br>'
        )
        self.selected_points_path = selected_points_path

    def filemanager(self):
        self.settings = get_settings(self.config)
        filemanager = self.settings["Filesystem"]["filemanager"]
        kmldir = self.settings["Export"]["kmldir"]
        output = subprocess.Popen(
            [filemanager, str(kmldir)], stdout=subprocess.PIPE
        ).communicate()[0]

    def compress_kml(self, outfile, icon):
        directory = os.path.dirname(str(outfile))
        iconname = icon.split("/")[-1]
        icontosave = directory + "/" + iconname
        # string = "cp %s %s" % (icon, icontosave)
        # cp = os.system(string)
        subprocess.Popen(["cp", icon, icontosave])
        outfilename = outfile.split("/")
        outfilename = outfilename[-1]
        kmz = outfile.split(".")[0] + ".kmz"
        with zipfile.ZipFile(str(kmz), "w") as z:
            z.write(str(outfile))
            z.write(str(icontosave))
            z.close

    @pyqtSlot(str)
    def testsignal_lon(self, message):
        # if not self.lock_location.isChecked():
        self.longitude.setText(message)

    @pyqtSlot(str)
    def testsignal_lat(self, message):
        # if not self.lock_location.isChecked():
        print("heloooo   $$$$$$$  hello helooo ")
        print(self.lock_location.isChecked())
        self.latitude.setText(message)

    def setLonValue(self, lon):
        self.lon = lon

    def setLatValue(self, lat):
        self.lat = lat

    def setChangeRoll(self, Rollchange):
        self.Rollchange = Rollchange

    def setChangeZoom(self, Zoomchange):
        self.Zoomchange = Zoomchange

    def setChangeRange(self, Rangechange):
        self.Rangechange = Rangechange

    def setChangePitch(self, Pitchchange):
        self.Pitchchange = Pitchchange

    def setChangeHead(self, Headchange):
        self.Headchange = Headchange

    def aggiorna(self):
        self.settings = get_settings(self.config)
        newlon = str(self.lon)
        newlat = str(self.lat)
        self.longitude.setText(newlon)
        self.latitude.setText(newlat)
        self.Roll.setText(str(self.Rollchange))
        self.Pitch.setText(str(self.Pitchchange))
        self.Head.setText(str(self.Headchange))
        self.Zoom.setText(str(self.Zoomchange))
        self.Range.setText(str(self.Rangechange))

    def get_altitude(self, index):
        self.altitude_mode = self.altitudeMode.itemText(index)
        return self.altitude_mode

    def GetIcon(self, index):
        # global iconpath
        icon = self.SelectIcon.itemText(index)
        self.iconpath = imagepath + str(icon) + str(".png")
        return self.iconpath

    def setVectorLineColor(self):
        global VectorLineColor
        global VectorLineColorName
        VectorLineColor = QColorDialog.getColor()
        VectorLineColorName = VectorLineColor.name()
        if VectorLineColor.isValid():
            self.linecolorlabel.setStyleSheet(
                "QWidget { background-color: %s }" % VectorLineColor.name()
            )
            return VectorLineColor.name()
        return VectorLineColorName

    def setVectorLabelColor(self):
        global VectorLabelColor
        global VectorLabelColorName
        VectorLabelColor = QColorDialog.getColor()
        VectorLabelColorName = VectorLabelColor.name()
        if VectorLabelColor.isValid():
            self.labelcolorlabel.setStyleSheet(
                "QWidget { background-color: %s }" % VectorLabelColor.name()
            )
            return VectorLabelColor.name()
        return VectorLabelColorName

    def setVectorPolygonColor(self):
        global VectorPolygonColor
        global VectorPolygonColorName
        VectorPolygonColor = QColorDialog.getColor()
        VectorPolygonColorName = VectorPolygonColor.name()
        if VectorPolygonColor.isValid():
            self.polygoncolorlabel.setStyleSheet(
                "QWidget { background-color: %s }" % VectorPolygonColor.name()
            )
            return VectorPolygonColor.name()
        return VectorPolygonColorName

    def SetLabelAlpha(self, ap):
        self.labelalpha = int(ap)
        self.LabelAlpha.setRange(0, 255)
        self.LabelAlpha.setValue(self.labelalpha)

    def SetLineAlpha(self, ap):
        self.linealpha = int(ap)
        self.LineAlpha.setRange(0, 255)
        self.LineAlpha.setValue(self.linealpha)

    def SetPolygonAlpha(self, ap):
        self.polygonalpha = int(ap)
        self.PolygonAlpha.setRange(0, 255)
        self.PolygonAlpha.setValue(self.polygonalpha)

    def SetLineWidth(self, wd):
        self.linewidth = int(wd)
        self.LineWidth.setRange(0, 99)
        self.LineWidth.setValue(self.linewidth)

    def SetOffset(self, ofst):
        self.offset = float(ofst)
        self.Offset.setRange(-10000, 1000000)
        self.Offset.setValue(self.offset)

    # def textlink(self):
    #     link = '<img src="/Users/epi/Desktop/201503.20150619.181141498.204632.jpeg" alt="Smiley face" height="50%"><br>'
    #     return link

    def addlinkf(self):
        # link = self.textlink()
        # self.description.setHtml(unicode(link))
        # self.description.append(str(link))
        self.image_files_path.append(self.image_path)
        self.description.append(self.currentimagestring)
        self.description.verticalScrollBar().setValue(
            self.description.verticalScrollBar().maximum()
        )

    def addImageMetadata(self):
        # link = self.textlink()
        # self.description.setHtml(unicode(link))
        # self.description.append(str(link))
        # self.image_files_path.append(self.image_path)
        self.description.append(self.currentimagemetadatastring)
        self.description.verticalScrollBar().setValue(
            self.description.verticalScrollBar().maximum()
        )

    def cleantext(self):
        self.description.setHtml("")
        self.image_files_path = []

    def savekml(self):
        # vedi di aggiungere zoom,range e view type ... magari link a immagini ???
        # aggiungi un "salva in sqlite" il db deve essere inizializzato nelle preferenze
        LabelAlpha = self.LabelAlpha.value()
        LineAlpha = self.LineAlpha.value()
        PolygonAlpha = self.PolygonAlpha.value()
        labalpha = hex(int(LabelAlpha))
        linalpha = hex(int(LineAlpha))
        polalpha = hex(int(PolygonAlpha))
        labalpha = labalpha.split("x")
        linalpha = linalpha.split("x")
        polalpha = polalpha.split("x")
        labalpha = labalpha[-1]
        linalpha = linalpha[-1]
        polalpha = polalpha[-1]
        if len(labalpha) == 1:
            labalpha = str("0") + labalpha
        if len(linalpha) == 1:
            linalpha = str("0") + linalpha
        if len(polalpha) == 1:
            polalpha = str("0") + polalpha
        colorlabel = VectorLabelColorName
        colorline = VectorLineColorName
        colorpolygon = VectorPolygonColorName
        colorlabel = colorlabel[1:]
        colorlabelR = colorlabel[0:2]
        colorlabelG = colorlabel[2:4]
        colorlabelB = colorlabel[4:6]
        colorlabel = colorlabelB + colorlabelG + colorlabelR
        colorlabel = str(labalpha) + colorlabel
        colorline = colorline[1:]
        colorlineR = colorline[0:2]
        colorlineG = colorline[2:4]
        colorlineB = colorline[4:6]
        colorline = colorlineB + colorlineG + colorlineR
        colorline = str(linalpha) + colorline
        colorpolygon = colorpolygon[1:]
        colorpolygonR = colorpolygon[0:2]
        colorpolygonG = colorpolygon[2:4]
        colorpolygonB = colorpolygon[4:6]
        colorpolygon = colorpolygonB + colorpolygonG + colorpolygonR
        colorpolygon = str(polalpha) + colorpolygon
        tessellate = 0
        extrude = 0
        self.settings = get_settings(self.config)
        kmldirectory = self.settings["Export"]["kmldir"]
        if self.Tessellate.isChecked():
            tessellate = 1
        if self.Extrude.isChecked():
            extrude = 1
        kml = simplekml.Kml()
        pnt = kml.newpoint(name=self.kmlname.text())
        pnt.coords = [
            (self.longitude.text(), self.latitude.text(), self.Offset.value())
        ]
        style = simplekml.Style()
        style.labelstyle.color = colorlabel  # simplekml.Color.red  # Make the text red
        style.labelstyle.scale = 1  # Make the text twice as big
        style.iconstyle.icon.href = self.iconpath
        style.linestyle.color = colorline
        style.linestyle.width = self.LineWidth.value()
        pnt.style = style
        html_description = self.description.toHtml()
        img_src_pattern = re.compile(rb'<img [^>]*src="([^"]+)')
        img_found = img_src_pattern.findall(html_description.encode())
        for i in img_found:
            html_description = html_description.replace(
                str(pathlib.Path(i.decode()).parents[0]), "files"
            )
        pnt.description = html_description
        pnt.extrude = extrude
        pnt.altitudemode = self.altitude_mode
        for i in self.image_files_path:
            kml.addfile(i)
        # altitudemode = simplekml.AltitudeMode.relativetoground
        kmldir = str(kmldirectory) + "/"
        # kmltosave = kmldir + self.kmlname.text() + ".kml"
        print('kmldir: ', kmldir)
        print('kmlname: ',self.kmlname.text())
        kmztosave = kmldir + self.kmlname.text() + ".kmz"
        # kml.save(kmltosave)
        print('kmztosave: ', kmztosave)
        kml.savekmz(kmztosave)
        # kmz = self.compress_kml(str(kmltosave), str(self.iconpath))
