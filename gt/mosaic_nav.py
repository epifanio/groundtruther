"""Build the explicit per-frame navigation a mode-B mosaic request carries.

The mosaic service offers two ways to place frames:

* **mode A** — give it a ``reference_key`` and a window; it pulls the navigation
  itself and anchors the whole mosaic on **that one frame's raw USBL fix**.
* **mode B** — give it the frames *with* their positions; GroundTruther decides
  where each one goes.

Mode A is simpler, and it is what the panel used to send.  The problem is the
anchor.  HabCam's USBL is piecewise-constant: it holds a value across roughly six
frames and then jumps, so the raw fix for any single frame sits somewhere on a
staircase.  Measured over the 296 frames of the reference strip, a raw fix is a
**median 0.78 m** (max 2.83 m) away from its own smoothed track — and a mosaic
anchored on it inherits that error wholesale.

That is what makes a mosaic and a
:mod:`photogrammetric ribbon <groundtruther.gt.ribbon>` of the same stretch fail
to sit on top of each other: the ribbon rubber-sheets the same USBL over a
51-frame window, so the staircase is averaged out of its placement.  Comparing
the two over that strip:

=====================================  ===============  =======
anchor                                 median vs ribbon p90
=====================================  ===============  =======
raw fix (mode A)                       0.72 m           1.52 m
smoothed over 21 frames                0.29 m           0.70 m
**smoothed over 51 frames**            **0.10 m**       0.47 m
=====================================  ===============  =======

So smoothing the anchor closes ~86 % of the disagreement, with no image matching
at all — the remaining 10 cm is the pixel chain, which a mosaic has no way to
reproduce and does not need to.

This module is deliberately Qt-free and side-effect-free so the geometry can be
unit-tested without QGIS or the network.
"""
from __future__ import annotations

import numpy as np

from groundtruther.gt import ribbon
from groundtruther.gt import roughness_geo

#: Frames used by the anchor smoother.  51 is the ribbon's window, and the
#: measurement above shows the gain has flattened by then.
DEFAULT_SMOOTH_FRAMES = 51

#: Extra frames pulled in on each side so the smoother has data beyond the
#: mosaic itself; without it the smoothed anchor bends toward the raw fixes at
#: the window edges, which is exactly where we least want it to.
DEFAULT_PAD_FRAMES = 60


class MosaicNavError(RuntimeError):
    """Raised when the metadata cannot supply a usable mode-B frame list."""


def _altitude_m(df, index, cols):
    """Altimeter reading in metres, or ``None``. Sets the flat-mode scale."""
    for col in ("Altimeter", "altitude_m", "altitude"):
        if col not in cols:
            continue
        try:
            value = float(np.asarray(df[col])[index])
        except (TypeError, ValueError, IndexError):
            continue
        if not np.isfinite(value):
            continue
        # The column is millimetres on this dataset; metres elsewhere. The
        # vehicle flies 1-3 m off the bottom, so anything past 100 is mm.
        return value / 1000.0 if value > 100.0 else value
    return None


