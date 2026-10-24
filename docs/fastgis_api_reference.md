# FastGIS wire reference — every route GroundTruther calls

Route-by-route reference for the HTTP calls the plugin actually makes, with the request
bodies it sends. Companion to [grass_fastgis.md](grass_fastgis.md), which explains *how the
subsystem is put together* and names the client functions; this page is the **wire level**,
for reading a server log, probing a route by hand, or discovering the surface on the server
side.

**This is derived from the client, not from the server.** It lists what GroundTruther calls
— a subset of what FastGIS serves, and it says nothing about routes nothing in the plugin
uses. The server's own truth is `api.fastgis.eu/openapi.json`. Where the two disagree, the
OpenAPI document is right and this page is stale.

Two clients make every request:

| client | base URL from | auth |
|---|---|---|
| [`gt/grass_api.py`](../gt/grass_api.py) | `Processing.grass_api_endpoint` | `X-API-Key` |
| [`gt/roughness_client.py`](../gt/roughness_client.py) | `Roughness.base_url`, falling back to `Processing.grass_api_endpoint` | `X-API-Key`, **or none** on the `direct_url` path |

Both send `accept: application/json`, and `Content-Type: application/json` only when there
is a JSON body. Every non-2xx becomes an exception carrying the server's `detail` field —
`GrassApiError` or `RoughnessError` — and **that string is what the user reads in QGIS**, so
`detail` is the server's user-facing error channel. An empty 2xx body returns `None` rather
than raising; a 2xx body that is not JSON raises `Non-JSON response from {path}`.

Timeouts, since a slow route shows up as a plugin-side failure: GRASS calls use **30 s**,
rising to **300 s** for location creation, imports, WCS and `/grass/exec`; roughness uses
**60 s**, **180 s** for mosaic and **10 s** for the health probe.

---

## GRASS — `gt/grass_api.py`

Every path below is relative to the endpoint, and everything except `/auth/me`,
`/grass/env*`, `/grass/modules*`, `/grass/tasks/*` and `/grass/exec` is scoped to an
`env_id`.

### Identity and environments

| function | route |
|---|---|
| `whoami` | `GET /auth/me` |
| `list_envs` | `GET /grass/env` |
| `create_env_epsg` | `POST /grass/env/epsg` |
| `create_env_dataset` | `POST /grass/env/dataset` (multipart) |
| `create_mapset` | `POST /grass/env/{env_id}/mapsets` |
| `delete_env` | `DELETE /grass/env/{env_id}` |

`GET /grass/env` is read out of `{"environments": [...]}`.

```json
POST /grass/env/epsg
{"epsg": 32619, "location": "habcam_utm19n", "mapset": "PERMANENT", "persist": true}
```

`db_driver` and `gisdb` are added only when set. `persist` defaults to `true` on purpose:
an ephemeral env is invisible to the Celery worker, so async tasks fail on one (see
`grass_fastgis.md`).

`POST /grass/env/dataset` is multipart — the file as `file`, with `location`, `mapset` and
`persist` as form fields (`persist` lowercased to the string `"true"`). It seeds the
location CRS only; the caller imports the file afterwards.

```json
POST /grass/env/{env_id}/mapsets
{"mapset": "work1", "copy_from_permanent": false}
```

This returns a **new env payload scoped to the created mapset**, not the old one.

### Import

Multipart, file in the `file` field, optional `output_name` as a form field:

- `POST /grass/env/{env_id}/import/raster` — runs `r.in.gdal` server-side, returns
  `{env_id, module, output, dataset}`
- `POST /grass/env/{env_id}/import/vector`

### Inventory and context

| function | route | reply unwrapped from |
|---|---|---|
| `gisenv` | `GET /grass/env/{env_id}/general/gisenv` (optional `?variable=`) | `variables` |
| `list_maps` | `GET /grass/env/{env_id}/general/list` | — |
| `projection` | `GET /grass/env/{env_id}/general/projection` | `projection` |
| `layers` | `GET /grass/env/{env_id}/layers` | — |
| `get_region` | `GET /grass/env/{env_id}/region` | `region` |

`list_maps` sends `?type=raster,vector` by default, plus `mapset` and `pattern` when given.
`projection` returns `epsg`, `ows_srs` (e.g. `"EPSG:32632"`), `proj`/`zone` and a full
`wkt` — enough to build a QGIS CRS client-side. `get_region`'s values are **strings in the
env's native CRS**.

### Geo operations

```json
POST /grass/env/{env_id}/reproject
{"points": [{"x": -68.91771, "y": 41.06611}],
 "source_crs": "EPSG:4326", "target_crs": "EPSG:32619"}
```

Returns `{"points": [{"x", "y", "source", "target"}, ...]}`.

```json
POST /grass/env/{env_id}/sample
{"layers": ["bathy_2015"], "point": {"x": -68.91771, "y": 41.06611},
 "crs": "EPSG:4326", "include_empty": true, "format": "grouped"}
```

`sample` replaced the old `r_what`. Send `points` instead of `point` for a batch, and
`distance` for vector proximity. The server reprojects from `crs` to the env's native CRS,
so the plugin's query tools send WGS-84 and do no transform. Raster values come back at
`results.raster[].samples[].value`.

```json
POST /grass/env/{env_id}/region
{"north": 4550000, "south": 4540000, "east": 400000, "west": 390000, "res": 1.0}
```

`set_region` takes **native-CRS bounds and has no `crs` parameter** — the caller reprojects
first. Any of `north`/`south`/`east`/`west`/`res` may be omitted, and `rows`, `cols`,
`nsres`, `ewres`, `align`, `raster`, `vector` pass through. An empty body is refused
client-side.

### Modules

