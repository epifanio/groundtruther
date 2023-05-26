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
        print("invalid field name for Easting/Northing parameters")
        point_selection_index = []
    return point_selection_index
