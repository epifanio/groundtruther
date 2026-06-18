"""Opt-in integration tests against the live FastGIS GRASS API.

These hit `https://api.fastgis.eu` (or $GROUNDTRUTHER_API_URL) and require a key.
They are skipped unless GROUNDTRUTHER_API_KEY is set:

    GROUNDTRUTHER_API_KEY=fgk_... .venv/bin/pytest tests/integration -m integration

The create/delete test makes (and removes) a throwaway environment.
"""
import os
import uuid

import pytest

from groundtruther.gt import grass_api as g
from groundtruther.gt.grass_api import GrassApiError

API_KEY = os.environ.get("GROUNDTRUTHER_API_KEY")
API_URL = os.environ.get("GROUNDTRUTHER_API_URL", "https://api.fastgis.eu")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not API_KEY, reason="set GROUNDTRUTHER_API_KEY to run live tests"),
]


def test_whoami():
    me = g.whoami(API_URL, API_KEY)
    assert isinstance(me, dict) and (me.get("username") or me.get("id"))


def test_list_modules_nonempty():
    mods = g.list_modules(API_URL, API_KEY)
    assert isinstance(mods, list) and len(mods) > 0
    assert all("name" in m for m in mods[:5])


def test_describe_module_geomorphon():
    schema = g.describe_module(API_URL, API_KEY, "r.geomorphon")
    names = {p["name"] for p in schema.get("parameters", [])}
    assert "elevation" in names


def test_create_use_delete_env():
    loc = f"gt_pytest_{uuid.uuid4().hex[:8]}"
    env = g.create_env_epsg(API_URL, API_KEY, epsg=32619, location=loc, persist=True)
    env_id = env["env_id"]
    try:
        ge = g.gisenv(API_URL, API_KEY, env_id)
        assert ge.get("LOCATION_NAME") == loc
        region = g.set_region(API_URL, API_KEY, env_id,
                              north=1000, south=0, east=1000, west=0, res=10)
        assert "region" in region
        assert g.list_maps(API_URL, API_KEY, env_id, type="raster") == []
    finally:
        g.delete_env(API_URL, API_KEY, env_id)
