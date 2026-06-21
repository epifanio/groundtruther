#!/usr/bin/env python
"""Generate the GroundTruther 2026 update deck as an editable .pptx.

Mirrors docs/slides_groundtruther_update_2026.html. Run:
    .venv/bin/python docs/build_pptx.py
Output: docs/slides_groundtruther_update_2026.pptx
"""
from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

INK     = RGBColor(0x14, 0x30, 0x3D)
ACCENT  = RGBColor(0x1A, 0x52, 0x76)
ACCENT2 = RGBColor(0x2E, 0x86, 0xC1)
SEA     = RGBColor(0x0E, 0x6E, 0x6E)
MUTED   = RGBColor(0x5B, 0x6B, 0x76)
SHOT_BG = RGBColor(0xEA, 0xF2, 0xF8)

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


# --------------------------------------------------------------------------- #
# Slide content (mirrors the reveal.js deck)
# --------------------------------------------------------------------------- #
SLIDES = [
    {"type": "title",
     "title": "GroundTruther",
     "subtitle": "What changed since the paper",
     "lines": ["A QGIS plugin for seafloor characterization — multibeam acoustics,",
               "seafloor imagery & survey video, together on one map.",
               "",
               "Development update · 2026 · v0.4 · QGIS 4 / Qt 6"]},

    {"type": "split", "title": "Recap — what it is",
     "bullets": [
         (0, "Runs inside QGIS as a dock-based toolset"),
         (0, "Joins three data worlds on one map:"),
         (1, "MBES bathymetry + backscatter (ARA)"),
         (1, "Seafloor imagery (HabCam-style stills)"),
         (1, "Survey video with per-frame GPS"),
         (0, "Ground-truth annotation → statistics → KMZ / HTML reports"),
         (0, "Remote GRASS GIS service for geoprocessing"),
     ],
     "shot": "GroundTruther docked in QGIS (overview)"},

    {"type": "bullets", "title": "Timeline",
     "bullets": [
         (0, "Paper release → first public, working tool"),
         (0, "This winter (≈ March 2026) → major modernization cycle begins"),
         (0, "Goals: QGIS 4 / Qt 6, a maintainable codebase, video support,"),
         (1, "and a modern authenticated GRASS API"),
         (0, "This deck = the highlights: platform · UI/UX · install · refactor · API · features · fixes"),
     ]},

    {"type": "split", "title": "QGIS 4 / Qt 6 support", "tag": "platform",
     "bullets": [
         (0, "Full port to QGIS 4.0+ / Qt 6 (system Python 3.14)"),
         (0, "Qt 6 API rework: scoped enums, exec_ → exec"),
         (0, "Fixed Qt 6 dock-walk crashes (register docks with main window)"),
         (0, "OpenGL 3-D viewer made Qt 6-safe (PyOpenGL context)"),
         (0, "Wayland: launch QT_QPA_PLATFORM=xcb for floating docks"),
         (0, "qgisMinimumVersion = 4.0"),
     ],
     "shot": "plugin running in QGIS 4 (toolbar + docks)"},

    {"type": "split", "title": "New UI layout & project management", "tag": "GUI",
     "bullets": [
         (0, "Each tool an independent dockable / floatable panel"),
         (0, "'Restore default layout' + reliable save/restore of docked layout"),
         (0, "Session persistence (new): a groundtruther_project file"),
         (0, "Restores image index, zoom, query selection, dock layout, map-sync"),
         (0, "Written on QGIS project save · loaded at start → resume where you left off"),
     ],
     "shot": "custom dock layout + Settings (session file field)"},

    {"type": "split", "title": "UI settings & configuration", "tag": "GUI",
     "bullets": [
         (0, "Single YAML config, validated by a pydantic v2 model"),
         (0, "Clear errors instead of obscure runtime failures"),
         (0, "Dialog for image / MBES / video / export / GRASS paths & keys"),
         (0, "CRS-aware: zoom-to uses map scale (1:N) — same in metric and geographic CRSs"),
     ],
     "shot": "Settings dialog"},

    {"type": "bullets", "title": "Streamlined installation", "tag": "setup",
     "bullets": [
         (0, "QGIS 4 runs on system Python (PEP-668, no pip) — handled cleanly:"),
         (1, "Plugin deps live in a .venv beside the source"),
         (1, "_bootstrap_venv() appends it to sys.path at load"),
         (0, "Install = symlink the repo into the QGIS profile + enable"),
         (0, "Fixed missing runtime deps & venv bootstrap → one-step setup"),
         (0, "Video decode via PyAV (bundled FFmpeg) — no system-codec hunt"),
     ]},

    {"type": "bullets", "title": "Code refactoring — modular & maintainable", "tag": "internals",
     "bullets": [
         (0, "Thin orchestrator + focused mixins — dockwidget ≈ 240 lines:"),
         (1, "image browser · video browser · video annotation · GRASS · report · settings · layout · session"),
         (0, "Stateless, testable core (gt/) — no Qt, unit-tested:"),
         (1, "grass_api · image_manager · video_manager · task_runner"),
         (1, "NEW: mbes_fields · video_reader · session_state"),
         (0, "A growing pytest suite (unit / GUI-offscreen / integration)"),
     ]},

    {"type": "split", "title": "New FastGIS API (GRASS backend)", "tag": "backend",
     "bullets": [
         (0, "Legacy flat, unauthenticated endpoint → api.fastgis.eu"),
         (0, "Authenticated (X-API-Key), built on an environment model (env_id)"),
         (0, "Schema-driven module dialogs — any GRASS module; async via QgsTask"),
         (0, "GRASS Tools is now an undockable QGIS panel:"),
         (1, "module picker · push rasters back to QGIS · show/hide computational region"),
     ],
     "shot": "GRASS Tools panel + a schema-driven module dialog"},

    {"type": "split", "title": "Feature — MBES query builder", "tag": "new",
     "bullets": [
         (0, "Draw a sampling unit (ellipse / rectangle) on the soundings"),
         (0, "ARA scatterplot · 3-D surface · histograms · stats · in-shape images"),
         (0, "Multi-level backscatter (new): auto-detects every BSWG-2015 level"),
         (1, "raw → RL → TL → area → AVG, back-compatible with the legacy format"),
         (0, "Beam-side filtering (Raw / Port / Starboard / Fold) fixed"),
     ],
     "shot": "query builder: sampling ellipse + ARA scatterplot / 3-D"},

    {"type": "split", "title": "Feature — video player", "tag": "new",
     "bullets": [
         (0, "Frame-accurate player docked in QGIS, driven from the metadata track"),
         (0, "Interlaced support (new): PyAV + yadif — fixes FFmpeg-8 black frames"),
         (0, "Geo-link to map: canvas follows the frame at a fixed, CRS-independent scale"),
         (0, "GPS track as a persistent GeoJSON layer — no scratch warning, auto-regenerated"),
     ],
     "shot": "video player docked + geo-linked map (track + marker)"},

    {"type": "split", "title": "Video & image annotation", "tag": "new",
     "bullets": [
         (0, "Image annotation: bounding boxes + species labels on stills;"),
         (1, "confidence-threshold filter; detector output overlay"),
         (0, "Video annotation: per-frame boxes, single-click draw → label → save;"),
         (1, "'Add new box' pauses on draw and releases on resume"),
         (0, "Shared label pool; edits persisted to CSV (frame_index ↔ bboxes / species / conf.)"),
         (0, "Annotations stay geolinked — every box ties back to a map position"),
     ],
     "shot": "annotation editor: a frame/image with labelled boxes"},

    {"type": "split", "title": "Feature — reporting", "tag": "new",
     "bullets": [
         (0, "One click sends query products to the report builder:"),
         (1, "ARA · 3-D · histogram · stats · sampling unit · image gallery"),
         (0, "Output to KMZ (geo-balloon) and a modern templated HTML report (Jinja2):"),
         (1, "card layout, uniform thumbnails, click-to-zoom lightbox"),
         (1, "browsable gallery of the in-sample seafloor images"),
         (0, "Stats as a real HTML table · title + location summary · PDF export"),
     ],
     "shot": "generated HTML report (gallery + lightbox + stats table)"},

    {"type": "bullets", "title": "Bug-fix roundup (selected)",
     "bullets": [
         (0, "3-D WGL viewer blank on Qt 6 → fixed (PyOpenGL context)"),
         (0, "ARA beam radios (L / R / Fold) had no effect → fixed"),
         (0, "KMZ save crashed on un-generated products → guarded + de-duplicated"),
         (0, "Docks / video player came back undocked → restoreState"),
         (0, "Geo-link marker moved but map didn't follow → throttle fix"),
         (0, "Zoom was projection-dependent → map scale (1:N), CRS-independent"),
         (0, "Interlaced video → black frames → PyAV / yadif"),
         (0, "Stale / broken track reference on reload → auto-regenerate"),
     ]},

    {"type": "split", "title": "Use case — HabCam", "tag": "imagery",
     "bullets": [
         (0, "Optical + acoustic ground-truthing of benthic habitat"),
         (0, "Browse tens of thousands of stills with metadata, linked to the MBES surface"),
         (0, "Sampling unit → backscatter angular response and the images inside it → annotate → report"),
         (0, "Reference dataset: HabCam test data on Zenodo (CC-BY-4.0)"),
     ],
     "shot": "HabCam still + metadata panel + map context"},

    {"type": "split", "title": "Use case — MAREANO", "tag": "video",
     "bullets": [
         (0, "Norwegian seabed-mapping programme — towed-camera video transects"),
         (0, "Loads the MAREANO survey .log format directly (DDM → decimal degrees)"),
         (0, "Video geo-linked to the map; GPS track drawn as a persistent layer"),
         (0, "Per-frame species / substrate annotation alongside the acoustics"),
     ],
     "shot": "MAREANO video transect + track on the canvas"},

    {"type": "bullets", "title": "Is this a unique tool?",
     "bullets": [
         (0, "Yes — the integration is the differentiator."),
         (0, "Most workflows are siloed: acoustics, image annotation, video review, GIS — all separate"),
         (0, "GroundTruther puts MBES + imagery + video + annotation + GRASS + reporting on one QGIS map, free & open source"),
         (0, "Cloud GRASS backend keeps heavy geoprocessing server-side"),
         (0, "Open formats throughout (Parquet · GeoJSON · KMZ · CSV / .log)"),
         (0, "Not a replacement for specialist acoustic suites — a connective, ground-truthing layer"),
     ]},

    {"type": "bullets", "title": "What's next?",
     "bullets": [
         (0, "ML-assisted annotation — pre-populate boxes; review instead of draw"),
         (0, "More backscatter analytics & calibration; multi-file mosaics"),
         (0, "Scale to very large soundings (10⁷+ rows) — Arrow-native, optional GPU"),
         (0, "Richer GRASS recipe presets; 'analysis as a saved session'"),
         (0, "Multi-user / shared cloud sessions; signed report bundles"),
         (0, "More survey-log adapters out of the box; turnkey installer + CI"),
     ]},

    {"type": "two_text", "title": "Would you use it?",
     "left_head": "Who it's for",
     "left": [
         (0, "Benthic ecologists & seabed-mapping teams doing ground-truthing"),
         (0, "Anyone who wants acoustics, imagery & video on the same map"),
     ],
     "right_head": "Honest take",
     "right": [
         (0, "Purely acoustic processing → keep your specialist suite"),
         (0, "Interpretation + ground-truth + reporting across data types, in GIS, open & scriptable → strong fit"),
     ]},

    {"type": "bullets", "title": "Need help setting it up?",
     "bullets": [
         (0, "Requirements: QGIS 4.0+ (Qt 6), the bundled .venv, a FastGIS API key for GRASS"),
         (0, "Install: symlink the repo into your QGIS profile, enable, point Settings at your data"),
         (0, "Try it: the Zenodo HabCam dataset (and a MAREANO .log + video)"),
         (0, "Repo & issues: github.com/epifanio/groundtruther"),
         (0, "Docs: GRASS / FastGIS integration guide in docs/"),
         (0, "Happy to walk you through install, config, or your own dataset."),
     ]},

    {"type": "title",
     "title": "Thank you",
     "subtitle": "GroundTruther · v0.4 · QGIS 4 / Qt 6",
     "lines": ["MBES · imagery · video · GRASS · ground-truth · report",
               "github.com/epifanio/groundtruther"]},
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

        title_bar(slide, s["title"], s.get("tag"))

        if t == "bullets":
            box = slide.shapes.add_textbox(Inches(0.7), Inches(1.6), Inches(12.0), Inches(5.4))
            tf = box.text_frame; tf.word_wrap = True
            add_bullets(tf, s["bullets"], size0=18, size1=15)

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
                p = ltf.add_paragraph(); _set(p, "•  " + txt, 15); p.space_after = Pt(6)
            rb = slide.shapes.add_textbox(Inches(6.9), Inches(1.7), Inches(5.9), Inches(5.0))
            rtf = rb.text_frame; rtf.word_wrap = True
            _set(rtf.paragraphs[0], s["right_head"], 18, color=SEA, bold=True)
            for lvl, txt in s["right"]:
                p = rtf.add_paragraph(); _set(p, "•  " + txt, 15); p.space_after = Pt(6)

    out = Path(__file__).resolve().parent / "slides_groundtruther_update_2026.pptx"
    prs.save(str(out))
    print("wrote", out, f"({len(prs.slides._sldIdLst)} slides)")


if __name__ == "__main__":
    build()
