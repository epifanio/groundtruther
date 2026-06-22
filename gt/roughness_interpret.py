"""Plain-language interpretation of roughness metrics — stateless.

Turns the raw ``/seafloor/roughness`` response into the science-aware labels the
Metrics tab shows.  Calibration/fusion findings baked in here:

* ``gamma2`` (spectral exponent) is the **load-bearing** output — robust across
  matchers, separates substrate A vs E, top feature in the fused classifier. It
  is the hero metric.
* ``w2`` absolute is **not** reliable from stereo in general; trust is per-frame
  via ``w2_trustworthy`` (NOT a blanket "provisional"). Show ``w2_cm4`` (cm⁴,
  APL-UW/Jackson convention) gated by that flag. ``rms_height_mm`` gets the same
  gate (it inflates on turbid frames).
* Ripples-vs-bioturbation per frame via ``is_rippled`` / ``anisotropy`` /
  ``orientation_deg`` / ``ripple_wavelength_cm``.
* A small **indicative** substrate read off ``gamma2`` + ``rugosity`` (A/E).

Pure Python — no Qt, no QGIS — so it's unit-testable; the mixin renders it.
States returned alongside text: ``"ok"`` (calibrated/in-range, render green),
``"warn"`` (unreliable, render amber/red), ``"plain"`` (neutral/unknown).
"""
from __future__ import annotations

import math

# Unicode glyphs used in the labels.
G2 = "γ₂"          # γ₂
CM4 = "cm⁴"             # cm⁴
CHECK = "✓"             # ✓
WARN = "⚠"              # ⚠
DEG = "°"               # °

ALTITUDE_TOL_MM = 30.0       # |Δ vs Altimeter| within this → green QA


def num(v):
    """Best-effort float, or ``None`` for missing/NaN/inf/non-numeric."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if (math.isnan(f) or math.isinf(f)) else f


def substrate_hint(gamma2, rugosity) -> str | None:
    """Indicative substrate read from gamma2 + rugosity (NOT a classification).

    From the A/E calibration data:
    * Substrate-A (soft/fine, diffuse BS): gamma2 ~3.0, rugosity ~1.44
    * Substrate-E (firmer/coarser, specular): gamma2 ~3.4, rugosity ~1.19
    """
    g, r = num(gamma2), num(rugosity)
    if g is None or r is None:
        return None
    if g <= 3.1 and r >= 1.3:
        return "fine / bioturbated — Substrate-A-like"
    if g >= 3.3 and r <= 1.25:
        return "firmer / smoother — Substrate-E-like"
    return "intermediate"


def w2_display(result: dict) -> tuple[str, str]:
    """``(text, state)`` for w2 in cm⁴, gated by ``w2_trustworthy``."""
    w2 = num((result or {}).get("w2_cm4"))
    if w2 is None:
        return (f"w2 = —", "plain")
    val = f"{w2:.3g} {CM4}"
    trust = (result or {}).get("w2_trustworthy")
    if trust is True:
        return (f"w2 = {val}  {CHECK} calibrated (APL-UW Table-2 range)", "ok")
    if trust is False:
        return (f"w2 = {val}  {WARN} unreliable (matcher-limited — use "
                f"{G2})", "warn")
    return (f"w2 = {val}", "plain")


def rms_display(result: dict) -> tuple[str, str]:
    """``(text, state)`` for rms_height_mm, gated by ``w2_trustworthy``.

    rms inflates on turbid / matcher-limited frames, so it shares w2's trust.
    """
    rms = num((result or {}).get("rms_height_mm"))
    if rms is None:
        return ("rms height = —", "plain")
    val = f"{rms:.0f} mm"
    trust = (result or {}).get("w2_trustworthy")
    if trust is False:
        return (f"rms height = {val}  {WARN} unreliable "
                f"(turbid/matcher-limited)", "warn")
    if trust is True:
        return (f"rms height = {val}  {CHECK}", "ok")
    return (f"rms height = {val}", "plain")


def texture_text(result: dict) -> str:
    """Ripples-vs-bioturbation read for the current frame."""
    result = result or {}
    if result.get("is_rippled"):
        wl = num(result.get("ripple_wavelength_cm"))
        az = num(result.get("orientation_deg"))
        bits = []
        if wl is not None:
            bits.append(f"~{wl:.0f} cm crests")
        if az is not None:
            bits.append(f"@ {az:.0f}{DEG}")
        return "Rippled: " + " ".join(bits) if bits else "Rippled"
    aniso = num(result.get("anisotropy"))
    base = "Isotropic (bioturbated/featureless)"
    return f"{base} · anisotropy {aniso:.2f}" if aniso is not None else base


def altitude_delta_mm(altitude_mm, altimeter_m, tol_mm: float = ALTITUDE_TOL_MM):
    """``(delta_mm, in_tolerance)`` of service altitude vs metadata Altimeter.

    ``delta = altitude_mm - altimeter_m*1000``.  Returns ``(None, None)`` when
    either input is missing.
    """
    alt, am = num(altitude_mm), num(altimeter_m)
    if alt is None or am is None:
        return (None, None)
    delta = alt - am * 1000.0
    return (delta, abs(delta) <= tol_mm)


def w2_cm4_short(result: dict) -> tuple[str, str]:
    """Compact ``(text, state)`` for footers, e.g. ``w₂=0.07 cm⁴ ✓``."""
    w2 = num((result or {}).get("w2_cm4"))
    if w2 is None:
        return ("", "plain")
    trust = (result or {}).get("w2_trustworthy")
    flag = f" {CHECK}" if trust is True else (f" {WARN}" if trust is False else "")
    state = "ok" if trust is True else ("warn" if trust is False else "plain")
    return (f"w₂={w2:.3g} {CM4}{flag}", state)
