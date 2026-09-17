#!/usr/bin/env python3
"""Build a photogrammetric seabed ribbon from one HabCam line — no QGIS.

A ribbon is the along-track composite of a few hundred per-frame stereo
micro-DEMs: millimetre resolution over ~170 m, which is the only product that
spans the gap between one frame's footprint (3 mm .. 1.2 m) and the MBES grid
(>= 2-3 m).  See ``docs/photogrammetric_ribbon.md``.

This is a script, not a plugin tool: nothing here is wired into the QGIS dock.
It runs in phases, each writing to ``--work`` so the next can be re-run without
repeating the one before it (in particular ``fetch`` writes a per-frame JSON
cache -- a rebuild after it needs no network at all).

    scripts/build_ribbon.py inventory          # frames: stereo present, on the DEM, contiguous runs
    scripts/build_ribbon.py scan               # score every run by TEXTURE (ORB link rate)
    scripts/build_ribbon.py chain  --start R --n N     # the offline registration chain
    scripts/build_ribbon.py fetch  --start R --n N     # the only phase that calls the service
    scripts/build_ribbon.py composite --start R --n N  # resample + blend -> GeoTIFFs
    scripts/build_ribbon.py analyse   --start R --n N  # profile vs MBES + along-track spectrum

Configuration (paths, API key) is read from ``config/config.yaml`` via the same
loader the plugin uses, so a machine that can run the plugin can run this.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np

try:
    from groundtruther.gt import ribbon
except ImportError:                                  # run straight from a checkout
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import types
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _pkg = types.ModuleType("groundtruther")
    _pkg.__path__ = [_root]
    sys.modules["groundtruther"] = _pkg
    _cfg = types.ModuleType("groundtruther.configure")
    _cfg.log_exception = lambda *a, **k: None
    sys.modules["groundtruther.configure"] = _cfg
    from groundtruther.gt import ribbon

DEFAULT_WORK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "ribbon_work")


# --------------------------------------------------------------------------
# configuration / data access
# --------------------------------------------------------------------------
def load_config(path=None):
    """The plugin's YAML config as a plain dict (paths + the API key)."""
    import yaml
    path = path or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config", "config.yaml")
    with open(path) as fh:
        return yaml.safe_load(fh) or {}


def stereo_left(stereo_dir, imagename):
    """The left camera half of one archived stereo frame, or ``None``."""
    import cv2
    path = os.path.join(stereo_dir, f"{imagename}_orig.png")
    image = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    return None if image is None else ribbon.left_half(image)


def read_inventory(work):
    import pandas as pd
    return pd.read_parquet(os.path.join(work, "inventory.pq"))


# --------------------------------------------------------------------------
# phase 1a — inventory
# --------------------------------------------------------------------------
def cmd_inventory(args):
    """Frames with stereo, their MBES depth, and the contiguous runs."""
    import pandas as pd
    from osgeo import gdal
    cfg = load_config(args.config)
    stereo_dir = cfg["HabCam"]["imagepath"]
    meta = cfg["HabCam"]["imagemetadata"]
    bathy = cfg["Mbes"]["reference_surface"]

    df = pd.read_parquet(meta).reset_index()
    df["row"] = np.arange(len(df))
    have = {f[: -len("_orig.png")] for f in os.listdir(stereo_dir)
            if f.endswith("_orig.png")}
    df["has_stereo"] = df["Imagename"].isin(have)
    # the calibrated USBL seafloor fix (see gt/roughness_geo)
    df["E"] = df["Xutm"] + df["dx"].fillna(0.0)
    df["N"] = df["Yutm"] + df["dy"].fillna(0.0)

    ds = gdal.Open(bathy)
    gt = ds.GetGeoTransform()
    band = ds.GetRasterBand(1)
    grid = band.ReadAsArray().astype("float64")
    nodata = band.GetNoDataValue()
    if nodata is not None and np.isfinite(nodata):
        grid[grid == nodata] = np.nan
    col = np.floor((df.E.values - gt[0]) / gt[1]).astype("int64")
    row = np.floor((df.N.values - gt[3]) / gt[5]).astype("int64")
    inside = ((col >= 0) & (col < grid.shape[1])
              & (row >= 0) & (row < grid.shape[0]))
    z = np.full(len(df), np.nan)
    z[inside] = grid[row[inside], col[inside]]
    df["mbes_z"] = z
    df["on_dem"] = np.isfinite(z)

    t = df["index"].values.astype("datetime64[ns]").astype("int64") / 1e9
    dt = np.diff(t, prepend=t[0] - 999.0)
    # a run breaks at a missing stereo frame or a gap in acquisition
    brk = (~df.has_stereo.values) | (dt >= 0.5) | (dt <= 0)
    df["run_id"] = np.cumsum(brk)
    df.loc[~df.has_stereo, "run_id"] = -1

    runs = []
    for run_id, g in df[df.has_stereo].groupby("run_id"):
        if len(g) < args.min_frames or g.on_dem.mean() < args.min_on_dem:
            continue
        z_run = g.mbes_z.values[np.isfinite(g.mbes_z.values)]
        runs.append(dict(
            run_id=int(run_id), start_row=int(g.row.iloc[0]),
            end_row=int(g.row.iloc[-1]), n=len(g),
            on_dem_frac=float(g.on_dem.mean()),
            relief=float(z_run.max() - z_run.min()) if len(z_run) else np.nan,
            track_m=float(np.hypot(np.diff(g.E.values),
                                   np.diff(g.N.values)).sum())))
    runs = pd.DataFrame(runs).sort_values("relief", ascending=False)

    os.makedirs(args.work, exist_ok=True)
    df.to_parquet(os.path.join(args.work, "inventory.pq"))
    runs.to_csv(os.path.join(args.work, "runs.csv"), index=False)
    print(f"stereo frames {len(have)}   on DEM {int(df.on_dem.sum())}")
    print(f"runs >= {args.min_frames} frames and >= {args.min_on_dem:.0%} on DEM: {len(runs)}")
    print(runs.head(12).to_string(index=False))


# --------------------------------------------------------------------------
# phase 1b — texture scan
# --------------------------------------------------------------------------
def _score_run(job):
    """Link rate for one run, sampled in blocks spread across it."""
    stereo_dir, names, run_id, start_row, n_blocks, block = job
    n = len(names)
    starts = np.linspace(0, max(n - block - 1, 0), n_blocks).astype(int)
    links = []
    t0 = time.time()
    for s in np.unique(starts):
        frames = [stereo_left(stereo_dir, names[i])
                  for i in range(s, min(s + block + 1, n))]
        for i in range(len(frames) - 1):
            links.append(ribbon.link_pair(frames[i], frames[i + 1], index=s + i))
    summary = ribbon.link_rate(links)
    summary.update(run_id=int(run_id), start_row=int(start_row),
                   seconds=round(time.time() - t0, 1))
    summary["reasons"] = json.dumps(summary["reasons"])
    return summary


