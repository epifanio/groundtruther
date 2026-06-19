# GRASS / FastGIS integration

How GroundTruther talks to the **FastGIS GRASS API** (`https://api.fastgis.eu`,
repo `epifanio/FastGIS`). This replaced a legacy flat, unauthenticated API
(`mbapi.wps.met.no/api/*`) — that migration is the origin of this subsystem.

## Three structural facts about the new API
1. **Auth:** every request carries an `X-API-Key: fgk_…` header. Missing header → HTTP
   **422**; invalid/revoked key → **401**.
2. **Environment-scoped:** all operations run against an `env_id` (a server-side UUID
   binding a gisdb/location/mapset to the calling user). There is no "list locations" —
   you list/create *your* environments. You can only use your own `env_id` (403 otherwise).
3. **No response envelope:** success = HTTP 2xx + bare JSON (usually carrying `env_id`);
   failure = HTTP 4xx with `{"detail": ...}`. (The old `{status, data}` wrapper is gone.)

## Client: `gt/grass_api.py`
Stateless functions taking `(endpoint, api_key[, env_id], ...)`. A central `_request`
injects the header, parses JSON, and raises **`GrassApiError(detail, status)`** on any
network/HTTP failure. Surface area:
- **Identity/env:** `whoami`, `list_envs`, `create_env_epsg`, `create_env_dataset`
  (multipart), `create_mapset`, `delete_env`.
- **Context:** `gisenv`, `list_maps` (g.list, by type), `layers`, `projection`
  (epsg/wkt — used to build a QGIS CRS), `get_region`.
- **Geo ops:** `reproject`, `sample` (replaces `r_what`; pass input `crs`, server
  reprojects to native), `set_region` (native-CRS bounds only).
- **Modules:** `list_modules` (catalog), `describe_module` (interface schema),
  `submit_task` + `get_task` + `cancel_task` (async), `exec_module` (generic
  `/grass/exec`), `import_raster` / `import_vector`, `wcs_geotiff` (download a raster).

## How the pieces fit
- **`grassconfig.py` (`GrassConfigDialog`)** — the connection/env UI. Reads
  endpoint+key from settings; lists envs into a combo (userData = `env_id`); "Use
  Environment" sets the active env; create-from-EPSG/dataset (georef creation also
  *imports* the file); create mapset. Public API consumers use:
  `connection() -> (endpoint, api_key, env_id)` and `get_active_env()`.
- **`mixins/grass_mixin.py`** — region set (reprojects the drawn bbox from the **project
  CRS** to the env CRS via `QgsCoordinateTransform`, then `set_region`), raster query
  (`sample`, crs=EPSG:4326), show/hide current region (rubber band), and the layer
  context-menu **"Send to active GRASS environment"** (reprojects the loaded layer to
  the env CRS with GDAL/`QgsVectorFileWriter`, then imports it).
- **`pygui/grass_module_form.py` (`GrassModuleForm`)** — PyQt port of the FastGIS web
  `grass_runner` `schema.js`: builds a form on the fly from a module's interface schema.
  Widget mapping: enum→`QComboBox`; `gisprompt.age=="old"`→editable combo populated from
  `list_maps`; integer/float→validated `QLineEdit`; flags→`QCheckBox`; grouped by
  `guisection`; required marked `*`.
- **`pygui/grass_module_runner.py` (`ModuleRunnerWidget`)** — self-building runner: fetch
  schema → build form → run **async** via `gt/task_runner.py` (`QgsTask` submit+poll,
  progress/cancel) → on success, **pull new output rasters into QGIS** (diff `g.list`,
  download each via WCS, add as layers). The three `run_*_mdi.py` are presets of this;
  the GRASS toolbar also has a module-name autocomplete that opens one for any module.

## Workflow gotchas (verified live)
- **Async module runs require a PERSISTENT env** (`persist=True`). The Celery worker is a
  separate container sharing only `/data`; an ephemeral (`/tmp`) env is invisible to it →
  task fails "Location … doesn't exist". Sync ops still work on ephemeral envs. The client
  defaults `persist=True`.
- **`create_env_dataset` only seeds the location CRS** — it does NOT import the file; call
  `import_raster`/`import_vector` after (the dialog does this for georef creation).
- **WCS download is MIME-wrapped.** `wcs_geotiff` does WCS 2.0.1 `GetCoverage`
  (`COVERAGEID=<rastername>&FORMAT=image/tiff`) and **strips a MIME part** before the TIFF
  magic (`II*\x00`/`MM\x00*`). The GeoTIFF is in native CRS; QGIS reprojects on the fly.
- **`set_region` takes native-CRS bounds with no `crs` param** → reproject client-side
  first. The region box tool emits **project-CRS** coordinates (not WGS-84); the query
  tools emit **WGS-84** — don't conflate them.
- **`/tasks` returns an opaque 500 when required params are missing** (the sync endpoint
  returns a clean 400). The schema-driven form marks required params, so users fill them
  before submit and avoid it.

## CRS conventions
- Query/identify points: WGS-84 (`crs="EPSG:4326"`), server reprojects.
- Region from drawn bbox: project CRS → reproject to env CRS client-side.
- Module output rasters: native CRS GeoTIFF via WCS; QGIS handles on-the-fly reprojection.

## Server access / API feedback
- Live server reachable via `ssh adventure` (Docker Swarm; the API service is
  `fastgis_fastgrass`, worker `fastgis_fastgrass-worker`). OpenAPI: `api.fastgis.eu/openapi.json`.
- Consumer-side improvement notes for the API live at
  `FastGIS/CONSUMER_API_FEEDBACK.md` (in the FastGIS repo).
