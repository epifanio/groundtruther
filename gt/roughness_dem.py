"""Turn a micro-DEM preview into a 3-D surface grid — stateless.

The roughness service returns the micro-DEM as a small grayscale PNG
(``micro_dem_png_b64``) whose luminance encodes *relative* height, plus the
real-world ``extent_mm`` ([xmin, xmax, ymin, ymax] in mm) and ``dem_shape`` of
the full DEM.  There is no calibrated elevation array in the response, so this
builds a relief surface from the preview: real metric X/Y from ``extent_mm`` and
a *relative* Z from the normalised luminance (vertical scale is a display
choice, adjustable via the viewer's vertical-exaggeration control).

The output ``(x, y, Z)`` matches the contract of
:meth:`pygui.reference_3d_view.Reference3DView.set_surface` — the same viewer the
reference-surface tab uses — so the micro-DEM renders identically: ``x`` of
length ``W`` (columns), ``y`` of length ``H`` (rows), ``Z`` of shape
``(W, H)``.

Pure numpy; no Qt, no QGIS — the PNG is decoded on the Qt side and the decoded
array handed in here, keeping this unit-testable.
"""
from __future__ import annotations

import base64

import numpy as np

# Default vertical relief as a fraction of the smaller horizontal span, used
# when no explicit ``z_scale`` is given.  Heights are relative/provisional, so
# this is a "looks reasonable at 1× exaggeration" choice, not a calibration.
_DEFAULT_RELIEF_FRACTION = 0.15


def _to_luminance(arr: np.ndarray) -> np.ndarray:
    """Reduce an image array to a 2-D luminance plane (float)."""
    a = np.asarray(arr, dtype=float)
    if a.ndim == 2:
        return a
    if a.ndim == 3:
        # RGB(A): standard luma weights over the first three channels.  The
        # micro-DEM PNG is grayscale (R==G==B), so a plain mean is equivalent,
        # but weighting is correct for any colourised preview too.
        rgb = a[..., :3]
        return rgb @ np.array([0.2126, 0.7152, 0.0722])
    raise ValueError(f"expected a 2-D or 3-D image array, got shape {a.shape}")


def micro_dem_grid(height_img, extent_mm=None, *, z_scale: float | None = None,
                   origin: str = "upper", invert: bool = False):
    """Build ``(x, y, Z)`` for the 3-D viewer from a micro-DEM preview image.

    Parameters
    ----------
    height_img:
        2-D (H, W) or 3-D (H, W, C) array of relative heights — typically the
        decoded grayscale ``micro_dem_png_b64`` (luminance ∝ height).
    extent_mm:
        ``[xmin, xmax, ymin, ymax]`` in millimetres (the response ``extent_mm``).
        When ``None``, pixel indices are used for X/Y.
    z_scale:
        Full vertical span (in mm) the normalised luminance maps onto.  When
        ``None``, defaults to ``0.15 × min(x-span, y-span)`` so the relief is
        visible at 1× exaggeration.
    origin:
        ``"upper"`` (default, image convention: row 0 is the top / north edge)
        flips rows so that ascending ``y`` runs south→north.  ``"lower"`` leaves
        rows as-is.
    invert:
        When ``True``, treat *brighter = lower* (flip the height sense).

    Returns
    -------
    (x, y, Z)
        ``x`` (len W, mm), ``y`` (len H, mm), and ``Z`` of shape ``(W, H)`` in
        mm — ready for ``Reference3DView.set_surface``.
    """
    lum = _to_luminance(height_img)
    if lum.ndim != 2 or lum.size == 0:
        raise ValueError("height_img must be a non-empty 2-D image")

    if origin == "upper":
        lum = lum[::-1]                      # row 0 -> ymax, so y can ascend
    h, w = lum.shape

    if extent_mm is not None:
        xmin, xmax, ymin, ymax = (float(v) for v in extent_mm)
    else:
        xmin, xmax, ymin, ymax = 0.0, float(w), 0.0, float(h)

    x = np.linspace(xmin, xmax, w)
    y = np.linspace(ymin, ymax, h)

    # Normalise luminance to [0, 1]; flat images become a flat surface.
    lo, hi = float(np.nanmin(lum)), float(np.nanmax(lum))
    znorm = (lum - lo) / (hi - lo) if hi > lo else np.zeros_like(lum)
    if invert:
        znorm = 1.0 - znorm

    if z_scale is None:
        xspan = abs(xmax - xmin)
        yspan = abs(ymax - ymin)
        z_scale = _DEFAULT_RELIEF_FRACTION * max(min(xspan, yspan), 1.0)

    Z = (znorm * float(z_scale)).T          # (H, W) -> (W, H) == (len(x), len(y))
    return x, y, Z


