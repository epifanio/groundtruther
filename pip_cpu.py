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

from numba import jit, njit
import numba
import numpy as np


def read_mbes(pq):
    # Not ``pd.read_parquet``: the MBES table has a timestamp column, and
    # letting pandas convert one segfaults QGIS on macOS.  See
    # ``gt/pandas_safe.py``; ``epoch_us`` keeps this million-row table at 8
    # bytes a row.
    from groundtruther.gt import pandas_safe
    return pandas_safe.read_parquet(pq, temporal="epoch_us")


@jit(nopython=True)
def is_inside_sm(polygon, point):
    length = len(polygon)-1
    dy2 = point[1] - polygon[0][1]
    intersections = 0
    ii = 0
    jj = 1

    while ii < length:
        dy = dy2
        dy2 = point[1] - polygon[jj][1]

        # consider only lines which are not completely above/bellow/right from the point
        if dy*dy2 <= 0.0 and (point[0] >= polygon[ii][0] or point[0] >= polygon[jj][0]):

            # non-horizontal line
            if dy < 0 or dy2 < 0:
                F = dy*(polygon[jj][0] - polygon[ii][0]) / \
                    (dy-dy2) + polygon[ii][0]

                # if line is left from the point - the ray moving towards left, will intersect it
                if point[0] > F:
                    intersections += 1
                elif point[0] == F:  # point on line
                    return 2

            # point on upper peak (dy2=dx2=0) or horizontal line (dy=dy2=0 and dx*dx2<=0)
            elif dy2 == 0 and (point[0] == polygon[jj][0] or (dy == 0 and (point[0]-polygon[ii][0])*(point[0]-polygon[jj][0]) <= 0)):
                return 2

        ii = jj
        jj += 1

    # print 'intersections =', intersections
    return intersections & 1

# px = point_df['Easting'].values.get()


@njit(parallel=True)
def get_spatial_selection_cpu(points, polygon):
    ln = len(points)
    D = np.empty(ln, dtype=numba.boolean)
    for i in numba.prange(ln):
        D[i] = is_inside_sm(polygon, points[i])
    return D
