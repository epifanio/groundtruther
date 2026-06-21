"""Unit tests for the stateless roughness client (gt/roughness_client.py).

No QGIS, no network — `requests.post` is monkeypatched.
"""
import json

import pytest
import requests

from groundtruther.gt import roughness_client as rc
from groundtruther.gt.roughness_client import RoughnessError

EP = "https://api.example.test"
KEY = "fgk_testkey"
FRAME = "201503.20150619.181140656.204627"

OK_PAYLOAD = {
    "quality": "ok", "gamma2": 2.4, "w2": 1.2e-4, "rms_height_mm": 3.1,
    "rugosity": 1.05, "altitude_mm": 2050.0, "matcher": "raft-stereo",
    "n_water": 1.34, "extent_mm": [0, 0, 500, 500],
}


class FakeResponse:
    def __init__(self, status=200, json_data=None, content=None, text=""):
        self.status_code = status
        self.ok = 200 <= status < 300
        self._json = json_data
        if content is not None:
            self.content = content
        elif json_data is not None:
            self.content = json.dumps(json_data).encode()
        else:
            self.content = b""
        self.text = text

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json


@pytest.fixture
def capture(monkeypatch):
    """Patch requests.post; capture the call and return a configurable response."""
    box = {"response": FakeResponse(json_data=OK_PAYLOAD), "calls": []}

    def fake_post(url, **kwargs):
        box["calls"].append({"url": url, **kwargs})
        return box["response"]

    monkeypatch.setattr(requests, "post", fake_post)
    return box


@pytest.fixture
def capture_get(monkeypatch):
    """Patch requests.get for health-probe tests."""
    box = {"response": FakeResponse(json_data={"status": "ok"}), "calls": []}

    def fake_get(url, **kwargs):
        box["calls"].append({"url": url, **kwargs})
        return box["response"]

    monkeypatch.setattr(requests, "get", fake_get)
    return box


# --- guards -----------------------------------------------------------------

def test_missing_frame_key_raises():
    with pytest.raises(RoughnessError, match="frame_key"):
        rc.roughness_for_frame("", endpoint=EP, api_key=KEY)


def test_missing_endpoint_raises():
    with pytest.raises(RoughnessError, match="endpoint"):
        rc.roughness_for_frame(FRAME, endpoint="", api_key=KEY)


def test_missing_key_raises():
    with pytest.raises(RoughnessError, match="key"):
        rc.roughness_for_frame(FRAME, endpoint=EP, api_key="")


# --- request building -------------------------------------------------------

def test_builds_url_auth_and_body(capture):
    rc.roughness_for_frame(FRAME + "/", api_key=KEY, endpoint=EP + "/")  # noqa
    rc.roughness_for_frame(FRAME, endpoint=EP + "/", api_key=KEY)
    call = capture["calls"][-1]
    assert call["url"] == f"{EP}/seafloor/roughness"    # trailing slash normalised
    assert call["headers"]["X-API-Key"] == KEY
    assert call["json"] == {"frame_key": FRAME}          # only the key by default


def test_custom_route(capture):
    rc.roughness_for_frame(FRAME, endpoint=EP, api_key=KEY, route="/v2/rough")
    assert capture["calls"][-1]["url"] == f"{EP}/v2/rough"


def test_optional_params_included(capture):
    rc.roughness_for_frame(FRAME, endpoint=EP, api_key=KEY,
                           res_mm=2.0, n_water=1.34, return_dem=True)
    body = capture["calls"][-1]["json"]
    assert body == {"frame_key": FRAME, "res_mm": 2.0,
                    "n_water": 1.34, "return_dem": True}


def test_return_dem_false_omitted(capture):
    rc.roughness_for_frame(FRAME, endpoint=EP, api_key=KEY, return_dem=False)
    assert "return_dem" not in capture["calls"][-1]["json"]


