"""Unit tests for the stateless FastGIS GRASS client (gt/grass_api.py).

No QGIS, no network — `requests` is monkeypatched.
"""
import json

import pytest
import requests

from groundtruther.gt import grass_api as g
from groundtruther.gt.grass_api import GrassApiError

EP = "https://api.example.test"
KEY = "fgk_testkey"


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
    """Patch requests.request; capture the call and return a configurable response."""
    box = {"response": FakeResponse(json_data={}), "calls": []}

    def fake_request(method, url, **kwargs):
        box["calls"].append({"method": method, "url": url, **kwargs})
        return box["response"]

    monkeypatch.setattr(requests, "request", fake_request)
    return box


# --- guards -----------------------------------------------------------------

def test_missing_endpoint_raises():
    with pytest.raises(GrassApiError, match="endpoint"):
        g.list_envs("", KEY)


def test_missing_key_raises():
    with pytest.raises(GrassApiError, match="key"):
        g.list_envs(EP, "")


# --- request building -------------------------------------------------------

def test_request_builds_url_and_auth_header(capture):
    capture["response"] = FakeResponse(json_data={"environments": []})
    g.list_envs(EP + "/", KEY)              # trailing slash should be normalised
    call = capture["calls"][-1]
    assert call["method"] == "GET"
    assert call["url"] == f"{EP}/grass/env"
    assert call["headers"]["X-API-Key"] == KEY
    assert call["headers"]["accept"] == "application/json"


def test_json_body_sets_content_type(capture):
    capture["response"] = FakeResponse(json_data={"env_id": "x"})
    g.set_region(EP, KEY, "e1", north=1, south=0, east=1, west=0)
    call = capture["calls"][-1]
    assert call["json"]["north"] == 1 and call["json"]["west"] == 0
    assert call["headers"]["Content-Type"] == "application/json"


# --- error handling ---------------------------------------------------------

def test_http_4xx_raises_with_detail_and_status(capture):
    capture["response"] = FakeResponse(401, json_data={"detail": "invalid or revoked API key"})
    with pytest.raises(GrassApiError) as ei:
        g.list_envs(EP, KEY)
    assert ei.value.status == 401
    assert "invalid or revoked" in ei.value.detail


def test_422_detail_list_is_joined(capture):
    capture["response"] = FakeResponse(
        422, json_data={"detail": [{"msg": "field required"}, {"msg": "bad value"}]})
    with pytest.raises(GrassApiError) as ei:
        g.list_envs(EP, KEY)
    assert "field required" in ei.value.detail and "bad value" in ei.value.detail


def test_network_error_raises(monkeypatch):
    def boom(*a, **k):
        raise requests.exceptions.ConnectionError("down")
    monkeypatch.setattr(requests, "request", boom)
    with pytest.raises(GrassApiError, match="Cannot reach"):
        g.list_envs(EP, KEY)


def test_empty_body_returns_none(capture):
    capture["response"] = FakeResponse(200, content=b"")
    assert g.delete_env(EP, KEY, "e1") is None


# --- response unwrapping ----------------------------------------------------

def test_list_envs_unwraps(capture):
    capture["response"] = FakeResponse(json_data={"environments": [{"env_id": "a"}]})
    assert g.list_envs(EP, KEY) == [{"env_id": "a"}]


def test_gisenv_unwraps_variables(capture):
    capture["response"] = FakeResponse(json_data={"variables": {"MAPSET": "PERMANENT"}})
    assert g.gisenv(EP, KEY, "e1") == {"MAPSET": "PERMANENT"}


def test_list_maps_params_and_unwrap(capture):
    capture["response"] = FakeResponse(json_data={"items": ["dem", "slope"]})
    out = g.list_maps(EP, KEY, "e1", type="raster", pattern="d*")
    call = capture["calls"][-1]
    assert call["url"].endswith("/grass/env/e1/general/list")
    assert call["params"]["type"] == "raster" and call["params"]["pattern"] == "d*"
    assert out == ["dem", "slope"]


def test_reproject_unwraps_points(capture):
    capture["response"] = FakeResponse(json_data={"points": [{"x": 1, "y": 2}]})
    out = g.reproject(EP, KEY, "e1", [{"x": 0, "y": 0}], "EPSG:4326", "EPSG:32619")
    assert out == [{"x": 1, "y": 2}]


# --- request shapes ---------------------------------------------------------

def test_set_region_requires_a_param():
    with pytest.raises(GrassApiError, match="at least one region parameter"):
        g.set_region(EP, KEY, "e1")


def test_submit_task_body(capture):
    capture["response"] = FakeResponse(json_data={"task_id": "t1", "state": "PENDING"})
    g.submit_task(EP, KEY, "e1", "r.geomorphon",
                  params={"elevation": "dem"}, flags=["overwrite"])
    body = capture["calls"][-1]["json"]
    assert body == {"module": "r.geomorphon",
                    "flags": ["overwrite"], "params": {"elevation": "dem"}}


def test_sample_body(capture):
    capture["response"] = FakeResponse(json_data={"results": {"raster": []}})
    g.sample(EP, KEY, "e1", layers=["dem"], point={"x": 1, "y": 2}, crs="EPSG:4326")
    body = capture["calls"][-1]["json"]
    assert body["layers"] == ["dem"]
    assert body["point"] == {"x": 1, "y": 2}
    assert body["crs"] == "EPSG:4326"


def test_describe_module_unwraps_schema(capture):
    capture["response"] = FakeResponse(json_data={"schema": {"module": "r.slope.aspect"}})
    assert g.describe_module(EP, KEY, "r.slope.aspect") == {"module": "r.slope.aspect"}


# --- WCS GeoTIFF (MIME-wrapped) ---------------------------------------------

def test_wcs_geotiff_strips_mime_prefix(monkeypatch):
    tiff = b"II*\x00" + b"\x08\x00\x00\x00rest-of-tiff"
    wrapped = (b"Content-Disposition: INLINE; filename=out.tif\r\n\r\n" + tiff)

    def fake_get(url, **kwargs):
        assert kwargs["params"]["REQUEST"] == "GetCoverage"
        assert kwargs["headers"]["X-API-Key"] == KEY
        return FakeResponse(200, content=wrapped)
    monkeypatch.setattr(requests, "get", fake_get)

    out = g.wcs_geotiff(EP, KEY, "e1", "bathy")
    assert out == tiff
    assert out[:4] == b"II*\x00"


def test_wcs_geotiff_non_tiff_raises(monkeypatch):
    monkeypatch.setattr(requests, "get",
                        lambda url, **k: FakeResponse(200, content=b"not a tiff at all"))
    with pytest.raises(GrassApiError, match="not a GeoTIFF"):
        g.wcs_geotiff(EP, KEY, "e1", "bathy")
