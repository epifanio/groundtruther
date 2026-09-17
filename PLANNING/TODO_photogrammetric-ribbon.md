# TODO — A photogrammetric seabed ribbon, to close the scale gap between the micro-DEM and the MBES

| | |
|---|---|
| **Status** | `PLANNED` |
| **Type** | feat |
| **Worktree branch** | `feat/photogrammetric-ribbon` |
| **Created** | 2026-09-17 |
| **Related memory** | `data-model-facts`, `roughness-integration`, `fastgis-grass-api`, `documentation` |
| **Execution PR** | _(filled in by the execution agent)_ |
| **Depends on** | [#31](https://github.com/epifanio/groundtruther/issues/31) — the heading fix **must land first** |

## Objective

Build one **continuous, georeferenced, millimetre-resolution elevation ribbon** of the
seabed by compositing the per-frame stereo micro-DEMs along a single HabCam track, and
use it to answer a question neither existing product can: **does the roughness measured
inside one frame extrapolate to the scales the acoustics actually see?**

Today there is a hole in the middle of the scale range:

| product | wavelengths it supports |
|---|---|
| per-frame micro-DEM | ~3 mm … **1.2 m** (one frame's footprint) |
| MBES bathymetry (`bathy_2015.tif`) | **≥ 2–3 m** (1 m grid) |
| **nothing** | **1.2 m … 3 m** |

γ₂ — the load-bearing roughness metric — is fitted inside a single frame and then used to
interpret backscatter whose footprint is metres across. Nobody has checked that the
power law holds across the gap. A 170 m ribbon at 3 mm spans **3 mm to 170 m along
track**, closing it in one product.

"Done" = the ribbon exists as a GeoTIFF pair (elevation + orthophoto) in the survey CRS,
its along-track profile has been compared against the MBES, and the along-track power
spectrum has been computed and compared with the per-frame γ₂.

## Context & background

### This was scoped from measurements, not from hope

The idea came from the user: *"create a 3D surface from overlapping frames … and match it
against a terrain feature on the bathymetry."* Before writing this plan the three
assumptions it rests on were tested against the real data. Two held, one did not and
changed the design.

**1. Is there enough contiguous stereo coverage?** Yes. The stereo archive is on an
external drive — `/run/media/epinux/WD_BLACK/DATA/HBC/DATA/2015_stereo`, **73 710**
`*_orig.png` (2720 × 1024 side-by-side; the left half is the `imgs_jpg` delivery). There
are **161 contiguous runs of ≥150 frames that sit ≥80 % on the MBES DEM.**

**2. Is there relief worth comparing against?** Yes. `bathy_2015.tif` is 3456 × 679 at
**1.00 m**, EPSG:32619, −81.96…−55.05 m, 53 % valid; 90 659 of 123 394 frames fall inside
it, and the depth under the track ranges over **24.37 m**. Individual candidate strips
carry 3.7–5.8 m of relief over ~170 m.

**3. Can consecutive frames be registered to each other?** **Only on some strips, and
the selection criterion is texture — not relief.** This is the finding that shaped the
design. Measured on three candidate strips, 150 consecutive pairs each:

| strip (rows) | nav overlap | template NCC ≥ 0.4 | **ORB + RANSAC ≥ 15 inliers** |
|---|---|---|---|
| 62911–63061 | 46 % | 0 % (median NCC 0.04) | **0 %** (median 5 inliers) |
| 43537–43687 | 38 % | 13 % (median 0.20) | **59 %** (median 40) |
| 6663–6813 | 36 % | 47 % (median 0.36) | **57 %** (median 64) |

Three things follow, and all three are design constraints:

- **Use ORB + RANSAC, not template matching.** Template matching understates the link
  rate badly (13 % vs 59 % on the same frames). The earlier scroll-direction work used
  template matching because it only needed a *median over many pairs*; a ribbon needs
  *this* pair, so the sensitive method is required.
- **Select strips by texture, not by relief.** The strip with the most relief
  (55651–55954, 5.83 m) is **featureless mud: 1 % link rate, median NCC 0.08** — it would
  have been the obvious pick and it is unbuildable. Strip 62911 likewise: 0 % by both
  methods. Texture and relief are uncorrelated here.
- **Expect a hybrid, not a clean chain.** At a ~58 % link rate, runs of consecutive links
  average ~2.4 frames. The ribbon's relative geometry will be short registered segments
  bridged by navigation, not one continuous photogrammetric chain. That is acceptable —
  absolute placement comes from the nav anyway — but it must be reported, not hidden.

### Why nav alone will not do it

`INTERFACE.md` says it and the data confirms it: **the USBL is piecewise-constant between
fixes.** On the candidate strip the median *per-frame* nav step is **91 mm** while the
imagery shows the vehicle actually advances **510 mm** per frame (aggregate nav over the
whole strip agrees: 172 m / 303 frames = 568 mm). So consecutive frames placed by raw nav
**stack in clumps of ~6 and then jump**. A purely nav-placed ribbon would be visibly
shingled.

### The hard dependency

[#31](https://github.com/epifanio/groundtruther/issues/31): GroundTruther currently sends
`heading_deg = bearing`, which is the ship→body direction — **180° out**. Every frame's
geotransform is rotated by that. Building a ribbon before the fix lands would composite
304 individually back-to-front frames. **This dependency is satisfied once PR
[#35](https://github.com/epifanio/groundtruther/pull/35) is merged** — Track 3 of
`PLANNING/docs-audit-code-findings.md` fixed the client side. Note that the **service**
still has the same bug for mode-A mosaics
([stereo-roughness#1](https://github.com/epifanio/stereo-roughness/issues/1)), so a ribbon
built by the service rather than from client-supplied nav is still 180° out.

### What exists already and should be reused

- `gt/roughness_client.roughness_for_frame(...)` — request `dem_format:"mm"`,
  `include_orthophoto`, and a `geo` object to get a real-height grid plus a geotransform.
- `gt/roughness_geo.py` — `geo_from_record` (builds the request `geo`), `extract_geo`
  (the `geo` block is **nested under `micro_dem`/`orthophoto`**, not top-level),
  `write_geotiff`.
- `gt/roughness_dem.py` — `decode_float_grid` (base64 float32, NaN = no data),
  `mesh_from_micro_dem`, `colors_from_rgb`.
- `gt/roughness_spectrum.py` — `prepare_spectrum`, for the per-frame γ₂ this plan
  compares against.
- The response's geotransform is a **rotated affine** `[c, a, b, f, d, e]`
  (`E = c + a·col + b·row`). Do not assume north-up.

## Scope

**In scope:**

- A stateless `gt/ribbon.py`: strip selection by texture, ORB registration with nav
  bridging, resampling many rotated micro-DEM grids into one north-up UTM grid, and
  writing the elevation + orthophoto GeoTIFFs.
- A disk cache for the API responses, keyed by frame — ~300 calls per strip is enough to
  be worth never repeating.
- The two analyses that justify the product: the **1 m-binned along-track profile vs
  `bathy_2015.tif`**, and the **along-track power spectrum vs the per-frame γ₂**.
- A short docs page describing the ribbon, how to build one, and the texture constraint.
- Unit tests for everything geometric (grid resampling, ORB-chain-with-gaps, binning)
  against synthetic inputs — no network in the test suite.

**Out of scope:**

- **A QGIS UI for this.** Build it as a script/notebook-style entry point first. Wiring a
  dock for a product nobody has looked at yet is premature; decide after seeing one.
- **Full structure-from-motion / bundle adjustment.** The per-frame micro-DEMs are already
  metric and individually georeferenced; this plan composites them, it does not re-derive
  geometry. If the seams turn out to need bundle adjustment, that is a separate plan.
- **Cross-track mosaics.** A single HabCam line has **no** cross-track overlap — the
  product is a ~1.2 m wide ribbon, and no amount of processing makes it a surface.
- Changing the roughness service, or anything in `INTERFACE.md`.
- Re-testing the heading question. It is settled; this plan **consumes** the fix.

## Prerequisites

- Read: `CLAUDE.md`, project memory (`MEMORY.md` + `data-model-facts`,
  `roughness-integration`, `documentation`), and
  `/home/epinux/dev/stereo-roughness/INTERFACE.md` §`geo`, §`micro_dem`, §`orthophoto`.
- **[#31](https://github.com/epifanio/groundtruther/issues/31) must be merged.** Verify:
  `geo_from_record` on a record with only `bearing` returns `heading_deg = bearing + 180`.
- **Mount the stereo drive**: `/run/media/epinux/WD_BLACK/DATA/HBC/DATA/2015_stereo`.
  Random access over USB is slow — read contiguous runs, and cache anything derived.
- Live API credentials (`Processing.grass_api_key`). This plan **is** authorised to call
  `/seafloor/roughness` for one strip (~300 frames). Cache every response to disk on
  arrival; do not re-request. Do not run multiple strips before the first is reviewed —
  the GPU is shared.
- Reference data: `groundtruther_test_dataset/projectdata.pq`,
  `groundtruther_test_dataset/groundtruther_test_dataset/bathy_2015.tif`.

## Worktree setup

```bash
cd /home/epinux/dev/groundtruther
git fetch origin
git worktree add ../groundtruther-photogrammetric-ribbon -b feat/photogrammetric-ribbon origin/master
cd ../groundtruther-photogrammetric-ribbon
ln -s /home/epinux/dev/groundtruther/.venv .venv
```

## Task breakdown

### Phase 1 — pick the strip (no API calls)

- [ ] **1. Score the 161 candidate runs by texture**, using ORB + RANSAC inlier counts on
      consecutive pairs (sample ~30 pairs per run; the full pass over the archive is slow).
      Record link rate and median inliers per run. **This replaces relief as the selection
      criterion** — see Context.
- [ ] **2. Pick the strip** maximising (link rate × relief × on-DEM fraction). The current
      front-runner from the sampling already done is **rows 6663–6958** — 296 frames,
      172 m of track, 4.16 m of relief under it, 100 % on the DEM, 36 % nav overlap,
      **57 % ORB link rate**. Backup: **43537–43851** (315 frames, 175 m, 3.70 m, 59 %).
      Avoid 55651–55954 and 62911–63201 — highest relief, no texture, unbuildable.
- [ ] **3. Build the registration chain offline**, imagery only: ORB + RANSAC between
      consecutive left halves, reject transforms inconsistent with the expected ~510 mm
      advance, and **bridge unlinked gaps with nav**. Output a per-frame 2-D pose
      (position + heading) plus a per-frame flag saying whether it came from pixels or
      nav. Plot it against the raw nav; the improvement over the 91 mm-per-frame USBL
      quantization is the thing to look at.

### Phase 2 — fetch (the only API phase)

- [ ] **4. Disk cache first, then fetch.** `dem_format:"mm"`, `include_orthophoto`,
      `geo` from the corrected `geo_from_record`, `dem_max_side` at the service default.
      ~300 calls; first is ~14 s cold, then ~0.5 s. Persist raw JSON per frame keyed by
      `frame_key` **before** any decoding, so a decode bug never costs a refetch.
- [ ] **5. Sanity-check the batch**: `quality == "ok"` rate, `altitude_mm` vs the metadata
      `Altimeter` (they should agree to a few cm), `valid_fraction`, and that every
      `micro_dem` carries a nested `geo` block. Report the `insufficient_coverage` rate —
      on turbid frames it will not be zero.

### Phase 3 — composite

- [ ] **6. `gt/ribbon.py` — resample into one grid.** Target 3 mm in the survey CRS
      (EPSG:32619). At 172 m × ~1.2 m that is roughly **57 000 × 400** cells — ~92 MB
      float32 per band, which is fine; 1 mm would be 9× that and is not. Each frame's grid
      is a **rotated** affine, so this is a proper resample, not a paste.
- [ ] **7. Blend the overlaps.** ~36–46 % along-track overlap means most cells are seen
      twice. Start with a distance-transform feather (what the service's mosaic does);
      keep the per-cell observation count as a QA band.
- [ ] **8. Write the outputs**: `ribbon_dem.tif` (1-band Float32, NaN nodata) and
      `ribbon_ortho.tif` (3-band RGB), both EPSG:32619, via `roughness_geo.write_geotiff`.
      Confirm they land on the bathymetry in QGIS.
- [ ] **9. Quantify the seams** — where two frames overlap, the elevation difference
      between them is the registration error. Report its distribution, split by whether
      the link was pixel-derived or nav-bridged. **This number is the honest quality
      statement for the whole product**; put it in the docs page.

### Phase 4 — the two analyses that justify it

- [ ] **10. Profile vs MBES.** Bin the ribbon to 1 m along track, compare against
      `bathy_2015.tif` sampled at the USBL fix. **Baseline to beat: the vehicle's own
      `-(V_Depth + Altimeter)` already matches the MBES to 0.27 m median** (corr 0.662,
      n ≈ 78 000) — that measurement is in the `data-model-facts` memory. If the ribbon
      does not beat 0.27 m, say so plainly; it would mean the ribbon adds texture, not
      accuracy, which is still a legitimate result.
- [ ] **11. The scale-gap spectrum — the point of the exercise.** Compute the along-track
      1-D power spectrum of the ribbon across 3 mm … 170 m. Overlay the per-frame γ₂ fits
      (`gt/roughness_spectrum.prepare_spectrum`) and the MBES-derived spectrum where they
      overlap. **Does the per-frame power law extrapolate into the 1.2–3 m band, or does
      it break?** Either answer is publishable; a break would mean γ₂ must not be
      extrapolated to acoustic footprints without a correction.
- [ ] **12. Write it up** — a `website/docs/tools/` page or a `docs/` note (decide which:
      the ribbon is a script, not a plugin tool, so it may belong in `docs/`). Must state
      the texture constraint, the seam error from task 9, and the spectrum result.

### Closing

- [ ] **13. Tests, memory, Progress Log**, rename `TODO_` → `Status: DONE`, PR opened and
      left unmerged.

## Acceptance criteria & verification

- [ ] `.venv/bin/pytest` green including new unit tests for the geometry
      (grid resampling, chain-with-gaps, binning) — all synthetic, no network.
- [ ] `ribbon_dem.tif` + `ribbon_ortho.tif` exist, load in QGIS in EPSG:32619, and overlay
      the bathymetry in the right place.
- [ ] The strip's **link rate, seam error distribution and `quality != "ok"` rate** are all
      reported. A ribbon without these numbers is not finished.
- [ ] The profile comparison is stated **against the 0.27 m altimeter baseline**, whichever
      way it falls.
- [ ] The along-track spectrum is plotted across the full range with the per-frame γ₂
      overlaid, and the question in task 11 is answered in one sentence.
- [ ] Every API response cached to disk; a rebuild from cache needs no network.
- [ ] `config/config.yaml` never staged; `website/site/` not committed.

### Manual checks by the user

- [ ] **Look at the ribbon over the bathymetry in QGIS.** Does it sit where that piece of
      seabed should be, and does the relief agree? You know this ground.
- [ ] Look at the orthophoto ribbon at full resolution and judge the seams — the numbers in
      task 9 say how big they are, but you can say whether they matter.
- [ ] Sanity-check the spectrum result against what you expect physically before it goes
      anywhere near a paper.

## Risks & rollback

- **Risk: the chosen strip turns out to be unbuildable anyway.** Link rate was sampled at
  30 pairs per run; the full strip may be worse. *Mitigation:* task 3 runs the whole chain
  **offline, before any API call** — if the link rate collapses, switch strips at zero cost.
- **Risk: the ribbon is shingled and ugly.** With ~42 % of links nav-bridged and the USBL
  quantized to ~91 mm per frame, visible steps are likely. *Mitigation:* task 9 measures
  it rather than arguing about it. If it dominates, stop and report — bundle adjustment is
  explicitly a different plan.
- **Risk: `insufficient_coverage` on turbid frames punches holes.** Expected, not fatal —
  the ribbon carries NaN and the observation-count band shows where. Report the rate.
- **Risk: scope creep into a QGIS dock.** Explicitly out of scope. Build the product,
  look at it, then decide.
- **Risk: building on the un-fixed heading.** Would silently produce a ribbon of 304
  back-to-front frames. *Mitigation:* the prerequisite check is a one-liner — run it.
- **Rollback:** own branch and worktree; the only external effect is ~300 cached API
  responses. Nothing in the plugin changes unless Phase 3 adds `gt/ribbon.py`, which is
  new and imported by nothing else.

## Kickoff prompt

```
You are working on the GroundTruther QGIS plugin (QGIS 4 / Qt6). Execute the plan in
PLANNING/TODO_photogrammetric-ribbon.md end to end.

First: read CLAUDE.md and review the project memory (your recalled memories + the
MEMORY.md index). Then confirm the hard prerequisite — issue #31 (the roughness heading
fix) must already be merged; check that geo_from_record on a record carrying only
`bearing` returns heading_deg = bearing + 180. If it does not, STOP: building this ribbon
on the un-fixed heading composites hundreds of individually back-to-front frames.

Then create the dedicated worktree exactly as the plan's "Worktree setup" section
specifies (branch: feat/photogrammetric-ribbon), and mount the stereo drive at
/run/media/epinux/WD_BLACK/DATA/HBC/DATA/2015_stereo.

Work the Task Breakdown in phase order. Phase 1 is entirely offline and decides whether
the strip is buildable — do not spend a single API call before its link rate is in hand.
Phase 2 is the only phase that calls the service (~300 frames, one strip); cache every
raw response to disk before decoding anything, and do not run a second strip before the
first is reviewed.

Two things this plan cares about more than a pretty picture: the honest quality numbers
(link rate, seam error, quality != "ok" rate), and the task-11 spectrum question — does
the per-frame gamma2 power law extrapolate into the 1.2-3 m band the acoustics see? A
negative answer is as valuable as a positive one; do not round it off.

Note that strip selection is by TEXTURE, not relief. The strip with the most relief in
this survey is featureless mud with a 1% link rate. Use ORB + RANSAC, not template
matching, to measure it.

When done: run .venv/bin/pytest (and mkdocs build --strict if a site page changed),
update the project memory with your findings, fill the Progress Log, rename
PLANNING/TODO_photogrammetric-ribbon.md → PLANNING/photogrammetric-ribbon.md
(Status: DONE), and open a PR against master (gh, account epifanio). Do NOT merge — I
will review, and I want to look at the ribbon over the bathymetry in QGIS myself first.
```

## Progress log

_(appended by the execution agent)_
