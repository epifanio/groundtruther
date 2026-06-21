---
marp: true
title: GroundTruther — 2026 Update
description: What changed since the paper — QGIS 4/Qt6, new UI, FastGIS, video, refactor
paginate: true
theme: default
class: lead
---

<!--
Speaker deck: GroundTruther development update (winter → spring 2026).
Render with Marp (`marp slides_groundtruther_update_2026.md --pdf`) or read as Markdown.
Each `---` is a new slide.
-->

# GroundTruther
## What changed since the paper

A QGIS plugin for **seafloor characterization** — browse & analyse multibeam
(MBES) acoustics, seafloor imagery, and survey video together, ground-truth
them, and report.

*Development update · 2026 · v0.4 · QGIS 4 / Qt 6*

---

## Recap — what GroundTruther is

- Runs **inside QGIS** (not standalone) as a dock-based toolset
- Joins three data worlds on one map:
  - **MBES** bathymetry + backscatter (ARA / angular response)
  - **Seafloor imagery** (HabCam-style stills)
  - **Survey video** with per-frame geolocation
- Ground-truth annotation → statistics → KMZ / HTML reports
- Calls a remote **GRASS GIS** service for bathymetric derivatives,
  backscatter queries, and arbitrary GRASS modules
- Published on the official QGIS plugin repository

---

## Timeline

- **Paper release** → first public, working tool
- **This winter (≈ March 2026)** → start of a major modernization cycle
- Goal: bring it to **QGIS 4 / Qt 6**, make it **maintainable**, add
  **video**, and move GRASS to a **modern authenticated API**

> This deck = the highlights of that cycle: new platform, new UI/UX,
> streamlined install, refactor, new API, new science features, bug fixes.

---

## 1 · QGIS 4 / Qt 6 support

- Full port to **QGIS 4.0+ on Qt 6** (system Python 3.14)
- Reworked the UI layer for Qt 6:
  - Scoped-enum / signal API changes, `exec_` → `exec`
  - Fixed Qt 6 dock-walk crashes (register docks with the QGIS main window)
  - OpenGL 3-D viewer made Qt 6-safe (PyOpenGL context handling)
- Wayland-aware: launch with `QT_QPA_PLATFORM=xcb` for free-floating docks
- **`qgisMinimumVersion = 4.0`**

---

## 2 · New UI layout & project management

**Dock-based workspace**
- Image browser, Video player, Query builder, Report builder, GRASS Tools —
  each an independent, dockable/floatable QGIS panel
- "Restore default layout" + reliable **save/restore of docked layout**
  (`QMainWindow.saveState`)

**Session persistence (new)**
- A `groundtruther_project` JSON file (set in Settings)
- Saves/restores **image index, zoom, query selections, dock layout,
  map-sync** — written on QGIS project save, loaded at start
- *Pick up exactly where you left off*

---

## 2 · UI settings & configuration

- Single **YAML config**, validated by a **pydantic v2** model
  (clear errors instead of obscure runtime failures)
- Settings dialog for image / MBES / video / export / GRASS paths + keys
- Per-project session file is just another setting → portable, shareable
- CRS-aware everywhere: zoom-to uses **map scale (1:N)**, so it behaves the
  same in metric *and* geographic project CRSs

---

## 3 · Streamlined installation

- QGIS 4 runs on **system Python (PEP-668, no pip)** — handled cleanly:
  - Plugin deps live in a **`.venv`** beside the source
  - `_bootstrap_venv()` appends it to `sys.path` at load → deps resolve no
    matter how QGIS was launched
- Install = **symlink the repo** into the QGIS profile + enable
- Fixed missing runtime deps & venv bootstrap (one-step setup)
- Video decode ships via **PyAV** (bundled FFmpeg) — no system codec hunt

---

## 4 · Code refactoring — modular & maintainable

**Thin orchestrator + focused mixins**
- `groundtruther_dockwidget.py` ≈ 240 lines; real logic in `mixins/`:
  image browser · video browser · video annotation · GRASS · report ·
  settings · layout · **session**

**Stateless, testable core (`gt/`)** — no Qt, unit-tested:
- `grass_api` · `image_manager` · `video_manager` · `task_runner`
- **new:** `mbes_fields` · `video_reader` · `session_state`

**Result:** a growing **pytest** suite (unit / GUI-offscreen / integration)

---

## 5 · New FastGIS API (GRASS backend)

- Migrated from a legacy **flat, unauthenticated** endpoint
  (`mbapi.wps.met.no`) → **`api.fastgis.eu`** (repo `epifanio/FastGIS`)
- **Authenticated** (`X-API-Key`) and built around an **environment** model
  (`env_id`): import rasters/vectors, set computational region, run modules
- **Schema-driven module dialogs** — any GRASS module rendered from its
  interface description; async runs polled via a `QgsTask`
- GRASS Tools is now an **undockable QGIS panel**: on-the-fly module picker,
  push output rasters **back into QGIS**, show/hide the computational region

---

## 6 · Feature highlight — MBES query builder

- Draw a **sampling unit** (ellipse / rectangle) on the soundings
- ARA scatterplot (backscatter vs. incidence angle), 3-D surface, histograms,
  summary statistics, and the in-shape image selection
