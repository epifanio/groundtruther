# Annotations & video

Three smaller CSV formats: detections on still imagery, the video navigation log,
and per-frame video annotations.

---

## Image annotation CSV

`HabCam.imageannotation` — the detector output overlaid on the imagery by the
[Image Browser](../tools/image-browser.md) and edited by the
[annotation editor](../tools/annotation.md).

**The file is read positionally, not by header name.** GroundTruther skips any
leading blank or comment lines, drops a header row if there is one, and then
assigns its own names to the eleven columns, in order:

| # | GroundTruther's name | Meaning |
|---|---|---|
| 1 | `Detection` | Detection id. |
| 2 | `Imagename` | Image the detection belongs to. A trailing `.jpg` is stripped, so the value joins against the metadata table's `Imagename` either way. |
| 3 | `Frame_Identifier` | Frame counter from the detector. |
| 4 | `TL_x` | Bounding box, top-left **x**, in image pixels. |
| 5 | `TL_y` | Bounding box, top-left **y**. |
| 6 | `BR_x` | Bounding box, bottom-right **x**. |
| 7 | `BR_y` | Bounding box, bottom-right **y**. |
| 8 | `detection_Confidence` | A second confidence value from the detector. Not used for filtering. |
| 9 | `Target_Length` | Measured target length. Not read by the plugin. |
| 10 | `Species` | The label string shown on the box and tallied in the metadata panel. |
| 11 | `Confidence` | **The value the confidence threshold filters on.** |

Columns 4–7 and 11 are coerced to numbers; unparseable values become `NaN`.
Rows are then grouped by `Imagename`, so one image carries parallel lists of
boxes, species and confidences. The box itself is stored as a closed
four-corner ring — `(TL_x, BR_y) → (BR_x, BR_y) → (BR_x, TL_y) → (TL_x, TL_y)`.

A file from the sample dataset looks like this — note that the header names
differ from GroundTruther's internal names but the **order matches**:

```csv
id,Imagename,frame_id,TL_x,TL_y,BR_x,BR_y,detection_length_confidence,target_length,species,detection_confidence
9,201503.20150619.181142496.204638.jpg,8,123.0,306.0,182.0,374.0,0.231257,0,fish,0.231257
15,201503.20150619.181143331.204643.jpg,12,422.875,325.125,584.375,567.375,0.335472,0,fish,0.335472
```

!!! info "The preamble is detected, not assumed"
    GroundTruther accepts the file however it arrives: with a header row or
    without, and with any number of blank or `#`-commented banner lines in front
    of it. A header is recognised by its bounding-box columns failing to parse as
    numbers, so a detection with one damaged coordinate is still read as a
    detection. **Every row is kept** — the sample dataset's
    `test_detector_output.csv` loads all 7 278 detections. Which shape was
    detected is logged to the `GroundTruther` message-log tab.

    The reader used to be fixed at `skiprows=[0, 1]`, which lost the first
    detection of a single-header file and turned the header of GroundTruther's own
    save into a phantom annotation
    ([#28](https://github.com/epifanio/groundtruther/issues/28)). Files written by
    that older version — two blank lines, then the header — still load correctly.

The **confidence threshold** spin box in the Image Browser hides any box whose
`Confidence` is below the value; the filter is inclusive (`>=`) and is shared
with the annotation editor.

---

## Video metadata CSV

`Video.videometadata` — the navigation log that geo-links the
[Video Player](../tools/video-player.md) to the map.

GroundTruther reads the **cruise-survey export format**: degrees-plus-decimal-
minutes with hemisphere letters, one row per logged observation. Column names
are matched by name (surrounding whitespace is stripped first, because the
instrument software pads them), and any column that is absent simply comes
through empty.

| Source column | Meaning |
|---|---|
| `Cruise`, `Superstation`, `Station` | Survey identifiers. |
| `Videoseqence` | The sequence number that becomes `frame_index`. *(Spelled exactly like that.)* |
| `Date`, `Time` | Parsed together with the format `%d.%m.%Y %H:%M:%S` — e.g. `19.06.2015 18:11:40`. A value in any other format becomes `NaT`. |
| `LatDeg`, `LatMin`, `NorthSouth` | Vessel latitude in DDM + hemisphere (`N`/`S`). |
| `LonDeg`, `LonMin`, `EastWest` | Vessel longitude in DDM + hemisphere (`E`/`W`). |
| `Depth` | Water depth, metres. |
| `Bottom`, `Biology`, `Comments` | Free-text observations. |
| `CP_LatDeg`, `CP_LatMin`, `CP_NorthSouth` | Camera-platform latitude in DDM. |
| `CP_LonDeg`, `CP_LonMin`, `CP_EastWest` | Camera-platform longitude in DDM. |
| `CP_Altitude`, `CP_Depth`, `CP_MeanAlt` | Camera-platform altitude, depth and mean altitude. |

After loading, the plugin works with this normalised frame, indexed by
`frame_index`:

`frame_index`, `timestamp`, `latitude`, `longitude`, `depth`, `bottom`,
`biology`, `comments`, `cruise`, `superstation`, `station`, `cp_latitude`,
`cp_longitude`, `cp_altitude`, `cp_depth`, `cp_mean_alt`

`latitude` / `longitude` are signed decimal degrees, converted from DDM on load
(`S` and `W` become negative). They are what the KD-tree is built on and what the
map marker and GPS-track layer use.

The player's metadata panel shows: **Sequence** (`frame_index`), **Date/Time**
(`timestamp`), **Latitude**, **Longitude**, **Depth (m)**, **Altitude**
(`cp_mean_alt`), **Bottom**, **Biology**, **Cruise**, **Station**, **Comments**.

!!! note "`frame_index` is a sequence number, not a video frame number"
    `Videoseqence` counts logged observations, not decoded video frames. A helper
    (`compute_frame_indices`) can estimate the true video frame from elapsed time
    × FPS when the two do not line up; it adds a derived `video_frame` column and
    does not change anything in your file.

---

## Video annotation CSV

`Video.videoannotation` — per-frame bounding boxes for the video player. This one
**is** read by header name, and it is the format the annotation editor writes
back, so it round-trips.

| Column | Type | Meaning |
|---|---|---|
| `frame_index` | int | Must match a `frame_index` in the video metadata. |
| `bboxes` | JSON string | List of `[x0, y0, x1, y1]` pixel boxes. |
| `species` | JSON string | List of label strings — same length as `bboxes`. |
| `confidences` | JSON string | List of floats — same length as `bboxes`. |

```csv
frame_index,bboxes,species,confidences
1204,"[[10,20,100,80],[200,150,320,280]]","[""Porifera"",""Echinodermata""]","[0.95,0.87]"
```

A row whose JSON does not parse, or which is missing one of the three columns, is
**skipped silently** — check the row count in the message log
(`Video annotations loaded: N frames`) if boxes are missing.

Saving from the editor rewrites the whole file, sorted by `frame_index`, with
exactly these four columns.
