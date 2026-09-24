# Screenshots — the shot list

The brief for each figure: what it must show, and why.

## Status (2026-09-24)

**Done — 7 images installed**

| file | page |
|---|---|
| `index-hero.jpg` | Home |
| `query-builder-1.jpg` | Query Builder (hero) |
| `query-builder-ara.png` | Query Builder → ARA |
| `query-builder-histogram.png` | Query Builder → Histogram |
| `image-browser-1.jpg` | Image Browser (hero) |
| `roughness-spectrum-1.png` | Seafloor Roughness → Spectrum |
| `roughness-microdem-3d.jpg` | Seafloor Roughness → Micro-DEM 3D |

Photo-dominated captures are **JPEG** (q90) and plot/line-art captures **PNG** —
the same crops as PNG throughout came to 4.5 MB against 1.5 MB this way.

**Still needed, in priority order**

1. `roughness-metrics-1.png` — the Metrics tab. The Seafloor Roughness page still
   leads with a placeholder, and γ₂ is its headline output.
2. `ribbon-1.png` + `ribbon-count.png` — nothing illustrates the ribbon at all.
3. `settings-dialog-1.png` (+ `settings-validation.png`)
4. `roughness-mosaic-1.png` (+ `roughness-mosaic-navplaced.png`)
5. `query-builder-3d-ref.png` — the Reference 3D tab.
6. `video-player-1.png`, `annotation-image-1.png`, `annotation-video-1.png`,
   `image-browser-2.png`, `report-builder-1.png`, `grass-settings-1.png`,
   `grass-region-1.png`, `grass-module-1.png`


**How to add one**

