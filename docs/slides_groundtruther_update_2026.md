---
marp: true
title: GroundTruther — 2026 Update
description: From plugin to measurement instrument — QGIS 4/Qt6, FastGIS, stereo photogrammetry, roughness, mosaics, the seabed ribbon, and the HRS1508 analysis
paginate: true
theme: default
class: lead
---

<!--
Speaker deck: GroundTruther development update (spring → autumn 2026).
Render with Marp (`marp slides_groundtruther_update_2026.md --pdf`) or read as Markdown.
Each `---` is a new slide.

Structure:
  Act I  (slides 4-11)  the platform — what it took to make the tool maintainable
  Act II (slides 12-19) optical geometry — the new stereo / roughness / mosaic / ribbon tools
  Act III(slides 20-23) the science the tools made possible (HRS1508)

Every number in Act III comes from run R2026-09-21 of the frozen manifest in
`PDAL_MBIO/paper/manifest.yml`; every ribbon number from `docs/photogrammetric_ribbon.md`.
-->

# GroundTruther
## From plugin to measurement instrument

A QGIS plugin for **seafloor characterization** — browse and analyse multibeam
(MBES) acoustics, seafloor imagery, survey video **and now stereo geometry**
together, ground-truth them, and report.

*Development update · September 2026 · v0.4 · QGIS 4 / Qt 6*

---

## Recap — what GroundTruther is

- Runs **inside QGIS** (not standalone) as a dock-based toolset
- Joins **four** data worlds on one map:
  - **MBES** bathymetry + backscatter (ARA / angular response)
  - **Seafloor imagery** (HabCam-style stereo stills)
  - **Survey video** with per-frame geolocation
  - **Stereo geometry** — micro-DEMs, roughness, mosaics *(new this cycle)*
- Ground-truth annotation → statistics → KMZ / HTML reports
- Calls remote services for the heavy work: a **GRASS GIS** backend for
  bathymetric derivatives and modules, a **GPU stereo service** for photogrammetry
- Published on the official QGIS plugin repository ·
  docs at **epifanio.github.io/groundtruther**

---

## Where it stands today

| when | what landed |
|---|---|
| **Apr 2026** | Port to **QGIS 4 / Qt 6**, Python 3.14, dock UI, video player |
| **Jun 2026** | **FastGIS** authenticated GRASS API · session persistence · **stereo roughness, micro-DEM 3-D and georeferenced mosaics** |
| **Sep 2026** | Config hardening · full docs site · the **180° georeference fix** · the **photogrammetric seabed ribbon** |
| **in parallel** | **HRS1508** — a frozen-manifest analysis asking whether stereo roughness actually adds to acoustics |

> **Act I** — the engineering that made the tool trustworthy.
> **Act II** — the new optical-geometry tools.
> **Act III** — the first science they made possible.

---

<!-- _class: lead -->

# Act I
## The platform

*QGIS 4 / Qt 6 · docks & sessions · configuration · internals · FastGIS ·
query builder · video · reports · docs*

---

## 1 · QGIS 4 / Qt 6 support

