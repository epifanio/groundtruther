# Report Builder

Assemble the acoustic and optical evidence for a site into a shareable,
quantitative report.

<figure markdown>
  <!-- TODO: replace src with assets/img/report-builder-1.png -->
  ![Report Builder](../assets/img/placeholder.svg){ width="900" }
  <figcaption>Composing a report that links imagery, annotations and acoustic queries.</figcaption>
</figure>

## What it does

- Collects the current context — selected imagery/annotations, acoustic query
  results and plots, and the computational region — into a structured report.
- Renders output with **Jinja2** templates and **matplotlib** figures.
- **Exports** to your chosen output folder, including KML/KMZ so locations and
  findings can be reviewed in any earth browser.

## How to use

1. Build up your interpretation with the [Image Browser](image-browser.md),
   [Annotation](annotation.md) and [Acoustic Query Builder](query-builder.md).
2. Open the **Report Builder** dock and compose/preview the report.
3. **Export** — files are written to the `kmldir` folder from Settings.

## Inputs (Settings → Export)

| Setting | What it is |
|---|---|
| `kmldir` | Output folder for generated reports / KMZ files. |
| `filemanager` | *Optional* external file-manager executable used to open the export folder. |

!!! tip
    Keep the export folder under version control or a shared drive so reports for
    a survey stay together and reproducible.
