"""Prepare the spectral-roughness plot data — stateless.

``/roughness`` with ``include_spectrum:true`` returns a ``spectrum`` object: the
radial power spectrum ``W(K)`` plus its power-law fit::

    { "K_rad_per_m":[…], "W":[…], "W_fit":[…], "n":352,
      "k_ref_rad_per_m":100, "gamma2":3.61, "w2":7.8e-4,
      "fit_band_rad_per_m":[lo,hi], "fit_r2":0.96 }

This filters it for a log-log plot (``W`` in m⁴ vs ``K`` in rad/m): log axes need
strictly-positive, finite values, and some array entries may be ``null`` (NaN),
so they are dropped here.  Diagnostics read off the plot: where the data peels
off ``W_fit`` at high K = stereo noise floor; a flat/odd shape = ripples (the
radial spectrum assumes isotropy).

Pure numpy — no Qt, no QGIS — so it is unit-testable; the Qt tab does the plot.
"""
from __future__ import annotations

import numpy as np


def _arr(seq) -> np.ndarray:
    """Coerce a list (possibly with ``None``) to a float array (None→NaN)."""
    if seq is None:
        return np.array([], dtype=float)
    return np.array([np.nan if v is None else v for v in seq], dtype=float)


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def prepare_spectrum(spec: dict | None) -> dict | None:
    """Filter a ``spectrum`` object into plot-ready positive/finite arrays.

    Returns ``None`` when there is no usable spectrum, else a dict with:
    ``K``/``W`` (scatter points), ``K_fit``/``W_fit`` (the fit line),
    ``fit_band`` (``(lo, hi)`` or ``None``), and the scalars ``gamma2``, ``w2``,
    ``fit_r2``, ``k_ref``, ``n``.  All arrays are strictly positive and finite
    (safe for log-log).
    """
    if not isinstance(spec, dict):
        return None
    K = _arr(spec.get("K_rad_per_m"))
    W = _arr(spec.get("W"))
    Wfit = _arr(spec.get("W_fit"))
    if K.size == 0:
        return None

    # Scatter points: positive + finite in both K and W (log-log needs > 0).
    md = np.isfinite(K) & np.isfinite(W) & (K > 0) & (W > 0)
    Kd, Wd = K[md], W[md]

    # Fit line: positive + finite in K and W_fit (W_fit is aligned to K).
    if Wfit.size == K.size:
        mf = np.isfinite(K) & np.isfinite(Wfit) & (K > 0) & (Wfit > 0)
        Kf, Wf = K[mf], Wfit[mf]
    else:
        Kf, Wf = np.array([], dtype=float), np.array([], dtype=float)

    band = spec.get("fit_band_rad_per_m")
    if (isinstance(band, (list, tuple)) and len(band) == 2
            and band[0] is not None and band[1] is not None):
        lo, hi = float(band[0]), float(band[1])
        band = (lo, hi) if (lo > 0 and hi > 0) else None
    else:
        band = None

    return {
        "K": Kd, "W": Wd, "K_fit": Kf, "W_fit": Wf, "fit_band": band,
        "gamma2": _num(spec.get("gamma2")), "w2": _num(spec.get("w2")),
        "fit_r2": _num(spec.get("fit_r2")),
        "k_ref": _num(spec.get("k_ref_rad_per_m")), "n": spec.get("n"),
    }
