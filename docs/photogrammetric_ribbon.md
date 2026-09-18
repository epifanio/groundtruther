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

Built and run end to end on strip 6663–6958. The service runs **on this machine**
— container `stereo-roughness`, port 7871 — and the client posts straight at it
with no auth header, so no FastGIS API key is involved:

```bash
scripts/build_ribbon.py inventory
scripts/build_ribbon.py scan
scripts/build_ribbon.py chain     --start 6663 --n 296
scripts/build_ribbon.py fetch     --start 6663 --n 296 \
    --direct-url http://127.0.0.1:7871/roughness
scripts/build_ribbon.py inspect   --start 6663 --n 296
scripts/build_ribbon.py composite
scripts/build_ribbon.py analyse
```

`api.fastgis.eu` is a *different* host (65.21.215.94) and its key store is a
Redis inside that deployment, so an expired key cannot be regenerated locally —
but with the GPU service on the same box, it does not need to be. `--direct-url`
is also read from `ROUGHNESS_DIRECT_URL`. `simulate` still stands in for the
fetch when neither is available.

Outputs (gitignored, in `ribbon_work/`): `ribbon_dem.tif` (1256 × 48339 Float32,
EPSG:32619, track-aligned at 273.1°, 18.3 M valid cells), `ribbon_ortho.tif`
(3-band RGB) and `ribbon_count.tif` (observations per cell, 1–6).

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

#### The answer, and why it is not a clean one

**Measured on the ribbon: 9.45× (+9.8 dB) more power in the 1.2–3 m band than the
per-frame γ₂ law predicts, with a fitted γ₁ = 2.29 ± 1.56 against a predicted
1.97.**

Read that with both error bars in view, because neither is small:

- **The slope is unconstrained.** ±1.56 on an exponent spans essentially every
  physically plausible value. The band is one third of a decade wide; that is all
  a 145 m ribbon can offer, and it is not enough to fit a slope.
- **The amplitude excess is only 1.7× above the ribbon's own noise floor.**
  Independent per-frame vertical placement errors of standard deviation σ, held
  across each frame and changing every 0.49 m, put a nearly flat spectrum right
  across this band (`registration_noise_spectrum`). At the measured σ = 60 mm
  that floor sits just 1.7× under the measurement. Using the *robust* σ = 21 mm —
  which excludes a handful of frames whose micro-DEM is genuinely metres out — the
  margin is 14×.

So the honest statement is: **the ribbon shows excess power at metre scales
relative to the per-frame extrapolation, and that is the interesting direction,
but this ribbon cannot separate it from its own registration noise.** It is
suggestive, not conclusive. A γ₂ extrapolated to an acoustic footprint would
under-predict roughness if the excess is real — which is the result worth chasing,
not one to claim on 1.7×.

**What would settle it is now a number.** To put the noise floor 10× below the
predicted signal, per-frame vertical placement would have to reach **≈ 6 mm**,
against the 60 mm achieved here — a factor of ten. That is a vertical
bundle-adjustment problem, and it is the single thing standing between this
product and a publishable answer.

Two supporting measurements, both real:

- **MBES along-track spectrum: γ₁ = 3.60 ± 0.16 (γ₂ ≈ 4.60)** over 2–40 m,
  r² 0.95. Far steeper than the per-frame γ₂ of 2.97 — consistent with the power
  law breaking somewhere between the two, but a 1 m grid is smoothed by its own
  gridding exactly there, so on its own it proves nothing.
- The ribbon's gap-band fit (γ₂ ≈ 3.29) sits *between* the frame scale (2.97) and
  the MBES scale (4.60), which is what a gradual break would look like. At
  ±1.56 that is a remark, not evidence.

### Vertical levelling — and what it cost

The dominant vertical error was not the photogrammetry. `V_Depth` is quantized to
10 mm and steps frame to frame with σ = **82 mm**, which is essentially the whole
of the measured per-frame vertical scatter (σ = 66 mm robust, before levelling).
The micro-DEMs measure their own relative height far better than that wherever
they overlap, so `level_vertically` solves for per-frame offsets from the overlap
medians (robust IRLS, lag-1 and lag-2 pairs for loop closure) and keeps only the
high-frequency part — the datum still belongs to the vehicle.

