# GroundTruther

**A QGIS plugin for seafloor characterization** — explore and analyse multibeam
echo-sounder (MBES) bathymetry and backscatter *together* with georeferenced
seafloor imagery and survey video, inside a single, map-centric workspace.

The seafloor is observed through very different instruments — acoustics paint
broad, continuous coverage; cameras give sparse but unambiguous ground truth.
GroundTruther brings them onto the same canvas so you can move fluidly between
*"what does the acoustic signal say here?"* and *"what does the seabed actually
look like here?"* — and build defensible, reproducible interpretations that link
**morphology, backscatter, and observed biota**.

<figure markdown>
  <!-- TODO: replace with a hero screenshot of the full plugin in QGIS -->
  ![GroundTruther in QGIS](assets/img/placeholder.svg){ width="900" }
  <figcaption>GroundTruther running inside QGIS 4.</figcaption>
</figure>

## What you can do

- **Browse thousands of geotagged seafloor images** spatially — click the map to
  jump to the nearest image, or scrub an index and watch the map follow.
- **Play survey video geo-linked to the map**, with the canvas panning to the
  current frame's GPS position.
- **Annotate** images and video frames with labelled bounding boxes and
  confidence scores.
- **Query MBES products acoustically** — pull backscatter / bathymetric-derivative
  values under points or sampling shapes via a remote GRASS GIS service.
- **Run any GRASS module on demand** — the toolbox builds a dialog from the
  module's own interface description and returns results straight to QGIS.
- **Generate quantitative reports** that tie the acoustic and optical evidence
  together.

## Why it exists

GroundTruther provides an efficient means of understanding the relationships
between morphology, backscatter, and the observed biota — and thus between the
physical and ecological elements of the seafloor. It offers new ways to interpret
remotely sensed MBES information, supports the development of spatial distribution
models, and helps improve the ground-truth databases used to build geophysical
models that connect acoustic backscatter to the seabed's natural properties.

## Cite the paper

GroundTruther is described in a peer-reviewed article in *Environmental Modelling
& Software*. If you use it in your research, please cite:

> Di Stefano, M. *GroundTruther: A QGIS plugin for seafloor characterization.*
> Environmental Modelling & Software.
> <https://www.sciencedirect.com/science/article/pii/S1364815223002475>

!!! tip "Get started"
    Head to **[Installation](installation/index.md)** to set up QGIS and the
    plugin, then explore the **[Tools](tools/image-browser.md)**. A free
    [sample dataset](https://zenodo.org/records/7995674) (CC-BY-4.0) lets you try
    everything end-to-end.

## At a glance

| | |
|---|---|
| **Host** | QGIS 4 / Qt6 (Linux, macOS, Windows) |
| **Inputs** | MBES soundings (Parquet), bathymetry rasters, HabCam imagery + metadata, survey video + GPS log, detector annotations |
| **Acoustic/GRASS backend** | [FastGIS GRASS API](tools/grass-fastgis.md) (`api.fastgis.eu`) |
| **Sample data** | [Zenodo 7995674](https://zenodo.org/records/7995674) (CC-BY-4.0) |
| **License** | GPL-2.0-or-later |
