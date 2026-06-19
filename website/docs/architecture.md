# Architecture

GroundTruther is a QGIS 4 / Qt6 plugin (Python) that orchestrates local data
browsing and annotation in the QGIS canvas, and delegates heavy geospatial
analysis to a remote GRASS service via the FastGIS API.

## Components & data flow

```mermaid
flowchart TB
  subgraph QGIS["QGIS 4 / Qt6 host"]
    direction TB
    CANVAS["Map canvas & layers"]
    subgraph PLUGIN["GroundTruther plugin"]
      direction TB
      DOCK["Dock widget<br/>(thin orchestrator)"]
      subgraph MIX["mixins/"]
        IB["Image Browser"]
        VID["Video Player"]
        ANN["Annotation editors"]
        GR["GRASS integration"]
        RPT["Report Builder"]
      end
      QB["Acoustic Query Builder"]
      subgraph GT["gt/ (stateless)"]
        API["grass_api client"]
        IMG["image_manager (KD-tree)"]
        VMG["video_manager"]
        TASK["task_runner (QgsTask)"]
      end
      FORM["Schema-driven<br/>module dialogs"]
      DOCK --> MIX
      DOCK --> QB
      GR --> API
      QB --> API
      FORM --> API
      TASK --> API
      IB --> IMG
      VID --> VMG
    end
    PLUGIN --- CANVAS
  end

  subgraph DATA["Local data"]
    IMGS["HabCam images + metadata (Parquet)"]
    ANNS["Annotations (CSV)"]
    MBES["MBES soundings (Parquet)"]
    VIDEO["Video + GPS log"]
    BATHY["Bathymetry rasters"]
  end

  subgraph FASTGIS["FastGIS GRASS API — api.fastgis.eu"]
    direction TB
    REST["FastAPI (auth: X-API-Key)"]
    WORKER["Celery worker"]
    GRASS["GRASS GIS engine"]
    PG["PostGIS (attributes)"]
    REDIS["Redis (envs, tasks, locks)"]
    WCS["WMS / WFS / WCS (MapServer)"]
    REST --> GRASS
    REST --> REDIS
    WORKER --> GRASS
    REST --> WORKER
    GRASS --> PG
    REST --> WCS
  end

  IMG -. reads .- IMGS
  IB -. reads .- ANNS
  QB -. reads .- MBES
  VMG -. reads .- VIDEO
  CANVAS -. displays .- BATHY
  API -- "HTTPS / REST" --> REST
  WCS -- "GeoTIFF outputs" --> API
```

**Reading the diagram:** the plugin runs entirely inside QGIS. UI logic lives in
focused **mixins** combined into one dock widget; reusable, Qt-free helpers live in
**`gt/`**. All acoustic/terrain work is sent over HTTPS to the **FastGIS GRASS
API**, which executes GRASS modules (synchronously or via a Celery worker),
stores state in Redis/PostGIS, and serves raster results back as GeoTIFF (WCS).

## Module map (in-repo)

```mermaid
flowchart LR
  INIT["__init__.py<br/>classFactory + venv bootstrap"] --> PLG["groundtruther.py<br/>GroundTruther (QgisPlugin)"]
  PLG --> DW["groundtruther_dockwidget.py"]
  DW --> M["mixins/*"]
  DW --> CFG["config_model.py + configure.py<br/>(pydantic v2, settings dialog)"]
  M --> GTPKG["gt/ (grass_api, image_manager,<br/>video_manager, task_runner)"]
  M --> PG2["pygui/ (Ui_*.py + widgets,<br/>grass_module_form/runner)"]
  PG2 --> UI["qtui/*.ui (pyuic6)"]
```

## Key dependencies

| Area | Packages |
|---|---|
| Data handling | numpy, pandas, pyarrow |
| Imagery / CV | scikit-image, scipy, opencv-python-headless |
| Viewer / plots | pyqtgraph, PyOpenGL, matplotlib, plotnine |
| Geospatial | pyproj, simplekml, geojson, requests |
| Acceleration | numba (optional GPU: cudf/cuspatial) |
| Config / templating | PyYAML, pydantic, starlette, Jinja2 |
| Host-provided (do **not** pip-install) | qgis, gdal/osgeo, PyQt6 |

## Design notes

- **Thin dock + mixins:** the dock widget is a high-level orchestrator; each
  feature area is an independently readable mixin.
- **Stateless `gt/` core:** networking, indexing and task orchestration are
  Qt-free and unit-testable.
- **Environment-scoped, authenticated API:** every GRASS call carries an API key
  and targets a server-side environment (location/mapset) owned by the user.
- **Schema-driven UIs:** GRASS module dialogs are generated from each module's
  interface description, so the toolset extends to new modules with no UI code.
- **Async by default for compute:** long-running modules run as background tasks
  with progress/cancel, keeping QGIS responsive.

For the developer/agent-oriented internals (conventions, gotchas, testing without
the GUI), see `CLAUDE.md` and `docs/grass_fastgis.md` in the repository.
