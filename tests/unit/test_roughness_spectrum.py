"""Unit tests for gt/roughness_spectrum.py (stateless spectrum prep)."""
import numpy as np
import pytest

from groundtruther.gt import roughness_spectrum as rs


SPEC = {
    "K_rad_per_m": [1.0, 10.0, 100.0, 1000.0],
    "W": [1e-2, 1e-3, 1e-4, 1e-5],
    "W_fit": [2e-2, 2e-3, 2e-4, 2e-5],
    "n": 4, "k_ref_rad_per_m": 100.0, "gamma2": 2.4, "w2": 7.8e-4,
    "fit_band_rad_per_m": [10.0, 500.0], "fit_r2": 0.96,
}


def test_prepare_basic():
    out = rs.prepare_spectrum(SPEC)
    assert out["K"].tolist() == [1.0, 10.0, 100.0, 1000.0]
    assert out["W_fit"].size == 4
    assert out["fit_band"] == (10.0, 500.0)
    assert out["gamma2"] == 2.4 and out["w2"] == pytest.approx(7.8e-4)
    assert out["fit_r2"] == 0.96 and out["k_ref"] == 100.0 and out["n"] == 4


def test_filters_null_and_nonpositive():
    spec = {
        "K_rad_per_m": [1.0, None, -5.0, 10.0, 0.0],
        "W":           [1e-2, 1e-3, 1e-3, None, 1e-4],
        "W_fit":       [2e-2, 2e-3, 2e-3, 2e-4, 2e-4],
    }
    out = rs.prepare_spectrum(spec)
    # only K=1.0 survives in the scatter (others null/neg/zero in K or W)
    assert out["K"].tolist() == [1.0]
    assert out["W"].tolist() == [1e-2]
    # all arrays strictly positive + finite
    assert np.all(out["K"] > 0) and np.all(np.isfinite(out["W"]))


def test_fit_line_filtered_independently():
    spec = {
        "K_rad_per_m": [1.0, 10.0, 100.0],
        "W":           [1e-2, 1e-3, 1e-4],
        "W_fit":       [2e-2, None, -1.0],   # only first is plottable
    }
    out = rs.prepare_spectrum(spec)
    assert out["K_fit"].tolist() == [1.0]
    assert out["W_fit"].tolist() == [2e-2]


def test_missing_w_fit_gives_empty_fit():
    spec = {"K_rad_per_m": [1.0, 10.0], "W": [1.0, 0.1]}
    out = rs.prepare_spectrum(spec)
    assert out["K"].size == 2
    assert out["K_fit"].size == 0 and out["W_fit"].size == 0


def test_bad_band_becomes_none():
    assert rs.prepare_spectrum({**SPEC, "fit_band_rad_per_m": [None, 5]})["fit_band"] is None
    assert rs.prepare_spectrum({**SPEC, "fit_band_rad_per_m": [0, 5]})["fit_band"] is None
    assert rs.prepare_spectrum({**SPEC, "fit_band_rad_per_m": [5]})["fit_band"] is None


def test_none_and_empty():
    assert rs.prepare_spectrum(None) is None
    assert rs.prepare_spectrum({}) is None
    assert rs.prepare_spectrum({"K_rad_per_m": []}) is None


def test_all_null_arrays_yield_empty_scatter():
    spec = {"K_rad_per_m": [None, None], "W": [None, None]}
    out = rs.prepare_spectrum(spec)
    assert out is not None and out["K"].size == 0