def test_geo_object_forwarded(capture):
    geo = {"easting": 1.0, "northing": 2.0, "heading_deg": 90.0, "epsg": 32619}
    rc.roughness_for_frame(FRAME, endpoint=EP, api_key=KEY, geo=geo)
    assert capture["calls"][-1]["json"]["geo"] == geo


def test_geo_omitted_when_none(capture):
    rc.roughness_for_frame(FRAME, endpoint=EP, api_key=KEY)
    assert "geo" not in capture["calls"][-1]["json"]


def test_output_flags_forwarded(capture):
    rc.roughness_for_frame(
        FRAME, endpoint=EP, api_key=KEY, dem_format="mm", dem_max_side=512,
        include_orthophoto=True, include_left_height=True, include_left_preview=True)
    body = capture["calls"][-1]["json"]
    assert body["dem_format"] == "mm"
    assert body["dem_max_side"] == 512
    assert body["include_orthophoto"] is True
    assert body["include_left_height"] is True
    assert body["include_left_preview"] is True


def test_output_flags_off_by_default(capture):
    rc.roughness_for_frame(FRAME, endpoint=EP, api_key=KEY)
    body = capture["calls"][-1]["json"]
    for k in ("dem_format", "dem_max_side", "include_orthophoto",
              "include_left_height", "include_left_preview"):
        assert k not in body


# --- direct fast-path -------------------------------------------------------

def test_direct_url_skips_auth(capture):
    rc.roughness_for_frame(FRAME, direct_url="http://127.0.0.1:7871/roughness")
    call = capture["calls"][-1]
    assert call["url"] == "http://127.0.0.1:7871/roughness"
    assert "X-API-Key" not in call["headers"]


def test_direct_url_needs_no_endpoint(capture):
    # No endpoint/api_key supplied — direct_url alone must work.
    out = rc.roughness_for_frame(FRAME, direct_url="http://127.0.0.1:7871/roughness")
    assert out["quality"] == "ok"


# --- response handling ------------------------------------------------------

def test_returns_parsed_dict(capture):
    out = rc.roughness_for_frame(FRAME, endpoint=EP, api_key=KEY)
    assert out["gamma2"] == 2.4
    assert out["matcher"] == "raft-stereo"


def test_non_ok_quality_is_not_an_error(capture):
    capture["response"] = FakeResponse(json_data={"quality": "insufficient_coverage",
                                                  "gamma2": None})
    out = rc.roughness_for_frame(FRAME, endpoint=EP, api_key=KEY)
    assert out["quality"] == "insufficient_coverage"
    assert out["gamma2"] is None


def test_http_error_raises_with_detail(capture):
    capture["response"] = FakeResponse(status=422, json_data={"detail": "bad frame"})
    with pytest.raises(RoughnessError) as exc:
        rc.roughness_for_frame(FRAME, endpoint=EP, api_key=KEY)
    assert exc.value.status == 422
    assert "bad frame" in str(exc.value)


def test_http_error_detail_list(capture):
    capture["response"] = FakeResponse(
        status=422, json_data={"detail": [{"msg": "field required", "loc": ["body"]}]})
    with pytest.raises(RoughnessError, match="field required"):
        rc.roughness_for_frame(FRAME, endpoint=EP, api_key=KEY)


def test_network_error_raises(monkeypatch):
    def boom(*a, **k):
        raise requests.exceptions.ConnectionError("down")
    monkeypatch.setattr(requests, "post", boom)
    with pytest.raises(RoughnessError, match="Cannot reach"):
        rc.roughness_for_frame(FRAME, endpoint=EP, api_key=KEY)


def test_non_json_body_raises(capture):
    capture["response"] = FakeResponse(status=200, content=b"<html>", text="<html>")
    with pytest.raises(RoughnessError, match="Non-JSON"):
        rc.roughness_for_frame(FRAME, endpoint=EP, api_key=KEY)


# --- helpers ----------------------------------------------------------------

def test_is_ok():
    assert rc.is_ok(OK_PAYLOAD) is True
    assert rc.is_ok({"quality": "insufficient_coverage"}) is False
    assert rc.is_ok(None) is False


