"""Unit tests for gt/ribbon.py — the geometry of the photogrammetric ribbon.

Everything here is synthetic: a made-up frame grid, a made-up track, a
made-up power-law surface.  No network, no stereo archive, no service.  What is
being checked is that the *geometry* is right, because that is what a bad
ribbon would hide: a sign error in the body-axis convention or a transposed
affine still produces a plausible-looking strip.
"""
import numpy as np
import pytest

from groundtruther.gt import ribbon


# --- image access -----------------------------------------------------------

def test_left_half_takes_the_left_camera():
    image = np.zeros((4, 10), dtype=np.uint8)
    image[:, :5] = 1
    left = ribbon.left_half(image)
    assert left.shape == (4, 5)
    assert (left == 1).all()


# --- the link gate ----------------------------------------------------------

def _gate(**kw):
    p = ribbon.LinkParams()
    args = dict(n_inliers=40, tx=-30.0, ty=500.0, rot=2.0, scale=1.0)
    args.update(kw)
    return ribbon._gate(args["n_inliers"], args["tx"], args["ty"],
                        args["rot"], args["scale"], p)


def test_gate_accepts_a_plausible_advance():
    assert _gate() == (True, "ok")


@pytest.mark.parametrize("kw,reason", [
    ({"n_inliers": 5}, "few_inliers"),
    ({"ty": 50.0}, "advance_out_of_band"),       # far too little advance
    ({"ty": 1500.0}, "advance_out_of_band"),     # more than a frame height
    ({"tx": 600.0}, "cross_track"),              # sideways, not along track
    ({"rot": 40.0}, "rotation"),
    ({"scale": 1.6}, "scale"),
])
def test_gate_rejects_implausible_transforms(kw, reason):
    """RANSAC returns confident nonsense on this imagery; the gate is the filter.

    Each of these was observed on real pairs with 15-25 "inliers" — an ungated
    chain would have integrated them.
    """
    accepted, why = _gate(**kw)
    assert not accepted and why == reason


def test_link_rate_summarises_and_counts_reasons():
    links = [ribbon.Link(i, 40, -30, 500, 1, 1, True) for i in range(6)]
    links += [ribbon.Link(i, 3, np.nan, np.nan, np.nan, np.nan, False,
                          "few_inliers") for i in range(6, 10)]
    summary = ribbon.link_rate(links)
    assert summary["n_pairs"] == 10
    assert summary["n_linked"] == 6
    assert summary["link_rate"] == pytest.approx(0.6)
    assert summary["reasons"] == {"few_inliers": 4}


def test_link_rate_of_nothing_is_not_a_crash():
    assert ribbon.link_rate([])["n_pairs"] == 0


# --- body-axis conventions (the sign errors that would flip the ribbon) -----

def test_content_scrolling_down_means_the_platform_advanced():
    """+ty (content moves down the image) is forward motion, not astern.

    Image bottom->top is the heading, so a feature slides *astern* — down the
    image — by exactly what the platform advances.
    """
    link = ribbon.Link(0, 50, tx=0.0, ty=500.0, rotation_deg=0.0, scale=1.0,
                       accepted=True)
    along, cross, _ = ribbon.link_to_body_motion(link, gsd_mm=1.0)
    assert along == pytest.approx(500.0)
    assert cross == pytest.approx(0.0)


def test_content_moving_left_means_the_platform_moved_starboard():
    link = ribbon.Link(0, 50, tx=-100.0, ty=500.0, rotation_deg=0.0, scale=1.0,
                       accepted=True)
    _, cross, _ = ribbon.link_to_body_motion(link, gsd_mm=2.0)
    assert cross == pytest.approx(200.0)


def test_yaw_is_the_negative_of_the_image_rotation():
    """Turn the platform clockwise and the imaged world turns anticlockwise."""
    link = ribbon.Link(0, 50, tx=0.0, ty=500.0, rotation_deg=3.0, scale=1.0,
                       accepted=True)
    assert ribbon.link_to_body_motion(link, 1.0)[2] == pytest.approx(-3.0)


@pytest.mark.parametrize("heading,expect", [
    (0.0, (0.0, 1.0)),       # north
    (90.0, (1.0, 0.0)),      # east
    (180.0, (0.0, -1.0)),
    (270.0, (-1.0, 0.0)),
])
def test_forward_motion_follows_the_compass_heading(heading, expect):
    de, dn = ribbon.body_to_world(1000.0, 0.0, heading)
    assert (de, dn) == (pytest.approx(expect[0], abs=1e-9),
                        pytest.approx(expect[1], abs=1e-9))


def test_starboard_is_ninety_degrees_right_of_the_heading():
    de, dn = ribbon.body_to_world(0.0, 1000.0, 0.0)     # heading north
    assert de == pytest.approx(1.0) and dn == pytest.approx(0.0, abs=1e-9)


