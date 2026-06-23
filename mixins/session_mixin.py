"""Persist / restore GroundTruther UI session state to a JSON sidecar file.

The file path is configured in Settings (``Session.groundtruther_project``).
It is written whenever the QGIS project is saved, when the plugin closes, and
on demand via a toolbar action; it is loaded at plugin start.  This lets the
user return to the same image index, zoom, query-builder selection, video
position and dock layout without re-doing setup.

Only *UI/session* state is stored — data source paths stay in config.yaml.
Every capture/apply step is defensive: a missing widget or stale key is logged
and skipped, never raised, so a partial or older session file stays usable.
"""
import os

from qgis.PyQt.QtWidgets import QAction, QFileDialog, QSpinBox, QDoubleSpinBox
from qgis.core import Qgis, QgsMessageLog

from groundtruther.gt.session_state import serialize, deserialize, default_state
from groundtruther.configure import log_exception

_BEAM_BUTTONS = ("raw_beam", "left_beam", "right_beam", "fold_beam")


class SessionMixin:
    """Save/restore restorable UI state to a configurable JSON file."""

    # ------------------------------------------------------------------ #
    # Lifecycle                                                            #
    # ------------------------------------------------------------------ #

    def _init_session(self) -> None:
        """Add the toolbar action, hook QGIS project-save, and load at start.

        Must run after all dock-creating ``_init_*`` methods and ``_init_layout``
        so every widget exists and the QSettings layout has already been applied
        (a configured session file then takes precedence).
        """
        try:
            from groundtruther.mixins.toolbar_icons import apply_icon
            action = QAction(self)
            apply_icon(action, "floppy-disk.svg")
            action.setToolTip("Save GroundTruther session")
            action.triggered.connect(lambda: self.save_session())
            self.w.toolBar.addAction(action)
            self._session_action = action
        except Exception as exc:
            log_exception("_init_session: toolbar action", exc, warn=True)

        try:
            self.project.projectSaved.connect(self._on_project_saved)
        except Exception as exc:
            log_exception("_init_session: projectSaved hook", exc, warn=True)

        self.load_session()

    def _teardown_session(self) -> None:
        """Save (if configured) and disconnect the project-save hook."""
        try:
            path = self._session_path()
            if path:
                self.save_session(path)
        except Exception as exc:
            log_exception("_teardown_session: save", exc, warn=True)
        try:
            self.project.projectSaved.disconnect(self._on_project_saved)
        except (TypeError, RuntimeError):
            pass  # never connected / already gone

    # ------------------------------------------------------------------ #
    # Save / load                                                          #
    # ------------------------------------------------------------------ #

    def _session_path(self):
        """Return the configured session-file path, or ``None`` if unset."""
        settings = getattr(self, "settings", None) or {}
        section = settings.get("Session") or {}
        path = section.get("groundtruther_project")
        return path.strip() if isinstance(path, str) and path.strip() else None

    def _on_project_saved(self) -> None:
        path = self._session_path()
        if path:
            self.save_session(path)

    def save_session(self, path=None) -> None:
        """Write the current session state to *path* (or the configured one).

        With no configured path and no argument, prompts for a file.
        """
        path = path or self._session_path()
        if not path:
            path, _ = QFileDialog.getSaveFileName(
                self, "Save GroundTruther session", "",
                "GroundTruther session (*.json);;All files (*)")
            if not path:
                return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(serialize(self._capture_session_state()))
            QgsMessageLog.logMessage(
                f"saved GroundTruther session: {path}", 'GroundTruther', Qgis.Info)
        except Exception as exc:
            log_exception("save_session", exc, warn=True)

    def load_session(self, path=None) -> None:
        """Load and apply session state from *path* (or the configured one)."""
        path = path or self._session_path()
        if not path or not os.path.exists(path):
            return
        try:
            with open(path, encoding="utf-8") as fh:
                state = deserialize(fh.read())
        except Exception as exc:
            log_exception("load_session: read", exc, warn=True)
            return
        self._apply_session_state(state)
        QgsMessageLog.logMessage(
            f"loaded GroundTruther session: {path}", 'GroundTruther', Qgis.Info)

    # ------------------------------------------------------------------ #
    # Capture                                                              #
    # ------------------------------------------------------------------ #

    def _capture_session_state(self) -> dict:
        state = default_state()

        try:
            state["image"]["index"] = int(self.w.ImageIndexSlider.value())
            state["image"]["zoom"] = int(self.w.range.value())
            state["image"]["annotation_confidence"] = float(
                self.w.annotation_confidence_spinBox.value())
            state["image"]["map_sync"] = bool(self.w.zoomto.isChecked())
        except Exception as exc:
            log_exception("_capture_session_state: image", exc, warn=True)

        try:
            player = getattr(self, "_video_player", None)
            if player is not None:
                state["video"]["frame"] = int(player.current_frame_index())
            state["video"]["geo_link"] = bool(
                getattr(self, "_video_geo_link_enabled", True))
        except Exception as exc:
            log_exception("_capture_session_state: video", exc, warn=True)

        try:
            qb = getattr(self, "querybuilder", None)
            if qb is not None:
                q = state["query"]
                q["shape"] = qb.qb_shapeselection.currentText()
                q["backscatter_field"] = qb.set_backscatter_field.currentText()
                q["beam"] = self._capture_beam(qb)
                q["longitude"] = qb.qb_longitude.text()
                q["latitude"] = qb.qb_latitude.text()
                q["ellipse_major"] = qb.qb_ellipsemajoraxis.text()
                q["ellipse_minor"] = qb.qb_ellipseminoraxis.text()
                q["ellipse_orientation"] = qb.qb_ellipseorientation.text()
                q["rect_l1"] = qb.qb_rectangle_l1.text()
                q["rect_l2"] = qb.qb_rectangle_l2.text()
        except Exception as exc:
            log_exception("_capture_session_state: query", exc, warn=True)

        try:
            state["layout"] = self._capture_layout()
        except Exception as exc:
            log_exception("_capture_session_state: layout", exc, warn=True)

        return state

    @staticmethod
    def _capture_beam(qb):
        for name in _BEAM_BUTTONS:
            widget = getattr(qb, name, None)
            if widget is not None and widget.isChecked():
                return name
        return None

    # ------------------------------------------------------------------ #
    # Apply                                                                #
    # ------------------------------------------------------------------ #

    def _apply_session_state(self, state: dict) -> None:
        image = state.get("image") or {}
        try:
            if image.get("zoom") is not None:
                self.w.range.setValue(int(image["zoom"]))
            if image.get("annotation_confidence") is not None:
                self.w.annotation_confidence_spinBox.setValue(
                    float(image["annotation_confidence"]))
            if image.get("map_sync") is not None:
                self.w.zoomto.setChecked(bool(image["map_sync"]))
            if image.get("index") is not None:
                self.w.ImageIndexSlider.setValue(self._clamp_image_index(image["index"]))
        except Exception as exc:
            log_exception("_apply_session_state: image", exc, warn=True)

        video = state.get("video") or {}
        try:
            if video.get("geo_link") is not None and hasattr(self, "set_video_geo_link"):
                self.set_video_geo_link(bool(video["geo_link"]))
            player = getattr(self, "_video_player", None)
            if player is not None and video.get("frame") is not None:
                player.seek_to_frame(int(video["frame"]))
        except Exception as exc:
            log_exception("_apply_session_state: video", exc, warn=True)

        qb = getattr(self, "querybuilder", None)
        if qb is not None:
            try:
                self._apply_query_state(qb, state.get("query") or {})
            except Exception as exc:
                log_exception("_apply_session_state: query", exc, warn=True)

        try:
            if state.get("layout"):
                self._apply_layout(state["layout"])
        except Exception as exc:
            log_exception("_apply_session_state: layout", exc, warn=True)

    def _clamp_image_index(self, index):
        index = int(index)
        meta = getattr(self, "imageMetadata", None)
        if meta is not None and len(meta):
            index = max(0, min(index, len(meta) - 1))
        return max(0, index)

    @staticmethod
    def _set_combo(combo, value):
        if value:
            i = combo.findText(value)
            if i >= 0:
                combo.setCurrentIndex(i)

    @staticmethod
    def _set_text(widget, value):
        """Set a restored value on a line edit or (double) spin box."""
        if value is None or value == "":
            return
        try:
            if isinstance(widget, QDoubleSpinBox):
                widget.setValue(float(value))
            elif isinstance(widget, QSpinBox):
                widget.setValue(int(float(value)))
            else:
                widget.setText(str(value))
        except (ValueError, TypeError):
            pass

    def _apply_query_state(self, qb, query: dict) -> None:
        # Block the query-builder combo/radio signals while restoring so that
        # setting them doesn't fire getshape()/get_backscatter_field(), which
        # would run (or crash on) a spatial recompute before the user has drawn
        # anything. Internal state and field visibility are restored explicitly.
        signal_widgets = [getattr(qb, n, None) for n in (
            "set_backscatter_field", "qb_shapeselection",
            "raw_beam", "left_beam", "right_beam", "fold_beam")]
        previous = [(w, w.blockSignals(True)) for w in signal_widgets if w is not None]
        try:
            self._set_combo(qb.set_backscatter_field, query.get("backscatter_field"))
            if query.get("backscatter_field"):
                qb.backscatter_field = qb.set_backscatter_field.currentText()

            self._set_text(qb.qb_longitude, query.get("longitude"))
            self._set_text(qb.qb_latitude, query.get("latitude"))
            self._set_text(qb.qb_ellipsemajoraxis, query.get("ellipse_major"))
            self._set_text(qb.qb_ellipseminoraxis, query.get("ellipse_minor"))
            self._set_text(qb.qb_ellipseorientation, query.get("ellipse_orientation"))
            self._set_text(qb.qb_rectangle_l1, query.get("rect_l1"))
            self._set_text(qb.qb_rectangle_l2, query.get("rect_l2"))

            self._set_combo(qb.qb_shapeselection, query.get("shape"))
            if query.get("shape"):
                qb.shape = query["shape"]
                if hasattr(qb, "_apply_shape_field_visibility"):
                    qb._apply_shape_field_visibility()

            beam = query.get("beam")
            if beam in _BEAM_BUTTONS:
                widget = getattr(qb, beam, None)
                if widget is not None:
                    widget.setChecked(True)
        finally:
            for widget, prev in previous:
                widget.blockSignals(prev)
