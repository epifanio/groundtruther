"""Clip a reference-surface GeoTIFF (DEM / bathymetry) to a sampling area.

Used by the query builder's 3-D viewer: when a ``reference_surface`` GeoTIFF is
configured, the surface under the selected sampling shape is read straight from
the raster instead of being gridded from the soundings parquet.

Pure / no-Qt (uses GDAL) so it can be unit-tested. The output ``(x, y, Z)``
matches what ``pyqtgraph.opengl.GLSurfacePlotItem`` expects:

* ``x`` — 1-D easting (column) coordinates, ascending, in the raster's CRS
* ``y`` — 1-D northing (row) coordinates, ascending, in the raster's CRS
* ``Z`` — 2-D elevation, shape ``(len(x), len(y))``, NoData filled

The window is read in the raster's native CRS (north-up GeoTIFFs assumed) and
downsampled so ``max(nx, ny) <= max_size`` to keep the GL surface light.
"""
from __future__ import annotations

import math

import numpy as np


class ReferenceSurfaceError(RuntimeError):
    """Raised when the GeoTIFF cannot be clipped to the sampling area."""


def clip_surface(geotiff_path, bbox_lonlat, max_size: int = 300, band: int = 1):
    """Clip *geotiff_path* to *bbox_lonlat* and return ``(x, y, Z)`` for 3-D.

    Parameters
    ----------
    geotiff_path:
        Path to a single-band (or multi-band; ``band`` selects) elevation raster.
    bbox_lonlat:
        ``(min_lon, min_lat, max_lon, max_lat)`` of the sampling shape, EPSG:4326.
    max_size:
        Cap on the larger output dimension (down-sampling factor derived from it).
    band:
        1-based raster band to read.

    Raises ``ReferenceSurfaceError`` on any failure (caller falls back to the
    parquet surface).
    """
    try:
        from osgeo import gdal, osr
    except ImportError as exc:  # pragma: no cover - GDAL ships with QGIS
        raise ReferenceSurfaceError(f"GDAL not available: {exc}")

    gdal.UseExceptions()
    try:
        ds = gdal.Open(str(geotiff_path))
    except Exception as exc:
        raise ReferenceSurfaceError(f"cannot open raster: {exc}")
    if ds is None:
        raise ReferenceSurfaceError(f"cannot open raster: {geotiff_path}")

    gt = ds.GetGeoTransform()
    if gt is None or gt[2] != 0 or gt[4] != 0:
        raise ReferenceSurfaceError("only north-up GeoTIFFs are supported")

    wkt = ds.GetProjection()
    if not wkt:
        raise ReferenceSurfaceError("raster has no CRS")

    src_srs = osr.SpatialReference()
    src_srs.ImportFromWkt(wkt)
    wgs = osr.SpatialReference()
    wgs.ImportFromEPSG(4326)
    src_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    wgs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    ct = osr.CoordinateTransformation(wgs, src_srs)

    min_lon, min_lat, max_lon, max_lat = bbox_lonlat
    corners = [(min_lon, min_lat), (min_lon, max_lat),
               (max_lon, min_lat), (max_lon, max_lat)]
    xs, ys = [], []
    for lon, lat in corners:
        X, Y, _ = ct.TransformPoint(float(lon), float(lat))
        xs.append(X)
        ys.append(Y)
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)

    # CRS bbox -> pixel window (gt[5] is negative for north-up rasters)
    inv_gt = gdal.InvGeoTransform(gt)
    px0, py0 = gdal.ApplyGeoTransform(inv_gt, minx, maxy)   # top-left
    px1, py1 = gdal.ApplyGeoTransform(inv_gt, maxx, miny)   # bottom-right
    col_off = max(0, int(math.floor(min(px0, px1))))
    row_off = max(0, int(math.floor(min(py0, py1))))
    col_end = min(ds.RasterXSize, int(math.ceil(max(px0, px1))))
    row_end = min(ds.RasterYSize, int(math.ceil(max(py0, py1))))
    win_w = col_end - col_off
    win_h = row_end - row_off
    if win_w < 2 or win_h < 2:
        raise ReferenceSurfaceError("sampling area does not overlap the reference surface")

    out_w = min(win_w, max_size)
    out_h = min(win_h, max_size)

    try:
        band_obj = ds.GetRasterBand(band)
        arr = band_obj.ReadAsArray(col_off, row_off, win_w, win_h, out_w, out_h)
    except Exception as exc:
        raise ReferenceSurfaceError(f"cannot read raster window: {exc}")
    if arr is None:
        raise ReferenceSurfaceError("empty raster window")
    arr = np.asarray(arr, dtype=float)

    nodata = band_obj.GetNoDataValue()
    if nodata is not None:
        arr[arr == nodata] = np.nan
    if np.isnan(arr).all():
        raise ReferenceSurfaceError("clipped surface is all NoData")
    if np.isnan(arr).any():
        arr = np.where(np.isnan(arr), np.nanmedian(arr), arr)

    # CRS bounds of the read window (cell edges)
    win_minx = gt[0] + col_off * gt[1]
    win_maxx = gt[0] + col_end * gt[1]
    win_maxy = gt[3] + row_off * gt[5]
    win_miny = gt[3] + row_end * gt[5]

    # cell-centre coordinates of the down-sampled grid
    x = win_minx + (np.arange(out_w) + 0.5) * (win_maxx - win_minx) / out_w
    y_top_down = win_maxy + (np.arange(out_h) + 0.5) * (win_miny - win_maxy) / out_h
    # flip rows so y ascends (south -> north), matching the parquet surface
    y = y_top_down[::-1]
    arr = arr[::-1, :]

    # For a correct 3-D aspect ratio the horizontal axes must share the unit of
    # the elevation (metres). Projected rasters already are metric; geographic
    # rasters (degrees) are converted to local metres (equirectangular about the
    # window centre) so x / y / Z are all in metres.
    if src_srs.IsGeographic():
        cx = float((x.min() + x.max()) / 2.0)
        cy = float((y.min() + y.max()) / 2.0)
        x = (x - cx) * 111320.0 * math.cos(math.radians(cy))
        y = (y - cy) * 110540.0

    Z = arr.T  # (nx, ny) as GLSurfacePlotItem expects
    ds = None
    return x, y, Z