# --------------------------------------------------------------------------- #
# Real-height micro-DEM (dem_format "mm"/"both") — a float32 world-mm grid     #
# --------------------------------------------------------------------------- #

def decode_float_grid(obj: dict):
    """Decode a ``{format, shape, data_b64, dx_mm, x0_mm, y0_mm}`` float grid.

    Returns ``(heights, dx_mm, x0_mm, y0_mm)`` where ``heights`` is a 2-D
    ``(rows, cols)`` float32 array in mm with ``NaN`` for no-data (preserved).
    """
    if not isinstance(obj, dict):
        raise ValueError("micro_dem float grid must be a dict")
    shape = obj.get("shape")
    b64 = obj.get("data_b64")
    if not shape or len(shape) != 2 or not b64:
        raise ValueError("micro_dem grid needs shape[2] and data_b64")
    rows, cols = int(shape[0]), int(shape[1])
    dt = np.dtype(np.float32)
    if str(obj.get("byte_order", "little")).lower().startswith("big"):
        dt = dt.newbyteorder(">")
    arr = np.frombuffer(base64.b64decode(b64), dtype=dt)
    if arr.size != rows * cols:
        raise ValueError(
            f"micro_dem grid size {arr.size} != rows*cols {rows * cols}")
    heights = np.ascontiguousarray(arr, dtype=np.float32).reshape(rows, cols)
    return (heights, float(obj.get("dx_mm", 1.0)),
            float(obj.get("x0_mm", 0.0)), float(obj.get("y0_mm", 0.0)))


def _erode_mask(valid: np.ndarray, iters: int) -> np.ndarray:
    """Erode a boolean mask by *iters* steps (4-connectivity).

    A cell survives only if it and its up/down/left/right neighbours are all
    valid, so each pass peels one ring off every no-data / outlier boundary.
    """
    m = valid
    for _ in range(int(iters)):
        e = m.copy()
        e[:-1, :] &= m[1:, :]
        e[1:, :] &= m[:-1, :]
        e[:, :-1] &= m[:, 1:]
        e[:, 1:] &= m[:, :-1]
        m = e
    return m


def mesh_from_micro_dem(obj: dict, *, fill_nan: bool = True, trim_border: int = 0,
                        clip_sigma: float | None = None, erode: int = 0):
    """Build a real-height mesh from the float micro-DEM for the 3-D viewer.

    ``X = x0_mm + col*dx_mm``, ``Y = y0_mm + row*dx_mm``, ``Z = height_mm``
    (Z up).  Returns ``(x, y, Z, valid)`` shaped for
    ``Reference3DView.set_surface``: ``x`` len ``cols``, ``y`` len ``rows``,
    ``Z`` and ``valid`` of shape ``(cols, rows)``.  Masked cells (no-data,
    outliers, eroded border) are filled with the median so the GL surface stays
    continuous and spike-free; the ``valid`` mask lets the caller hide them
    (e.g. via texture alpha in :func:`colors_from_rgb`).

    Edge-spike mitigation (the stereo DEM is unreliable at the very edge and
    around no-data holes — bad disparity there shows as "stalactite" spikes
    draped with stretched texture):

    * *trim_border* — drop that many outer rows/columns up front.
    * *clip_sigma* — robust outlier rejection: mask cells whose height is more
      than ``clip_sigma`` MAD-based robust sigmas from the median (kills spikes).
    * *erode* — peel that many rings off every no-data / outlier boundary, where
      disparity is noisiest.

    Pass the same *trim_border* to :func:`colors_from_rgb`, and the returned
    ``valid`` mask, so the texture hides exactly the masked cells.
    """
    heights, dx, x0, y0 = decode_float_grid(obj)
    t = int(trim_border)
    if t > 0 and heights.shape[0] > 2 * t and heights.shape[1] > 2 * t:
        heights = heights[t:-t, t:-t]
        x0 += t * dx          # origin shifts with the dropped left/top edge
        y0 += t * dx
    rows, cols = heights.shape
    x = x0 + np.arange(cols, dtype=float) * dx
    y = y0 + np.arange(rows, dtype=float) * dx
    Z = heights.T.astype(float)                       # (cols, rows)
    valid = ~np.isnan(Z)

    # Robust outlier rejection — MAD-based, so a few wild edge cells don't drag
    # the threshold. sigma ≈ 1.4826·MAD (consistent with std for a normal).
    if clip_sigma and valid.any():
        v = Z[valid]
        med = float(np.median(v))
        sigma = 1.4826 * float(np.median(np.abs(v - med)))
        if sigma <= 0:                     # near-constant data → MAD degenerates
            sigma = float(np.std(v))
        if sigma > 0:
            valid &= np.abs(Z - med) <= float(clip_sigma) * sigma

    # Erode the boundary ring (touching no-data / outliers) where edge disparity
    # is unreliable.
    if erode and not valid.all():
        valid = _erode_mask(valid, erode)

    if fill_nan and not valid.all():
        fill = float(np.median(Z[valid])) if valid.any() else 0.0
        Z = np.where(valid, Z, fill)
    return x, y, Z, valid


