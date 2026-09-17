# HabCam image metadata

`HabCam.imagemetadata` — the table that drives the
[Image Browser](../tools/image-browser.md), the map lookup, the metadata panel
and every position GroundTruther sends to a service.

- **Format:** Apache **Parquet** (read with `pandas.read_parquet`; the file
  extension does not matter — `.pq` and `.parquet` are both fine).
- **One row per image.**
- **Index:** a `DatetimeIndex` — the acquisition time of each frame. The metadata
  panel's **Time** row displays it, so a table indexed by something else will
  show a blank there but is otherwise usable.
- **Reference file:** the sample dataset's `projectdata.pq`
  ([Zenodo 7995674](https://zenodo.org/records/7995674)) — 123 394 rows,
  38 columns. The tables below describe exactly that file.

---

## Positioning: read this first

The table carries **three different horizontal positions**, and they are metres
apart. Choosing the wrong one silently misplaces every sample you take.

| Position | Columns | What it is | Use it? |
|---|---|---|---|
| **Calibrated USBL fix** | `Xutm` + `dx`, `Yutm` + `dy` | The measured acoustic fix of the towed HabCam on the seabed. **This is what GroundTruther uses everywhere.** | ✅ **Yes** |
| Layback *model* | `Xutm_adj`, `Yutm_adj` (= `habcam_lon`/`habcam_lat` projected) | A modelled tow position, not a measurement. Verified to sit ≈ 2.5 m (median) from the USBL fix. | ⚠️ Fallback only |
| Ship GPS | `sXutm`, `sYutm` (and `x`, `y`, `vessel_lon`, `vessel_lat`) | The **surface vessel**. The HabCam trails it by ~150 m along the cable. | ❌ **Never** a seafloor position |

!!! danger "`sXutm` / `sYutm` is not where the camera is"
    It is where the *ship* is. In the sample dataset the median separation
    between the ship and the HabCam fix is **≈ 148 m** — larger than most
    sampling shapes. A backscatter sample taken at the ship position describes a
    patch of seabed the camera never saw.

**How GroundTruther applies this.** At load time the plugin computes
`easting = Xutm + dx`, `northing = Yutm + dy`, projects it from
`Roughness.epsg` (default EPSG:32619) to WGS-84, and stores the result as two
extra columns, `usbl_lon` / `usbl_lat`. Those drive **one canonical position**
for everything: the KD-tree nearest-image lookup, the red map marker, the KMZ
export, the query builder's sampling centre, and the `geo` object sent to the
roughness service. If `Xutm`/`Yutm` are absent the plugin falls back to
`habcam_lon` / `habcam_lat` throughout — consistent, just less accurate.

---

## Required columns

Without these the plugin cannot do its job.

| Column | dtype | Meaning | Used for |
|---|---|---|---|
| `Imagename` | string | The frame identifier, **without an extension** — e.g. `201503.20150619.181140656.204627`. Encodes cruise, date, timestamp and a frame counter. | Resolving the image file on disk (`<name>.jpg`, `.png`, …, or `<name>_orig.*` for stereo deliveries); joining the annotation CSV; the `frame_key` sent to the roughness service. |
| `habcam_lon`, `habcam_lat` | float64 | HabCam position in WGS-84 decimal degrees (the layback model). | The fallback position for the KD-tree, the map marker and the sampling centre when the USBL columns are missing. |

## Positioning columns

| Column | dtype | Units | Meaning |
|---|---|---|---|
| `Xutm`, `Yutm` | float64 | m (projected CRS) | The **base** position the USBL offset is applied to. Exactly equal to `Longitude`/`Latitude` projected into EPSG:32619, and piecewise-constant across consecutive frames (one value per navigation fix). |
| `dx`, `dy` | float64 | m | The horizontal offset from the base position to the HabCam seabed fix. Magnitude equals `distance`, direction equals `bearing`. Typically 30–200 m — this is the tow layback, not a small lever-arm correction. |
| `Xutm_adj`, `Yutm_adj` | float64 | m (EPSG:32619) | `habcam_lon` / `habcam_lat` projected — the layback *model*. The query builder uses these to select images inside a sampling shape **only** when `Xutm`/`dx` are absent. |
| `sXutm`, `sYutm` | float64 | m (projected CRS) | Ship GPS position. Not read by the plugin. |
| `x`, `y` | float64 | m (projected CRS) | `vessel_lon` / `vessel_lat` projected. A second surface-vessel position series. Not read by the plugin. |
| `vessel_lon`, `vessel_lat` | float64 | ° WGS-84 | Surface-vessel position. Not read by the plugin. |
| `Longitude`, `Latitude` | float64 | ° WGS-84 | The WGS-84 form of `Xutm`/`Yutm` (verified: they project onto each other exactly). Shown in the metadata panel and included in the report summary. |
| `distance` | float64 | m | Length of the (`dx`, `dy`) offset vector. |
| `bearing` | float64 | ° (−180…180) | Direction of the (`dx`, `dy`) offset vector — ship **→** HabCam, i.e. *astern*. GroundTruther derives the roughness service's `heading_deg` from it by **reversing it** (`bearing + 180`) when there is no `Heading` column — see the note below. |
| `location` | string | — | `Point(<habcam_lon> <habcam_lat>)`, a WKT-like restatement of the HabCam position. Not read by the plugin. |

!!! note "`Heading` vs `bearing` — not two names for one thing"
    The roughness georeferencing needs a **platform heading**. GroundTruther uses
    a `Heading` column as it stands, and if the table has none — as the sample
    dataset does not — derives the heading from `bearing` **reversed**.

    `bearing` is not an attitude. It is the direction of the (`dx`, `dy`) layback
    offset, from the ship to the body it tows ~148 m behind it, so it points
    **astern** — roughly 180° from the course being made good (median |`bearing`
    − course over ground| ≈ 173–178° across the survey). The service rotates each
    frame so that image bottom→top is `heading_deg`, and the camera's image-up
    points **forward** along the tow, so the heading is `bearing + 180`.

    How that was settled: seabed content scrolls **down** between consecutive
    frames — 60 of 60 confident template matches, by ≈ 478 mm per frame against
    an independent prediction of ≈ 489 mm from speed × interval. Rotating that
    measured image shift into ground coordinates and comparing it with the course
    over ground taken independently from the nav gives a median error of
    **175°** for `heading = bearing` and **4.9°** for `heading = bearing + 180`.
    Only one of the two reproduces the track the vehicle actually followed.

    That ~5° residual — camera yaw relative to the track, USBL noise, cross-track
    drift — is also **how accurate the derived heading is**, so it bounds how well
    a single frame's raster can be expected to align. Leave `heading_offset_deg`
    at 0; it is a residual mount fine-tune, not the place for this.

    If your own table has a true vehicle heading, name the column `Heading` and it
    will be preferred automatically.

!!! warning "Rasters exported before this was fixed are rotated 180°"
    Until [#31](https://github.com/epifanio/groundtruther/issues/31) GroundTruther
    sent `bearing` unchanged, so every georeferenced micro-DEM, orthophoto and
    nav-placed mosaic it produced is **rotated 180° about its own centre**.
    Positions are unaffected. Regenerate anything exported earlier.

    The roughness service makes the same assumption for the mosaics where **it**
    pulls the nav ([stereo-roughness#1](https://github.com/epifanio/stereo-roughness/issues/1)),
    and GroundTruther deliberately does not compensate for that from the client —
    doing so would double-correct once the service is fixed. Until then a
    roughness raster and a service-side mosaic of the same patch disagree with
    each other by 180°.

## Depth and altitude

Verified relation in the sample data: `V_Depth + Altimeter ≈ Water_Depth`.

| Column | dtype | Units | Meaning |
|---|---|---|---|
| `V_Depth` | float64 | m | Vehicle depth below the surface. |
| `Altimeter` | float64 | m | Vehicle altitude above the seabed. Also the QA cross-check for the roughness service's reported `altitude_mm`. |
| `Water_Depth` | float64 | m | Total water depth at the vehicle. |

## Imaging geometry

Both columns are sparsely populated — in the sample dataset only 1 145 of
123 394 rows (≈ 1 %) carry a value.

| Column | dtype | Units | Meaning |
|---|---|---|---|
| `Fov` | float64 | m | Across-track ground field of view of the frame. |
| `Mm_pix` | float64 | mm/px | Ground sample distance. Consistent with `Fov ≈ Mm_pix × 1360 px` (the image width). |

## Environmental sensors

Displayed in the metadata panel and carried into the report summary. **Salinity
and temperature are in conventional units; the optical channels are raw sensor
output** — their scaling is not recorded anywhere in the plugin or the dataset.

| Column | dtype | Units | Meaning |
|---|---|---|---|
| `Salinity` | float64 | PSU | Practical salinity (sample values ≈ 32–33). |
| `Temp` | float64 | °C | Water temperature (sample values ≈ 7–13). |
| `O2` | float64 | *unconfirmed* | Dissolved-oxygen channel (sample values ≈ 6.9–8.9). |
| `Cdom` | float64 | *raw counts* | Coloured dissolved organic matter fluorometer. Takes negative values in the sample data, so it is uncalibrated instrument output, not a concentration. |
| `Chlorophyll` | float64 | *raw counts* | Chlorophyll fluorometer. |
| `Turb` | float64 | *raw counts* | Turbidity sensor. |

## Timing

All redundant with the DatetimeIndex; none is read by the plugin.

| Column | dtype | Meaning |
|---|---|---|
| `Date` | float64 | Calendar date as `YYYYMMDD`. |
| `DecDay` | float64 | Fraction of the day, `0…1`. Verified equal to the time of day of the index. |
| `DateTm` | float64 | `Date + DecDay`. |
| `TripDay` | float64 | Day number within the cruise, plus `DecDay` — `15.758…` is day 15 at 18:11. |
| `dT` | float64 | Elapsed time since the previous record, **in days** (≈ 1.9 × 10⁻⁶ ≈ 0.17 s in the sample). |

## Survey bookkeeping

| Column | dtype | Meaning |
|---|---|---|
| `Step` | float64 | Per-frame increment of `Position`. |
| `Position` | float64 | Monotonically increasing running total; `Position[i] − Position[i−1] == Step[i]` holds for 99.999 % of rows (the one exception is a data gap). Its origin is offset by ≈ 2.6 × 10⁶ and its physical unit is not recorded — the magnitudes are consistent with an along-track distance in metres, but this is **not confirmed**. |

Neither column is read by GroundTruther.

## Columns GroundTruther adds at load

These are **not** in your file — the plugin computes them.

| Column | Meaning |
|---|---|
| `usbl_lon`, `usbl_lat` | WGS-84 form of the USBL fix (`Xutm + dx`, `Yutm + dy`, projected from `Roughness.epsg`). The canonical position for the KD-tree, marker, export and sampling. Deliberately **hidden** from the metadata panel. |
| `Annotation` | The parsed annotation record for this image, joined on `Imagename`. Rendered in the metadata panel as a species → count tally. See [Annotations](annotations-and-video.md). |

---

## Bringing your own survey

The minimum viable table is:

| You must provide | Why |
|---|---|
| A `DatetimeIndex` | The metadata panel's Time row. |
| `Imagename` | File resolution and annotation joins. |
| `habcam_lon`, `habcam_lat` | Position, if you provide nothing better. |
| `Xutm`, `Yutm`, `dx`, `dy` | Strongly recommended — the accurate position path. `dx`/`dy` may be zero if your positions need no offset. |

Everything else is optional: **every** column in the file is listed in the
metadata panel automatically, so extra columns of your own are displayed without
any code change. Columns the plugin looks up by name (`Heading`, `bearing`,
`Altimeter`, the environment channels) simply do not contribute if absent.

The projected columns must be in the CRS named by
[`Roughness.epsg`](../configuration/settings-reference.md#georeferencing)
(default EPSG:32619, WGS 84 / UTM 19N) — that is the CRS used to turn them back
into longitude/latitude.
