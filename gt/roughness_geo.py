"""UTM georeferencing for roughness outputs — stateless.

When georeferencing is enabled, GroundTruther attaches a ``geo`` object to the
roughness request, built from the frame's navigation:

    geo = {
        "easting": <Xutm + dx>, "northing": <Yutm + dy>,   # calibrated USBL fix
        "heading_deg": <Heading|bearing>, "epsg": 32619,
        # mount fine-tune (server applies these):
        "heading_offset_deg": 0.0, "mirror": false,
    }

The easting/northing are the **calibrated USBL seafloor fix** —
``Xutm + dx`` / ``Yutm + dy`` (a direct measurement, canonical for HRS1508 and
matching pdal-mbio) — NOT the layback *model* ``Xutm_adj``/``Yutm_adj`` (which is
just ``proj(habcam_lon/lat)``, ~2.3–3.4 m off) and NOT the raw ship GPS
(``sXutm``/``sYutm``). Because the position is already corrected, ``layback_m``
stays 0.

The service then returns a GDAL geotransform for the micro-DEM / orthophoto grid
(they share one grid, so a single geotransform serves both)::

    geotransform = [c, a, b, f, d, e]      # GDAL order
    E = c + a*col + b*row
    N = f + d*col + e*row

This module assembles the request ``geo`` object and parses the returned
geotransform + imagery, and writes a GeoTIFF from a decoded grid.  Pure Python /
numpy / GDAL — no Qt, no QGIS, so it is unit-testable; the Qt mixin decodes the
PNGs and adds the resulting GeoTIFFs to the map.
"""
from __future__ import annotations

import math

import numpy as np

# Per-frame nav columns. easting/northing are the calibrated USBL seafloor fix
# ``Xutm + dx`` / ``Yutm + dy`` (base position + USBL offset) — the independent,
# measured truth (matches pdal-mbio), NOT the layback model ``Xutm_adj`` nor the
# ship GPS ``sXutm`` — so the rendered raster coincides with the substrate map
# and the sampling point.  This dataset has no "Heading" column — it carries
# "bearing"; try Heading first, then fall back to bearing.
DEFAULT_EASTING_COL = "Xutm"
DEFAULT_EASTING_OFFSET_COL = "dx"
DEFAULT_NORTHING_COL = "Yutm"
DEFAULT_NORTHING_OFFSET_COL = "dy"
DEFAULT_HEADING_COLS = ("Heading", "bearing")
DEFAULT_EPSG = 32619


def _finite(v) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) or math.isinf(f) else f


def usbl_easting_northing(record, *, easting_col: str = DEFAULT_EASTING_COL,
                          easting_offset_col: str = DEFAULT_EASTING_OFFSET_COL,
                          northing_col: str = DEFAULT_NORTHING_COL,
                          northing_offset_col: str = DEFAULT_NORTHING_OFFSET_COL):
    """Return the USBL seafloor fix ``(easting, northing)`` for a metadata row.

    ``easting = Xutm + dx``, ``northing = Yutm + dy`` (the calibrated USBL
    measurement).  Returns ``(None, None)`` when the base position is missing; a
    missing/NaN offset is treated as 0 (falls back to the base position).
    Shared by the request ``geo`` and the GT sampling-point marker so both sit on
    the same point.
    """
    def get(col):
        try:
            return record[col]
        except (KeyError, IndexError, TypeError):
            return None

    e_base, n_base = _finite(get(easting_col)), _finite(get(northing_col))
    if e_base is None or n_base is None:
        return None, None
    e_off = _finite(get(easting_offset_col)) or 0.0
    n_off = _finite(get(northing_offset_col)) or 0.0
    return e_base + e_off, n_base + n_off


def usbl_xy(df, *, easting_col: str = DEFAULT_EASTING_COL,
            easting_offset_col: str = DEFAULT_EASTING_OFFSET_COL,
            northing_col: str = DEFAULT_NORTHING_COL,
            northing_offset_col: str = DEFAULT_NORTHING_OFFSET_COL):
    """Vectorized USBL ``(easting, northing)`` arrays for a metadata DataFrame.

    ``easting = Xutm + dx``, ``northing = Yutm + dy``.  Returns
    ``(easting_array, northing_array)`` (numpy float arrays), or ``(None, None)``
    when the base position columns are absent.  NaN offsets are treated as 0.
    Used to put the image lookup / marker on the same USBL fix as the geo
    request.
    """
    cols = getattr(df, "columns", [])
    if easting_col not in cols or northing_col not in cols:
        return None, None
    e = np.asarray(df[easting_col], dtype=float)
    n = np.asarray(df[northing_col], dtype=float)
    if easting_offset_col in cols:
        e = e + np.nan_to_num(np.asarray(df[easting_offset_col], dtype=float))
    if northing_offset_col in cols:
        n = n + np.nan_to_num(np.asarray(df[northing_offset_col], dtype=float))
    return e, n


def build_geo(easting, northing, heading_deg, *, epsg: int = DEFAULT_EPSG,
              heading_offset_deg: float = 0.0, mirror: bool = False) -> dict | None:
    """Assemble the request ``geo`` object, or ``None`` if nav is incomplete.

    The mount is known, so the server derives position *and* rotation from the
    nav directly — no calibration.  ``heading_offset_deg`` is a residual
    fine-tune and ``mirror`` the only escape hatch; both are forwarded verbatim
    (the *server* applies them when computing the geotransform).
    """
    e, n, h = _finite(easting), _finite(northing), _finite(heading_deg)
    if e is None or n is None or h is None:
        return None
    return {
        "easting": e, "northing": n, "heading_deg": h, "epsg": int(epsg),
        "heading_offset_deg": float(heading_offset_deg), "mirror": bool(mirror),
        # easting/northing are ALREADY the towed-HabCam (layback-corrected)
        # position, so the server must not shift the origin again.
        "layback_m": 0.0, "cross_track_m": 0.0,
    }