| function | route |
|---|---|
| `list_modules` | `GET /grass/modules` → `{"modules": [{name, label, type}]}` |
| `describe_module` | `GET /grass/modules/{name}/schema` → `{"schema": {...}}` |
| `submit_task` | `POST /grass/env/{env_id}/tasks` → `{task_id, state, ...}` |
| `get_task` | `GET /grass/tasks/{task_id}` |
| `cancel_task` | `DELETE /grass/tasks/{task_id}` |
| `exec_module` | `POST /grass/exec` (synchronous) |

The schema — `{module, label, description, parameters[], flags[]}` — is what builds the
dynamic PyQt forms, and it is env-independent, so it can be fetched before any env exists.

```json
POST /grass/env/{env_id}/tasks
{"module": "r.geomorphon", "flags": ["m"],
 "params": {"elevation": "bathy_2015", "forms": "geom_out", "search": 15}}
```

`args` (a precompiled CLI list) may be sent instead of `flags`/`params`. Each of the three
is omitted when empty, so the minimum body is `{"module": "..."}` — which is how the opaque
500 described in `grass_fastgis.md` is reached.

```json
POST /grass/exec
{"env_id": "<id>", "module": "r.param.scale", "args": ["input=dem", "output=x", "-f"]}
```

`/grass/exec` is the one route that carries `env_id` **in the body** rather than the path,
and it imposes no family-prefix restriction — which is why non-prefixed modules such as
`grm_lsi` go through it.

### WCS — the one non-JSON route

```
GET /grass/env/{env_id}/wcs
    ?SERVICE=WCS&VERSION=2.0.1&REQUEST=GetCoverage
    &COVERAGEID=<rastername>&FORMAT=image/tiff
```

Sent with `accept: */*`. MapServer wraps the TIFF in a MIME part, so the client scans the
body for the TIFF magic (`II*\x00` or `MM\x00*`) and returns everything from there on. A
response with neither magic raises `WCS response for '<coverage>' was not a GeoTIFF`. The
GeoTIFF is in the env's native CRS; QGIS reprojects on the fly.

---

## Seafloor roughness and mosaic — `gt/roughness_client.py`

Three routes, each overridable by config — `Roughness.base_url` and `Roughness.route` — or
bypassed entirely by `Roughness.direct_url`, which POSTs straight to the on-host GPU
service **with no auth header at all**:

| constant | route | method |
|---|---|---|
| `DEFAULT_ROUTE` | `/seafloor/roughness` | POST |
| `MOSAIC_ROUTE` | `/seafloor/mosaic` | POST |
| `HEALTH_ROUTE` | `/seafloor/health` | **GET** |

```json
POST /seafloor/roughness
{"frame_key": "20150704_1_1234", "res_mm": 2.0, "n_water": 1.34,
 "return_dem": true, "dem_format": "mm", "dem_max_side": 1024,
 "include_orthophoto": true, "include_left_height": true,
 "include_left_preview": true, "include_spectrum": true}
```

`frame_key` is the only required field, and **every optional output is off by default** —
the client sends only the knobs in use, so a body in a server log tells you exactly what
the user asked to be rendered. `dem_format` is `png` (8-bit preview), `mm` (a real float
height grid, for the 3-D mesh) or `both`. `geo`, when present, is the UTM-georeferencing
object from `gt/roughness_geo.build_geo`, forwarded verbatim, and makes the service return
a geotransform so the micro-DEM and orthophoto can be written as GeoTIFFs.

**A `quality != "ok"` response is not an error.** It returns 2xx with null roughness fields,
and the plugin reads `quality` — `ok`, `insufficient_coverage` or `spectrum_fit_failed` — to
decide what to tell the user. So a failure to compute belongs in `quality`, not in a 4xx.

```json
POST /seafloor/mosaic
{"reference_key": "20150704_1_1234", "window": 5, "mode": "auto",
 "out_gsd_m": 0.002, "epsg": 32619, "interp": "cubic", "alpha": true}
```

Mode A: composite the ±`window` contiguous frames around `reference_key` into one
georeferenced UTM raster. The service pulls the nav itself (easting/northing/heading/
altimeter) for the window and skips frames with no image in the archive. It returns
`{mosaic_png_b64, geotransform, epsg, shape, bands, nodata, has_alpha, mode, n_frames,
frames_skipped, out_gsd_m, ...}`.

`illumination_correct` and `gain_compensate` default **on** server-side, so the client sends
them only to switch them off — an absent key means on, which is the opposite of the reading
every other optional field here invites.

---

## Probing by hand

`/auth/me` is the cheapest probe: an authenticated GET needing no env, so it separates a key
problem from a route problem in one call.

```bash
curl -s -H "X-API-Key: $FASTGIS_KEY" https://api.fastgis.eu/auth/me
```

```bash
curl -s -H "X-API-Key: $FASTGIS_KEY" https://api.fastgis.eu/grass/env
curl -s -H "X-API-Key: $FASTGIS_KEY" https://api.fastgis.eu/grass/modules
curl -s -H "X-API-Key: $FASTGIS_KEY" https://api.fastgis.eu/seafloor/health
```

Keep the key in an environment variable, never on the command line: a pasted key lands in
the shell history and in any log of this session. It is also the value of
`Processing.grass_api_key` in `config/config.yaml`, which is gitignored for that reason.

## One route family outside these two clients

`ioutils.send_layer_as_geojson` and `send_layer_as_geojson_using_gdal_` POST a GeoJSON body
to an **arbitrary `api_endpoint` argument** with `Content-Type: application/json` and **no
auth header**. Nothing in the plugin calls either one — they are dead code from the legacy
flat API — but they are the only HTTP paths outside `gt/grass_api.py` and
`gt/roughness_client.py`, so a request of that shape reaching the server did not come from
any live GroundTruther feature.