def cmd_scan(args):
    """Score every candidate run by texture — the strip-selection criterion."""
    import pandas as pd
    from concurrent.futures import ProcessPoolExecutor
    cfg = load_config(args.config)
    stereo_dir = cfg["HabCam"]["imagepath"]
    df = read_inventory(args.work)
    runs = pd.read_csv(os.path.join(args.work, "runs.csv"))
    if args.limit:
        runs = runs.head(args.limit)

    jobs = []
    for r in runs.itertuples():
        names = df.Imagename.values[r.start_row: r.end_row + 1]
        jobs.append((stereo_dir, list(names), r.run_id, r.start_row,
                     args.blocks, args.block))

    # Runs are scanned in descending relief, and the score is
    # link_rate * relief * on_dem_frac with link_rate <= 1, so once the best
    # score so far exceeds the relief of every remaining run, no unscanned run
    # can win.  The scan stops there and says so -- a proof, not a shortcut.
    partial = os.path.join(args.work, "scan_partial.csv")
    out, best = [], 0.0
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for i, (res, r) in enumerate(zip(pool.map(_score_run, jobs),
                                         runs.itertuples()), 1):
            res["score"] = res["link_rate"] * r.relief * r.on_dem_frac
            out.append(res)
            best = max(best, res["score"])
            pd.DataFrame(out).to_csv(partial, index=False)   # survive a stop
            print(f"[{i}/{len(jobs)}] run {res['run_id']:6d} row {res['start_row']:7d} "
                  f"link {res['link_rate']*100:5.1f}%  med inl {res['median_inliers']:5.1f} "
                  f"score {res['score']:5.2f} ({res['seconds']}s)", flush=True)
            remaining = runs.relief.values[i:]
            if remaining.size and best >= remaining.max():
                print(f"stopping: best score {best:.2f} >= the relief of every "
                      f"remaining run ({remaining.max():.2f} m), so none can win",
                      flush=True)
                break

    scored = pd.DataFrame(out).merge(runs, on=["run_id", "start_row"])
    scored = scored.sort_values("score", ascending=False)
    path = os.path.join(args.work, "scan.csv")
    scored.to_csv(path, index=False)
    print("\nwrote", path)
    cols = ["run_id", "start_row", "n", "link_rate", "median_inliers_linked",
            "relief", "track_m", "score"]
    print(scored[cols].head(15).to_string(index=False))


# --------------------------------------------------------------------------
# phase 1c — the offline registration chain
# --------------------------------------------------------------------------
def strip_frames(df, start, n):
    """The metadata rows of one strip, as a DataFrame with nav columns."""
    strip = df.iloc[start:start + n].copy()
    strip["heading"] = np.nan
    if "bearing" in strip.columns:
        # the platform heading: `bearing` points astern (ship -> towed body),
        # so it is reversed -- see gt/roughness_geo and issue #31
        strip["heading"] = (strip["bearing"].astype(float) + 180.0) % 360.0
    if "Heading" in strip.columns:
        direct = strip["Heading"].astype(float)
        strip.loc[direct.notna(), "heading"] = direct[direct.notna()] % 360.0
    strip["altitude_mm"] = strip["Altimeter"].astype(float) * 1000.0
    return strip


def cmd_chain(args):
    """Register every consecutive pair and build the pose chain — no API calls.

    This is the phase that decides whether a strip is buildable, which is why it
    runs before anything is fetched: if the link rate collapses here, switching
    strips costs nothing.
    """
    import pandas as pd
    cfg = load_config(args.config)
    stereo_dir = cfg["HabCam"]["imagepath"]
    df = read_inventory(args.work)
    strip = strip_frames(df, args.start, args.n)
    names = strip.Imagename.values
    print(f"strip rows {args.start}..{args.start + args.n - 1}  ({len(strip)} frames)")

    links_path = os.path.join(args.work, "links.csv")
    if args.from_links and os.path.exists(links_path):
        # registration is the expensive part (a few hundred reads off a USB
        # drive); re-deriving the track from cached links costs nothing
        print("reusing", links_path)
        links = [ribbon.Link(int(r.index), int(r.n_inliers), r.tx, r.ty,
                             r.rotation_deg, r.scale, bool(r.accepted), r.reason)
                 for r in pd.read_csv(links_path).itertuples()]
    else:
        t0 = time.time()
        links = []
        previous = stereo_left(stereo_dir, names[0])
        for i in range(len(names) - 1):
            current = stereo_left(stereo_dir, names[i + 1])
            links.append(ribbon.link_pair(previous, current, index=i))
            previous = current
            if (i + 1) % 50 == 0:
                print(f"  {i + 1}/{len(names) - 1} pairs ({time.time() - t0:.0f}s)",
                      flush=True)
    summary = ribbon.link_rate(links)
    print(f"\nlink rate      : {summary['link_rate'] * 100:.1f}% "
          f"({summary['n_linked']}/{summary['n_pairs']})")
    print(f"median inliers : {summary['median_inliers']:.0f} (all) / "
          f"{summary['median_inliers_linked']:.0f} (linked)")
    print(f"rejections     : {summary['reasons']}")

    runs_of_links = []
    current_run = 0
    for l in links:
        current_run = current_run + 1 if l.accepted else 0
        runs_of_links.append(current_run)
    print(f"longest unbroken registered run: {max(runs_of_links)} pairs; "
          f"mean {np.mean([r for r in runs_of_links if r]) if any(runs_of_links) else 0:.1f}")

    nav_e = strip.E.values
    nav_n = strip.N.values
    track = ribbon.chain_track(links, nav_e, nav_n, strip.heading.values,
                               strip.altitude_mm.values,
                               anchor_window=args.anchor_window)
    nav_steps = ribbon.step_lengths(nav_e, nav_n)
    chain_steps = ribbon.step_lengths(track["easting"], track["northing"])
    print(f"\nfocal length   : {track['focal_px']:.1f} px "
          f"(nominal {ribbon.FOCAL_PX:.1f}, ratio {track['scale_ratio']:.3f} "
          f"from {track['scale_windows']} windows)")
    print(f"nav   step/frame: median {np.median(nav_steps) * 1000:.0f} mm  "
          f"min {nav_steps.min() * 1000:.0f}  max {nav_steps.max() * 1000:.0f}")
    print(f"chain step/frame: median {np.median(chain_steps) * 1000:.0f} mm  "
          f"min {chain_steps.min() * 1000:.0f}  max {chain_steps.max() * 1000:.0f}")
    print(f"track length    : nav {nav_steps.sum():.1f} m  "
          f"chain {chain_steps.sum():.1f} m")
    print(f"max |chain - nav|: {np.hypot(track['easting'] - nav_e, track['northing'] - nav_n).max():.2f} m")

    pd.DataFrame([{"index": l.index, "n_inliers": l.n_inliers, "tx": l.tx,
                   "ty": l.ty, "rotation_deg": l.rotation_deg, "scale": l.scale,
                   "accepted": l.accepted, "reason": l.reason} for l in links]
                 ).to_csv(os.path.join(args.work, "links.csv"), index=False)
    poses = pd.DataFrame({
        "row": np.arange(args.start, args.start + len(strip)),
        "frame_key": names, "easting": track["easting"],
        "northing": track["northing"], "heading": track["heading"],
        "source": track["source"], "nav_easting": nav_e, "nav_northing": nav_n,
        "nav_heading": strip.heading.values,
        "altitude_mm": strip.altitude_mm.values, "mbes_z": strip.mbes_z.values,
        # the vehicle's own depth, to lift camera-relative heights onto the
        # survey datum at composite time
        "v_depth_m": strip["V_Depth"].astype(float).values,
        "water_depth_m": strip["Water_Depth"].astype(float).values})
    poses.to_csv(os.path.join(args.work, "poses.csv"), index=False)
    with open(os.path.join(args.work, "chain_summary.json"), "w") as fh:
        json.dump({**summary, "start": args.start, "n": args.n,
                   "focal_px": track["focal_px"],
                   "scale_ratio": track["scale_ratio"],
                   "scale_windows": int(track["scale_windows"]),
                   "nav_track_m": float(nav_steps.sum()),
                   "chain_track_m": float(chain_steps.sum()),
                   "longest_registered_run": int(max(runs_of_links))}, fh, indent=2)
    print("\nwrote links.csv, poses.csv, chain_summary.json")


