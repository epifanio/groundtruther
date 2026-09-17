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


# --- USBL position ----------------------------------------------------------

def test_usbl_easting_northing():
    rec = {"Xutm": 510918.4, "Yutm": 4545982.3, "dx": 144.9, "dy": 4.5}
    e, n = rg.usbl_easting_northing(rec)
    assert e == pytest.approx(511063.3)        # Xutm + dx
    assert n == pytest.approx(4545986.8)       # Yutm + dy


def test_usbl_missing_offset_falls_back_to_base():
    e, n = rg.usbl_easting_northing({"Xutm": 100.0, "Yutm": 200.0})  # no dx/dy
    assert (e, n) == (100.0, 200.0)


def test_usbl_missing_base_is_none():
    assert rg.usbl_easting_northing({"dx": 1.0, "dy": 2.0}) == (None, None)


def test_usbl_xy_vectorized():
    import pandas as pd
    df = pd.DataFrame({"Xutm": [100.0, 200.0], "Yutm": [10.0, 20.0],
                       "dx": [1.0, 2.0], "dy": [0.5, np.nan]})
    e, n = rg.usbl_xy(df)
    assert e.tolist() == [101.0, 202.0]            # Xutm + dx
    assert n.tolist() == [10.5, 20.0]              # Yutm + dy (NaN offset -> 0)


def test_usbl_xy_missing_columns():
    import pandas as pd
    assert rg.usbl_xy(pd.DataFrame({"Yutm": [1.0]})) == (None, None)


# --- geo_from_record --------------------------------------------------------

def test_geo_from_record_uses_usbl_fix():
    # easting = Xutm + dx, northing = Yutm + dy (NOT Xutm_adj / sXutm)
    rec = {"Xutm": 1000.0, "Yutm": 2000.0, "dx": 12.0, "dy": -3.0, "bearing": 88.3}
    geo = rg.geo_from_record(rec)
    assert geo["easting"] == pytest.approx(1012.0)
    assert geo["northing"] == pytest.approx(1997.0)
    assert geo["heading_deg"] == pytest.approx(268.3)       # bearing reversed
    assert geo["layback_m"] == 0.0             # position already corrected


def test_geo_from_record_missing_nav():
    assert rg.geo_from_record({"Xutm": 1.0}) is None        # no Yutm / heading


def test_geo_from_record_pandas_series():
    import pandas as pd
    s = pd.Series({"Xutm": 510916.7, "Yutm": 4545982.0, "dx": 2.0, "dy": 1.0,
                   "bearing": 88.0})
    geo = rg.geo_from_record(s, heading_offset_deg=2.0, mirror=True)
    assert geo["easting"] == pytest.approx(510918.7)        # Xutm + dx
    assert geo["heading_deg"] == pytest.approx(268.0)       # bearing reversed
    assert geo["heading_offset_deg"] == 2.0
    assert geo["mirror"] is True


# --- the heading convention (issue #31) -------------------------------------
#
# `Heading` and `bearing` are two different quantities, not two spellings of
# one.  `Heading` is a vehicle attitude.  `bearing` is the compass direction of
# the layback offset (dx, dy) — ship -> towed HabCam, ~148 m astern — so it
# points *backwards* along the tow, roughly 180 deg from the course made good.
#
# The service rotates the frame so image bottom->top is `heading_deg`, and the
# camera's image-up points forward (seabed content scrolls DOWN between
# consecutive frames, 60 of 60 confident template matches, by the distance the
# platform travels).  So a `bearing` must be reversed before it is sent.
#
# Until this was fixed the plugin sent `bearing` as `heading_deg`, which rotated
# every georeferenced micro-DEM, orthophoto and nav-placed mosaic 180 deg about
# its own centre.  Positions were, and are, correct.

def test_a_true_heading_column_is_sent_unchanged():
    base = {"Xutm": 100.0, "Yutm": 200.0, "dx": 0.0, "dy": 0.0}
    assert rg.geo_from_record({**base, "Heading": 90.0})["heading_deg"] == 90.0


def test_a_bearing_column_is_turned_round():
    base = {"Xutm": 100.0, "Yutm": 200.0, "dx": 0.0, "dy": 0.0}
    assert rg.geo_from_record({**base, "bearing": 88.3})["heading_deg"] == (
        pytest.approx(268.3))


def test_heading_wins_over_bearing_when_both_are_present():
    """A measured attitude beats geometry inferred from the layback."""
    rec = {"Xutm": 100.0, "Yutm": 200.0, "dx": 0.0, "dy": 0.0,
           "Heading": 268.0, "bearing": 88.3}
    assert rg.geo_from_record(rec)["heading_deg"] == 268.0


@pytest.mark.parametrize("bearing, expected", [
    (0.0, 180.0),
    (88.3, 268.3),
    (180.0, 0.0),           # wraps
    (-180.0, 0.0),          # the nav's own range is -180..180
    (-91.7, 88.3),
    (359.0, 179.0),
    (270.0, 90.0),
])
def test_reverse_bearing_normalises_to_0_360(bearing, expected):
    assert rg.reverse_bearing(bearing) == pytest.approx(expected)


def test_reversing_twice_is_the_identity():
    for b in (0.0, 45.5, 88.3, 179.9, 359.0):
        assert rg.reverse_bearing(rg.reverse_bearing(b)) == pytest.approx(b % 360.0)


def test_platform_heading_is_none_when_the_row_has_neither_column():
    assert rg.platform_heading_from_record({"Xutm": 1.0, "Yutm": 2.0}) is None


def test_the_reversal_reproduces_the_course_over_ground():
    """The sanity check that made this a measurement rather than an argument.

    `bearing` is the direction of the (dx, dy) offset, so a row's own numbers
    say which way is astern; the heading is the other way round.
    """
    import math
    dx, dy = 143.56, 3.37                       # a real row from the HRS1508 nav
    bearing = math.degrees(math.atan2(dx, dy)) % 360.0
    rec = {"Xutm": 0.0, "Yutm": 0.0, "dx": dx, "dy": dy, "bearing": bearing}

    heading = rg.geo_from_record(rec)["heading_deg"]
    # the ship is ahead of the body, so ship-relative-to-body is the heading
    towards_ship = math.degrees(math.atan2(-dx, -dy)) % 360.0
    assert heading == pytest.approx(towards_ship, abs=1e-6)


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
