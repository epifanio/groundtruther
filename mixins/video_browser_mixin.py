"""Video browser mixin for the GroundTruther dock widget.

``VideoBrowserMixin`` adds a floating video-player dock to the QGIS window
and integrates it with the geo-linked map canvas.

Responsibilities
----------------
* Create and manage the ``VideoPlayerWidget`` (in a ``QDockWidget``).
* Load video path, metadata CSV, and annotation CSV from plugin settings.
* Build a KDTree over video metadata so that map clicks can be translated to
  the nearest video frame (same pattern as the image browser).
* Feed per-frame metadata to ``VideoPlayerWidget.set_frame_metadata()`` on
  every ``frame_changed`` so the metadata panel stays in sync with playback.
* Sync the map view to the GPS position of the current frame when geo-linking
  is enabled.  Handles projection changes by reconnecting to
  ``canvas.destinationCrsChanged`` — the transform is always built fresh from
  the current project CRS so there is no stale cached transform.
* Offer ``_cleanup_video_browser()`` for orderly teardown.
"""
from __future__ import annotations

from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtWidgets import QDockWidget, QAction, QMainWindow
from qgis.core import (
    QgsMessageLog, Qgis,
    QgsPointXY, QgsRectangle, QgsCoordinateReferenceSystem,
    QgsCoordinateTransform, QgsProject,
    QgsVectorLayer, QgsFeature, QgsGeometry, QgsPoint,
    QgsSingleSymbolRenderer, QgsLineSymbol,
)
from qgis.gui import QgsVertexMarker
from qgis.PyQt.QtGui import QColor

from groundtruther.pygui.video_player_gui import VideoPlayerWidget


