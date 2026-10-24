# GroundTruther — a toolset for seafloor characterization
#
# Copyright (C) 2023-2026 Massimo Di Stefano <epiesasha@me.com>
# https://github.com/epifanio/groundtruther
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Unit tests for the pydantic configuration model (config_model.py)."""
import pytest
from pydantic import ValidationError

from groundtruther.config_model import HabcamSettings


def _valid_kwargs(tmp_path):
    meta = tmp_path / "meta.pq"
    meta.write_bytes(b"")
    return dict(
        HabCam={"imagepath": str(tmp_path), "imagemetadata": str(meta),
                "imageannotation": None},
        Mbes={"soundings": None},
        Export={"kmldir": str(tmp_path)},
        Processing={"gpu_avaibility": False,
                    "grass_api_endpoint": "https://api.fastgis.eu",
                    "grass_api_key": "fgk_abc"},
        Filesystem={"filemanager": None},
        Video=None,
    )


def test_valid_config(tmp_path):
    s = HabcamSettings(**_valid_kwargs(tmp_path))
    assert s.Processing.grass_api_key == "fgk_abc"
    assert str(s.Processing.grass_api_endpoint).startswith("https://api.fastgis.eu")


def test_grass_api_key_optional(tmp_path):
    kw = _valid_kwargs(tmp_path)
    kw["Processing"].pop("grass_api_key")
    s = HabcamSettings(**kw)
    assert s.Processing.grass_api_key is None


def test_nonexistent_imagepath_rejected(tmp_path):
    kw = _valid_kwargs(tmp_path)
    kw["HabCam"]["imagepath"] = str(tmp_path / "does-not-exist")
    with pytest.raises(ValidationError):
        HabcamSettings(**kw)


def test_imagemetadata_must_be_a_file(tmp_path):
    kw = _valid_kwargs(tmp_path)
    kw["HabCam"]["imagemetadata"] = str(tmp_path)   # a directory, not a file
    with pytest.raises(ValidationError):
        HabcamSettings(**kw)
