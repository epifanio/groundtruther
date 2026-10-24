"""Regression tests for the image browser's metadata HTML summary.

**The fault these pin down.** On QGIS 4.2.1 on macOS (pandas 3.0.3 against numpy
2.5.0) the metadata panel killed the whole application the first time the user
changed image.  ``mixins/image_browser_mixin.py`` built its summary with

    pd.DataFrame([self.imageMetadata[available].iloc[self.imageindex]]).to_html()

and ``.iloc[i]`` carries the index label as the Series' *name*.  The HabCam
metadata index holds ``datetime.datetime`` objects — object dtype by design, see
``gt/pandas_safe.py`` — so ``pd.DataFrame([series])`` built the new frame's index
from a datetime and pandas segfaulted inferring a dtype for it: SIGSEGV in
``maybe_convert_objects``, exit 139, no exception, no traceback.  Measured, and
written up in ``PLANNING/TODO_mac-install-test.md`` §6.2.

**Why there is a source-level test here.** As ``test_pandas_safe.py`` already
argues, asserting that a call returns is worthless for a fault that kills the
process — pytest reports nothing at all.  Worse, this crash is
platform-specific: on Linux pandas converts the datetime name happily, so a
behavioural test passes whether or not the bug is present.  CI can therefore
only protect the Mac by pinning the *shape of the call*, which is what
``test_summary_is_built_from_a_dict`` does.  The rest exercise the safe shape.
"""

import datetime
import pathlib
import re

import pandas as pd
import pytest

MIXIN = (pathlib.Path(__file__).resolve().parents[2]
         / "mixins" / "image_browser_mixin.py")

# The eleven columns the panel actually summarises.
WANTED = ['Longitude', 'Latitude', 'V_Depth', 'Water_Depth', 'Altimeter',
          'Salinity', 'Temp', 'O2', 'Cdom', 'Chlorophyll', 'Turb']


def _row():
    """A metadata row exactly as ``df[available].iloc[i]`` hands it over.

    The point is the ``name``: a ``datetime.datetime``, which is what the
    object-dtype metadata index is made of.
    """
    return pd.Series(
        {c: float(i) for i, c in enumerate(WANTED)},
        name=datetime.datetime(2015, 6, 19, 18, 11, 42, 496000),
    )


def test_summary_is_built_from_a_dict():
    """The panel must not hand a *named* Series to the DataFrame constructor.

    This is the test that protects macOS from CI running on Linux: it reads the
    source rather than the behaviour, because the behaviour differs by platform
    while the dangerous shape does not.
    """
    src = MIXIN.read_text(encoding="utf-8")

    assert "pd.DataFrame([row.to_dict()]).to_html()" in src, (
        "the metadata summary no longer builds from row.to_dict(); if it was "
        "rewritten, keep the index label out of the DataFrame constructor"
    )

    banned = re.search(r"pd\.DataFrame\(\s*\[\s*self\.imageMetadata", src)
    assert banned is None, (
        "pd.DataFrame([self.imageMetadata...iloc[...]]) is back at "
        f"{MIXIN.name}: the Series' name is a datetime and pandas segfaults "
        "building an index from it (TODO_mac-install-test.md §6.2)"
    )


def test_the_safe_shape_summarises_a_row_with_a_datetime_name():
    """``to_dict()`` drops the name, so the summary carries only the columns."""
    row = _row()
    assert isinstance(row.name, datetime.datetime)      # the hazard is present

    html = pd.DataFrame([row.to_dict()]).to_html()

    for col in WANTED:
        assert col in html
    # The datetime name does not reach the table, in any rendering.
    assert "2015-06-19" not in html
    assert "18:11:42" not in html


def test_the_safe_shape_keeps_no_datetime_dtype():
    """No column or index of the summary may be a datetime64/timedelta64.

    The same invariant ``test_pandas_safe.py`` pins for the readers: holding one
    of these dtypes *is* the crash on the broken build.
    """
    frame = pd.DataFrame([_row().to_dict()])

    for dtype in [frame.index.dtype, *frame.dtypes]:
        assert not pd.api.types.is_datetime64_any_dtype(dtype), dtype
        assert not pd.api.types.is_timedelta64_dtype(dtype), dtype


@pytest.mark.parametrize("missing", [[], ['Turb'], ['O2', 'Cdom', 'Turb']])
def test_the_summary_tolerates_absent_columns(missing):
    """``available`` filters the wanted list, so a short file still renders."""
    present = [c for c in WANTED if c not in missing]
    html = pd.DataFrame([_row()[present].to_dict()]).to_html()

    for col in present:
        assert col in html
    for col in missing:
        assert f"<th>{col}</th>" not in html
