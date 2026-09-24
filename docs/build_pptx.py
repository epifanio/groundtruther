#!/usr/bin/env python
"""Generate the GroundTruther 2026 update deck as an editable .pptx.

Mirrors docs/slides_groundtruther_update_2026.html. Run:
    .venv/bin/python docs/build_pptx.py
Output: docs/slides_groundtruther_update_2026.pptx
"""
from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

INK     = RGBColor(0x14, 0x30, 0x3D)
ACCENT  = RGBColor(0x1A, 0x52, 0x76)
ACCENT2 = RGBColor(0x2E, 0x86, 0xC1)
SEA     = RGBColor(0x0E, 0x6E, 0x6E)
MUTED   = RGBColor(0x5B, 0x6B, 0x76)
SHOT_BG = RGBColor(0xEA, 0xF2, 0xF8)
ROW_HI  = RGBColor(0xEA, 0xF6, 0xFF)

WIDTH, HEIGHT = Inches(13.333), Inches(7.5)


def _set(p, text, size, color=INK, bold=False, align=PP_ALIGN.LEFT, italic=False):
    p.alignment = align
    r = p.add_run()           # works for empty strings too (p.text='' makes no run)
    r.text = text
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.italic = italic
    r.font.color.rgb = color


def add_bullets(tf, bullets, size0=16, size1=14):
    """bullets: list of (level, text). Prefix glyphs (textboxes don't auto-bullet)."""
    for i, (lvl, text) in enumerate(bullets):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        glyph = "•  " if lvl == 0 else "–  "
        _set(p, glyph + text, size0 if lvl == 0 else size1,
             color=INK if lvl == 0 else MUTED)
        p.level = lvl
        p.space_after = Pt(6)


def title_bar(slide, title, tag=None):
    box = slide.shapes.add_textbox(Inches(0.55), Inches(0.35), Inches(12.2), Inches(1.0))
    tf = box.text_frame; tf.word_wrap = True
    _set(tf.paragraphs[0], title, 30, color=ACCENT, bold=True)
    if tag:
        tb = slide.shapes.add_textbox(Inches(11.0), Inches(0.5), Inches(1.9), Inches(0.5))
        ttf = tb.text_frame
        _set(ttf.paragraphs[0], tag.upper(), 11, color=ACCENT2, bold=True, align=PP_ALIGN.RIGHT)
    return box


def shot_placeholder(slide, left, top, width, height, caption):
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    shp.fill.solid(); shp.fill.fore_color.rgb = SHOT_BG
    shp.line.color.rgb = ACCENT2; shp.line.width = Pt(1.75)
    try:
        from pptx.enum.line import MSO_LINE_DASH_STYLE
        shp.line.dash_style = MSO_LINE_DASH_STYLE.DASH
    except Exception:
        pass
    shp.shadow.inherit = False
    tf = shp.text_frame; tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    _set(tf.paragraphs[0], "🖼  Screenshot", 14, color=ACCENT, bold=True, align=PP_ALIGN.CENTER)
    p = tf.add_paragraph()
    _set(p, caption, 11, color=ACCENT, align=PP_ALIGN.CENTER)
    return shp




def section_divider(slide, title, subtitle, lines):
    """An 'Act N' divider: big centred title, sea-coloured subtitle, muted blurb."""
    box = slide.shapes.add_textbox(Inches(1.0), Inches(2.4), Inches(11.3), Inches(2.8))
    tf = box.text_frame; tf.word_wrap = True
    _set(tf.paragraphs[0], title, 50, color=ACCENT, bold=True, align=PP_ALIGN.CENTER)
    p = tf.add_paragraph()
    _set(p, subtitle, 26, color=SEA, bold=True, align=PP_ALIGN.CENTER)
    p.space_before = Pt(8)
    for line in lines:
        pl = tf.add_paragraph()
        _set(pl, line, 14, color=MUTED, align=PP_ALIGN.CENTER)


def add_table(slide, rows, left, top, width, header=True, col_widths=None):
    """rows: list of tuples of cell strings. First row is the header when header=True."""
    n_rows, n_cols = len(rows), len(rows[0])
    height = Inches(0.32) * n_rows
    shape = slide.shapes.add_table(n_rows, n_cols, left, top, width, height)
    tbl = shape.table
    tbl.first_row = header
    if col_widths:
        total = sum(col_widths)
        for c, frac in enumerate(col_widths):
            tbl.columns[c].width = Emu(int(width * frac / total))
    for r, row in enumerate(rows):
        tbl.rows[r].height = Inches(0.28)
        for c, text in enumerate(row):
            cell = tbl.cell(r, c)
            cell.margin_left = Inches(0.06); cell.margin_right = Inches(0.06)
            cell.margin_top = Inches(0.02); cell.margin_bottom = Inches(0.02)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.fill.solid()
            cell.fill.fore_color.rgb = ACCENT if (header and r == 0) else (
                ROW_HI if text.startswith("*") else RGBColor(0xFF, 0xFF, 0xFF))
            tfc = cell.text_frame; tfc.word_wrap = True
            _set(tfc.paragraphs[0], text.lstrip("*"), 11,
                 color=RGBColor(0xFF, 0xFF, 0xFF) if (header and r == 0) else INK,
                 bold=(header and r == 0) or text.startswith("*"))
    return shape


