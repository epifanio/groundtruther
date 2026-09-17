"""Loss-free merging of GroundTruther settings dicts.

The Settings dialog has widgets for only *some* of the keys in
``config/config.yaml``: the whole ``Roughness:`` section (georeferencing, the
micro-DEM mesh knobs, the on-host ``direct_url``) and ``Video.videoannotation``
are hand-edited in YAML and have no form field. Saving therefore has to be a
*merge* over the file already on disk — anything that rebuilds the document
from the form alone silently deletes those keys.

These helpers are pure (no Qt / no YAML I/O) so they can be unit-tested.
"""


def merge_settings(existing, updates):
    """Return *existing* with *updates* merged over it, recursively.

    Nested mappings are merged key-by-key, so a section (or a single key) that
    *updates* does not mention survives untouched — that is the whole point:
    the Settings dialog can only speak for the keys it has widgets for.

    A key that *is* present in *updates* wins even when its value is ``None``,
    so clearing a form field really does clear the setting. To *preserve* a
    key, leave it out of *updates* entirely rather than passing ``None``.

    Neither argument is modified; the result is a new dict.
    """
    merged = dict(existing or {})
    for key, new_value in (updates or {}).items():
        old_value = merged.get(key)
        if isinstance(old_value, dict) and isinstance(new_value, dict):
            merged[key] = merge_settings(old_value, new_value)
        else:
            merged[key] = new_value
    return merged
