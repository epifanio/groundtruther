"""Unit tests for gt/image_manager.py (pure numpy/pandas/scipy helpers)."""
import numpy as np
import pandas as pd
import pytest

from groundtruther.gt import image_manager as im


@pytest.fixture
def df():
    return pd.DataFrame({
        "Imagename": ["img_a", "img_b", "img_c"],
        "habcam_lon": [0.0, 10.0, 20.0],
        "habcam_lat": [0.0, 10.0, 20.0],
    })


def test_load_metadata_roundtrip(tmp_path, df):
    p = tmp_path / "meta.parquet"
    df.to_parquet(p)
    loaded = im.load_metadata(p)
    assert list(loaded["Imagename"]) == ["img_a", "img_b", "img_c"]


def test_load_metadata_missing_file(tmp_path):
    with pytest.raises((FileNotFoundError, OSError)):
        im.load_metadata(tmp_path / "nope.parquet")


def test_nearest_image_index(df):
    kdt = im.build_kdtree(df)
    idx, dist = im.nearest_image_index(kdt, 9.0, 11.0)   # closest to img_b (10,10)
    assert idx == 1
    assert isinstance(idx, int) and isinstance(dist, float)
    assert dist == pytest.approx((1.0**2 + 1.0**2) ** 0.5)


def test_build_kdtree_custom_columns():
    d = pd.DataFrame({"lon": [1.0, 2.0], "lat": [1.0, 2.0]})
    kdt = im.build_kdtree(d, lon_col="lon", lat_col="lat")
    assert im.nearest_image_index(kdt, 2.1, 2.1)[0] == 1


def test_image_path(df, tmp_path):
    p = im.image_path(tmp_path, df, 2)
    assert p.name == "img_c.jpg"
    assert p.parent == tmp_path
    assert im.image_path(tmp_path, df, 0, extension=".png").name == "img_a.png"


def test_attach_annotations(df):
    ann = {"img_b": {"bbox": [[0, 0, 1, 1]], "Species": ["x"], "Confidence": [0.9]}}
    out = im.attach_annotations(df, ann)
    assert "Annotation" in out.columns
    assert out.loc[out["Imagename"] == "img_b", "Annotation"].iloc[0]["Species"] == ["x"]
    assert pd.isna(out.loc[out["Imagename"] == "img_a", "Annotation"].iloc[0])
    assert "Annotation" not in df.columns          # original not mutated


def test_filter_annotations_by_confidence():
    ann = {
        "bbox": [[0, 0, 1, 1], [2, 2, 3, 3], [4, 4, 5, 5]],
        "Species": ["a", "b", "c"],
        "Confidence": [0.95, 0.4, 0.8],
    }
    kept = im.filter_annotations_by_confidence(ann, 0.8)
    assert [k["species"] for k in kept] == ["a", "c"]
    assert all(k["confidence"] >= 0.8 for k in kept)
    assert {"bbox", "species", "confidence"} == set(kept[0])


def test_filter_annotations_handles_missing():
    assert im.filter_annotations_by_confidence(None, 0.5) == []
    assert im.filter_annotations_by_confidence(np.nan, 0.5) == []
