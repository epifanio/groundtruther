# GroundTruther — a toolset for seafloor characterization
#
# Copyright (C) 2023-2026 Massimo Di Stefano <epiesasha@me.com>
# https://github.com/epifanio/groundtruther
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Sample a regular-grid surface along a segment (for the 3-D measure tool).

Pure / no-Qt so it can be unit-tested. Given a gridded surface (ascending
``x``/``y`` axes and ``Z`` shaped ``(len(x), len(y))`` — i.e. ``Z[i, j]`` at
``(x[i], y[j])``) it returns the *draped* profile between two points and its
along-surface length, plus the horizontal (plan) length.
"""
from __future__ import annotations

import numpy as np


def bilinear_z(x, y, Z, px, py):
    """Bilinearly interpolate the surface elevation at ``(px, py)``."""
    x = np.asarray(x); y = np.asarray(y)
    nx, ny = len(x), len(y)
    i = int(np.clip(np.searchsorted(x, px) - 1, 0, nx - 2))
    j = int(np.clip(np.searchsorted(y, py) - 1, 0, ny - 2))
    x0, x1 = x[i], x[i + 1]
    y0, y1 = y[j], y[j + 1]
    tx = (px - x0) / (x1 - x0) if x1 > x0 else 0.0
    ty = (py - y0) / (y1 - y0) if y1 > y0 else 0.0
    tx = min(max(tx, 0.0), 1.0)
    ty = min(max(ty, 0.0), 1.0)
    z00, z10 = Z[i, j], Z[i + 1, j]
    z01, z11 = Z[i, j + 1], Z[i + 1, j + 1]
    return float(z00 * (1 - tx) * (1 - ty) + z10 * tx * (1 - ty)
                 + z01 * (1 - tx) * ty + z11 * tx * ty)


def sample_profile(x, y, Z, a, b, n=None):
    """Drape the segment ``a``→``b`` over the surface.

    Parameters
    ----------
    a, b: ``(E, N[, Z])`` end points (Z ignored — read from the surface).
    n: number of samples; default ≈ one per grid cell crossed (clamped 8…400).

    Returns ``(pts, surface_len, plan_len)``:
    * ``pts`` — ``(n, 3)`` draped polyline in real coords;
    * ``surface_len`` — along-surface (3-D) length;
    * ``plan_len`` — horizontal (E,N) straight length.
    """
    x = np.asarray(x, float); y = np.asarray(y, float)
    ax, ay = float(a[0]), float(a[1])
    bx, by = float(b[0]), float(b[1])
    plan_len = float(np.hypot(bx - ax, by - ay))

    if n is None:
        cell = min(
            float(np.mean(np.diff(x))) if len(x) > 1 else 1.0,
            float(np.mean(np.diff(y))) if len(y) > 1 else 1.0,
        )
        n = int(np.clip(round(plan_len / max(cell, 1e-9)) + 1, 8, 400))

    ts = np.linspace(0.0, 1.0, int(n))
    pts = np.empty((len(ts), 3), dtype=float)
    for k, t in enumerate(ts):
        px = ax + (bx - ax) * t
        py = ay + (by - ay) * t
        pts[k] = (px, py, bilinear_z(x, y, Z, px, py))

    surface_len = float(np.sqrt((np.diff(pts, axis=0) ** 2).sum(axis=1)).sum())
    return pts, surface_len, plan_len
