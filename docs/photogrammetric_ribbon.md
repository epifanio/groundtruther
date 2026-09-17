# The photogrammetric seabed ribbon

A **ribbon** is the along-track composite of a few hundred per-frame stereo
micro-DEMs from one HabCam line: ~170 m of seabed at millimetre resolution,
georeferenced in the survey CRS. It exists to close a hole in the middle of the
scale range:

| product | wavelengths it supports |
|---|---|
| per-frame micro-DEM | ~3 mm … **1.2 m** (one frame's footprint) |
| MBES bathymetry (`bathy_2015.tif`) | **≥ 2–3 m** (1 m grid) |
| **the ribbon** | **3 mm … 170 m** — it spans the whole range |

γ₂, the load-bearing roughness metric, is fitted inside a single frame and then
used to interpret backscatter whose footprint is metres across. Nobody has
checked that the power law holds across the gap. A ribbon can check it.

This is a **script, not a plugin tool** — `scripts/build_ribbon.py`. Nothing here
is wired into the QGIS dock; that decision waits until someone has looked at a
ribbon. The reusable geometry lives in [`gt/ribbon.py`](../gt/ribbon.py) and is
unit-tested against synthetic inputs with no network.

## Status

| phase | state |
|---|---|
| 1 — strip selection and the offline registration chain | **done, on real imagery** |
| 2 — fetch the micro-DEMs from the roughness service | **blocked**: the API key in `config/config.yaml` is rejected (`401 invalid or revoked API key`) |
| 3 — composite | code complete, **verified on a synthetic seabed**, never run on real micro-DEMs |
| 4 — profile vs MBES, and the scale-gap spectrum | the service-independent halves are done on real data; the ribbon halves await phase 2 |

To finish it, put a working FastGIS key in `Processing.grass_api_key` and run:

```bash
scripts/build_ribbon.py fetch     --start 6663 --n 296   # ~296 calls, cached to disk
scripts/build_ribbon.py inspect   --start 6663 --n 296   # quality, altitude, geo checks
scripts/build_ribbon.py composite                         # -> ribbon_dem.tif, ribbon_ortho.tif
scripts/build_ribbon.py analyse                           # -> the two results
```

Phases 1 and 3–4 need no credentials; `simulate` stands in for phase 2.

## Choose the strip by texture, never by relief

This is the finding that shapes everything else. Consecutive frames can only be
registered to each other where the seabed has **texture**, and on this survey
texture and relief are uncorrelated:

| strip (rows) | relief | link rate | median inliers |
|---|---|---|---|
| 55651–55954 | **5.80 m** (the most in the survey) | 57 % | 22 |
| 9081–9383 | 5.42 m | 20 % | 10 |
| 62911–63201 | 3.75 m | **0 %** | 10 |
| 47465–47653 | 4.04 m | **0 %** | 9 |
| **6663–6958** | 4.21 m | **77 %** | **239** |
| 43537–43851 | 3.67 m | 87 % | 85 |

Measured by `scripts/build_ribbon.py scan`: ORB + RANSAC on 30 consecutive pairs
per run, sampled in five blocks spread across the run. Two runs with metres of
relief register on **none** of the pairs sampled — they are featureless mud, and
picking by relief would have chosen one of them.

The scan is ordered by descending relief and stops as soon as the best score so
far (`link_rate × relief × on_dem_fraction`, and `link_rate ≤ 1`) exceeds the
relief of every remaining run. That is a proof, not a sampling shortcut: after 13
of the 161 candidate runs, no unscanned run could reach the leader.

> **These numbers are not comparable with the planning table.** Those were
> measured with a plain ORB+RANSAC and only over the first 150 frames of each
> run; this matcher adds a displacement prefilter and a physical gate, and
> samples the whole run. Strip 55651 is the clearest case: 1 % over its first
> 150 frames, 57 % sampled across all 304, so its texture is real but localised.
> Its median of 22 inliers against strip 6663's 239 is the honest discriminator,
> and is why 6663 was chosen despite a fractionally lower composite score.

### Why ORB and not template matching

Template NCC is fine for a *median over many pairs* — the heading work used it
for exactly that. It is far too blunt for "is **this** pair linked", which is
what a ribbon needs: on the same 150 pairs it called 13 % linked where ORB called
59 %.

But ORB on this imagery needs help. The frames are dark (mean grey ~21/255) and
the texture repeats, so:

- **No preprocessing.** Flat-fielding and CLAHE both *lowered* the inlier count —
  they amplify the sensor noise the descriptors then lock onto.
- **A loose Lowe ratio (0.95).** A strict one throws away nearly every true
  match.
- **Detection masked to the overlapping band.** The platform advances ~45 % of a
  frame height per frame, so more than half the features in each image have no
  counterpart at all and are pure distractors.
- **A displacement prefilter before RANSAC, and a physical gate after it.** This
  is not optional. Without it RANSAC routinely returns a confident 15–25-inlier
  consensus on a completely wrong transform; several were observed on real
  pairs. The gate checks the implied advance is in band, the motion is roughly
  along track, the scale is near unity and the rotation small.

## The chain: pixels where they work, navigation everywhere else

The USBL is piecewise-constant. On the chosen strip its median *per-frame* step
is **92 mm** while the imagery shows the vehicle advancing **491 mm** — so
frames placed by raw nav stack in clumps of ~6 and then jump.

`chain_track` integrates the accepted links into a track, bridges unlinked pairs
with the nav, and then rubber-sheets the result back onto the nav over a
51-frame window so *absolute* placement still comes from the USBL while the
*relative* geometry comes from the pixels. Two details matter:

- The anchor smoother is **Gaussian and trend-preserving**. A moving average
  only attenuates the nav's 6-frame sawtooth by about a factor of ten, which puts
  a ~7 cm ripple straight back into the per-frame steps; and a smoother that is
  blind to a linear trend shortens the track by several percent, which would
  arrive disguised as a camera focal length.
- Within half a window of either end there is not enough data to average the
  clumps away, so the first and last ~25 frames keep a little of the staircase.
  Another reason a ribbon wants a long run.

### Measured on strip 6663–6958 (296 frames, 172 m)

| | |
|---|---|
| link rate | **89.8 %** (265/295 pairs) |
| median inliers, linked pairs | 309 |
| longest unbroken registered run | **119 pairs** (mean 48) |
| rejections | 28 too few inliers, 1 rotation, 1 advance out of band |
| nav step per frame | median 92 mm (min 13, max 3538) |
| chain step per frame | median 491 mm (min 8, max 3345) |
| frames placed from pixels / from nav | 265 / 31 |

The plan expected a hybrid of ~2.4-frame registered fragments bridged by nav. At
this link rate it is the other way round: a nearly continuous photogrammetric
chain with 31 nav-bridged gaps.

**Two independent checks that the geometry is right**, both of which a 180°
heading error or a sign slip in the body axes would break:

- The chain's own end-to-end azimuth is **273.1°**; the corrected nav heading is
  **273.2°**. Before [#31](https://github.com/epifanio/groundtruther/issues/31)
  the plugin sent `heading_deg = bearing`, which would have put this 180° out and
  run the chain backwards.
- Calibrating the focal length against the nav's end-to-end displacement over
  50-frame windows returns **2507 px against the nominal rectified-left 2480.28 px
  — a ratio of 1.011**. The mount convention, the body axes and the
  `altitude/focal` ground sample distance all have to be right for that to land
  within 1 %.

## Compositing

Each frame's micro-DEM arrives on its own **rotated** affine, so combining them
is a resample, not a paste. The target grid is aligned to the track, not
north-up: 172 m of ribbon at 3 mm is ~57 000 × 400 cells track-aligned but
~41 000 × 41 000 in a north-up box — seventy times the cells for the same data.
(`--north-up` is available and guarded by `--max-cells`.) QGIS warps rotated
rasters to north-up on display; the file and its georeference are correct.

The cached service response keeps the **nav-built** geotransform, and the chain's
correction is applied at composite time by `adjust_geotransform`. That keeps the
response cache independent of whatever the chain happened to produce, so the
chain can be re-derived without refetching.

Overlaps are feathered by distance to the frame edge and a **per-cell
observation count** ships as `ribbon_count.tif` — where it falls to zero the
frame was turbid and the service returned `insufficient_coverage`.

## The two results

### Profile vs MBES — the baseline to beat

The bar is not zero. The vehicle's own `-(V_Depth + Altimeter)` already tracks
the MBES well, and **on this strip it does much better than survey-wide**:

| | corr | median &#124;dz&#124; |
|---|---|---|
| survey-wide (n ≈ 78 000, from the `data-model-facts` memory) | 0.662 | 0.27 m |
| **this strip (n = 296)** | **0.988** | **0.115 m** |

So strip 6663–6958 is an easy one for the altimeter and a hard target for the
ribbon. If the ribbon does not beat 0.115 m here that is a legitimate result — it
would mean the ribbon adds texture, not vertical accuracy — and it should be
reported that way rather than compared against the softer survey-wide number.

### The scale-gap spectrum — the point of the exercise

The per-frame fit is two-dimensional and isotropic,
`W2(K) = w2·(K/k_ref)^(-γ₂)`; a ribbon profile measures the one-dimensional
`W1(k)`. Integrating out the unmeasured cross-track wavenumber gives a closed
form with **no free parameter**:

```
W1(k) = w2 · k_ref^γ₂ · k^(1-γ₂) · √π · Γ((γ₂-1)/2) / Γ(γ₂/2)
```

so `γ₁ = γ₂ - 1` and the amplitude follows too (`ribbon.w1_from_gamma2`, checked
against numerical integration in the tests). Fit the ribbon's own spectrum in the
**1.2–3 m** band and compare: that is the whole question.

**A raw periodogram cannot answer it.** Across 1.2–3 m a 172 m profile holds only
~30 Fourier ordinates and each carries ~100 % relative error; fitted raw, a
planted exponent came back scattered by more than a unit. The spectrum is
**band-averaged in log-spaced bins** before fitting, and `power_law_fit` reports
a standard error on the exponent. Quote it.

#### What can be said today

Real, service-independent, on this strip:

- **MBES along-track spectrum: γ₁ = 3.60 ± 0.16, i.e. γ₂ ≈ 4.60**, fitted over
  2–40 m (r² 0.95, 27 bands). Per-frame γ₂ on this survey runs ~2.4–3.6, so the
  metre-scale spectrum is **much steeper** than the frame-scale one. That is a
  hint that the power law does *not* extrapolate — but it is only a hint, and it
  must not be quoted as the answer: a 1 m MBES grid is smoothed by its own
  gridding near the grid scale, which steepens a spectrum exactly here. The
  ribbon is the instrument that settles it, because it measures both bands with
  one sensor.

Verified on a synthetic seabed with a planted γ₂ = 3.00, run through the real
`simulate → composite → analyse` path:

- recovered **γ₁ = 2.35 ± 0.41** in the 1.2–3 m band (planted 2.00 — inside 1σ);
- measured/predicted power in that band **1.02× (+0.1 dB)** — the extrapolation
  identity survives the composite intact;
- seam error **9.0 mm** median, which is the resampling-and-blending floor of the
  method, since the simulation has no registration error by construction.

**The real answer is not in yet, and is not being guessed at.** It needs phase 2.

## Honest quality numbers

A ribbon without these is not finished. Report all four:

| number | where it comes from | status |
|---|---|---|
| link rate | `chain` | **89.8 %** |
| seam error, split pixel-linked vs nav-bridged | `composite` | 9.0 mm on the synthetic; **real value pending** |
| `quality != "ok"` rate | `inspect` | **pending** (needs phase 2) |
| γ from the gap band, with its standard error | `analyse` | **pending** |

## Things to check on the first real fetch

- `inspect` prints `geotransform heading - nav heading`. It **must** be ~0. The
  compositing convention — image bottom→top is the heading, image-right is
  starboard — was derived from `INTERFACE.md` and is consistent throughout
  `gt/ribbon.py` and its tests, but it has never been confirmed against a real
  response. If that number comes back near 180, the service still has
  [stereo-roughness#1](https://github.com/epifanio/stereo-roughness/issues/1).
- `altitude_mm` against the metadata `Altimeter` (expect a few cm).
- That every `micro_dem` carries a **nested** `geo` block; there is no top-level
  one.
- The `insufficient_coverage` rate. On turbid frames it will not be zero.

## Out of scope, deliberately

- **A QGIS dock.** Look at a ribbon first.
- **Bundle adjustment.** The micro-DEMs are already metric and individually
  georeferenced; this composites them. If the seams turn out to need more, that
  is a separate plan.
- **Cross-track mosaics.** One HabCam line has no cross-track overlap. The
  product is a ~1.2 m wide ribbon and no processing makes it a surface.
