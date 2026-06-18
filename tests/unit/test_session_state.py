"""Unit tests for gt.session_state (de)serialisation."""
import json
import pytest

from groundtruther.gt.session_state import (
    SESSION_VERSION,
    default_state,
    serialize,
    deserialize,
)


def test_default_state_has_all_sections():
    state = default_state()
    assert state["version"] == SESSION_VERSION
    assert set(state) == {"version", "image", "video", "query", "layout"}
    assert state["image"]["index"] is None
    assert state["query"]["backscatter_field"] is None


def test_roundtrip_preserves_values():
    state = default_state()
    state["image"]["index"] = 42
    state["image"]["zoom"] = 5000
    state["query"]["shape"] = "Ellipse"
    state["query"]["backscatter_field"] = "BS_AVG_dB"
    state["query"]["beam"] = "left_beam"
    state["layout"] = {"_image_dock": {"floating": True, "visible": True,
                                       "geometry": "AAAA"}}
    out = deserialize(serialize(state))
    assert out["image"]["index"] == 42
    assert out["image"]["zoom"] == 5000
    assert out["query"]["shape"] == "Ellipse"
    assert out["query"]["backscatter_field"] == "BS_AVG_dB"
    assert out["query"]["beam"] == "left_beam"
    assert out["layout"]["_image_dock"]["floating"] is True


def test_partial_file_merges_onto_defaults():
    # an older/partial file with only an image index still loads fully
    partial = json.dumps({"image": {"index": 7}})
    out = deserialize(partial)
    assert out["image"]["index"] == 7
    assert out["image"]["zoom"] is None          # filled from default
    assert out["video"]["geo_link"] is None       # whole missing section present
    assert out["query"]["beam"] is None
    assert out["layout"] == {}


def test_serialize_normalises_version():
    out = deserialize(serialize({"version": 999, "image": {"index": 1}}))
    assert out["version"] == SESSION_VERSION


def test_deserialize_rejects_non_object():
    with pytest.raises(ValueError):
        deserialize("[1, 2, 3]")


def test_empty_text_yields_defaults():
    assert deserialize("") == default_state()
