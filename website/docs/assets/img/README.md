# Screenshots

Each tool page references one or more images in this folder. Until real captures
are added, every figure points at `placeholder.svg`.

To add a real screenshot:

1. Capture the tool in QGIS (PNG, ideally ~1600px wide).
2. Save it here with the filename the page expects, e.g.:
   - `image-browser-1.png`, `image-browser-2.png`
   - `video-player-1.png`
   - `annotation-image-1.png`, `annotation-video-1.png`
   - `query-builder-1.png`
   - `report-builder-1.png`
   - `grass-settings-1.png`, `grass-module-1.png`, `grass-region-1.png`
3. In the corresponding `docs/tools/*.md`, swap the `placeholder.svg` `src` for your
   file name (the `<figure>` blocks are marked with a `TODO` comment).

PNG/JPG/WebP/SVG are all served as-is by MkDocs.
