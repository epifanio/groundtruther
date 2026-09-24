# Settings reference

Every key in `config/config.yaml`, grouped the way the file and the Settings
dialog are grouped. **27 keys in 8 sections.**

How to read the tables:

- **Type** — what the validator accepts (`gt/config_check.py`). `dir` and `file`
  must exist and be readable; `url` must be `http(s)://…` with a host;
  `parent_dir` only requires the *containing folder* to exist.
- **Default** — the value in `config_model.py` when the key is absent.
- **Required** — `HabCam.imagepath` and `HabCam.imagemetadata` are the only two
  keys that block startup. Every other key is optional: unset is silent,
  set-but-invalid is a warning that disables its own feature and nothing else.
  See [Validation & troubleshooting](validation.md).
- **When unset or wrong** — exactly which capability you lose.

---

## `Filesystem`

| Key | Type | Default | Required | What it does | When unset or wrong |
|---|---|---|---|---|---|
| `Filesystem.filemanager` | file | *(none)* | no | Path to an external file-manager executable the KML report builder uses to open the export folder. | No "open folder" convenience; reports still export normally. |

---

## `HabCam`

The imagery this whole plugin is built around. **These are the only required
settings.**

| Key | Type | Default | Required | What it does | When unset or wrong |
|---|---|---|---|---|---|
| `HabCam.imagepath` | dir | — | **yes** | Directory holding the seafloor image files. Names come from the metadata table's `Imagename` column; the loader probes `<name>.jpg`, `.jpeg`, `.png`, `.tif`, `.tiff` and the `<name>_orig.*` stereo variant, so one metadata file drives mono and stereo deliveries alike. | **Fatal.** GroundTruther refuses to start and asks you to fix it in Settings. |
| `HabCam.imagemetadata` | file | — | **yes** | The per-image metadata table (Parquet) — positions, depth, altimeter, environment. Drives the index slider, the KD-tree map lookup and the metadata panel. See [Image metadata](../data-model/image-metadata.md). | **Fatal.** Same as above. |
| `HabCam.imageannotation` | file | *(none)* | no | CSV of bounding-box detections to overlay on the imagery. See [Annotations](../data-model/annotations-and-video.md#image-annotation-csv). | No boxes are drawn and the confidence filter has nothing to filter; browsing is unaffected. |

---

## `Mbes`

| Key | Type | Default | Required | What it does | When unset or wrong |
|---|---|---|---|---|---|
| `Mbes.soundings` | file | *(none)* | no | The MBES soundings table (Parquet) the [Acoustic Query Builder](../tools/query-builder.md) selects from. Its columns also populate the backscatter-field combo. See [MBES soundings](../data-model/mbes-soundings.md). | The query builder opens but has no soundings to select; spatial selection and the angular-response plots are unavailable. |
| `Mbes.reference_surface` | file | *(none)* | no | Optional GeoTIFF DEM / bathymetry raster. When set, the query builder's 3-D viewer clips **this raster** to the sampling shape instead of gridding the soundings. | The 3-D viewer falls back to a surface gridded from the selected soundings — which is also what happens if the file is present but cannot be read. |

---

## `Export`

| Key | Type | Default | Required | What it does | When unset or wrong |
|---|---|---|---|---|---|
| `Export.kmldir` | dir | *(none)* | no | Output folder for generated reports and KMZ files ([Report Builder](../tools/report-builder.md)). | Reports have nowhere to be written; exporting fails until you set it. |

---

## `Processing`

The FastGIS credentials. These are shared: the roughness service reuses them
unless you override them under `Roughness`.

| Key | Type | Default | Required | What it does | When unset or wrong |
|---|---|---|---|---|---|
| `Processing.gpu_avaibility` | bool | `false` | no | Declares that a CUDA-capable GPU (`cudf`/`cuspatial`) is available to accelerate point-in-polygon selection. *(The dialog's control is currently disabled — automatic RAPIDS detection is not implemented, so this is effectively a YAML-only switch.)* | Spatial selection uses the CPU `numba` path. Slower on large soundings files, identical results. |
| `Processing.grass_api_endpoint` | url | *(none)* | no | Base URL of the FastGIS GRASS API, e.g. `https://api.fastgis.eu`. | The whole [GRASS / FastGIS toolbox](../tools/grass-fastgis.md) is unavailable — and so is [Seafloor Roughness](../tools/seafloor-roughness.md), unless you set `Roughness.base_url` or `Roughness.direct_url`. |
| `Processing.grass_api_key` | str | *(none)* | no | Your API key, sent as the `X-API-Key` header on every request. **This is a secret** — see [Configuration](index.md#it-contains-a-secret). | Same as above: no GRASS, no roughness. The key is not validated locally, so a *wrong* key shows up as a 401/403 from the server, not as a config warning. |

!!! note "Note the spelling"
    `gpu_avaibility` is misspelled in the schema. It is kept as-is for backward
    compatibility with existing configuration files — write it exactly that way.

---

## `Video`

| Key | Type | Default | Required | What it does | When unset or wrong |
|---|---|---|---|---|---|
| `Video.videofile` | file | *(none)* | no | The survey video (MP4 / H.264 recommended), decoded with OpenCV. | The [Video Player](../tools/video-player.md) has nothing to play. |
| `Video.videometadata` | file | *(none)* | no | The per-frame navigation CSV that geo-links playback to the map. See [Video metadata](../data-model/annotations-and-video.md#video-metadata-csv). | Video plays, but geo-link, the GPS track layer and the metadata panel are all empty. |
| `Video.videoannotation` | file | *(none)* | no | Per-frame bounding-box annotations. See [Video annotations](../data-model/annotations-and-video.md#video-annotation-csv). | No boxes on video frames; new annotations can still be created and saved. |

---

## `Session`

| Key | Type | Default | Required | What it does | When unset or wrong |
|---|---|---|---|---|---|
| `Session.groundtruther_project` | parent_dir | *(none)* | no | Path to a JSON file storing restorable UI state — image index, zoom, query-builder selection, video position, dock layout. Written when the project is saved or the plugin closes, loaded at start. | Nothing is restored; every session starts at defaults. Only the **containing folder** has to exist — the file itself is created on first save, so pointing at a not-yet-existing `.json` is correct and produces no warning. |

---

## `Roughness`

Thirteen keys for the [Seafloor Roughness](../tools/seafloor-roughness.md)
service. All optional; all have working defaults.

### Service / transport

| Key | Type | Default | Required | What it does | When unset or wrong |
|---|---|---|---|---|---|
| `Roughness.base_url` | url | *(none)* | no | FastGIS base URL for the roughness route. | **Empty is the normal setting** — it falls back to `Processing.grass_api_endpoint` and reuses the same API key. |
| `Roughness.route` | str | *(none)* | no | Route path appended to the base URL. | Empty means `/seafloor/roughness`, which is correct for the current FastGIS deployment. |
| `Roughness.direct_url` | url | *(none)* | no | On-host GPU service URL, e.g. `http://127.0.0.1:7871/roughness`. When set, GroundTruther POSTs here **directly with no auth header**, skipping FastGIS entirely. | Empty means "go through FastGIS" — the right choice unless you are running QGIS on the GPU host itself. |

### Computation

| Key | Type | Default | Required | What it does | When unset or wrong |
|---|---|---|---|---|---|
| `Roughness.res_mm` | float ≥ 0 | *(unset)* | no | **Requested** micro-DEM cell size in millimetres, forwarded to the service. | Unset — the dialog shows *"service default"* — is the recommended setting. The service's nominal default is 1.0 mm, but it chooses the cell size **per frame** and the value it actually used comes back as `dx_mm` — 1 mm on some frames of the reference dataset, 2–5 mm on others. Treat this key as a request, not a guarantee, and read `dx_mm`. |
| `Roughness.n_water` | float ≥ 0 | *(unset)* | no | Refractive index of water. | **Leave unset.** The 2015 HabCam calibration was performed in water, so the refraction is already absorbed; sending `1.33` would double-count it and corrupt every height and roughness value. The server default is `1.0`. It exists only for a future air-calibrated dataset. |
| `Roughness.dem_max_side` | int ≥ 1 | `512` | no | Cap on the longest side of the returned micro-DEM grid. | Larger grids mean more detail in the 3-D tab and a bigger payload; the dialog allows 64–4096. |

### Georeferencing

!!! warning "These four are *defaults for new datasets only*"
    The roughness panel's **Georef** tab saves its own calibration per dataset
    (keyed by a hash of the metadata file path, in `QgsSettings`) and **that
    saved calibration wins**. If you change these values here and see no effect,
    it is because the current dataset already has a saved calibration. Change it
    on the Georef tab instead — see
    [Seafloor Roughness](../tools/seafloor-roughness.md#georeferencing-georef-tab).

| Key | Type | Default | Required | What it does | When unset or wrong |
|---|---|---|---|---|---|
| `Roughness.georeference` | bool | `false` | no | Attach the frame's UTM navigation to the request, then write the returned micro-DEM and orthophoto as GeoTIFFs and add them to QGIS. | Off: roughness metrics and the 3-D view still work, but nothing is written to disk or added to the map. |
| `Roughness.epsg` | int 1024–999999 | `32619` | no | Projected CRS for the georeferenced output and for the internal USBL→WGS-84 conversion. `32619` is WGS 84 / UTM zone 19N. | A value outside the range is rejected with a warning and the key is treated as unset (the code then falls back to `32619`). Set it to your survey's UTM zone. |
| `Roughness.heading_offset_deg` | float | `0.0` | no | Residual rotation added to the navigation heading before the service computes the geotransform. | `0` is correct out of the box — the camera mount is known (image bottom→top = heading, image-right = starboard). Only nudge it if rasters are consistently rotated relative to the bathymetry. |
| `Roughness.mirror` | bool | `false` | no | Flip the port/starboard handedness of the output grid. | The escape hatch. Set it `true` **once** if a mosaic comes out port/starboard-flipped; a reflection is not something a heading offset can fix. |

### 3-D mesh edge-spike mitigation

The stereo DEM is unreliable at the grid border and around no-data holes, which
shows up as height spikes draped with stretched texture. These three are the
*starting values* for the live controls on the **Micro-DEM 3D** tab.

| Key | Type | Default | Required | What it does | When unset or wrong |
|---|---|---|---|---|---|
| `Roughness.dem_trim_border` | int ≥ 0 | `2` | no | Drop this many outer rings of the DEM grid before meshing. | `0` keeps the full grid, spikes included. The dialog allows 0–10. |
| `Roughness.dem_clip_sigma` | float ≥ 0 | `5.0` | no | Mask cells more than this many robust standard deviations from the median height. Lower is more aggressive. | The dialog shows `0` as *"off"* — no outlier rejection at all. |
| `Roughness.dem_erode` | int ≥ 0 | `1` | no | Peel this many rings off every no-data / outlier boundary. | Higher means fewer edge spikes but less coverage; `0` disables erosion. The dialog allows 0–5. |

---

## Keeping this page honest

A unit test (`tests/unit/test_settings_docs.py`) asserts that every key in
`gt/config_check.SPEC` appears on this page, and that this page names no key the
schema does not have. Adding a config key therefore means editing three places:
`config_model.py`, `config_check.SPEC`, and this table.
