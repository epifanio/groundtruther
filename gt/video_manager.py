"""Stateless video-metadata and annotation helpers for the GroundTruther plugin.

All functions are pure: they take plain Python/numpy/pandas objects and return
plain objects.  No Qt, no QGIS, no plugin state — callers handle UI feedback.

Generic Video Metadata CSV schema (normalised output)
------------------------------------------------------
frame_index : int
    Sequence number from the source file (``Videoseqence`` column).
timestamp : datetime
    Combined Date + Time parsed to a ``pandas.Timestamp``.
latitude, longitude : float
    WGS-84 decimal degrees (converted from DDM on load).
depth : float
    Water depth in metres.
altitude : float
    Platform altitude above seabed (``CP_MeanAlt``).
bottom : str
    Bottom-type description.
biology : str
    Biology observation notes.
comments : str
    Free-form comments.
cruise, superstation, station : str / int
    Survey identifiers.

Survey CSV schema (raw input from instrument)
---------------------------------------------
The ``load_video_metadata_survey()`` function accepts the cruise-survey format::

    Cruise, Superstation, Station, Videoseqence, Date, Time,
    LatDeg, LatMin, NorthSouth, LonDeg, LonMin, EastWest,
    Depth, Bottom, Biology, Comments,
    CP_LatDeg, CP_LatMin, CP_NorthSouth,
    CP_LonDeg, CP_LonMin, CP_EastWest,
    CP_Altitude, CP_Depth, CP_MeanAlt

Lat/lon are given in degrees + decimal minutes (DDM) with N/S and E/W
hemisphere codes.  They are converted to signed decimal degrees on load.

Video Annotation CSV schema
---------------------------
frame_index : int
    Must match a ``frame_index`` in the metadata CSV.
bboxes : str
    JSON-encoded list of ``[x0, y0, x1, y1]`` pixel bounding boxes,
    e.g. ``"[[10,20,100,80],[200,150,320,280]]"``.
species : str
    JSON-encoded list of species label strings (same length as *bboxes*),
    e.g. ``"[\\"Porifera\\",\\"Echinodermata\\"]"``.
confidences : str
    JSON-encoded list of float confidence scores (same length as *bboxes*),
    e.g. ``"[0.95,0.87]"``.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import spatial


# ---------------------------------------------------------------------------
# Metadata helpers
# ---------------------------------------------------------------------------

def load_video_metadata(csv_path: str | Path) -> pd.DataFrame:
    """Read the video metadata CSV and return a DataFrame.

    The CSV must contain at least the columns ``frame_index``, ``latitude``,
    and ``longitude``.  All other columns are optional.

    Raises ``FileNotFoundError`` if the file does not exist and ``Exception``
    (from pandas) if the file cannot be parsed — callers should catch these.
    """
    df = pd.read_csv(csv_path)
    # Ensure frame_index is the index for fast look-up
    if "frame_index" in df.columns:
        df = df.set_index("frame_index", drop=False)
    return df


def _ddm_to_decimal(degrees: float, minutes: float, hemisphere: str) -> float:
    """Convert degrees + decimal minutes (DDM) to signed decimal degrees.

    Parameters
    ----------
    degrees:
        Integer degree part (e.g. 74 for 74° N).
    minutes:
        Decimal minutes part (e.g. 41.8144).
    hemisphere:
        ``'N'`` / ``'S'`` for latitude; ``'E'`` / ``'W'`` for longitude.
        Whitespace is stripped before comparison.
    """
    dd = float(degrees) + float(minutes) / 60.0
    if hemisphere.strip().upper() in ("S", "W"):
        dd = -dd
    return dd


def load_video_metadata_survey(csv_path: str | Path) -> pd.DataFrame:
    """Parse a cruise-survey video metadata CSV and return a normalised DataFrame.

    The function handles the instrument-export format where lat/lon are stored
    as degrees + decimal minutes with N/S/E/W hemisphere codes.  All column
    names are stripped of surrounding whitespace on read (the instrument
    software sometimes pads them).

    Parameters
    ----------
    csv_path:
        Path to the survey CSV file.

    Returns
    -------
    A DataFrame with columns:

    ``frame_index``, ``timestamp``, ``latitude``, ``longitude``,
    ``depth``, ``altitude``, ``bottom``, ``biology``, ``comments``,
    ``cruise``, ``superstation``, ``station``,
    ``cp_latitude``, ``cp_longitude``, ``cp_altitude``, ``cp_depth``,
    ``cp_mean_alt``

    The DataFrame index is set to ``frame_index`` for fast look-up.

    Raises ``FileNotFoundError`` / ``Exception`` on I/O or parse failures.
    """
    df_raw = pd.read_csv(csv_path)
    # Strip whitespace from column names (instrument CSV often pads them)
    df_raw.columns = df_raw.columns.str.strip()

    def _col(name: str) -> pd.Series:
        """Return column, stripping string values; return NaN series if absent."""
        if name not in df_raw.columns:
            return pd.Series([None] * len(df_raw))
        s = df_raw[name]
        if s.dtype == object:
            s = s.str.strip()
        return s

    # --- Lat / Lon (DDM → decimal degrees) ---
    latitude = [
        _ddm_to_decimal(lat_d, lat_m, ns)
        for lat_d, lat_m, ns in zip(
            _col("LatDeg"), _col("LatMin"), _col("NorthSouth"))
    ]
    longitude = [
        _ddm_to_decimal(lon_d, lon_m, ew)
        for lon_d, lon_m, ew in zip(
            _col("LonDeg"), _col("LonMin"), _col("EastWest"))
    ]

    cp_latitude = [
        _ddm_to_decimal(lat_d, lat_m, ns)
        for lat_d, lat_m, ns in zip(
            _col("CP_LatDeg"), _col("CP_LatMin"), _col("CP_NorthSouth"))
    ]
    cp_longitude = [
        _ddm_to_decimal(lon_d, lon_m, ew)
        for lon_d, lon_m, ew in zip(
            _col("CP_LonDeg"), _col("CP_LonMin"), _col("CP_EastWest"))
    ]

    # --- Timestamp ---
    date_col = _col("Date")
    time_col = _col("Time")
    timestamps = pd.to_datetime(
        date_col.astype(str) + " " + time_col.astype(str),
        format="%d.%m.%Y %H:%M:%S",
        errors="coerce",
    )

    out = pd.DataFrame({
        "frame_index":  _col("Videoseqence").astype(int),
        "timestamp":    timestamps,
        "latitude":     latitude,
        "longitude":    longitude,
        "depth":        pd.to_numeric(_col("Depth"), errors="coerce"),
        "bottom":       _col("Bottom").fillna(""),
        "biology":      _col("Biology").fillna(""),
        "comments":     _col("Comments").fillna(""),
        "cruise":       _col("Cruise"),
        "superstation": _col("Superstation"),
        "station":      _col("Station"),
        "cp_latitude":  cp_latitude,
        "cp_longitude": cp_longitude,
        "cp_altitude":  pd.to_numeric(_col("CP_Altitude"), errors="coerce"),
        "cp_depth":     pd.to_numeric(_col("CP_Depth"), errors="coerce"),
        "cp_mean_alt":  pd.to_numeric(_col("CP_MeanAlt"), errors="coerce"),
    })
    out = out.set_index("frame_index", drop=False)
    return out


def compute_frame_indices(df: pd.DataFrame, fps: float) -> pd.DataFrame:
    """Add a ``video_frame`` column by computing elapsed time from the first row.

    This is needed when the ``frame_index`` (Videoseqence) is a 1-based
    sequence counter rather than an actual video-frame number.  The function
    estimates the video frame number from elapsed seconds × FPS.

    Parameters
    ----------
    df:
        Normalised metadata DataFrame (must contain a ``timestamp`` column).
    fps:
        Frames per second of the associated video file.

    Returns
    -------
    The same DataFrame with a new ``video_frame`` column (int).
    """
    df = df.copy()
    t0 = df["timestamp"].iloc[0]
    elapsed = (df["timestamp"] - t0).dt.total_seconds()
    df["video_frame"] = (elapsed * fps).round().astype(int)
    return df


def build_kdtree(df: pd.DataFrame,
                 lon_col: str = "longitude",
                 lat_col: str = "latitude") -> spatial.KDTree:
    """Build a 2-D KDTree over the (lon, lat) columns of *df*.

    Parameters
    ----------
    df:
        The metadata DataFrame returned by :func:`load_video_metadata`.
    lon_col, lat_col:
        Column names for longitude and latitude respectively.
    """
    return spatial.KDTree(df[[lon_col, lat_col]].values)


def nearest_frame_index(kdt: spatial.KDTree,
                        df: pd.DataFrame,
                        lon: float,
                        lat: float) -> tuple[int, float]:
    """Return the ``frame_index`` of the video frame nearest to *(lon, lat)*.

    Parameters
    ----------
    kdt:
        A KDTree built by :func:`build_kdtree`.
    df:
        The same DataFrame that was used to build *kdt* (needed to translate
        the KDTree row number back to the actual ``frame_index`` value).
    lon, lat:
        Query point in the same coordinate space as the tree (WGS-84).

    Returns
    -------
    (frame_index, distance)
        The ``frame_index`` value from *df* and the Euclidean distance in
        degree-space.
    """
    distance, row = kdt.query([lon, lat])
    frame_idx = int(df["frame_index"].iloc[row])
    return frame_idx, float(distance)


def frame_position(df: pd.DataFrame, frame_index: int) -> dict:
    """Return the geographic position recorded for *frame_index*.

    Parameters
    ----------
    df:
        Metadata DataFrame with ``frame_index`` as the index.
    frame_index:
        The target frame number.

    Returns
    -------
    A dict with keys ``latitude``, ``longitude``, and optionally ``depth``,
    ``altitude``, ``heading``, ``pitch``, ``roll``, ``timestamp`` — whatever
    columns are present in *df*.
    """
    row = df.loc[frame_index]
    return row.to_dict()


# ---------------------------------------------------------------------------
# Annotation helpers
# ---------------------------------------------------------------------------

def load_video_annotations(csv_path: str | Path) -> dict[int, dict]:
    """Parse the video annotation CSV and return a frame → annotation mapping.

    Parameters
    ----------
    csv_path:
        Path to the annotation CSV file.

    Returns
    -------
    A dict keyed by ``frame_index`` (int).  Each value is a dict with keys:

    * ``bboxes``       — list of ``[x0, y0, x1, y1]`` int lists
    * ``species``      — list of species label strings
    * ``confidences``  — list of float confidence scores

    Raises ``FileNotFoundError`` / ``Exception`` on I/O or parse failures.
    """
    df = pd.read_csv(csv_path)
    result: dict[int, dict] = {}
    for _, row in df.iterrows():
        fidx = int(row["frame_index"])
        try:
            bboxes = json.loads(row["bboxes"])
            species = json.loads(row["species"])
            confidences = json.loads(row["confidences"])
        except (KeyError, ValueError, TypeError):
            continue
        result[fidx] = {
            "bboxes": bboxes,
            "species": species,
            "confidences": confidences,
        }
    return result


def filter_annotations_by_confidence(annotation: dict | None,
                                      threshold: float) -> list[dict]:
    """Return bounding-box entries whose confidence meets *threshold*.

    Parameters
    ----------
    annotation:
        The annotation dict for a single frame (value from the dict returned
        by :func:`load_video_annotations`), or ``None`` when no annotation
        exists for the frame.
    threshold:
        Minimum confidence value (inclusive).

    Returns
    -------
    A (possibly empty) list of dicts with keys ``bbox``, ``species``, and
    ``confidence``.
    """
    if annotation is None:
        return []
    results = []
    for i, bbox in enumerate(annotation.get("bboxes", [])):
        conf = annotation["confidences"][i]
        if conf >= threshold:
            results.append({
                "bbox": bbox,
                "species": annotation["species"][i],
                "confidence": conf,
                "index": i,
            })
    return results


def save_video_annotations(annotations: dict[int, dict],
                            csv_path: str | Path) -> None:
    """Serialise the annotation dict back to the CSV format.

    Parameters
    ----------
    annotations:
        Mapping of frame_index → annotation dict, as produced / modified by
        the annotation editor.
    csv_path:
        Destination path (created or overwritten).
    """
    rows = []
    for frame_idx in sorted(annotations):
        ann = annotations[frame_idx]
        rows.append({
            "frame_index": frame_idx,
            "bboxes": json.dumps(ann.get("bboxes", [])),
            "species": json.dumps(ann.get("species", [])),
            "confidences": json.dumps(ann.get("confidences", [])),
        })
    pd.DataFrame(rows).to_csv(csv_path, index=False)