| seam error, where two frames overlap | before | after |
|---|---|---|
| pixel-linked pairs (n = 356) | 62.0 mm | **13.7 mm** |
| nav-bridged pairs (n = 38) | 235.5 mm | 119.3 mm |
| all (n = 394) | 67.1 mm | 18.5 mm |
| per-frame vertical σ | 139.9 mm (66.2 robust) | 60.4 mm (21.1 robust) |

**Pixel-linked seams are 8.7× better than nav-bridged ones** (13.7 mm vs
119.3 mm). That is the clearest single vindication of registering the frames at
all.

But levelling is not free, and the trade is worth stating: it made the 1 m-binned
profile agree *less* well with the MBES (median |dz| 0.147 m → 0.185 m, corr
0.971 → 0.924) while making the seams 4.5× better. The likely reason is that some
of the large corrections — the p95 correction is 1.26 m, rescuing frames whose
micro-DEM is badly wrong — are over-fitting bad overlaps rather than repairing bad
frames. For this product's purpose (a spectrum at millimetre-to-metre scales)
internal consistency is what matters, so levelling is on by default; `--no-level`
ships the raw version.

## Honest quality numbers

A ribbon without these is not finished:

| number | value |
|---|---|
| link rate | **89.8 %** (265/295 pairs) |
| `quality != "ok"` rate | **2.0 %** (6 of 296 frames, all `insufficient_coverage`) |
| seam error, pixel-linked | **13.7 mm** median &#124;dz&#124; (rms 23.2, p95 45.4) |
| seam error, nav-bridged | **119.3 mm** median &#124;dz&#124; — 8.7× worse |
| per-frame vertical σ | **60.4 mm** (21.1 mm robust) |
| γ₁ in the 1.2–3 m band | **2.29 ± 1.56** — the error bar is the result |
| ribbon vs MBES, 1 m bins | corr +0.924, median &#124;dz&#124; **0.185 m** |

Batch health from `inspect`: service `altitude_mm` agrees with the metadata
`Altimeter` to a **median 37 mm**; `valid_fraction` median 0.837; γ₂ median 2.97
(IQR 2.66–3.15); every `micro_dem` carried a nested `geo`. The service picks its
own cell size per frame — **2, 3, 4 and 5 mm all appear** — which the compositor
handles because each frame is resampled through its own affine.

**Task 10's verdict: the ribbon does not beat the altimeter baseline.** On this
strip `-(V_Depth + Altimeter)` matches the MBES to 0.115 m (corr 0.988) and the
ribbon manages 0.185 m (corr 0.924). That is a legitimate result and the plan
anticipated it: **the ribbon adds texture, not vertical accuracy**. Note the
baseline here is much better than the survey-wide 0.27 m / 0.662, so this strip
was a hard place to beat it.

## Confirmed against the live service

- **`geotransform heading − nav heading` = +0.00°**, median over all 296 frames.
  The compositing convention — image bottom→top is the heading, image-right is
  starboard — was derived from `INTERFACE.md` and is now verified against real
  responses. This service does **not** have
  [stereo-roughness#1](https://github.com/epifanio/stereo-roughness/issues/1) on
  the client-supplied `geo` path.
- `altitude_mm` against the metadata `Altimeter`: median 37 mm. ✔
- Every `micro_dem` carries a **nested** `geo`; there is no top-level one. ✔
- `insufficient_coverage` rate 2.0 % — non-zero, as expected on turbid frames. ✔

Throughput on the local GPU is ~13 s/frame, not the ~0.5 s the interface quotes,
most likely because the GPU is shared with another container. 296 frames took
73 minutes and 312 MB of cache. Every response is written to disk before any
decoding, so a rebuild needs no service at all.

## Out of scope, deliberately

- **A QGIS dock.** Look at a ribbon first.
- **Bundle adjustment.** The micro-DEMs are already metric and individually
  georeferenced; this composites them. If the seams turn out to need more, that
  is a separate plan.
- **Cross-track mosaics.** One HabCam line has no cross-track overlap. The
  product is a ~1.2 m wide ribbon and no processing makes it a surface.