# --------------------------------------------------------------------------
# phase 2 — fetch (the only phase that calls the service)
# --------------------------------------------------------------------------
def cmd_fetch(args):
    """Fetch and cache one micro-DEM per frame. Cache first, decode later."""
    import pandas as pd
    from groundtruther.gt import roughness_client as rc
    from groundtruther.gt import roughness_geo

    cfg = load_config(args.config)
    endpoint = cfg["Processing"]["grass_api_endpoint"]
    api_key = cfg["Processing"]["grass_api_key"]
    df = read_inventory(args.work)
    strip = strip_frames(df, args.start, args.n)
    cache = os.path.join(args.work, "cache")
    os.makedirs(cache, exist_ok=True)

    rows = []
    t0 = time.time()
    for position, (_, record) in enumerate(strip.iterrows()):
        frame_key = record["Imagename"]
        path = os.path.join(cache, f"{frame_key}.json")
        if os.path.exists(path) and not args.refresh:
            rows.append({"frame_key": frame_key, "cached": True})
            continue
        # the geo sent is built from the RAW nav, so the cache does not depend
        # on the chain; the chain correction is applied at composite time
        geo = roughness_geo.geo_from_record(record)
        try:
            result = rc.roughness_for_frame(
                frame_key, endpoint=endpoint, api_key=api_key, geo=geo,
                dem_format="mm", include_orthophoto=True, include_spectrum=True)
        except rc.RoughnessError as exc:
            print(f"  [{position}] {frame_key}: FAILED {exc}", flush=True)
            rows.append({"frame_key": frame_key, "error": str(exc)})
            continue
        # persist the raw JSON BEFORE decoding anything, so a decode bug never
        # costs a refetch
        with open(path, "w") as fh:
            json.dump(result, fh)
        rows.append({"frame_key": frame_key, "cached": False})
        if (position + 1) % 25 == 0:
            print(f"  {position + 1}/{len(strip)} ({time.time() - t0:.0f}s)",
                  flush=True)
    print(f"fetched/cached {len(rows)} frames in {time.time() - t0:.0f}s")
    pd.DataFrame(rows).to_csv(os.path.join(args.work, "fetch_log.csv"), index=False)


def load_cached(cache_dir, frame_key):
    path = os.path.join(cache_dir, f"{frame_key}.json")
    if not os.path.exists(path):
        return None
    with open(path) as fh:
        return json.load(fh)


def cmd_inspect(args):
    """Sanity-check the fetched batch — quality, altitude, coverage, geo."""
    import pandas as pd
    from groundtruther.gt import roughness_geo
    df = read_inventory(args.work)
    strip = strip_frames(df, args.start, args.n)
    cache = os.path.join(args.work, "cache")

    rows = []
    for _, record in strip.iterrows():
        result = load_cached(cache, record["Imagename"])
        if result is None:
            rows.append({"frame_key": record["Imagename"], "quality": "MISSING"})
            continue
        micro = result.get("micro_dem") or {}
        ortho = result.get("orthophoto") or {}
        geo = roughness_geo.extract_geo(result)
        spectrum = result.get("spectrum") or {}
        rows.append({
            "frame_key": record["Imagename"], "quality": result.get("quality"),
            "gamma2": result.get("gamma2"), "w2": result.get("w2"),
            "fit_r2": result.get("fit_r2"),
            "fit_lo": (result.get("fit_band_rad_per_m") or [None, None])[0],
            "fit_hi": (result.get("fit_band_rad_per_m") or [None, None])[1],
            "altitude_mm": result.get("altitude_mm"),
            "metadata_altitude_mm": float(record["Altimeter"]) * 1000.0,
            "valid_fraction": result.get("valid_fraction"),
            "rms_height_mm": result.get("rms_height_mm"),
            "dx_mm": (micro.get("dx_mm") if micro else None),
            "dem_rows": (micro.get("shape") or [None, None])[0],
            "dem_cols": (micro.get("shape") or [None, None])[1],
            "has_micro_geo": bool(isinstance(micro.get("geo"), dict)),
            "has_ortho": bool(ortho.get("png_b64")),
            "has_spectrum": bool(spectrum.get("K_rad_per_m")),
            "geotransform_heading": (ribbon.heading_from_geotransform(geo["geotransform"])
                                     if geo else None),
            "nav_heading": float(record["heading"]),
        })
    table = pd.DataFrame(rows)
    table.to_csv(os.path.join(args.work, "batch_quality.csv"), index=False)

    n = len(table)
    print(f"frames            : {n}")
    print("quality           :")
    for value, count in table.quality.value_counts(dropna=False).items():
        print(f"    {str(value):22s} {count:4d}  ({count / n * 100:5.1f}%)")
    ok = table[table.quality == "ok"]
    if len(ok):
        dz = (ok.altitude_mm - ok.metadata_altitude_mm) / 1000.0
        print(f"altitude vs Altimeter : median {dz.median():+.3f} m  "
              f"median|.| {dz.abs().median():.3f} m  p95|.| {dz.abs().quantile(.95):.3f} m")
        print(f"valid_fraction        : median {ok.valid_fraction.median():.3f}  "
              f"min {ok.valid_fraction.min():.3f}")
        print(f"gamma2                : median {ok.gamma2.median():.2f}  "
              f"IQR {ok.gamma2.quantile(.25):.2f}-{ok.gamma2.quantile(.75):.2f}")
        print(f"dem cell size         : {sorted(set(ok.dx_mm.dropna()))} mm")
    missing_geo = int((~table.has_micro_geo).sum())
    print(f"micro_dem without a nested geo block: {missing_geo}")
    both = table.dropna(subset=["geotransform_heading", "nav_heading"])
    if len(both):
        delta = (both.geotransform_heading - both.nav_heading + 180) % 360 - 180
        print(f"geotransform heading - nav heading: median {delta.median():+.2f} deg "
              f"(0 confirms the mount convention and the #31 fix)")
    print("\nwrote batch_quality.csv")