def test_health_builds_url_and_auth(capture_get):
    out = rc.health(EP, KEY)
    call = capture_get["calls"][-1]
    assert call["url"] == f"{EP}/seafloor/health"
    assert call["headers"]["X-API-Key"] == KEY
    assert out == {"status": "ok"}


def test_health_error(capture_get):
    capture_get["response"] = FakeResponse(status=503, json_data={"detail": "down"})
    with pytest.raises(RoughnessError, match="down"):
        rc.health(EP, KEY)


def test_quality_message():
    assert rc.quality_message(OK_PAYLOAD) == ""
    assert "stereo coverage" in rc.quality_message({"quality": "insufficient_coverage"})
    assert "fit failed" in rc.quality_message({"quality": "spectrum_fit_failed"})
    assert rc.quality_message(None) == "no roughness"


# --- mosaic (mode A) --------------------------------------------------------

def test_mosaic_missing_reference_raises():
    with pytest.raises(RoughnessError, match="reference_key"):
        rc.mosaic_by_reference("", endpoint=EP, api_key=KEY)


def test_mosaic_builds_url_auth_and_body(capture):
    capture["response"] = FakeResponse(json_data={"mosaic_png_b64": "x"})
    rc.mosaic_by_reference(FRAME, window=5, endpoint=EP + "/", api_key=KEY)
    call = capture["calls"][-1]
    assert call["url"] == f"{EP}/seafloor/mosaic"
    assert call["headers"]["X-API-Key"] == KEY
    assert call["json"] == {"reference_key": FRAME, "window": 5, "mode": "flat"}


def test_mosaic_optional_params(capture):
    capture["response"] = FakeResponse(json_data={"mosaic_png_b64": "x"})
    rc.mosaic_by_reference(FRAME, window=3, mode="ortho", out_gsd_m=0.003,
                           epsg=32619, endpoint=EP, api_key=KEY)
    assert capture["calls"][-1]["json"] == {
        "reference_key": FRAME, "window": 3, "mode": "ortho",
        "out_gsd_m": 0.003, "epsg": 32619}


def test_mosaic_direct_url_skips_auth(capture):
    capture["response"] = FakeResponse(json_data={"mosaic_png_b64": "x"})
    rc.mosaic_by_reference(FRAME, direct_url="http://127.0.0.1:7871/mosaic")
    call = capture["calls"][-1]
    assert call["url"] == "http://127.0.0.1:7871/mosaic"
    assert "X-API-Key" not in call["headers"]


def test_mosaic_http_error_raises(capture):
    capture["response"] = FakeResponse(status=503, json_data={"detail": "GPU busy"})
    with pytest.raises(RoughnessError, match="GPU busy"):
        rc.mosaic_by_reference(FRAME, endpoint=EP, api_key=KEY)


def test_mosaic_new_controls_in_body(capture):
    capture["response"] = FakeResponse(json_data={"mosaic_png_b64": "x"})
    rc.mosaic_by_reference(FRAME, window=4, mode="ortho", out_gsd_m=0.0008,
                           epsg=32619, max_side=8192, interp="lanczos",
                           supersample=3, alpha=True, nodata=0,
                           endpoint=EP, api_key=KEY)
    assert capture["calls"][-1]["json"] == {
        "reference_key": FRAME, "window": 4, "mode": "ortho",
        "out_gsd_m": 0.0008, "epsg": 32619, "max_side": 8192,
        "interp": "lanczos", "supersample": 3, "alpha": True, "nodata": 0.0}


def test_mosaic_controls_omitted_when_unset(capture):
    capture["response"] = FakeResponse(json_data={"mosaic_png_b64": "x"})
    rc.mosaic_by_reference(FRAME, endpoint=EP, api_key=KEY)
    body = capture["calls"][-1]["json"]
    for k in ("max_side", "interp", "supersample", "alpha", "nodata"):
        assert k not in body
