"""Map MBES soundings parquet columns to query-builder UI fields.

The query builder must accept two soundings schemas:

* **Legacy** (``mbes_2015.parquet``) — a single processed backscatter pair,
  columns ``"Backscatter Value"`` and ``"Corrected Backscatter Value"``.
* **Multi-level** (``mbes_2015_multilevel.parquet``) — every step of the
  BSWG-2015 Ch.6 chain, columns ``BS_raw_dB``, ``BS_RL_dB``, ``BS_TL_dB``,
  ``BS_area_dB`` and ``BS_AVG_dB`` (see the dataset README).

These helpers are pure (no Qt / pandas) so they can be unit-tested: they take an
iterable of column names and return the backscatter columns to expose in the UI.
"""

# Known backscatter columns in *preferred display order*. The first entry that
# is present in a file is also used as the default selection, so the most
# "corrected" / angular-normalised level is listed first. ``BS_AVG_dB`` is the
# multi-level equivalent of the legacy ``"Corrected Backscatter Value"``
# (both are mbbackangle angular-response corrected, ref 30 deg).
_KNOWN_BACKSCATTER_FIELDS = [
    "Corrected Backscatter Value",
    "BS_AVG_dB",
    "BS_area_dB",
    "BS_TL_dB",
    "BS_RL_dB",
    "BS_raw_dB",
    "Backscatter Value",
]


def detect_backscatter_fields(columns):
    """Return the backscatter columns present in ``columns``, ordered for the UI.

    Known fields (legacy + multi-level) come first in their preferred order;
    any other column that looks like backscatter (``BS_*`` prefix or containing
    "backscatter") is appended so future schemas degrade gracefully.
    """
    cols = list(columns)
    ordered = [c for c in _KNOWN_BACKSCATTER_FIELDS if c in cols]
    extra = [
        c
        for c in cols
        if c not in ordered
        and (str(c).startswith("BS_") or "backscatter" in str(c).lower())
    ]
    return ordered + extra


def default_backscatter_field(columns):
    """Return the preferred default backscatter column, or ``None`` if there is none."""
    fields = detect_backscatter_fields(columns)
    return fields[0] if fields else None
