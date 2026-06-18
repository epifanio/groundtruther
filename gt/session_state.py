"""(De)serialise GroundTruther UI/session state to versioned JSON.

Pure helpers (no Qt): the dock widget assembles a plain dict of restorable UI
values (image index, zoom, query-builder selections, dock layout) and this
module turns it into JSON and back, tolerating missing or older keys so a
partial / previous-version session file still loads without raising.

Only *UI/session* state lives here — data source paths stay in config.yaml.
"""
import json

SESSION_VERSION = 1


def default_state():
    """Return the full state skeleton with every key present and unset.

    Loaded files are merged onto this, so any key a file omits falls back to
    ``None`` (treated as "leave the widget as-is" by the apply step).
    """
    return {
        "version": SESSION_VERSION,
        "image": {
            "index": None,
            "zoom": None,
            "annotation_confidence": None,
            "map_sync": None,
        },
        "video": {
            "frame": None,
            "geo_link": None,
        },
        "query": {
            "shape": None,
            "backscatter_field": None,
            "beam": None,
            "longitude": None,
            "latitude": None,
            "ellipse_major": None,
            "ellipse_minor": None,
            "ellipse_orientation": None,
            "rect_l1": None,
            "rect_l2": None,
        },
        # attr name -> {"geometry": <base64 str>, "floating": bool,
        #               "visible": bool, "area": int}
        "layout": {},
    }


def _deep_merge(base, override):
    """Recursively merge ``override`` onto ``base`` (override wins)."""
    out = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def serialize(state):
    """Return pretty JSON for *state*, normalised onto the current schema."""
    merged = _deep_merge(default_state(), state or {})
    merged["version"] = SESSION_VERSION
    return json.dumps(merged, indent=2)


def deserialize(text):
    """Parse a session JSON string, merged onto the default skeleton.

    Raises ``ValueError`` if the text is not a JSON object.
    """
    data = json.loads(text) if text else {}
    if not isinstance(data, dict):
        raise ValueError("session file is not a JSON object")
    return _deep_merge(default_state(), data)
