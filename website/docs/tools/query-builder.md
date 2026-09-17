# Acoustic Query Builder

Interrogate MBES products — backscatter and bathymetric derivatives — under
points and sampling shapes, and summarise their distributions. This is where the
acoustic side of the "ground-truthing" happens.

<figure markdown>
  <!-- TODO: replace src with assets/img/query-builder-1.png -->
  ![Acoustic Query Builder](../assets/img/placeholder.svg){ width="900" }
  <figcaption>Querying backscatter / derivatives under a sampling shape.</figcaption>
</figure>

## What it does

- **Point query:** click the map to read the value(s) of selected GRASS raster
  layers (backscatter, slope, geomorphons, …) at that location, via the
  [GRASS/FastGIS](grass-fastgis.md) `sample` endpoint (the server reprojects your
  click as needed).
- **Spatial selection:** draw a sampling shape and select the MBES soundings that
  fall inside it. Point-in-polygon testing runs over a soundings **Parquet** table
  with a fast `numba`-accelerated routine (with an optional GPU/`cuspatial` path).
- **Distributions:** visualise the selected values (e.g. backscatter angular
  response / density) with `plotnine`/`matplotlib`, ready to compare against the
  optical evidence.

## How to use

1. In the GRASS toolbox, **select an environment** and choose which raster layers
   to query.
2. Use the **point-query** map tool to read values at a click, or draw a
   **sampling shape** to select soundings within it.
3. Review the returned values / plots; results can feed into the
   [Report Builder](report-builder.md).

## Inputs (Settings → Mbes)

| Setting | What it is |
|---|---|
| `soundings` | MBES soundings table (Parquet) used for spatial selection. |
| `reference_surface` | *Optional* GeoTIFF DEM. When set, the 3-D viewer clips **this raster** to the sampling shape instead of gridding the selected soundings; it falls back to the soundings surface if the file is missing or unreadable. |

Column-by-column — including how the backscatter field is chosen and what the
port/starboard/fold beam filter does:
**[MBES soundings](../data-model/mbes-soundings.md)**.

GRASS raster layers (backscatter, derivatives) live in the active GRASS
environment — see the [GRASS / FastGIS toolbox](grass-fastgis.md).

!!! tip "Column names are configurable"
    Easting, Northing, Longitude and Latitude are read from **editable text
    fields** in the query builder, so a table using different names works without
    any code change. If one of the four is missing, the spatial tools stay
    disabled and the missing names are logged to the `GroundTruther` message-log
    tab.