- **New multi-level backscatter** support — auto-detects every BSWG-2015
  processing level present in the file
  (`BS_raw → BS_RL → BS_TL → BS_area → BS_AVG`), **back-compatible** with the
  legacy single-value format
- Beam-side filtering (Raw / Port / Starboard / Fold) now works correctly

---

## 6 · Feature highlight — video player

- Frame-accurate player docked in QGIS, driven from the metadata track
- **Interlaced-source support (new):** PyAV + `yadif` deinterlace — fixes the
  FFmpeg-8 "interlaced → progressive" black-frame failure
- **Geo-link to map:** the canvas follows the current frame at a fixed,
  CRS-independent **map scale**; track marker + map stay in sync during play
- **GPS track layer** persisted as a real file (GeoJSON) — no "scratch layer"
  warning, restored with the project, auto-regenerated on load
- Per-frame **bounding-box annotation** with single-click draw / resume

---

## 6 · Feature highlight — reporting

- One click sends query-builder products to the **report builder**:
  ARA scatterplot · 3-D surface · histogram · statistics table ·
  **sampling-unit** description · **image-selection gallery**
- Output to **KMZ** (geo-referenced balloon) *and* a modern, **templated
  HTML report** (Jinja2):
  - Card layout, uniform thumbnails, **click-to-zoom lightbox**
  - **Browsable gallery** of the seafloor images in the sample
  - Statistics as a real HTML table; title + location summary
- PDF export of the composed report

---

## 7 · Bug-fix roundup (selected)

- 3-D WGL viewer rendered nothing on Qt 6 → fixed (PyOpenGL context)
- ARA beam radios (L/R/Fold) had no effect → fixed
- KMZ save crashed on un-generated products → guarded + de-duplicated
- Dock layout / video player came back **undocked** → `restoreState`
- Geo-link marker moved but **map didn't follow** → throttle fix
- Zoom was projection-dependent → **map scale (1:N)**, CRS-independent
- Interlaced video → black frames → **PyAV/yadif**
- Stale/broken track reference on reload → **auto-regenerate**

---

## 8 · Use case — HabCam

- Optical + acoustic ground-truthing of benthic habitat
- Browse tens of thousands of stills with metadata (depth, position,
  detector annotations), spatially linked to the MBES surface
- Draw a sampling unit → get the backscatter angular response **and** the
  images that fall inside it → annotate → report
- Reference dataset: open **HabCam test data on Zenodo** (CC-BY-4.0)

---

## 8 · Use case — MAREANO

- Norwegian seabed-mapping programme — towed-camera **video** transects
- Loads the MAREANO survey **`.log`** format directly
  (degrees + decimal-minutes → decimal degrees, control-point track)
- Video geo-linked to the map; GPS track drawn as a persistent layer
- Per-frame species / substrate annotation alongside the acoustics
- Demonstrates the tool beyond its original HabCam scope

---

## Is this a unique tool?

**Yes — the *integration* is the differentiator.**

- Most workflows are **siloed**: acoustics in one suite, image annotation in
  another, video review in a third, GIS somewhere else
- GroundTruther puts **MBES + imagery + video + annotation + GRASS analysis +
  reporting** on **one QGIS map**, free and open source
- Cloud GRASS backend (FastGIS) keeps the heavy geoprocessing **server-side**
- Open formats throughout (Parquet, GeoJSON, KMZ, CSV/`.log`)

*Not a replacement for specialist acoustic suites — a connective,
ground-truthing layer that ties them together.*

---

## What's next?

- **ML-assisted annotation** (pre-populate boxes; review instead of draw)
- More backscatter analytics & calibration helpers; multi-file mosaics
- Scale to very large soundings (10⁷+ rows) — lazy/Arrow-native, optional GPU
- Richer GRASS recipe presets; reproducible "analysis as a saved session"
- Multi-user / shared cloud sessions; signed report bundles
- Broaden metadata-format adapters (more survey logs out of the box)
- Harden CI: grow the test suite, package a turnkey installer

---

## Would you use it?

**Who it's for**
- Benthic ecologists & seabed-mapping teams doing **ground-truthing**
- Anyone who wants acoustics, imagery and video **on the same map** without
  stitching five tools together

**Honest take**
- If your work is *purely* acoustic processing → keep your specialist suite
- If it's **interpretation + ground-truth + reporting** across data types,
  inside GIS, open and scriptable → **yes, it's a strong fit** and only
  getting better this cycle

---

## Need help setting it up?

- **Requirements:** QGIS 4.0+ (Qt 6), the bundled `.venv`, a FastGIS API key
  for GRASS features
- **Install:** symlink the repo into your QGIS profile, enable the plugin,
  point Settings at your data
- **Try it:** the Zenodo HabCam test dataset (and a MAREANO `.log` + video)
- Repo & issues: **github.com/epifanio/groundtruther**
- Docs: GRASS/FastGIS integration guide in `docs/`

**Happy to walk you through install, config, or your own dataset.**

---

# Thank you

**GroundTruther** · v0.4 · QGIS 4 / Qt 6
*MBES · imagery · video · GRASS · ground-truth · report*

github.com/epifanio/groundtruther
