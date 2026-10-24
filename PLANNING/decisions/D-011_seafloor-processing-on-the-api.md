---
id: D-011
date: 2026-10-24
status: accepted
decided-by: epifanio, 2026-10-24 ("we want those seafloor related tools, routines and api to live in the seafloor roughness repository (if not already)", then "we have the processing on the API and QGIS holds the UI to trig the api, send payload and receive and render results"); the four questions below carry this session's recommendation and are accepted as written when this PR merges
lanes: U, C, D, P
enforce: /seafloor/ in mixins/
enforce: /seafloor/ in pygui/
---
**Decision.** Seafloor-roughness **processing** lives on the API side; GroundTruther holds the
**UI** for it and nothing else — trigger the route, build the payload, render what comes back. Three
repositories, one job each:

| Repository | Owns |
|---|---|
| `epifanio/stereo-roughness` | the science: RAFT-Stereo, `w2`/`gamma2`, micro-DEM, fusion — and `INTERFACE.md`, the request/response contract both sides pin to |
| `epifanio/seafloor-gateway` | the `/seafloor/*` HTTP surface: proxy, endpoint fallback, error mapping |
| `epifanio/groundtruther` | the Qt/QGIS UI, the stateless client that calls the route, and the rendering of the response |

Four modules in this repository are on the wrong side of that line and **move to the API side**:
`gt/ribbon.py` (1065 lines), `scripts/build_ribbon.py` (1195), `gt/roughness_join.py` (164), and
`gt/mosaic_nav.py` (in PR #43, unmerged). They compute, they do not render. The calibration
thresholds baked into `gt/roughness_interpret.py` move to `INTERFACE.md`; the wording built on top
of them stays here, because the labels are UI.

Everything else under `gt/roughness_*` stays: `roughness_client` (trigger), `roughness_geo` (builds
the `geo` payload), `roughness_dem` (decodes the DEM for the viewport), `roughness_spectrum` (plot
data), and `mixins/roughness_mixin.py` (the dialog). Decoding a response for display is rendering,
not processing.

**Why.** The boundary itself is the owner's, quoted above, and is not re-argued here. What this
record settles is where the code actually sits against it, measured on 2026-10-24 rather than taken
from any repository's prose:

- **The API surface exists twice.** `https://api.fastgis.eu/openapi.json` (HTTP 200, 533 paths)
  carries `/seafloor/health`, `/seafloor/mosaic`, `/seafloor/roughness` and
  `/seafloor/roughness/upload`. So does `epifanio/seafloor-gateway`, deployed at
  `https://seafloor.fastgis.eu`. Both proxy the same GPU service. FastGIS `main` holds
  `app/api/routes/roughness.py` and `app/services/seafloor/gateway.py`, committed 2026-06-20…21 and
  touched 2026-08-17.
- **FastGIS decided to give the surface up and has not.** Its own
  `PLANNING/TODO_seafloor_gateway_split.md` records *"the seafloor/HabCam roughness functionality
  stays OUT of FastGIS"* (owner, 2026-08-22), resolved by the standalone repo rather than by merging
  its PR #206 — and that file is 💤 deferred (owner, 2026-10-09). **That file is also stale:** it
  says PR #206 "never merged, so `api.fastgis.eu/seafloor/*` never shipped", and the live OpenAPI
  above shows those four paths serving today. Read the OpenAPI, not the plan.
- **The plugin calls the FastGIS copy.** `gt/roughness_client.py:62,65,68` point `/seafloor/*` at
  the configured FastGIS endpoint with an `X-API-Key` header; the owner confirmed on 2026-10-24 that
  the key works. So the keyed FastGIS route is the path in use, and the keyless gateway is the one
  that was supposed to replace it.
- **Nothing end-to-end can be exercised today.** `https://seafloor.fastgis.eu/seafloor/health` →
  HTTP 502 `{"detail":"roughness service unreachable"}` — the gateway up, reporting the GPU behind
  it down. `https://roughness.epinux.com/health` → HTTP 403 Cloudflare Access, which `INTERFACE.md`
  calls the expected tokenless response, so it says nothing either way. The home GPU box has been
  offline since at least 2026-08-22 and was still offline when this record was written.
- **The four modules are processing by their own docstrings.** `gt/ribbon.py`: *"Composite per-frame
  stereo micro-DEMs into one along-track seabed ribbon … pure functions over numpy arrays"*.
  `gt/roughness_join.py` joins per-frame roughness onto backscatter samples through a KD-tree.
  `gt/mosaic_nav.py` (PR #43) smooths a USBL fix to anchor the mosaic, 0.72 m → 0.11 m against the
  ribbon. The gateway already exposes `/seafloor/mosaic`, so mosaic work written plugin-side
  duplicates a route that exists.

**Binds.** Lanes U, C, D and P, and any future plan that adds a seafloor feature: the algorithm goes
behind the route, the plugin gets the dialog and the renderer. It rules out growing
`gt/roughness_*`, `gt/ribbon.py` or `mixins/roughness_mixin.py` with new computation, and it rules
out a second client transport — D-002 already puts all GRASS/FastGIS HTTP through `gt/grass_api.py`
and this record puts all seafloor HTTP through `gt/roughness_client.py`.

The two `enforce` lines hold one narrow part of it: the route paths are the API's vocabulary and
must not be spelled out in the UI layer. Verified in both directions at `master` `955f7ba` — `git
ls-files -- 'mixins/*' 'pygui/*' | xargs grep -nE '/seafloor/'` returns nothing today, and a planted
`"/seafloor/roughness"` in `mixins/roughness_mixin.py` is reported as D4. The literals stay where
they belong, `gt/roughness_client.py:62,65,68`. `gt/` and `tests/` are deliberately out of scope:
the client defines the constants and the suite asserts on the URLs it builds.

Nothing else is enforceable by grep. "This function computes rather than renders" is a review
judgement, and a regex that tried to catch it would either miss the next case or fail on
`roughness_dem.py`, which legitimately turns a PNG into a grid for the 3-D view. This record is a
rule a reviewer applies, not a check CI can make.

**The six parked PRs.** They were parked whole on 2026-10-23 (*"those are all unrelated the fastgis
at the moment keep them alone, we probably need to move them out of fastgis and transfer them to my
seafloor roughness repository"*). Re-read at `master` `955f7ba`, they are not one batch:

| PR | What | Disposition |
|---|---|---|
| [#41](https://github.com/epifanio/groundtruther/pull/41) | collapsible sections in the Settings dialog — `configure.py`, `tests/gui/` | **not seafloor work at all**: parked by mistake. Lands in this repository whenever the owner wants it |
| [#42](https://github.com/epifanio/groundtruther/pull/42) | the "featureless seabed" warning blames the wrong thing — 24 lines in `roughness_interpret` | stays: a bug fix in a UI label. Can land now |
| [#39](https://github.com/epifanio/groundtruther/pull/39) | Stretch checkbox for the micro-DEM photo texture | stays (UI), but it carries `docs/slides_*.pptx/html/md` and `docs/build_pptx.py` — presentation files that should not ride in |
| [#40](https://github.com/epifanio/groundtruther/pull/40) | fetch the 3-D surface by default | stays: UI, 183 lines |
| [#43](https://github.com/epifanio/groundtruther/pull/43) | anchor the mosaic on a smoothed USBL fix | **moves**: `gt/mosaic_nav.py` is processing, and `/seafloor/mosaic` already exists. Conflicting with `master` |
| [#37](https://github.com/epifanio/groundtruther/pull/37) | the ribbon results record and the orientation answer — docs and three figures | **follows `ribbon.py`**: the scientific record belongs with the science. Conflicting with `master` |

**Asked, with this session's recommendation; your merge accepts them as written.**

1. **Which repository receives the moved processing** — recommend `stereo-roughness`, with
   `seafloor-gateway` growing only the route that exposes it. The owner said "the seafloor roughness
   repository", and of the two that is the one holding algorithms; the gateway is a proxy and should
   stay one.
2. **How the ribbon is exposed** — recommend a batch tool in `stereo-roughness` first, not a
   synchronous route. It composites many frames into one product, which is not the per-frame
   interactive shape `/roughness` has, and `scripts/build_ribbon.py` is already a command-line
   entry point.
3. **Which gateway the plugin should call** — recommend `seafloor-gateway`
   (`https://seafloor.fastgis.eu`), because that is what the 2026-08-22 decision was for, and then
   removing `/seafloor/*` from FastGIS so one surface exists. This is not configuration alone:
   `gt/roughness_client.py:223` raises `"No API key configured"` on the non-direct path, while the
   gateway is unauthenticated by design, so the client needs a code change before the settings can
   point at it. FastGIS's own plan calls this step "no code"; measured from this side, it is not.
4. **When the four modules move** — recommend after 0.4.1 is listed on plugins.qgis.org. It is
   uploaded and awaiting approval (`<trusted>False</trusted>`); taking ~2,400 lines out of the
   plugin while a release is in the queue risks the release for no gain, and the GPU service being
   offline means nothing moved could be tested anyway.