class VideoBrowserMixin:
    """Mixin: floating video player dock with geo-linking support.

    Expected to be mixed into ``GroundTrutherDockWidget``.  All ``self.*``
    attributes accessed here must be set by ``GroundTrutherDockWidget.__init__``
    before :meth:`_init_video_browser` is called.
    """

    # CRS of all survey metadata CSVs
    _VIDEO_SRC_CRS = "EPSG:4326"

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _init_video_browser(self) -> None:
        """Create the floating video dock and wire all signals."""
        from qgis.utils import iface as _iface

        self._video_dock: QDockWidget | None = None
        self._video_player: VideoPlayerWidget | None = None
        self._video_metadata_df = None
        self._video_kdtree = None
        self._video_annotations: dict = {}
        self._video_geo_link_enabled: bool = True
        self._video_vertex_marker: QgsVertexMarker | None = None
        self._video_track_layer: QgsVectorLayer | None = None

        # Debounce timer: coalesces rapid canvas refresh calls during playback
        # so that the track layer renderer always gets to complete a full cycle.
        self._pending_extent: QgsRectangle | None = None
        self._map_update_timer = QTimer()
        self._map_update_timer.setSingleShot(True)
        self._map_update_timer.setInterval(150)   # ms — ~6 redraws/s max
        self._map_update_timer.timeout.connect(self._flush_map_update)

        # Inner QMainWindow: allows annotation editor to dock inside the player
        # window rather than into the main QGIS window.
        self._video_inner_window = QMainWindow()
        self._video_inner_window.setWindowFlags(Qt.WindowType(1))  # Widget
        self._video_inner_window.statusBar().hide()
        self._video_inner_window.menuBar().hide()

        self._video_player = VideoPlayerWidget()
        self._video_inner_window.setCentralWidget(self._video_player)

        # Outer dock widget (floats in the main QGIS window)
        self._video_dock = QDockWidget("Video Player", _iface.mainWindow())
        self._video_dock.setObjectName("GroundTrutherVideoDock")
        self._video_dock.setAllowedAreas(Qt.DockWidgetArea(15))   # AllDockWidgetAreas
        self._video_dock.setFeatures(
            QDockWidget.DockWidgetFeature(7))    # Closable|Movable|Floatable

        self._video_dock.setWidget(self._video_inner_window)

        # Docked on the right side of QGIS; hidden until a video is loaded.
        # DockWidgetFloatable is set in features so the user can detach it freely.
        _iface.addDockWidget(Qt.DockWidgetArea(2), self._video_dock)
        self._video_dock.hide()

        # frame_changed → update metadata panel + (optionally) pan map
        self._video_player.frame_changed.connect(self._on_video_frame_changed)

        # geo-link checkbox in the player widget drives our internal flag
        self._video_player.geo_link_toggled.connect(self._on_geo_link_toggled)

        # Zoom spinbox change → immediate re-sync so the new level takes effect
        # whether the video is playing or paused.
        self._video_player.zoom_changed.connect(self._on_zoom_level_changed)

        # Track style controls
        self._video_player.track_visibility_changed.connect(self._on_track_visibility_changed)
        self._video_player.track_color_changed.connect(self._on_track_color_changed)
        self._video_player.track_width_changed.connect(self._on_track_width_changed)

        # Re-sync map position whenever the user changes the project CRS
        self.canvas.destinationCrsChanged.connect(self._on_canvas_crs_changed)

        self._video_dock.visibilityChanged.connect(self._on_video_dock_visibility)

        # Toolbar action to show/hide the video dock
        self._wire_video_toolbar_action()

        QgsMessageLog.logMessage(
            "Video browser initialised", "GroundTruther", Qgis.Info)

    def _wire_video_toolbar_action(self) -> None:
        """Add a 'Video Player' toggle to the plugin toolbar if one exists."""
        try:
            from groundtruther.mixins.toolbar_icons import make_toggle_icon
            action = QAction(self)
            action.setIcon(make_toggle_icon("forward.svg"))
            action.setCheckable(True)
            action.setToolTip("Show / hide the Video Player")
            action.triggered.connect(self._toggle_video_dock)
            self.w.toolBar.addAction(action)
            self._video_toolbar_action = action
        except AttributeError:
            self._video_toolbar_action = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show_video_dock(self) -> None:
        """Make the floating video dock visible."""
        if self._video_dock is not None:
            self._video_dock.show()
            self._video_dock.raise_()

    def hide_video_dock(self) -> None:
        """Hide the floating video dock."""
        if self._video_dock is not None:
            self._video_dock.hide()

    def set_video_geo_link(self, enabled: bool) -> None:
        """Enable or disable map-sync when the video frame changes."""
        self._video_geo_link_enabled = enabled
        if self._video_player is not None:
            self._video_player.set_geo_link_enabled(enabled)

    # ------------------------------------------------------------------
    # Settings / data loading
    # ------------------------------------------------------------------

    def _apply_video_settings(self) -> None:
        """Load video file, metadata, and annotation CSV from ``self.settings``.

        Safe to call even when the Video section is absent from older config
        files.  Missing or empty paths are silently skipped.
        """
        video_settings = self.settings.get("Video") or {}
        videofile     = video_settings.get("videofile", "") or ""
        videometadata = video_settings.get("videometadata", "") or ""
        videoannotation = video_settings.get("videoannotation", "") or ""

        if not videofile:
            return

        if self._video_player is None:
            return

        # --- Load the video ---
        loaded = self._video_player.load_video(videofile)
        if not loaded:
            QgsMessageLog.logMessage(
                f"Video browser: cannot open: {videofile}",
                "GroundTruther", Qgis.Warning)

        # --- Load metadata CSV ---
        if videometadata:
            try:
                from gt.video_manager import load_video_metadata_survey, build_kdtree
                self._video_metadata_df = load_video_metadata_survey(videometadata)
                self._video_kdtree = build_kdtree(self._video_metadata_df)
                QgsMessageLog.logMessage(
                    f"Video metadata loaded: {len(self._video_metadata_df)} frames",
                    "GroundTruther", Qgis.Info)
                self._build_video_track_layer()
            except Exception as exc:
                QgsMessageLog.logMessage(
                    f"Video browser: cannot load metadata: {exc}",
                    "GroundTruther", Qgis.Warning)

        # --- Load annotation CSV ---
        if videoannotation:
            try:
                from gt.video_manager import load_video_annotations
                self._video_annotations = load_video_annotations(videoannotation)
                self._video_player.set_annotations(self._video_annotations)
                QgsMessageLog.logMessage(
                    f"Video annotations loaded: {len(self._video_annotations)} frames",
                    "GroundTruther", Qgis.Info)
            except Exception as exc:
                QgsMessageLog.logMessage(
                    f"Video browser: cannot load annotations: {exc}",
                    "GroundTruther", Qgis.Warning)

    # ------------------------------------------------------------------
    # Frame-change handler
    # ------------------------------------------------------------------

    def _metadata_row_for_frame(self, frame_index: int) -> dict | None:
        """Return the metadata dict for the closest row to *frame_index*.

        The metadata CSV is sampled at a much lower rate than the video FPS
        (e.g. one row per 10 s vs 25 fps), so ``Videoseqence`` values never
        align with actual frame numbers.  Instead of an exact label lookup we
        linearly interpolate: frame 0 → row 0, last frame → last row, and
        everything in between proportionally.
        """
        df = self._video_metadata_df
        if df is None or len(df) == 0:
            return None
        total = (self._video_player.total_frames
                 if self._video_player and self._video_player.total_frames > 0
                 else len(df))
        # Clamp and scale frame index to a row position
        frac = max(0.0, min(1.0, frame_index / max(total - 1, 1)))
        row_idx = int(round(frac * (len(df) - 1)))
        return df.iloc[row_idx].to_dict()

    def _on_video_frame_changed(self, frame_index: int) -> None:
        """Update metadata panel and optionally pan the map.

        Called by ``VideoPlayerWidget.frame_changed`` on every frame advance
        (playback tick, manual seek, step buttons).
        """
        if self._video_metadata_df is None:
            return

        pos = self._metadata_row_for_frame(frame_index)
        if pos is None:
            return

        # Update the in-player metadata panel
        self._video_player.set_frame_metadata(pos)

        # Also update the shared Image Metadata tab (optional secondary display)
        try:
            if hasattr(self, "imagemetadata_gui"):
                self.imagemetadata_gui.show_video_frame_metadata(pos)
        except Exception:
            pass

        if self._video_geo_link_enabled:
            self._sync_map_to_position(pos)

    # ------------------------------------------------------------------
    # Geo-linking
    # ------------------------------------------------------------------

    def _sync_map_to_position(self, pos: dict) -> None:
        """Zoom the map canvas to the WGS-84 position in *pos*.

        Mirrors ``ImageBrowserMixin.zoom_to()``:
        * Builds a fresh ``QgsCoordinateTransform`` each call (projection
          changes are always respected — no stale cached transform).
        * Half-extent = ``zoom_level / 10 000`` in destination map units,
          where ``zoom_level`` comes from the spinbox in the video player.
        * Places (or moves) a red × ``QgsVertexMarker`` at the position.
        * Calls ``canvas.setExtent()`` + ``canvas.refresh()``.
        """
        # Use the CP (control-point) position — already converted from DDM
        # to signed decimal degrees by load_video_metadata_survey().
        # Fall back to the platform lat/lon if CP columns are absent.
        lon = pos.get("cp_longitude") or pos.get("longitude")
        lat = pos.get("cp_latitude")  or pos.get("latitude")
        if lon is None or lat is None:
            return
        try:
            src_crs = QgsCoordinateReferenceSystem(self._VIDEO_SRC_CRS)
            dst_crs = self.canvas.mapSettings().destinationCrs()
            if not dst_crs.isValid():
                return

            transform = QgsCoordinateTransform(
                src_crs, dst_crs, QgsProject.instance())
            pt = transform.transform(QgsPointXY(float(lon), float(lat)))

            # --- Vertex marker: update every frame (cheap scene-item move) ---
            if self._video_vertex_marker is None:
                self._video_vertex_marker = QgsVertexMarker(self.canvas)
                self._video_vertex_marker.setColor(QColor(0, 180, 255))
                self._video_vertex_marker.setIconSize(10)
                self._video_vertex_marker.setIconType(QgsVertexMarker.ICON_X)
                self._video_vertex_marker.setPenWidth(3)
            self._video_vertex_marker.setCenter(pt)

            # --- Canvas extent + track layer: debounced ---
            # During playback canvas.refresh() is called at the full video
            # frame rate (e.g. 25 fps).  QGIS cancels in-progress render jobs
            # when a new refresh is requested, so the track layer renderer
            # never gets to complete a cycle and the line stays invisible.
            # We store the desired extent and let a single-shot timer apply it
            # at most every 150 ms, giving the renderer time to finish.
            zoom = self._video_player.zoom_level if self._video_player else 50
            distance = float(zoom) / 10000.0
            self._pending_extent = QgsRectangle(
                pt.x() - distance, pt.y() - distance,
                pt.x() + distance, pt.y() + distance,
            )
            # start() restarts the timer if already running (debounce)
            self._map_update_timer.start()

        except Exception as exc:
            QgsMessageLog.logMessage(
                f"Video geo-link error: {exc}", "GroundTruther", Qgis.Warning)

    def _flush_map_update(self) -> None:
        """Apply the most-recently queued extent and repaint.

        Called by ``_map_update_timer`` (150 ms single-shot) so that rapid
        frame-change events during playback are coalesced into a single canvas
        render cycle.  This gives the QGIS renderer enough time to complete
        a full draw of the track layer before the next extent change arrives.
        """
        if self._pending_extent is None:
            return
        if self._track_layer_valid():
            self._video_track_layer.triggerRepaint()
        self.canvas.setExtent(self._pending_extent)
        self._pending_extent = None
        self.canvas.refresh()

    def _sync_map_to_video_frame(self, frame_index: int) -> None:
        """Pan the map to the recorded position of *frame_index*."""
        pos = self._metadata_row_for_frame(frame_index)
        if pos is not None:
            self._sync_map_to_position(pos)

    def get_video_frame_from_position(self, lon: float, lat: float) -> int | None:
        """Return the nearest frame index for a map-canvas click at *(lon, lat)*."""
        if self._video_kdtree is None or self._video_metadata_df is None:
            return None
        from gt.video_manager import nearest_frame_index
        frame_idx, _ = nearest_frame_index(
            self._video_kdtree, self._video_metadata_df, lon, lat)
        return frame_idx

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_geo_link_toggled(self, enabled: bool) -> None:
        """Called when the user clicks the geo-link checkbox in the player."""
        self._video_geo_link_enabled = enabled

    def _on_zoom_level_changed(self, _value: int) -> None:
        """Re-sync the map immediately when the zoom spinbox changes.

        Without this, the new zoom level only takes effect on the next frame
        change signal, which never arrives when the video is paused.
        """
        if not self._video_geo_link_enabled:
            return
        if self._video_player is None or self._video_metadata_df is None:
            return
        # Cancel any pending debounced update and apply one immediately so the
        # new zoom level is reflected right away rather than on the next tick.
        self._map_update_timer.stop()
        self._sync_map_to_video_frame(self._video_player.current_frame_index)
        # _sync_map_to_position queued a new debounced update; flush it now.
        self._flush_map_update()

    def _on_canvas_crs_changed(self) -> None:
        """Update both the track layer and the vertex marker when the project
        CRS changes.

        Two independent concerns are handled here:

        * **Track layer** — the memory layer is stored in EPSG:4326.  QGIS
          reprojects it on-the-fly, but the render cache is keyed to the old
          CRS so a ``triggerRepaint()`` is needed to flush it and get a clean
          reprojected tile.  This is done unconditionally (geo-link state is
          irrelevant — the layer is visible regardless).

        * **Vertex marker** — ``QgsVertexMarker`` is positioned in map-canvas
          (destination CRS) coordinates.  Its last-set ``center`` is now
          wrong for the new CRS and must be recomputed.  We always reposition
          it from the current frame's geographic coordinates so the cross
          stays on the correct pixel even when geo-link is turned off.
        """
        # --- Track layer: flush the reprojection cache ---
        if self._track_layer_valid():
            self._video_track_layer.triggerRepaint()

        # --- Vertex marker: reproject to the new CRS ---
        if self._video_player is None or self._video_metadata_df is None:
            return
        # Reposition the marker at the current frame's geographic location.
        # _sync_map_to_video_frame builds a fresh QgsCoordinateTransform from
        # the current project CRS, so the result is always correct.
        # Only pan the canvas view if geo-link is active; but always move the
        # marker so it is in the right place if the user re-enables geo-link.
        frame = self._video_player.current_frame_index
        pos = self._metadata_row_for_frame(frame)
        if pos is None:
            return

        lon = pos.get("cp_longitude") or pos.get("longitude")
        lat = pos.get("cp_latitude")  or pos.get("latitude")
        if lon is None or lat is None:
            return

        try:
            from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform
            src_crs = QgsCoordinateReferenceSystem(self._VIDEO_SRC_CRS)
            dst_crs = self.canvas.mapSettings().destinationCrs()
            if not dst_crs.isValid():
                return
            transform = QgsCoordinateTransform(
                src_crs, dst_crs, QgsProject.instance())
            pt = transform.transform(QgsPointXY(float(lon), float(lat)))

            if self._video_vertex_marker is None:
                self._video_vertex_marker = QgsVertexMarker(self.canvas)
                self._video_vertex_marker.setColor(QColor(0, 180, 255))
                self._video_vertex_marker.setIconSize(10)
                self._video_vertex_marker.setIconType(QgsVertexMarker.ICON_X)
                self._video_vertex_marker.setPenWidth(3)
            self._video_vertex_marker.setCenter(pt)
        except Exception as exc:
            QgsMessageLog.logMessage(
                f"Video CRS-change marker update error: {exc}",
                "GroundTruther", Qgis.Warning)
            return

        # Pan the view only when geo-link is active
        if self._video_geo_link_enabled:
            self._sync_map_to_video_frame(frame)

    # ------------------------------------------------------------------
    # Teardown
    # ------------------------------------------------------------------

    def _cleanup_video_browser(self) -> None:
        """Release all video resources and remove the floating dock."""
        # Stop the debounce timer before anything else so it cannot fire
        # against a partially-torn-down object.
        try:
            self._map_update_timer.stop()
        except Exception:
            pass
        self._pending_extent = None

        # Disconnect CRS change signal to avoid callbacks on a dead object
        try:
            self.canvas.destinationCrsChanged.disconnect(
                self._on_canvas_crs_changed)
        except Exception:
            pass

        if self._video_player is not None:
            try:
                self._video_player.cleanup()
            except Exception:
                pass
            self._video_player = None

        if self._video_dock is not None:
            try:
                from qgis.utils import iface as _iface
                _iface.removeDockWidget(self._video_dock)
                self._video_dock.deleteLater()
            except Exception:
                pass
            self._video_dock = None

        # Remove the track layer from the project
        try:
            if self._track_layer_valid():
                QgsProject.instance().removeMapLayer(self._video_track_layer.id())
        except Exception:
            pass
        self._video_track_layer = None

        # Remove the vertex marker from the canvas scene
        try:
            scene = self.canvas.scene() if self.canvas else None
            if scene is not None and self._video_vertex_marker is not None:
                scene.removeItem(self._video_vertex_marker)
        except Exception:
            pass
        self._video_vertex_marker = None

        self._video_metadata_df = None
        self._video_kdtree = None
        self._video_annotations = {}

    # ------------------------------------------------------------------
    # Track layer
    # ------------------------------------------------------------------

    def _build_video_track_layer(self) -> None:
        """Build an in-memory LineString layer from all CP positions and add it
        to the QGIS project (if the 'Show on map' checkbox is checked).

        The layer uses EPSG:4326 as its native CRS because the CP coordinates
        in the metadata CSV are already in decimal degrees.  QGIS reprojects
        on-the-fly when the project uses a different CRS.
        """
        df = self._video_metadata_df
        if df is None or len(df) == 0:
            return

        # Drop rows where CP position is missing
        cp_df = df.dropna(subset=["cp_longitude", "cp_latitude"])
        if len(cp_df) < 2:
            QgsMessageLog.logMessage(
                "Video track: fewer than 2 valid CP positions — track not built",
                "GroundTruther", Qgis.Warning)
            return

        # Remove any previously built track layer
        try:
            if self._track_layer_valid():
                QgsProject.instance().removeMapLayer(self._video_track_layer.id())
        except Exception:
            pass
        self._video_track_layer = None

        # Create memory layer
        layer = QgsVectorLayer(
            "LineString?crs=EPSG:4326",
            "Video GPS Track",
            "memory",
        )
        provider = layer.dataProvider()

        # Build the polyline from CP positions in row order
        points = [
            QgsPoint(float(row["cp_longitude"]), float(row["cp_latitude"]))
            for _, row in cp_df.iterrows()
        ]
        feature = QgsFeature()
        feature.setGeometry(QgsGeometry.fromPolyline(points))
        provider.addFeatures([feature])
        layer.updateExtents()

        # Apply initial style from the player widget
        color = self._video_player.track_color if self._video_player else None
        width = self._video_player.track_width if self._video_player else 0.5
        self._apply_track_style(layer, color, width)

        self._video_track_layer = layer

        # Add to project only when the checkbox says so
        visible = (self._video_player.track_visible
                   if self._video_player else True)
        if visible:
            QgsProject.instance().addMapLayer(layer)

        QgsMessageLog.logMessage(
            f"Video track layer built: {len(points)} vertices",
            "GroundTruther", Qgis.Info)

    @staticmethod
    def _apply_track_style(
        layer: "QgsVectorLayer",
        color: "QColor | None",
        width_mm: float,
    ) -> None:
        """Apply a ``QgsLineSymbol`` renderer to *layer* with the given style."""
        symbol = QgsLineSymbol.createSimple({
            "color": color.name() if color is not None else "#00b4ff",
            "width": str(width_mm),
            "width_unit": "MM",
            "capstyle": "round",
            "joinstyle": "round",
        })
        layer.setRenderer(QgsSingleSymbolRenderer(symbol))

    # ------------------------------------------------------------------
    # Track slots
    # ------------------------------------------------------------------

    def _track_layer_valid(self) -> bool:
        """Return True iff _video_track_layer exists and its C++ object is alive."""
        if self._video_track_layer is None:
            return False
        try:
            # PyQt6 (QGIS 4) ships sip under PyQt6.sip; fall back to bare sip for PyQt5.
            try:
                from PyQt6 import sip
            except ImportError:
                import sip
            if sip.isdeleted(self._video_track_layer):
                self._video_track_layer = None
                return False
        except Exception:
            # sip unavailable — do a cheap attribute probe instead
            try:
                self._video_track_layer.id()
            except RuntimeError:
                self._video_track_layer = None
                return False
        return True

    def _on_track_visibility_changed(self, visible: bool) -> None:
        """Show or hide the track layer in the project/canvas."""
        if not self._track_layer_valid():
            return
        project = QgsProject.instance()
        layer_id = self._video_track_layer.id()
        already_in_project = project.mapLayer(layer_id) is not None
        if visible and not already_in_project:
            # Add with addMapLayer(layer, False) to avoid auto-inserting into
            # the layer tree, then insert manually so we control position.
            project.addMapLayer(self._video_track_layer, False)
            project.layerTreeRoot().insertLayer(0, self._video_track_layer)
        elif already_in_project:
            # Toggle layer-tree visibility — keeps the layer alive in the project.
            node = project.layerTreeRoot().findLayer(layer_id)
            if node is not None:
                node.setItemVisibilityChecked(visible)

    def _on_track_color_changed(self, color: "QColor") -> None:
        """Update the track layer's line colour."""
        if not self._track_layer_valid():
            return
        renderer = self._video_track_layer.renderer()
        if renderer is not None:
            sym = renderer.symbol()
            if sym is not None:
                sym.setColor(color)
                self._video_track_layer.triggerRepaint()

    def _on_track_width_changed(self, width: float) -> None:
        """Update the track layer's line width (mm)."""
        if not self._track_layer_valid():
            return
        renderer = self._video_track_layer.renderer()
        if renderer is not None:
            sym = renderer.symbol()
            if sym is not None:
                from qgis.core import QgsUnitTypes
                sym.setWidth(width)
                sym.setWidthUnit(QgsUnitTypes.RenderMillimeters)
                self._video_track_layer.triggerRepaint()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _toggle_video_dock(self, checked: bool) -> None:
        if checked:
            self.show_video_dock()
        else:
            self.hide_video_dock()

    def _on_video_dock_visibility(self, visible: bool) -> None:
        action = getattr(self, '_video_toolbar_action', None)
        if action is None:
            return
        action.blockSignals(True)
        action.setChecked(visible)
        action.blockSignals(False)
