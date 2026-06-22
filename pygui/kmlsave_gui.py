#!/usr/bin/env python
"""KML/KMZ report-builder panel.

``SaveKml`` is a ``QWidget`` tab embedded in the main dock.  It lets the user
compose a rich-text description (with images and metadata tables embedded as
HTML), assign KML styling (icon, line/label/polygon colours and alpha), and
save the result as a geo-referenced KMZ file to the configured export
directory.

Key signals received from the dockwidget:
  - ``send_image_path`` → ``from_main_imagepath_signal`` — current image path
  - ``send_imagemetadata_string`` → ``from_main_imagemetadata_signal`` — HTML metadata table

Signals forwarded from the QueryBuilder:
  - ``send_2dgraph_path``, ``send_3dgraph_path``, ``send_selected_points_path``
"""
import sys

from qgis.PyQt.QtCore import Qt, QSize, pyqtSignal, pyqtSlot
from qgis.PyQt.QtGui import QColor, QFont
from qgis.PyQt.QtWidgets import QWidget, QFileDialog, QColorDialog, QToolButton
from qgis.PyQt.QtPrintSupport import QPrinter
from groundtruther.pygui.Ui_kmlsave_ui import Ui_Form
import os
import zipfile
import subprocess
import tempfile
import uuid

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

from groundtruther.configure import get_settings, error_message, log_exception
from qgis.core import Qgis, QgsMessageLog

