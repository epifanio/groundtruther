"""Regression tests for gt/pandas_safe.py and its two callers.

**Why these tests look paranoid.** On QGIS 4.2.1 on macOS (pandas 3.0.3 against
numpy 2.5.0) letting pandas build a ``datetime64`` from Arrow data does not
raise — it *segfaults the whole process*, exit 139, no exception and no
traceback.  ``HabCam.imagemetadata`` is one of the two config keys that are
errors, and the plugin's own test file has a ``timestamp[us]`` index, so before
``load_metadata`` was rewritten the plugin could not start at all on that
machine.  See ``PLANNING/TODO_mac-install-test.md`` §5.

A test that merely asserts the return value is not enough for a fault like that,
because on a machine where the bug is live the process dies *inside* the call and
pytest reports nothing at all.  So these tests pin the two things that are
actually load-bearing:

1. the implementation never routes a temporal column through pandas
   (``pd.read_parquet`` is poisoned, and the safe converter is spied on), and
2. the result never contains a ``datetime64``/``timedelta64`` dtype.

Violating (2) *is* the segfault on the broken build, so on Linux — where pandas
works and nothing crashes — these tests still fail loudly the moment someone
reverts to ``pd.read_parquet`` or to ``Table.to_pandas()``.  That is deliberate:
Linux CI is the only place this can be caught before a user's QGIS dies.

These tests never call ``to_pandas()`` on a temporal column themselves, because
doing so would take the test runner down on macOS.
"""
import datetime

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from groundtruther.gt import image_manager as im
from groundtruther.gt import pandas_safe
from groundtruther.gt import video_manager as vm


def _write(tmp_path, table, name="meta.parquet"):
    path = tmp_path / name
    pq.write_table(table, path)
    return path


def _timestamp_table(unit="us", tz=None, with_index_metadata=True):
    """A table shaped like test_imagemetadata.pq: data columns plus a timestamp
    column that the pandas metadata marks as the index.
    """
    stamps = [datetime.datetime(2015, 6, 19, 18, 11, 42, 496000),
              datetime.datetime(2015, 6, 19, 18, 11, 43, 500000),
              datetime.datetime(2015, 6, 19, 18, 11, 44, 250000)]
    if tz is not None:
        stamps = [s.replace(tzinfo=datetime.timezone.utc) for s in stamps]
    table = pa.table({
        "Imagename": pa.array(["img_a", "img_b", "img_c"]),
        "habcam_lon": pa.array([-68.86, -68.87, -68.88]),
        "habcam_lat": pa.array([41.06, 41.07, 41.08]),
        "index": pa.array(stamps, type=pa.timestamp(unit, tz=tz)),
    })
    if with_index_metadata:
        import json
        meta = {
            "index_columns": ["index"],
            "columns": [{"name": n, "field_name": n} for n in table.schema.names],
        }
        table = table.replace_schema_metadata({"pandas": json.dumps(meta)})
    return table


# --- the invariant whose violation is the crash ----------------------------

def _temporal_dtypes(df):
    kinds = [df.index.dtype] + list(df.dtypes)
    return [str(d) for d in kinds if getattr(d, "kind", None) in ("M", "m")]


@pytest.mark.parametrize("unit", ["s", "ms", "us", "ns"])
def test_no_datetime64_anywhere_in_the_result(tmp_path, unit):
    """datetime64 in the result == SIGSEGV on QGIS 4.2.1 / macOS."""
    df = im.load_metadata(_write(tmp_path, _timestamp_table(unit=unit)))
    assert _temporal_dtypes(df) == [], (
        "load_metadata produced a datetime64/timedelta64 dtype; that is the "
        "representation that segfaults QGIS on macOS"
    )


def test_no_datetime64_for_tz_aware_timestamps(tmp_path):
    df = im.load_metadata(_write(tmp_path, _timestamp_table(tz="UTC")))
    assert _temporal_dtypes(df) == []
    assert df.index[0].tzinfo is not None


def test_no_datetime64_for_duration_columns(tmp_path):
    table = pa.table({
        "x": pa.array([1.0, 2.0]),
        "dt": pa.array([datetime.timedelta(seconds=5), datetime.timedelta(seconds=7)],
                       type=pa.duration("us")),
    })
    df = im.load_metadata(_write(tmp_path, table))
    assert _temporal_dtypes(df) == []
    assert df["dt"].tolist() == [datetime.timedelta(seconds=5),
                                 datetime.timedelta(seconds=7)]