def valid_faces(valid) -> np.ndarray:
    """Triangle faces for a grid surface, skipping quads that touch a hole.

    *valid* is the ``(nx, ny)`` boolean mask with vertex index ``i*ny + j``
    (matching ``Reference3DView``'s grid flattening).  Returns an ``(M, 3)``
    int32 array of vertex indices — two triangles per fully-valid quad — for a
    ``GLMeshItem``.  No-data / masked cells become genuine holes (no faces drawn)
    rather than transparent ones, which avoids the depth/blend "ghosting" and
    flicker you get when rendering alpha-masked surface cells.
    """
    v = np.asarray(valid, dtype=bool)
    if v.ndim != 2:
        raise ValueError("valid mask must be 2-D")
    nx, ny = v.shape
    if nx < 2 or ny < 2:
        return np.empty((0, 3), dtype=np.int32)
    # A quad is drawable only when all four corners are valid.
    quad = v[:-1, :-1] & v[1:, :-1] & v[:-1, 1:] & v[1:, 1:]
    ii, jj = np.nonzero(quad)
    v00 = ii * ny + jj
    v10 = (ii + 1) * ny + jj
    v01 = ii * ny + (jj + 1)
    v11 = (ii + 1) * ny + (jj + 1)
    faces = np.empty((2 * ii.size, 3), dtype=np.int32)
    faces[0::2] = np.stack([v00, v10, v11], axis=1)
    faces[1::2] = np.stack([v00, v11, v01], axis=1)
    return faces


def colors_from_rgb(rgb, valid=None, *, trim_border: int = 0):
    """Per-vertex RGBA colours (0–1) for a textured GL surface.

    *rgb* is the orthophoto ``(rows, cols, 3+)``; it is co-registered
    cell-for-cell with the micro-DEM, so texel ``(row, col)`` maps to mesh
    vertex ``(row, col)``.  Returns a ``(cols, rows, 4)`` array aligned to the
    mesh's ``(x, y)`` ordering; where *valid* is False the alpha is 0 (no-data
    cells become transparent holes).

    *trim_border* must match the value passed to :func:`mesh_from_micro_dem` so
    the texture stays cell-aligned with the (border-trimmed) mesh.
    """
    a = np.asarray(rgb)
    if a.ndim != 3 or a.shape[2] < 3:
        raise ValueError(f"orthophoto must be (rows, cols, 3+), got {a.shape}")
    t = int(trim_border)
    if t > 0 and a.shape[0] > 2 * t and a.shape[1] > 2 * t:
        a = a[t:-t, t:-t]
    rgb3 = np.transpose(a[..., :3].astype(float) / 255.0, (1, 0, 2))  # (cols,rows,3)
    h, w = rgb3.shape[0], rgb3.shape[1]
    out = np.ones((h, w, 4), dtype=float)
    out[..., :3] = rgb3
    if valid is not None:
        out[..., 3] = np.asarray(valid, dtype=float)
    return out
