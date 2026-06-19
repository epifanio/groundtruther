# Image Browser

Browse large collections of georeferenced seafloor images spatially and by index,
with the map and the imagery kept in sync.

<figure markdown>
  <!-- TODO: replace src with assets/img/image-browser-1.png -->
  ![Image Browser dock](../assets/img/placeholder.svg){ width="900" }
  <figcaption>The Image Browser dock: viewer, navigation, and metadata panel.</figcaption>
</figure>

## What it does

- Loads a per-image **metadata table** (Parquet) and builds a spatial index
  (KD-tree) over the image positions, so the nearest image to any location is
  found instantly.
- Displays the current image in a fast `pyqtgraph` viewer with an **LRU cache**
  for smooth back-and-forth navigation.
- Shows a **metadata panel** for the current image (position, depth, altimeter,
  field-of-view, mm/pixel, salinity/temperature, …).
- Overlays **bounding-box annotations** (e.g. detector output) with a tunable
  **confidence threshold**.

## How to use

- **Navigate** with the forward/back buttons, the **index slider**, or the index
  spin-box; the **step** control sets how many images each press advances.
- **Click the map** (image-query tool) to jump to the image nearest that point.
- Enable **Zoom-to** so the map recenters on each image as you browse. The
  zoom control is a **map scale (1:N)** — larger numbers zoom out — so it behaves
  the same whether your project is in metres or degrees.
- Adjust the **annotation confidence** spin-box to show/hide detections below a
  threshold.

<figure markdown>
  <!-- TODO: replace src with assets/img/image-browser-2.png -->
  ![Annotations over an image](../assets/img/placeholder.svg){ width="900" }
  <figcaption>Bounding-box annotations with a confidence threshold.</figcaption>
</figure>

## Inputs (Settings → HabCam)

| Setting | What it is |
|---|---|
| `imagepath` | Folder of image files (JPEG). |
| `imagemetadata` | Per-image metadata table (Parquet) — must include image name, longitude, latitude (plus depth, FOV, etc.). |
| `imageannotation` | *Optional* CSV mapping image names to bounding boxes + species + confidence. |

!!! tip
    The map marker placed at the current image position uses the active project
    CRS; coordinates from the metadata are treated as WGS-84 and reprojected as
    needed.
