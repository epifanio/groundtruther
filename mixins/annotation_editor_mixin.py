"""Annotation editor dock mixin."""
from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import Qt
from qgis.core import Qgis, QgsMessageLog

from groundtruther.pygui.annotation_editor_gui import AnnotationEditorWidget


class AnnotationEditorMixin:
    """Manages the floating annotation-editor dock panel and its toolbar actions."""

    def _init_annotation_editor(self):
        """Create the annotation editor dock and wire toolbar actions.

        Must be called after _init_image_browser_dock() so that
        self._image_inner_window and self._image_toolbar exist.
        """
        self.annotation_editor = AnnotationEditorWidget(self.imv)
        self.annotation_editor_dock = QtWidgets.QDockWidget("Edit Annotations")
        self.annotation_editor_dock.setWidget(self.annotation_editor)
        self.annotation_editor_dock.setAllowedAreas(
            Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.LeftDockWidgetArea)
        self.annotation_editor_dock.hide()
        # Dock inside the image browser's inner window (mirrors video annotation pattern)
        self._image_inner_window.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self.annotation_editor_dock)

        # Toolbar lives in the image browser window
        toolbar = self._image_toolbar

        self._ann_editor_action = QtWidgets.QAction("Annotate", self._image_inner_window)
        self._ann_editor_action.setCheckable(True)
        self._ann_editor_action.setToolTip("Show/hide the annotation editor panel")
        self._ann_editor_action.toggled.connect(self._toggle_annotation_editor)
        toolbar.addAction(self._ann_editor_action)

        toolbar.addSeparator()

        self._draw_ann_action = QtWidgets.QAction("Draw box", self._image_inner_window)
        self._draw_ann_action.setCheckable(True)
        self._draw_ann_action.setToolTip(
            "Click and drag on the image to draw a new bounding box")
        self._draw_ann_action.toggled.connect(self._toggle_draw_mode)
        self._draw_ann_action.setVisible(False)
        toolbar.addAction(self._draw_ann_action)

        # Wire editor signals
        self.annotation_editor.annotation_changed.connect(self._on_annotation_changed)
        self.annotation_editor.draw_mode_exited.connect(
            lambda: self._draw_ann_action.setChecked(False))
        self.annotation_editor.seek_requested.connect(self._on_annotation_seek_image)
        self.annotation_editor.save_clicked.connect(self._save_annotations)
        self.annotation_editor.load_clicked.connect(self._load_annotations_from_file)

    def _toggle_annotation_editor(self, checked: bool):
        """Show or hide the annotation editor dock."""
        self.annotation_editor_dock.setVisible(checked)
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
                self.annotation_editor.update_annotated_images(self.imageMetadata)
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
        # Keep the annotated-images list in sync
        self.annotation_editor.update_annotated_images(self.imageMetadata)
        QgsMessageLog.logMessage(
            f"Annotation updated for image index {image_index}",
            'GroundTruther', Qgis.Info,
        )

    def _on_annotation_seek_image(self, image_index: int) -> None:
        """Navigate the image browser to *image_index* when user clicks the list."""
        if self.imageMetadata is None:
            return
        max_idx = len(self.imageMetadata) - 1
        image_index = max(0, min(image_index, max_idx))
        # Setting the slider triggers setValueImageIndexspinBox → add_image
        self.w.ImageIndexSlider.setValue(image_index)

    def _save_annotations(self):
        """Commit the current image then write all annotations to CSV."""
        if self.imageMetadata is None:
            return
        self._on_annotation_changed(self.imageindex)
        self.annotation_editor.save_all_to_csv(
            self.imageMetadata, self.imageannotationfile
        )

    def _load_annotations_from_file(self) -> None:
        """Open a file dialog and reload annotations from the chosen CSV."""
        from qgis.PyQt.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            None, "Load image annotations", "", "CSV files (*.csv)")
        if not path:
            return
        try:
            from groundtruther.ioutils import parse_annotation
            from groundtruther.gt import image_manager as img_mgr
            annotations_by_image = parse_annotation(path)
            self.imageMetadata = img_mgr.attach_annotations(
                self.imageMetadata, annotations_by_image)
            self.imageannotationfile = path
            self.annotation_editor.update_annotated_images(self.imageMetadata)
            # Reload current image in editor with fresh annotation data
            annotation = self.imageMetadata["Annotation"].iloc[self.imageindex]
            imagename  = self.imageMetadata["Imagename"].iloc[self.imageindex]
            self.annotation_editor.load_image(
                self.imageindex, imagename, annotation, path)
            self._refresh_known_labels()
            QgsMessageLog.logMessage(
                f"Image annotations loaded from {path}", 'GroundTruther', Qgis.Info)
        except Exception as exc:
            QgsMessageLog.logMessage(
                f"Failed to load image annotations: {exc}",
                'GroundTruther', Qgis.Warning)
