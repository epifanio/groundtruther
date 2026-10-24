"""Build datetimes without letting pandas build a ``datetime64``.

**Why this module exists.** QGIS 4.2.1 on macOS bundles pandas 3.0.3 against
numpy 2.5.0, and that pandas' datetime C extension is broken: the null
dereference is inside pandas' own ``get_datetime_metadata_from_dtype``, reading
a dtype it cannot interpret — a pandas/numpy C-API ABI mismatch in QGIS's build.
It does not raise.  **It segfaults the whole application** (SIGSEGV, exit 139,
no exception and no log line), so there is nothing for a ``try``/``except`` to
catch and nothing in the QGIS log to show a user.  See
``PLANNING/TODO_mac-install-test.md`` §5 for the crash report and the frame.

Measured one process per case on the bundled stack (pandas 3.0.3, pyarrow
23.0.1, numpy 2.5.0):

=========================================================  ==========
``pd.to_datetime([...])`` — strings, with or without format  SIGSEGV
``pd.to_datetime(int64_array, unit=...)``                    SIGSEGV
``pd.to_timedelta([...])``                                   SIGSEGV
``pd.Series(np.array([], dtype="datetime64[us]"))`` — empty!  SIGSEGV
``Table.to_pandas()`` on timestamp (any unit, tz or not)      SIGSEGV
``Table.to_pandas()`` on duration                             SIGSEGV
``pd.Series(arrow, dtype=pd.ArrowDtype(pa.timestamp(...)))``  SIGSEGV
Arrow ``date32`` / ``date64`` / ``time64``, double, int64,
string; numpy's own ``datetime64``; and object-dtype
``datetime.datetime`` in a Series or an Index                 fine
=========================================================  ==========

Three consequences worth knowing before changing anything here:

* An **empty** array is enough to crash it, so the fault is in pandas' dtype
  machinery rather than in the data — and **it cannot be probed for at runtime,
  because the probe is the crash.**  That is why these helpers are
  unconditional rather than hidden behind a platform or capability check.
* **Pinning cannot fix it.**  ``import qgis.core`` imports pandas itself before
  any plugin code runs, and ``__init__.py``'s ``_bootstrap_venv()`` *appends* to
  ``sys.path``, so QGIS's own pandas always wins whatever the venv holds.
* ``pd.ArrowDtype`` is a trap that looks like a win: it *stores* fine and
  ``.dt.year`` works, but reading one element back builds a ``pd.Timestamp`` and
  dies.

So datetimes in ``gt/`` are carried as **object dtype holding plain
``datetime.datetime`` / ``datetime.timedelta``**, on every platform.  That is
deliberately uniform rather than branched: object dtype is correct everywhere
and is the one path that both Linux CI and macOS exercise, whereas a platform
branch would leave the macOS path untested by CI — the last thing you want for a
crash that takes the application down silently.  The cost is that ``.dt``
accessors and time-based slicing are not available on such a column; no caller
in the plugin uses either.

**Inference is the enemy, not any single call.**  pandas infers a
``datetime64`` from an object-dtype array of datetimes in the ``DataFrame`` and
``Series`` constructors and in ``set_index``, so every datetime column has to be
handed over with ``dtype=object`` spelled out — that is what
:func:`object_series` is for.

**The one surviving edge, and it is pandas', not ours.**  Object datetimes are
inert in a *column*, but pandas re-infers them when they move out of an *index*,
and that inference is the crash.  Measured on the same build,
``df.reset_index()`` and ``pd.concat([df, df])`` on a frame whose index holds
object datetimes are SIGSEGV, while ``copy``, ``sort_index``, ``iloc``, ``at``,
``to_csv``, assigning a column and reading ``df.index[i]`` are all fine.  The
plugin calls neither — there is no ``reset_index`` and no ``pd.concat`` anywhere
in ``mixins/``, ``gt/`` or ``pygui/``.  Do not add one to such a frame without
converting the index to strings first.
"""
from __future__ import annotations

