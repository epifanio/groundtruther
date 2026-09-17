"""Unit tests for loss-free settings merging (gt/config_merge.py).

Regression cover for the bug where saving from the Settings dialog rebuilt
``config/config.yaml`` from a fixed template and silently deleted every key the
dialog has no widget for — the whole ``Roughness:`` section and
``Video.videoannotation``.
"""
import yaml

from groundtruther.gt.config_merge import merge_settings


def test_unmentioned_section_survives():
    existing = {
        "HabCam": {"imagepath": "/old"},
        "Roughness": {"georeference": True, "epsg": 32619, "dem_erode": 2},
    }
    merged = merge_settings(existing, {"HabCam": {"imagepath": "/new"}})

    assert merged["HabCam"]["imagepath"] == "/new"
    assert merged["Roughness"] == {"georeference": True, "epsg": 32619, "dem_erode": 2}


def test_unmentioned_key_within_a_merged_section_survives():
    existing = {"Video": {"videofile": "/a.mp4", "videoannotation": "/ann.csv"}}
    merged = merge_settings(existing, {"Video": {"videofile": "/b.mp4"}})

    assert merged["Video"] == {"videofile": "/b.mp4", "videoannotation": "/ann.csv"}


def test_explicit_none_clears_a_value():
    """A cleared form field (``None``) must win — that is how you unset a key."""
    existing = {"Mbes": {"soundings": "/s.parquet"}}
    merged = merge_settings(existing, {"Mbes": {"soundings": None}})

    assert merged["Mbes"]["soundings"] is None


def test_new_sections_are_added():
    merged = merge_settings({}, {"HabCam": {"imagepath": "/new"}})
    assert merged == {"HabCam": {"imagepath": "/new"}}


def test_inputs_are_not_mutated():
    existing = {"HabCam": {"imagepath": "/old"}}
    updates = {"HabCam": {"imagepath": "/new"}}
    merge_settings(existing, updates)

    assert existing == {"HabCam": {"imagepath": "/old"}}
    assert updates == {"HabCam": {"imagepath": "/new"}}


def test_none_arguments_are_tolerated():
    assert merge_settings(None, {"A": 1}) == {"A": 1}
    assert merge_settings({"A": 1}, None) == {"A": 1}


def test_scalar_does_not_absorb_a_dict():
    """A section that used to be a scalar is replaced, not merged into."""
    merged = merge_settings({"Video": ""}, {"Video": {"videofile": "/a.mp4"}})
    assert merged["Video"] == {"videofile": "/a.mp4"}


def test_yaml_round_trip_preserves_roughness(tmp_path):
    """End-to-end shape of what write_config() now does to the file on disk."""
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "---\n"
        "HabCam:\n"
        "    imagepath: /old\n"
        "Video:\n"
        "    videofile: /a.mp4\n"
        "    videoannotation: /ann.csv\n"
        "Roughness:\n"
        "    georeference: true\n"
        "    direct_url: http://127.0.0.1:7871/roughness\n",
        encoding="utf8",
    )

    existing = yaml.safe_load(cfg.read_text(encoding="utf8"))
    merged = merge_settings(existing, {
        "HabCam": {"imagepath": "/new"},
        "Video": {"videofile": "/b.mp4"},
    })
    cfg.write_text(
        yaml.safe_dump(merged, sort_keys=False, default_flow_style=False,
                       explicit_start=True, indent=4, allow_unicode=True),
        encoding="utf8",
    )

    reloaded = yaml.safe_load(cfg.read_text(encoding="utf8"))
    assert reloaded["HabCam"]["imagepath"] == "/new"
    assert reloaded["Video"]["videofile"] == "/b.mp4"
    assert reloaded["Video"]["videoannotation"] == "/ann.csv"
    assert reloaded["Roughness"] == {
        "georeference": True,
        "direct_url": "http://127.0.0.1:7871/roughness",
    }
    # Key order is preserved, so the file stays recognisable after a save.
    assert list(reloaded) == ["HabCam", "Video", "Roughness"]


def test_yaml_round_trip_quotes_awkward_values(tmp_path):
    """The old template interpolated raw values; ':' or '#' broke the YAML."""
    merged = merge_settings({}, {"HabCam": {"imagepath": "/data/dive: 3 #1"}})
    dumped = yaml.safe_dump(merged, sort_keys=False, default_flow_style=False,
                            explicit_start=True, indent=4, allow_unicode=True)

    assert yaml.safe_load(dumped)["HabCam"]["imagepath"] == "/data/dive: 3 #1"
