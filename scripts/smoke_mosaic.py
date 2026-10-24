#!/usr/bin/env python3
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

"""Smoke-test mosaic mode A against the live roughness service — no QGIS.

Calls the same client the plugin uses, writes the returned mosaic to a GeoTIFF
(EPSG:32619), and prints n_frames / frames_skipped so you can confirm the
round-trip + georeferencing before testing the full UI.

Run with GDAL + Pillow available (e.g. QGIS's python, or a gdal-enabled env):

  # direct fast-path (GT on the GPU host):
  ROUGHNESS_DIRECT_URL=http://127.0.0.1:7871/mosaic \
      python3 scripts/smoke_mosaic.py <reference_key> [window]

  # or via the FastGIS tunnel:
  ROUGHNESS_ENDPOINT=https://api... ROUGHNESS_API_KEY=fgk_... \
      python3 scripts/smoke_mosaic.py <reference_key> [window]

reference_key defaults to the INTERFACE.md example; window defaults to 5.
"""
import base64
import io
import os
import sys

import numpy as np

from groundtruther.gt import roughness_client as rc
from groundtruther.gt import roughness_geo

ref = sys.argv[1] if len(sys.argv) > 1 else "201503.20150619.210859731.268197"
window = int(sys.argv[2]) if len(sys.argv) > 2 else 5

res = rc.mosaic_by_reference(
    ref, window=window, mode="flat", out_gsd_m=0.003, epsg=32619,
    endpoint=os.environ.get("ROUGHNESS_ENDPOINT"),
    api_key=os.environ.get("ROUGHNESS_API_KEY"),
    direct_url=os.environ.get("ROUGHNESS_DIRECT_URL"))

print("n_frames      :", res.get("n_frames"))
print("frames_skipped:", res.get("frames_skipped"))
print("mode / epsg   :", res.get("mode"), "/", res.get("epsg"))
print("shape         :", res.get("shape"))
print("geotransform  :", res.get("geotransform"))

png = res.get("mosaic_png_b64")
if not png:
    sys.exit("ERROR: response had no mosaic_png_b64")
from PIL import Image  # noqa: E402  (only needed for the standalone decode)
img = np.array(Image.open(io.BytesIO(base64.b64decode(png))))
print("decoded image :", img.shape, img.dtype)

out = f"/tmp/mosaic_{ref.split('.')[-1]}.tif"
roughness_geo.write_geotiff(img[..., :3], res["geotransform"], res["epsg"], out)
print("wrote         :", out, "  → open in QGIS or `gdalinfo`")