import datetime

import numpy as np
import pandas as pd
import pyarrow as pa

# The Arrow types pandas maps onto datetime64 / timedelta64, i.e. the ones whose
# conversion is broken.  date32/date64/time64 land as object dtype and are safe.
_UNSAFE_ARROW_PREDICATES = (pa.types.is_timestamp, pa.types.is_duration)


def is_unsafe_arrow_type(arrow_type) -> bool:
    """Would letting pandas convert a column of *arrow_type* risk the segfault?"""
    return any(pred(arrow_type) for pred in _UNSAFE_ARROW_PREDICATES)


def object_array(values) -> np.ndarray:
    """*values* as an object-dtype array, element by element.

    ``np.array(list_of_datetimes)`` would coerce to ``datetime64`` on its own,
    which is the dtype that must never be built, so the array is filled
    explicitly.
    """
    values = list(values)
    out = np.empty(len(values), dtype=object)
    for i, value in enumerate(values):
        out[i] = value
    return out


def object_series(values, index=None) -> pd.Series:
    """*values* as an explicitly object-dtype Series.

    Needed because ``pd.DataFrame({"t": array_of_datetimes})`` and
    ``pd.Series(array_of_datetimes)`` **infer** a ``datetime64`` dtype even from
    an object-dtype array — and that inference is the crash.  Every datetime
    column must therefore be handed to pandas through this, with the dtype
    spelled out.
    """
    return pd.Series(object_array(values), index=index, dtype=object)


def temporal_objects(column) -> np.ndarray:
    """A timestamp/duration Arrow column as object-dtype Python datetimes.

    ``Arrow -> Python -> object array`` stays clear of every pandas code path
    that constructs a ``datetime64``.  Nulls arrive as ``None``.
    """
    return object_array(column.to_pylist())


def parse_datetimes(strings, fmt: str) -> np.ndarray:
    """Parse *strings* with :meth:`datetime.datetime.strptime`, as objects.

    The stand-in for ``pd.to_datetime(..., format=fmt, errors="coerce")``, which
    segfaults.  Anything unparseable becomes ``None``, which is this module's
    equivalent of ``coerce``'s ``NaT`` — and, unlike ``NaT``, inert.
    """
    out = []
    for value in strings:
        if value is None or (isinstance(value, float) and np.isnan(value)):
            out.append(None)
            continue
        try:
            out.append(datetime.datetime.strptime(str(value), fmt))
        except (ValueError, TypeError):
            out.append(None)
    return object_array(out)


def elapsed_seconds(stamps, origin=None) -> np.ndarray:
    """Seconds between each of *stamps* and *origin* (the first by default).

    The stand-in for ``(series - t0).dt.total_seconds()``: ``.dt`` needs a
    datetime64 column, and subtracting inside pandas would build one.  Python's
    own ``datetime`` subtraction gives a ``timedelta``, so the arithmetic is
    done here and only floats go back to pandas.  Unparseable entries give
    ``nan``.
    """
    stamps = list(stamps)
    if origin is None:
        origin = next((s for s in stamps if s is not None), None)
    if origin is None:
        return np.full(len(stamps), np.nan)
    return np.array([
        (s - origin).total_seconds() if s is not None else np.nan
        for s in stamps
    ], dtype=float)


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
    """Convert a ``pyarrow.Table`` to a DataFrame, crash-free on pandas 3.

    Does what ``table.to_pandas()`` does — the same columns in the same order,
    with the index restored from the file's pandas metadata — except that
    timestamp and duration data is converted by :func:`temporal_objects` and
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
        df[name] = object_series(temporal_objects(table.column(name)),
                                 index=df.index)
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
                 else pd.MultiIndex.from_arrays(
                     levels, names=[lvl.name for lvl in levels]))
        df = df.drop(columns=index_names)
        df.index = index
    return df
