"""Enriched 3-D view for the reference-surface (GeoTIFF) tab.

A ``pyqtgraph.opengl.GLViewWidget`` subclass that adds, on top of the surface:

* coloured **XYZ axes** + a sized floor **grid**;
* **3-D text labels** — axis hints and real-world tick values at the corners;
* adjustable **vertical exaggeration** (:meth:`set_vertical_exaggeration`);
* a live **cursor read-out** (Easting / Northing / Elevation under the pointer),
  **snapped to the nearest grid sample** for an exact value;
* **picking** (click drops a marker) and a 2-point **measure** tool
  (3-D distance + horizontal + vertical), toggled via :meth:`set_measure_mode`.

Picking uses depth-buffer unprojection (pyqtgraph has no built-in 3-D hit test)
to find the (x, y) under the pointer, then snaps to the nearest grid cell and
reads the true elevation there — so the result is exact and unaffected by depth
precision or the current exaggeration. The maths lives in :mod:`gt.glmath` and
is unit-tested; every GL read is guarded so a failure degrades to "no read-out".
"""
from __future__ import annotations

import numpy as np

import pyqtgraph.opengl as gl
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QColor


def _qmat_to_np(qmat):
    """QMatrix4x4 (column-major) -> numpy 4x4 in math order (M @ v)."""
    return np.array(qmat.data(), dtype=float).reshape(4, 4).T


