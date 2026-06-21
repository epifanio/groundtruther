"""Unit tests for gt/roughness_geo.py (geo request, response parse, GeoTIFF)."""
import math

import numpy as np
import pytest

from groundtruther.gt import roughness_geo as rg


# --- build_geo --------------------------------------------------------------

def test_build_geo_basic():
    geo = rg.build_geo(510916.7, 4545982.0, 88.3)
    assert geo["easting"] == pytest.approx(510916.7)
    assert geo["northing"] == pytest.approx(4545982.0)
    assert geo["heading_deg"] == pytest.approx(88.3)
    assert geo["epsg"] == 32619
    # mount known → defaults: offset 0, mirror false
    assert geo["heading_offset_deg"] == 0.0
    assert geo["mirror"] is False
    assert "flip_e" not in geo and "flip_n" not in geo


def test_build_geo_calibration_passthrough():
    geo = rg.build_geo(1, 2, 3, epsg=32620, heading_offset_deg=5.5, mirror=True)
    assert geo["epsg"] == 32620
    assert geo["heading_offset_deg"] == 5.5
    assert geo["mirror"] is True


@pytest.mark.parametrize("e,n,h", [
    (None, 1, 2), (1, None, 2), (1, 2, None),
    (float("nan"), 1, 2), (1, 2, float("nan")), ("x", 1, 2),
])
def test_build_geo_incomplete_returns_none(e, n, h):
    assert rg.build_geo(e, n, h) is None


# --- geo_from_record --------------------------------------------------------

def test_geo_from_record_uses_heading_then_bearing():
    rec = {"Xutm_adj": 100.0, "Yutm_adj": 200.0, "bearing": 88.3}  # no Heading
    geo = rg.geo_from_record(rec)
    assert geo["heading_deg"] == pytest.approx(88.3)

    rec2 = {"Xutm_adj": 100.0, "Yutm_adj": 200.0, "Heading": 90.0, "bearing": 88.3}
    assert rg.geo_from_record(rec2)["heading_deg"] == 90.0  # Heading wins


def test_geo_from_record_missing_nav():
    assert rg.geo_from_record({"Xutm_adj": 1.0}) is None        # no northing/heading


def test_geo_from_record_pandas_series():
    import pandas as pd
    s = pd.Series({"Xutm_adj": 510916.7, "Yutm_adj": 4545982.0, "bearing": 88.0})
    geo = rg.geo_from_record(s, heading_offset_deg=2.0, mirror=True)
    assert geo["easting"] == pytest.approx(510916.7)
    assert geo["heading_offset_deg"] == 2.0
    assert geo["mirror"] is True


# --- extract_geo ------------------------------------------------------------

GT = [510000.0, 0.001, 0.0, 4545000.0, 0.0, -0.001]


def test_extract_geo_shared_top_level():
    out = rg.extract_geo({"geo": {"geotransform": GT, "epsg": 32619}})
    assert out["geotransform"] == GT
    assert out["epsg"] == 32619


def test_extract_geo_nested_under_micro_dem():
    out = rg.extract_geo({"micro_dem": {"geo": {"geotransform": GT, "epsg": 32619}}})
    assert out["geotransform"] == GT


def test_extract_geo_absent_or_bad():
    assert rg.extract_geo({}) is None
    assert rg.extract_geo({"geo": {"geotransform": [1, 2, 3]}}) is None  # wrong len
    assert rg.extract_geo(None) is None


# --- extract_images ---------------------------------------------------------

def test_extract_images_flat():
    imgs = rg.extract_images({"micro_dem_png_b64": "AAA"})
    assert imgs["micro_dem"] == "AAA"
    assert imgs["orthophoto"] is None


def test_extract_images_nested_and_ortho():
    imgs = rg.extract_images({
        "micro_dem": {"png_b64": "DEM"},
        "orthophoto": {"png_b64": "ORTHO"},
    })
    assert imgs["micro_dem"] == "DEM"
    assert imgs["orthophoto"] == "ORTHO"


def test_extract_images_ortho_alt_key():
    assert rg.extract_images({"ortho_png_b64": "X"})["orthophoto"] == "X"


# --- write_geotiff (GDAL round-trip) ---------------------------------------

def test_write_geotiff_singleband_roundtrip(tmp_path):
    from osgeo import gdal
    arr = np.arange(12, dtype=np.float32).reshape(3, 4)
    path = str(tmp_path / "dem.tif")
    rg.write_geotiff(arr, GT, 32619, path)

    ds = gdal.Open(path)
    assert ds.RasterXSize == 4 and ds.RasterYSize == 3
    assert ds.RasterCount == 1
    assert list(ds.GetGeoTransform()) == pytest.approx(GT)
    assert "32619" in ds.GetProjection()
    assert np.array_equal(ds.GetRasterBand(1).ReadAsArray(), arr)


def test_write_geotiff_rgb_roundtrip(tmp_path):
    from osgeo import gdal
    rgb = np.zeros((3, 4, 3), dtype=np.uint8)
    rgb[..., 0] = 255
    path = str(tmp_path / "ortho.tif")
    rg.write_geotiff(rgb, GT, 32619, path)

    ds = gdal.Open(path)
    assert ds.RasterCount == 3
    assert np.array_equal(ds.GetRasterBand(1).ReadAsArray(),
                          np.full((3, 4), 255, np.uint8))


def test_write_geotiff_bad_geotransform(tmp_path):
    with pytest.raises(ValueError):
        rg.write_geotiff(np.zeros((2, 2)), [1, 2, 3], 32619,
                         str(tmp_path / "x.tif"))