1. Capture in QGIS at **~1600 px wide**, PNG. Use the Zenodo
   [sample dataset](https://zenodo.org/records/7995674) so the images match the
   docs and can be re-shot by anyone.
2. Save it here under the exact filename below.
3. In the page named, swap the `placeholder.svg` `src` for your filename and delete
   the `<!-- TODO -->` comment above it.

**House style** — light QGIS theme; no other plugins' panels in frame; crop to the
dock plus enough canvas for context; blur or avoid any visible absolute path that
identifies a machine. Where a number is on screen (γ₂, a statistic, a VE factor),
make sure it is legible at 900 px display width — that is the width the pages
render at.

---

## Priority 1 — the site has no image of these at all

### `index-hero.png` — GroundTruther in QGIS
**Page:** `index.md` · **Currently:** the only image on the landing page.

The one image most people will ever see. Full QGIS window, with the bathymetry and
a backscatter layer on the canvas, the **Image Browser** dock open on one side
showing a real seafloor frame, and the GroundTruther toolbar visible. The red
position marker should be on the canvas near the displayed frame so the
image↔map link is self-evident. Aim for "four kinds of data, one map" at a glance
— resist opening every dock at once; three is legible, six is soup.

### `query-builder-ara.png` — The angular response (ARA tab)
**Page:** `tools/query-builder.md`, *The angular response (ARA)* · **supplied
2026-09-24.**

The **ARA** tab: backscatter against incidence angle for the selected soundings,
with the polynomial fit through the cloud and the **Data Model** radios
(Raw / L / R / Fold) in frame. This is the acoustic read-out of a sampling unit and
the natural lead figure for the page.

> **Superseded:** an earlier brief here asked for a **WGL** soundings-surface
> capture to illustrate the nearest-neighbour warning. Dropped on the tool author's
> advice, and the code agrees: WGL grids at a fixed 1.5 nodes/m across the
> selection's bounding box, so a ground-truthing sampling unit yields a 3×3-node
> "surface" and anything under ~0.7 m yields an empty one. Photographing it would
> have documented a use the tool is not for. The warning stays in prose; the
> relief figure is `query-builder-3d-ref.png` below.

### `query-builder-3d-ref.png` — The reference surface (Reference 3D tab)
**Page:** `tools/query-builder.md`, *Reading it quantitatively* · **Currently: none.**

The **Reference 3D** tab with a `reference_surface` GeoTIFF clipped to a sampling
shape. Must show: the **cursor read-out** with live Easting / Northing / Elevation,
a **two-point measurement** in progress (so the 3-D / horizontal / vertical
components are on screen), and the **VE slider with its label** — captured at
**1×**, so the page's "note the VE" advice is modelled rather than undermined. A
second capture of the same area at 10× would make an excellent before/after pair if
you want to spend two slots here.

### `ribbon-1.png` — A seabed ribbon over the bathymetry
**Page:** `tools/seabed-ribbon.md` (hero) · **Filename already referenced.**

The highest-value new capture on the site. `ribbon_dem.tif` loaded in QGIS over the
MBES bathymetry, zoomed so the **scale contrast is the subject**: the ribbon's
millimetre texture inside a 1 m-gridded surface. Include the QGIS **scale bar** —
without it the reader cannot tell whether they are looking at 2 m or 200 m, which is
the entire point of the product. A long, thin, track-aligned strip is the natural
shape; do not crop it to a square.

### `ribbon-count.png` — The observation-count layer
**Page:** `tools/seabed-ribbon.md`, *What you get* · **Currently: none.**

`ribbon_count.tif` with a graduated colour ramp, ideally beside or blended with the
DEM. The page calls this "the ribbon's honesty layer", so the capture must show
**variation**: cells at 1 (single frame, no cross-check), cells at 5–6 (well
observed), and at least one **zero/no-data gap** where a turbid frame was rejected.
A styled legend in frame is worth more than a prettier ramp.

---

## Priority 2 — pages whose main claim is unillustrated

### `roughness-metrics-1.png` — The Seafloor Roughness dock, Metrics tab
**Page:** `tools/seafloor-roughness.md` (hero) · **Filename already referenced.**

The dock on the **Metrics** tab for a frame whose `quality` is `ok`, with the **γ₂**
read-out large and legible — it is the page's headline output. Also visible: the
substrate and texture lines, `rugosity`, `altitude`, `quality`, `matcher`, and
crucially the **colour-coding on w₂ and rms height**. If you can catch a frame where
those two are *not* green, take that one: the page's "trust γ₂, not w₂'s absolute
value" warning is then visible in the UI rather than only in prose.

### `roughness-spectrum-1.png` — The relief power spectrum
**Page:** `tools/seafloor-roughness.md`, *Spectrum tab* · **Currently: none.**

The log-log W vs K plot with the fitted power law, the shaded fit band, and the
γ₂ / w₂ / R² annotations. Pick a frame where the measured curve visibly **peels away
from the fit line at high K** — the page teaches that as the stereo noise floor, and
this is the one image that makes that diagnostic learnable. A textbook-clean
spectrum would actually be the worse screenshot here.

### `roughness-microdem-3d.png` — Photo-textured micro-DEM
**Pages:** `tools/seafloor-roughness.md`, *Micro-DEM 3D tab* **and** the slide deck
(*Stereo photogrammetric reconstruction*) · **Currently: none.**

The **Micro-DEM 3D** tab with real heights draped in the orthophoto, tilted enough
that relief reads as relief. A frame with genuine structure — cobbles, a ripple
field, a burrow — beats smooth mud. If the border spikes are visible before
masking, a second capture with **trim border / clip σ / erode** applied would
document those three controls, which currently have no image.

### `roughness-mosaic-1.png` — A georeferenced mosaic
**Page:** `tools/seafloor-roughness.md`, *Mosaic* · **Currently: none.**

A mosaic on the map canvas, built over a window of frames, ideally where
**illumination correction** has done visible work (continuous brightness across
seams rather than a grid of bright centres). If you can also capture the
**low-texture warning banner** — *"only N/10 pairs registered — low texture, mosaic
is nav-placed"* — on a mud stretch, that is a second, separately valuable image:
`roughness-mosaic-navplaced.png`.

### `settings-dialog-1.png` — The Settings dialog
**Pages:** `configuration/index.md` **and** the slide deck · **Filename already
referenced.**

The dialog with the group boxes expanded enough to show that there is one per config
section. **Blank or blur the GRASS API key field** — it is a secret. A companion
capture of the **message-log tab showing a validation report** (a set-but-invalid
path reported as a warning while the plugin runs on) would illustrate the
degrade-don't-veto model, which is currently prose only: `settings-validation.png`.

---

## Priority 3 — existing placeholders on already-illustrated pages

| filename | page | what it must show |
|---|---|---|
| `image-browser-1.png` | `tools/image-browser.md` | The dock: image viewer, navigation controls and the **metadata panel** with real values (depth, position, altitude). Map visible with the red marker. |
| `image-browser-2.png` | `tools/image-browser.md` | Bounding-box annotations drawn over a frame, with the **confidence threshold control** in shot and set high enough that some boxes are filtered out. |
| `video-player-1.png` | `tools/video-player.md` | The dock mid-playback with the **GPS track** drawn as a layer and the position marker on it. Timeline and frame counter legible. |
| `annotation-image-1.png` | `tools/annotation.md` | The image annotation editor with a box selected and its **label + confidence** fields populated. |
| `annotation-video-1.png` | `tools/annotation.md` | Per-frame annotation in the Video Player — show that the box belongs to *this* frame (frame number visible). |
| `query-builder-1.png` | `tools/query-builder.md` | Hero. Ideally a **sampling shape** on the soundings *and* the ARA plot together; if the docks cannot be shown side by side, `query-builder-ara.png` already covers the plot, so this one should favour the **map + sampling shape**. |
| `report-builder-1.png` | `tools/report-builder.md` | The composed report — card layout, thumbnail gallery, statistics table. The **rendered HTML output** is more useful here than the builder UI; consider both. |
| `grass-settings-1.png` | `tools/grass-fastgis.md` | Connecting and selecting a GRASS **environment**. **Blank the API key.** |
| `grass-region-1.png` | `tools/grass-fastgis.md` | The **computational region** rectangle rendered on the canvas over the bathymetry. |
| `grass-module-1.png` | `tools/grass-fastgis.md` | A dialog **generated from a module's interface description** — `r.geomorphon` as the docs say. The point is that nobody hand-wrote this form, so show enough fields to make that obvious. |

---

## Slide deck

`docs/slides_groundtruther_update_2026.{md,html}` and `docs/build_pptx.py` carry
**10** dashed screenshot boxes. Eight are satisfied by images above:

| deck slot | reuse |
|---|---|
| GroundTruther docked in QGIS (overview) | `index-hero.png` |
| plugin running in QGIS 4 (toolbar + docks) | `index-hero.png` (or a wider variant) |
| Settings dialog + validation report | `settings-dialog-1.png` + `settings-validation.png` |
| GRASS Tools panel + generated module form | `grass-module-1.png` |
| query builder: sampling unit + ARA scatterplot | `query-builder-1.png` |
| video dock + GPS track | `video-player-1.png` |
| HTML report with gallery + statistics | `report-builder-1.png` |
| Micro-DEM 3D, photo-textured mesh | `roughness-microdem-3d.png` |
| Metrics + Spectrum side by side | `roughness-metrics-1.png` + `roughness-spectrum-1.png` |

Two are deck-only:

### `dock-layout-session.png` — A saved workspace
**Deck slide:** *Dock workspace & session persistence*.

A deliberately **customised** dock arrangement — panels moved, resized, some
floating — so that "this layout survives a restart" is a visible claim. Pair it with
the Settings field holding the `groundtruther_project` path.

---

## Deliberately not screenshots

The slide deck's Act III (HRS1508) uses **tables of numbers**, not captures. If you
want figures there instead, the analysis already emits them:
`F11_ablation.png`, `F12_calibration_stress.png`,
`S1_coverage_gate_by_class.png` and `S2_support_vs_separability.png` in the paper
run's `figures/` directory. They are plots, not screenshots, and belong to the
frozen run that produced them — copy them with their `run_id` recorded.

PNG/JPG/WebP/SVG are all served as-is by MkDocs.