# --------------------------------------------------------------------------- #
# Slide content (mirrors the reveal.js deck and the Marp markdown)
#
#   Act I   (5-13)  the platform
#   Act II  (15-22) optical geometry — the new stereo / roughness / mosaic / ribbon tools
#   Act III (24-26) the science the tools made possible (HRS1508)
#
# Act III numbers come from run R2026-09-21 of PDAL_MBIO/paper/manifest.yml;
# ribbon numbers from docs/photogrammetric_ribbon.md.
# --------------------------------------------------------------------------- #
SLIDES = [
    # ---------------------------------------------------------------- opening
    {"type": "title",
     "title": "GroundTruther",
     "subtitle": "From plugin to measurement instrument",
     "lines": ["A QGIS plugin for seafloor characterization — multibeam acoustics, seafloor",
               "imagery, survey video and now stereo geometry, together on one map.",
               "",
               "Development update · September 2026 · v0.4 · QGIS 4 / Qt 6"]},

    {"type": "split", "title": "Recap — what it is",
     "bullets": [
         (0, "Runs inside QGIS as a dock-based toolset"),
         (0, "Joins four data worlds on one map:"),
         (1, "MBES bathymetry + backscatter (ARA)"),
         (1, "Seafloor imagery (HabCam-style stereo stills)"),
         (1, "Survey video with per-frame GPS"),
         (1, "Stereo geometry — micro-DEMs, roughness, mosaics (new)"),
         (0, "Ground-truth annotation → statistics → KMZ / HTML reports"),
         (0, "Heavy work stays server-side: GRASS backend + a GPU stereo service"),
     ],
     "shot": "GroundTruther docked in QGIS (overview)"},

    {"type": "table", "title": "Where it stands today",
     "rows": [("when", "what landed"),
              ("Apr 2026", "Port to QGIS 4 / Qt 6, Python 3.14, dock UI, video player"),
              ("Jun 2026", "FastGIS authenticated GRASS API · session persistence · stereo "
                           "roughness, micro-DEM 3-D and georeferenced mosaics"),
              ("Sep 2026", "Config hardening · full docs site · the 180° georeference fix · "
                           "the photogrammetric seabed ribbon"),
              ("in parallel", "HRS1508 — a frozen-manifest analysis asking whether stereo "
                              "roughness actually adds to acoustics")],
     "col_widths": [1, 5],
     "note": "Act I — the engineering that made the tool trustworthy · Act II — the new "
             "optical-geometry tools · Act III — the first science they made possible."},

    # ------------------------------------------------------------------ Act I
    {"type": "section", "title": "Act I", "subtitle": "The platform",
     "lines": ["QGIS 4 / Qt 6 · docks & sessions · configuration · internals ·",
               "FastGIS · query builder · video · reports · docs"]},

    {"type": "split", "title": "QGIS 4 / Qt 6 support", "tag": "platform",
     "bullets": [
         (0, "Full port to QGIS 4.0+ / Qt 6 (system Python 3.14)"),
         (0, "Qt 6 API rework: scoped enums, exec_ → exec"),
         (0, "Fixed Qt 6 dock-walk crashes — register docks with the QGIS main window,"),
         (1, "never with the plugin's inner QMainWindow"),
         (0, "OpenGL 3-D viewer made Qt 6-safe (PyOpenGL context)"),
         (0, "QWebEngineView → QTextBrowser (WebEngine absent from QGIS 4 OSGeo4W)"),
         (0, "Wayland: launch QT_QPA_PLATFORM=xcb for floating docks"),
         (0, "qgisMinimumVersion = 4.0"),
     ],
     "shot": "plugin running in QGIS 4 (toolbar + docks)"},

    {"type": "split", "title": "Dock workspace & session persistence", "tag": "GUI",
     "bullets": [
         (0, "Each tool an independent dockable / floatable panel: image browser, video"),
         (1, "player, query builder, report builder, GRASS tools, seafloor roughness"),
         (0, "'Restore default layout' + reliable save/restore of docked layout"),
         (0, "Session persistence: a groundtruther_project file"),
         (0, "Restores image index, zoom, query selection, dock layout, map-sync"),
         (0, "Written on QGIS project save · loaded at start → resume where you left off"),
     ],
     "shot": "custom dock layout + Settings (session file field)"},

    {"type": "split", "title": "Configuration that degrades instead of failing",
     "tag": "robustness",
     "bullets": [
         (0, "The old model was all-or-nothing: one stale path and the plugin would not start"),
         (0, "27 keys, validated per key and severity-aware; pydantic v2 is the schema of record"),
         (0, "Only the two image paths are errors — everything else is a warning when"),
         (1, "set-but-invalid, and silent when unset"),
         (0, "degrade() blanks only the failed keys → a bad value disables its own feature"),
         (0, "Config values treated as untrusted throughout"),
         (0, "Settings dialog covers every key and saves by merging into the file on disk"),
         (1, "(the old fixed template silently deleted whole sections)"),
         (0, "Cloud panels hide themselves when no service is configured"),
     ],
     "shot": "Settings dialog + a validation report in the message log"},

    {"type": "bullets", "title": "Internals — modular, tested, documented", "tag": "internals",
     "bullets": [
         (0, "Thin orchestrator + focused mixins — dockwidget ≈ 240 lines:"),
         (1, "image browser · video browser · video annotation · GRASS · roughness ·"),
         (1, "report · settings · layout · session"),
         (0, "Stateless, testable core (gt/) — no Qt, unit-tested:"),
         (1, "grass_api · image_manager · video_manager · task_runner · mbes_fields ·"),
         (1, "session_state · roughness_client / _geo / _dem / _spectrum / _interpret · ribbon"),
         (0, "415 tests collected (unit / GUI-offscreen / integration) — including tests that"),
         (1, "guard the conventions: import hygiene, settings-docs drift, UI-built-once"),
         (0, "Non-trivial work is planned first in PLANNING/, executed in a dedicated git"),
         (1, "worktree, and closed out with a progress log"),
     ]},

    {"type": "split", "title": "FastGIS — the GRASS backend", "tag": "API",
     "bullets": [
         (0, "Legacy flat, unauthenticated endpoint → api.fastgis.eu"),
         (0, "Authenticated (X-API-Key), built around an environment model (env_id)"),
         (0, "Schema-driven module dialogs — any GRASS module rendered from its interface"),
         (1, "description; async runs polled via a QgsTask"),
         (0, "Detachable QGIS panel: module picker, push output rasters back into QGIS,"),
         (1, "show/hide the computational region"),
         (0, "Same credentials carry the stereo roughness service"),
     ],
     "shot": "GRASS Tools panel + a generated module form"},

    {"type": "split", "title": "MBES query builder & ARA", "tag": "feature",
     "bullets": [
         (0, "Draw a sampling unit (ellipse / rectangle) on the soundings"),
         (0, "ARA scatterplot, 3-D surface, histograms, statistics, in-shape image selection"),
         (0, "Multi-level backscatter: auto-detects every BSWG-2015 level present"),
         (1, "(BS_raw → BS_RL → BS_TL → BS_area → BS_AVG), back-compatible"),
         (0, "Beam-side filtering (Raw / Port / Starboard / Fold) works correctly"),
         (0, "Sampling centre uses the calibrated USBL fix, so marker, sample and"),
         (1, "georeferenced rasters all coincide"),
     ],
     "shot": "query builder: sampling unit + ARA scatterplot"},

    {"type": "split", "title": "Video player", "tag": "feature",
     "bullets": [
         (0, "Frame-accurate player docked in QGIS, driven from the metadata track"),
         (0, "Interlaced-source support: PyAV + yadif — fixes the FFmpeg-8 black-frame failure"),
         (0, "Geo-link: the canvas follows the frame at a fixed, CRS-independent map scale;"),
         (1, "marker and map stay in sync during play"),
         (0, "GPS track persisted as a real GeoJSON layer — restored with the project,"),
         (1, "auto-regenerated on load"),
         (0, "Per-frame bounding-box annotation; loads the MAREANO .log format directly"),
     ],
     "shot": "video dock + GPS track on the map"},

    {"type": "split", "title": "Reporting", "tag": "feature",
     "bullets": [
         (0, "One click sends query-builder products to the report builder: ARA scatterplot,"),
         (1, "3-D surface, histogram, statistics, sampling-unit description, image gallery"),
         (0, "Output to KMZ (geo-referenced balloon) and a templated HTML report (Jinja2):"),
         (1, "card layout, uniform thumbnails, click-to-zoom lightbox, browsable gallery"),
         (0, "PDF export of the composed report"),
     ],
     "shot": "HTML report with gallery + statistics table"},

    {"type": "bullets", "title": "Documentation", "tag": "docs",
     "bullets": [
         (0, "User-facing docs are a MkDocs Material site, published to"),
         (1, "epifanio.github.io/groundtruther on merge"),
         (0, "Installation (Linux / macOS / Windows) · Tools (one page per feature) ·"),
         (1, "Configuration (all 27 keys + the validation model) · Data model · Architecture"),
         (0, "A data-model reference documents every column the plugin reads — including"),
         (1, "which position column is the USBL fix and which is a model."),
         (1, "This is what surfaced the 180° bug in Act II."),
         (0, "mkdocs build --strict in CI catches broken links and orphan pages; a unit test"),
         (1, "fails if a config key is added without its documentation row"),
     ]},

    # ----------------------------------------------------------------- Act II
    {"type": "section", "title": "Act II", "subtitle": "Optical geometry",
     "lines": ["Stereo reconstruction · roughness · georeferencing · mosaics ·",
               "the seabed ribbon"]},

    {"type": "table", "title": "The gap this act is about",
     "lead": "Roughness is measured inside one camera frame. Backscatter is measured over a "
             "footprint metres across. Between them sat a scale range nothing was measuring.",
     "rows": [("product", "wavelengths it supports"),
              ("per-frame stereo micro-DEM", "~3 mm … 1.2 m (one frame's footprint)"),
              ("MBES bathymetry (1 m grid)", "≥ 2–3 m"),
              ("*the photogrammetric ribbon", "*3 mm … 170 m — it spans the whole range")],
     "col_widths": [2, 3],
     "note": "γ₂ is fitted at frame scale, then used to interpret acoustics at metre scale. "
             "Nobody had checked the power law holds across the gap."},

    {"type": "split", "title": "Stereo photogrammetric reconstruction", "tag": "new tool",
     "bullets": [
         (0, "A real-height micro-DEM of the patch under the camera, from the HabCam"),
         (1, "stereo pair itself — independently of the acoustics"),
         (0, "Computed server-side on a GPU (RAFT-Stereo, SGBM fallback). Only the frame's"),
         (1, "Imagename is sent — no image bytes leave the machine"),
         (0, "Float32 heights in millimetres, ~2–5 mm cells, NaN no-data, plus a"),
         (1, "cell-for-cell co-registered orthophoto"),
         (0, "Micro-DEM 3-D tab — the mesh draped with the orthophoto 1:1 (one texel/vertex)"),
         (0, "Edge spikes masked, not hidden: trim border · clip σ · erode"),
         (0, "Background QgsTask, cached per frame: ~14 s first, ~0.5 s after"),
     ],
     "shot": "Micro-DEM 3D tab, photo-textured mesh"},

    {"type": "split", "title": "Seafloor roughness — γ₂, and what to trust", "tag": "new tool",
     "bullets": [
         (0, "Metrics tab: γ₂ · substrate & texture hints · w₂ · rms height · rugosity ·"),
         (1, "anisotropy · altitude · quality · matcher"),
         (0, "Spectrum tab: radial relief power spectrum log-log, fitted power law, fit band"),
         (1, "shaded, γ₂ / w₂ / R² annotated"),
         (0, "γ₂ — the spectral exponent — is the load-bearing output. Robust across matchers"),
         (0, "w₂ and rms are NOT trustworthy in absolute terms: no consistent RAFT-vs-SGBM"),
         (1, "bias, and the median rms (50 mm) sits far above the 3–23 mm literature range"),
         (0, "When quality != ok, every field is null — shown, not faked"),
         (0, "Where the curve peels off the fit at high K, that's the stereo noise floor"),
     ],
     "shot": "Metrics + Spectrum tabs side by side"},

    {"type": "table", "title": "Georeferencing — and a 180° bug worth telling", "tag": "fix",
     "lead": "The bug (#31): the plugin sent the nav's `bearing` column as heading. bearing "
             "points ASTERN — so every georeferenced product was rotated 180°, and a saved "
             "±180 heading offset was the natural way to paper over it.",
     "rows": [("hypothesis", "median residual", "within 30°"),
              ("heading = bearing (old)", "−175.3°", "0 %"),
              ("*heading = bearing + 180", "*+3.9°", "*100 %")],
     "col_widths": [3, 2, 2],
     "bullets": [
         (0, "Proved on the imagery, not by argument: imagery-derived course minus nav course"),
         (1, "over 250 registered frame pairs (table above)"),
         (0, "Side benefit: a single frame's heading is good to ~4° — now a measured number"),
         (0, "Rotation ≠ reflection. Heading offset fixes a rotation; Mirror fixes a handedness"),
         (1, "flip. No rotation can undo a reflection — rasters exported before the fix"),
         (1, "are 180° out and need regenerating"),
     ]},

    {"type": "table", "title": "Georeferenced mosaics", "tag": "new tool",
     "rows": [("mode", "how frames are placed"),
              ("Auto (default)", "Per window, from nav-predicted overlap: piled-up → pixel, "
                                 "well-spread → flat"),
              ("Flat", "Navigation alone (position, heading, flat-seabed scale). Fast"),
              ("Ortho", "Relief-corrected per-frame orthophoto, then nav placement. Slowest"),
              ("Pixel", "Registered by image content, georeferenced through the reference "
                        "frame's nav")],
     "col_widths": [1, 4],
     "bullets": [
         (0, "Illumination correction (flat-fields the strobe vignette) and gain compensation"),
         (1, "on by default — this is what makes a mosaic look continuous"),
         (0, "Presets: Browse (3 mm, fast) · Publication (ortho, 0.8 mm, lanczos, 8192 px, RGBA)"),
         (0, "Honest failure mode: featureless mud cannot be content-registered by any method —"),
         (1, "'only 0/10 pairs registered — low texture, mosaic is nav-placed'"),
     ]},

    {"type": "bullets", "title": "The photogrammetric seabed ribbon", "tag": "new",
     "bullets": [
         (0, "Composite a few hundred per-frame micro-DEMs along ONE HabCam line into ~170 m"),
         (1, "of millimetre-resolution georeferenced seabed. A script (scripts/build_ribbon.py),"),
         (1, "not yet a dock — look at a ribbon first"),
         (0, "Choose the strip by TEXTURE, never by relief. On this survey they are"),
         (1, "uncorrelated: two runs with ~4 m of relief (3.75 and 4.04 m) linked on 0 % of"),
         (1, "sampled pairs — featureless mud — while the strip with the MOST relief in the"),
         (1, "survey (5.80 m) managed only 22 median inliers. Picking by relief would have"),
         (1, "chosen one of the dead ones"),
         (0, "ORB + RANSAC needs help here: no preprocessing (CLAHE and flat-fielding both"),
         (1, "LOWERED inliers), a loose Lowe ratio 0.95, detection masked to the overlapping"),
         (1, "band, and a displacement prefilter + physical gate — without the gate RANSAC"),
         (1, "confidently returns 15–25-inlier consensuses on completely wrong transforms"),
         (0, "Pixels where they work, navigation everywhere else: the USBL is"),
         (1, "piecewise-constant (median step 92 mm against a true 491 mm), so nav-placed"),
         (1, "frames stack in clumps of ~6 and jump. The chain integrates the links, bridges"),
         (1, "gaps with nav, then rubber-sheets back onto it — absolute placement from the"),
         (1, "USBL, relative geometry from the pixels"),
     ]},

    {"type": "table", "title": "The ribbon — measured", "tag": "results",
     "lead": "Strip 6663–6958: 296 frames, 172 m, EPSG:32619, track-aligned at 273.1°, "
             "1256 × 48 339 cells at 3 mm.",
     "rows": [("link rate", "89.8 % (265 / 295 pairs), median 309 inliers"),
              ("longest unbroken registered run", "119 pairs (mean 48)"),
              ("quality != ok", "2.0 % (6 frames, all insufficient_coverage)"),
              ("service altitude vs Altimeter", "median 37 mm"),
              ("*seam error, pixel-linked", "*62.0 mm → 13.7 mm after levelling"),
              ("seam error, nav-bridged", "235.5 mm → 119.3 mm — 8.7× worse")],
     "col_widths": [2, 3],
     "header": False,
     "bullets": [
         (0, "The vertical error was the depth sensor, not the stereo. V_Depth is quantized to"),
         (1, "10 mm and steps with σ = 82 mm — essentially the whole per-frame scatter."),
         (1, "Levelling solves per-frame offsets from overlap medians (robust IRLS, lag-1 and"),
         (1, "lag-2 pairs for loop closure), keeping the datum with the vehicle"),
         (0, "The trade, stated: seams 4.5× better, but the 1 m profile agrees LESS with the"),
         (1, "MBES (0.147 → 0.185 m). Some large corrections over-fit bad overlaps"),
         (0, "Independent checks: chain azimuth 273.1° vs nav 273.2°; focal length calibrated"),
         (1, "against nav displacement 2507 px vs nominal 2480.28 — ratio 1.011"),
     ]},

    {"type": "bullets", "title": "Does the power law cross the gap?",
     "tag": "suggestive, not settled",
     "bullets": [
         (0, "The per-frame fit is 2-D and isotropic; a ribbon profile measures the 1-D"),
         (1, "spectrum. Integrating out the cross-track wavenumber gives a closed form with"),
         (1, "NO free parameter — so γ₁ = γ₂ − 1 and the amplitude are both predicted"),
         (0, "Measured in the 1.2–3 m band: 9.45× (+9.8 dB) more power than the per-frame law"),
         (1, "predicts, fitted γ₁ = 2.29 ± 1.56 against a predicted 1.97"),
         (0, "The slope is unconstrained. ±1.56 spans every plausible exponent — the band is a"),
         (1, "third of a decade, all a 145 m ribbon can offer"),
         (0, "The amplitude excess is only 1.7× above the ribbon's own noise floor: a per-frame"),
         (1, "vertical error held across each frame and changing every 0.49 m puts a nearly"),
         (1, "FLAT spectrum across exactly this band (14× at the robust σ = 21 mm)"),
         (0, "What would settle it is now a number: per-frame vertical placement must reach"),
         (1, "≈ 6 mm, from 60 mm — a vertical bundle adjustment"),
         (0, "Supporting: MBES along-track γ₁ = 3.60 ± 0.16 (γ₂ ≈ 4.60) over 2–40 m, far"),
         (1, "steeper than the per-frame 2.97, with the ribbon's 3.29 BETWEEN them — the shape"),
         (1, "of a gradual break, at an error bar that makes it a remark"),
         (0, "And the ribbon does not beat the altimeter on vertical accuracy (0.185 m vs"),
         (1, "0.115 m median |dz| against the MBES). It adds texture, not depth"),
     ]},

    # ---------------------------------------------------------------- Act III
    {"type": "section", "title": "Act III", "subtitle": "The science it made possible",
     "lines": ["HRS1508 — does stereo roughness add anything to acoustics?"]},

    {"type": "table", "title": "HRS1508 — the question and the setup",
     "lead": "Does optical roughness carry substrate information that backscatter does not? "
             "A binary problem — Substrate A vs Substrate E — on the HRS1508 survey.",
     "rows": [("stream", "what went in"),
              ("MBES beams", "29 027 174 beams, all 512 formed beams/ping, full angular range"),
              ("cells", "25 m grid → 2318 ARA cells (median 9846 beams/cell, 6 angle bins)"),
              ("optical nav", "123 394 HabCam frames, positioned by calibrated USBL"),
              ("stereo roughness", "12 563 per-frame records → γ₂, rugosity, anisotropy"),
              ("*analysis set", "*217 cells with a majority single-substrate label and ≥ 3 "
                                "roughness frames")],
     "col_widths": [1, 4],
     "bullets": [
         (0, "7 ARA descriptors (6 × 10° angle bins + slope), per-line normalised so the"),
         (1, "unknown source level cancels, plus 3 roughness features"),
         (0, "Random forest, 5-fold spatially blocked CV on 200 m blocks (33 blocks); folds"),
         (1, "frozen once and reused, so every comparison is genuinely paired"),
     ]},

    {"type": "table", "title": "The result", "tag": "headline",
     "rows": [("model", "accuracy", "gain vs ARA", "95 % CI"),
              ("ARA only (baseline)", "0.659", "—", "—"),
              ("ARA + γ₂", "0.691", "+0.032", "−0.005 … 0.072"),
              ("ARA + γ₂ + rugosity", "0.714", "+0.055", "0.005 … 0.108"),
              ("*ARA + all roughness", "*0.756", "*+0.097", "*0.039 … 0.155"),
              ("roughness only", "0.756", "+0.097", "0.014 … 0.183")],
     "col_widths": [3, 1, 1, 2],
     "bullets": [
         (0, "Block-permutation p < 0.001; macro-F₁ 0.597 → 0.715; minority-class (Substrate E)"),
         (1, "recall 0.43 → 0.60 — the gain is where it matters"),
         (0, "γ₂ ranks FIRST of all ten features (importance 0.215, above every backscatter"),
         (1, "bin — the best of those is 0.175)"),
         (0, "Modality ladder: backscatter alone 0.70 · + bathymetric slope correction 0.66 ·"),
         (1, "+ γ₂ 0.69 · + all roughness 0.76"),
         (0, "Holds across scale: at a 15 m cell the same ladder runs 0.74 → 0.83"),
         (0, "Two-tier map: 881 of 2318 cells (38 %) have both modalities; adding roughness"),
         (1, "flips 14.5 % of the classified swath"),
     ]},

    {"type": "bullets", "title": "Why you can believe it — and what it does not say",
     "bullets": [
         (0, "One run, one manifest. Two earlier fusion results (0.769→0.864 on 221 cells,"),
         (1, "0.761→0.820 on 987 cells) differed in BOTH the beam table and the cell subset —"),
         (1, "invisible to the author, obvious to a referee. The fix was not to pick a number,"),
         (1, "it was to make two impossible: one frozen manifest.yml, one library, one beam"),
         (1, "table, one fold assignment, every input hashed into a lock file"),
         (0, "Calibration stress test: inject per-line source-level error up to 5 dB (against a"),
         (1, "MEASURED per-line spread of 4.59 dB over 17 lines). The normalised pipeline moves"),
         (1, "0.000; without per-line normalisation it drifts 0.018; strip the shape too and the"),
         (1, "level-only classifier falls to 0.58 and drifts 0.028. The result does not depend"),
         (1, "on absolute calibration"),
         (0, "The image classifier survives honest CV: 0.942 stratified → 0.939 on 200 m"),
         (1, "spatial blocks. Optimism 0.002 — it was not leaking geography"),
         (0, "LIMITS, stated not buried — the stereo coverage gate is NOT label-neutral:"),
         (1, "2.7 % of Substrate A cells rejected against 12.9 % of Substrate E (Fisher OR 5.3,"),
         (1, "p ≈ 2×10⁻²⁵). That is a result about turbidity over fine sediment"),
         (0, "w₂ and rms height are never model inputs — amplitude is not recoverable from"),
         (1, "this stereo; and fit_r2 / valid_fraction / altitude_mm / matcher are absent from"),
         (1, "the committed CSVs, so spectrum quality cannot yet be filtered on"),
     ]},

    # ---------------------------------------------------------------- closing
    {"type": "bullets", "title": "Is this a unique tool?",
     "bullets": [
         (0, "Yes — and the differentiator has shifted"),
         (0, "It started as an INTEGRATION argument: most workflows are siloed — acoustics in"),
         (1, "one suite, image annotation in another, video review in a third, GIS somewhere"),
         (1, "else. GroundTruther puts them on one QGIS map, free and open source"),
         (0, "It is now also a MEASUREMENT argument: no other GIS-native tool turns the"),
         (1, "survey's own stereo imagery into metric seabed geometry — micro-DEMs, spectral"),
         (1, "roughness, georeferenced mosaics, a millimetre ribbon — and puts it beside the"),
         (1, "acoustics in the same project"),
         (0, "Heavy work stays server-side (FastGIS for GRASS, a GPU service for stereo);"),
         (1, "the plugin stays a thin, scriptable client"),
         (0, "Open formats throughout (Parquet, GeoJSON, GeoTIFF, KMZ, CSV/.log)"),
         (0, "Not a replacement for specialist acoustic suites — a connective, ground-truthing"),
         (1, "layer, which now measures something of its own"),
     ]},

    {"type": "two_text", "title": "What's next?",
     "left_head": "Committed, with a number attached",
     "left": [(0, "Vertical bundle adjustment for the ribbon: per-frame placement 60 mm → ≈ 6 mm. "
                  "That single factor of ten converts the scale-gap result from suggestive to "
                  "publishable"),
              (0, "Persist the roughness QC fields (fit_r2, valid_fraction, altitude_mm, matcher) "
                  "so spectrum quality can be reported and filtered on"),
              (0, "Resolve mount handedness against a target of known handedness — the one link "
                  "in the geometry chain still untested")],
     "right_head": "Open",
     "right": [(0, "ML-assisted annotation (review instead of draw)"),
               (0, "A ribbon dock in QGIS, once people have used a ribbon in anger"),
               (0, "Multi-line ribbons and cross-line closure"),
               (0, "Reproducible 'analysis as a saved session'"),
               (0, "Multi-user / shared cloud sessions; signed report bundles"),
               (0, "More survey-log adapters; CI toward a turnkey installer")]},

    {"type": "two_text", "title": "Would you use it?",
     "left_head": "Who it's for",
     "left": [(0, "Benthic ecologists & seabed-mapping teams doing ground-truthing"),
              (0, "Anyone who wants acoustics, imagery and video on the same map without "
                  "stitching five tools together"),
              (0, "New: anyone who needs quantitative seabed geometry from imagery they "
                  "already have — without building a photogrammetry pipeline")],
     "right_head": "Honest take",
     "right": [(0, "Purely acoustic processing → keep your specialist suite"),
               (0, "Sub-metre optical geometry at survey scale with full bundle adjustment → "
                   "this is not a photogrammetry suite (yet)"),
               (0, "Interpretation + ground-truth + reporting across data types, inside GIS, "
                   "open and scriptable → yes, and the optical side now measures as well as "
                   "displays")]},

    {"type": "bullets", "title": "Need help setting it up?",
     "bullets": [
         (0, "Requirements: QGIS 4.0+ (Qt 6), the bundled .venv, a FastGIS API key for GRASS"),
         (1, "and roughness (or a direct URL if you run the GPU service yourself)"),
         (0, "Install: symlink the repo into your QGIS profile, enable, point Settings at your"),
         (1, "data — invalid keys now disable only their own feature"),
         (0, "Try it: the Zenodo 'groundtruther test dataset' (CC-BY-4.0)"),
         (0, "Repo & issues: github.com/epifanio/groundtruther"),
         (0, "Docs: epifanio.github.io/groundtruther · dev notes in docs/grass_fastgis.md"),
         (1, "and docs/photogrammetric_ribbon.md"),
         (0, "Analysis workflow: PDAL_MBIO/paper — frozen manifest, notebooks 00→09"),
         (0, "Happy to walk you through install, config, or your own dataset."),
     ]},

    {"type": "title", "title": "Thank you",
     "subtitle": "GroundTruther · v0.4 · QGIS 4 / Qt 6",
     "lines": ["MBES · imagery · video · stereo geometry · roughness · mosaics · ribbon · report",
               "github.com/epifanio/groundtruther · epifanio.github.io/groundtruther"]},
]


