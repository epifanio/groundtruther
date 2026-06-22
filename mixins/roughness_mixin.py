"""Seafloor-roughness mixin: async compute, LRU cache, and a small panel dock.

Per-frame roughness is computed server-side from HabCam stereo pairs (see
:mod:`groundtruther.gt.roughness_client`).  This mixin owns the Qt/QGIS side:

* a floating "Seafloor Roughness" dock showing the current frame's metrics;
* an async :class:`~groundtruther.gt.task_runner.RoughnessTask` so the ~14 s
  cold call never blocks the UI ("computing roughness…" while it runs);
* an LRU cache keyed by ``frame_key`` so browsing back is instant;
* optional micro-DEM overlay request (delegated to the image browser).

All network/parsing logic lives in the stateless ``gt/`` package; this file
only wires it to widgets, per CLAUDE.md.
"""
import hashlib
import os
import tempfile
from collections import OrderedDict

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QAction, QCheckBox, QComboBox, QDockWidget, QDoubleSpinBox, QFormLayout,
    QFrame, QGroupBox, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QSpinBox,
    QTabWidget, QVBoxLayout, QWidget,
)
from qgis.core import (
    Qgis, QgsMessageLog, QgsProject, QgsRasterLayer, QgsSettings,
)

from groundtruther.configure import log_exception
from groundtruther.gt import roughness_client
from groundtruther.gt import task_runner

_CACHE_MAX = 64

# Shared panel palette / styles (also used by the image-metadata panel).
from groundtruther.mixins.ui_style import (  # noqa: E402
    C_OK as _C_OK, C_WARN as _C_WARN, C_MUTED as _C_MUTED,
    VALUE_CSS as _VALUE_CSS, LABEL_CSS as _LABEL_CSS,
)