def test_gsd_is_altitude_over_focal_length():
    assert ribbon.gsd_mm_per_px(2480.28) == pytest.approx(1.0)


# --- the chain --------------------------------------------------------------

def _straight_track(n, step_m=0.5, heading=90.0):
    """A clean eastbound track, and the quantized nav an USBL would report."""
    truth_e = np.arange(n) * step_m
    truth_n = np.zeros(n)
    # piecewise-constant nav: one fix every 6 frames, as measured on this survey
    nav_e = truth_e[(np.arange(n) // 6) * 6]
    nav_n = truth_n.copy()
    return truth_e, truth_n, nav_e, nav_n, np.full(n, heading)


def test_chain_uses_pixels_between_the_nav_fixes():
    """The point of the chain: recover the real 0.5 m step from clumped nav.

    A real run length (296 frames) with the documented default window — the
    anchor needs several clump periods on each side of a frame to average the
    staircase away, so a short run keeps some of it near the ends.
    """
    n = 296
    truth_e, truth_n, nav_e, nav_n, heading = _straight_track(n)
    altitude = np.full(n, 2480.28)                 # so gsd = 1 mm/px
    links = [ribbon.Link(i, 40, tx=0.0, ty=500.0, rotation_deg=0.0, scale=1.0,
                         accepted=True) for i in range(n - 1)]
    out = ribbon.chain_track(links, nav_e, nav_n, heading, altitude)
    assert out["n_pixel_steps"] == n - 1
    assert (out["source"][1:] == "pixel").all()
    steps = ribbon.step_lengths(out["easting"], out["northing"])
    assert np.allclose(steps, 0.5, atol=0.01)
    # the raw nav, by contrast, is a staircase of zeros and 3 m jumps
    nav_steps = ribbon.step_lengths(nav_e, nav_n)
    assert nav_steps.min() == pytest.approx(0.0)
    assert nav_steps.max() > 2.9


def test_anchor_window_must_outrun_the_usbl_clumps():
    """A window near the clump period leaves the staircase in — a boxcar's flaw.

    The smoother is Gaussian for exactly this reason; the test pins that the
    default window is doing real work rather than being decorative.
    """
    n = 296
    _, _, nav_e, nav_n, heading = _straight_track(n)
    altitude = np.full(n, 2480.28)
    links = [ribbon.Link(i, 40, 0.0, 500.0, 0.0, 1.0, True) for i in range(n - 1)]
    tight = ribbon.chain_track(links, nav_e, nav_n, heading, altitude,
                               anchor_window=7)
    loose = ribbon.chain_track(links, nav_e, nav_n, heading, altitude,
                               anchor_window=51)
    ripple = lambda out: np.std(ribbon.step_lengths(out["easting"], out["northing"]))
    assert ripple(tight) > 5 * ripple(loose)


def test_chain_bridges_unlinked_gaps_with_the_navigation():
    n = 60
    _, _, nav_e, nav_n, heading = _straight_track(n)
    altitude = np.full(n, 2480.28)
    links = [ribbon.Link(i, 40, 0.0, 500.0, 0.0, 1.0, accepted=(i % 3 != 0))
             for i in range(n - 1)]
    out = ribbon.chain_track(links, nav_e, nav_n, heading, altitude,
                             anchor_window=21)
    source = out["source"]
    assert source[0] == "nav"
    assert [s for s in source[1:4]] == ["nav", "pixel", "pixel"]
    assert out["n_pixel_steps"] == sum(1 for l in links if l.accepted)


def test_chain_stays_anchored_to_the_navigation():
    """Absolute placement is the nav's job; a scaled-up chain must not drift off."""
    n = 120
    _, _, nav_e, nav_n, heading = _straight_track(n)
    altitude = np.full(n, 2480.28)
    # links that would imply a 20 % too long track if left unanchored
    links = [ribbon.Link(i, 40, 0.0, 600.0, 0.0, 1.0, True) for i in range(n - 1)]
    out = ribbon.chain_track(links, nav_e, nav_n, heading, altitude,
                             anchor_window=31)
    drift = np.abs(out["easting"] - nav_e)
    assert drift.max() < 2.0          # unanchored this would reach ~12 m


def test_calibrate_scale_recovers_a_wrong_focal_length():
    n = 160
    truth_e, _, nav_e, nav_n, heading = _straight_track(n)
    # the real gsd makes 500 px == 0.5 m, i.e. focal 2480.28; hand the
    # calibrator a focal length 10 % too long and it should find its way back
    links = [ribbon.Link(i, 40, 0.0, 500.0, 0.0, 1.0, True) for i in range(n - 1)]
    focal, ratio, windows = ribbon.calibrate_scale(links, truth_e, np.zeros(n),
                                                   np.full(n, 2480.28),
                                                   focal_px=2480.28 * 1.1)
    assert windows >= 2
    assert ratio == pytest.approx(1 / 1.1, rel=1e-6)
    assert focal == pytest.approx(2480.28, rel=1e-6)


def test_calibrate_scale_is_immune_to_the_usbl_staircase():
    """Per-step nav distances are 13 mm one frame and 3.5 m the next.

    Summing them would inflate the reference; comparing end-to-end displacement
    over a long window does not, so the quantized nav gives the same answer as
    the true track.
    """
    n = 160
    truth_e, _, nav_e, nav_n, _ = _straight_track(n)
    links = [ribbon.Link(i, 40, 0.0, 500.0, 0.0, 1.0, True) for i in range(n - 1)]
    altitude = np.full(n, 2480.28)
    clean = ribbon.calibrate_scale(links, truth_e, np.zeros(n), altitude)[1]
    quantized = ribbon.calibrate_scale(links, nav_e, nav_n, altitude)[1]
    assert quantized == pytest.approx(clean, rel=0.02)


def test_calibrate_scale_skips_windows_containing_an_unlinked_pair():
    n = 160
    truth_e, _, _, _, _ = _straight_track(n)
    links = [ribbon.Link(i, 40, 0.0, 500.0, 0.0, 1.0, accepted=(i != 10))
             for i in range(n - 1)]
    _, _, windows = ribbon.calibrate_scale(links, truth_e, np.zeros(n),
                                           np.full(n, 2480.28))
    assert windows == 2          # the first window is skipped, not fudged


def test_calibrate_scale_with_nothing_linked_leaves_the_focal_alone():
    links = [ribbon.Link(i, 3, 0, 0, 0, 0, False) for i in range(50)]
    focal, ratio, windows = ribbon.calibrate_scale(links, np.arange(60.0),
                                                   np.zeros(60),
                                                   np.full(60, 2480.28))
    assert focal == pytest.approx(ribbon.FOCAL_PX)
    assert np.isnan(ratio) and windows == 0


def test_chain_rejects_mismatched_input_lengths():
    with pytest.raises(ValueError):
        ribbon.chain_track([], [0, 1, 2], [0, 1], [0, 0, 0], [2000, 2000, 2000])


def test_along_track_distance_starts_at_zero_and_accumulates():
    d = ribbon.along_track_distance([0, 3, 3], [0, 0, 4])
    assert list(d) == [0.0, 3.0, 7.0]


# --- the affine and the resample -------------------------------------------

def _rotated_geotransform(origin, pixel_m, heading_deg):
    """A frame grid rotated to *heading_deg* — the shape the service returns.

    The mount fixes the convention: image bottom->top is the heading and
    image-right is starboard.  So ``-row`` must point along ``(sin h, cos h)``
    and ``+col`` along ``(cos h, -sin h)``, which is what these six numbers say.
    """
    t = np.radians(heading_deg)
    a, d = pixel_m * np.cos(t), -pixel_m * np.sin(t)      # +col = starboard
    b, e = -pixel_m * np.sin(t), -pixel_m * np.cos(t)     # -row = heading
    return [origin[0], a, b, origin[1], d, e]


def test_affine_parts_uses_gdal_order():
    origin, matrix = ribbon.affine_parts([10, 1, 2, 20, 3, 4])
    assert list(origin) == [10, 20]
    assert matrix.tolist() == [[1, 2], [3, 4]]


def test_frame_corners_of_a_north_up_grid():
    corners = ribbon.frame_corners([100.0, 1.0, 0.0, 200.0, 0.0, -1.0], (10, 20))
    assert corners.min(axis=0).tolist() == [100.0, 190.0]
    assert corners.max(axis=0).tolist() == [120.0, 200.0]


def test_target_grid_covers_every_rotated_frame():
    geotransforms = [_rotated_geotransform((0.0, 0.0), 0.01, h)
                     for h in (0.0, 45.0, 90.0)]
    shapes = [(50, 50)] * 3
    target = ribbon.target_grid(geotransforms, shapes, 0.01)
    assert target["geotransform"][1] == pytest.approx(0.01)
    assert target["geotransform"][5] == pytest.approx(-0.01)
    corners = np.vstack([ribbon.frame_corners(gt, s)
                         for gt, s in zip(geotransforms, shapes)])
    c, px, _, f, _, _ = target["geotransform"]
    assert c <= corners[:, 0].min() + 1e-9
    assert f >= corners[:, 1].max() - 1e-9
    assert c + target["width"] * px >= corners[:, 0].max() - 1e-9


def test_resample_of_a_north_up_frame_is_the_identity():
    values = np.arange(60, dtype=float).reshape(6, 10)
    gt = [100.0, 1.0, 0.0, 200.0, 0.0, -1.0]
    target = ribbon.target_grid([gt], [values.shape], 1.0)
    window, out, valid = ribbon.resample_frame(values, gt, target)
    assert valid.sum() >= values.size * 0.9
    got = out[0][valid]
    want = np.resize(values, out[0].shape)[valid]
    assert np.allclose(got, want, atol=1e-6)


def test_resample_puts_a_rotated_frame_where_the_affine_says():
    """A marked cell must land at the world point the affine maps it to.

    This is the test that would fail on a transposed or inverted affine — the
    kind of bug that still yields a ribbon, just not of that piece of seabed.
    """
    values = np.full((21, 21), np.nan)
    values[5, 3] = 42.0
    gt = _rotated_geotransform((500000.0, 4500000.0), 0.01, 37.0)
    origin, matrix = ribbon.affine_parts(gt)
    world = origin + matrix @ np.array([3 + 0.5, 5 + 0.5])
    target = ribbon.target_grid([gt], [values.shape], 0.005, margin_m=0.05)
    window, out, valid = ribbon.resample_frame(values, gt, target)
    row0, _, col0, _ = window
    hit = np.argwhere(np.isfinite(out[0]))
    assert hit.size, "the marked cell disappeared in the resample"
    c, px, _, f, _, _ = target["geotransform"]
    east = c + (col0 + hit[:, 1] + 0.5) * px
    north = f - (row0 + hit[:, 0] + 0.5) * px
    assert np.abs(east - world[0]).min() < 0.02
    assert np.abs(north - world[1]).min() < 0.02
    assert np.nanmax(out[0]) == pytest.approx(42.0, rel=1e-6)


def test_resample_carries_every_band_on_one_grid():
    dem = np.arange(20, dtype=float).reshape(4, 5)
    red = dem * 2
    gt = [0.0, 1.0, 0.0, 10.0, 0.0, -1.0]
    target = ribbon.target_grid([gt], [dem.shape], 1.0)
    _, out, valid = ribbon.resample_frame([dem, red], gt, target)
    assert out.shape[0] == 2
    assert np.allclose(out[1][valid], 2 * out[0][valid])


def test_no_data_does_not_smear_across_the_frame_edge():
    values = np.ones((10, 10))
    values[:, 5:] = np.nan
    gt = [0.0, 1.0, 0.0, 10.0, 0.0, -1.0]
    target = ribbon.target_grid([gt], [values.shape], 1.0)
    _, out, valid = ribbon.resample_frame(values, gt, target)
    assert np.isfinite(out[0][valid]).all()
    assert np.allclose(out[0][valid], 1.0)


# --- blending ---------------------------------------------------------------

def test_feather_weights_peak_in_the_middle_and_vanish_outside():
    valid = np.zeros((9, 9), bool)
    valid[2:7, 2:7] = True
    w = ribbon.feather_weights(valid)
    assert w[~valid].max() == 0.0
    assert w[4, 4] == w.max()
    assert w[2, 2] < w[4, 4]


def test_canvas_averages_two_frames_and_counts_observations():
    target = {"geotransform": [0.0, 1.0, 0.0, 4.0, 0.0, -1.0],
              "width": 4, "height": 4, "pixel_m": 1.0}
    canvas = ribbon.RibbonCanvas(target, n_bands=1)
    valid = np.ones((2, 4), bool)
    canvas.add((0, 2, 0, 4), np.full((1, 2, 4), 10.0), valid,
               weights=np.ones((2, 4)))
    canvas.add((1, 3, 0, 4), np.full((1, 2, 4), 20.0), valid,
               weights=np.ones((2, 4)))
    bands, count = canvas.result()
    assert count[0, 0] == 1 and count[1, 0] == 2 and count[3, 0] == 0
    assert bands[0][0, 0] == pytest.approx(10.0)
    assert bands[0][1, 0] == pytest.approx(15.0)     # the overlap
    assert bands[0][2, 0] == pytest.approx(20.0)
    assert np.isnan(bands[0][3, 0])


def test_canvas_weights_the_blend():
    target = {"geotransform": [0.0, 1.0, 0.0, 2.0, 0.0, -1.0],
              "width": 2, "height": 2, "pixel_m": 1.0}
    canvas = ribbon.RibbonCanvas(target, n_bands=1)
    valid = np.ones((2, 2), bool)
    canvas.add((0, 2, 0, 2), np.full((1, 2, 2), 0.0), valid,
               weights=np.full((2, 2), 3.0))
    canvas.add((0, 2, 0, 2), np.full((1, 2, 2), 10.0), valid,
               weights=np.full((2, 2), 1.0))
    bands, _ = canvas.result()
    assert bands[0][0, 0] == pytest.approx(2.5)


def test_overlap_difference_measures_the_seam():
    a = np.zeros((20, 20))
    b = np.full((20, 20), 0.03)          # 3 cm mis-registration in height
    valid = np.ones((20, 20), bool)
    stats = ribbon.overlap_difference(a, valid, b, valid)
    assert stats["n_cells"] == 400
    assert stats["median"] == pytest.approx(-0.03)
    assert stats["median_abs"] == pytest.approx(0.03)


def test_overlap_difference_needs_a_real_overlap():
    valid_a = np.zeros((20, 20), bool); valid_a[:5] = True
    valid_b = np.zeros((20, 20), bool); valid_b[15:] = True
    assert ribbon.overlap_difference(np.zeros((20, 20)), valid_a,
                                     np.zeros((20, 20)), valid_b) is None


# --- binning and profile comparison ----------------------------------------

def test_bin_along_track_averages_into_fixed_bins():
    distance = np.array([0.1, 0.4, 1.2, 1.8, 5.0])
    values = np.array([1.0, 3.0, 10.0, 20.0, 7.0])
    centres, mean, count = ribbon.bin_along_track(distance, values, 1.0)
    assert count[0] == 2 and mean[0] == pytest.approx(2.0)
    assert count[1] == 2 and mean[1] == pytest.approx(15.0)
    assert count[2] == 0 and np.isnan(mean[2])
    assert centres[0] == pytest.approx(0.6)


def test_bin_along_track_ignores_nan():
    centres, mean, count = ribbon.bin_along_track([0.1, 0.2], [np.nan, 4.0], 1.0)
    assert count[0] == 1 and mean[0] == pytest.approx(4.0)


def test_compare_profiles_removes_a_constant_offset():
    x = np.sin(np.linspace(0, 6, 50))
    stats = ribbon.compare_profiles(x + 12.0, x)
    assert stats["corr"] == pytest.approx(1.0)
    assert stats["bias"] == pytest.approx(12.0)
    assert stats["median_abs_dz"] == pytest.approx(0.0, abs=1e-9)


def test_compare_profiles_with_nothing_in_common():
    out = ribbon.compare_profiles([np.nan, np.nan], [1.0, 2.0])
    assert out["n"] == 0 and np.isnan(out["corr"])


# --- the spectrum (task 11) -------------------------------------------------

def test_spectrum_conserves_variance():
    """Parseval: integrating W1 over both signs of k returns the variance."""
    rng = np.random.default_rng(0)
    n, dx = 4096, 0.01
    z = rng.normal(0, 0.05, n)
    k, w = ribbon.along_track_spectrum(z, dx, detrend=False, window=False)
    dk = 2 * np.pi / (n * dx)
    assert 2 * float(np.sum(w) * dk) == pytest.approx(np.var(z), rel=0.05)


def test_spectrum_finds_a_sinusoid_at_its_own_wavenumber():
    n, dx, wavelength = 2048, 0.01, 0.8
    x = np.arange(n) * dx
    z = 0.02 * np.sin(2 * np.pi * x / wavelength)
    k, w = ribbon.along_track_spectrum(z, dx)
    assert k[np.argmax(w)] == pytest.approx(2 * np.pi / wavelength, rel=0.02)


def test_spectrum_interpolates_across_no_data():
    z = np.sin(np.linspace(0, 20, 512))
    z[100:104] = np.nan
    k, w = ribbon.along_track_spectrum(z, 0.01)
    assert np.isfinite(w).all()


def test_spectrum_refuses_a_profile_that_is_almost_all_gap():
    z = np.full(64, np.nan)
    z[:4] = 1.0
    with pytest.raises(ValueError):
        ribbon.along_track_spectrum(z, 0.01)


def test_power_law_fit_recovers_a_planted_exponent():
    k = np.logspace(0, 3, 200)
    w = 1e-4 * k ** -2.6
    fit = ribbon.power_law_fit(k, w, (10, 500))
    assert fit["gamma"] == pytest.approx(2.6, rel=1e-6)
    assert fit["amplitude"] == pytest.approx(1e-4, rel=1e-6)
    assert fit["r2"] == pytest.approx(1.0, abs=1e-9)


def test_power_law_fit_declines_an_empty_band():
    k = np.logspace(0, 1, 50)
    assert np.isnan(ribbon.power_law_fit(k, k ** -2, (1e4, 1e5))["gamma"])


def test_the_one_dimensional_slope_is_one_shallower_than_the_two():
    """gamma1 = gamma2 - 1 — the identity task 11 leans on."""
    k = np.logspace(-1, 3, 300)
    w1 = ribbon.w1_from_gamma2(k, gamma2=3.2, w2=1e-7)
    fit = ribbon.power_law_fit(k, w1, (1, 100))
    assert fit["gamma"] == pytest.approx(2.2, rel=1e-6)


def test_w1_from_gamma2_matches_numerical_integration():
    """The closed form must equal integrating W2 over the cross-track wavenumber."""
    gamma2, w2, k_ref = 3.0, 2.5e-7, 100.0
    k = 4.0
    q = np.linspace(-4000, 4000, 2_000_001)
    kk = np.hypot(k, q)
    integrand = w2 * (kk / k_ref) ** -gamma2
    numeric = np.trapezoid(integrand, q)
    assert ribbon.w1_from_gamma2(k, gamma2, w2, k_ref) == pytest.approx(numeric,
                                                                       rel=1e-3)


def test_w1_from_gamma2_declines_a_non_convergent_exponent():
    assert np.isnan(ribbon.w1_from_gamma2(1.0, gamma2=0.8, w2=1e-7))


def test_wavelength_band_to_k_is_the_acoustic_gap():
    k_lo, k_hi = ribbon.wavelength_band_to_k(1.2, 3.0)
    assert k_lo == pytest.approx(2 * np.pi / 3.0)
    assert k_hi == pytest.approx(2 * np.pi / 1.2)


# --- re-placing a frame with the corrected pose -----------------------------

def test_adjust_geotransform_translates_without_turning():
    gt = [100.0, 1.0, 0.0, 200.0, 0.0, -1.0]
    out = ribbon.adjust_geotransform(gt, (10, 10), d_east=5.0, d_north=-3.0)
    assert out[0] == pytest.approx(105.0)
    assert out[3] == pytest.approx(197.0)
    assert out[1:3] == pytest.approx(gt[1:3])
    assert out[4:6] == pytest.approx(gt[4:6])


def test_adjust_geotransform_turns_about_the_frame_centre():
    """The nav fix is at the frame centre, so that is what must stay put."""
    gt = _rotated_geotransform((500000.0, 4500000.0), 0.01, 30.0)
    shape = (40, 30)
    before = ribbon.affine_parts(gt)
    centre_before = before[0] + before[1] @ np.array([15.0, 20.0])
    out = ribbon.adjust_geotransform(gt, shape, d_heading_deg=12.0)
    after = ribbon.affine_parts(out)
    centre_after = after[0] + after[1] @ np.array([15.0, 20.0])
    assert centre_after == pytest.approx(centre_before)
    assert ribbon.heading_from_geotransform(out) == pytest.approx(42.0, abs=1e-6)


def test_heading_from_geotransform_reads_back_what_was_built_in():
    for heading in (0.0, 37.0, 175.0, 300.0):
        gt = _rotated_geotransform((0.0, 0.0), 0.003, heading)
        assert ribbon.heading_from_geotransform(gt) == pytest.approx(heading,
                                                                    abs=1e-6)


def test_adjust_geotransform_of_a_rotated_frame_keeps_the_pixel_size():
    gt = _rotated_geotransform((0.0, 0.0), 0.003, 77.0)
    out = ribbon.adjust_geotransform(gt, (20, 20), 1.0, 2.0, 5.0)
    _, matrix = ribbon.affine_parts(out)
    assert np.hypot(matrix[0, 0], matrix[1, 0]) == pytest.approx(0.003)


# --- the track-aligned target grid ------------------------------------------

def test_track_azimuth_is_the_end_to_end_course():
    assert ribbon.track_azimuth([0, 10], [0, 0]) == pytest.approx(90.0)
    assert ribbon.track_azimuth([0, 0], [0, 10]) == pytest.approx(0.0)
    assert ribbon.track_azimuth([0, -10], [0, 0]) == pytest.approx(270.0)


def test_a_diagonal_ribbon_needs_a_track_aligned_grid():
    """North-up round a 45-degree ribbon costs tens of times the cells.

    The ratio is about ``length * |sin a cos a| / width``: ~40x for this 100 m
    synthetic, ~70x for the real 172 m strip.  This is the whole reason the
    target grid is allowed to be rotated, so it is worth pinning rather than
    leaving as a comment.
    """
    pixel = 0.003
    frames = [(_rotated_geotransform((s * 0.7071 * 100, s * 0.7071 * 100),
                                     pixel, 45.0), (400, 400))
              for s in np.linspace(0, 1, 40)]
    gts = [f[0] for f in frames]
    shapes = [f[1] for f in frames]
    north_up = ribbon.target_grid(gts, shapes, pixel)
    aligned = ribbon.target_grid(gts, shapes, pixel, azimuth_deg=45.0)
    north_up_cells = north_up["width"] * north_up["height"]
    aligned_cells = aligned["width"] * aligned["height"]
    assert aligned_cells * 40 < north_up_cells
    assert min(aligned["width"], aligned["height"]) < 1000     # a ribbon, not a box


def test_track_aligned_grid_still_covers_every_frame():
    gts = [_rotated_geotransform((i * 0.5, i * 0.3), 0.01, 60.0) for i in range(5)]
    shapes = [(30, 40)] * 5
    target = ribbon.target_grid(gts, shapes, 0.01, azimuth_deg=60.0)
    origin, matrix = ribbon.affine_parts(target["geotransform"])
    inverse = np.linalg.inv(matrix)
    for gt, shape in zip(gts, shapes):
        grid = (ribbon.frame_corners(gt, shape) - origin) @ inverse.T
        assert grid[:, 0].min() >= -1e-6
        assert grid[:, 1].min() >= -1e-6
        assert grid[:, 0].max() <= target["width"] + 1e-6
        assert grid[:, 1].max() <= target["height"] + 1e-6


def test_resample_into_a_rotated_target_lands_on_the_same_world_point():
    values = np.full((21, 21), np.nan)
    values[7, 4] = 17.0
    gt = _rotated_geotransform((500000.0, 4500000.0), 0.01, 20.0)
    origin, matrix = ribbon.affine_parts(gt)
    world = origin + matrix @ np.array([4.5, 7.5])
    target = ribbon.target_grid([gt], [values.shape], 0.005, margin_m=0.05,
                                azimuth_deg=20.0)
    window, out, valid = ribbon.resample_frame(values, gt, target)
    row0, _, col0, _ = window
    hit = np.argwhere(np.isfinite(out[0]))
    assert hit.size
    t_origin, t_matrix = ribbon.affine_parts(target["geotransform"])
    cols = col0 + hit[:, 1] + 0.5
    rows = row0 + hit[:, 0] + 0.5
    east = t_origin[0] + t_matrix[0, 0] * cols + t_matrix[0, 1] * rows
    north = t_origin[1] + t_matrix[1, 0] * cols + t_matrix[1, 1] * rows
    assert np.hypot(east - world[0], north - world[1]).min() < 0.02
    assert np.nanmax(out[0]) == pytest.approx(17.0, rel=1e-6)


def test_intersect_windows_cuts_both_frames_to_the_shared_patch():
    a = (0, 10, 0, 10)
    b = (5, 15, 3, 8)
    window, cut_a, cut_b = ribbon.intersect_windows(a, b)
    assert window == (5, 10, 3, 8)
    values_a = np.arange(100).reshape(10, 10)
    values_b = np.arange(50).reshape(10, 5)
    assert values_a[cut_a].shape == values_b[cut_b].shape == (5, 5)
    assert values_a[cut_a][0, 0] == values_a[5, 3]
    assert values_b[cut_b][0, 0] == values_b[0, 0]


def test_intersect_windows_of_frames_that_never_meet():
    assert ribbon.intersect_windows((0, 5, 0, 5), (10, 15, 0, 5)) is None


def test_smoothing_a_track_does_not_shorten_it():
    """A trend-blind smoother would eat a few percent of the track length.

    That error would arrive disguised as a camera focal length, so it is worth a
    test of its own rather than trusting the calibration to notice.
    """
    x = np.arange(200, dtype=float) * 0.5
    smoothed = ribbon._smooth(x, 51)
    assert smoothed[-1] - smoothed[0] == pytest.approx(x[-1] - x[0], rel=1e-9)


def test_smoothing_still_removes_the_usbl_staircase():
    """The ripple goes; the constant lag stays, because it is real.

    A staircase reports each clump at the position of its first frame, so it
    sits half a clump behind the truth throughout.  That is a property of the
    USBL, not noise, and smoothing neither should nor does remove it.
    """
    truth = np.arange(200, dtype=float) * 0.5
    staircase = truth[(np.arange(200) // 6) * 6]
    smoothed = ribbon._smooth(staircase, 51)
    assert np.std(smoothed - truth) < np.std(staircase - truth) / 10
    assert np.mean(smoothed - truth) == pytest.approx(np.mean(staircase - truth),
                                                      abs=0.05)


def test_band_average_smooths_a_noisy_periodogram():
    """A raw periodogram's 100 % per-ordinate error has to come down first."""
    rng = np.random.default_rng(3)
    k = np.logspace(0, 3, 4000)
    truth = 1e-4 * k ** -2.4
    noisy = truth * rng.exponential(1.0, k.size)      # chi-squared-2 statistics
    kb, wb, counts = ribbon.band_average(k, noisy)
    assert counts.sum() == k.size
    assert np.all(np.diff(kb) > 0)
    scatter = lambda kk, ww: np.std(np.log(ww) - np.log(1e-4 * kk ** -2.4))
    assert scatter(kb, wb) < scatter(k, noisy) / 3


def test_band_average_makes_a_narrow_band_exponent_recoverable():
    rng = np.random.default_rng(7)
    k = np.logspace(0, 3, 6000)
    noisy = 1e-4 * k ** -2.4 * rng.exponential(1.0, k.size)
    band = (10.0, 60.0)
    raw = ribbon.power_law_fit(k, noisy, band)
    kb, wb, _ = ribbon.band_average(k, noisy)
    smoothed = ribbon.power_law_fit(kb, wb, band)
    assert abs(smoothed["gamma"] - 2.4) < abs(raw["gamma"] - 2.4)
    assert smoothed["gamma"] == pytest.approx(2.4, abs=0.25)


def test_band_average_of_nothing():
    k, w, counts = ribbon.band_average(np.zeros(0), np.zeros(0))
    assert k.size == w.size == counts.size == 0


def test_power_law_fit_reports_a_standard_error_on_the_exponent():
    rng = np.random.default_rng(11)
    k = np.logspace(0, 2, 200)
    clean = ribbon.power_law_fit(k, 1e-4 * k ** -2.6, (1, 100))
    noisy = ribbon.power_law_fit(k, 1e-4 * k ** -2.6 * np.exp(
        rng.normal(0, 0.8, k.size)), (1, 100))
    assert clean["gamma_err"] < 1e-6
    assert noisy["gamma_err"] > clean["gamma_err"]
    assert abs(noisy["gamma"] - 2.6) < 5 * noisy["gamma_err"]


# --- end to end: a planted roughness must survive the whole pipeline --------

def _planted_surface(gamma2, w2, *, k_min=0.3, k_max=150.0, n_modes=400, seed=5):
    """An east-west surface whose along-track ``W1`` is exactly the power law.

    Amplitudes are ``2*sqrt(W1*dk)``: the variance of a sum of random-phase
    cosines is ``sum(a^2/2)`` and it has to equal the **two-sided** integral
    ``2*sum(W1*dk)``.
    """
    rng = np.random.default_rng(seed)
    edges = np.logspace(np.log10(k_min), np.log10(k_max), n_modes + 1)
    k = np.sqrt(edges[:-1] * edges[1:])
    amplitude = 2.0 * np.sqrt(ribbon.w1_from_gamma2(k, gamma2, w2) * np.diff(edges))
    phase = rng.uniform(0, 2 * np.pi, k.size)

    def surface(easting, northing):
        e = np.asarray(easting, dtype=float)
        return (amplitude * np.cos(k * e[..., None] + phase)).sum(axis=-1)
    return surface


def test_a_planted_roughness_survives_resample_blend_and_spectrum():
    """The whole geometric pipeline, against a surface whose answer is known.

    Frames are laid along an eastbound track, each on its own rotated grid,
    resampled into one track-aligned canvas, blended, reduced to an along-track
    profile and spectrally fitted.  A sign error in the affine, a transposed
    resample or a botched window normalisation all break this; none of them
    break the individual unit tests above.
    """
    gamma2, w2, pixel = 3.0, 2.0e-7, 0.01
    surface = _planted_surface(gamma2, w2)
    side, step, n_frames = 80, 0.2, 100

    geotransforms, grids = [], []
    for i in range(n_frames):
        centre = np.array([i * step, 0.0])
        matrix = np.array([[0.0, -pixel], [-pixel, 0.0]])     # heading 90 deg
        origin = centre - matrix @ np.array([side / 2.0, side / 2.0])
        gt = [origin[0], matrix[0, 0], matrix[0, 1],
              origin[1], matrix[1, 0], matrix[1, 1]]
        col, row = np.meshgrid(np.arange(side) + 0.5, np.arange(side) + 0.5)
        east = origin[0] + matrix[0, 0] * col + matrix[0, 1] * row
        north = origin[1] + matrix[1, 0] * col + matrix[1, 1] * row
        geotransforms.append(gt)
        grids.append(surface(east, north))

    shapes = [g.shape for g in grids]
    target = ribbon.target_grid(geotransforms, shapes, pixel, azimuth_deg=90.0)
    canvas = ribbon.RibbonCanvas(target, n_bands=1)
    for gt, grid in zip(geotransforms, grids):
        window, values, valid = ribbon.resample_frame(grid, gt, target)
        canvas.add(window, values, valid)
    bands, counts = canvas.result()

    assert (counts > 1).any(), "frames should overlap"
    with np.errstate(all="ignore"):
        profile = np.nanmedian(np.where(counts > 0, bands[0], np.nan), axis=1)
    profile = profile[::-1]                      # -row is the direction of travel
    assert np.mean(np.isfinite(profile)) > 0.9

    k, w = ribbon.along_track_spectrum(profile, pixel)
    k_band, w_band, _ = ribbon.band_average(k, w)
    band = ribbon.wavelength_band_to_k(0.4, 4.0)
    fit = ribbon.power_law_fit(k_band, w_band, band)
    assert fit["gamma"] == pytest.approx(gamma2 - 1.0, abs=3 * fit["gamma_err"] + 0.3)

    inside = (k_band >= band[0]) & (k_band <= band[1])
    predicted = ribbon.w1_from_gamma2(k_band[inside], gamma2, w2)
    ratio = float(np.median(w_band[inside] / predicted))
    assert ratio == pytest.approx(1.0, rel=0.5), "the amplitude has to survive too"
