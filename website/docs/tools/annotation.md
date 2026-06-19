# Image & Video Annotation

Create and curate labelled observations on both still imagery and video frames —
the optical "ground truth" that anchors the acoustic interpretation.

## Image annotation

<figure markdown>
  <!-- TODO: replace src with assets/img/annotation-image-1.png -->
  ![Image annotation editor](../assets/img/placeholder.svg){ width="900" }
  <figcaption>Editing a bounding-box annotation on a seafloor image.</figcaption>
</figure>

- Draw a **bounding box** over a feature in the current image, assign a **label**
  and a **confidence**, and save it.
- Existing annotations (e.g. from an automated detector CSV) are shown as boxes;
  select one to **edit** its label/extent or **delete** it.
- A **confidence threshold** filters which annotations are displayed (shared with
  the [Image Browser](image-browser.md)).
- Known labels are remembered to keep labelling consistent across images.

**How to use:** enter *Add* (draw) mode, drag a box on the image, pick/enter a
label and confidence in the editor panel, and save. Click an existing box to
re-select it for editing or deletion.

## Video annotation

<figure markdown>
  <!-- TODO: replace src with assets/img/annotation-video-1.png -->
  ![Video annotation editor](../assets/img/placeholder.svg){ width="900" }
  <figcaption>Per-frame annotations in the Video Player.</figcaption>
</figure>

- Annotations are attached **per frame**: add / edit / delete boxes on the frame
  currently shown in the [Video Player](video-player.md).
- Each annotation carries a label and confidence, mirroring the image workflow.

!!! tip "Annotation data"
    Image annotations come from / persist to the `imageannotation` CSV; video
    annotations are keyed by frame index. Both feed the same labelled-observation
    model used elsewhere in the plugin.
