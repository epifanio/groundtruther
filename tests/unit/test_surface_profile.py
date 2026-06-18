"""Tests for gt.surface_profile (draped profile sampling)."""
import numpy as np

from groundtruther.gt.surface_profile import bilinear_z, sample_profile


def _grid(fn, n=21, lo=0.0, hi=100.0):
    x = np.linspace(lo, hi, n)
    y = np.linspace(lo, hi, n)
    Z = np.array([[fn(xi, yj) for yj in y] for xi in x])   # Z[i, j]
    return x, y, Z


def test_bilinear_on_tilted_plane_is_exact():
    x, y, Z = _grid(lambda X, Y: 2.0 * X - 3.0 * Y + 5.0)
    for px, py in [(10.0, 20.0), (33.3, 71.1), (0.0, 100.0)]:
        assert abs(bilinear_z(x, y, Z, px, py) - (2 * px - 3 * py + 5)) < 1e-6


def test_profile_on_plane_equals_straight_3d():
    # On a flat (tilted) plane the draped profile is straight: surface_len == chord
    x, y, Z = _grid(lambda X, Y: 0.5 * X + 0.2 * Y)
    a = (10.0, 10.0, 0)
    b = (80.0, 60.0, 0)
    pts, surf, plan = sample_profile(x, y, Z, a, b)
    za = 0.5 * 10 + 0.2 * 10
    zb = 0.5 * 80 + 0.2 * 60
    chord = np.sqrt((80 - 10) ** 2 + (60 - 10) ** 2 + (zb - za) ** 2)
    assert abs(surf - chord) < 1e-3
    assert abs(plan - np.hypot(70, 50)) < 1e-6
    assert pts.shape[1] == 3


def test_profile_over_bump_is_longer_than_plan():
    # A Gaussian bump -> draped length exceeds the horizontal (plan) length
    x, y, Z = _grid(lambda X, Y: 30.0 * np.exp(-(((X - 50) ** 2 + (Y - 50) ** 2) / 200.0)))
    pts, surf, plan = sample_profile(x, y, Z, (20, 50), (80, 50))
    assert plan == 60.0
    assert surf > plan * 1.1            # noticeably longer over the bump


def test_endpoints_match_requested_xy():
    x, y, Z = _grid(lambda X, Y: X - Y)
    pts, _, _ = sample_profile(x, y, Z, (12, 34), (56, 78))
    assert np.allclose(pts[0, :2], [12, 34])
    assert np.allclose(pts[-1, :2], [56, 78])