# --------------------------------------------------------------------------
# phase 3 — composite
# --------------------------------------------------------------------------
def decode_frame(result):
    """``(elevation_m, rgb, geotransform)`` for one cached response, or None.

    Elevation is the micro-DEM's height in **metres, camera-relative** (the
    service returns ``-range``, so values sit near ``-altitude``); the caller
    adds the vehicle depth to put it on the survey datum.
    """
    import base64
    import io
    from PIL import Image
    from groundtruther.gt import roughness_dem, roughness_geo

    if not isinstance(result, dict) or result.get("quality") != "ok":
        return None
    micro = result.get("micro_dem")
    geo = roughness_geo.extract_geo(result)
    if not isinstance(micro, dict) or geo is None:
        return None
    heights_mm, _, _, _ = roughness_dem.decode_float_grid(micro)
    rgb = None
    ortho = result.get("orthophoto")
    if isinstance(ortho, dict) and ortho.get("png_b64"):
        image = Image.open(io.BytesIO(base64.b64decode(ortho["png_b64"]))).convert("RGB")
        rgb = np.asarray(image, dtype=np.float32)
        if rgb.shape[:2] != heights_mm.shape:
            return None          # co-registration is the whole point; if the
                                 # grids disagree the frame is unusable
    return np.asarray(heights_mm, dtype=np.float64) / 1000.0, rgb, geo["geotransform"]


def placed_frames(poses, cache):
    """Yield ``(position, geotransform, shape)`` for every usable frame.

    The cached geotransform was built from the raw nav, so the chain's
    correction is applied here rather than being baked into the request.
    """
    for position, pose in enumerate(poses.itertuples()):
        result = load_cached(cache, pose.frame_key)
        decoded = decode_frame(result)
        if decoded is None:
            continue
        elevation, rgb, geotransform = decoded
        adjusted = ribbon.adjust_geotransform(
            geotransform, elevation.shape,
            d_east=pose.easting - pose.nav_easting,
            d_north=pose.northing - pose.nav_northing,
            d_heading_deg=(pose.heading - pose.nav_heading + 180) % 360 - 180)
        yield position, adjusted, elevation, rgb


def cmd_composite(args):
    """Resample every frame into one grid, blend, and write the GeoTIFFs."""
    import pandas as pd
    from groundtruther.gt import roughness_geo
    poses = pd.read_csv(os.path.join(args.work, "poses.csv"))
    cache = os.path.join(args.work, "cache")

    # pass 1: where does everything land
    geotransforms, shapes, used = [], [], []
    for position, geotransform, elevation, _ in placed_frames(poses, cache):
        geotransforms.append(geotransform)
        shapes.append(elevation.shape)
        used.append(position)
    if not geotransforms:
        raise SystemExit("no usable frames in the cache — run `fetch` first")
    azimuth = (None if args.north_up
               else ribbon.track_azimuth(poses.easting.values, poses.northing.values))
    target = ribbon.target_grid(geotransforms, shapes, args.pixel,
                                margin_m=0.05, azimuth_deg=azimuth)
    cells = target["width"] * target["height"]
    print(f"usable frames : {len(used)}/{len(poses)}")
    print(f"target grid   : {target['width']} x {target['height']} "
          f"({cells / 1e6:.1f} Mcell) at {args.pixel * 1000:.0f} mm, "
          f"azimuth {'north-up' if azimuth is None else f'{azimuth:.1f} deg'}")
    if cells > args.max_cells:
        raise SystemExit(f"grid would be {cells / 1e9:.1f} Gcell; raise --max-cells "
                         f"or drop --north-up")

    # pass 2: resample, blend, and measure the seams as we go
    canvas = ribbon.RibbonCanvas(target, n_bands=4)
    previous = None
    seams = []
    t0 = time.time()
    for count, (position, geotransform, elevation, rgb) in enumerate(
            placed_frames(poses, cache), 1):
        pose = poses.iloc[position]
        # camera-relative height -> survey datum
        absolute = elevation - float(pose.v_depth_m)
        bands = [absolute]
        bands += ([rgb[..., i] for i in range(3)] if rgb is not None
                  else [np.full(absolute.shape, np.nan)] * 3)
        window, values, valid = ribbon.resample_frame(bands, geotransform, target)
        if not np.any(valid):
            continue
        canvas.add(window, values, valid)
        if previous is not None:
            shared = ribbon.intersect_windows(previous[0], window)
            if shared is not None:
                _, cut_prev, cut_now = shared
                stats = ribbon.overlap_difference(
                    previous[1][cut_prev], previous[2][cut_prev],
                    values[0][cut_now], valid[cut_now])
                if stats:
                    stats["source"] = pose.source
                    stats["position"] = int(position)
                    seams.append(stats)
        previous = (window, values[0], valid)
        if count % 25 == 0:
            print(f"  {count}/{len(used)} frames ({time.time() - t0:.0f}s)", flush=True)

    bands, count_band = canvas.result()
    covered = int((count_band > 0).sum())
    print(f"\ncoverage      : {covered / cells * 100:.1f}% of the grid, "
          f"{covered * args.pixel ** 2:.2f} m2")
    seen = count_band[count_band > 0]
    print(f"observations  : median {np.median(seen):.0f} per covered cell, "
          f"max {seen.max()}")

    epsg = args.epsg
    dem_path = os.path.join(args.work, "ribbon_dem.tif")
    ortho_path = os.path.join(args.work, "ribbon_ortho.tif")
    count_path = os.path.join(args.work, "ribbon_count.tif")
    roughness_geo.write_geotiff(bands[0].astype(np.float32), target["geotransform"],
                                epsg, dem_path, nodata=float("nan"))
    rgb_stack = np.stack([np.nan_to_num(bands[i + 1]).clip(0, 255).astype(np.uint8)
                          for i in range(3)], axis=-1)
    roughness_geo.write_geotiff(rgb_stack, target["geotransform"], epsg, ortho_path)
    roughness_geo.write_geotiff(count_band.astype(np.int16), target["geotransform"],
                                epsg, count_path, nodata=0)
    print("wrote", dem_path, ortho_path, count_path, sep="\n  ")

    if seams:
        frame = pd.DataFrame(seams)
        frame.to_csv(os.path.join(args.work, "seams.csv"), index=False)
        print("\nseam error (overlap elevation difference between consecutive frames)")
        print(f"  pairs measured      : {len(frame)}")
        for source, group in frame.groupby("source"):
            print(f"  {source:6s} n={len(group):3d}  median|dz| {group.median_abs.median() * 1000:7.1f} mm"
                  f"   rms {group.rms.median() * 1000:7.1f} mm"
                  f"   p95 {group.p95_abs.median() * 1000:7.1f} mm")
        print(f"  ALL    n={len(frame):3d}  median|dz| {frame.median_abs.median() * 1000:7.1f} mm"
              f"   rms {frame.rms.median() * 1000:7.1f} mm"
              f"   p95 {frame.p95_abs.median() * 1000:7.1f} mm")
    with open(os.path.join(args.work, "composite_summary.json"), "w") as fh:
        json.dump({"frames_used": len(used), "frames_total": int(len(poses)),
                   "grid": {k: target[k] for k in ("width", "height", "pixel_m",
                                                   "azimuth_deg")},
                   "coverage_fraction": covered / cells,
                   "seam_median_abs_mm": (float(pd.DataFrame(seams).median_abs.median() * 1000)
                                          if seams else None)}, fh, indent=2)


