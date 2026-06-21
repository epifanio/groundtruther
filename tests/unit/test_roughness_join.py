"""Unit tests for gt/roughness_join.py (pure numpy/pandas/scipy join)."""
import numpy as np
import pandas as pd
import pytest

from groundtruther.gt import roughness_join as rj


@pytest.fixture
def image_df():
    return pd.DataFrame({
        "Imagename": ["201503.aaa.111.204627",
                      "201503.bbb.222.294209",
                      "201503.ccc.333.300000"],
        "habcam_lon": [0.0, 10.0, 20.0],
        "habcam_lat": [0.0, 10.0, 20.0],
    })


@pytest.fixture
def roughness_by_frame():
    return {
        "204627": {"quality": "ok", "gamma2": 2.4, "w2": 1.1e-4,
                   "rms_height_mm": 3.0},
        # keyed by the FULL image id this time, to exercise variant lookup
        "201503.bbb.222.294209": {"quality": "ok", "gamma2": 2.8, "w2": 2.0e-4,
                                  "rms_height_mm": 5.0},
    }


def test_frame_key_variants():
    assert rj.frame_key_variants("201503.x.y.204627") == ["201503.x.y.204627", "204627"]
    assert rj.frame_key_variants("204627") == ["204627"]


def test_lookup_roughness_variant(roughness_by_frame):
    # trailing-token key
    assert rj.lookup_roughness(roughness_by_frame, "201503.aaa.111.204627")["gamma2"] == 2.4
    # full-id key
    assert rj.lookup_roughness(roughness_by_frame, "201503.bbb.222.294209")["gamma2"] == 2.8
    assert rj.lookup_roughness(roughness_by_frame, "999") is None
    assert rj.lookup_roughness({}, "x") is None


def test_join_attaches_nearest_frame(image_df, roughness_by_frame):
    samples = pd.DataFrame({"lon": [0.1, 9.8], "lat": [0.1, 10.1]})
    out = rj.join_roughness_to_samples(samples, image_df, roughness_by_frame)

    assert list(out["rough_frame"]) == ["201503.aaa.111.204627",
                                        "201503.bbb.222.294209"]
    assert out["gamma2"].tolist() == [2.4, 2.8]
    assert out["quality"].tolist() == ["ok", "ok"]
    # placement note present on attached rows, value-not-remeasured wording
    assert all("placement" in n for n in out["rough_placement_note"])
    # original frame not mutated
    assert "gamma2" not in samples.columns


def test_join_frame_without_roughness(image_df, roughness_by_frame):
    # nearest is the third image (300000), which has no computed roughness
    samples = pd.DataFrame({"lon": [20.0], "lat": [20.0]})
    out = rj.join_roughness_to_samples(samples, image_df, roughness_by_frame)
    assert out["rough_frame"].iloc[0] == "201503.ccc.333.300000"
    assert out["gamma2"].iloc[0] is None
    assert "no roughness computed" in out["rough_placement_note"].iloc[0]


def test_join_max_distance_cap(image_df, roughness_by_frame):
    # sample far from any frame; cap rejects the match
    samples = pd.DataFrame({"lon": [0.0], "lat": [0.0]})
    out = rj.join_roughness_to_samples(samples, image_df, roughness_by_frame,
                                       max_distance=1e-6)
    # frame 204627 is at distance 0 -> within cap; pick a far sample instead
    samples_far = pd.DataFrame({"lon": [5.0], "lat": [5.0]})
    out_far = rj.join_roughness_to_samples(samples_far, image_df, roughness_by_frame,
                                           max_distance=0.1)
    assert out["gamma2"].iloc[0] == 2.4
    assert out_far["gamma2"].iloc[0] is None
    assert "max_distance" in out_far["rough_placement_note"].iloc[0]


def test_join_empty_samples(image_df, roughness_by_frame):
    samples = pd.DataFrame({"lon": [], "lat": []})
    out = rj.join_roughness_to_samples(samples, image_df, roughness_by_frame)
    assert len(out) == 0
    for col in ("rough_frame", "rough_dist", "gamma2", "rough_placement_note"):
        assert col in out.columns


def test_join_reuses_prebuilt_kdtree(image_df, roughness_by_frame):
    from groundtruther.gt import image_manager as im
    kdt = im.build_kdtree(image_df)
    samples = pd.DataFrame({"lon": [9.8], "lat": [10.1]})
    out = rj.join_roughness_to_samples(samples, image_df, roughness_by_frame, kdt=kdt)
    assert out["gamma2"].iloc[0] == 2.8


def test_join_custom_columns(roughness_by_frame):
    image_df = pd.DataFrame({
        "name": ["201503.aaa.111.204627"], "x": [0.0], "y": [0.0]})
    samples = pd.DataFrame({"X": [0.0], "Y": [0.0]})
    out = rj.join_roughness_to_samples(
        samples, image_df, roughness_by_frame,
        sample_lon_col="X", sample_lat_col="Y",
        image_lon_col="x", image_lat_col="y", frame_key_col="name")
    assert out["gamma2"].iloc[0] == 2.4