def test_unsafe_type_classification():
    for unit in ("s", "ms", "us", "ns"):
        assert pandas_safe.is_unsafe_arrow_type(pa.timestamp(unit))
    assert pandas_safe.is_unsafe_arrow_type(pa.timestamp("us", tz="UTC"))
    assert pandas_safe.is_unsafe_arrow_type(pa.duration("us"))
    # Measured safe on the broken build, so they may go through the bridge.
    for safe in (pa.float64(), pa.int64(), pa.string(),
                 pa.date32(), pa.date64(), pa.time64("us")):
        assert not pandas_safe.is_unsafe_arrow_type(safe)


# --- the implementation must not go through pandas -------------------------

def test_load_metadata_does_not_use_pandas_read_parquet(tmp_path, monkeypatch):
    """pd.read_parquet is the call that kills QGIS. Poison it."""
    def poisoned(*args, **kwargs):
        raise AssertionError(
            "load_metadata called pandas.read_parquet, which segfaults QGIS on "
            "macOS; it must read through pyarrow instead"
        )
    monkeypatch.setattr(pd, "read_parquet", poisoned)
    df = im.load_metadata(_write(tmp_path, _timestamp_table()))
    assert df.shape == (3, 3)


def test_temporal_columns_take_the_safe_converter(tmp_path, monkeypatch):
    """The timestamp column must be built by _temporal_objects, not by the
    Arrow->pandas bridge. If someone reverts the reader, the spy never fires.
    """
    seen = []
    original = pandas_safe.temporal_objects

    def spy(column):
        seen.append(str(column.type))
        return original(column)

    monkeypatch.setattr(pandas_safe, "temporal_objects", spy)
    im.load_metadata(_write(tmp_path, _timestamp_table()))
    assert seen == ["timestamp[us]"], (
        "the timestamp column did not go through the safe converter"
    )


# --- behaviour the callers in mixins/ depend on ----------------------------

def test_timestamp_index_is_preserved_as_python_datetimes(tmp_path):
    """The metadata panel's Time row reads ``record.name``, so the timestamps
    have to stay on the index and stay datetime instances.
    """
    df = im.load_metadata(_write(tmp_path, _timestamp_table()))
    assert df.index.name == "index"
    assert "index" not in df.columns
    assert list(df.columns) == ["Imagename", "habcam_lon", "habcam_lat"]
    assert all(isinstance(v, datetime.datetime) for v in df.index)
    assert df.index[0] == datetime.datetime(2015, 6, 19, 18, 11, 42, 496000)
    assert df.index.is_monotonic_increasing
    # what ``record = df.iloc[i]`` then ``record.name`` gives the panel
    assert isinstance(df.iloc[1].name, datetime.datetime)


def test_values_and_column_order_survive(tmp_path):
    df = im.load_metadata(_write(tmp_path, _timestamp_table()))
    assert list(df["Imagename"]) == ["img_a", "img_b", "img_c"]
    assert df["habcam_lon"].iloc[0] == pytest.approx(-68.86)
    assert im.nearest_image_index(im.build_kdtree(df), -68.87, 41.07)[0] == 1


def test_operations_the_plugin_performs_stay_safe(tmp_path):
    """Object-dtype datetimes are inert in these; ``reset_index``/``concat``
    would re-infer and crash, which is why nothing in the plugin calls them.
    """
    df = im.load_metadata(_write(tmp_path, _timestamp_table()))
    assert df.copy().shape == df.shape
    assert df.sort_index().shape == df.shape
    assert len(df.to_csv()) > 0
    df.at[df.index[1], "habcam_lon"] = 1.0
    assert df["habcam_lon"].iloc[1] == 1.0
    assert im.attach_annotations(df, {"img_b": {"Species": ["x"]}}).shape == (3, 4)


