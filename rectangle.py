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