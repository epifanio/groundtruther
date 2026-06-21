"""Unit tests for gt/roughness_dem.py (pure numpy grid builder)."""
import numpy as np
import pytest

from groundtruther.gt import roughness_dem as rd


def test_shapes_match_set_surface_contract():
    # H=4 rows, W=6 cols
    img = np.arange(24, dtype=float).reshape(4, 6)
    x, y, Z = rd.micro_dem_grid(img, extent_mm=[0, 60, 0, 40])
    assert x.shape == (6,)          # len W
    assert y.shape == (4,)          # len H
    assert Z.shape == (6, 4)        # (len(x), len(y))


def test_extent_maps_to_xy():
    img = np.zeros((5, 10))
    x, y, Z = rd.micro_dem_grid(img, extent_mm=[-100, 100, -50, 50])
    assert x[0] == pytest.approx(-100) and x[-1] == pytest.approx(100)
    assert y[0] == pytest.approx(-50) and y[-1] == pytest.approx(50)


def test_default_extent_is_pixel_indices():
    img = np.zeros((3, 7))
    x, y, _ = rd.micro_dem_grid(img)
    assert x[0] == 0.0 and x[-1] == pytest.approx(7.0)
    assert y[0] == 0.0 and y[-1] == pytest.approx(3.0)


def test_z_normalised_and_scaled():
    # gradient 0..255; z_scale=100 -> Z spans 0..100
    img = np.tile(np.linspace(0, 255, 8), (4, 1))   # (4, 8)
    _, _, Z = rd.micro_dem_grid(img, extent_mm=[0, 8, 0, 4], z_scale=100.0)
    assert np.nanmin(Z) == pytest.approx(0.0)
    assert np.nanmax(Z) == pytest.approx(100.0)


def test_flat_image_is_flat_surface():
    img = np.full((4, 5), 128.0)
    _, _, Z = rd.micro_dem_grid(img, z_scale=50.0)
    assert np.allclose(Z, 0.0)      # no division-by-zero, flat relief


def test_invert_flips_height_sense():
    img = np.tile(np.linspace(0, 1, 6), (3, 1))
    _, _, Z = rd.micro_dem_grid(img, z_scale=10.0, origin="lower")
    _, _, Zi = rd.micro_dem_grid(img, z_scale=10.0, origin="lower", invert=True)
    # brightest column is max in normal, min when inverted
    assert Z[-1, 0] == pytest.approx(10.0)
    assert Zi[-1, 0] == pytest.approx(0.0)


def test_origin_upper_flips_rows():
    # distinct value per row; origin="upper" should put row 0 (top) at ymax
    img = np.array([[0.0], [1.0], [2.0]])   # 3 rows, 1 col -> needs W>=1
    img = np.repeat(img, 4, axis=1)         # (3, 4)
    _, _, Z_up = rd.micro_dem_grid(img, extent_mm=[0, 4, 0, 3],
                                   origin="upper", z_scale=2.0)
    _, _, Z_lo = rd.micro_dem_grid(img, extent_mm=[0, 4, 0, 3],
                                   origin="lower", z_scale=2.0)
    # Z is (W,H); column 0 over y. upper vs lower reverse the y-ordering.
    assert np.allclose(Z_up[0], Z_lo[0][::-1])


def test_rgb_input_reduced_to_luminance():
    rgb = np.zeros((2, 3, 3))
    rgb[..., 1] = 255.0                      # pure green
    x, y, Z = rd.micro_dem_grid(rgb, z_scale=10.0)
    assert Z.shape == (3, 2)                  # (W,H)
    # green-only is constant -> flat
    assert np.allclose(Z, 0.0)


def test_default_z_scale_scales_with_extent():
    img = np.tile(np.linspace(0, 1, 10), (10, 1))
    _, _, Z = rd.micro_dem_grid(img, extent_mm=[0, 1000, 0, 800])
    # default relief = 0.15 * min(1000, 800) = 120
    assert np.nanmax(Z) == pytest.approx(120.0)


def test_rejects_bad_input():
    with pytest.raises(ValueError):
        rd.micro_dem_grid(np.zeros((2, 2, 2, 2)))
    with pytest.raises(ValueError):
        rd.micro_dem_grid(np.array([]))


# --- real float32 micro-DEM (dem_format mm) --------------------------------