def test_nulls_in_a_timestamp_column(tmp_path):
    table = pa.table({
        "x": pa.array([1.0, 2.0, 3.0]),
        "t": pa.array([datetime.datetime(2015, 1, 1), None,
                       datetime.datetime(2015, 1, 3)], type=pa.timestamp("us")),
    })
    df = im.load_metadata(_write(tmp_path, table))
    assert _temporal_dtypes(df) == []
    assert df["t"].iloc[0] == datetime.datetime(2015, 1, 1)
    assert df["t"].iloc[1] is None
    assert df["t"].iloc[2] == datetime.datetime(2015, 1, 3)


def test_timestamp_as_a_plain_column_keeps_its_place(tmp_path):
    """No pandas index metadata: the timestamp stays a column, in order."""
    table = pa.table({
        "a": pa.array([1.0, 2.0]),
        "t": pa.array([datetime.datetime(2015, 1, 1), datetime.datetime(2015, 1, 2)],
                      type=pa.timestamp("us")),
        "b": pa.array(["p", "q"]),
    })
    df = im.load_metadata(_write(tmp_path, table))
    assert list(df.columns) == ["a", "t", "b"]
    assert df["t"].dtype == object
    assert _temporal_dtypes(df) == []


def test_table_of_only_temporal_columns_keeps_its_row_count(tmp_path):
    table = pa.table({
        "t": pa.array([datetime.datetime(2015, 1, 1)] * 4, type=pa.timestamp("us")),
    })
    df = im.load_metadata(_write(tmp_path, table))
    assert df.shape == (4, 1)
    assert _temporal_dtypes(df) == []


def test_frames_without_any_temporal_column_are_untouched(tmp_path):
    table = pa.table({"a": pa.array([1.0, 2.0]), "b": pa.array(["x", "y"])})
    df = im.load_metadata(_write(tmp_path, table))
    assert list(df.columns) == ["a", "b"]
    assert df["a"].tolist() == [1.0, 2.0]


def test_missing_file_still_raises_filenotfound(tmp_path):
    with pytest.raises(FileNotFoundError):
        im.load_metadata(tmp_path / "nope.parquet")


def test_arrow_table_to_dataframe_is_reusable_for_other_readers():
    """It is the documented entry point for any gt/ reader of Arrow data."""
    table = _timestamp_table()
    df = pandas_safe.arrow_table_to_dataframe(table)
    assert _temporal_dtypes(df) == []
    assert isinstance(df, pd.DataFrame)
    assert isinstance(df.index[0], datetime.datetime)


def test_temporal_objects_returns_an_object_array():
    column = pa.chunked_array([pa.array(
        [datetime.datetime(2015, 1, 1), datetime.datetime(2015, 1, 2)],
        type=pa.timestamp("us"))])
    out = pandas_safe.temporal_objects(column)
    assert isinstance(out, np.ndarray)
    assert out.dtype == object          # not datetime64 — that is the crash
    assert out[0] == datetime.datetime(2015, 1, 1)


# --- the second call site: gt/video_manager.py ------------------------------
# `pd.to_datetime` on *strings* segfaults the same way, so the survey-CSV reader
# was a live crash on macOS too — in a feature path, and one the mixin's
# try/except cannot catch, because a SIGSEGV is not an exception.

_SURVEY_CSV = (
    "Videoseqence,Date,Time,LatDeg,LatMin,NorthSouth,LonDeg,LonMin,EastWest,"
    "Depth,Bottom,Biology,Comments,Cruise,Superstation,Station,"
    "CP_LatDeg,CP_LatMin,CP_NorthSouth,CP_LonDeg,CP_LonMin,CP_EastWest,"
    "CP_Altitude,CP_Depth,CP_MeanAlt\n"
    "1,19.06.2015,18:11:42,41,3.9,N,68,52.1,W,120.5,sand,none,,C1,S1,St1,"
    "41,3.9,N,68,52.1,W,2.0,120.0,2.1\n"
    "2,19.06.2015,18:11:52,41,4.0,N,68,52.2,W,121.0,mud,none,,C1,S1,St1,"
    "41,4.0,N,68,52.2,W,2.1,121.0,2.2\n"
    "3,19.06.2015,18:12:02,41,4.1,N,68,52.3,W,121.5,mud,none,,C1,S1,St1,"
    "41,4.1,N,68,52.3,W,2.2,121.5,2.3\n"
)