# from xml.dom import minidom
import codecs
import simplekml
from pathlib import Path
import pathlib
import re
from jinja2 import Environment, FileSystemLoader, select_autoescape

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
    """Report-builder widget that saves a KMZ point with a rich-text description."""

    # procDone = pyqtSignal(str)
    def __init__(self, parent=None):
        super(SaveKml, self).__init__(parent)
        # print(" +++++++++++++ config: ", config)
        self.parent = parent
        self.config = config
        # Use the parent dockwidget's already-validated settings.
        # If for some reason the parent has no settings yet, try to load from
        # disk.  SaveKml does not own a config dialog – that lives on the
        # dockwidget – so there is nothing more we can do here.
        parent_settings = getattr(self.parent, "settings", None)
        self.settings = parent_settings or get_settings(self.config) or {}
        
        # self.settings = get_settings(self.config)
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

        # Extra query-builder products (added programmatically so we don't have
        # to regenerate the stale .ui). Each button inserts the product into the
        # description under a descriptive header and, for image products, queues
        # its file(s) for embedding in the KMZ.
        self.get_sampling = self._add_product_button(
            "SU", "Add sampling unit table from query builder", self.get_sampling_path)
        self.get_stats = self._add_product_button(
            "Σ", "Add statistics table from query builder", self.get_stats_path)
        self.get_histogram = self._add_product_button(
            "H", "Add histogram from query builder", self.get_histogram_path)
        self.get_imageselection = self._add_product_button(
            "IMG", "Add sampling-shape image selection from query builder",
            self.get_imageselection_path)
        # Seafloor-roughness products (pulled from the roughness panel on the
        # parent dock for the current frame / last mosaic).
        self.get_roughness = self._add_product_button(
            "Rgh", "Add roughness metrics (current frame)",
            self.get_roughness_details)
        self.get_microdem = self._add_product_button(
            "DEM", "Add a Micro-DEM 3D snapshot", self.get_microdem_image)
        self.get_spectrum = self._add_product_button(
            "Spec", "Add the spectral-roughness plot", self.get_spectrum_image)
        self.get_mosaic = self._add_product_button(
            "Mos", "Add the last UTM mosaic", self.get_mosaic_image)
        # Classification / ARA + roughness-fusion formula cheat sheet (the report
        # is where substrate / ARA features are surfaced).
        try:
            from groundtruther.pygui.cheatsheet import CheatSheetButton
            self.horizontalLayout.addWidget(CheatSheetButton(
                "03_classification.png", "Seabed classification — formulae"))
        except Exception as exc:  # noqa: BLE001 — info button must never block init
            log_exception("report builder cheat-sheet button", exc, warn=True)
        # icon = self.SelectIcon.itemText(index)
        self.iconpath = imagepath + \
            str(self.SelectIcon.itemText(1)) + str(".png")
        self.altitude_mode = simplekml.AltitudeMode.relativetoground
        # self.update.clicked.connect(self.from_main_signal)
        # self.neweditor.show()
        self.graph2d_path = ""
        self.graph3d_path = ""
        self.selected_points_path = ""
        self.graph2d_string = "None"
        self.graph3d_string = "None"
        self.selected_points_string = "None"
        self.histograms = []            # list of (path, label) — all variants
        self.imageselection_paths = []
        self.stats_html = ""
        self.sampling_html = ""
        self.imageselection_string = "None"
        self._report_env = None

        # Structured products for the styled HTML report (cards, gallery, scrollable
        # tables). The rich-text editor stays the source of truth for *presence*:
        # at save time these items are pruned to what is still in the editor, so
        # deletions propagate while the report keeps its nice rendering.
        self.report_items = []

        self.editor_save.clicked.connect(self.SavetoPDF)

    def _add_report_item(self, item):
        """Record a product for the styled HTML report (skips empty ones)."""
        if item.get("type") == "image" and not item.get("path"):
            return
        if item.get("type") == "gallery" and not item.get("paths"):
            return
        self.report_items.append(item)

    def _add_product_button(self, text, tooltip, slot):
        """Create a small toolbutton in the report toolbar wired to ``slot``."""
        button = QToolButton(self.groupBox_2)
        button.setText(text)
        button.setToolTip(tooltip)
        button.setMinimumSize(QSize(26, 26))
        button.setMaximumSize(QSize(40, 26))
        button.clicked.connect(slot)
        self.horizontalLayout.addWidget(button)
        return button

    def SavetoPDF(self):
        filename = QFileDialog.getSaveFileName(self, 'Save to PDF')
        if filename:
            QgsMessageLog.logMessage(f"SavetoPDF: {filename}", 'GroundTruther', Qgis.Info)
            printer = QPrinter(QPrinter.HighResolution)
            printer.setPageSize(QPrinter.A4)
            printer.setColorMode(QPrinter.Color)
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setOutputFileName(filename[0])
            self.description.document().print_(printer)

    def get_graph2d_path(self):
        self._add_report_item({"type": "image", "header": "ARA Scatterplot",
                               "path": self.graph2d_path})
        self._append_with_header("ARA Scatterplot", self.graph2d_string)

    def get_graph3d_path(self):
        self._add_report_item({"type": "image", "header": "3D Surface Sample",
                               "path": self.graph3d_path})
        self._append_with_header("3D Surface Sample", self.graph3d_string)

    def get_selected_points_path(self):
        # self.image_files_path.append(self.selected_points_path)
        # self.description.append(self.selected_points_path)
        #self.description.verticalScrollBar().setValue(
        #    self.description.verticalScrollBar().maximum()
        #)
        QgsMessageLog.logMessage(f"selected_points_path={self.selected_points_path}, string={self.selected_points_string}", 'GroundTruther', Qgis.Info)

    def _append_with_header(self, header, content):
        """Append a product to the description under an ``<h3>`` header.

        The ``<br>`` before the header separates successive outputs, and the one
        after the header puts a blank line between the header and its content.
        """
        self.description.append(f"<br><h3>{header}</h3><br>{content}<br>")
        self.description.verticalScrollBar().setValue(
            self.description.verticalScrollBar().maximum()
        )

    def get_sampling_path(self):
        self._add_report_item({"type": "table", "header": "Sampling Unit",
                               "html": self.sampling_html})
        self._append_with_header("Sampling Unit", self.sampling_html)

    def get_stats_path(self):
        self._add_report_item({"type": "table", "header": "Statistics",
                               "html": self.stats_html})
        self._append_with_header("Statistics", self.stats_html)

    def get_histogram_path(self):
        # Insert all histogram variants (Density / Group norm / Group scaled),
        # each under its own header.
        for path, label in self.histograms:
            if not path:
                continue
            self._add_report_item({"type": "image", "header": label, "path": path})
            self._append_with_header(
                label, f'<img src="{path}" alt="histogram" height="300"><br>')

    def get_imageselection_path(self):
        header = f"Image Selection ({len(self.imageselection_paths)} images)"
        self._add_report_item({"type": "gallery", "header": header,
                               "paths": list(self.imageselection_paths)})
        self._append_with_header(header, self.imageselection_string)

    # ------------------------------------------------------------------ #
    # Seafloor-roughness products (from the roughness panel on the dock)  #
    # ------------------------------------------------------------------ #

    def _roughness_export_dir(self):
        """Directory for roughness product images (KML export dir, else temp)."""
        kmldir = (self.settings or {}).get("Export", {}).get("kmldir", "")
        return str(kmldir) if kmldir else tempfile.gettempdir()

    def get_roughness_details(self):
        """Insert the current frame's roughness metrics as a table."""
        html = None
        fn = getattr(self.parent, "report_roughness_html", None)
        if callable(fn):
            html = fn()
        if not html:
            error_message("No roughness computed for the current frame.\n"
                          "Open the Seafloor Roughness panel and click Compute.")
            return
        self._add_report_item({"type": "table", "header": "Roughness", "html": html})
        self._append_with_header("Roughness", html)

    def _add_roughness_image(self, export_attr, header, basename):
        """Export a roughness product image via the dock and add it to the report."""
        fn = getattr(self.parent, export_attr, None)
        if not callable(fn):
            error_message("Roughness panel is not available.")
            return
        path = os.path.join(self._roughness_export_dir(),
                            f"{basename}_{uuid.uuid1().hex}.png")
        if not fn(path):
            error_message(
                f"No {header} available yet.\n"
                "Generate it in the Seafloor Roughness panel first.")
            return
        self._add_report_item({"type": "image", "header": header, "path": path})
        self._append_with_header(
            header, f'<img src="{path}" alt="{header}" height="300"><br>')

    def get_microdem_image(self):
        self._add_roughness_image("export_micro_dem_png", "Micro-DEM 3D", "microdem")

    def get_spectrum_image(self):
        self._add_roughness_image(
            "export_spectrum_png", "Spectral Roughness", "spectrum")

    def get_mosaic_image(self):
        self._add_roughness_image("export_mosaic_png", "UTM Mosaic", "mosaic")

    def font_size(self):
        self.description.setFontPointSize(float(self.fontsize.value()))

    def bold_text(self):
        # print(dir(self.description)) 50 57 75
        if self.description.fontWeight() == 75:
            self.description.setFontWeight(QFont.Weight(50))
        else:
            self.description.setFontWeight(QFont.Weight(75))

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
        self.description.setAlignment(Qt.AlignmentFlag(1))

    def align_right(self):
        self.description.setAlignment(Qt.AlignmentFlag(2))

    def align_center(self):
        self.description.setAlignment(Qt.AlignmentFlag(132))

    def align_justify(self):
        self.description.setAlignment(Qt.AlignmentFlag(8))

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

    @pyqtSlot(str)
    def from_querybuilder_stats_signal(self, stats_html):
        self.stats_html = stats_html

    @pyqtSlot(str)
    def from_querybuilder_sampling_signal(self, sampling_html):
        self.sampling_html = sampling_html

    @pyqtSlot(object)
    def from_querybuilder_histograms_signal(self, histograms):
        # histograms: list of (path, label) for every histogram variant
        self.histograms = [(p, l) for p, l in (histograms or []) if p]

    @pyqtSlot(str)
    def from_querybuilder_imageselection_signal(self, paths_joined):
        self.imageselection_paths = [p for p in paths_joined.split("\n") if p]
        self.imageselection_string = "".join(
            f'<img src="{p}" alt="selected image" height="300"><br>'
            for p in self.imageselection_paths
        )

    def filemanager(self):
        # Refresh settings in case the user has just saved a new config
        fresh = get_settings(self.config)
        if fresh:
            self.settings = fresh
        filemanager = self.settings.get("Filesystem", {}).get("filemanager", "")
        kmldir = self.settings.get("Export", {}).get("kmldir", "")
        if not filemanager:
            error_message("No file manager configured.\nSet one in Settings.")
            return
        subprocess.Popen([filemanager, str(kmldir)], stdout=subprocess.PIPE)

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
        QgsMessageLog.logMessage(f"testsignal_lat: lock_location={self.lock_location.isChecked()}", 'GroundTruther', Qgis.Info)
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
        image_path = getattr(self, "image_path", "")
        if image_path:
            self._add_report_item({"type": "image", "header": "Image",
                                   "path": image_path})
        self.description.append(self.currentimagestring)
        self.description.verticalScrollBar().setValue(
            self.description.verticalScrollBar().maximum()
        )

    def addImageMetadata(self):
        metadata_html = getattr(self, "imagemetadata_string", "")
        if metadata_html:
            self._add_report_item({"type": "table", "header": "Image metadata",
                                   "html": metadata_html})
        # Header so it can be pruned from the report when removed from the editor.
        self._append_with_header("Image metadata", metadata_html)

    def cleantext(self):
        self.description.setHtml("")
        self.report_items = []

    def _location_rows(self):
        """Location summary as a list of (label, value) tuples."""
        return [
            ("Longitude", self.longitude.text()),
            ("Latitude", self.latitude.text()),
            ("Offset", self.Offset.value()),
            ("Altitude mode", self.altitude_mode),
        ]

    def _report_header_html(self, name):
        """Title (from the point name) + a location summary table (KML balloon)."""
        summary = "".join(
            f"<tr><td><b>{label}</b></td><td>{value}</td></tr>"
            for label, value in self._location_rows()
        )
        return (
            f'<h1 class="gt-title">{name or "GroundTruther report"}</h1>'
            "<h3>Location summary</h3>"
            '<table class="gt-location" border="1" cellpadding="3" cellspacing="0">'
            f"{summary}</table><hr>"
        )

    @staticmethod
    def _extract_body(full_html):
        """Return the inner ``<body>`` HTML of a QTextEdit ``toHtml()`` document."""
        match = re.search(r"<body[^>]*>(.*)</body>", full_html, re.DOTALL | re.IGNORECASE)
        return match.group(1) if match else full_html

    def _report_template(self):
        """Lazily build the Jinja environment and return the report template."""
        if self._report_env is None:
            templates_dir = Path(__file__).resolve().parents[1] / "config" / "templates"
            self._report_env = Environment(
                loader=FileSystemLoader(str(templates_dir)),
                autoescape=select_autoescape(["html", "j2", "html.j2"]),
            )
        return self._report_env.get_template("report.html.j2")

    def _prune_report_items(self, body_html):
        """Keep only the products still present in *body_html* (the editor).

        Images / galleries are matched by their file name in the editor's
        <img src>; tables by their header text. This keeps the styled report
        (cards, gallery, scrollable tables) while honouring deletions made in
        the editor.
        """
        kept = []
        for item in self.report_items:
            kind = item.get("type")
            if kind == "image":
                path = item.get("path") or ""
                if path and os.path.basename(path) in body_html:
                    kept.append(item)
            elif kind == "gallery":
                paths = [p for p in item.get("paths", [])
                         if os.path.basename(p) in body_html]
                if paths:
                    kept.append({**item, "paths": paths})
            elif kind == "table":
                if item.get("header") and item["header"] in body_html:
                    kept.append(item)
            else:
                kept.append(item)
        return kept

    def _render_html_report(self, name, body_html):
        """Render the styled HTML report from the structured products.

        Products are pruned to what is still in the editor (*body_html*) so the
        saved HTML matches the editor — including deletions — while keeping the
        cards / browsable gallery / scrollable tables. Image ``src`` are
        absolute so the file renders on its own.
        """
        return self._report_template().render(
            title=name or "GroundTruther report",
            location_rows=self._location_rows(),
            items=self._prune_report_items(body_html),
        )

    def _write_html_report(self, kmldirectory, name, body_html):
        """Write the standalone HTML report next to the KMZ."""
        document = self._render_html_report(name, body_html)
        html_path = os.path.join(str(kmldirectory), (name or "report") + ".html")
        with open(html_path, "w", encoding="utf-8") as fh:
            fh.write(document)
        QgsMessageLog.logMessage(f"saved HTML report: {html_path}", 'GroundTruther', Qgis.Info)
        return html_path

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
        fresh = get_settings(self.config)
        if fresh:
            self.settings = fresh
        kmldirectory = self.settings.get("Export", {}).get("kmldir", "")
        if not kmldirectory:
            error_message("No KML export directory configured.\nSet one in Settings.")
            return
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
        name = self.kmlname.text()
        report_header = self._report_header_html(name)
        body_inner = self._extract_body(self.description.toHtml())

        # Companion standalone HTML report (CSS-styled, absolute image paths so
        # it renders on its own), saved next to the KMZ.
        try:
            self._write_html_report(kmldirectory, name, body_inner)
        except Exception as exc:
            log_exception("savekml: write HTML report", exc, warn=True)

        # KML balloon description: title + location summary, then the body with
        # local image dirs rewritten to the KMZ's "files/" folder.
        html_description = report_header + body_inner
        img_src_pattern = re.compile(rb'<img [^>]*src="([^"]+)')
        img_found = img_src_pattern.findall(html_description.encode())
        # Embed exactly the images currently in the editor body (1:1) — dedup,
        # skip empty/missing so simplekml.savekmz never raises.
        seen = set()
        for raw in img_found:
            path = raw.decode()
            if not path or path in seen:
                continue
            seen.add(path)
            if os.path.exists(path):
                kml.addfile(path)
            else:
                QgsMessageLog.logMessage(
                    f"skipping missing report image: {path!r}", 'GroundTruther', Qgis.Warning)
        for path in seen:
            html_description = html_description.replace(
                str(pathlib.Path(path).parents[0]), "files")
        pnt.description = html_description
        pnt.extrude = extrude
        pnt.altitudemode = self.altitude_mode
        # altitudemode = simplekml.AltitudeMode.relativetoground
        kmldir = str(kmldirectory) + "/"
        # kmltosave = kmldir + self.kmlname.text() + ".kml"
        kmztosave = kmldir + self.kmlname.text() + ".kmz"
        QgsMessageLog.logMessage(f"saving KMZ: {kmztosave}", 'GroundTruther', Qgis.Info)
        kml.savekmz(kmztosave)
        # kmz = self.compress_kml(str(kmltosave), str(self.iconpath))
