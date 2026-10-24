"""Stateless image-metadata helpers for the GroundTruther plugin.

All functions are pure: they take plain Python/numpy/pandas objects and
return plain objects.  No Qt, no QGIS, no plugin state — callers handle
UI feedback.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from scipy import spatial


# --- on-disk image-file resolution -----------------------------------------
# The metadata stores a bare frame name (e.g. "201503.20150619.181140656.204627").
# Different deliveries of the same survey store the pixels under different
# suffix/extension combinations — the mono set as "<name>.jpg", the stereo set as
# "<name>_orig.png", etc.  Resolve by probing the common variants so one metadata
# file drives every delivery.
_IMAGE_VARIANTS = ("", "_orig")
_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".tif", ".tiff")
_PREFERRED_VARIANT: tuple | None = None   # (suffix, ext) that last matched


def resolve_image_path(dirname, imagename) -> str | None:
    """Return the on-disk path of *imagename* within *dirname*, or ``None``.

    Probes common ``<name><suffix><ext>`` combinations (e.g. ``<name>.jpg`` and
    ``<name>_orig.png``) so the same metadata works across mono / stereo
    deliveries.  Remembers the matching pattern so subsequent lookups are a
    single ``stat``.
    """
    global _PREFERRED_VARIANT
    if not dirname or imagename is None or str(imagename) == "":
        return None
    base = os.path.join(str(dirname), str(imagename))
    combos = []
    if _PREFERRED_VARIANT is not None:
        combos.append(_PREFERRED_VARIANT)
    combos.extend((s, e) for s in _IMAGE_VARIANTS for e in _IMAGE_EXTS
                  if (s, e) != _PREFERRED_VARIANT)
    for suffix, ext in combos:
        path = base + suffix + ext
        if os.path.isfile(path):
            _PREFERRED_VARIANT = (suffix, ext)
            return path
    return None


def image_path_or_default(dirname, imagename, default_ext: str = ".jpg") -> str:
    """:func:`resolve_image_path`, falling back to ``<name><default_ext>`` when
    nothing is on disk — so callers always have a stable path to display/report.
    """
    found = resolve_image_path(dirname, imagename)
    if found:
        return found
    return os.path.join(str(dirname), str(imagename) + default_ext)


# --- Parquet reading -------------------------------------------------------
# NEVER let pandas build a datetime64 value from Arrow data in this plugin.
#
# QGIS 4.2.1 on macOS bundles pandas 3.0.3 against numpy 2.5.0, and that pair's
# datetime64 support is an ABI mismatch that *segfaults the whole process*.
# There is no exception and no traceback: QGIS dies with SIGSEGV (exit 139).
# Measured, one process per case, on QGIS's own pandas 3.0.3 / pyarrow 23.0.1 /
# numpy 2.5.0:
#
#     table.to_pandas() on timestamp (s/ms/us/ns, tz or not)   SIGSEGV
#     table.to_pandas() on duration                            SIGSEGV
#     pd.to_datetime(int64 array, unit=...)                    SIGSEGV
#     pd.Series(np.array([], dtype="datetime64[us]"))          SIGSEGV  (empty!)
#     pd.Series(arrow_array, dtype=pd.ArrowDtype(timestamp))   SIGSEGV
#     date32, date64, time64, double, int64, string            fine
#     object-dtype datetime.datetime in a Series or an Index   fine
#
# An empty datetime64 array is enough to kill it, so the fault is in pandas'
# dtype machinery, not in the data — which also means it cannot be probed for
# safely at runtime, because the probe is the crash.  pandas is the only
# variable (the same pyarrow is fine under pandas 2.x), so pinning pyarrow would
# not help; and no ``sys.path`` strategy can help either, because
# ``import qgis.core`` imports pandas itself before any plugin code runs, so the
# venv's working pandas can never displace the bundled one.
#
# So temporal Arrow columns are converted here, to **object dtype holding plain
# ``datetime.datetime`` / ``datetime.timedelta``**, on every platform.  That is
# deliberately uniform rather than branched: object dtype is correct everywhere
# and is the one path both Linux CI and macOS actually exercise, whereas a
# platform branch would leave the macOS path untested by CI — the last thing you
# want for a crash that takes the application down silently.  The cost is that
# the returned index/column is object dtype rather than ``datetime64``, so
# ``.dt`` accessors and time-based slicing are not available on it; no caller in
# the plugin uses either.
#
# One sharp edge survives, and it is pandas', not ours: object-dtype datetimes
# are inert in a *column*, but pandas re-infers them when they move out of an
# *index*, and that inference is the crash.  Measured on the same build,
# ``df.reset_index()`` and ``pd.concat([df, df])`` on the returned frame are
# SIGSEGV, while ``copy``, ``sort_index``, ``iloc``, ``at``, ``to_csv``,
# assigning a column and reading ``df.index[i]`` are all fine.  Nothing in the
# plugin calls either (checked across ``mixins/``, ``gt/`` and ``pygui/``), and
# the index has to stay an index because the metadata panel's Time row reads
# ``record.name``.  Do not add a ``reset_index()`` or a ``concat()`` on this
# frame without converting the index to strings first.
#
# ``HabCam.imagemetadata`` is one of the two config keys that are *errors*, and
# its own test file carries a ``timestamp[us]`` index, so before this change the
# crash blocked plugin startup outright on macOS.  See
# ``PLANNING/TODO_mac-install-test.md`` §5.
_UNSAFE_ARROW_PREDICATES = (pa.types.is_timestamp, pa.types.is_duration)


def is_unsafe_arrow_type(arrow_type) -> bool:
    """Would letting pandas convert a column of *arrow_type* risk the segfault?

    True for the Arrow types pandas maps onto ``datetime64`` / ``timedelta64``
    (timestamp and duration), which is the machinery that is broken.
    """
    return any(pred(arrow_type) for pred in _UNSAFE_ARROW_PREDICATES)


def _temporal_objects(column) -> np.ndarray:
    """A temporal Arrow column as an object-dtype array of Python datetimes.

    ``Arrow -> Python -> object array`` stays clear of every pandas code path
    that constructs a ``datetime64``.  Nulls arrive as ``None``.  Built element
    by element because ``np.array(list_of_datetimes)`` would coerce to
    ``datetime64`` on its own.
    """
    values = column.to_pylist()
    out = np.empty(len(values), dtype=object)
    for i, value in enumerate(values):
        out[i] = value
    return out


def _pandas_index_fields(schema) -> list[tuple[str, str | None]]:
    """The ``(column name, index label)`` pairs a Parquet file's pandas metadata
    marks as the index, in order.  Empty when there is none, or when the index
    was stored as a RangeIndex descriptor rather than as a column.
    """
    metadata = schema.pandas_metadata or {}
    names = set(schema.names)
    labels = {
        col.get("field_name"): col.get("name")
        for col in metadata.get("columns", [])
        if isinstance(col, dict)
    }
    return [(entry, labels.get(entry))
            for entry in metadata.get("index_columns", [])
            if isinstance(entry, str) and entry in names]


def arrow_table_to_dataframe(table) -> pd.DataFrame:
    """Convert a ``pyarrow.Table`` to a DataFrame without crashing pandas 3.

    Does what ``table.to_pandas()`` does — the same columns in the same order,
    with the index restored from the file's pandas metadata — except that
    timestamp and duration data is converted by :func:`_temporal_objects` and
    lands as object dtype.  Use this, never ``to_pandas()``, anywhere in ``gt/``
    that turns Arrow data into a DataFrame.
    """
    names = list(table.schema.names)
    unsafe = {name for name, arrow_type in zip(names, table.schema.types)
              if is_unsafe_arrow_type(arrow_type)}
    index_fields = _pandas_index_fields(table.schema)
    index_names = [name for name, _ in index_fields]

    # Everything the bridge can safely convert goes over in one call; the
    # temporal columns are rebuilt here and put back in their original place.
    safe = table.select([n for n in names if n not in unsafe])
    if safe.num_columns:
        df = safe.to_pandas(ignore_metadata=True)
    else:
        # Every column was temporal: nothing for the bridge to do, but the frame
        # still has to carry the file's row count.
        df = pd.DataFrame(index=pd.RangeIndex(table.num_rows))
    for name in unsafe:
        df[name] = pd.Series(_temporal_objects(table.column(name)),
                             index=df.index, dtype=object)
    df = df[names]

    if index_names:
        # Not ``set_index``: it infers a dtype for the new index, and for
        # datetimes that inference is the segfault.  Build each level by hand,
        # forcing object dtype for the temporal ones.
        levels = [
            pd.Index(df[name].to_numpy(), dtype=object, name=label)
            if name in unsafe else pd.Index(df[name], name=label)
            for name, label in index_fields
        ]
        index = (levels[0] if len(levels) == 1
                 else pd.MultiIndex.from_arrays(levels,
                                                names=[lvl.name for lvl in levels]))
        df = df.drop(columns=index_names)
        df.index = index
    return df


def load_metadata(parquet_path: str | Path) -> pd.DataFrame:
    """Read the HabCam image-metadata Parquet file and return a DataFrame.

    Raises ``FileNotFoundError`` if the file does not exist, and
    ``Exception`` (from pyarrow) if the file is malformed — callers are
    expected to catch and handle these.

    Reads through pyarrow rather than :func:`pandas.read_parquet` because that
    call segfaults QGIS on macOS; see :func:`arrow_table_to_dataframe`.
    """
    path = Path(parquet_path)
    if not path.is_file():
        raise FileNotFoundError(f"No such Parquet file: {path}")
    return arrow_table_to_dataframe(pq.read_table(path))


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