# --------------------------------------------------------------------------
# phase 4 — the two analyses that justify the product
# --------------------------------------------------------------------------
def sample_raster(path, easting, northing):
    """Bilinear sample of a north-up raster at world coordinates (NaN outside)."""
    from osgeo import gdal
    ds = gdal.Open(path)
    gt = ds.GetGeoTransform()
    band = ds.GetRasterBand(1)
    grid = band.ReadAsArray().astype("float64")
    nodata = band.GetNoDataValue()
    if nodata is not None and np.isfinite(nodata):
        grid[grid == nodata] = np.nan
    col = (np.asarray(easting, float) - gt[0]) / gt[1] - 0.5
    row = (np.asarray(northing, float) - gt[3]) / gt[5] - 0.5
    out, _ = ribbon._bilinear_nan(grid, col, row)
    return out


def ribbon_profile(path):
    """The along-track elevation profile of a ribbon GeoTIFF.

    The grid is track-aligned, so ``-row`` runs along the azimuth: each row is
    one cross-track slice and its median is the profile sample.  A median, not a
    mean, because the ribbon's edges carry the noisiest stereo.
    """
    from osgeo import gdal
    ds = gdal.Open(path)
    gt = ds.GetGeoTransform()
    band = ds.GetRasterBand(1)
    grid = band.ReadAsArray().astype("float64")
    nodata = band.GetNoDataValue()
    if nodata is not None and np.isfinite(nodata):
        grid[grid == nodata] = np.nan
    pixel = float(np.hypot(gt[1], gt[4]))
    with np.errstate(all="ignore"):
        counts = np.sum(np.isfinite(grid), axis=1)
        profile = np.full(grid.shape[0], np.nan)
        rows = np.where(counts > 0)[0]
        for r in rows:
            profile[r] = np.nanmedian(grid[r])
    # -row is the direction of travel, so reverse to get increasing distance
    profile = profile[::-1]
    counts = counts[::-1]
    distance = np.arange(profile.size) * pixel
    return distance, profile, counts, pixel


