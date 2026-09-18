"""Composite per-frame stereo micro-DEMs into one along-track seabed ribbon.

Stateless, no Qt, no QGIS — everything here is a pure function over numpy arrays
so it can be unit-tested without the plugin.  The QGIS-side entry point is a
script (``scripts/build_ribbon.py``), not a dock: see
``docs/photogrammetric_ribbon.md``.

The product
-----------
One HabCam line gives a ~1.2 m wide strip of seabed per frame, overlapping the
next frame by ~35-45 % *along* track and not at all *across* it.  Compositing a
few hundred of those yields a ribbon ~170 m long at millimetre resolution — the
only product that spans the gap between what one frame can measure (3 mm ..
1.2 m) and what the MBES grid resolves (>= 2-3 m).

Why the navigation alone will not place the frames
--------------------------------------------------
The USBL fix is piecewise-constant: the median *per-frame* nav step on the test
line is 91 mm while the imagery shows the vehicle advancing ~510 mm per frame.
Placed by raw nav, consecutive frames stack in clumps of ~6 and then jump.  So
the relative geometry has to come from the pixels where the pixels allow it:

* :func:`link_pair` registers two consecutive left images with ORB + RANSAC and
  **gates the result on physical plausibility** (advance inside a plausible
  band, motion roughly along track, near-unit scale, small rotation).  The gate
  matters: on this imagery RANSAC will happily return a 20-inlier consensus on
  a wrong solution, and an ungated chain inherits it.
* :func:`chain_track` integrates the accepted links into a track, **bridging
  unlinked gaps with the navigation**, and rubber-sheets the result back onto
  the nav over long windows so absolute placement still comes from the USBL.

Texture, not relief, decides whether a line is buildable: on this survey the
strip with the most relief is featureless mud with a ~1 % link rate.
:func:`link_rate` is the screening measurement.

Compositing
-----------
Each frame's micro-DEM arrives on its own grid with a **rotated** affine
geotransform (``E = c + a*col + b*row``), so combining them is a resample, not a
paste: :func:`resample_frame` maps a target north-up UTM grid back through each
frame's inverse affine, and :func:`blend_accumulate` feathers the overlaps by
distance to the frame edge while keeping a per-cell observation count.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

#: Rectified-left focal length in pixels (INTERFACE.md, "Rectified LEFT
#: intrinsics").  Ground sample distance is ``altitude_mm / FOCAL_PX``; the raw
#: left half differs from the rectified left by the rectification homography, so
#: treat this as a starting scale and calibrate it against the nav
#: (:func:`calibrate_scale`) rather than trusting it to better than a few %.
FOCAL_PX = 2480.28

#: Stereo frames are stored side by side, left camera first.
def left_half(image: np.ndarray) -> np.ndarray:
    """The left camera's half of a side-by-side stereo frame.

    The ``*_orig.png`` archive is 2720x1024 with the two cameras side by side;
    the ``imgs_jpg`` delivery the plugin normally shows is exactly this left
    half, unflipped, so image-up means the same thing in both.
    """
    return image[:, : image.shape[1] // 2]


@dataclass(frozen=True)
class LinkParams:
    """Tuning for :func:`link_pair`, with the physical gate it applies.

    The defaults are measured on the 2015 HabCam line: content scrolls **down**
    between consecutive frames (the camera looks forward-down and advances), by
    ~400-650 px at a ground sample distance of ~0.7-1.2 mm/px.

    Attributes
    ----------
    n_features, fast_threshold:
        ORB detector size.  The imagery is dark (mean grey ~21/255) and
        low-contrast, so a low FAST threshold and a large budget are both
        needed; there is no useful preprocessing win here (flat-field and CLAHE
        both *reduced* the inlier count in testing -- they amplify the sensor
        noise the descriptors then lock onto).
    ratio:
        Lowe ratio.  Deliberately loose (0.95).  Seabed texture is repetitive,
        so a strict ratio throws away nearly every true match; the displacement
        prefilter and RANSAC below are what reject the bad ones.
    overlap_frac:
        Detection is masked to the band that can actually overlap -- the top
        ``overlap_frac`` of the earlier frame and the bottom ``overlap_frac`` of
        the later one.  Features outside it are pure distractors.
    dy_min, dy_max:
        Plausible along-track image shift, pixels (content moves +y = down).
    cross_frac, cross_abs:
        Cross-track tolerance: ``|dx| <= cross_frac*|dy| + cross_abs``.
    min_inliers:
        RANSAC inlier count for an accepted link.
    max_rotation_deg, scale_tol:
        The transform must be near-rigid: the seabed is near-planar and the
        altitude changes slowly.
    """

    n_features: int = 8000
    fast_threshold: int = 5
    ratio: float = 0.95
    overlap_frac: float = 0.70
    reproj_threshold: float = 4.0
    dy_min: float = 200.0
    dy_max: float = 900.0
    cross_frac: float = 0.45
    cross_abs: float = 120.0
    min_inliers: int = 15
    max_rotation_deg: float = 15.0
    scale_tol: float = 0.25


DEFAULT_LINK = LinkParams()


@dataclass(frozen=True)
class Link:
    """One consecutive-pair registration result.

    ``tx``/``ty`` are the image-space translation taking frame *i* to frame
    *i+1* (pixels, +y down), ``rotation_deg`` and ``scale`` the rest of the
    similarity.  ``accepted`` is the gate verdict and ``reason`` says which test
    failed, so a rejected link can be reported rather than silently dropped.
    """

    index: int
    n_inliers: int
    tx: float
    ty: float
    rotation_deg: float
    scale: float
    accepted: bool
    reason: str = "ok"


def _masks(shape, overlap_frac):
    """Detection masks for the bands of two frames that can overlap."""
    h, w = shape
    cut = int(round(h * overlap_frac))
    earlier = np.zeros((h, w), np.uint8)
    earlier[:cut] = 255            # content here scrolls down into the next frame
    later = np.zeros((h, w), np.uint8)
    later[h - cut:] = 255
    return earlier, later


def _gate(n_inliers, tx, ty, rot, scale, p: LinkParams):
    """Return ``(accepted, reason)`` for a candidate transform."""
    if n_inliers < p.min_inliers:
        return False, "few_inliers"
    if not (p.dy_min < ty < p.dy_max):
        return False, "advance_out_of_band"
    if abs(tx) > p.cross_frac * abs(ty) + p.cross_abs:
        return False, "cross_track"
    if abs(rot) > p.max_rotation_deg:
        return False, "rotation"
    if abs(scale - 1.0) > p.scale_tol:
        return False, "scale"
    return True, "ok"


def link_pair(earlier: np.ndarray, later: np.ndarray, *, index: int = 0,
              params: LinkParams = DEFAULT_LINK) -> Link:
    """Register two consecutive left images with ORB + RANSAC.

    Returns a :class:`Link` whose ``accepted`` flag is the answer to "is *this*
    pair linked" -- which is why ORB is used rather than the template matching
    that earlier work used for population medians: on the same 150 pairs,
    template NCC called 13 % linked where ORB called 59 %.

    A rejected link is still returned (with ``reason``), so the caller can count
    *why* a line failed instead of just that it did.
    """
    import cv2      # imported lazily: only the ribbon needs OpenCV

    fail = Link(index=index, n_inliers=0, tx=np.nan, ty=np.nan,
                rotation_deg=np.nan, scale=np.nan, accepted=False)
    if earlier is None or later is None or earlier.shape != later.shape:
        return replace(fail, reason="bad_input")

    mask_a, mask_b = _masks(earlier.shape, params.overlap_frac)
    orb = cv2.ORB_create(nfeatures=params.n_features,
                         fastThreshold=params.fast_threshold)
    kp_a, des_a = orb.detectAndCompute(earlier, mask_a)
    kp_b, des_b = orb.detectAndCompute(later, mask_b)
    if des_a is None or des_b is None or len(kp_a) < 8 or len(kp_b) < 8:
        return replace(fail, reason="no_features")

    matches = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(des_a, des_b, k=2)
    good = [m[0] for m in matches
            if len(m) == 2 and m[0].distance < params.ratio * m[1].distance]
    if len(good) < 8:
        return replace(fail, reason="no_matches")

    src = np.float32([kp_a[m.queryIdx].pt for m in good])
    dst = np.float32([kp_b[m.trainIdx].pt for m in good])
    # Prefilter on the physical envelope before RANSAC.  Without this the
    # consensus is routinely found among the (far more numerous) wrong matches.
    delta = dst - src
    keep = ((delta[:, 1] > params.dy_min) & (delta[:, 1] < params.dy_max)
            & (np.abs(delta[:, 0])
               <= params.cross_frac * np.abs(delta[:, 1]) + params.cross_abs))
    if int(keep.sum()) < 8:
        return replace(fail, reason="no_plausible_matches")

    model, inliers = cv2.estimateAffinePartial2D(
        src[keep].reshape(-1, 1, 2), dst[keep].reshape(-1, 1, 2),
        method=cv2.RANSAC, ransacReprojThreshold=params.reproj_threshold,
        maxIters=10000, confidence=0.999)
    if model is None or inliers is None:
        return replace(fail, reason="no_model")

    n = int(inliers.sum())
    scale = float(np.hypot(model[0, 0], model[1, 0]))
    rot = float(np.degrees(np.arctan2(model[1, 0], model[0, 0])))
    tx, ty = float(model[0, 2]), float(model[1, 2])
    accepted, reason = _gate(n, tx, ty, rot, scale, params)
    return Link(index=index, n_inliers=n, tx=tx, ty=ty, rotation_deg=rot,
                scale=scale, accepted=accepted, reason=reason)


def link_rate(links) -> dict:
    """Summarise a sequence of :class:`Link` s: the texture screening number.

    Returns ``{"n_pairs", "n_linked", "link_rate", "median_inliers",
    "median_inliers_linked", "reasons"}``.  ``link_rate`` is the fraction of
    consecutive pairs that registered -- the criterion for choosing a line.
    """
    links = list(links)
    n = len(links)
    if not n:
        return {"n_pairs": 0, "n_linked": 0, "link_rate": float("nan"),
                "median_inliers": float("nan"),
                "median_inliers_linked": float("nan"), "reasons": {}}
    linked = [l for l in links if l.accepted]
    reasons: dict[str, int] = {}
    for l in links:
        if not l.accepted:
            reasons[l.reason] = reasons.get(l.reason, 0) + 1
    return {
        "n_pairs": n,
        "n_linked": len(linked),
        "link_rate": len(linked) / n,
        "median_inliers": float(np.median([l.n_inliers for l in links])),
        "median_inliers_linked": (float(np.median([l.n_inliers for l in linked]))
                                  if linked else float("nan")),
        "reasons": reasons,
    }


# --------------------------------------------------------------------------
# the pose chain: pixels where they work, navigation everywhere else
# --------------------------------------------------------------------------
def gsd_mm_per_px(altitude_mm, focal_px: float = FOCAL_PX):
    """Ground sample distance in mm/px for a nadir-ish frame at *altitude_mm*."""
    return np.asarray(altitude_mm, dtype=float) / float(focal_px)


def link_to_body_motion(link: Link, gsd_mm: float):
    """Platform motion implied by one image-space link, in body axes.

    Returns ``(along_mm, cross_mm, delta_heading_deg)``: ``along`` positive
    forward (along the heading), ``cross`` positive to starboard, and the yaw
    change between the two frames.

    Mount (INTERFACE.md): image bottom->top is the heading and image-right is
    starboard, so image ``+x`` = starboard and image ``+y`` = **astern**.  A
    feature therefore slides *astern* (``+y``) by exactly as far as the platform
    advances, and slides to *port* (``-x``) when the platform moves to
    starboard -- hence the sign flip on ``tx``.  The same convention makes the
    yaw the negative of the image rotation: turning the platform clockwise turns
    the imaged world anticlockwise.
    """
    return (float(link.ty) * gsd_mm, -float(link.tx) * gsd_mm,
            -float(link.rotation_deg))


def body_to_world(along_mm, cross_mm, heading_deg):
    """Body-axis motion (mm) to a world ``(dE, dN)`` offset in metres.

    Heading is degrees clockwise from north, so forward is
    ``(sin h, cos h)`` and starboard ``(cos h, -sin h)``.
    """
    h = np.radians(np.asarray(heading_deg, dtype=float))
    along, cross = np.asarray(along_mm, float) / 1000.0, np.asarray(cross_mm, float) / 1000.0
    return (along * np.sin(h) + cross * np.cos(h),
            along * np.cos(h) - cross * np.sin(h))


def _smooth(x, window):
    """Gaussian low-pass over *window* frames, edges replicated.

    A boxcar would be the obvious choice and is the wrong one here.  The USBL is
    piecewise-constant in clumps of ~6 frames, so the chain-minus-nav residual
    this smooths is a sawtooth of that period with metre-scale amplitude, and a
    moving average only attenuates a period it does not evenly divide by about
    a factor of ten -- enough to put a visible ~7 cm ripple back into the
    per-frame steps the chain exists to clean up.  A Gaussian of
    ``sigma = window/4`` kills it outright.  ``window <= 1`` is the identity.

    Any straight-line trend is removed first and put back afterwards, so a
    smoothed *track* keeps its length.  Without that, the edge padding -- which
    has only the local mean to go on -- pulls the first and last samples toward
    the middle and shortens the track by several percent, which would go
    straight into the scale calibration as if it were a camera property.
    """
    x = np.asarray(x, dtype=float)
    window = int(window)
    if window <= 1 or x.size < 2:
        return x.copy()
    index = np.arange(x.size, dtype=float)
    slope, offset = np.polyfit(index, x, 1)
    trend = slope * index + offset
    x = x - trend
    sigma = window / 4.0
    half = max(int(np.ceil(3.0 * sigma)), 1)
    offsets = np.arange(-half, half + 1, dtype=float)
    kernel = np.exp(-0.5 * (offsets / sigma) ** 2)
    kernel /= kernel.sum()
    # Pad with the local *mean*, not the endpoint sample: the residual being
    # smoothed is a sawtooth, so replicating whichever phase happens to sit at
    # the end biases the first and last half-window by up to its full amplitude.
    edge = min(half, x.size)
    padded = np.concatenate([np.full(half, x[:edge].mean()), x,
                             np.full(half, x[-edge:].mean())])
    return np.convolve(padded, kernel, mode="valid") + trend


def _unwrap_deg(a):
    return np.degrees(np.unwrap(np.radians(np.asarray(a, dtype=float))))


def calibrate_scale(links, nav_e, nav_n, altitude_mm, *, focal_px=FOCAL_PX,
                    window: int = 50):
    """One global correction to :data:`FOCAL_PX`, from the nav's own geometry.

    The archived left half is not the *rectified* left the intrinsics belong to,
    so ``altitude/FOCAL_PX`` is out by a double-digit percentage.  The
    navigation can calibrate it, but only if it is asked the right question:
    summing per-step nav distances would compare against a staircase whose
    individual steps are 13 mm one frame and 3.5 m the next, and the jitter
    inflates that sum.  Instead this compares **end-to-end displacement over
    long windows** -- immune to both the quantization and the jitter, because
    over 50 frames the USBL has had many fixes and its start and end points are
    sound.

    Only windows in which every link was accepted are used, so no nav-bridged
    step can enter the comparison.  Returns ``(focal_px_calibrated, ratio,
    n_windows)``; a ratio far from 1 is a real statement about the imagery, not
    a bug, and is worth reporting.
    """
    links = list(links)
    nav_e = np.asarray(nav_e, dtype=float)
    nav_n = np.asarray(nav_n, dtype=float)
    n = nav_e.size
    accepted = {l.index: l for l in links if l.accepted and 0 <= l.index < n - 1}
    gsd = gsd_mm_per_px(altitude_mm, focal_px)
    # Smooth the nav before measuring displacement.  A window endpoint that
    # lands mid-clump reports the position of the clump's *first* frame, which
    # truncates the window by up to one clump -- a few percent bias, always in
    # the same direction.  Smoothing puts the endpoint back where the vehicle
    # was.
    smooth_e = _smooth(nav_e, max(window // 2, 9))
    smooth_n = _smooth(nav_n, max(window // 2, 9))

    pixel_total = nav_total = 0.0
    windows = 0
    start = 0
    while start + window < n:
        span = range(start, start + window)
        if all(i in accepted for i in span):
            # Accumulate in body axes and take the magnitude at the end: a
            # rotation common to the whole window cancels, so no heading source
            # is needed and none of its error enters the calibration.
            along = cross = 0.0
            for i in span:
                step_along, step_cross, _ = link_to_body_motion(accepted[i],
                                                               float(gsd[i]))
                along += step_along
                cross += step_cross
            pixel_total += float(np.hypot(along, cross)) / 1000.0
            nav_total += float(np.hypot(smooth_e[start + window] - smooth_e[start],
                                        smooth_n[start + window] - smooth_n[start]))
            windows += 1
            start += window
        else:
            start += 1
    if windows == 0 or pixel_total <= 0 or nav_total <= 0:
        return float(focal_px), float("nan"), 0
    ratio = pixel_total / nav_total
    # too long a pixel track means the assumed focal length was too short
    return float(focal_px) * ratio, float(ratio), windows


def chain_track(links, nav_e, nav_n, heading_deg, altitude_mm, *,
                focal_px: float = FOCAL_PX, anchor_window: int = 51,
                use_link_heading: bool = True):
    """Integrate the accepted links into a track, bridging the gaps with nav.

    The ribbon's *absolute* placement must still come from the USBL, so the
    integrated chain is rubber-sheeted back onto the navigation: the chain-minus-
    nav residual is smoothed over ``anchor_window`` frames and added back.  The
    window has to be much longer than the ~6-frame clumps the piecewise-constant
    USBL produces (51 frames is ~26 m here) or the correction would simply
    reinstate the quantization it is there to remove.  Within half a window of
    either end there is not enough data to average those clumps away, so the
    first and last ~25 frames carry a little of the staircase back; on a
    300-frame run that is the edge only, which is another reason a ribbon wants
    a long run.

    Returns a dict of per-frame arrays: ``easting``, ``northing``, ``heading``,
    ``source`` (``"pixel"`` or ``"nav"`` for the step that *reached* this frame;
    frame 0 is ``"nav"``), plus ``focal_px``, ``scale_ratio`` and
    ``n_pixel_steps``.
    """
    nav_e = np.asarray(nav_e, dtype=float)
    nav_n = np.asarray(nav_n, dtype=float)
    heading = _unwrap_deg(heading_deg)
    n = len(nav_e)
    if len(nav_n) != n or len(heading) != n:
        raise ValueError("nav_e, nav_n and heading_deg must be the same length")

    focal_cal, ratio, n_windows = calibrate_scale(links, nav_e, nav_n,
                                                  altitude_mm, focal_px=focal_px)
    gsd = gsd_mm_per_px(altitude_mm, focal_cal)

    by_index = {l.index: l for l in links if l.accepted and 0 <= l.index < n - 1}
    d_e = np.diff(nav_e)
    d_n = np.diff(nav_n)
    d_h = np.diff(heading)
    source = np.array(["nav"] * n, dtype=object)
    for i, link in by_index.items():
        along, cross, dh = link_to_body_motion(link, float(gsd[i]))
        d_e[i], d_n[i] = body_to_world(along, cross, heading[i])
        if use_link_heading:
            d_h[i] = dh
        source[i + 1] = "pixel"

    chain_e = nav_e[0] + np.concatenate([[0.0], np.cumsum(d_e)])
    chain_n = nav_n[0] + np.concatenate([[0.0], np.cumsum(d_n)])
    chain_h = heading[0] + np.concatenate([[0.0], np.cumsum(d_h)])

    # keep the high-frequency geometry from the pixels, the low-frequency
    # placement from the nav
    chain_e += _smooth(nav_e - chain_e, anchor_window)
    chain_n += _smooth(nav_n - chain_n, anchor_window)
    chain_h += _smooth(heading - chain_h, anchor_window)

    return {"easting": chain_e, "northing": chain_n,
            "heading": np.mod(chain_h, 360.0), "source": source,
            "focal_px": focal_cal, "scale_ratio": ratio,
            "scale_windows": int(n_windows),
            "n_pixel_steps": int(len(by_index))}


def step_lengths(easting, northing):
    """Per-step distances along a track (length ``n-1``)."""
    return np.hypot(np.diff(np.asarray(easting, float)),
                    np.diff(np.asarray(northing, float)))


def along_track_distance(easting, northing):
    """Cumulative along-track distance, starting at 0."""
    return np.concatenate([[0.0], np.cumsum(step_lengths(easting, northing))])


# --------------------------------------------------------------------------
# compositing: many rotated frame grids -> one north-up UTM grid
# --------------------------------------------------------------------------
def affine_parts(geotransform):
    """Split a GDAL geotransform into ``(origin(2,), matrix(2,2))``.

    ``E = c + a*col + b*row``, ``N = f + d*col + e*row`` -- so the matrix maps
    ``(col, row)`` to a world offset.  ``b`` and ``d`` are non-zero here: each
    frame is rotated to its own heading, which is why compositing is a resample
    and not a paste.
    """
    c, a, b, f, d, e = (float(v) for v in geotransform)
    return np.array([c, f]), np.array([[a, b], [d, e]])


def frame_corners(geotransform, shape):
    """World coordinates of the four corners of a frame grid ``(rows, cols)``."""
    rows, cols = int(shape[0]), int(shape[1])
    origin, matrix = affine_parts(geotransform)
    grid = np.array([[0, 0], [cols, 0], [0, rows], [cols, rows]], dtype=float)
    return origin + grid @ matrix.T


def grid_matrix(pixel_m, azimuth_deg=None):
    """The 2x2 part of a target geotransform, north-up or turned to an azimuth.

    ``azimuth_deg=None`` gives the usual north-up raster (``+col`` east,
    ``+row`` south).  Otherwise the grid follows the frames' own convention --
    ``-row`` along the azimuth, ``+col`` 90 deg to its right -- which is what
    makes a long diagonal ribbon storable at all: 172 m of track at 3 mm is
    ~57000 x 400 cells track-aligned (2.3e7), but a north-up box round the same
    diagonal is ~41000 x 41000 (1.7e9) -- seventy times the cells for the same
    data.  The ratio is roughly ``L*|sin a cos a| / w``, so it grows with the
    ribbon's length-to-width ratio and is worst on a diagonal line.
    """
    if azimuth_deg is None:
        return np.array([[pixel_m, 0.0], [0.0, -pixel_m]])
    t = np.radians(float(azimuth_deg))
    return np.array([[pixel_m * np.cos(t), -pixel_m * np.sin(t)],
                     [-pixel_m * np.sin(t), -pixel_m * np.cos(t)]])


def track_azimuth(easting, northing):
    """Mean course of a track in degrees clockwise from north (end to end)."""
    e = np.asarray(easting, dtype=float)
    n = np.asarray(northing, dtype=float)
    return float(np.degrees(np.arctan2(e[-1] - e[0], n[-1] - n[0])) % 360.0)


def target_grid(geotransforms, shapes, pixel_m, *, margin_m: float = 0.0,
                azimuth_deg=None):
    """A target grid covering every frame, north-up or aligned to a track.

    Returns ``{"geotransform", "width", "height", "pixel_m", "azimuth_deg"}``.
    Pass ``azimuth_deg`` (see :func:`track_azimuth`) for a long ribbon; leave it
    ``None`` for a compact patch.  Elevation is stored as float32, so at 3 mm a
    172 m x 1.2 m track-aligned ribbon is ~57000 x 400 cells (~92 MB/band) --
    1 mm would be nine times that and is not worth it.
    """
    matrix = grid_matrix(float(pixel_m), azimuth_deg)
    inverse = np.linalg.inv(matrix)
    corners = np.vstack([frame_corners(gt, shape)
                         for gt, shape in zip(geotransforms, shapes)])
    grid = corners @ inverse.T                      # world -> (col, row)
    lo = grid.min(axis=0) - margin_m / float(pixel_m)
    hi = grid.max(axis=0) + margin_m / float(pixel_m)
    width = int(np.ceil(hi[0] - lo[0]))
    height = int(np.ceil(hi[1] - lo[1]))
    origin = matrix @ lo
    return {"geotransform": [origin[0], matrix[0, 0], matrix[0, 1],
                             origin[1], matrix[1, 0], matrix[1, 1]],
            "width": width, "height": height, "pixel_m": float(pixel_m),
            "azimuth_deg": (None if azimuth_deg is None else float(azimuth_deg))}


def frame_window(geotransform, shape, target):
    """Target-grid slice ``(row0, row1, col0, col1)`` a frame can touch."""
    corners = frame_corners(geotransform, shape)
    origin, matrix = affine_parts(target["geotransform"])
    grid = (corners - origin) @ np.linalg.inv(matrix).T
    col0 = max(int(np.floor(grid[:, 0].min())) - 1, 0)
    col1 = min(int(np.ceil(grid[:, 0].max())) + 1, target["width"])
    row0 = max(int(np.floor(grid[:, 1].min())) - 1, 0)
    row1 = min(int(np.ceil(grid[:, 1].max())) + 1, target["height"])
    return row0, row1, col0, col1


def _bilinear_nan(values, col, row, *, min_weight=0.5):
    """NaN-aware bilinear sample of ``values`` at float ``(col, row)``.

    ``scipy.ndimage.map_coordinates`` would smear the no-data NaNs across the
    frame edge; here a NaN simply carries zero weight and the sample is dropped
    when less than ``min_weight`` of the stencil survives.
    """
    values = np.asarray(values, dtype=float)
    rows, cols = values.shape
    c0 = np.floor(col).astype(int)
    r0 = np.floor(row).astype(int)
    fc = col - c0
    fr = row - r0
    out = np.zeros(col.shape, dtype=float)
    wsum = np.zeros(col.shape, dtype=float)
    for dr, dc, w in ((0, 0, (1 - fr) * (1 - fc)), (0, 1, (1 - fr) * fc),
                      (1, 0, fr * (1 - fc)), (1, 1, fr * fc)):
        rr, cc = r0 + dr, c0 + dc
        inside = (rr >= 0) & (rr < rows) & (cc >= 0) & (cc < cols)
        if not inside.any():
            continue
        sample = np.zeros(col.shape, dtype=float)
        sample[inside] = values[rr[inside], cc[inside]]
        finite = inside & np.isfinite(sample)
        weight = np.where(finite, w, 0.0)
        out += weight * np.where(finite, sample, 0.0)
        wsum += weight
    valid = wsum >= min_weight
    with np.errstate(invalid="ignore", divide="ignore"):
        out = np.where(valid, out / np.where(wsum > 0, wsum, 1.0), np.nan)
    return out, valid


def resample_frame(bands, geotransform, target, *, window=None):
    """Resample one frame's grid(s) onto the north-up target grid.

    ``bands`` is a 2-D array or a sequence of 2-D arrays sharing one grid (the
    micro-DEM and its co-registered orthophoto do).  Returns
    ``(window, values, valid)`` where ``window`` is ``(row0, row1, col0, col1)``
    in the target and ``values`` has shape ``(n_bands, h, w)``.
    """
    bands = [np.asarray(bands, dtype=float)] if np.ndim(bands) == 2 else \
        [np.asarray(b, dtype=float) for b in bands]
    shape = bands[0].shape
    if window is None:
        window = frame_window(geotransform, shape, target)
    row0, row1, col0, col1 = window
    if row1 <= row0 or col1 <= col0:
        return window, np.zeros((len(bands), 0, 0)), np.zeros((0, 0), bool)

    target_origin, target_matrix = affine_parts(target["geotransform"])
    col_grid, row_grid = np.meshgrid(np.arange(col0, col1) + 0.5,
                                     np.arange(row0, row1) + 0.5)
    east = target_origin[0] + target_matrix[0, 0] * col_grid + target_matrix[0, 1] * row_grid
    north = target_origin[1] + target_matrix[1, 0] * col_grid + target_matrix[1, 1] * row_grid

    origin, matrix = affine_parts(geotransform)
    inverse = np.linalg.inv(matrix)
    delta = np.stack([east - origin[0], north - origin[1]], axis=-1)
    frame_col = delta[..., 0] * inverse[0, 0] + delta[..., 1] * inverse[0, 1]
    frame_row = delta[..., 0] * inverse[1, 0] + delta[..., 1] * inverse[1, 1]
    # the affine maps cell *corners*; sample at cell centres
    frame_col -= 0.5
    frame_row -= 0.5

    values = np.full((len(bands),) + east.shape, np.nan)
    valid = None
    for i, band in enumerate(bands):
        sample, ok = _bilinear_nan(band, frame_col, frame_row)
        values[i] = sample
        valid = ok if valid is None else (valid & ok)
    return window, values, valid


def feather_weights(valid, *, floor: float = 1e-3):
    """Distance-to-edge blending weights for a frame's valid mask.

    The same feather the service's own mosaic uses: a cell's weight is its
    distance to the nearest invalid cell or frame edge, so the seam between two
    frames falls where both contribute least.
    """
    from scipy import ndimage
    valid = np.asarray(valid, dtype=bool)
    padded = np.zeros((valid.shape[0] + 2, valid.shape[1] + 2), dtype=bool)
    padded[1:-1, 1:-1] = valid
    distance = ndimage.distance_transform_edt(padded)[1:-1, 1:-1]
    return np.where(valid, np.maximum(distance, floor), 0.0)


class RibbonCanvas:
    """Weighted accumulator for the composited ribbon.

    Keeps ``sum(w*v)`` and ``sum(w)`` per band plus a per-cell **observation
    count**, which ships as a QA band: at 35-45 % along-track overlap most cells
    are seen twice, and where the count drops to zero the frame was turbid and
    the service returned ``insufficient_coverage``.
    """

    def __init__(self, target, n_bands: int = 1):
        self.target = target
        shape = (int(target["height"]), int(target["width"]))
        self.n_bands = int(n_bands)
        # float32: a 57000 x 400 canvas with four bands is ~550 MB this way
        # and twice that in float64, for a precision nobody can use
        self.weighted = np.zeros((self.n_bands,) + shape, dtype=np.float32)
        self.weight = np.zeros(shape, dtype=np.float32)
        self.count = np.zeros(shape, dtype=np.int32)

    def add(self, window, values, valid, weights=None):
        """Accumulate one resampled frame into the canvas."""
        row0, row1, col0, col1 = window
        if row1 <= row0 or col1 <= col0 or not np.any(valid):
            return
        if weights is None:
            weights = feather_weights(valid)
        weights = np.where(valid, weights, 0.0)
        for i in range(self.n_bands):
            band = np.where(valid, np.nan_to_num(values[i]), 0.0)
            self.weighted[i, row0:row1, col0:col1] += weights * band
        self.weight[row0:row1, col0:col1] += weights
        self.count[row0:row1, col0:col1] += valid.astype(np.int32)

    def result(self):
        """``(bands, count)`` — the blended mean per band (NaN where unseen)."""
        with np.errstate(invalid="ignore", divide="ignore"):
            out = np.where(self.weight > 0,
                           self.weighted / np.where(self.weight > 0, self.weight, 1.0),
                           np.nan)
        return out, self.count


def overlap_difference(values_a, valid_a, values_b, valid_b):
    """Elevation difference statistics where two resampled frames overlap.

    **This is the honest quality statement for the ribbon**: where the same
    patch of seabed is seen by two frames, the difference between their
    elevations is the registration error, not the seabed.  Returns ``None`` if
    the two do not overlap in at least 100 cells.
    """
    both = np.asarray(valid_a, bool) & np.asarray(valid_b, bool)
    n = int(both.sum())
    if n < 100:
        return None
    diff = np.asarray(values_a, float)[both] - np.asarray(values_b, float)[both]
    diff = diff[np.isfinite(diff)]
    if diff.size < 100:
        return None
    return {"n_cells": int(diff.size), "median": float(np.median(diff)),
            "median_abs": float(np.median(np.abs(diff))),
            "rms": float(np.sqrt(np.mean(diff ** 2))),
            "p95_abs": float(np.percentile(np.abs(diff), 95))}


# --------------------------------------------------------------------------
# the two analyses that justify the product
# --------------------------------------------------------------------------
def bin_along_track(distance, values, bin_m):
    """Average *values* into fixed along-track bins.

    Returns ``(centres, mean, count)`` with NaN where a bin is empty.  Used to
    take the ribbon down to the MBES grid's 1 m so the two are comparable.
    """
    distance = np.asarray(distance, dtype=float)
    values = np.asarray(values, dtype=float)
    finite = np.isfinite(distance) & np.isfinite(values)
    if not finite.any():
        return np.zeros(0), np.zeros(0), np.zeros(0, dtype=int)
    distance, values = distance[finite], values[finite]
    n_bins = max(int(np.ceil((distance.max() - distance.min()) / bin_m)), 1)
    edges = distance.min() + np.arange(n_bins + 1) * bin_m
    index = np.clip(np.digitize(distance, edges) - 1, 0, n_bins - 1)
    total = np.bincount(index, weights=values, minlength=n_bins)
    count = np.bincount(index, minlength=n_bins)
    with np.errstate(invalid="ignore"):
        mean = np.where(count > 0, total / np.where(count > 0, count, 1), np.nan)
    return (edges[:-1] + bin_m / 2.0), mean, count.astype(int)


def compare_profiles(a, b, *, remove_bias: bool = True):
    """Correlation and |difference| between two co-located depth profiles.

    ``remove_bias`` strips a constant offset first -- the comparison of interest
    is of *shape*, since the ribbon's datum and the MBES datum need not agree.
    The baseline this has to be read against is the vehicle's own
    ``-(V_Depth + Altimeter)``, which already matches the MBES to a median
    0.27 m (corr 0.662) over ~78 000 frames.
    """
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    both = np.isfinite(a) & np.isfinite(b)
    n = int(both.sum())
    if n < 3:
        return {"n": n, "corr": float("nan"), "median_abs_dz": float("nan"),
                "rms_dz": float("nan"), "bias": float("nan")}
    x, y = a[both], b[both]
    bias = float(np.median(x - y)) if remove_bias else 0.0
    d = (x - bias) - y
    return {"n": n, "corr": float(np.corrcoef(x, y)[0, 1]),
            "median_abs_dz": float(np.median(np.abs(d))),
            "rms_dz": float(np.sqrt(np.mean(d ** 2))), "bias": bias}


def along_track_spectrum(heights, spacing_m, *, detrend: bool = True,
                         window: bool = True):
    """1-D along-track roughness spectrum ``W1(k)`` of a height profile.

    ``heights`` in metres at uniform ``spacing_m``; returns ``(k, W1)`` with
    ``k`` in **rad/m** and ``W1`` in **m^3**, the one-dimensional companion of
    the service's two-dimensional ``W2`` (m^4) -- same convention family, so
    ``sum(W1) * dk`` over both signs of k recovers the height variance.

    NaNs are dropped by linear interpolation across short gaps; a profile with a
    large no-data fraction should not be spectrally analysed at all, so the
    caller is expected to check the gap fraction first.
    """
    z = np.asarray(heights, dtype=float)
    n = z.size
    if n < 8:
        raise ValueError("need at least 8 samples for a spectrum")
    finite = np.isfinite(z)
    if not finite.all():
        if finite.sum() < 8:
            raise ValueError("too few finite samples")
        idx = np.arange(n)
        z = np.interp(idx, idx[finite], z[finite])
    if detrend:
        idx = np.arange(n, dtype=float)
        slope, offset = np.polyfit(idx, z, 1)
        z = z - (slope * idx + offset)
    if window:
        w = np.hanning(n)
        z = z * w
        correction = float(np.mean(w ** 2))
    else:
        correction = 1.0

    length = n * float(spacing_m)
    spectrum = np.fft.rfft(z) * float(spacing_m)
    k = 2.0 * np.pi * np.fft.rfftfreq(n, d=float(spacing_m))
    w1 = (np.abs(spectrum) ** 2) / (2.0 * np.pi * length * correction)
    return k[1:], w1[1:]          # drop the zero-wavenumber (mean) bin


def band_average(k, w, *, per_decade: int = 24):
    """Average a spectrum into log-spaced bands, with the count per band.

    A raw periodogram is a chi-squared-with-2-degrees-of-freedom estimate: every
    single ordinate has ~100 % relative error.  Over the 1.2-3 m band that
    matters here a 172 m profile holds only ~30 ordinates, so a fit to the raw
    spectrum is dominated by that noise -- in testing it returned exponents
    scattered over more than a unit either side of the planted value.  Averaging
    into log-spaced bands first is what makes the exponent in a narrow band
    estimable at all.

    Returns ``(k_centres, w_mean, counts)``, dropping empty bands.
    """
    k = np.asarray(k, dtype=float)
    w = np.asarray(w, dtype=float)
    use = np.isfinite(k) & np.isfinite(w) & (k > 0) & (w > 0)
    k, w = k[use], w[use]
    if k.size == 0:
        return np.zeros(0), np.zeros(0), np.zeros(0, dtype=int)
    decades = np.log10(k.max() / k.min())
    n_bins = max(int(np.ceil(decades * per_decade)), 1)
    edges = np.logspace(np.log10(k.min()), np.log10(k.max() * 1.0001), n_bins + 1)
    index = np.clip(np.digitize(k, edges) - 1, 0, n_bins - 1)
    counts = np.bincount(index, minlength=n_bins)
    w_sum = np.bincount(index, weights=w, minlength=n_bins)
    k_sum = np.bincount(index, weights=np.log(k), minlength=n_bins)
    keep = counts > 0
    return (np.exp(k_sum[keep] / counts[keep]), w_sum[keep] / counts[keep],
            counts[keep].astype(int))


def power_law_fit(k, w, band):
    """Least-squares ``W = A * k**(-gamma)`` over the wavenumber ``band``.

    Returns ``{"gamma", "amplitude", "r2", "n", "band"}`` -- ``amplitude`` is
    ``W`` at ``k = 1 rad/m``.  Returns ``gamma = nan`` when fewer than 5 points
    fall inside the band.
    """
    k = np.asarray(k, dtype=float)
    w = np.asarray(w, dtype=float)
    lo, hi = float(band[0]), float(band[1])
    use = (k >= lo) & (k <= hi) & np.isfinite(w) & (w > 0)
    if int(use.sum()) < 5:
        return {"gamma": float("nan"), "amplitude": float("nan"),
                "r2": float("nan"), "n": int(use.sum()), "band": (lo, hi)}
    x, y = np.log(k[use]), np.log(w[use])
    slope, intercept = np.polyfit(x, y, 1)
    predicted = slope * x + intercept
    residual = y - predicted
    ss_res = float(np.sum(residual ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    n = int(use.sum())
    # standard error of the slope — without it a fitted exponent over a narrow
    # band is a number with no claim attached
    variance_x = float(np.sum((x - x.mean()) ** 2))
    slope_err = (float(np.sqrt(ss_res / (n - 2) / variance_x))
                 if n > 2 and variance_x > 0 else float("nan"))
    return {"gamma": float(-slope), "gamma_err": slope_err,
            "amplitude": float(np.exp(intercept)),
            "r2": float(1.0 - ss_res / ss_tot) if ss_tot > 0 else float("nan"),
            "n": n, "band": (lo, hi)}


def w1_from_gamma2(k, gamma2, w2, k_ref_rad_per_m: float = 100.0):
    """The 1-D spectrum implied by an isotropic 2-D power law — the bridge.

    The per-frame roughness fit is two-dimensional and isotropic,
    ``W2(K) = w2 * (K/k_ref)**(-gamma2)``, while a ribbon profile measures the
    one-dimensional ``W1(k)``.  Integrating the 2-D spectrum over the
    unmeasured cross-track wavenumber gives

        W1(k) = w2 * k_ref**gamma2 * k**(1-gamma2)
                * sqrt(pi) * Gamma((gamma2-1)/2) / Gamma(gamma2/2)

    so the slopes differ by exactly one (``gamma1 = gamma2 - 1``) and the
    amplitude follows with no free parameter.  **This is what makes task 11
    answerable**: extrapolate the per-frame fit through this identity and see
    whether the ribbon's own spectrum lies on it in the 1.2-3 m band that
    neither the frames nor the MBES can reach.  Valid for ``gamma2 > 1``.
    """
    from math import gamma as gamma_fn
    g = float(gamma2)
    if not np.isfinite(g) or g <= 1.0:
        return np.full(np.shape(k), np.nan)
    factor = np.sqrt(np.pi) * gamma_fn((g - 1.0) / 2.0) / gamma_fn(g / 2.0)
    return (float(w2) * float(k_ref_rad_per_m) ** g
            * np.asarray(k, dtype=float) ** (1.0 - g) * factor)


def wavelength_band_to_k(lambda_min_m, lambda_max_m):
    """``(k_lo, k_hi)`` in rad/m for a wavelength band in metres."""
    return (2.0 * np.pi / float(lambda_max_m), 2.0 * np.pi / float(lambda_min_m))


def rotate_world(d_heading_deg):
    """World-frame rotation matrix for a heading *increase* of *d_heading_deg*.

    Headings are compass bearings, so increasing one turns the platform
    clockwise; in ``(E, N)`` that is ``[[cos, sin], [-sin, cos]]``.
    """
    t = np.radians(float(d_heading_deg))
    return np.array([[np.cos(t), np.sin(t)], [-np.sin(t), np.cos(t)]])


def adjust_geotransform(geotransform, shape, d_east=0.0, d_north=0.0,
                        d_heading_deg=0.0):
    """Re-place a frame's grid by a translation and a rotation about its centre.

    The service builds each frame's geotransform from the ``geo`` it was sent,
    i.e. from the raw navigation.  Rather than sending the corrected track (which
    would tie the response cache to whatever the chain happened to produce that
    day), the cache keeps the nav-built geotransform and the correction is
    applied here: the frame is shifted by ``(d_east, d_north)`` and turned by
    ``d_heading_deg`` **about its own centre**, which is where the nav fix sits.
    """
    origin, matrix = affine_parts(geotransform)
    rows, cols = int(shape[0]), int(shape[1])
    centre = origin + matrix @ np.array([cols / 2.0, rows / 2.0])
    rotation = rotate_world(d_heading_deg)
    new_matrix = rotation @ matrix
    new_centre = centre + np.array([float(d_east), float(d_north)])
    new_origin = new_centre - new_matrix @ np.array([cols / 2.0, rows / 2.0])
    return [new_origin[0], new_matrix[0, 0], new_matrix[0, 1],
            new_origin[1], new_matrix[1, 0], new_matrix[1, 1]]


def heading_from_geotransform(geotransform):
    """The compass heading a frame grid is rotated to, in degrees.

    Image bottom->top is the heading, so the grid's ``-row`` direction is
    forward: ``(-b, -e)`` in world ``(E, N)``.
    """
    _, a, b, _, d, e = (float(v) for v in geotransform)
    return float(np.degrees(np.arctan2(-b, -e)) % 360.0)


def intersect_windows(window_a, window_b):
    """Where two target-grid windows overlap, as slices into each.

    Returns ``(window, slices_a, slices_b)`` -- the shared window and the pair
    of ``(rows, cols)`` slice tuples that cut each frame's own array down to it
    -- or ``None`` when they do not meet.  Used to difference two frames where
    they see the same seabed, which is the seam measurement.
    """
    row0 = max(window_a[0], window_b[0])
    row1 = min(window_a[1], window_b[1])
    col0 = max(window_a[2], window_b[2])
    col1 = min(window_a[3], window_b[3])
    if row1 <= row0 or col1 <= col0:
        return None
    def cut(w):
        return (slice(row0 - w[0], row1 - w[0]), slice(col0 - w[2], col1 - w[2]))
    return (row0, row1, col0, col1), cut(window_a), cut(window_b)


# --------------------------------------------------------------------------
# vertical levelling, and the noise floor it leaves behind
# --------------------------------------------------------------------------
def level_vertically(pairs, n_frames, *, anchor_window: int = 51,
                     iterations: int = 5, huber_k: float = 2.0):
    """Per-frame vertical offsets that make the overlaps agree.

    ``pairs`` is a sequence of ``(i, j, d)``: frame *i* reads ``d`` metres higher
    than frame *j* where they overlap (the **median** difference, so within-frame
    stereo noise is already averaged out of it).  Returns an array of offsets to
    **subtract** from each frame.

    Why this is needed: each frame's heights arrive camera-relative and are
    lifted onto the survey datum with the vehicle's own ``V_Depth``, which on
    this survey is quantized to 10 mm and steps by a standard deviation of
    ~82 mm from frame to frame.  That lands almost exactly on the measured
    per-frame vertical scatter -- the depth sensor, not the stereo, is what makes
    the seams.  The micro-DEMs measure their own relative height far better than
    that wherever they overlap, so the overlaps can supply the high-frequency
    levelling.

    Solved as **iteratively reweighted** least squares on ``o_i - o_j = d_ij``
    with ``sum(o) = 0``.  The reweighting is not optional: a handful of frames
    return a partly wrong micro-DEM and disagree with their neighbours by more
    than a metre, and plain least squares spreads that over the whole chain (it
    produced a 1.2 m 95th-percentile correction on real data, against a 0.1 m
    median).  Huber weights on a robustly scaled residual leave those pairs
    outvoted.  Only
    the **high-frequency** part of the solution is kept: the correction is
    high-passed over ``anchor_window`` frames so the absolute datum still comes
    from the vehicle's depth, exactly as :func:`chain_track` leaves absolute
    position to the navigation.  Without that, a chain of pairwise differences
    is a random walk and the ribbon's far end would drift away in depth.
    """
    n = int(n_frames)
    pairs = [(int(i), int(j), float(d)) for i, j, d in pairs
             if 0 <= int(i) < n and 0 <= int(j) < n and np.isfinite(d)]
    if not pairs:
        return np.zeros(n)
    design = np.zeros((len(pairs) + 1, n))
    observed = np.zeros(len(pairs) + 1)
    for row, (i, j, d) in enumerate(pairs):
        design[row, i] = 1.0
        design[row, j] = -1.0
        observed[row] = d
    design[-1, :] = 1.0          # gauge: the mean offset is zero
    weights = np.ones(len(pairs) + 1)
    offsets = np.zeros(n)
    for _ in range(int(iterations)):
        scaled = design * weights[:, None]
        offsets, *_ = np.linalg.lstsq(scaled, observed * weights, rcond=None)
        residual = design[:-1] @ offsets - observed[:-1]
        spread = np.median(np.abs(residual - np.median(residual))) / 0.6745
        if not np.isfinite(spread) or spread <= 0:
            break
        cut = huber_k * spread
        weights[:-1] = np.minimum(1.0, cut / np.maximum(np.abs(residual), 1e-12))
    # keep the high frequencies, hand the low frequencies back to V_Depth
    return offsets - _smooth(offsets, anchor_window)


def registration_noise_spectrum(sigma_m, spacing_m, k):
    """The along-track spectrum a per-frame vertical placement error produces.

    **Without this the ribbon's spectrum cannot be interpreted.**  Independent
    vertical offsets of standard deviation ``sigma_m``, held constant across each
    frame and changing every ``spacing_m``, are a staircase of random steps whose
    two-sided spectral density is

        W1_noise(k) = sigma^2 * ds / (2*pi) * sinc^2(k*ds/2)

    (it integrates to ``sigma^2``, as it must).  For a 0.49 m frame spacing that
    is essentially flat right across the 1.2-3 m band this product exists to
    measure, so it competes directly with the seabed roughness there.  Compare it
    with the measured spectrum before claiming any excess is the seabed.
    """
    sigma = float(sigma_m)
    spacing = float(spacing_m)
    k = np.asarray(k, dtype=float)
    return (sigma ** 2 * spacing / (2.0 * np.pi)) * np.sinc(k * spacing / (2.0 * np.pi)) ** 2


def sigma_for_noise_floor(target_w1, spacing_m, k):
    """The per-frame vertical accuracy needed to push the noise below *target_w1*.

    Inverts :func:`registration_noise_spectrum`.  Use it to say what a future
    attempt would have to achieve rather than just that this one fell short.
    """
    unit = registration_noise_spectrum(1.0, spacing_m, k)
    unit = np.asarray(unit, dtype=float)
    with np.errstate(invalid="ignore", divide="ignore"):
        return float(np.sqrt(np.min(np.asarray(target_w1, float) / unit)))
