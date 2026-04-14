"""Stateless image-metadata helpers for the GroundTruther plugin.

All functions are pure: they take plain Python/numpy/pandas objects and
return plain objects.  No Qt, no QGIS, no plugin state — callers handle
UI feedback.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import spatial


def load_metadata(parquet_path: str | Path) -> pd.DataFrame:
    """Read the HabCam image-metadata Parquet file and return a DataFrame.

    Raises ``FileNotFoundError`` if the file does not exist, and
    ``Exception`` (from pyarrow) if the file is malformed — callers are
    expected to catch and handle these.
    """
    return pd.read_parquet(parquet_path)


def build_kdtree(df: pd.DataFrame,
                 lon_col: str = "habcam_lon",
                 lat_col: str = "habcam_lat") -> spatial.KDTree:
    """Build a 2-D KDTree over the (lon, lat) columns of *df*.

    Parameters
    ----------
    df:
        The metadata DataFrame returned by :func:`load_metadata`.
    lon_col, lat_col:
        Column names for longitude and latitude respectively.
    """
    return spatial.KDTree(df[[lon_col, lat_col]].values)


def nearest_image_index(kdt: spatial.KDTree,
                        lon: float, lat: float) -> tuple[int, float]:
    """Find the index of the image nearest to *(lon, lat)*.

    Parameters
    ----------
    kdt:
        A KDTree built by :func:`build_kdtree`.
    lon, lat:
        Query point in the same coordinate space as the tree.

    Returns
    -------
    (index, distance)
        Row index into the original DataFrame and the Euclidean distance.
    """
    distance, index = kdt.query([lon, lat])
    return int(index), float(distance)


def image_path(dirname: str | Path,
               df: pd.DataFrame,
               index: int,
               extension: str = ".jpg") -> Path:
    """Return the full path for the image at *index* in *df*.

    Parameters
    ----------
    dirname:
        Root directory that contains the image files.
    df:
        The metadata DataFrame (must have an ``Imagename`` column).
    index:
        Row index into *df*.
    extension:
        File-extension to append (default: ``".jpg"``).
    """
    name = df["Imagename"].iloc[index]
    return Path(dirname) / f"{name}{extension}"


def attach_annotations(df: pd.DataFrame,
                        annotations_by_image: dict) -> pd.DataFrame:
    """Map the pre-parsed annotation dict onto the ``Annotation`` column.

    Parameters
    ----------
    df:
        The metadata DataFrame.
    annotations_by_image:
        Mapping of image-name → annotation dict, as returned by
        :func:`groundtruther.ioutils.parse_annotation`.

    Returns
    -------
    The same DataFrame with an ``Annotation`` column added (or replaced).
    """
    df = df.copy()
    df["Annotation"] = df["Imagename"].map(annotations_by_image)
    return df


def filter_annotations_by_confidence(annotation: dict | float,
                                      threshold: float) -> list[dict]:
    """Return bounding-box entries whose confidence meets *threshold*.

    Parameters
    ----------
    annotation:
        The annotation dict for a single image (from the ``Annotation``
        column), or ``NaN`` / ``None`` when no annotation exists.
    threshold:
        Minimum confidence value (inclusive).

    Returns
    -------
    A (possibly empty) list of dicts with keys ``bbox``, ``Species``,
    and ``Confidence``.
    """
    if annotation is np.nan or annotation is None:
        return []
    results = []
    for i, bbox in enumerate(annotation.get("bbox", [])):
        if annotation["Confidence"][i] >= threshold:
            results.append({
                "bbox": bbox,
                "species": annotation["Species"][i],
                "confidence": annotation["Confidence"][i],
            })
    return results
