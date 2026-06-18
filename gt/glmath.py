"""Pure GL projection / unprojection helpers (no Qt, no OpenGL).

Used by the Reference 3-D viewer to turn a mouse pixel + depth-buffer value into
a world coordinate (for cursor read-out, picking and measuring). Kept here so the
maths can be unit-tested independently of an OpenGL context.

Conventions (OpenGL):
* matrices are 4x4 numpy arrays in standard math order, i.e. ``clip = M @ v``
  with column vectors;
* ``mvp = projection @ view``;
* ``viewport = (x, y, w, h)`` in device pixels, origin **bottom-left**;
* window depth is in ``[0, 1]`` (as read from the depth buffer).
"""
from __future__ import annotations

import numpy as np


def project(world_xyz, mvp, viewport):
    """World coordinate -> ``(win_x, win_y, depth)`` (origin bottom-left).

    Returns ``None`` when the point is degenerate (w == 0).
    """
    vx, vy, vw, vh = viewport
    v = np.asarray([world_xyz[0], world_xyz[1], world_xyz[2], 1.0], dtype=float)
    clip = np.asarray(mvp, dtype=float) @ v
    if clip[3] == 0:
        return None
    ndc = clip[:3] / clip[3]
    win_x = vx + (ndc[0] + 1.0) * 0.5 * vw
    win_y = vy + (ndc[1] + 1.0) * 0.5 * vh
    depth = (ndc[2] + 1.0) * 0.5
    return win_x, win_y, depth


def unproject(win_x, win_y, depth, inv_mvp, viewport):
    """``(win_x, win_y, depth)`` -> world ``(x, y, z)`` given ``inverse(mvp)``.

    *depth* is the value sampled from the depth buffer (``[0, 1]``); window
    coordinates use the OpenGL bottom-left origin. Returns ``None`` if degenerate.
    """
    vx, vy, vw, vh = viewport
    ndc = np.asarray([
        2.0 * (win_x - vx) / vw - 1.0,
        2.0 * (win_y - vy) / vh - 1.0,
        2.0 * depth - 1.0,
        1.0,
    ], dtype=float)
    world = np.asarray(inv_mvp, dtype=float) @ ndc
    if world[3] == 0:
        return None
    return (world[0] / world[3], world[1] / world[3], world[2] / world[3])


def project_points(world_pts, mvp, viewport):
    """Project ``world_pts`` (N×3) to screen. Returns ``(screen_xy (N×2), in_front)``.

    Window coords use the OpenGL bottom-left origin. ``in_front`` is a boolean
    mask of points with positive clip-w (in front of the camera).
    """
    pts = np.asarray(world_pts, dtype=float)
    n = len(pts)
    homog = np.concatenate([pts, np.ones((n, 1))], axis=1)
    clip = homog @ np.asarray(mvp, dtype=float).T
    w = clip[:, 3]
    in_front = w > 0
    w_safe = np.where(in_front, w, 1.0)
    ndc = clip[:, :3] / w_safe[:, None]
    vx, vy, vw, vh = viewport
    sx = vx + (ndc[:, 0] + 1.0) * 0.5 * vw
    sy = vy + (ndc[:, 1] + 1.0) * 0.5 * vh
    return np.stack([sx, sy], axis=1), in_front


def pick_nearest(mouse_xy, world_pts, mvp, viewport, max_dist):
    """Index of the on-screen-nearest *in-front* vertex to ``mouse_xy``.

    Returns ``None`` if the nearest vertex is farther than ``max_dist`` pixels
    (pointer not over the surface). Avoids the depth buffer entirely, so it works
    with QOpenGLWidget's offscreen FBO.
    """
    screen, in_front = project_points(world_pts, mvp, viewport)
    d2 = (screen[:, 0] - mouse_xy[0]) ** 2 + (screen[:, 1] - mouse_xy[1]) ** 2
    d2 = np.where(in_front, d2, np.inf)
    idx = int(np.argmin(d2))
    if not np.isfinite(d2[idx]) or d2[idx] > max_dist * max_dist:
        return None
    return idx


def perspective(fovy_deg, aspect, near, far):
    """A standard OpenGL perspective matrix (for tests / reference)."""
    f = 1.0 / np.tan(np.radians(fovy_deg) / 2.0)
    m = np.zeros((4, 4))
    m[0, 0] = f / aspect
    m[1, 1] = f
    m[2, 2] = (far + near) / (near - far)
    m[2, 3] = (2 * far * near) / (near - far)
    m[3, 2] = -1.0
    return m