- Full port to **QGIS 4.0+ on Qt 6** (system Python 3.14)
- Reworked the UI layer for Qt 6:
  - Scoped-enum / signal API changes, `exec_` → `exec`
  - Fixed Qt 6 dock-walk crashes (register docks with the QGIS main window,
    never with the plugin's inner `QMainWindow`)
  - OpenGL 3-D viewer made Qt 6-safe (PyOpenGL context handling)
  - `QWebEngineView` → `QTextBrowser` (WebEngine absent from QGIS 4 OSGeo4W)
- Wayland-aware: launch with `QT_QPA_PLATFORM=xcb` for free-floating docks
- **`qgisMinimumVersion = 4.0`**

---

## 2 · Dock workspace & session persistence

**Dock-based workspace**
- Image browser · Video player · Query builder · Report builder · GRASS Tools ·
  **Seafloor roughness** — each an independent, dockable/floatable QGIS panel
- "Restore default layout" + reliable **save/restore of docked layout**
  (`QMainWindow.saveState`)

**Session persistence**
- A `groundtruther_project` JSON file (set in Settings)
- Saves/restores **image index, zoom, query selections, dock layout, map-sync** —
  written on QGIS project save, loaded at start
- *Pick up exactly where you left off*

---

## 3 · Configuration that degrades instead of failing

The old model was all-or-nothing: one stale path and the plugin would not start.

- **27 config keys**, each validated **per key** and **severity-aware**
  (`gt/config_check.py`), with `config_model.py` as the pydantic v2 schema of record
- Only `HabCam.imagepath` + `HabCam.imagemetadata` are **errors**; every other key
  is a **warning** when set-but-invalid and silent when unset
- `degrade()` blanks **only** the failed keys → one bad value disables **its own
  feature**, nothing else
- Config values are treated as **untrusted** throughout — no bare `int(...)` or
  `Path(...)` on a settings value
- The Settings dialog now has a widget for **every** key, and saves by
  **merging into the file on disk** (the old fixed template silently deleted
  whole sections)
- Cloud-dependent panels **hide themselves** when no service is configured

---

## 4 · Internals — modular, tested, documented

**Thin orchestrator + focused mixins** — `groundtruther_dockwidget.py` ≈ 240 lines;
logic lives in `mixins/`: image browser · video browser · video annotation ·
GRASS · **roughness** · report · settings · layout · session

**Stateless, testable core (`gt/`)** — no Qt, unit-tested: `grass_api` ·
`image_manager` · `video_manager` · `task_runner` · `mbes_fields` · `session_state` ·
`roughness_client` / `_geo` / `_dem` / `_spectrum` / `_interpret` · **`ribbon`**

- **415 tests** collected (unit / GUI-offscreen / integration), with tests that
  guard the *conventions*: import hygiene, settings-docs drift, UI-built-once
- Every intra-plugin import is `from groundtruther… import …`; nothing appends the
  plugin dir to `sys.path`
- Non-trivial work is **planned first** in `PLANNING/`, executed in a dedicated
  git worktree, and closed out with a progress log

---

## 5 · FastGIS — the GRASS backend

- Migrated from a legacy **flat, unauthenticated** endpoint
  (`mbapi.wps.met.no`) → **`api.fastgis.eu`** (repo `epifanio/FastGIS`)
- **Authenticated** (`X-API-Key`) and built around an **environment** model
  (`env_id`): import rasters/vectors, set computational region, run modules
- **Schema-driven module dialogs** — any GRASS module rendered from its interface
  description; async runs polled via a `QgsTask`
- GRASS Tools is a **detachable QGIS panel**: on-the-fly module picker, push
  output rasters **back into QGIS**, show/hide the computational region
- Same credentials carry the **stereo roughness** service (Act II), so if GRASS
  works, roughness works

---

## 6 · MBES query builder & ARA

- Draw a **sampling unit** (ellipse / rectangle) on the soundings
- ARA scatterplot (backscatter vs. incidence angle), 3-D surface, histograms,
  summary statistics, and the in-shape image selection
- **Multi-level backscatter**: auto-detects every BSWG-2015 processing level
  present in the file (`BS_raw → BS_RL → BS_TL → BS_area → BS_AVG`),
  back-compatible with the legacy single-value format
- Beam-side filtering (Raw / Port / Starboard / Fold) works correctly
- Sampling centre now uses the **calibrated USBL fix**, so the marker, the sample
  and the georeferenced rasters all coincide

---

## 7 · Video player

- Frame-accurate player docked in QGIS, driven from the metadata track
- **Interlaced-source support:** PyAV + `yadif` deinterlace — fixes the FFmpeg-8
  "interlaced → progressive" black-frame failure
- **Geo-link to map:** the canvas follows the current frame at a fixed,
  CRS-independent **map scale**; track marker and map stay in sync during play
- **GPS track layer** persisted as a real file (GeoJSON) — no "scratch layer"
  warning, restored with the project, auto-regenerated on load
- Per-frame **bounding-box annotation** with single-click draw / resume
- Loads the MAREANO survey **`.log`** format directly

---

## 8 · Reporting

- One click sends query-builder products to the **report builder**:
  ARA scatterplot · 3-D surface · histogram · statistics table ·
  **sampling-unit** description · **image-selection gallery**
- Output to **KMZ** (geo-referenced balloon) *and* a modern, **templated HTML
  report** (Jinja2):
  - Card layout, uniform thumbnails, **click-to-zoom lightbox**
  - **Browsable gallery** of the seafloor images in the sample
  - Statistics as a real HTML table; title + location summary
- PDF export of the composed report

---

## 9 · Documentation

- User-facing docs are now a **MkDocs Material site** in `website/`, published to
  **epifanio.github.io/groundtruther** on merge
- Sections: Installation (Linux/macOS/Windows) · **Tools** (one page per feature) ·
  **Configuration** (all 27 keys + the validation model) · **Data model** ·
  Architecture
- A **data-model reference** documents every column the plugin reads — including
  which position column is the USBL fix and which is a model *(this is what
  surfaced the 180° bug in Act II)*
- `mkdocs build --strict` in CI catches broken links and orphan pages; a unit test
  fails if a config key is added without its documentation row

---

<!-- _class: lead -->

# Act II
## Optical geometry

*Stereo reconstruction · roughness · georeferencing · mosaics · the seabed ribbon*

---

## The gap this act is about

Roughness is measured **inside one camera frame**. Backscatter is measured over a
footprint **metres across**. Between them sits a scale range nothing was
measuring:

| product | wavelengths it supports |
|---|---|
| per-frame stereo micro-DEM | ~3 mm … **1.2 m** (one frame's footprint) |
| MBES bathymetry (1 m grid) | **≥ 2–3 m** |
| **the photogrammetric ribbon** | **3 mm … 170 m** — it spans the whole range |

γ₂, the load-bearing roughness metric, is fitted at frame scale and then used to
interpret acoustics at metre scale. **Nobody had checked the power law holds
across the gap.** Act II builds the instruments; the last slide reports what they
say.

---

## 10 · Stereo photogrammetric reconstruction

A **real-height micro-DEM** of the patch under the camera, from the HabCam stereo
pair itself — independent of the acoustics.

- Computed **server-side** on a GPU (**RAFT-Stereo**, SGBM fallback). GroundTruther
  sends only the frame's `Imagename`; **no image bytes leave the machine**
- Returns a Float32 height grid in **millimetres**, ~2–5 mm cells (the service picks
  per frame), NaN no-data, plus a **cell-for-cell co-registered orthophoto**
- **Micro-DEM 3-D tab** — the mesh draped with the orthophoto as a 1:1 texture
  (one texel per vertex): a true representation of the seabed patch, not a
  high-passed roughness field
- Stereo is unreliable at grid borders and hole edges; three live controls
  (**trim border · clip σ · erode**) mask the spikes instead of pretending
- Runs as a background `QgsTask`, cached per frame — ~14 s for the first frame of a
  session, ~0.5 s after

---

## 11 · Seafloor roughness — γ₂, and what to trust

**Metrics tab:** γ₂ · substrate & texture hints · w₂ · rms height · rugosity ·
anisotropy · altitude · quality · matcher. **Spectrum tab:** the radial relief
power spectrum on log-log axes with the fitted power law, fit band shaded, γ₂ /
w₂ / R² annotated.

- **γ₂ — the spectral exponent — is the load-bearing output.** It describes the
  fractal/texture character of the surface and is robust across stereo matchers
- **w₂ and rms height are *not* trustworthy in absolute terms** from this stereo:
  no consistent bias between RAFT and SGBM, and the population median rms (50 mm)
  sits far above the 3–23 mm literature range. The panel colour-codes them per
  frame by the service's own trust flag — rarely green
- When `quality` is not `ok`, **every** roughness field is null; the panel shows
  that rather than fabricating a number
- The spectrum tab is the diagnostic: where the curve peels off the fit line at
  high K you are looking at the **stereo noise floor**, not the seabed

---

## 12 · Georeferencing — and a 180° bug worth telling

Tick **Georeference** and the frame's navigation goes with the request; the plugin
writes the micro-DEM, orthophoto and mosaic as **GeoTIFFs in the survey CRS**, so
they overlay the bathymetry directly. The affine is **rotated** — the grid is
aligned to the vehicle's heading, not north.

- **The bug (issue #31):** the plugin sent the nav's `bearing` column as heading.
  `bearing` points **astern** — so *every* georeferenced product was rotated
  **180°**, and a saved heading offset of ±180 was the natural way to paper over it
- **Proved on the imagery, not by argument:** imagery-derived course minus nav
  course over 250 registered frame pairs —
  `heading = bearing` → **−175.3°** median residual, **0 %** within 30°;
  `heading = bearing + 180` → **+3.9°**, **100 %** within 30°
- Side benefit: **a single frame's heading is good to ~4°** — now a measured number
- **Rotation ≠ reflection.** Heading offset fixes a rotation; **Mirror** fixes a
  handedness flip. No rotation can undo a reflection — the docs say so explicitly
- Rasters exported before the fix are 180° out and need regenerating

---

## 13 · Georeferenced mosaics

Build a mosaic of the frames **around the current one** — pick a window (± N
frames), a mode, press **Build mosaic**.

| mode | how frames are placed |
|---|---|
| **Auto** *(default)* | Per window, from nav-predicted overlap: piled-up → *pixel*, well-spread → *flat* |
| **Flat** | Navigation alone (position, heading, flat-seabed scale). Fast |
| **Ortho** | Relief-corrected per-frame orthophoto, then nav placement. Slowest |
| **Pixel** | Registered by **image content**, georeferenced through the reference frame's nav |

- **Illumination correction** (flat-fields the strobe vignette) and **gain
  compensation** on by default — this is what makes a mosaic look continuous.
  Turn illumination off for absolute-radiometry work
- Presets: **Browse** (3 mm, fast) and **Publication** (ortho, 0.8 mm, lanczos,
  8192 px, RGBA)
- **Honest failure mode:** featureless mud cannot be content-registered by any
  method. The service reports how many pairs it actually registered, and the panel
  warns — *"only 0/10 pairs registered — low texture, mosaic is nav-placed"*

---

## 14 · The photogrammetric seabed ribbon

Composite a few hundred per-frame micro-DEMs along **one HabCam line** into
~170 m of millimetre-resolution, georeferenced seabed. A **script**
(`scripts/build_ribbon.py`), not yet a dock — look at a ribbon first.

- **Choose the strip by texture, never by relief.** Consecutive frames register only
  where the seabed has texture, and on this survey texture and relief are
  *uncorrelated*: two runs with **~4 m of relief** (3.75 m and 4.04 m) linked on
  **0 %** of sampled pairs — featureless mud — while the strip with the most relief in
  the survey (5.80 m) managed only 22 median inliers. Picking by relief would have
  chosen one of them
- **ORB + RANSAC needs help on this imagery:** no preprocessing (CLAHE and
  flat-fielding both *lowered* inliers), a **loose Lowe ratio 0.95**, detection
  masked to the overlapping band, and a **displacement prefilter + physical gate** —
  without the gate, RANSAC confidently returns 15–25-inlier consensuses on
  completely wrong transforms
- **Pixels where they work, navigation everywhere else:** the USBL is
  piecewise-constant (median step **92 mm** against a true **491 mm**), so frames
  placed by raw nav stack in clumps of ~6 and jump. The chain integrates the links,
  bridges gaps with nav, then rubber-sheets back onto the nav — *absolute* placement
  from the USBL, *relative* geometry from the pixels

---

## 15 · The ribbon — measured

**Strip 6663–6958: 296 frames, 172 m, EPSG:32619, track-aligned at 273.1°,
1256 × 48 339 cells at 3 mm.**

| | |
|---|---|
| link rate | **89.8 %** (265 / 295 pairs), median 309 inliers |
| longest unbroken registered run | **119 pairs** (mean 48) |
| `quality != ok` | **2.0 %** (6 frames, all `insufficient_coverage`) |
| service altitude vs `Altimeter` | median **37 mm** |
| seam error, **pixel-linked** | 62.0 mm → **13.7 mm** after levelling |
| seam error, **nav-bridged** | 235.5 mm → 119.3 mm — **8.7× worse** |

- **The vertical error was the depth sensor, not the stereo.** `V_Depth` is
  quantized to 10 mm and steps frame-to-frame with σ = 82 mm — essentially the whole
  per-frame scatter. Levelling solves per-frame offsets from overlap medians
  (robust IRLS, lag-1 **and** lag-2 for loop closure), keeping only the high
  frequencies so the datum stays with the vehicle
- **The trade, stated:** levelling improved seams 4.5× but made the 1 m profile agree
  *less* with the MBES (0.147 → 0.185 m). Some large corrections over-fit bad overlaps
- Two independent geometry checks: chain azimuth **273.1°** vs nav **273.2°**, and a
  focal length calibrated against nav displacement at **2507 px vs a nominal
  2480.28 — ratio 1.011**

---

## 16 · Does the power law cross the gap? *Suggestive, not settled.*

The per-frame fit is 2-D and isotropic; a ribbon profile measures the 1-D spectrum.
Integrating out the unmeasured cross-track wavenumber gives a closed form with
**no free parameter** — so γ₁ = γ₂ − 1 *and* the amplitude are both predicted.

**Measured in the 1.2–3 m band: 9.45× (+9.8 dB) more power than the per-frame law
predicts, fitted γ₁ = 2.29 ± 1.56 against a predicted 1.97.**

**Why that is not an answer — both error bars, in view:**
- **The slope is unconstrained.** ±1.56 spans every physically plausible exponent.
  The band is a third of a decade — all a 145 m ribbon can offer
- **The amplitude excess is only 1.7× above the ribbon's own noise floor.** A
  per-frame vertical error held across each frame and changing every 0.49 m puts a
  nearly *flat* spectrum across exactly this band. At the measured σ = 60 mm the
  floor sits 1.7× under the measurement (14× at the robust σ = 21 mm)
- **What would settle it is now a number:** per-frame vertical placement must reach
  **≈ 6 mm**, from 60 mm — a vertical bundle adjustment, and a separate plan
- Supporting, both real: MBES along-track **γ₁ = 3.60 ± 0.16** (γ₂ ≈ 4.60) over
  2–40 m, far steeper than the per-frame 2.97, with the ribbon's 3.29 **between**
  them — the shape of a gradual break, at an error bar that makes it a remark
- **And the ribbon does not beat the altimeter** on vertical accuracy (0.185 m vs
  0.115 m median |dz| against the MBES). **It adds texture, not depth.**

---

<!-- _class: lead -->

# Act III
## The science it made possible

*HRS1508 — does stereo roughness add anything to acoustics?*

---

## 17 · HRS1508 — the question and the setup

**Does optical roughness carry substrate information that backscatter does not?**
A binary problem — Substrate A vs Substrate E — on the HRS1508 survey.

| stream | what went in |
|---|---|
| MBES beams | **29 027 174** beams, all 512 formed beams/ping, full angular range |
| cells | 25 m grid → **2318** ARA cells (median 9846 beams/cell, 6 angle bins) |
| optical nav | 123 394 HabCam frames, positioned by **calibrated USBL** |
| stereo roughness | 12 563 per-frame records → γ₂, rugosity, anisotropy |
| analysis set | **217 cells** with a majority single-substrate label and ≥ 3 roughness frames |

- Features: 7 ARA descriptors (6 × 10° angle bins + slope), **per-line normalised**
  so the unknown source level cancels, plus 3 roughness features
- Random forest, **5-fold spatially blocked CV on 200 m blocks** (33 blocks),
  folds **frozen once** and reused by every experiment so comparisons are paired

---

## 18 · The result

| model | accuracy | gain vs ARA | 95 % CI |
|---|---|---|---|
| ARA only *(baseline)* | 0.659 | — | — |
| ARA + γ₂ | 0.691 | +0.032 | −0.005 … 0.072 |
| ARA + γ₂ + rugosity | 0.714 | +0.055 | 0.005 … 0.108 |
| **ARA + all roughness** | **0.756** | **+0.097** | **0.039 … 0.155** |
| roughness only | 0.756 | +0.097 | 0.014 … 0.183 |

- Block-permutation **p < 0.001**; macro-F₁ 0.597 → **0.715**; the minority class
  (Substrate E) recall **0.43 → 0.60** — the gain is where it matters
- **γ₂ ranks first of all ten features** (importance 0.215, above every backscatter
  bin — the best of those is 0.175)
- **Modality ladder:** backscatter alone 0.70 · + bathymetric slope correction 0.66 ·
  + γ₂ 0.69 · + all roughness **0.76**
- Holds across scale: at a **15 m** cell the same ladder runs 0.74 → **0.83**
- **Two-tier map:** 881 of 2318 cells (38 %) have both modalities; adding roughness
  **flips 14.5 %** of the classified swath

---

## 19 · Why you can believe it — and what it does not say

**One run, one manifest.** Two earlier fusion results (0.769→0.864 on 221 cells,
0.761→0.820 on 987 cells) differed in *both* the beam table and the cell subset —
invisible to the author, obvious to a referee. The fix was not to pick a number,
it was to make two impossible: **one frozen `manifest.yml`, one library, one beam
table, one fold assignment**, every input hashed into a lock file.

- **Calibration stress test.** Inject per-line source-level error up to 5 dB
  (against a *measured* per-line spread of 4.59 dB over 17 lines): the normalised
  pipeline moves **0.000**; strip the per-line normalisation and it drifts 0.018;
  strip the *shape* too and the level-only classifier falls to 0.58 and drifts 0.028.
  **The result does not depend on absolute calibration.**
- **The image classifier survives honest CV:** 0.942 stratified → **0.939** on 200 m
  spatial blocks. Optimism 0.002 — it was not leaking geography.

**Stated limits, not buried:**
- **The stereo coverage gate is not label-neutral** — 2.7 % of Substrate A cells
  rejected against **12.9 %** of Substrate E (Fisher OR **5.3**, p ≈ 2×10⁻²⁵). That
  is a *result* about turbidity over fine sediment, not an inconvenience
- **w₂ and rms height are never model inputs** — amplitude is not recoverable from
  this stereo
- `fit_r2`, `valid_fraction`, `altitude_mm`, `matcher` are **absent** from the
  committed roughness CSVs although the service returns them: until they are
  persisted, spectrum quality cannot be filtered on

---

## Is this a unique tool?

**Yes — and the differentiator has shifted.**

- It started as an **integration** argument: most workflows are siloed — acoustics
  in one suite, image annotation in another, video review in a third, GIS
  somewhere else. GroundTruther puts them on **one QGIS map**, free and open source
- It is now also a **measurement** argument: no other GIS-native tool turns the
  survey's own stereo imagery into **metric seabed geometry** — micro-DEMs,
  spectral roughness, georeferenced mosaics, a millimetre ribbon — and puts it
  beside the acoustics in the same project
- Heavy work stays **server-side** (FastGIS for GRASS, a GPU service for stereo);
  the plugin stays a thin, scriptable client
- Open formats throughout (Parquet, GeoJSON, GeoTIFF, KMZ, CSV/`.log`)

*Not a replacement for specialist acoustic suites — a connective, ground-truthing
layer, which now measures something of its own.*

---

## What's next?

**Committed, with a number attached**
- **Vertical bundle adjustment** for the ribbon: per-frame placement 60 mm → **≈ 6 mm**.
  That single factor of ten converts the scale-gap result from suggestive to publishable
- **Persist the roughness QC fields** (`fit_r2`, `valid_fraction`, `altitude_mm`,
  `matcher`) so spectrum quality can be reported and filtered on
- **Resolve mount handedness** against a target of known handedness — the one link in
  the geometry chain still untested

**Open**
- ML-assisted annotation (pre-populate boxes; review instead of draw)
- A **ribbon dock** in QGIS, once people have used a ribbon in anger
- Multi-line ribbons and cross-line closure; reproducible "analysis as a saved session"
- Multi-user / shared cloud sessions; signed report bundles
- More survey-log adapters out of the box; harden CI toward a turnkey installer

---

## Would you use it?

**Who it's for**
- Benthic ecologists & seabed-mapping teams doing **ground-truthing**
- Anyone who wants acoustics, imagery and video **on the same map** without
  stitching five tools together
- **New:** anyone who needs **quantitative seabed geometry** from imagery they
  already have — roughness, micro-relief, mosaics — without building a
  photogrammetry pipeline

**Honest take**
- If your work is *purely* acoustic processing → keep your specialist suite
- If you need sub-metre optical geometry at survey scale with full bundle
  adjustment → this is not a photogrammetry suite (yet)
- If it's **interpretation + ground-truth + reporting** across data types, inside
  GIS, open and scriptable → **yes**, and the optical side now measures as well as
  displays

---

## Need help setting it up?

- **Requirements:** QGIS 4.0+ (Qt 6), the bundled `.venv`, a FastGIS API key for
  GRASS and roughness features (or a direct URL if you run the GPU service yourself)
- **Install:** symlink the repo into your QGIS profile, enable the plugin, point
  Settings at your data — invalid keys now disable only their own feature
- **Try it:** the Zenodo *groundtruther test dataset* (CC-BY-4.0)
- Repo & issues: **github.com/epifanio/groundtruther**
- Docs: **epifanio.github.io/groundtruther** ·
  agent/dev notes in `docs/grass_fastgis.md` and `docs/photogrammetric_ribbon.md`
- Analysis workflow: `PDAL_MBIO/paper` — frozen manifest, notebooks 00→09

**Happy to walk you through install, config, or your own dataset.**

---

# Thank you

**GroundTruther** · v0.4 · QGIS 4 / Qt 6
*MBES · imagery · video · stereo geometry · roughness · mosaics · ribbon · report*

github.com/epifanio/groundtruther · epifanio.github.io/groundtruther
