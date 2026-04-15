"""Annotation editor dock mixin."""
from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import Qt
from qgis.core import Qgis, QgsMessageLog

from groundtruther.pygui.annotation_editor_gui import AnnotationEditorWidget


class AnnotationEditorMixin:
    """Manages the floating annotation-editor dock panel and its toolbar actions."""

    def _init_annotation_editor(self):
        """Create the annotation editor dock and wire toolbar actions.

        Must be called after ``self.imv`` and ``self.w.toolBar`` exist.
        """
        self.annotation_editor = AnnotationEditorWidget(self.imv)
        self.annotation_editor_dock = QtWidgets.QDockWidget("Edit Annotations", self.w)
        self.annotation_editor_dock.setWidget(self.annotation_editor)
        self.annotation_editor_dock.setAllowedAreas(
            Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        self.annotation_editor_dock.hide()
        self.w.addDockWidget(Qt.RightDockWidgetArea, self.annotation_editor_dock)

        # Toggle button in the browser toolbar
        self._ann_editor_action = QtWidgets.QAction("Edit annotations", self.w)
        self._ann_editor_action.setCheckable(True)
        self._ann_editor_action.setToolTip("Show/hide the annotation editor panel")
        self._ann_editor_action.toggled.connect(self._toggle_annotation_editor)
        self.w.toolBar.addSeparator()
        self.w.toolBar.addAction(self._ann_editor_action)

        # Save-all button (visible only when editor is open)
        self._save_ann_action = QtWidgets.QAction("Save annotations", self.w)
        self._save_ann_action.setToolTip("Save all annotation edits back to CSV")
        self._save_ann_action.triggered.connect(self._save_annotations)
        self._save_ann_action.setVisible(False)
        self.w.toolBar.addAction(self._save_ann_action)

        # "Draw new box" toggle action (only visible when editor is open)
        self._draw_ann_action = QtWidgets.QAction("Draw box", self.w)
        self._draw_ann_action.setCheckable(True)
        self._draw_ann_action.setToolTip(
            "Click and drag on the image to draw a new bounding box")
        self._draw_ann_action.toggled.connect(self._toggle_draw_mode)
        self._draw_ann_action.setVisible(False)
        self.w.toolBar.addAction(self._draw_ann_action)

        # Wire editor signals
        self.annotation_editor.annotation_changed.connect(self._on_annotation_changed)
        self.annotation_editor.draw_mode_exited.connect(
            lambda: self._draw_ann_action.setChecked(False))

    def _toggle_annotation_editor(self, checked: bool):
        """Show or hide the annotation editor dock."""
        self.annotation_editor_dock.setVisible(checked)
        self._save_ann_action.setVisible(checked)
        self._draw_ann_action.setVisible(checked)
        if checked:
            self._refresh_known_labels()
            if hasattr(self, 'imageMetadata') and self.imageMetadata is not None:
                annotation = self.imageMetadata["Annotation"].iloc[self.imageindex]
                imagename = self.imageMetadata["Imagename"].iloc[self.imageindex]
                self.annotation_editor.load_image(
                    self.imageindex, imagename,
                    annotation, self.imageannotationfile,
                )
        else:
            self._draw_ann_action.setChecked(False)
            self.annotation_editor.load_image(self.imageindex, "", None, "")
            if self.w.actionAnnotation.isChecked():
                self.add_image_annotation()

    def _refresh_known_labels(self):
        """Extract unique species labels from loaded annotations and push to editor."""
        if not hasattr(self, 'annotation_editor'):
            return
        if not (hasattr(self, 'imageMetadata') and self.imageMetadata is not None):
            return
        if "Annotation" not in self.imageMetadata.columns:
            return
        all_species: set[str] = set()
        for ann in self.imageMetadata["Annotation"]:
            if isinstance(ann, dict) and "Species" in ann:
                all_species.update(ann["Species"])
        if all_species:
            self.annotation_editor.set_known_labels(sorted(all_species))

    def _toggle_draw_mode(self, checked: bool):
        """Enable or disable rubber-band draw mode on the image view."""
        if checked:
            self.annotation_editor.start_draw_mode()
        else:
            self.annotation_editor.stop_draw_mode()

    def _on_annotation_changed(self, image_index: int):
        """Push edited annotation from the editor back into the DataFrame."""
        if self.imageMetadata is None:
            return
        edited = self.annotation_editor.commit()
        self.imageMetadata.at[
            self.imageMetadata.index[image_index], "Annotation"
        ] = edited
        QgsMessageLog.logMessage(
            f"Annotation updated for image index {image_index}",
            'GroundTruther', Qgis.Information,
        )

    def _save_annotations(self):
        """Write all in-memory annotations to CSV via the editor widget."""
        if self.imageMetadata is None:
            return
        self._on_annotation_changed(self.imageindex)
        self.annotation_editor.save_all_to_csv(
            self.imageMetadata, self.imageannotationfile
        )