def cmd_analyse(args):
    """Profile vs MBES, and the along-track spectrum across the scale gap."""
    import pandas as pd
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    cfg = load_config(args.config)
    bathy = cfg["Mbes"]["reference_surface"]
    poses = pd.read_csv(os.path.join(args.work, "poses.csv"))
    out = {}

    # ---- the baseline the ribbon has to beat -------------------------------
    track_s = ribbon.along_track_distance(poses.easting.values, poses.northing.values)
    mbes_at_frames = sample_raster(bathy, poses.easting.values, poses.northing.values)
    vehicle_z = -(poses.v_depth_m.values + poses.altitude_mm.values / 1000.0)
    baseline = ribbon.compare_profiles(vehicle_z, mbes_at_frames)
    out["altimeter_baseline"] = baseline
    print("baseline  -(V_Depth + Altimeter) vs MBES, this strip:")
    print(f"    n {baseline['n']}  corr {baseline['corr']:+.3f}  "
          f"median|dz| {baseline['median_abs_dz']:.3f} m  rms {baseline['rms_dz']:.3f} m")
    print("    (survey-wide figure from the data-model memory: 0.27 m, corr 0.662)")

    # ---- the MBES's own along-track spectrum -------------------------------
    bin_m = 1.0
    centres, mbes_binned, counts = ribbon.bin_along_track(track_s, mbes_at_frames, bin_m)
    usable = np.isfinite(mbes_binned)
    mbes_spectrum = None
    if usable.sum() >= 16:
        k_mbes, w_mbes = ribbon.along_track_spectrum(mbes_binned[usable], bin_m)
        mbes_spectrum = (k_mbes, w_mbes)
        k_mbes_b, w_mbes_b, _ = ribbon.band_average(k_mbes, w_mbes)
        fit = ribbon.power_law_fit(k_mbes_b, w_mbes_b,
                                   (2 * np.pi / 40.0, np.pi / bin_m))
        out["mbes_spectrum_fit"] = fit
        print(f"\nMBES along-track spectrum: gamma1 {fit['gamma']:.2f} "
              f"+-{fit['gamma_err']:.2f} (=> gamma2 {fit['gamma'] + 1:.2f}) over "
              f"{2 * np.pi / fit['band'][1]:.1f}-{2 * np.pi / fit['band'][0]:.0f} m, "
              f"r2 {fit['r2']:.2f}, n {fit['n']}")

    # ---- the per-frame roughness the ribbon is being compared against ------
    quality_path = os.path.join(args.work, "batch_quality.csv")
    per_frame = None
    if os.path.exists(quality_path):
        table = pd.read_csv(quality_path)
        ok = table[(table.quality == "ok") & table.gamma2.notna()]
        if len(ok):
            per_frame = {"gamma2": float(ok.gamma2.median()),
                         "w2": float(ok.w2.median()),
                         "fit_lo": float(ok.fit_lo.median()),
                         "fit_hi": float(ok.fit_hi.median()),
                         "n": int(len(ok))}
            out["per_frame"] = per_frame
            print(f"\nper-frame roughness: median gamma2 {per_frame['gamma2']:.2f}, "
                  f"w2 {per_frame['w2']:.3e} m4, fitted over "
                  f"{per_frame['fit_lo']:.0f}-{per_frame['fit_hi']:.0f} rad/m "
                  f"(n={per_frame['n']})")

    # ---- the ribbon itself -------------------------------------------------
    dem_path = os.path.join(args.work, "ribbon_dem.tif")
    ribbon_spectrum = None
    if not os.path.exists(dem_path):
        print(f"\nNO RIBBON at {dem_path} — the two ribbon-dependent results "
              f"(profile comparison and the scale-gap spectrum) cannot be "
              f"computed. Everything above is service-independent.")
    else:
        distance, profile, counts, pixel = ribbon_profile(dem_path)
        gap = float(np.mean(~np.isfinite(profile)))
        print(f"\nribbon profile: {profile.size} samples at {pixel * 1000:.0f} mm "
              f"over {distance[-1]:.1f} m, {gap * 100:.1f}% no-data")
        out["ribbon_profile"] = {"n": int(profile.size), "pixel_m": pixel,
                                 "length_m": float(distance[-1]),
                                 "nodata_fraction": gap}

        # task 10 — binned to the MBES grid
        r_centres, r_binned, r_counts = ribbon.bin_along_track(distance, profile, bin_m)
        common = min(r_binned.size, mbes_binned.size)
        stats = ribbon.compare_profiles(r_binned[:common], mbes_binned[:common])
        out["ribbon_vs_mbes"] = stats
        print(f"ribbon (1 m bins) vs MBES: n {stats['n']}  corr {stats['corr']:+.3f}  "
              f"median|dz| {stats['median_abs_dz']:.3f} m  rms {stats['rms_dz']:.3f} m")
        verdict = ("BEATS" if stats["median_abs_dz"] < baseline["median_abs_dz"]
                   else "does NOT beat")
        print(f"  -> the ribbon {verdict} the "
              f"{baseline['median_abs_dz']:.3f} m altimeter baseline on this strip")

        # task 11 — the scale-gap spectrum
        if gap < 0.5:
            k_r, w_r = ribbon.along_track_spectrum(profile, pixel)
            # fit the band-averaged spectrum: the raw periodogram holds only
            # ~30 ordinates across the 1.2-3 m band, each with ~100 % error
            k_rb, w_rb, _ = ribbon.band_average(k_r, w_r)
            ribbon_spectrum = (k_r, w_r, k_rb, w_rb)
            gap_band = ribbon.wavelength_band_to_k(1.2, 3.0)
            gap_fit = ribbon.power_law_fit(k_rb, w_rb, gap_band)
            out["ribbon_gap_fit"] = gap_fit
            print(f"\nribbon spectrum in the 1.2-3 m gap: gamma1 {gap_fit['gamma']:.2f} "
                  f"+-{gap_fit['gamma_err']:.2f} (=> gamma2 "
                  f"{gap_fit['gamma'] + 1:.2f}), r2 {gap_fit['r2']:.2f}, "
                  f"n {gap_fit['n']} bands")
            if per_frame:
                predicted = ribbon.w1_from_gamma2(k_rb, per_frame["gamma2"],
                                                  per_frame["w2"])
                inside = (k_rb >= gap_band[0]) & (k_rb <= gap_band[1])
                ratio = np.nanmedian(w_rb[inside] / predicted[inside])
                out["extrapolation"] = {
                    "gamma1_ribbon": gap_fit["gamma"],
                    "gamma1_ribbon_err": gap_fit["gamma_err"],
                    "gamma1_predicted": per_frame["gamma2"] - 1.0,
                    "amplitude_ratio_measured_over_predicted": float(ratio)}
                print(f"  per-frame gamma2 {per_frame['gamma2']:.2f} predicts "
                      f"gamma1 {per_frame['gamma2'] - 1:.2f} in that band")
                print(f"  measured/predicted power in the gap band: {ratio:.2f}x "
                      f"({10 * np.log10(ratio):+.1f} dB)")

    # ---- one figure --------------------------------------------------------
    fig, axes = plt.subplots(2, 1, figsize=(11, 9))
    ax = axes[0]
    ax.plot(centres, mbes_binned, label="MBES (1 m)", lw=2)
    ax.plot(track_s, vehicle_z - baseline["bias"], label="-(V_Depth + Altimeter)",
            lw=1, alpha=0.7)
    if ribbon_spectrum is not None or os.path.exists(dem_path):
        ax.plot(r_centres, r_binned - stats["bias"], label="ribbon (1 m bins)", lw=1.5)
    ax.set_xlabel("along-track distance (m)")
    ax.set_ylabel("seabed elevation (m)")
    ax.legend(); ax.grid(alpha=0.3)
    ax.set_title("Along-track profile: ribbon vs MBES vs the altimeter baseline")

    ax = axes[1]
    if ribbon_spectrum is not None:
        ax.loglog(ribbon_spectrum[0], ribbon_spectrum[1], lw=0.5, alpha=0.3,
                  color="C0", label="ribbon, raw periodogram")
        ax.loglog(ribbon_spectrum[2], ribbon_spectrum[3], lw=1.8, color="C0",
                  label="ribbon, band-averaged")
    if mbes_spectrum is not None:
        ax.loglog(mbes_spectrum[0], mbes_spectrum[1], lw=1.5, label="MBES (1 m)")
    if per_frame:
        k_line = np.logspace(-1.5, 3.2, 200)
        ax.loglog(k_line, ribbon.w1_from_gamma2(k_line, per_frame["gamma2"],
                                                per_frame["w2"]),
                  "k--", lw=1.5,
                  label=f"per-frame fit extrapolated (gamma2={per_frame['gamma2']:.2f})")
        ax.axvspan(per_frame["fit_lo"], per_frame["fit_hi"], color="0.85",
                   label="band the per-frame fit was made in")
    gap_lo, gap_hi = ribbon.wavelength_band_to_k(1.2, 3.0)
    ax.axvspan(gap_lo, gap_hi, color="orange", alpha=0.25,
               label="the 1.2-3 m scale gap")
    ax.set_xlabel("wavenumber k (rad/m)")
    ax.set_ylabel("W1(k)  (m^3)")
    ax.legend(fontsize=8); ax.grid(alpha=0.3, which="both")
    ax.set_title("Along-track roughness spectrum across the scale gap")
    fig.tight_layout()
    figure_path = os.path.join(args.work, "ribbon_analysis.png")
    fig.savefig(figure_path, dpi=130)
    print("\nwrote", figure_path)

    with open(os.path.join(args.work, "analysis.json"), "w") as fh:
        json.dump(out, fh, indent=2, default=float)
    print("wrote", os.path.join(args.work, "analysis.json"))