def _grid_obj(heights, dx=2.0, x0=-10.0, y0=-20.0):
    import base64
    a = np.asarray(heights, dtype="<f4")
    return {"format": "float32", "byte_order": "little",
            "shape": list(a.shape), "data_b64": base64.b64encode(a.tobytes()).decode(),
            "dx_mm": dx, "x0_mm": x0, "y0_mm": y0, "units": "mm", "z_is_height": True}


def test_decode_float_grid_roundtrip():
    h = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], dtype=np.float32)  # (2,3)
    heights, dx, x0, y0 = rd.decode_float_grid(_grid_obj(h))
    assert heights.shape == (2, 3)
    assert np.allclose(heights, h)
    assert (dx, x0, y0) == (2.0, -10.0, -20.0)


def test_decode_float_grid_preserves_nan():
    h = np.array([[1.0, np.nan], [3.0, 4.0]], dtype=np.float32)
    heights, *_ = rd.decode_float_grid(_grid_obj(h))
    assert np.isnan(heights[0, 1])


def test_decode_float_grid_bad():
    with pytest.raises(ValueError):
        rd.decode_float_grid({"shape": [2, 2]})           # no data
    with pytest.raises(ValueError):
        rd.decode_float_grid(_grid_obj(np.zeros((2, 3))) | {"shape": [5, 5]})


def test_mesh_from_micro_dem_shapes_and_coords():
    h = np.arange(6, dtype=np.float32).reshape(2, 3)       # rows=2, cols=3
    x, y, Z, valid = rd.mesh_from_micro_dem(_grid_obj(h, dx=2.0, x0=-10, y0=-20))
    assert x.shape == (3,) and y.shape == (2,)             # cols, rows
    assert Z.shape == (3, 2) and valid.shape == (3, 2)     # (cols, rows)
    assert list(x) == [-10.0, -8.0, -6.0]                  # x0 + col*dx
    assert list(y) == [-20.0, -18.0]                       # y0 + row*dx
    assert Z[0, 0] == 0.0 and Z[2, 1] == 5.0               # heights.T


def test_mesh_trim_border_drops_outer_ring():
    h = np.arange(16, dtype=np.float32).reshape(4, 4)       # rows=4, cols=4
    x, y, Z, valid = rd.mesh_from_micro_dem(
        _grid_obj(h, dx=2.0, x0=-10, y0=-20), trim_border=1)
    assert x.shape == (2,) and y.shape == (2,)             # one ring dropped
    assert Z.shape == (2, 2) and valid.shape == (2, 2)
    assert list(x) == [-8.0, -6.0]                         # origin shifted by dx
    assert list(y) == [-18.0, -16.0]
    assert Z[0, 0] == h[1, 1] and Z[1, 1] == h[2, 2]       # interior survives (heights.T)


def test_mesh_trim_border_noop_when_too_small():
    h = np.zeros((2, 2), dtype=np.float32)
    _, _, Z, _ = rd.mesh_from_micro_dem(_grid_obj(h), trim_border=1)
    assert Z.shape == (2, 2)                               # too small -> untouched


def test_colors_trim_border_matches_trimmed_mesh():
    rgb = np.zeros((4, 4, 3), dtype=np.uint8)
    valid = np.ones((2, 2), dtype=bool)                    # trimmed-mesh shape
    colors = rd.colors_from_rgb(rgb, valid, trim_border=1)
    assert colors.shape == (2, 2, 4)                       # aligned with trimmed mesh


def test_mesh_fills_nan_but_reports_validity():
    h = np.array([[1.0, np.nan], [3.0, 4.0]], dtype=np.float32)
    _, _, Z, valid = rd.mesh_from_micro_dem(_grid_obj(h))
    assert not np.isnan(Z).any()                            # filled
    assert valid.sum() == 3                                 # one hole flagged


def test_colors_from_rgb_alignment_and_alpha():
    rgb = np.zeros((2, 3, 3), dtype=np.uint8)               # rows=2, cols=3
    rgb[..., 0] = 255                                        # red
    valid = np.array([[True, True], [True, False], [True, True]])  # (cols,rows)
    colors = rd.colors_from_rgb(rgb, valid)
    assert colors.shape == (3, 2, 4)                        # (cols, rows, 4)
    assert np.allclose(colors[0, 0, :3], [1.0, 0.0, 0.0])   # red, normalised
    assert colors[1, 1, 3] == 0.0                           # invalid -> transparent
    assert colors[0, 0, 3] == 1.0
