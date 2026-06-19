# GroundTruther documentation site

Reference documentation for GroundTruther, built with
[MkDocs Material](https://squidfunk.github.io/mkdocs-material/).

## Build / preview locally

```bash
# from the repo root, using the project venv (already has mkdocs-material),
# or: pip install -r website/requirements-docs.txt
cd website
mkdocs serve            # live preview at http://127.0.0.1:8000
mkdocs build --strict   # static site into website/site/
```

## Publish to GitHub Pages

Automatic: the workflow `.github/workflows/docs.yml` builds and deploys to the
`gh-pages` branch on every push to `master` that touches `website/`. Enable
GitHub Pages for the repo with **Source = `gh-pages` branch** (Settings → Pages).
The site is served at <https://epifanio.github.io/groundtruther/>.

Manual one-off deploy:

```bash
cd website
mkdocs gh-deploy --force
```

## Structure

```
website/
  mkdocs.yml              # site config, theme, nav
  requirements-docs.txt   # docs toolchain
  docs/
    index.md              # overview + paper citation
    installation/         # index + linux / macos / windows (QGIS install types)
    tools/                # one page per tool (with screenshot slots)
    architecture.md       # Mermaid component & module diagrams
    assets/img/           # screenshots (see assets/img/README.md)
```

## Adding screenshots

Every tool page has `<figure>` blocks pointing at `assets/img/placeholder.svg`
with a `TODO` comment naming the expected file. Drop your PNGs in
`docs/assets/img/` and swap the `src`. See `docs/assets/img/README.md`.
