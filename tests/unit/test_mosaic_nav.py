"""Explicit per-frame navigation for a mode-B mosaic (``gt.mosaic_nav``).

The point of the module is that a mosaic should not anchor on whichever USBL
step its reference frame happens to sit on. These tests pin the geometry that
makes that true, and the fallbacks that keep a thin metadata table working.
"""
import numpy as np
import pandas as pd
import pytest

from groundtruther.gt import mosaic_nav as mn


def _table(n=400, *, step_frames=6, step_m=0.5, heading=273.0,
           altimeter_mm=1700.0, names=True):
    """A metadata table whose USBL is piecewise-constant, like HabCam's.

    The vehicle advances smoothly, but the fix only updates every
    *step_frames* frames — the staircase the smoother exists to remove.

    The held value is the **centre** of each group, so the error oscillates about
    the true track rather than always lagging it. That matters: a constant lag is
    a real offset and a trend-preserving smoother will (correctly) keep it, so a
    lagging fixture would assert something the smoother must not do.
    """
    i = np.arange(n)
    true_e = 507000.0 + i * step_m
    held = (i // step_frames) * step_frames + (step_frames - 1) / 2.0
    df = pd.DataFrame({
        "Xutm": 507000.0 + held * step_m,
        "dx": np.zeros(n),
        "Yutm": np.full(n, 4546000.0),
        "dy": np.zeros(n),
        "bearing": np.full(n, (heading + 180.0) % 360.0),   # points astern
        "Altimeter": np.full(n, altimeter_mm),
    })
    if names:
        df["Imagename"] = [f"201503.20150619.{100000 + k}.{k}" for k in i]
    df.attrs["true_easting"] = true_e
    return df


class TestSmoothedFrames:
    def test_it_returns_one_frame_per_window_slot(self):
        frames = mn.smoothed_frames(_table(), 200, 8)
        assert len(frames) == 17
        assert [f["frame_key"] for f in frames] == \
               [f"201503.20150619.{100000 + k}.{k}" for k in range(192, 209)]

    def test_each_frame_carries_what_mode_b_needs(self):
        f = mn.smoothed_frames(_table(), 200, 2)[0]
        assert set(f) >= {"frame_key", "easting", "northing", "heading_deg"}
        assert f["layback_m"] == 0

    def test_the_heading_is_reversed_from_bearing(self):
        # `bearing` points astern; sending it unreversed is issue #31.
        f = mn.smoothed_frames(_table(heading=273.0), 200, 1)[1]
        assert f["heading_deg"] == pytest.approx(273.0, abs=1e-6)

    def test_altimeter_millimetres_become_metres(self):
        f = mn.smoothed_frames(_table(altimeter_mm=1700.0), 200, 1)[0]
        assert f["altitude_m"] == pytest.approx(1.7)

    def test_smoothing_removes_the_usbl_staircase(self):
        """The whole point: smoothed positions track the true path, raw ones step."""
        df = _table()
        truth = df.attrs["true_easting"]
        frames = mn.smoothed_frames(df, 200, 20)
        smooth = np.array([f["easting"] for f in frames])
        raw = np.asarray(df["Xutm"] + df["dx"])[180:221]
        t = truth[180:221]
        # Smoothed must follow the real advance far better than the held fix.
        assert np.median(np.abs(smooth - t)) < np.median(np.abs(raw - t)) / 2

    def test_a_straight_run_is_not_shortened(self):
        """A trend-blind smoother would contract the track — caught in the ribbon."""
        frames = mn.smoothed_frames(_table(step_m=0.5), 200, 20)
        e = np.array([f["easting"] for f in frames])
        assert np.ptp(e) == pytest.approx(40 * 0.5, rel=0.05)

    def test_the_window_is_clipped_at_the_table_edges(self):
        frames = mn.smoothed_frames(_table(n=50), 2, 8)
        assert len(frames) == 11        # rows 0..10, not -6..10

    def test_it_still_works_near_the_start_where_padding_is_short(self):
        frames = mn.smoothed_frames(_table(n=80), 5, 3)
        assert len(frames) == 7
        assert all(np.isfinite(f["easting"]) for f in frames)


class TestFallbacks:
    def test_no_position_columns_is_an_explicit_error(self):
        df = pd.DataFrame({"Imagename": ["a", "b"], "bearing": [0.0, 0.0]})
        with pytest.raises(mn.MosaicNavError, match="USBL"):
            mn.smoothed_frames(df, 0, 1)

    def test_no_name_column_is_an_explicit_error(self):
        df = _table(names=False)
        with pytest.raises(mn.MosaicNavError, match="Imagename"):
            mn.smoothed_frames(df, 10, 1)

    def test_a_window_outside_the_table_is_an_explicit_error(self):
        with pytest.raises(mn.MosaicNavError, match="outside"):
            mn.smoothed_frames(_table(n=20), 500, 4)

    def test_frames_without_a_heading_are_dropped_not_guessed(self):
        df = _table(n=60)
        df.loc[28:32, "bearing"] = np.nan
        frames = mn.smoothed_frames(df, 30, 5)
        assert len(frames) == 6           # 11 slots, 5 unusable
        assert all(np.isfinite(f["heading_deg"]) for f in frames)

    def test_no_usable_frame_at_all_is_an_error(self):
        df = _table(n=40)
        df["bearing"] = np.nan
        with pytest.raises(mn.MosaicNavError, match="heading"):
            mn.smoothed_frames(df, 20, 3)


class TestAnchorOffset:
    def test_it_reports_how_far_the_raw_fix_sits_from_the_track(self):
        df = _table(step_frames=6, step_m=0.5)
        offsets = [mn.anchor_offset_m(df, r) for r in range(150, 250)]
        offsets = [o for o in offsets if o is not None]
        # A held fix sits up to half a group away from the smoothed track.
        assert max(offsets) > 0.5
        assert max(offsets) < (6 - 1) / 2.0 * 0.5 * 1.5

    def test_it_is_near_zero_when_the_fix_does_not_step(self):
        df = _table(step_frames=1)        # a fix every frame: no staircase
        assert mn.anchor_offset_m(df, 200) == pytest.approx(0.0, abs=0.02)

    def test_it_returns_none_rather_than_raising_on_a_thin_table(self):
        assert mn.anchor_offset_m(pd.DataFrame({"a": [1]}), 0) is None
        assert mn.anchor_offset_m(_table(n=40), 999) is None
