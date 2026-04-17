"""Video annotation editor mixin for the GroundTruther dock widget.

Mirrors ``AnnotationEditorMixin`` (still-image editor) so the video
annotation workflow is consistent with the image workflow:

* floating ``QDockWidget`` containing a ``VideoAnnotationEditorWidget``
* toolbar "Video Annotations" toggle action + "Save" + "Draw box" actions
* frame changes → ``editor.load_frame()`` (suppressed during playback)
* ``annotation_changed`` signal → syncs edits back into ``_video_annotations``
  and refreshes the video player display

Must be mixed into ``GroundTrutherDockWidget`` *after* ``VideoBrowserMixin``
so that ``self._video_player`` and ``self._video_annotations`` already exist.
"""
from __future__ import annotations

from qgis.PyQt.QtWidgets import QDockWidget, QAction
from qgis.PyQt.QtCore import Qt
from qgis.core import Qgis, QgsMessageLog

from groundtruther.pygui.video_annotation_editor_gui import VideoAnnotationEditorWidget


class VideoAnnotationMixin:
    """Mixin: floating video annotation editor dock with toolbar actions.

    Expected to be mixed into ``GroundTrutherDockWidget``.  All ``self.*``
    attributes accessed here must be set up by ``VideoBrowserMixin`` before
    :meth:`_init_video_annotation_editor` is called.
    """

    # ------------------------------------------------------------------ #
    # Initialisation                                                       #
    # ------------------------------------------------------------------ #

    def _init_video_annotation_editor(self) -> None:
        """Create the annotation editor dock and wire toolbar actions.

        Safe to call even when no video has been loaded yet; the editor
        stays hidden until the user opens it via the toolbar action.
        """
        from qgis.utils import iface as _iface

        self._video_ann_editor: VideoAnnotationEditorWidget | None = None
        self._video_ann_editor_dock: QDockWidget | None = None
        self._video_ann_action: QAction | None = None
        self._video_ann_save_action: QAction | None = None
        self._video_ann_draw_action: QAction | None = None

        if self._video_player is None:
            QgsMessageLog.logMessage(
                "VideoAnnotationMixin: no video player — skipping editor init",
                "GroundTruther", Qgis.Warning)
            return

        self._video_ann_editor = VideoAnnotationEditorWidget(self._video_player)

        self._video_ann_editor_dock = QDockWidget("Annotations")
        self._video_ann_editor_dock.setObjectName(
            "GroundTrutherVideoAnnotationDock")
        self._video_ann_editor_dock.setWidget(self._video_ann_editor)
        self._video_ann_editor_dock.setFeatures(
            QDockWidget.DockWidgetFeature(13))   # Movable|Closable|Floatable

        # Dock inside the video player's inner QMainWindow so the annotation
        # panel lives alongside the player rather than in the main QGIS window.
        self._video_inner_window.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea,
            self._video_ann_editor_dock,
        )
        self._video_ann_editor_dock.hide()

        # Connect editor signals
        self._video_ann_editor.annotation_changed.connect(
            self._on_video_annotation_changed)
        self._video_ann_editor.draw_mode_exited.connect(
            self._on_video_draw_mode_exited)
        self._video_ann_editor.frame_sync_needed.connect(
            self._on_video_ann_frame_sync)
        self._video_ann_editor.seek_requested.connect(
            self._video_player.seek_to_frame)
        self._video_ann_editor.save_clicked.connect(
            self._save_video_annotations)
        self._video_ann_editor.load_clicked.connect(
            self._load_video_annotations_from_file)

        # Connect to frame changes so the editor follows navigation
        self._video_player.frame_changed.connect(
            self._on_frame_changed_for_annotation)

        # Set CSV path if already known from settings
        self._sync_video_ann_csv_path()

        # Toolbar actions
        self._wire_video_annotation_toolbar_actions()

        QgsMessageLog.logMessage(
            "Video annotation editor initialised", "GroundTruther", Qgis.Info)

    def _wire_video_annotation_toolbar_actions(self) -> None:
        """Add annotation actions to the video player's embedded toolbar."""
        toolbar = self._video_player.player_toolbar

        self._video_ann_action = QAction("Annotate", self)
        self._video_ann_action.setCheckable(True)
        self._video_ann_action.setToolTip(
            "Show / hide the video annotation editor panel")
        self._video_ann_action.toggled.connect(
            self._toggle_video_annotation_editor)
        toolbar.addAction(self._video_ann_action)

        toolbar.addSeparator()

        self._video_ann_draw_action = QAction("Draw box", self)
        self._video_ann_draw_action.setCheckable(True)
        self._video_ann_draw_action.setToolTip(
            "Click and drag on the video frame to draw a new bounding box")
        self._video_ann_draw_action.toggled.connect(
            self._toggle_video_draw_mode)
        self._video_ann_draw_action.setVisible(False)
        toolbar.addAction(self._video_ann_draw_action)

        # Save action lives in the editor panel now — keep a None reference
        # so existing code that checks it doesn't crash.
        self._video_ann_save_action = None

    # ------------------------------------------------------------------ #
    # Public helpers                                                       #
    # ------------------------------------------------------------------ #

    def _sync_video_ann_csv_path(self) -> None:
        """Push the annotation CSV path from settings to the editor."""
        if self._video_ann_editor is None:
            return
        path = (self.settings.get("Video") or {}).get("videoannotation", "") or ""
        if path:
            self._video_ann_editor.set_csv_path(path)

    def _refresh_video_known_labels(self) -> None:
        """Build the known-label pool from all loaded video annotations."""
        if self._video_ann_editor is None:
            return
        all_species: set[str] = set()
        for ann in self._video_annotations.values():
            for s in ann.get("species", []):
                all_species.add(s)
        if all_species:
            self._video_ann_editor.set_known_labels(sorted(all_species))

    # ------------------------------------------------------------------ #
    # Slots                                                                #
    # ------------------------------------------------------------------ #

    def _toggle_video_annotation_editor(self, checked: bool) -> None:
        """Show or hide the annotation editor dock."""
        if self._video_ann_editor_dock is None:
            return
        self._video_ann_editor_dock.setVisible(checked)
        if self._video_ann_draw_action:
            self._video_ann_draw_action.setVisible(checked)
        if checked:
            self._refresh_video_known_labels()
            self._video_ann_editor.update_annotated_frames(
                self._video_annotations)
            # Load annotations for the current frame
            if self._video_player is not None:
                frame = self._video_player.current_frame_index
                ann = self._video_annotations.get(frame)
                self._video_ann_editor.load_frame(frame, ann)
        else:
            if self._video_ann_draw_action:
                self._video_ann_draw_action.setChecked(False)
            if self._video_ann_editor:
                self._video_ann_editor.stop_draw_mode()
                self._video_player.set_selected_annotation_idx(None)

    def _toggle_video_draw_mode(self, checked: bool) -> None:
        if self._video_ann_editor is None:
            return
        if checked:
            self._video_ann_editor.start_draw_mode()
        else:
            self._video_ann_editor.stop_draw_mode()

    def _on_video_draw_mode_exited(self) -> None:
        if self._video_ann_draw_action:
            self._video_ann_draw_action.setChecked(False)

    def _on_video_ann_frame_sync(self, frame_index: int) -> None:
        """Update editor frame state without touching draw mode.

        Called just before a draw press so the editor has the correct frame
        index and annotation data.  Unlike load_frame(), this does NOT exit
        draw mode — doing so would cancel the in-progress draw gesture.
        """
        if self._video_ann_editor is None:
            return
        ann = self._video_annotations.get(frame_index)
        self._video_ann_editor.sync_frame_state(frame_index, ann)

    def _on_frame_changed_for_annotation(self, frame_index: int) -> None:
        """Update the editor when the user navigates to a new frame.

        Suppressed during active playback so rapid frame-change events
        don't trigger unsaved-changes prompts.
        """
        if self._video_ann_editor_dock is None:
            return
        if not self._video_ann_editor_dock.isVisible():
            return
        if self._video_player and self._video_player._playing:
            return
        ann = self._video_annotations.get(frame_index)
        self._video_ann_editor.load_frame(frame_index, ann, interactive=True)

    def _on_video_annotation_changed(self, frame_index: int) -> None:
        """Push editor changes back into ``_video_annotations`` and refresh."""
        edited = self._video_ann_editor.commit()
        if edited and edited.get("bboxes"):
            self._video_annotations[frame_index] = edited
        elif frame_index in self._video_annotations:
            del self._video_annotations[frame_index]
        # Refresh the player so the new/removed boxes appear immediately
        if self._video_player is not None:
            self._video_player.set_annotations(self._video_annotations)
        # Keep the annotated-frames list in sync
        self._video_ann_editor.update_annotated_frames(self._video_annotations)

    def _save_video_annotations(self) -> None:
        """Commit the current frame then write all annotations to CSV."""
        if self._video_ann_editor is None:
            return
        # Commit any in-progress edits before saving
        if self._video_player is not None:
            self._on_video_annotation_changed(
                self._video_player.current_frame_index)
        path = (self.settings.get("Video") or {}).get("videoannotation", "") or ""
        self._video_ann_editor.save_all_to_csv(self._video_annotations, path)

    def _load_video_annotations_from_file(self) -> None:
        """Open a file dialog and merge the chosen CSV into _video_annotations."""
        from qgis.PyQt.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            None, "Load video annotations", "", "CSV files (*.csv)")
        if not path:
            return
        try:
            from gt.video_manager import load_video_annotations
            loaded = load_video_annotations(path)
            self._video_annotations.update(loaded)
            self._video_ann_editor.set_csv_path(path)
            if self._video_player is not None:
                self._video_player.set_annotations(self._video_annotations)
            self._video_ann_editor.update_annotated_frames(
                self._video_annotations)
            QgsMessageLog.logMessage(
                f"Video annotations loaded: {len(loaded)} annotated frames "
                f"from {path}",
                "GroundTruther", Qgis.Info)
        except Exception as exc:
            QgsMessageLog.logMessage(
                f"Failed to load video annotations: {exc}",
                "GroundTruther", Qgis.Warning)

    # ------------------------------------------------------------------ #
    # Teardown                                                             #
    # ------------------------------------------------------------------ #

    def _cleanup_video_annotation_editor(self) -> None:
        """Release all annotation editor resources."""
        if self._video_ann_editor is not None:
            try:
                self._video_ann_editor.cleanup()
            except Exception:
                pass
            self._video_ann_editor = None

        if self._video_ann_editor_dock is not None:
            try:
                # The dock lives inside _video_inner_window; that window is
                # destroyed by _cleanup_video_browser, so we only need to
                # remove the reference here.
                self._video_ann_editor_dock.hide()
            except Exception:
                pass
            self._video_ann_editor_dock = None