class Reference3DView(gl.GLViewWidget):
    """GL surface viewer with axes, labels, exaggeration, picking & measuring."""

    cursor_text = pyqtSignal(str)    # live "E … N … Z …" under the pointer
    status_text = pyqtSignal(str)    # extent / ranges, and measure results

    def __init__(self, parent=None):
        super().__init__(parent, rotationMethod="euler")
        self.setCameraPosition(distance=150)
        self.setMouseTracking(True)
        self._x = self._y = self._Z = None
        self._labels_text = ("Easting (m)", "Northing (m)", "Elevation (m)")
        self._off = None             # (x0, y0, z0): real <-> centred world
        self._ve = 1.0               # vertical exaggeration
        self._surface = None
        self._world_pts = None       # (N, 3) grid vertices, for projection-picking
        self._measure_mode = False
        self._measure_pts = []       # real (E, N, Z) picks (≤ 2)
        self._profile_pts = None     # draped polyline (real coords)
        self._surface_len = self._plan_len = 0.0
        self._measure_items = []     # all GL items for the current measurement
        self._press_pos = None       # for click-vs-drag disambiguation

    def has_surface(self):
        """True when a reference surface is currently displayed."""
        return self._surface is not None and self._x is not None

    def clear_surface(self):
        """Remove the surface and all overlays (used when no reference applies)."""
        self.clear_measurement()
        self.clear()
        self._surface = None
        self._x = self._y = self._Z = None
        self._world_pts = None
        self._off = None

    # ------------------------------------------------------------------ #
    # Coordinate helpers                                                  #
    # ------------------------------------------------------------------ #
    def _real_to_world(self, real):
        """Real (E, N, Z) metres -> centred, exaggerated GL world coords."""
        x0, y0, z0 = self._off
        return (real[0] - x0, real[1] - y0, (real[2] - z0) * self._ve)

    # ------------------------------------------------------------------ #
    # Surface setup                                                       #
    # ------------------------------------------------------------------ #
    def set_surface(self, x, y, Z,
                    x_label="Easting (m)", y_label="Northing (m)",
                    z_label="Elevation (m)"):
        """Render *x, y, Z* (real-world metres) with axes, grid and labels."""
        self._x = np.asarray(x, float)
        self._y = np.asarray(y, float)
        self._Z = np.asarray(Z, float)
        self._labels_text = (x_label, y_label, z_label)
        x0, y0 = float(self._x.mean()), float(self._y.mean())
        z0 = float(np.nanmean(Z)) - 10.0          # matches the surface lift
        self._off = (x0, y0, z0)
        self._measure_pts = []
        self._profile_pts = None
        self._measure_items = []
        self._rebuild()
        span = max(self._x.max() - self._x.min(),
                   self._y.max() - self._y.min(), 1.0)
        self.setCameraPosition(distance=span * 2.0)
        self.status_text.emit(self._extent_summary())

    def _rebuild(self):
        """(Re)build all GL items for the current vertical exaggeration."""
        if self._x is None:
            return
        self.clear()
        x, y, Z = self._x, self._y, self._Z
        x0, y0, z0 = self._off
        ve = self._ve
        zmin, zmax = float(np.nanmin(Z)), float(np.nanmax(Z))
        xspan = float(x.max() - x.min())
        yspan = float(y.max() - y.min())

        # surface — x/y centred, z centred and exaggerated
        self._surface = gl.GLSurfacePlotItem(
            x=x, y=y, z=(Z - z0) * ve, shader="normalColor", smooth=True)
        self._surface.translate(-x0, -y0, 0)
        self.addItem(self._surface)

        # floor grid under the surface
        grid = gl.GLGridItem()
        grid.setSize(x=xspan, y=yspan)
        grid.setSpacing(x=max(xspan / 10.0, 1.0), y=max(yspan / 10.0, 1.0))
        grid.translate(0, 0, (zmin - z0) * ve)
        self.addItem(grid)

        # coloured XYZ axes at the min corner
        axis = gl.GLAxisItem()
        axis.setSize(x=xspan * 0.55, y=yspan * 0.55,
                     z=max(zmax - zmin, 1.0) * ve * 1.2)
        axis.translate(-xspan / 2.0, -yspan / 2.0, (zmin - z0) * ve)
        self.addItem(axis)

        # Axis labels: just the axis name for E / N; Z carries its min/max values.
        xmin, xmax = float(x.min()), float(x.max())
        ymin, ymax = float(y.min()), float(y.max())
        self._add_label((xmax, ymin, zmin), "E", (160, 200, 255, 255))
        self._add_label((xmin, ymax, zmin), "N", (255, 235, 160, 255))
        self._add_label((xmin, ymin, zmax), f"Z {zmax:,.1f}", (170, 255, 190, 255))
        self._add_label((xmin, ymin, zmin), f"Z {zmin:,.1f}", (170, 255, 190, 255))

        # Cache grid vertices (centred + exaggerated world coords) for picking.
        nx, ny = len(x), len(y)
        wx = np.repeat(x - x0, ny)
        wy = np.tile(y - y0, nx)
        wz = ((Z - z0) * ve).reshape(-1)
        self._world_pts = np.stack([wx, wy, wz], axis=1)

        if self._measure_pts:        # redraw the measurement at the new exaggeration
            self._draw_measurement()

    def _add_label(self, real, text, color=(210, 230, 245, 255)):
        item = gl.GLTextItem(pos=np.array(self._real_to_world(real), dtype=float),
                             text=text, color=QColor(*color))
        self.addItem(item)

    def _extent_summary(self):
        if self._x is None:
            return ""
        xspan = float(self._x.max() - self._x.min())
        yspan = float(self._y.max() - self._y.min())
        zmin, zmax = float(np.nanmin(self._Z)), float(np.nanmax(self._Z))
        return (f"Extent {xspan:,.0f} × {yspan:,.0f} m   |   "
                f"Z {zmin:,.1f} … {zmax:,.1f} m (Δ {zmax - zmin:,.1f})   |   "
                f"{self._ve:g}× vertical")

    # ------------------------------------------------------------------ #
    # Vertical exaggeration                                               #
    # ------------------------------------------------------------------ #
    def set_vertical_exaggeration(self, ve):
        self._ve = max(0.1, float(ve))
        if self._x is not None:
            self._rebuild()
            self.status_text.emit(self._extent_summary())

    # ------------------------------------------------------------------ #
    # Measuring                                                           #
    # ------------------------------------------------------------------ #
    _MEASURE_HINT = "Measure: click two points (drag still navigates; Clear to reset)"

    def set_measure_mode(self, on: bool):
        self._measure_mode = bool(on)
        self.status_text.emit(self._MEASURE_HINT if on else self._extent_summary())

    def clear_measurement(self):
        for item in self._measure_items:
            try:
                self.removeItem(item)
            except Exception:
                pass
        self._measure_items = []
        self._measure_pts = []
        self._profile_pts = None
        self.status_text.emit(
            self._MEASURE_HINT if self._measure_mode else self._extent_summary())

    def _add_measure_point(self, real):
        if len(self._measure_pts) >= 2:
            return                       # complete — Clear to start a new one
        self._measure_pts.append(real)
        if len(self._measure_pts) == 2:
            from groundtruther.gt.surface_profile import sample_profile
            a, b = self._measure_pts
            self._profile_pts, self._surface_len, self._plan_len = sample_profile(
                self._x, self._y, self._Z, a, b)
        self._draw_measurement()
        if len(self._measure_pts) == 2:
            self._emit_measurement()
        else:
            self.status_text.emit("Measure: click the second point")

    def _draw_measurement(self):
        """(Re)draw markers + draped profile + floor projection (VE-aware)."""
        for item in self._measure_items:
            try:
                self.removeItem(item)
            except Exception:
                pass
        self._measure_items = []
        if not self._measure_pts:
            return

        def add(item):
            self.addItem(item)
            self._measure_items.append(item)

        # picked points (markers on the surface)
        add(gl.GLScatterPlotItem(
            pos=np.array([self._real_to_world(r) for r in self._measure_pts], float),
            color=(1.0, 0.2, 0.2, 1.0), size=12))

        if len(self._measure_pts) == 2 and self._profile_pts is not None:
            a, b = self._measure_pts
            zfloor = float(np.nanmin(self._Z))
            # draped profile line — follows the surface (the 3-D distance)
            add(gl.GLLinePlotItem(
                pos=np.array([self._real_to_world(p) for p in self._profile_pts], float),
                color=(1.0, 0.30, 0.30, 1.0), width=3, antialias=True))
            # horizontal projection on the E,N floor (the 2-D / plan distance)
            add(gl.GLLinePlotItem(
                pos=np.array([self._real_to_world((a[0], a[1], zfloor)),
                              self._real_to_world((b[0], b[1], zfloor))], float),
                color=(0.30, 0.80, 1.0, 1.0), width=2, antialias=True))
            # thin verticals tying the surface points to their floor projection
            for r in (a, b):
                add(gl.GLLinePlotItem(
                    pos=np.array([self._real_to_world(r),
                                  self._real_to_world((r[0], r[1], zfloor))], float),
                    color=(0.65, 0.65, 0.65, 0.7), width=1, antialias=True))

    def _emit_measurement(self):
        a, b = self._measure_pts
        dz = b[2] - a[2]                 # net endpoint change Z(B) - Z(A)
        chord = float(np.sqrt((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2 + dz * dz))
        zrange = 0.0                     # relief along the profile: max(Z) - min(Z)
        if self._profile_pts is not None and len(self._profile_pts):
            zcol = self._profile_pts[:, 2]
            zrange = float(np.nanmax(zcol) - np.nanmin(zcol))
        self.status_text.emit(
            f"Profile (3-D) {self._surface_len:,.1f} m   |   "
            f"Plan (2-D) {self._plan_len:,.1f} m   |   "
            f"straight {chord:,.1f} m   |   "
            f"ΔZ A→B {dz:,.1f} m   |   Z-range {zrange:,.1f} m")

    # ------------------------------------------------------------------ #
    # Picking (depth-buffer unprojection + grid snap)                     #
    # ------------------------------------------------------------------ #
    def _pick_world(self, pos):
        """Return the on-screen-nearest grid sample (E, N, Z) under *pos*.

        Forward-projects the grid vertices and picks the nearest to the pointer
        (no depth-buffer read — that fails with QOpenGLWidget's offscreen FBO).
        """
        if self._off is None or getattr(self, "_world_pts", None) is None:
            return None
        try:
            from groundtruther.gt.glmath import pick_nearest
            dpr = self.devicePixelRatioF()
            vp = tuple(int(v) for v in self.getViewport())   # (x, y, w, h)
            mouse = (pos.x() * dpr, vp[3] - pos.y() * dpr)    # GL bottom-left
            proj = _qmat_to_np(self.projectionMatrix(vp, vp))
            mvp = proj @ _qmat_to_np(self.viewMatrix())
            idx = pick_nearest(mouse, self._world_pts, mvp, vp, max_dist=24 * dpr)
            if idx is None:
                return None
            ny = len(self._y)
            i, j = divmod(idx, ny)
            return (float(self._x[i]), float(self._y[j]), float(self._Z[i, j]))
        except Exception:
            return None

    # ------------------------------------------------------------------ #
    # Mouse events                                                        #
    # ------------------------------------------------------------------ #
    def _event_pos(self, ev):
        return ev.position() if hasattr(ev, "position") else ev.pos()

    def mouseMoveEvent(self, ev):
        if ev.buttons() == Qt.MouseButton.NoButton:     # hover -> read-out
            real = self._pick_world(self._event_pos(ev))
            self.cursor_text.emit(
                f"E {real[0]:,.1f}   N {real[1]:,.1f}   Z {real[2]:,.1f} m"
                if real is not None else "")
            return
        super().mouseMoveEvent(ev)     # button held -> navigate (rotate/pan)

    def mousePressEvent(self, ev):
        # Always let the base class handle navigation; a *clean click* (handled
        # on release) is what picks. So dragging rotates/pans even in measure
        # mode and never disturbs an existing measurement.
        self._press_pos = self._event_pos(ev)
        super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev):
        super().mouseReleaseEvent(ev)
        if (self._measure_mode and ev.button() == Qt.MouseButton.LeftButton
                and self._press_pos is not None and len(self._measure_pts) < 2):
            pos = self._event_pos(ev)
            moved = abs(pos.x() - self._press_pos.x()) + abs(pos.y() - self._press_pos.y())
            if moved < 5:               # a click, not a drag
                real = self._pick_world(pos)
                if real is not None:
                    self._add_measure_point(real)
        self._press_pos = None