def build():
    prs = Presentation()
    prs.slide_width = WIDTH
    prs.slide_height = HEIGHT
    blank = prs.slide_layouts[6]

    for s in SLIDES:
        slide = prs.slides.add_slide(blank)
        t = s["type"]

        if t == "title":
            box = slide.shapes.add_textbox(Inches(1.0), Inches(2.3), Inches(11.3), Inches(3.0))
            tf = box.text_frame; tf.word_wrap = True
            _set(tf.paragraphs[0], s["title"], 46, color=ACCENT, bold=True, align=PP_ALIGN.CENTER)
            p = tf.add_paragraph(); _set(p, s["subtitle"], 24, color=SEA, bold=True, align=PP_ALIGN.CENTER)
            p.space_before = Pt(8)
            for line in s.get("lines", []):
                pl = tf.add_paragraph()
                _set(pl, line, 15, color=MUTED, align=PP_ALIGN.CENTER)
            continue

        if t == "section":
            section_divider(slide, s["title"], s["subtitle"], s.get("lines", []))
            continue

        title_bar(slide, s["title"], s.get("tag"))

        if t == "bullets":
            n = len(s["bullets"])
            if n <= 12:
                size0, size1 = 18, 15
            elif n <= 16:
                size0, size1 = 15, 13
            else:
                size0, size1 = 13, 11.5
            box = slide.shapes.add_textbox(Inches(0.7), Inches(1.6), Inches(12.0), Inches(5.4))
            tf = box.text_frame; tf.word_wrap = True
            add_bullets(tf, s["bullets"], size0=size0, size1=size1)

        elif t == "split":
            tbox = slide.shapes.add_textbox(Inches(0.55), Inches(1.6), Inches(6.4), Inches(5.4))
            tf = tbox.text_frame; tf.word_wrap = True
            add_bullets(tf, s["bullets"], size0=16, size1=13)
            shot_placeholder(slide, Inches(7.2), Inches(1.7), Inches(5.6), Inches(5.0), s["shot"])

        elif t == "two_text":
            lb = slide.shapes.add_textbox(Inches(0.6), Inches(1.7), Inches(5.9), Inches(5.0))
            ltf = lb.text_frame; ltf.word_wrap = True
            _set(ltf.paragraphs[0], s["left_head"], 18, color=SEA, bold=True)
            for lvl, txt in s["left"]:
                p = ltf.add_paragraph(); _set(p, "•  " + txt, 14); p.space_after = Pt(6)
            rb = slide.shapes.add_textbox(Inches(6.9), Inches(1.7), Inches(5.9), Inches(5.0))
            rtf = rb.text_frame; rtf.word_wrap = True
            _set(rtf.paragraphs[0], s["right_head"], 18, color=SEA, bold=True)
            for lvl, txt in s["right"]:
                p = rtf.add_paragraph(); _set(p, "•  " + txt, 14); p.space_after = Pt(6)

        elif t == "table":
            top = Inches(1.5)
            if s.get("lead"):
                lb = slide.shapes.add_textbox(Inches(0.7), top, Inches(12.0), Inches(0.8))
                ltf = lb.text_frame; ltf.word_wrap = True
                _set(ltf.paragraphs[0], s["lead"], 14, color=MUTED)
                top = top + Inches(0.75)
            tbl = add_table(slide, s["rows"], Inches(0.7), top, Inches(11.9),
                            header=s.get("header", True), col_widths=s.get("col_widths"))
            top = top + tbl.height + Inches(0.22)
            if s.get("bullets"):
                bb = slide.shapes.add_textbox(Inches(0.7), top, Inches(12.0),
                                              max(Inches(0.8), Inches(7.1) - top))
                btf = bb.text_frame; btf.word_wrap = True
                add_bullets(btf, s["bullets"], size0=14, size1=12)
            if s.get("note"):
                nb = slide.shapes.add_textbox(Inches(0.7), top, Inches(12.0), Inches(1.0))
                ntf = nb.text_frame; ntf.word_wrap = True
                _set(ntf.paragraphs[0], s["note"], 14, color=SEA, bold=True)

    out = Path(__file__).resolve().parent / "slides_groundtruther_update_2026.pptx"
    prs.save(str(out))
    print("wrote", out, f"({len(prs.slides._sldIdLst)} slides)")


if __name__ == "__main__":
    build()
