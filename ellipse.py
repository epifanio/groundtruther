import math
import re
import string
import sys

import numpy as np
from pyproj import Transformer
from osgeo import ogr

# TODO:
# port to GPU/numba ?


def getEllipseCoords(pt, sma, smi, azi, in_proj=4326, out_proj=4326):
    if in_proj != 4326:
        transformer = Transformer.from_crs(f"epsg:{in_proj}", "epsg:4326")
        lon, lat = transformer.transform(pt[0], pt[1])
    else:
        lon = pt[0]
        lat = pt[1]
    sma = 0.000539957 * sma
    smi = 0.000539957 * smi
    TPI = math.pi * 2.0
    PI_2 = math.pi / 2.0
    DG2NM = 60.0  # Degrees on the Earth's Surface to NM
    c = []
    cnt = 0
    if smi < 0.0005:
        smi = 0.0005
    if sma < 0.0005:
        sma = 0.0005
    center_lat = math.radians(lat)
    center_lon = math.radians(lon)
    sma = math.radians(sma / DG2NM)
    smi = math.radians(smi / DG2NM)
    azi = math.radians(azi)
    size = 512
    angle = 18.0 * smi / sma
    if angle < 1.0:
        minimum = angle
    else:
        minimum = 1.0
    maxang = math.pi / 6 * minimum
    while azi < 0:
        azi += TPI
    while azi > math.pi:
        azi -= math.pi
    slat = math.sin(center_lat)
    clat = math.cos(center_lat)
    ab = sma * smi
    a2 = sma * sma
    b2 = smi * smi
    delta = ab * math.pi / 30.0
    o = azi
    while True:
        sino = math.sin(o - azi)
        coso = math.cos(o - azi)
        if o > math.pi and o < TPI:
            sgn = -1.0
            azinc = TPI - o
        else:
            sgn = 1.0
            azinc = o
        rad = ab / math.sqrt(a2 * sino * sino + b2 * coso * coso)
        sinr = math.sin(rad)
        cosr = math.cos(rad)
        acos_val = cosr * slat + sinr * clat * math.cos(azinc)
        if acos_val > 1.0:
            acos_val = 1.0
        elif acos_val < -1.0:
            acos_val = -1.0
        tmplat = math.acos(acos_val)
        acos_val = (cosr - slat * math.cos(tmplat)) / (clat * math.sin(tmplat))
        if acos_val > 1.0:
            acos_val = 1.0
        elif acos_val < -1.0:
            acos_val = -1.0
        tmplon = math.acos(acos_val)
        tmplat = math.degrees(PI_2 - tmplat)
        tmplon = math.degrees(center_lon + sgn * tmplon)
        c.append([tmplon, tmplat])
        cnt += 1
        delo = delta / (rad * rad)
        if maxang < delo:
            delo = maxang
        o += delo
        if (o >= TPI + azi + delo / 2.0) or (cnt >= size):
            break
    if c[cnt - 1][0] != c[0][0] or c[cnt - 1][1] != c[0][1]:
        c[cnt - 1] = [c[0][0], c[0][1]]
    cc = np.array(c)
    if out_proj != 4326:
        transformer = Transformer.from_crs(f"epsg:4326", f"epsg:{out_proj}")
        xx, yy = transformer.transform(cc[:, 1], cc[:, 0])
        cc = np.vstack((xx, yy)).T
    return cc