# --------------------------------------------------------------------------
# a synthetic stand-in for the service, so phases 3-4 can be verified offline
# --------------------------------------------------------------------------
def synthetic_surface(gamma2, w2, azimuth_deg, origin, *, k_ref=100.0,
                      k_min=0.02, k_max=400.0, n_modes=3000,
                      cross_amplitude=0.05, seed=0):
    """A random seabed whose **along-track** spectrum is exactly known.

    Returns ``z(easting, northing)`` in metres.

    The target is the 1-D spectrum a per-frame ``(gamma2, w2)`` fit implies,
    ``W1 = w1_from_gamma2(k, gamma2, w2)``, and the modes that carry it are laid
    along the track azimuth with amplitudes ``sqrt(2 W1 dk)``.  Drawing random
    *2-D* wavevectors instead -- the obvious thing -- does not work as a test
    target: each 2-D mode projects onto the track at ``|k| cos(theta)``, so a
    tractable number of modes gives a sparse, spiky along-track spectrum whose
    fitted exponent scatters by more than a unit.  (The 2-D-to-1-D identity
    itself is verified analytically in the unit tests, against numerical
    integration; it does not need re-testing here.)

    ``k_max`` must stay below the Nyquist wavenumber of whatever the ribbon is
    composited at (``pi/pixel``); modes above it alias down into the band under
    test and steepen the fitted exponent -- at 6 mm cells, a k_max of 900 rad/m
    turned a planted 2.00 into 2.72.

    A cross-track component is added on top for texture -- it carries no
    along-track power, so it exercises the rotated resampling without
    disturbing the quantity being checked.

    ``origin`` is the ``(easting, northing)`` the surface is built around; UTM
    coordinates are millions of metres, and the lookups below only span a few
    hundred either side of it.
    """
    rng = np.random.default_rng(seed)
    from groundtruther.gt.ribbon import w1_from_gamma2

    edges = np.logspace(np.log10(k_min), np.log10(k_max), n_modes + 1)
    k = np.sqrt(edges[:-1] * edges[1:])
    dk = np.diff(edges)
    # variance = sum(a^2/2) must equal the TWO-sided integral 2*sum(W1*dk),
    # so a = 2*sqrt(W1*dk).  Getting this wrong by the obvious sqrt(2) puts the
    # synthetic surface a clean factor of two below its own target spectrum.
    amplitude = 2.0 * np.sqrt(w1_from_gamma2(k, gamma2, w2, k_ref) * dk)
    phase = rng.uniform(0, 2 * np.pi, k.size)

    t = np.radians(float(azimuth_deg))
    along = np.array([np.sin(t), np.cos(t)])          # unit vector along track
    cross = np.array([np.cos(t), -np.sin(t)])

    n_cross = 40
    k_cross = np.logspace(np.log10(0.5), np.log10(30.0), n_cross)
    amp_cross = cross_amplitude * k_cross ** -1.0
    phase_cross = rng.uniform(0, 2 * np.pi, n_cross)

    # Both components are functions of a single projected coordinate, so build
    # each once on a fine 1-D lookup and interpolate.  Summing 3000 modes at
    # every cell of every frame directly would be ~10^10 cosines.
    def tabulate(span, step, wavenumbers, amplitudes, phases):
        grid = np.arange(-span, span + step, step)
        values = np.zeros(grid.size)
        for start in range(0, wavenumbers.size, 64):
            block = slice(start, start + 64)
            values += (amplitudes[block]
                       * np.cos(np.outer(grid, wavenumbers[block])
                                + phases[block])).sum(axis=1)
        return grid, values

    step = min(np.pi / (8.0 * k_max), 0.001)
    span = 300.0
    along_grid, along_values = tabulate(span, step, k, amplitude, phase)
    cross_grid, cross_values = tabulate(span, step * 20, k_cross, amp_cross,
                                        phase_cross)

    origin = np.asarray(origin, dtype=float)

    def surface(easting, northing):
        e = np.asarray(easting, dtype=float) - origin[0]
        n = np.asarray(northing, dtype=float) - origin[1]
        return (np.interp(e * along[0] + n * along[1], along_grid, along_values)
                + np.interp(e * cross[0] + n * cross[1], cross_grid, cross_values))
    return surface


