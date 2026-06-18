"""Round-trip tests for gt.glmath project / unproject."""
import numpy as np
import pytest

from groundtruther.gt.glmath import (
    project, unproject, perspective, project_points, pick_nearest,
)


def _look_at(eye, target, up):
    eye, target, up = map(lambda a: np.asarray(a, float), (eye, target, up))
    f = target - eye; f /= np.linalg.norm(f)
    s = np.cross(f, up); s /= np.linalg.norm(s)
    u = np.cross(s, f)
    m = np.eye(4)
    m[0, :3], m[1, :3], m[2, :3] = s, u, -f
    m[:3, 3] = -m[:3, :3] @ eye
    return m


def test_project_unproject_roundtrip():
    proj = perspective(45.0, 16 / 9, 1.0, 1000.0)
    view = _look_at([0, -50, 30], [0, 0, 0], [0, 0, 1])
    mvp = proj @ view
    inv = np.linalg.inv(mvp)
    viewport = (0, 0, 1280, 720)

    for world in ([0, 0, 0], [10, -5, 3], [-20, 15, -8], [4.2, 4.2, 4.2]):
        win = project(world, mvp, viewport)
        assert win is not None
        wx, wy, depth = win
        assert 0.0 <= depth <= 1.0
        back = unproject(wx, wy, depth, inv, viewport)
        assert back is not None
        assert np.allclose(back, world, atol=1e-4), (world, back)


def test_unproject_at_pixel_centre():
    proj = perspective(60.0, 1.0, 0.5, 500.0)
    view = _look_at([0, -30, 0], [0, 0, 0], [0, 0, 1])
    mvp = proj @ view
    inv = np.linalg.inv(mvp)
    viewport = (0, 0, 800, 800)
    # the look-at target projects to the viewport centre
    win = project([0, 0, 0], mvp, viewport)
    assert win is not None
    assert abs(win[0] - 400) < 1e-6 and abs(win[1] - 400) < 1e-6


def test_pick_nearest_hits_the_pointed_vertex():
    proj = perspective(45.0, 1.0, 1.0, 1000.0)
    view = _look_at([0, -60, 40], [0, 0, 0], [0, 0, 1])
    mvp = proj @ view
    viewport = (0, 0, 800, 800)
    # a small grid of world vertices
    gx, gy = np.meshgrid(np.linspace(-20, 20, 11), np.linspace(-20, 20, 11))
    gz = np.zeros_like(gx)
    pts = np.stack([gx.ravel(), gy.ravel(), gz.ravel()], axis=1)
    target = 57                         # arbitrary vertex
    sxy = project(pts[target], mvp, viewport)[:2]
    idx = pick_nearest(sxy, pts, mvp, viewport, max_dist=10)
    assert idx == target


def test_pick_nearest_misses_when_far():
    proj = perspective(45.0, 1.0, 1.0, 1000.0)
    view = _look_at([0, -60, 40], [0, 0, 0], [0, 0, 1])
    mvp = proj @ view
    pts = np.array([[0.0, 0.0, 0.0]])
    # pointer far from the single vertex's projection -> None
    assert pick_nearest((5, 5), pts, mvp, (0, 0, 800, 800), max_dist=3) is None


def test_degenerate_returns_none():
    bad = np.zeros((4, 4))
    assert project([1, 2, 3], bad, (0, 0, 10, 10)) is None
    assert unproject(5, 5, 0.5, bad, (0, 0, 10, 10)) is None