class RoughnessMixin:
    """Async roughness compute + display panel for the current HabCam frame."""

    # ------------------------------------------------------------------ #
    # Init / cleanup                                                       #
    # ------------------------------------------------------------------ #

    def _init_roughness(self) -> None:
        """Build the roughness dock and toolbar toggle.  Call after the image
        browser dock exists (so ``self.w.toolBar`` is available)."""
        from qgis.utils import iface as _iface

        self._roughness_cache: "OrderedDict[str, dict]" = OrderedDict()
        self._roughness_task = None
        self._rough_widgets: dict = {}
        self._micro_dem_view = None
        self._micro_dem_last_result = None   # cached for live mitigation re-mesh
        self._last_mosaic_png_b64 = None     # last mosaic image, for the report
        self._last_mosaic_ref = None

        # Georeferencing state: per-(frame,kind) raster layer ids + a temp dir
        # for the GeoTIFFs, and the per-dataset mount calibration.
        self._georef_layers: dict = {}
        self._georef_dir = os.path.join(tempfile.gettempdir(), "gt_roughness")
        try:
            os.makedirs(self._georef_dir, exist_ok=True)
        except OSError:
            pass
        self._georef_cal = self._load_georef_calibration()

        # Tabs: metrics panel, 3-D micro-DEM relief view (same GL viewer the
        # reference-surface tab uses), and the georeferencing / calibration tab.
        tabs = QTabWidget()
        tabs.addTab(self._build_roughness_panel(), "Metrics")
        tabs.addTab(self._build_spectrum_tab(), "Spectrum")
        tabs.addTab(self._build_micro_dem_tab(), "Micro-DEM 3D")
        tabs.addTab(self._build_georef_tab(), "Georef")

        self._roughness_dock = QDockWidget("Seafloor Roughness", _iface.mainWindow())
        self._roughness_dock.setObjectName("GroundTrutherRoughnessDock")
        self._roughness_dock.setAllowedAreas(Qt.DockWidgetArea(15))       # all areas
        self._roughness_dock.setFeatures(QDockWidget.DockWidgetFeature(7))  # C|M|F
        self._roughness_dock.setWidget(tabs)
        _iface.addDockWidget(Qt.DockWidgetArea(2), self._roughness_dock)  # right
        self._roughness_dock.hide()

        from groundtruther.mixins.toolbar_icons import make_toggle_icon
        self._roughness_action = QAction(self)
        try:
            self._roughness_action.setIcon(make_toggle_icon("cubes.svg"))
        except Exception:
            self._roughness_action.setText("Roughness")
        self._roughness_action.setCheckable(True)
        self._roughness_action.setChecked(False)
        self._roughness_action.setToolTip("Show / hide the Seafloor Roughness panel")
        self._roughness_action.toggled.connect(self._toggle_roughness_dock)
        self._roughness_dock.visibilityChanged.connect(
            self._on_roughness_dock_visibility)
        # Floating / re-docking reparents the Micro-DEM 3D QOpenGLWidget into a
        # new top-level window with a fresh GL context; re-render the surface
        # afterwards so its GL items rebind to that context (the paintGL guard
        # already keeps the reparent itself from hanging).
        self._roughness_dock.topLevelChanged.connect(
            self._on_roughness_top_level_changed)
        self.w.toolBar.addAction(self._roughness_action)

        QgsMessageLog.logMessage(
            "Seafloor Roughness dock created", "GroundTruther", Qgis.Info)

    def _build_roughness_panel(self) -> QWidget:
        """Construct the metrics panel; store value labels in ``_rough_widgets``."""
        container = QWidget()
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(8, 8, 8, 8)
        vbox.setSpacing(6)

        from groundtruther.pygui.cheatsheet import CheatSheetButton
        # Header: frame id + formula cheat-sheet.
        header = QHBoxLayout()
        self._rough_frame_label = QLabel("—")
        self._rough_frame_label.setWordWrap(True)
        self._rough_frame_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        header.addWidget(self._rough_frame_label, 1)
        header.addWidget(CheatSheetButton(
            "01_seafloor_roughness.png", "Seafloor roughness — formulae"),
            0, Qt.AlignmentFlag.AlignTop)
        vbox.addLayout(header)

        # HERO — gamma2 is the load-bearing acoustic metric (robust across
        # matchers; separates substrate A/E; #1 feature in the fused classifier).
        self._rough_gamma2 = QLabel("γ₂ = —")
        self._rough_gamma2.setStyleSheet("font-size: 26pt; font-weight: bold;")
        self._rough_gamma2.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        self._rough_gamma2.setToolTip(
            "Spectral exponent — the trustworthy acoustic input and the metric "
            "this tool adds on top of backscatter.")
        vbox.addWidget(self._rough_gamma2)

        # Indicative substrate read (grey italic) + texture line.
        self._rough_substrate = QLabel("")
        self._rough_substrate.setWordWrap(True)
        self._rough_substrate.setStyleSheet(
            f"color: {_C_MUTED}; font-size: 13px; font-style: italic;")
        vbox.addWidget(self._rough_substrate)
        self._rough_texture = QLabel("")
        self._rough_texture.setWordWrap(True)
        self._rough_texture.setStyleSheet("font-size: 13px;")
        vbox.addWidget(self._rough_texture)

        # Trust-gated metrics (w2 / rms) — prominent, colour-coded per frame
        # (w2 absolute is matcher-limited; trust is per-frame, not a blanket flag).
        self._rough_w2 = QLabel("w2 = —")
        self._rough_w2.setWordWrap(True)
        self._set_trust_style(self._rough_w2, "plain")
        vbox.addWidget(self._rough_w2)
        self._rough_rms = QLabel("rms height = —")
        self._rough_rms.setWordWrap(True)
        self._set_trust_style(self._rough_rms, "plain")
        vbox.addWidget(self._rough_rms)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {_C_MUTED};")
        vbox.addWidget(sep)

        # Secondary metrics — video-panel style: grey right-aligned labels.
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(5)
        for key, label in [("rugosity", "rugosity"), ("altitude_mm", "altitude"),
                           ("quality", "quality"), ("matcher", "matcher")]:
            lab = QLabel(label)
            lab.setStyleSheet(_LABEL_CSS)
            w = QLabel("—")
            w.setStyleSheet(_VALUE_CSS)
            w.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self._rough_widgets[key] = w
            form.addRow(lab, w)
        vbox.addLayout(form)

        self._rough_status = QLabel("")
        self._rough_status.setWordWrap(True)
        self._rough_status.setStyleSheet(f"color: {_C_MUTED}; font-size: 12px;")
        vbox.addWidget(self._rough_status)

        # Controls — request only the optional outputs you want rendered.
        self._rough_surface_check = QCheckBox("3-D surface + photo (real heights)")
        self._rough_surface_check.setToolTip(
            "Request the real-height micro-DEM grid + orthophoto so the "
            "Micro-DEM 3D tab shows a photo-textured surface — slower.")
        vbox.addWidget(self._rough_surface_check)

        self._rough_overlay_check = QCheckBox("2-D height overlay on image")
        self._rough_overlay_check.setToolTip(
            "Request the per-left-pixel height raster + rectified-left preview "
            "and drape it on the displayed image — slower.")
        vbox.addWidget(self._rough_overlay_check)

        btn_row = QHBoxLayout()
        self._rough_compute_btn = QPushButton("Compute roughness")
        self._rough_compute_btn.clicked.connect(
            self.compute_roughness_for_current_frame)
        btn_row.addWidget(self._rough_compute_btn)
        self._rough_auto_check = QCheckBox("Auto")
        self._rough_auto_check.setToolTip(
            "Automatically compute roughness when you browse to a new frame.")
        btn_row.addWidget(self._rough_auto_check)
        vbox.addLayout(btn_row)

        vbox.addStretch()
        return container

    def _build_micro_dem_tab(self) -> QWidget:
        """Build the 3-D micro-DEM relief tab (reuses ``Reference3DView``)."""
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(4, 4, 4, 4)
        v.setSpacing(4)

        self._micro_dem_hint = QLabel(
            "Tick “3-D surface + photo”, then Compute, to view the micro-DEM as "
            "a photo-textured 3-D surface (real heights, mm).\n"
            "gamma2 is trustworthy; rms/w2 remain provisional.")
        self._micro_dem_hint.setWordWrap(True)
        self._micro_dem_hint.setStyleSheet("color: #888;")
        v.addWidget(self._micro_dem_hint)

        try:
            from groundtruther.pygui.reference_3d_view import Reference3DView
            view = Reference3DView(w)
            view.setMinimumHeight(280)
            view.setSizePolicy(QSizePolicy.Policy(7), QSizePolicy.Policy(7))
            v.addWidget(view, 1)
            self._micro_dem_view = view

            ctl = QHBoxLayout()
            # Same 2-point measure tool as the reference-surface panel: toggle,
            # then click two points — Reference3DView reports the 3-D / horizontal
            # / vertical distance off the true surface height.
            self._micro_dem_measure = QPushButton("Measure")
            self._micro_dem_measure.setCheckable(True)
            self._micro_dem_measure.setToolTip(
                "Toggle measure mode, then click two points on the surface "
                "(3-D / horizontal / vertical distance).")
            self._micro_dem_measure.toggled.connect(view.set_measure_mode)
            ctl.addWidget(self._micro_dem_measure)
            self._micro_dem_clear = QPushButton("Clear")
            self._micro_dem_clear.setToolTip("Clear the current measurement.")
            self._micro_dem_clear.clicked.connect(view.clear_measurement)
            ctl.addWidget(self._micro_dem_clear)
            ctl.addWidget(QLabel("VE"))
            self._micro_dem_ve = QSpinBox()
            self._micro_dem_ve.setRange(1, 30)
            self._micro_dem_ve.setValue(1)
            self._micro_dem_ve.setSuffix("×")
            self._micro_dem_ve.setToolTip(
                "Vertical exaggeration of the 3-D surface "
                "(scroll, arrows, or type).")
            self._micro_dem_ve.valueChanged.connect(
                lambda val: view.set_vertical_exaggeration(float(val)))
            ctl.addWidget(self._micro_dem_ve)
            self._micro_dem_cursor = QLabel("")     # live x / y / height under pointer
            ctl.addWidget(self._micro_dem_cursor, 1)
            v.addLayout(ctl)

            # Edge-spike mitigation — tune live against the GL view. Re-meshes the
            # cached DEM (no server call), so dragging is instant.
            cfg = (getattr(self, "settings", None) or {}).get("Roughness") or {}
            mit = QHBoxLayout()
            mit.addWidget(QLabel("Trim"))
            self._micro_dem_trim = QSpinBox()
            self._micro_dem_trim.setRange(0, 10)
            self._micro_dem_trim.setValue(int(cfg.get("dem_trim_border", 2)))
            self._micro_dem_trim.setToolTip("Drop N outer rings of the DEM grid.")
            self._micro_dem_trim.valueChanged.connect(self._rerender_micro_dem)
            mit.addWidget(self._micro_dem_trim)
            mit.addWidget(QLabel("Clip σ"))
            self._micro_dem_clip = QDoubleSpinBox()
            self._micro_dem_clip.setRange(0.0, 20.0)
            self._micro_dem_clip.setSingleStep(0.5)
            self._micro_dem_clip.setDecimals(1)
            self._micro_dem_clip.setSpecialValueText("off")     # 0.0 → masking off
            self._micro_dem_clip.setValue(float(cfg.get("dem_clip_sigma", 5.0)))
            self._micro_dem_clip.setToolTip(
                "Mask height outliers beyond N robust σ from the median (0 = off). "
                "Lower = more aggressive spike removal.")
            self._micro_dem_clip.valueChanged.connect(self._rerender_micro_dem)
            mit.addWidget(self._micro_dem_clip)
            mit.addWidget(QLabel("Erode"))
            self._micro_dem_erode = QSpinBox()
            self._micro_dem_erode.setRange(0, 5)
            self._micro_dem_erode.setValue(int(cfg.get("dem_erode", 1)))
            self._micro_dem_erode.setToolTip(
                "Peel N rings off every no-data / outlier boundary "
                "(higher = fewer edge spikes, less coverage).")
            self._micro_dem_erode.valueChanged.connect(self._rerender_micro_dem)
            mit.addWidget(self._micro_dem_erode)
            mit.addStretch()
            v.addLayout(mit)

            self._micro_dem_status = QLabel("")
            self._micro_dem_status.setWordWrap(True)
            self._micro_dem_status.setStyleSheet("color: #888;")
            view.cursor_text.connect(self._micro_dem_cursor.setText)
            view.status_text.connect(self._micro_dem_status.setText)
            v.addWidget(self._micro_dem_status)
        except Exception as exc:  # noqa: BLE001 — GL may be unavailable
            self._micro_dem_view = None
            log_exception("roughness: 3-D micro-DEM view unavailable", exc, warn=True)
            self._micro_dem_hint.setText(
                "3-D micro-DEM view unavailable (OpenGL not initialised).")
        return w

    def _update_micro_dem_3d(self, result: dict | None) -> None:
        """Render (or clear) the 3-D micro-DEM surface for *result*.

        Prefers the real-height float grid (``dem_format:"mm"``) draped with the
        co-registered orthophoto (1:1 texture); falls back to the 8-bit PNG
        preview as a relative-relief surface.
        """
        view = getattr(self, "_micro_dem_view", None)
        if view is None:
            return
        result = result or {}
        # Remember the rendered result so the mitigation sliders can re-mesh it
        # without another server round-trip.
        self._micro_dem_last_result = result if (
            result.get("micro_dem") or result.get("micro_dem_png_b64")) else None
        from groundtruther.gt import roughness_dem

        md = result.get("micro_dem")
        if isinstance(md, dict) and md.get("data_b64"):
            try:
                self._render_textured_mesh(view, result, md, roughness_dem)
                self._micro_dem_hint.hide()
                return
            except Exception as exc:  # noqa: BLE001
                log_exception("roughness: build micro-DEM mesh", exc, warn=True)

        # Fallback: 8-bit preview as a relative-relief surface.
        png_b64 = result.get("micro_dem_png_b64")
        if not png_b64:
            view.clear_surface()
            self._micro_dem_hint.show()
            return
        from groundtruther.mixins.image_browser_mixin import _decode_png_b64
        arr = _decode_png_b64(png_b64)
        if arr is None:
            view.clear_surface()
            self._micro_dem_hint.show()
            return
        try:
            x, y, Z = roughness_dem.micro_dem_grid(arr, result.get("extent_mm"))
            view.set_surface(x, y, Z, x_label="x (mm)", y_label="y (mm)",
                             z_label="rel. height")
            self._micro_dem_hint.hide()
        except Exception as exc:  # noqa: BLE001
            log_exception("roughness: build micro-DEM surface", exc, warn=True)
            view.clear_surface()
            self._micro_dem_hint.show()

    def _mesh_mitigation_params(self):
        """``(trim, clip_sigma, erode)`` from the live sliders, else config."""
        cfg = (getattr(self, "settings", None) or {}).get("Roughness") or {}
        trim = (self._micro_dem_trim.value()
                if getattr(self, "_micro_dem_trim", None) is not None
                else int(cfg.get("dem_trim_border", 2)))
        clip = (self._micro_dem_clip.value()
                if getattr(self, "_micro_dem_clip", None) is not None
                else float(cfg.get("dem_clip_sigma", 5.0)))
        erode = (self._micro_dem_erode.value()
                 if getattr(self, "_micro_dem_erode", None) is not None
                 else int(cfg.get("dem_erode", 1)))
        return int(trim), float(clip), int(erode)

    def _rerender_micro_dem(self, *_args) -> None:
        """Re-mesh the cached DEM with the current mitigation settings (no call)."""
        result = getattr(self, "_micro_dem_last_result", None)
        if result:
            self._update_micro_dem_3d(result)

    def _render_textured_mesh(self, view, result, md, roughness_dem) -> None:
        """Real-height mesh + (optional) orthophoto texture → the GL viewer.

        Edge-spike mitigation (live-tunable via the tab's Trim/Clip σ/Erode
        controls, defaulting to config): the stereo DEM is unreliable at the
        border and around no-data holes and renders as spikes with stretched
        texture. Trim the outer rings, reject MAD-based height outliers, and
        erode the noisy boundary ring; masked cells are then culled from the
        mesh (real opaque holes, no transparent faces).
        """
        from groundtruther.mixins.image_browser_mixin import _decode_png_b64
        trim, clip_sigma, erode = self._mesh_mitigation_params()
        x, y, Z, valid = roughness_dem.mesh_from_micro_dem(
            md, trim_border=trim, clip_sigma=clip_sigma, erode=erode)
        colors = None
        ortho = result.get("orthophoto")
        ortho_png = (ortho.get("png_b64") if isinstance(ortho, dict)
                     else result.get("orthophoto_png_b64"))
        if ortho_png:
            rgb = _decode_png_b64(ortho_png)
            rows, cols = int(md["shape"][0]), int(md["shape"][1])
            # Only texture when the photo is on the same grid as the DEM.
            if rgb is not None and rgb.shape[0] == rows and rgb.shape[1] == cols:
                colors = roughness_dem.colors_from_rgb(rgb, valid, trim_border=trim)
        # Pass the validity mask so masked / no-data quads are culled (opaque
        # holes) — no transparent faces, hence no camera ghosting or flicker.
        view.set_surface(x, y, Z, x_label="E (mm)", y_label="N (mm)",
                         z_label="height (mm)", colors=colors, mask=valid)

    # ------------------------------------------------------------------ #
    # Spectral roughness plot (log-log W vs K + power-law fit)             #
    # ------------------------------------------------------------------ #

    def _build_spectrum_tab(self) -> QWidget:
        """Build the log-log radial power-spectrum plot tab."""
        from groundtruther.pygui.cheatsheet import CheatSheetButton
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(4, 4, 4, 4)
        v.setSpacing(4)

        head = QHBoxLayout()
        self._spectrum_hint = QLabel(
            "Compute roughness to see the radial power spectrum W(K) and its "
            "power-law fit (slope −γ₂).")
        self._spectrum_hint.setWordWrap(True)
        self._spectrum_hint.setStyleSheet("color: #888;")
        head.addWidget(self._spectrum_hint, 1)
        head.addWidget(CheatSheetButton(
            "01_seafloor_roughness.png", "Seafloor roughness — formulae"),
            0, Qt.AlignmentFlag.AlignTop)
        v.addLayout(head)

        try:
            import pyqtgraph as pg
            self._spectrum_plot = pg.PlotWidget()
            self._spectrum_plot.setLogMode(x=True, y=True)
            self._spectrum_plot.setLabel("bottom", "K", units="rad/m")
            self._spectrum_plot.setLabel("left", "W", units="m⁴")
            self._spectrum_plot.showGrid(x=True, y=True, alpha=0.3)
            # Keep a handle so each update clears old entries instead of
            # re-adding them (avoids "item already added to this scene").
            self._spectrum_legend = self._spectrum_plot.addLegend(offset=(-10, 10))
            self._spectrum_plot.setMinimumHeight(260)
            self._spectrum_plot.setSizePolicy(
                QSizePolicy.Policy(7), QSizePolicy.Policy(7))
            v.addWidget(self._spectrum_plot, 1)
        except Exception as exc:  # noqa: BLE001 — pyqtgraph should be present
            self._spectrum_plot = None
            log_exception("roughness: spectrum plot unavailable", exc, warn=True)
            self._spectrum_hint.setText("spectrum plot unavailable (pyqtgraph).")

        self._spectrum_status = QLabel("")
        self._spectrum_status.setWordWrap(True)
        self._spectrum_status.setStyleSheet("color: #888;")
        v.addWidget(self._spectrum_status)
        return w

    def _update_spectrum(self, result: dict | None) -> None:
        """Plot the radial power spectrum + fit for *result* (or clear)."""
        plot = getattr(self, "_spectrum_plot", None)
        if plot is None:
            return
        plot.clear()
        legend = getattr(self, "_spectrum_legend", None)
        if legend is not None:
            try:
                legend.clear()       # drop old entries so they aren't re-added
            except Exception:        # noqa: BLE001 — pyqtgraph version differences
                pass
        from groundtruther.gt import roughness_spectrum as rs
        data = rs.prepare_spectrum((result or {}).get("spectrum"))
        if data is None or data["K"].size == 0:
            self._spectrum_hint.show()
            self._spectrum_status.setText("")
            return
        self._spectrum_hint.hide()

        import numpy as np
        import pyqtgraph as pg
        # Shade the fit band. LinearRegionItem is not a data item, so its
        # coordinates are the plot's (log10) space when logMode is on.
        band = data["fit_band"]
        if band:
            region = pg.LinearRegionItem(
                values=[np.log10(band[0]), np.log10(band[1])],
                movable=False, brush=(80, 160, 255, 40))
            region.setZValue(-10)
            plot.addItem(region)
        # Scatter W vs K (data items get log-transformed automatically).
        plot.plot(data["K"], data["W"], pen=None, symbol="o", symbolSize=3,
                  symbolPen=None, symbolBrush=(170, 170, 170, 160), name="W(K)")
        # Power-law fit line (straight line of slope −γ₂ on log-log).
        if data["K_fit"].size:
            plot.plot(data["K_fit"], data["W_fit"],
                      pen=pg.mkPen((255, 90, 90), width=2), name="fit (−γ₂)")

        from groundtruther.gt import roughness_interpret as ri
        parts = []
        if data["gamma2"] is not None:
            parts.append(f"γ₂={data['gamma2']:.2f}")
        w2_short, _state = ri.w2_cm4_short(result or {})
        if w2_short:                       # cm⁴ + trust flag (✓/⚠), not raw m⁴
            parts.append(w2_short)
        if data["fit_r2"] is not None:
            parts.append(f"R²={data['fit_r2']:.3f}")
        if band:
            parts.append(f"fit band {band[0]:.0f}–{band[1]:.0f} rad/m")
        footer = "   ".join(parts)
        if (result or {}).get("is_rippled"):
            footer += ("  ·  " + ri.texture_text(result)
                       + " — the radial (isotropic) spectrum is a simplification here")
        footer += "  ·  data peeling off the fit at high K = stereo noise floor"
        self._spectrum_status.setText(footer)

    # ------------------------------------------------------------------ #
    # Georeferencing — calibration, request geo, write GeoTIFFs           #
    # ------------------------------------------------------------------ #

    def _georef_defaults(self) -> dict:
        """Georeferencing defaults from config (Roughness.* keys)."""
        cfg = (getattr(self, "settings", None) or {}).get("Roughness") or {}
        return {
            "georeference": bool(cfg.get("georeference", False)),
            "epsg": int(cfg.get("epsg") or 32619),
            "heading_offset_deg": float(cfg.get("heading_offset_deg") or 0.0),
            "mirror": bool(cfg.get("mirror", False)),
        }

    def _georef_settings_prefix(self) -> str:
        """QgsSettings key prefix, scoped to the current dataset (metadata file)."""
        dataset = str(getattr(self, "metadatafile", "") or "default")
        digest = hashlib.md5(dataset.encode("utf-8")).hexdigest()[:12]
        return f"groundtruther/roughness/{digest}"

    def _load_georef_calibration(self) -> dict:
        """Per-dataset calibration from QgsSettings, falling back to config."""
        cal = self._georef_defaults()
        try:
            s = QgsSettings()
            prefix = self._georef_settings_prefix()
            cal["georeference"] = s.value(
                f"{prefix}/georeference", cal["georeference"], type=bool)
            cal["epsg"] = s.value(f"{prefix}/epsg", cal["epsg"], type=int)
            cal["heading_offset_deg"] = s.value(
                f"{prefix}/heading_offset_deg", cal["heading_offset_deg"], type=float)
            cal["mirror"] = s.value(f"{prefix}/mirror", cal["mirror"], type=bool)
        except Exception as exc:  # noqa: BLE001 — settings best-effort
            log_exception("roughness: load calibration", exc, warn=True)
        return cal

    def _save_georef_calibration(self) -> None:
        """Persist the current calibration for this dataset (QgsSettings)."""
        try:
            s = QgsSettings()
            prefix = self._georef_settings_prefix()
            for key, val in self._georef_cal.items():
                s.setValue(f"{prefix}/{key}", val)
            self._georef_status.setText("calibration saved for this dataset")
        except Exception as exc:  # noqa: BLE001
            log_exception("roughness: save calibration", exc, warn=True)
            self._georef_status.setText("could not save calibration")

    def _build_georef_tab(self) -> QWidget:
        """Build the UTM-georeferencing + mount-calibration controls."""
        cal = self._georef_cal
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)

        self._georef_enable = QCheckBox("Georeference (write GeoTIFFs, add to map)")
        self._georef_enable.setChecked(cal["georeference"])
        self._georef_enable.setToolTip(
            "Attach the frame's UTM nav to the request and add the returned "
            "micro-DEM / orthophoto to QGIS as georeferenced rasters.")
        self._georef_enable.toggled.connect(self._on_georef_cal_changed)
        v.addWidget(self._georef_enable)

        box = QGroupBox("Mount (known — correct out of the box)")
        form = QFormLayout(box)
        self._georef_epsg = QSpinBox()
        self._georef_epsg.setRange(1024, 999999)
        self._georef_epsg.setValue(cal["epsg"])
        self._georef_epsg.setToolTip("Projected CRS EPSG (32619 = UTM 19N).")
        self._georef_epsg.valueChanged.connect(self._on_georef_cal_changed)
        form.addRow("EPSG", self._georef_epsg)

        self._georef_offset = QDoubleSpinBox()
        self._georef_offset.setRange(-180.0, 180.0)
        self._georef_offset.setDecimals(2)
        self._georef_offset.setSingleStep(0.5)
        self._georef_offset.setSuffix(" °")
        self._georef_offset.setValue(cal["heading_offset_deg"])
        self._georef_offset.setToolTip("Residual heading fine-tune (default 0).")
        self._georef_offset.valueChanged.connect(self._on_georef_cal_changed)
        form.addRow("Heading offset", self._georef_offset)

        self._georef_mirror = QCheckBox("Mirror")
        self._georef_mirror.setChecked(cal["mirror"])
        self._georef_mirror.setToolTip(
            "Escape hatch — enable only if a mosaic comes out "
            "port/starboard-flipped.")
        self._georef_mirror.toggled.connect(self._on_georef_cal_changed)
        form.addRow(self._georef_mirror)
        v.addWidget(box)

        mbox = QGroupBox("Mosaic (±window contiguous frames)")
        mform = QFormLayout(mbox)
        self._mosaic_window = QSpinBox()
        self._mosaic_window.setRange(1, 50)
        self._mosaic_window.setValue(5)
        self._mosaic_window.setToolTip(
            "Contiguous frames on EACH side of the current frame; the service "
            "pulls the nav and skips gaps.")
        mform.addRow("Window ±", self._mosaic_window)
        self._mosaic_gsd = QDoubleSpinBox()
        self._mosaic_gsd.setRange(0.0005, 0.05)
        self._mosaic_gsd.setDecimals(4)
        self._mosaic_gsd.setSingleStep(0.001)
        self._mosaic_gsd.setValue(0.003)
        self._mosaic_gsd.setSuffix(" m")
        self._mosaic_gsd.setToolTip("Output ground sample distance (m/pixel).")
        mform.addRow("Out GSD", self._mosaic_gsd)
        self._mosaic_ortho = QCheckBox("Relief-corrected (ortho)")
        self._mosaic_ortho.setToolTip(
            "flat = altitude/f scale (fast); ortho = relief-corrected using the "
            "per-frame micro-DEM.")
        mform.addRow(self._mosaic_ortho)
        self._mosaic_interp = QComboBox()
        self._mosaic_interp.addItems(["auto", "linear", "area", "lanczos", "cubic"])
        self._mosaic_interp.setToolTip(
            "Resampling. auto = area for coarse GSD (>1 mm), lanczos for fine; "
            "linear = fast browse; area = anti-aliased coarse; lanczos/cubic = "
            "sharp near-native (pair with a fine GSD).")
        mform.addRow("Interp", self._mosaic_interp)
        self._mosaic_maxside = QSpinBox()
        self._mosaic_maxside.setRange(512, 16384)
        self._mosaic_maxside.setSingleStep(1024)
        self._mosaic_maxside.setValue(4096)
        self._mosaic_maxside.setToolTip(
            "Output side cap (px); the service auto-coarsens above it. Raise to "
            "8192 for big fine strips.")
        mform.addRow("Max side", self._mosaic_maxside)
        self._mosaic_alpha = QCheckBox("Transparent border (RGBA)")
        self._mosaic_alpha.setToolTip(
            "4-band RGBA — QGIS shows the uncovered border transparent "
            "automatically (robust). Off = 3-band + nodata fill.")
        mform.addRow(self._mosaic_alpha)

        preset_row = QHBoxLayout()
        browse_btn = QPushButton("Browse preset")
        browse_btn.setToolTip("3 mm, anti-aliased — fast overview.")
        browse_btn.clicked.connect(lambda: self._apply_mosaic_preset("browse"))
        preset_row.addWidget(browse_btn)
        pub_btn = QPushButton("Publication preset")
        pub_btn.setToolTip("ortho, 0.8 mm, lanczos, 8192 px, RGBA — near-native export.")
        pub_btn.clicked.connect(lambda: self._apply_mosaic_preset("publication"))
        preset_row.addWidget(pub_btn)
        mform.addRow(preset_row)

        self._mosaic_btn = QPushButton("Build mosaic")
        self._mosaic_btn.setToolTip(
            "Composite the contiguous frames around the current one into a "
            "georeferenced UTM mosaic (EPSG above) and add it to QGIS.")
        self._mosaic_btn.clicked.connect(self.build_mosaic_for_current_frame)
        mform.addRow(self._mosaic_btn)
        v.addWidget(mbox)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save calibration")
        save_btn.setToolTip("Persist these values for this dataset.")
        save_btn.clicked.connect(self._save_georef_calibration)
        btn_row.addWidget(save_btn)
        clear_btn = QPushButton("Clear georef layers")
        clear_btn.clicked.connect(self._clear_georef_layers)
        btn_row.addWidget(clear_btn)
        v.addLayout(btn_row)

        self._georef_status = QLabel(
            "Mount is known — position and rotation are correct from the nav. "
            "Only set Mirror if a mosaic comes out port/starboard-flipped.")
        self._georef_status.setWordWrap(True)
        self._georef_status.setStyleSheet("color: #888;")
        v.addWidget(self._georef_status)

        v.addStretch()
        return w

    def _on_georef_cal_changed(self, *_args) -> None:
        """Pull the calibration from the widgets and re-render the current frame."""
        self._georef_cal = {
            "georeference": self._georef_enable.isChecked(),
            "epsg": int(self._georef_epsg.value()),
            "heading_offset_deg": float(self._georef_offset.value()),
            "mirror": self._georef_mirror.isChecked(),
        }
        # Re-request the current frame so the tweak is visible immediately.
        if self._georef_cal["georeference"] and self._current_frame_key():
            self.compute_roughness_for_current_frame()

    def build_mosaic_for_current_frame(self) -> None:
        """Mode-A mosaic: composite ±window contiguous frames around this one.

        The service pulls the nav for the window itself and skips gaps; we write
        the returned ``mosaic_png_b64 + geotransform + epsg`` to a GeoTIFF and add
        it to QGIS, reporting ``frames_skipped``.
        """
        ref = self._current_frame_key()
        if ref is None:
            self._georef_status.setText("no frame loaded")
            return
        cfg = self._roughness_config()
        if not cfg["direct_url"] and not (cfg["endpoint"] and cfg["api_key"]):
            self._georef_status.setText("roughness service not configured")
            return
        # The mosaic is a sibling route; derive its direct URL from the roughness
        # one when the direct fast-path is in use.
        direct = cfg["direct_url"]
        mosaic_direct = (direct.rsplit("/", 1)[0] + "/mosaic") if direct else None
        self._mosaic_btn.setEnabled(False)
        self._mosaic_btn.setText("building…")
        self._georef_status.setText(
            f"building mosaic (±{int(self._mosaic_window.value())}) around {ref}…")
        gsd = float(self._mosaic_gsd.value())
        interp = self._mosaic_interp.currentText()
        if interp == "auto":     # smart: anti-alias coarse, sharpen near-native
            interp = "area" if gsd > 0.001 else "lanczos"
        self._mosaic_task = task_runner.run_mosaic_task(
            ref, window=int(self._mosaic_window.value()),
            mode=("ortho" if self._mosaic_ortho.isChecked() else "flat"),
            out_gsd_m=gsd, epsg=int(self._georef_epsg.value()),
            max_side=int(self._mosaic_maxside.value()), interp=interp,
            alpha=self._mosaic_alpha.isChecked(),
            endpoint=cfg["endpoint"], api_key=cfg["api_key"],
            direct_url=mosaic_direct,
            on_success=self._on_mosaic_success, on_error=self._on_mosaic_error,
            description=f"Mosaic {ref}")

    def _reset_mosaic_button(self) -> None:
        btn = getattr(self, "_mosaic_btn", None)
        if btn is not None:
            btn.setEnabled(True)
            btn.setText("Build mosaic")

    def _on_mosaic_success(self, reference_key: str, result: dict) -> None:
        self._mosaic_task = None
        self._reset_mosaic_button()
        from groundtruther.mixins.image_browser_mixin import _decode_png_b64
        png = result.get("mosaic_png_b64")
        gt = result.get("geotransform")
        epsg = result.get("epsg") or int(self._georef_epsg.value())
        if not png or not gt or len(gt) != 6:
            self._georef_status.setText(
                "mosaic: service returned no raster / geotransform")
            return
        arr = _decode_png_b64(png)
        if arr is None:
            self._georef_status.setText("mosaic: could not decode image")
            return
        geo = {"geotransform": [float(v) for v in gt], "epsg": int(epsg)}
        # 4-band RGBA (alpha:true) → QGIS shows transparency automatically; else
        # 3-band + nodata fill so the uncovered border still renders transparent.
        bands = int(result.get("bands") or (arr.shape[2] if arr.ndim == 3 else 1))
        if bands >= 4 and arr.ndim == 3 and arr.shape[2] >= 4:
            data, nodata = arr[..., :4], None
        else:
            data = arr[..., :3] if arr.ndim == 3 else arr
            nd = result.get("nodata", 0)
            nodata = float(nd) if nd is not None else None
        ok = self._add_geotiff_layer(reference_key, "mosaic", data, geo, nodata=nodata)
        if ok:                              # remember it for the report builder
            self._last_mosaic_png_b64 = png
            self._last_mosaic_ref = reference_key
        skipped = result.get("frames_skipped") or []
        n_sk = len(skipped) if isinstance(skipped, (list, tuple)) else int(skipped or 0)
        n = result.get("n_frames", "?")
        self._georef_status.setText(
            f"mosaic added: {n} frames, {n_sk} skipped, {bands}-band (EPSG:{geo['epsg']})"
            if ok else "mosaic: failed to write raster")

    def _on_mosaic_error(self, reference_key: str, detail: str) -> None:
        self._mosaic_task = None
        self._reset_mosaic_button()
        self._georef_status.setText(f"mosaic error: {detail}")

    # ------------------------------------------------------------------ #
    # Report-builder export — products for the KMZ / HTML report           #
    # ------------------------------------------------------------------ #

    def report_roughness_html(self):
        """HTML table of the current frame's roughness metrics, or ``None``.

        Consumed by the report builder's "Roughness" product button.
        """
        frame_key = self._current_frame_key()
        result = self._roughness_cache_get(frame_key) if frame_key else None
        if not result:
            return None
        rows = [("frame", frame_key),
                ("quality", result.get("quality")),
                ("matcher", result.get("matcher"))]
        if roughness_client.is_ok(result):
            rows += [
                ("gamma2 (spectral exp.)", _fmt(result.get("gamma2"))),
                ("w2 [provisional]", _fmt(result.get("w2"))),
                ("rms height mm [provisional]", _fmt(result.get("rms_height_mm"))),
                ("rugosity", _fmt(result.get("rugosity"))),
                ("altitude mm", _fmt(result.get("altitude_mm"))),
            ]
        body = "".join(
            f"<tr><td><b>{k}</b></td><td>{'' if v is None else v}</td></tr>"
            for k, v in rows)
        return ('<table border="1" cellpadding="3" cellspacing="0">'
                f"{body}</table>")

    def export_micro_dem_png(self, path) -> bool:
        """Save a snapshot of the Micro-DEM 3D view to *path*. Returns success."""
        view = getattr(self, "_micro_dem_view", None)
        if view is None or not view.has_surface():
            return False
        try:
            return bool(view.grabFramebuffer().save(str(path)))
        except Exception as exc:  # noqa: BLE001
            log_exception("export micro-DEM snapshot", exc, warn=True)
            return False

    def export_spectrum_png(self, path) -> bool:
        """Save the spectral-roughness plot to *path*. Returns success."""
        plot = getattr(self, "_spectrum_plot", None)
        if plot is None:
            return False
        hint = getattr(self, "_spectrum_hint", None)
        if hint is not None and hint.isVisible():
            return False                    # no spectrum plotted yet
        try:
            return bool(plot.grab().save(str(path)))
        except Exception as exc:  # noqa: BLE001
            log_exception("export spectrum plot", exc, warn=True)
            return False

    def export_mosaic_png(self, path) -> bool:
        """Write the last-built mosaic image to *path*. Returns success."""
        b64 = getattr(self, "_last_mosaic_png_b64", None)
        if not b64:
            return False
        try:
            import base64
            with open(str(path), "wb") as fh:
                fh.write(base64.b64decode(b64))
            return True
        except Exception as exc:  # noqa: BLE001
            log_exception("export mosaic image", exc, warn=True)
            return False

    def _apply_mosaic_preset(self, kind: str) -> None:
        """Set the mosaic controls to a named preset (Browse / Publication)."""
        if kind == "publication":
            self._mosaic_ortho.setChecked(True)
            self._mosaic_gsd.setValue(0.0008)
            self._mosaic_interp.setCurrentText("lanczos")
            self._mosaic_maxside.setValue(8192)
            self._mosaic_alpha.setChecked(True)
        else:  # browse
            self._mosaic_ortho.setChecked(False)
            self._mosaic_gsd.setValue(0.003)
            self._mosaic_interp.setCurrentText("area")
            self._mosaic_maxside.setValue(4096)
            self._mosaic_alpha.setChecked(False)

    def _geo_for_current(self) -> dict | None:
        """Build the request ``geo`` from the current frame's nav, if enabled."""
        cal = self._georef_cal
        if not cal.get("georeference") or getattr(self, "imageMetadata", None) is None:
            return None
        try:
            record = self.imageMetadata.iloc[self.imageindex]
        except (IndexError, AttributeError):
            return None
        from groundtruther.gt import roughness_geo
        return roughness_geo.geo_from_record(
            record, epsg=cal["epsg"],
            heading_offset_deg=cal["heading_offset_deg"], mirror=cal["mirror"])

    def _maybe_add_georef_layers(self, frame_key: str, result: dict) -> None:
        """Write the georeferenced micro-DEM / orthophoto and add them to QGIS."""
        if not self._georef_cal.get("georeference"):
            return
        import numpy as np
        from groundtruther.gt import roughness_geo, roughness_dem
        from groundtruther.mixins.image_browser_mixin import _decode_png_b64

        geo = roughness_geo.extract_geo(result)
        if geo is None:
            self._georef_status.setText(
                "service returned no geotransform yet — pending server "
                "georeferencing support")
            return

        added = []
        # Orthophoto → RGB GeoTIFF (co-registered to the DEM grid).
        ortho = result.get("orthophoto")
        ortho_png = (ortho.get("png_b64") if isinstance(ortho, dict)
                     else result.get("orthophoto_png_b64")
                     or result.get("ortho_png_b64"))
        if ortho_png:
            rgb = _decode_png_b64(ortho_png)
            if rgb is not None and self._add_geotiff_layer(
                    frame_key, "ortho", rgb[..., :3], geo):
                added.append("orthophoto")

        # Micro-DEM → real-height float GeoTIFF (NaN = no-data); else PNG preview.
        md = result.get("micro_dem")
        if isinstance(md, dict) and md.get("data_b64"):
            try:
                heights, *_ = roughness_dem.decode_float_grid(md)
                if self._add_geotiff_layer(frame_key, "dem", heights, geo,
                                           nodata=float("nan")):
                    added.append("micro-DEM")
            except Exception as exc:  # noqa: BLE001
                log_exception("roughness: decode micro_dem grid", exc, warn=True)
        elif result.get("micro_dem_png_b64"):
            arr = _decode_png_b64(result["micro_dem_png_b64"])
            if arr is not None and self._add_geotiff_layer(
                    frame_key, "dem", arr[..., :3].mean(axis=2).astype("float32"),
                    geo):
                added.append("micro-DEM(preview)")

        self._georef_status.setText(
            f"added {', '.join(added)} for {frame_key} (EPSG:{geo['epsg']})"
            if added else "no rasters returned for this frame")

    def _add_geotiff_layer(self, frame_key, kind, data, geo, *, nodata=None) -> bool:
        """Write *data* as a GeoTIFF with *geo* and add it as a QGIS raster."""
        from groundtruther.gt import roughness_geo
        safe = "".join(c if c.isalnum() else "_" for c in str(frame_key))
        path = os.path.join(self._georef_dir, f"{kind}_{safe}.tif")
        try:
            roughness_geo.write_geotiff(
                data, geo["geotransform"], geo["epsg"], path, nodata=nodata)
        except Exception as exc:  # noqa: BLE001
            log_exception(f"roughness: write {kind} GeoTIFF", exc, warn=True)
            return False
        return self._replace_raster_layer(frame_key, kind, path)

    def _replace_raster_layer(self, frame_key, kind, path) -> bool:
        """Add (or replace) the QGIS raster for this (frame, kind)."""
        project = QgsProject.instance()
        layer_key = (str(frame_key), kind)
        old_id = self._georef_layers.pop(layer_key, None)
        if old_id:
            try:
                project.removeMapLayer(old_id)
            except Exception:  # noqa: BLE001
                pass
        layer = QgsRasterLayer(path, f"roughness_{kind}_{frame_key}")
        if not layer.isValid():
            QgsMessageLog.logMessage(
                f"roughness: invalid raster {path}", "GroundTruther", Qgis.Warning)
            return False
        project.addMapLayer(layer)
        self._georef_layers[layer_key] = layer.id()
        return True

    def _clear_georef_layers(self) -> None:
        """Remove all roughness georef layers from the project."""
        project = QgsProject.instance()
        for layer_id in list(self._georef_layers.values()):
            try:
                project.removeMapLayer(layer_id)
            except Exception:  # noqa: BLE001
                pass
        self._georef_layers = {}
        if getattr(self, "_georef_status", None) is not None:
            self._georef_status.setText("georef layers cleared")

    def _cleanup_roughness(self) -> None:
        try:
            self._clear_georef_layers()
        except Exception:
            pass
        # Close the pyqtgraph spectrum plot and the GL view FIRST, while their
        # C++ scene / GL context are still alive.  pyqtgraph keeps process-wide
        # registries (ViewBox.AllViews, GL items); closing them now deregisters
        # them so Python GC can't later destroy a wrapper whose C++ object is
        # already gone — the same access-violation-on-reload guard the image
        # dock uses for its ImageView.
        for attr in ("_spectrum_plot", "_micro_dem_view"):
            widget = getattr(self, attr, None)
            if widget is None:
                continue
            try:
                widget.close()
            except Exception:
                pass
            setattr(self, attr, None)
        dock = getattr(self, "_roughness_dock", None)
        if dock is None:
            return
        self._roughness_dock = None
        try:
            dock.hide()
            dock.setWidget(None)
            from qgis.utils import iface as _iface
            _iface.removeDockWidget(dock)
            dock.deleteLater()
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # Dock toggle plumbing (mirrors the other panel docks)                 #
    # ------------------------------------------------------------------ #

    def _toggle_roughness_dock(self, checked: bool) -> None:
        dock = getattr(self, "_roughness_dock", None)
        if dock is None:
            return
        if checked:
            dock.show()
            dock.raise_()
            self._on_frame_changed_roughness()   # refresh for current frame
        else:
            dock.hide()

    def _on_roughness_dock_visibility(self, visible: bool) -> None:
        action = getattr(self, "_roughness_action", None)
        if action is None:
            return
        action.blockSignals(True)
        action.setChecked(visible)
        action.blockSignals(False)

    def _on_roughness_top_level_changed(self, _floating: bool) -> None:
        """Re-render the 3-D surface after a float / re-dock reparent.

        The reparent gives the ``QOpenGLWidget`` a new GL context; re-rendering
        the cached surface rebinds its GL items to it (and refreshes after any
        transient blank during the move).  Deferred to the next event-loop turn
        so Qt has finished the reparent, and skipped when nothing is rendered.
        """
        if getattr(self, "_micro_dem_last_result", None) is None:
            return
        from qgis.PyQt.QtCore import QTimer
        QTimer.singleShot(
            0, lambda: self._update_micro_dem_3d(self._micro_dem_last_result))

    # ------------------------------------------------------------------ #
    # Frame integration                                                    #
    # ------------------------------------------------------------------ #

    def _current_frame_key(self):
        """Return the current frame's image id (``Imagename``) or ``None``."""
        if getattr(self, "imageMetadata", None) is None:
            return None
        try:
            return str(self.imageMetadata["Imagename"].iloc[self.imageindex])
        except (KeyError, IndexError):
            return None

    def _on_frame_changed_roughness(self) -> None:
        """React to a frame change: show cached roughness or offer to compute.

        Called (guarded) from the image browser's ``add_image``.  Cheap when the
        dock is hidden — does nothing.
        """
        dock = getattr(self, "_roughness_dock", None)
        if dock is None or not dock.isVisible():
            return
        frame_key = self._current_frame_key()
        self._rough_frame_label.setText(f"Frame: {frame_key or '—'}")
        if frame_key is None:
            self._clear_roughness_panel()
            return

        cached = self._roughness_cache_get(frame_key)
        if cached is not None:
            self._show_roughness_result(frame_key, cached)
        else:
            self._clear_roughness_panel()
            if self._rough_auto_check.isChecked():
                self.compute_roughness_for_current_frame()
            else:
                self._rough_status.setText("press “Compute roughness”")

    # ------------------------------------------------------------------ #
    # LRU cache                                                             #
    # ------------------------------------------------------------------ #

    def _roughness_cache_get(self, frame_key: str):
        cache = getattr(self, "_roughness_cache", None)
        if not cache or frame_key not in cache:
            return None
        cache.move_to_end(frame_key)   # mark most-recently used
        return cache[frame_key]

    def _roughness_cache_put(self, frame_key: str, result: dict) -> None:
        cache = self._roughness_cache
        cache[frame_key] = result
        cache.move_to_end(frame_key)
        while len(cache) > _CACHE_MAX:
            cache.popitem(last=False)

    # ------------------------------------------------------------------ #
    # Compute                                                              #
    # ------------------------------------------------------------------ #

    def _roughness_config(self) -> dict:
        """Resolve endpoint/api_key/route/direct_url/knobs from config + creds."""
        cfg = (getattr(self, "settings", None) or {}).get("Roughness") or {}
        # Reuse the GRASS credentials (same FastGIS X-API-Key + base URL).
        try:
            endpoint, api_key, _env = self.grass_dialog.connection()
        except Exception:
            endpoint, api_key = None, None
        base_url = (cfg.get("base_url") or "").strip() or endpoint
        route = (cfg.get("route") or "").strip() or roughness_client.DEFAULT_ROUTE
        direct_url = (cfg.get("direct_url") or "").strip() or None
        return {
            "endpoint": base_url,
            "api_key": api_key,
            "route": route,
            "direct_url": direct_url,
            "res_mm": cfg.get("res_mm"),
            "n_water": cfg.get("n_water"),
            "dem_max_side": cfg.get("dem_max_side"),
        }

    def compute_roughness_for_current_frame(self) -> None:
        """Kick off (or reuse a cached) roughness computation for this frame."""
        frame_key = self._current_frame_key()
        if frame_key is None:
            self._rough_status.setText("no frame loaded")
            return

        geo = self._geo_for_current()
        cfg = self._roughness_config()
        # Decide which optional outputs to request — "only what we render".
        # Georeferencing needs the world-grid DEM + orthophoto, so it implies the
        # surface outputs.
        want_surface = self._rough_surface_check.isChecked() or geo is not None
        want_overlay = self._rough_overlay_check.isChecked()
        # The spectrum is a small array payload and a core diagnostic shown
        # alongside the metrics panel — always request it.
        outputs: dict = {"include_spectrum": True}
        if want_surface:
            outputs["dem_format"] = "mm"
            outputs["include_orthophoto"] = True
            if cfg.get("dem_max_side"):
                outputs["dem_max_side"] = cfg["dem_max_side"]
        if want_overlay:
            outputs["include_left_height"] = True
            outputs["include_left_preview"] = True

        cached = self._roughness_cache_get(frame_key)
        # A cache hit short-circuits only when it already carries what we need.
        # When georeferencing (geo set) we always recompute so the geotransform
        # reflects the latest mount settings.
        if geo is None and self._cache_satisfies(cached, want_surface, want_overlay):
            self._show_roughness_result(frame_key, cached)
            return

        if not cfg["direct_url"] and not (cfg["endpoint"] and cfg["api_key"]):
            self._rough_status.setText(
                "roughness service not configured (set Roughness.base_url / "
                "direct_url or the GRASS API key)")
            return

        self._set_roughness_busy(True)
        self._rough_status.setText("computing roughness…")
        # _roughness_config carries transport/knobs; strip the dem_max_side
        # default we surfaced above (it's already folded into outputs).
        client_cfg = {k: v for k, v in cfg.items() if k != "dem_max_side"}
        self._roughness_task = task_runner.run_roughness_task(
            frame_key, geo=geo,
            on_success=self._on_roughness_success,
            on_error=self._on_roughness_error,
            description=f"Roughness {frame_key}", **client_cfg, **outputs)

    @staticmethod
    def _cache_satisfies(cached, want_surface, want_overlay) -> bool:
        """True when a cached result already has the requested optional outputs."""
        if cached is None:
            return False
        # The spectrum is always requested; a cache entry without it predates the
        # feature, so recompute to fill the Spectrum tab.
        if not isinstance(cached.get("spectrum"), dict):
            return False
        if want_surface and not (
                isinstance(cached.get("micro_dem"), dict)
                or cached.get("micro_dem_png_b64")):
            return False
        if want_overlay and not isinstance(cached.get("height_left"), dict):
            return False
        return True

    def _on_roughness_success(self, frame_key: str, result: dict) -> None:
        self._roughness_task = None
        self._set_roughness_busy(False)
        self._roughness_cache_put(frame_key, result)
        if frame_key == self._current_frame_key():
            self._show_roughness_result(frame_key, result)
        self._maybe_add_georef_layers(frame_key, result)

    def _on_roughness_error(self, frame_key: str, detail: str) -> None:
        self._roughness_task = None
        self._set_roughness_busy(False)
        QgsMessageLog.logMessage(
            f"roughness {frame_key}: {detail}", "GroundTruther", Qgis.Warning)
        if frame_key == self._current_frame_key():
            self._rough_status.setText(f"error: {detail}")

    def _set_roughness_busy(self, busy: bool) -> None:
        btn = getattr(self, "_rough_compute_btn", None)
        if btn is not None:
            btn.setEnabled(not busy)
            btn.setText("computing…" if busy else "Compute roughness")

    # ------------------------------------------------------------------ #
    # Display                                                              #
    # ------------------------------------------------------------------ #

    def _clear_roughness_panel(self) -> None:
        for w in getattr(self, "_rough_widgets", {}).values():
            w.setText("—")
            w.setStyleSheet(_VALUE_CSS)
        self._reset_metric_labels()
        self._clear_micro_dem_overlay()
        self._update_micro_dem_3d(None)
        self._update_spectrum(None)

    def _show_roughness_result(self, frame_key: str, result: dict) -> None:
        """Fill the panel from a roughness payload and (maybe) overlay the DEM."""
        from groundtruther.gt import roughness_interpret as ri
        widgets = self._rough_widgets
        widgets["quality"].setText(str(result.get("quality", "—")))
        widgets["matcher"].setText(str(result.get("matcher") or "—"))

        if roughness_client.is_ok(result):
            self._rough_status.setText("")
            gamma2 = result.get("gamma2")
            self._rough_gamma2.setText(f"γ₂ = {_fmt(gamma2)}")
            hint = ri.substrate_hint(gamma2, result.get("rugosity"))
            self._rough_substrate.setText(
                f"{hint}   (indicative)" if hint else "")
            self._rough_texture.setText(ri.texture_text(result))

            w2_text, w2_state = ri.w2_display(result)
            self._rough_w2.setText(w2_text)
            self._set_trust_style(self._rough_w2, w2_state)
            rms_text, rms_state = ri.rms_display(result)
            self._rough_rms.setText(rms_text)
            self._set_trust_style(self._rough_rms, rms_state)

            widgets["rugosity"].setText(_fmt(result.get("rugosity")))
            widgets["altitude_mm"].setText(self._altitude_text(result))
        else:
            # quality != ok → roughness fields are null; say so plainly.
            self._rough_status.setText(roughness_client.quality_message(result))
            self._reset_metric_labels()

        # Spectral plot + 3-D photo-textured surface + 2-D height overlay.
        self._update_spectrum(result)
        self._update_micro_dem_3d(result)
        self._update_image_height_overlay(result)

    @staticmethod
    def _set_trust_style(label, state: str) -> None:
        """Colour a trust-gated label (green/red); neutral inherits the theme."""
        css = "font-size: 14px;"
        color = {"ok": _C_OK, "warn": _C_WARN}.get(state)
        if color:
            css += f" color: {color};"
        label.setStyleSheet(css)

    def _reset_metric_labels(self) -> None:
        """Blank the hero / trust-gated metric labels."""
        self._rough_gamma2.setText("γ₂ = —")
        self._rough_substrate.setText("")
        self._rough_texture.setText("")
        self._rough_w2.setText("w2 = —")
        self._set_trust_style(self._rough_w2, "plain")
        self._rough_rms.setText("rms height = —")
        self._set_trust_style(self._rough_rms, "plain")
        for key in ("rugosity", "altitude_mm"):
            w = self._rough_widgets.get(key)
            if w is not None:
                w.setText("—")
                w.setStyleSheet(_VALUE_CSS)

    def _update_image_height_overlay(self, result: dict) -> None:
        """Drape the per-left-pixel height raster on the displayed image.

        Uses ``height_left`` (aligned 1:1 to the rectified LEFT image) — the
        turnkey 2-D overlay — registered identity onto the displayed JPG when it
        *is* the rectified left (full_shape matches).  World-mm products are for
        3-D/UTM; ``height_left`` is the one meant for the JPEG overlay.
        """
        hl = result.get("height_left")
        if not (isinstance(hl, dict) and hl.get("data_b64")):
            self._clear_micro_dem_overlay()
            return
        try:
            import numpy as np
            from groundtruther.gt import roughness_dem
            heights, *_ = roughness_dem.decode_float_grid(hl)
            ds = int(hl.get("downsample", 1)) or 1
            if ds > 1:                                   # upscale to full-res pixels
                heights = np.repeat(np.repeat(heights, ds, 0), ds, 1)
            valid = ~np.isnan(heights)
            if valid.any():
                lo, hi = float(np.nanmin(heights)), float(np.nanmax(heights))
                norm = (heights - lo) / (hi - lo) if hi > lo else np.zeros_like(heights)
            else:
                norm = np.zeros_like(heights)
            rgba = np.zeros((*heights.shape, 4), dtype=np.uint8)
            gray = (np.nan_to_num(norm) * 255).astype(np.uint8)
            rgba[..., 0] = gray
            rgba[..., 1] = gray
            rgba[..., 2] = gray
            rgba[..., 3] = np.where(valid, 160, 0).astype(np.uint8)
            self._show_image_overlay_rgba(rgba)
        except Exception as exc:  # noqa: BLE001
            log_exception("roughness: height_left overlay", exc, warn=True)
            self._clear_micro_dem_overlay()

    def _altitude_text(self, result: dict) -> str:
        """Service altitude + QA delta vs the metadata Altimeter (green if close).

        Side-effect: colours the altitude label green when |Δ| is within
        tolerance (a good cross-check), else neutral.
        """
        from groundtruther.gt import roughness_interpret as ri
        alt = result.get("altitude_mm")
        text = f"{_fmt(alt)} mm" if alt is not None else "—"
        try:
            altimeter_m = float(
                self.imageMetadata["Altimeter"].iloc[self.imageindex])
        except (KeyError, IndexError, TypeError, ValueError):
            altimeter_m = None
        delta, in_tol = ri.altitude_delta_mm(alt, altimeter_m)
        if delta is not None:
            text += f"   (Δ vs Altimeter {delta:+.0f} mm)"
        w = self._rough_widgets.get("altitude_mm")
        if w is not None:
            w.setStyleSheet(_VALUE_CSS + (f" color: {_C_OK};" if in_tol else ""))
        return text


def _fmt(value, places: int = 4) -> str:
    """Format a numeric metric compactly; ``—`` for null."""
    if value is None:
        return "—"
    try:
        f = float(value)
    except (TypeError, ValueError):
        return str(value)
    if f != 0 and (abs(f) < 1e-3 or abs(f) >= 1e5):
        return f"{f:.3e}"
    return f"{f:.{places}g}"