def cmd_simulate(args):
    """Fabricate a cache in the service's response shape, from a known surface.

    Phase 2 is the only phase that needs the network; this replaces it with a
    seabed whose roughness is known exactly, so the composite and the analysis
    can be verified end to end -- and so a reviewer can re-run the whole
    pipeline without credentials.  It is **not** a substitute for the real
    fetch: it assumes the geotransform convention rather than confirming it
    (``inspect`` is what confirms it, against a real response).
    """
    import base64
    import io
    import shutil
    from PIL import Image
    import pandas as pd

    source_poses = os.path.join(args.source_work, "poses.csv")
    os.makedirs(args.work, exist_ok=True)
    if os.path.abspath(args.work) != os.path.abspath(args.source_work):
        shutil.copy(source_poses, os.path.join(args.work, "poses.csv"))
    poses = pd.read_csv(os.path.join(args.work, "poses.csv"))
    if args.frames:
        poses = poses.head(args.frames)
        poses.to_csv(os.path.join(args.work, "poses.csv"), index=False)
    cache = os.path.join(args.work, "cache")
    os.makedirs(cache, exist_ok=True)

    azimuth = ribbon.track_azimuth(poses.easting.values, poses.northing.values)
    surface = synthetic_surface(args.gamma2, args.w2, azimuth,
                                (poses.nav_easting.iloc[0], poses.nav_northing.iloc[0]),
                                seed=args.seed)
    dx_m = args.dx_mm / 1000.0
    rows = cols = args.dem_side
    quality_rows = []
    for pose in poses.itertuples():
        # the grid the service would return: rotated to the heading it was sent
        t = np.radians(pose.nav_heading)
        matrix = np.array([[dx_m * np.cos(t), -dx_m * np.sin(t)],
                           [-dx_m * np.sin(t), -dx_m * np.cos(t)]])
        centre = np.array([pose.nav_easting, pose.nav_northing])
        origin = centre - matrix @ np.array([cols / 2.0, rows / 2.0])
        geotransform = [origin[0], matrix[0, 0], matrix[0, 1],
                        origin[1], matrix[1, 0], matrix[1, 1]]

        col_grid, row_grid = np.meshgrid(np.arange(cols) + 0.5, np.arange(rows) + 0.5)
        east = origin[0] + matrix[0, 0] * col_grid + matrix[0, 1] * row_grid
        north = origin[1] + matrix[1, 0] * col_grid + matrix[1, 1] * row_grid
        # the truth is sampled at the frame's TRUE pose; the cached
        # geotransform records the NAV pose, so the composite has to apply the
        # chain correction to put it back — exactly as with real frames
        shift = np.array([pose.easting - pose.nav_easting,
                          pose.northing - pose.nav_northing])
        truth = surface(east + shift[0], north + shift[1])
        heights_mm = (truth + pose.v_depth_m) * 1000.0
        heights_mm[:2, :] = np.nan            # a little no-data at the edges
        heights_mm[-2:, :] = np.nan

        payload = np.asarray(heights_mm, dtype="<f4").tobytes()
        shade = np.nan_to_num((truth - np.nanmin(truth)))
        shade = (255 * shade / max(shade.max(), 1e-9)).astype(np.uint8)
        buffer = io.BytesIO()
        Image.fromarray(np.dstack([shade] * 3)).save(buffer, format="PNG")

        geo = {"geotransform": geotransform, "epsg": 32619}
        result = {
            "quality": "ok", "gamma2": args.gamma2, "w2": args.w2,
            "k_ref_rad_per_m": 100.0, "fit_band_rad_per_m": [251.1, 1412.2],
            "fit_r2": 0.99, "altitude_mm": float(pose.altitude_mm),
            "valid_fraction": 0.9, "dx_mm": args.dx_mm,
            "dem_shape": [rows, cols], "frame_key": pose.frame_key,
            "micro_dem": {"format": "float32", "byte_order": "little",
                          "shape": [rows, cols],
                          "data_b64": base64.b64encode(payload).decode(),
                          "dx_mm": args.dx_mm, "x0_mm": 0.0, "y0_mm": 0.0,
                          "units": "mm", "z_is_height": True, "nan": "NaN",
                          "geo": geo},
            "orthophoto": {"png_b64": base64.b64encode(buffer.getvalue()).decode(),
                           "shape": [rows, cols], "dx_mm": args.dx_mm,
                           "x0_mm": 0.0, "y0_mm": 0.0,
                           "frame": "world_local_mm", "geo": geo},
            "simulated": True,
        }
        with open(os.path.join(cache, f"{pose.frame_key}.json"), "w") as fh:
            json.dump(result, fh)
        quality_rows.append({"frame_key": pose.frame_key, "quality": "ok",
                             "gamma2": args.gamma2, "w2": args.w2,
                             "fit_lo": 251.1, "fit_hi": 1412.2})
    pd.DataFrame(quality_rows).to_csv(os.path.join(args.work, "batch_quality.csv"),
                                      index=False)
    print(f"simulated {len(poses)} frames at {args.dx_mm} mm "
          f"({rows}x{cols}) with gamma2={args.gamma2}, w2={args.w2:.2e} "
          f"into {cache}")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--work", default=DEFAULT_WORK, help="working/cache directory")
    p.add_argument("--config", default=None, help="path to config.yaml")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("inventory", help="frames, MBES depth, contiguous runs")
    s.add_argument("--min-frames", type=int, default=150)
    s.add_argument("--min-on-dem", type=float, default=0.80)
    s.set_defaults(func=cmd_inventory)

    s = sub.add_parser("scan", help="score runs by texture (ORB link rate)")
    s.add_argument("--blocks", type=int, default=5, help="sample blocks per run")
    s.add_argument("--block", type=int, default=6, help="pairs per block")
    s.add_argument("--workers", type=int, default=4)
    s.add_argument("--limit", type=int, default=0)
    s.set_defaults(func=cmd_scan)

    def strip_args(parser):
        parser.add_argument("--start", type=int, required=True,
                            help="first metadata row of the strip")
        parser.add_argument("--n", type=int, required=True, help="frame count")
        return parser

    s = strip_args(sub.add_parser("chain", help="offline ORB chain + nav bridging"))
    s.add_argument("--anchor-window", type=int, default=51)
    s.add_argument("--from-links", action="store_true",
                   help="reuse links.csv instead of re-registering the imagery")
    s.set_defaults(func=cmd_chain)

    s = strip_args(sub.add_parser("fetch", help="fetch + cache one micro-DEM per frame"))
    s.add_argument("--refresh", action="store_true", help="refetch cached frames")
    s.set_defaults(func=cmd_fetch)

    s = strip_args(sub.add_parser("inspect", help="sanity-check the fetched batch"))
    s.set_defaults(func=cmd_inspect)

    s = sub.add_parser("composite", help="resample + blend -> GeoTIFFs")
    s.add_argument("--pixel", type=float, default=0.003, help="target cell size, m")
    s.add_argument("--epsg", type=int, default=32619)
    s.add_argument("--north-up", action="store_true",
                   help="do not align the grid to the track (huge for a long ribbon)")
    s.add_argument("--max-cells", type=float, default=4e8)
    s.set_defaults(func=cmd_composite)

    s = sub.add_parser("analyse", help="profile vs MBES + the scale-gap spectrum")
    s.set_defaults(func=cmd_analyse)

    s = sub.add_parser("simulate",
                       help="fabricate a cache from a known surface (no network)")
    s.add_argument("--source-work", default=DEFAULT_WORK,
                   help="directory holding the real poses.csv")
    s.add_argument("--frames", type=int, default=0, help="0 = all")
    s.add_argument("--gamma2", type=float, default=3.0)
    s.add_argument("--w2", type=float, default=2.0e-7)
    s.add_argument("--dx-mm", type=float, default=6.0)
    s.add_argument("--dem-side", type=int, default=200)
    s.add_argument("--seed", type=int, default=0)
    s.set_defaults(func=cmd_simulate)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