def _survey(tmp_path):
    path = tmp_path / "survey.csv"
    path.write_text(_SURVEY_CSV)
    return path


def test_survey_timestamps_are_object_datetimes(tmp_path):
    df = vm.load_video_metadata_survey(_survey(tmp_path))
    assert df["timestamp"].dtype == object
    assert _temporal_dtypes(df) == [], (
        "load_video_metadata_survey produced a datetime64; that is the "
        "representation that segfaults QGIS on macOS"
    )
    assert df["timestamp"].iloc[0] == datetime.datetime(2015, 6, 19, 18, 11, 42)
    assert df["timestamp"].iloc[2] == datetime.datetime(2015, 6, 19, 18, 12, 2)


def test_survey_reader_does_not_use_pd_to_datetime(tmp_path, monkeypatch):
    def poisoned(*args, **kwargs):
        raise AssertionError(
            "pd.to_datetime segfaults QGIS on macOS; parse with "
            "pandas_safe.parse_datetimes instead"
        )
    monkeypatch.setattr(pd, "to_datetime", poisoned)
    df = vm.load_video_metadata_survey(_survey(tmp_path))
    assert len(df) == 3


def test_compute_frame_indices_without_dt_accessor(tmp_path):
    df = vm.compute_frame_indices(vm.load_video_metadata_survey(_survey(tmp_path)), fps=25.0)
    # rows are 10 s apart -> 0, 250, 500 frames at 25 fps
    assert df["video_frame"].tolist() == [0, 250, 500]
    assert _temporal_dtypes(df) == []


def test_compute_frame_indices_does_not_use_the_dt_accessor(tmp_path, monkeypatch):
    """``.dt`` needs a datetime64 column, which is the crash."""
    def poisoned(self):
        raise AssertionError(".dt requires a datetime64 column; that segfaults QGIS")
    monkeypatch.setattr(pd.Series, "dt", property(poisoned))
    df = vm.compute_frame_indices(vm.load_video_metadata_survey(_survey(tmp_path)), fps=25.0)
    assert df["video_frame"].tolist() == [0, 250, 500]


def test_unparseable_timestamps_become_none_not_nat(tmp_path):
    """``None`` is this module's ``coerce``: same meaning, and inert."""
    path = tmp_path / "bad.csv"
    path.write_text(_SURVEY_CSV.replace("19.06.2015,18:11:52", "not-a-date,nonsense"))
    df = vm.load_video_metadata_survey(path)
    assert df["timestamp"].iloc[1] is None
    assert _temporal_dtypes(df) == []


# --- the helpers in isolation ----------------------------------------------

def test_parse_datetimes():
    out = pandas_safe.parse_datetimes(["19.06.2015 18:11:42", "junk", None],
                                      "%d.%m.%Y %H:%M:%S")
    assert out.dtype == object
    assert out[0] == datetime.datetime(2015, 6, 19, 18, 11, 42)
    assert out[1] is None and out[2] is None


def test_parse_datetimes_tolerates_nan():
    out = pandas_safe.parse_datetimes([float("nan")], "%d.%m.%Y %H:%M:%S")
    assert out[0] is None


def test_elapsed_seconds():
    stamps = [datetime.datetime(2015, 1, 1, 0, 0, 0),
              datetime.datetime(2015, 1, 1, 0, 0, 10),
              None,
              datetime.datetime(2015, 1, 1, 0, 1, 0)]
    out = pandas_safe.elapsed_seconds(stamps)
    assert out[0] == 0.0 and out[1] == 10.0 and out[3] == 60.0
    assert np.isnan(out[2])


def test_elapsed_seconds_skips_leading_nulls_for_the_origin():
    out = pandas_safe.elapsed_seconds([None, datetime.datetime(2015, 1, 1, 0, 0, 5),
                                       datetime.datetime(2015, 1, 1, 0, 0, 7)])
    assert np.isnan(out[0]) and out[1] == 0.0 and out[2] == 2.0


def test_elapsed_seconds_all_null():
    out = pandas_safe.elapsed_seconds([None, None])
    assert np.isnan(out).all()


def test_object_array_never_coerces_to_datetime64():
    out = pandas_safe.object_array([datetime.datetime(2015, 1, 1)])
    assert out.dtype == object      # np.array() alone would give datetime64
