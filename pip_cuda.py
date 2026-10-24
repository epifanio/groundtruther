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

import cuspatial
import cudf


# cudf.read_parquet
# refresh_settings 159
# get_point 235

# cuspatial.pip
# get_cuspatial_selection 377

# px point_df[self.xutm_field].values,
# py point_df[self.yutm_field].values,

def read_mbes(pq):
    return cudf.read_parquet(pq)


def get_spatial_selection_gpu(px, py, xx, yy):
    try:
        result = cuspatial.point_in_polygon(
            px,
            py,
            cudf.Series([0], index=["geom"]),
            cudf.Series([0], name="r_pos", dtype="int32"),
            xx,
            yy,
        )
        point_selection_index = result["geom"]
    except KeyError:
        point_selection_index = []  # invalid field name for Easting/Northing
    return point_selection_index
