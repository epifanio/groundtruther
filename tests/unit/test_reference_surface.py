"""Unit tests for gt.reference_surface.clip_surface (synthetic GeoTIFF)."""
import numpy as np
import pytest

gdal_osr = pytest.importorskip("osgeo")
from osgeo import gdal, osr  # noqa: E402

from groundtruther.gt.reference_surface import clip_surface, ReferenceSurfaceError


def _make_geotiff(path, nx=100, ny=100, lon0=18.0, lat0=75.0, px=0.001,
                  nodata=-9999.0):
    """A 4326 DEM with a known ramp z = -100 - (row + col); some NoData cells."""
    drv = gdal.GetDriverByName("GTiff")
    ds = drv.Create(str(path), nx, ny, 1, gdal.GDT_Float32)
    # north-up: origin top-left, gt[5] negative
    ds.SetGeoTransform((lon0, px, 0, lat0, 0, -px))
    srs = osr.SpatialReference(); srs.ImportFromEPSG(4326)
    ds.SetProjection(srs.ExportToWkt())
    rows, cols = np.mgrid[0:ny, 0:nx]
    z = (-100.0 - (rows + cols)).astype(np.float32)
    z[0:3, 0:3] = nodata          # a NoData patch in the far corner
    band = ds.GetRasterBand(1)
    band.SetNoDataValue(nodata)
    band.WriteArray(z)
    ds.FlushCache(); ds = None


def test_clip_basic(tmp_path):
    tif = tmp_path / "dem.tif"
    _make_geotiff(tif)
    # sub-window well inside the raster (and away from the NoData corner)
    bbox = (18.02, 74.96, 18.05, 74.99)   # min_lon, min_lat, max_lon, max_lat
    x, y, Z = clip_surface(str(tif), bbox)

    assert x.ndim == 1 and y.ndim == 1 and Z.ndim == 2
    assert Z.shape == (len(x), len(y))                 # GLSurfacePlotItem layout
    assert np.all(np.diff(x) > 0) and np.all(np.diff(y) > 0)  # ascending
    # geographic raster -> horizontal coords converted to local metres, centred
    assert abs(x.mean()) < 1.0 and abs(y.mean()) < 1.0
    # ~0.03 deg window -> hundreds–thousands of metres across
    assert 100 < (x.max() - x.min()) < 6000
    assert 100 < (y.max() - y.min()) < 6000
    # elevation is the negative ramp (bathymetry-like), finite everywhere
    assert np.isfinite(Z).all()
    assert Z.max() < 0


def test_downsampling_caps_size(tmp_path):
    tif = tmp_path / "big.tif"
    _make_geotiff(tif, nx=400, ny=400)
    x, y, Z = clip_surface(str(tif), (18.0, 74.61, 18.39, 75.0), max_size=120)
    assert max(len(x), len(y)) <= 120
    assert Z.shape == (len(x), len(y))


def test_nodata_filled_not_nan(tmp_path):
    tif = tmp_path / "dem.tif"
    _make_geotiff(tif)
    # window overlapping the NoData corner (top-left of the raster)
    x, y, Z = clip_surface(str(tif), (18.0, 74.98, 18.02, 75.0))
    assert np.isfinite(Z).all()   # NoData replaced with median, no holes


def test_no_overlap_raises(tmp_path):
    tif = tmp_path / "dem.tif"
    _make_geotiff(tif)
    with pytest.raises(ReferenceSurfaceError):
        clip_surface(str(tif), (10.0, 60.0, 10.1, 60.1))   # far from the raster


def test_missing_file_raises(tmp_path):
    with pytest.raises(ReferenceSurfaceError):
        clip_surface(str(tmp_path / "nope.tif"), (18.0, 74.9, 18.1, 75.0))
