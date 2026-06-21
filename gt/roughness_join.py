"""Join per-frame roughness onto backscatter (BS) samples — stateless.

The plugin already builds a KD-tree over HabCam image ``(lon, lat)`` in
:mod:`groundtruther.gt.image_manager`.  Given a set of BS samples (from the
pdal-mbio Parquet) and the image metadata, this module finds, for each sample,
the nearest image frame and attaches that frame's computed roughness
(``gamma2``, ``w2``, ``rms_height_mm``, ``quality``) when available.

The attachment is a *spatial placement*, not a co-located measurement: the
HabCam tow body trails the ship by a ~1 m layback, so the positional
uncertainty (a few metres) lands on the placement — captured as a per-row note
column — never on the roughness *value* itself.

Pure numpy/pandas/scipy; no Qt, no QGIS — unit-testable in isolation.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import spatial

from groundtruther.gt import image_manager as img_mgr

#: Roughness fields copied onto each BS sample (subset of the response contract).
ROUGHNESS_FIELDS = ("gamma2", "w2", "rms_height_mm", "quality")

#: Per-row provenance note: the placement carries the layback uncertainty, the
#: roughness value does not.
PLACEMENT_NOTE = (
    "roughness from nearest HabCam frame; placement ±~1 m (tow-body layback), "
    "value not re-measured at the BS sample"
)


def frame_key_variants(name) -> list[str]:
    """Return candidate roughness-cache keys for an image name.

    HabCam image names look like ``"201503.20150619.181140656.204627"``; the
    roughness cache may be keyed by the full id or just the trailing numeric
    token (``"204627"``).  Try the full string first, then the last token.
    """
    s = str(name)
    variants = [s]
    if "." in s:
        tail = s.rsplit(".", 1)[-1]
        if tail and tail != s:
            variants.append(tail)
    return variants


def lookup_roughness(roughness_by_frame: dict, name) -> dict | None:
    """Look up *name* in *roughness_by_frame*, trying key variants."""
    if not roughness_by_frame:
        return None
    for key in frame_key_variants(name):
        if key in roughness_by_frame:
            return roughness_by_frame[key]
    return None


def join_roughness_to_samples(
        samples: pd.DataFrame,
        image_df: pd.DataFrame,
        roughness_by_frame: dict,
        *,
        kdt: spatial.KDTree | None = None,
        sample_lon_col: str = "lon",
        sample_lat_col: str = "lat",
        image_lon_col: str = "habcam_lon",
        image_lat_col: str = "habcam_lat",
        frame_key_col: str = "Imagename",
        fields: tuple[str, ...] = ROUGHNESS_FIELDS,
        max_distance: float | None = None,
) -> pd.DataFrame:
    """Attach nearest-frame roughness to each BS sample.

    Parameters
    ----------
    samples:
        BS-sample DataFrame with ``sample_lon_col`` / ``sample_lat_col`` columns
        (same coordinate space as the image lon/lat — typically WGS-84).
    image_df:
        Image-metadata DataFrame (must have ``frame_key_col`` plus the image
        lon/lat columns).
    roughness_by_frame:
        Mapping of frame_key → roughness dict (the cached client responses).
        Frames absent from the map get null roughness columns.
    kdt:
        Pre-built KD-tree over the image lon/lat (e.g. from
        :func:`image_manager.build_kdtree`).  Built on demand if ``None``.
    max_distance:
        Optional cap (in the lon/lat units) beyond which the nearest frame is
        considered too far and no roughness is attached (note still records the
        distance).  ``None`` = no cap.

    Returns
    -------
    A copy of *samples* with added columns: ``rough_frame`` (the matched image
    name), ``rough_dist`` (distance to it), one column per entry in *fields*,
    and ``rough_placement_note``.  Roughness columns are ``None`` where no frame
    matched, was out of range, or had no computed roughness.
    """
    out = samples.copy()

    new_cols: dict[str, list] = {"rough_frame": [], "rough_dist": []}
    for f in fields:
        new_cols[f] = []
    new_cols["rough_placement_note"] = []

    if len(out) == 0 or len(image_df) == 0:
        for col, vals in new_cols.items():
            out[col] = pd.Series(vals, dtype="object")
        return out

    if kdt is None:
        kdt = img_mgr.build_kdtree(image_df, lon_col=image_lon_col,
                                   lat_col=image_lat_col)

    names = image_df[frame_key_col].values
    query = out[[sample_lon_col, sample_lat_col]].values
    dists, idxs = kdt.query(query)
    dists = np.atleast_1d(dists)
    idxs = np.atleast_1d(idxs)

    for dist, idx in zip(dists, idxs):
        frame = names[int(idx)]
        dist = float(dist)
        in_range = max_distance is None or dist <= max_distance
        rough = lookup_roughness(roughness_by_frame, frame) if in_range else None

        new_cols["rough_frame"].append(str(frame))
        new_cols["rough_dist"].append(dist)
        for f in fields:
            new_cols[f].append(rough.get(f) if rough else None)
        if not in_range:
            new_cols["rough_placement_note"].append(
                f"nearest frame {dist:.1f} > max_distance {max_distance}; "
                "no roughness attached")
        elif rough is None:
            new_cols["rough_placement_note"].append("no roughness computed for frame")
        else:
            new_cols["rough_placement_note"].append(PLACEMENT_NOTE)

    for col, vals in new_cols.items():
        out[col] = vals
    return out
