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

import numpy as np
from pyproj import Proj

def getRectangleCoords(pt, d1, d2, in_proj='proj=utm +zone=19 +datum=WGS84 +units=m +no_defs', utmzone=None, ellps='WGS84', preserve_units=False):
    if in_proj:
        myProj = Proj("proj=utm +zone=19 +datum=WGS84 +units=m +no_defs")
    else:
        myProj = Proj(proj="utm", zone=utmzone, ellps="WGS84", preserve_units=False)
    #myProj = Proj(in_proj)
    x, y = myProj(pt[0], pt[1])
    
    ulx = x - d1/2.0
    uly = y + d2/2.0
    
    urx = x + d1/2.0
    ury = uly
    
    lrx = urx
    lry = y - d2/2.0
    
    llx = ulx
    lly = lry
    
    geom_x = [ulx,
            urx,
            lrx,
            llx]
    geom_y = [uly,
            ury,
            lry,
            lly]
    geom = myProj(geom_x, geom_y, inverse=True)
    return geom