def geo_from_record(record, *, epsg: int = DEFAULT_EPSG,
                    heading_offset_deg: float = 0.0, mirror: bool = False,
                    heading_cols=DEFAULT_HEADING_COLS) -> dict | None:
    """Build ``geo`` from a metadata row (pandas Series or plain mapping).

    easting/northing are the USBL fix (``Xutm + dx`` / ``Yutm + dy`` via
    :func:`usbl_easting_northing`).  ``heading_deg`` is looked up from the nav by
    the frame (per-row heading); tries each name in *heading_cols* in order (so
    "Heading" wins when present, else "bearing").  Returns ``None`` when
    position or heading are missing.
    """
    def get(col):
        try:
            return record[col]
        except (KeyError, IndexError, TypeError):
            return None

    heading = None
    for col in heading_cols:
        v = _finite(get(col))
        if v is not None:
            heading = v
            break
    easting, northing = usbl_easting_northing(record)
    return build_geo(easting, northing, heading,
                     epsg=epsg, heading_offset_deg=heading_offset_deg,
                     mirror=mirror)


def _as_geo(container) -> dict | None:
    """Coerce a ``{geotransform, epsg}`` block to a validated dict, or None."""
    if not isinstance(container, dict):
        return None
    gt = container.get("geotransform")
    if gt is None or len(gt) != 6:
        return None
    try:
        gt = [float(v) for v in gt]
    except (TypeError, ValueError):
        return None
    epsg = container.get("epsg")
    return {"geotransform": gt, "epsg": int(epsg) if epsg else None}


def extract_geo(result: dict | None) -> dict | None:
    """Find the geotransform+epsg in a roughness response, tolerant of shape.

    Looks for a shared top-level ``geo`` first (the documented "one geotransform
    serves both" case), then a ``geo`` nested under ``micro_dem`` / ``orthophoto``.
    Returns ``{"geotransform": [6], "epsg": int|None}`` or ``None``.
    """
    if not isinstance(result, dict):
        return None
    candidates = [result.get("geo")]
    for key in ("micro_dem", "orthophoto"):
        sub = result.get(key)
        if isinstance(sub, dict):
            candidates.append(sub.get("geo"))
    for c in candidates:
        geo = _as_geo(c)
        if geo is not None:
            return geo
    return None


def extract_images(result: dict | None) -> dict:
    """Return ``{"micro_dem": b64|None, "orthophoto": b64|None}`` from a result.

    Tolerant of both the flat (``micro_dem_png_b64``) and nested
    (``micro_dem: {png_b64}``) response shapes, and of a couple of plausible
    orthophoto key names.
    """
    result = result or {}

    def nested(key):
        sub = result.get(key)
        return sub.get("png_b64") if isinstance(sub, dict) else None

    micro = result.get("micro_dem_png_b64") or nested("micro_dem")
    ortho = (result.get("orthophoto_png_b64") or result.get("ortho_png_b64")
             or nested("orthophoto"))
    return {"micro_dem": micro, "orthophoto": ortho}


def write_geotiff(array, geotransform, epsg, path, *, nodata=None) -> str:
    """Write *array* as a GeoTIFF at *path* with the given geotransform + CRS.

    ``array`` may be 2-D (single band, e.g. the micro-DEM grid) or 3-D
    ``(H, W, bands)`` (e.g. an RGB(A) orthophoto).  ``geotransform`` is the GDAL
    6-tuple ``[c, a, b, f, d, e]`` (passed straight to ``SetGeoTransform``).
    Returns *path*.
    """
    from osgeo import gdal, gdal_array, osr

    a = np.asarray(array)
    if a.ndim == 2:
        h, w = a.shape
        bands = 1
    elif a.ndim == 3:
        h, w, bands = a.shape
    else:
        raise ValueError(f"array must be 2-D or 3-D, got shape {a.shape}")
    if len(geotransform) != 6:
        raise ValueError("geotransform must have 6 elements [c,a,b,f,d,e]")

    gdt = gdal_array.NumericTypeCodeToGDALTypeCode(a.dtype)
    if gdt is None:
        a = a.astype(np.float32)
        gdt = gdal_array.NumericTypeCodeToGDALTypeCode(a.dtype)

    ds = gdal.GetDriverByName("GTiff").Create(str(path), int(w), int(h),
                                              int(bands), gdt)
    if ds is None:
        raise RuntimeError(f"GDAL could not create GeoTIFF at {path}")
    ds.SetGeoTransform([float(v) for v in geotransform])
    if epsg:
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(int(epsg))
        ds.SetProjection(srs.ExportToWkt())
    if a.ndim == 2:
        band = ds.GetRasterBand(1)
        band.WriteArray(a)
        if nodata is not None:
            band.SetNoDataValue(float(nodata))
    else:
        # RGB / RGBA: tag colour interpretation so QGIS renders a 4th band as
        # alpha (automatic transparency); for 3-band output honour the nodata
        # fill so the uncovered border renders transparent.
        ci = [gdal.GCI_RedBand, gdal.GCI_GreenBand, gdal.GCI_BlueBand,
              gdal.GCI_AlphaBand]
        for i in range(bands):
            b = ds.GetRasterBand(i + 1)
            b.WriteArray(a[:, :, i])
            if i < len(ci):
                b.SetColorInterpretation(ci[i])
            if nodata is not None and i < 3:   # nodata on the colour bands only
                b.SetNoDataValue(float(nodata))
    ds.FlushCache()
    ds = None
    return str(path)
