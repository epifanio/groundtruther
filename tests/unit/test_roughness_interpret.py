"""Unit tests for gt/roughness_interpret.py (pure label/interpretation logic)."""
import pytest

from groundtruther.gt import roughness_interpret as ri


# --- substrate hint ---------------------------------------------------------

def test_substrate_A_like():
    # gamma2 <= 3.1 and rugosity >= 1.3
    assert "Substrate-A-like" in ri.substrate_hint(3.0, 1.44)
    assert "Substrate-A-like" in ri.substrate_hint(2.33, 1.62)


def test_substrate_E_like():
    # gamma2 >= 3.3 and rugosity <= 1.25
    assert "Substrate-E-like" in ri.substrate_hint(3.4, 1.19)


def test_substrate_intermediate():
    assert ri.substrate_hint(2.85, 1.18) == "intermediate"   # neither rule
    assert ri.substrate_hint(3.2, 1.3) == "intermediate"


def test_substrate_missing():
    assert ri.substrate_hint(None, 1.4) is None
    assert ri.substrate_hint(3.0, None) is None
    assert ri.substrate_hint("x", 1.4) is None


# --- w2 display (trust-gated, cm^4) -----------------------------------------

def test_w2_trustworthy_true_green():
    text, state = ri.w2_display({"w2_cm4": 0.0427, "w2_trustworthy": True})
    assert state == "ok"
    assert "cm⁴" in text and "calibrated" in text and ri.CHECK in text


def test_w2_trustworthy_false_warn():
    text, state = ri.w2_display({"w2_cm4": 12.6, "w2_trustworthy": False})
    assert state == "warn"
    assert "unreliable" in text and ri.WARN in text and "γ₂" in text


def test_w2_unknown_trust_plain():
    text, state = ri.w2_display({"w2_cm4": 1.0})
    assert state == "plain" and ri.CHECK not in text and ri.WARN not in text


def test_w2_missing():
    text, state = ri.w2_display({})
    assert text == "w2 = —" and state == "plain"


# --- rms display (same gate) ------------------------------------------------

def test_rms_false_warn():
    text, state = ri.rms_display({"rms_height_mm": 74.0, "w2_trustworthy": False})
    assert state == "warn" and "74 mm" in text and "unreliable" in text


def test_rms_true_ok():
    text, state = ri.rms_display({"rms_height_mm": 20.0, "w2_trustworthy": True})
    assert state == "ok" and "20 mm" in text and ri.CHECK in text


def test_rms_missing():
    assert ri.rms_display({})[0] == "rms height = —"


# --- texture / ripples ------------------------------------------------------

def test_texture_rippled():
    t = ri.texture_text({"is_rippled": True, "ripple_wavelength_cm": 3.0,
                         "orientation_deg": 91.0})
    assert t.startswith("Rippled:") and "3 cm crests" in t and "91°" in t


def test_texture_isotropic_with_anisotropy():
    t = ri.texture_text({"is_rippled": False, "anisotropy": 0.08})
    assert "Isotropic" in t and "0.08" in t


def test_texture_isotropic_plain():
    assert ri.texture_text({"is_rippled": False}) == "Isotropic (bioturbated/featureless)"


# --- altitude delta ---------------------------------------------------------

def test_altitude_delta_in_tol():
    delta, ok = ri.altitude_delta_mm(2050.0, 2.04)   # 2050 - 2040 = 10 mm
    assert delta == pytest.approx(10.0) and ok is True


def test_altitude_delta_out_of_tol():
    delta, ok = ri.altitude_delta_mm(2219.5, 1.88)   # 2219.5 - 1880 = 339.5
    assert ok is False


def test_altitude_delta_missing():
    assert ri.altitude_delta_mm(None, 2.0) == (None, None)
    assert ri.altitude_delta_mm(2050, None) == (None, None)


# --- footer short -----------------------------------------------------------

def test_w2_cm4_short():
    text, state = ri.w2_cm4_short({"w2_cm4": 0.07, "w2_trustworthy": True})
    assert text.startswith("w₂=") and "cm⁴" in text and ri.CHECK in text and state == "ok"
    assert ri.w2_cm4_short({})[0] == ""


# --- mosaic summary ---------------------------------------------------------

def test_mosaic_summary_auto_to_pixel():
    s = ri.mosaic_summary({"mode_requested": "auto", "mode": "pixel",
                           "nav_overlap": 0.867,
                           "register": {"pixel_pairs": 5, "n_pairs": 6}})
    assert "auto: overlap 0.87 → pixel" in s
    assert "5/6 by content" in s


def test_mosaic_summary_auto_to_flat():
    s = ri.mosaic_summary({"mode_requested": "auto", "mode": "flat",
                           "nav_overlap": 0.41})
    assert s == "auto: overlap 0.41 → flat"


def test_mosaic_summary_explicit_mode():
    s = ri.mosaic_summary({"mode_requested": "ortho", "mode": "ortho"})
    assert s == "ortho"


def test_mosaic_summary_empty():
    assert ri.mosaic_summary({}) == ""
    assert ri.mosaic_summary(None) == ""


# --- mosaic register warning ------------------------------------------------

def test_mosaic_register_warning_low():
    t, q = ri.mosaic_register_warning({"register": {
        "quality": "low", "pixel_pairs": 0, "n_pairs": 10,
        "warning": "0/10 pairs registered — low texture, nav-placed"}})
    assert q == "low" and "low texture" in t


def test_mosaic_register_warning_none_adds_hint():
    t, q = ri.mosaic_register_warning({"register": {"quality": "none", "warning": ""}})
    assert q == "none" and "single frames" in t


def test_mosaic_register_warning_ok_and_absent():
    _, q = ri.mosaic_register_warning({"register": {"quality": "ok"}})
    assert q == "ok"
    assert ri.mosaic_register_warning({}) == ("", None)
    assert ri.mosaic_register_warning(None) == ("", None)