def smoothed_frames(df, centre_index: int, window: int, *,
                    smooth_frames: int = DEFAULT_SMOOTH_FRAMES,
                    pad_frames: int = DEFAULT_PAD_FRAMES,
                    name_col: str = "Imagename") -> list[dict]:
    """Per-frame nav for the ±*window* frames around *centre_index*, smoothed.

    Returns the ``frames`` list of a mode-B mosaic request: one dict per frame
    with ``frame_key``, ``easting``, ``northing``, ``heading_deg`` and (when the
    metadata carries an altimeter) ``altitude_m``.

    Positions are the **calibrated USBL fix** (``Xutm + dx`` / ``Yutm + dy``),
    smoothed over *smooth_frames* with the ribbon's trend-preserving filter so a
    straight run is not shortened.  Headings come from
    :func:`~groundtruther.gt.roughness_geo.platform_heading_from_record`, which
    knows that ``bearing`` points astern — the mistake behind issue #31.

    The smoother reads *pad_frames* beyond the window on each side where the
    table allows; near the ends of a survey it simply uses what there is.

    Raises :class:`MosaicNavError` if the table has no position columns, no name
    column, or the window lands entirely outside it.
    """
    cols = list(getattr(df, "columns", []))
    if name_col not in cols:
        raise MosaicNavError(f"metadata has no {name_col!r} column")

    easting, northing = roughness_geo.usbl_xy(df)
    if easting is None or northing is None:
        raise MosaicNavError(
            "metadata has no USBL position columns (Xutm/Yutm) — "
            "cannot supply explicit frame navigation")

    n_rows = len(easting)
    window = max(0, int(window))
    lo = int(centre_index) - window
    hi = int(centre_index) + window
    if hi < 0 or lo >= n_rows:
        raise MosaicNavError("the mosaic window lies outside the metadata table")
    lo, hi = max(0, lo), min(n_rows - 1, hi)

    pad_lo = max(0, lo - int(pad_frames))
    pad_hi = min(n_rows - 1, hi + int(pad_frames))
    span = slice(pad_lo, pad_hi + 1)

    # Smooth over the padded span, then take only the window out of the middle.
    width = min(int(smooth_frames), pad_hi - pad_lo + 1)
    if width >= 3:
        smooth_e = ribbon._smooth(easting[span], width)
        smooth_n = ribbon._smooth(northing[span], width)
    else:                       # too few rows to smooth; fall back to raw
        smooth_e, smooth_n = easting[span], northing[span]

    names = np.asarray(df[name_col])
    frames: list[dict] = []
    for index in range(lo, hi + 1):
        key = names[index]
        if key is None or str(key).strip() == "":
            continue
        k = index - pad_lo
        e, n = float(smooth_e[k]), float(smooth_n[k])
        if not (np.isfinite(e) and np.isfinite(n)):
            continue
        try:
            record = df.iloc[index]
        except Exception:                       # noqa: BLE001 - not a DataFrame
            record = {c: np.asarray(df[c])[index] for c in cols}
        heading = roughness_geo.platform_heading_from_record(record)
        if heading is None:
            continue                            # no heading -> cannot place it
        frame = {"frame_key": str(key), "easting": e, "northing": n,
                 "heading_deg": float(heading), "layback_m": 0}
        altitude = _altitude_m(df, index, cols)
        if altitude is not None:
            frame["altitude_m"] = altitude
        frames.append(frame)

    if not frames:
        raise MosaicNavError(
            "no frame in the window has both a position and a heading")
    return frames


def anchor_offset_m(df, centre_index: int, *,
                    smooth_frames: int = DEFAULT_SMOOTH_FRAMES,
                    pad_frames: int = DEFAULT_PAD_FRAMES) -> float | None:
    """How far the raw fix at *centre_index* sits from the smoothed track, in m.

    This is the error a mode-A mosaic would inherit in its absolute placement, so
    it is worth showing: a large value means the anchor frame happens to sit on a
    USBL step, not that anything is broken.
    """
    easting, northing = roughness_geo.usbl_xy(df)
    if easting is None or northing is None:
        return None
    n_rows = len(easting)
    if not (0 <= int(centre_index) < n_rows):
        return None
    lo = max(0, int(centre_index) - int(pad_frames))
    hi = min(n_rows - 1, int(centre_index) + int(pad_frames))
    width = min(int(smooth_frames), hi - lo + 1)
    if width < 3:
        return None
    span = slice(lo, hi + 1)
    smooth_e = ribbon._smooth(easting[span], width)
    smooth_n = ribbon._smooth(northing[span], width)
    k = int(centre_index) - lo
    offset = float(np.hypot(easting[centre_index] - smooth_e[k],
                            northing[centre_index] - smooth_n[k]))
    return offset if np.isfinite(offset) else None
