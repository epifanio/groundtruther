"""Annotation-CSV reader/writer tests — the spec for issue #28.

The reader used to hard-code ``skiprows=[0, 1]``, which was wrong for both of
the formats it is actually given, in opposite directions:

* GroundTruther's own save (two blank lines, then the header) read back **four**
  records from three, the extra one being the header row itself; and
* a detector export (one header line) read back **two** from three — the header
  *and the first detection* were both discarded.

These tests pin down "N annotations in, N annotations out" for every preamble
shape, and the corner-ring round trip that the editor depends on.
"""
import csv
import io

import pandas as pd
import pytest

from groundtruther.gt.annotations import (
    ANNOTATION_COLUMNS,
    bbox_ring_to_rect,
    rect_to_bbox_ring,
    parse_annotation,
    read_annotation_frame,
    split_preamble,
    write_annotation_rows,
)


# --------------------------------------------------------------------------- #
# fixtures / helpers                                                          #
# --------------------------------------------------------------------------- #

def make_rows(n, species="fish", confidence=0.9):
    """*n* well-formed detection rows, one per image."""
    return [
        {
            "Detection": i,
            "Imagename": f"img{i}.jpg",
            "Frame_Identifier": i,
            "TL_x": 10.0 * i,
            "TL_y": 20.0 * i,
            "BR_x": 30.0 * i,
            "BR_y": 40.0 * i,
            "detection_Confidence": confidence,
            "Target_Length": 0,
            "Species": species,
            "Confidence": confidence,
        }
        for i in range(1, n + 1)
    ]


def render(rows, preamble="", header=True, fieldnames=None):
    """Serialise *rows* the way some producer of this format would."""
    buf = io.StringIO()
    buf.write(preamble)
    writer = csv.DictWriter(buf, fieldnames=ANNOTATION_COLUMNS)
    if header:
        if fieldnames is None:
            writer.writeheader()
        else:
            buf.write(",".join(fieldnames) + "\r\n")
    writer.writerows(rows)
    return buf.getvalue()


# The header a real detector export carries — different spellings, same order.
DETECTOR_HEADER = [
    "id", "Imagename", "frame_id", "TL_x", "TL_y", "BR_x", "BR_y",
    "detection_length_confidence", "target_length", "species",
    "detection_confidence",
]


# --------------------------------------------------------------------------- #
# every preamble shape keeps every record                                     #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("label, text", [
    # what GroundTruther itself writes since #28
    ("plain header", render(make_rows(3))),
    # what GroundTruther wrote *before* #28 — the shape skiprows=[0, 1] was
    # built for, and the one that produced a phantom header record
    ("two blank lines + header", render(make_rows(3), preamble="\n\n")),
    # a detector export: one header line, different column spellings
    ("detector header", render(make_rows(3), fieldnames=DETECTOR_HEADER)),
    # the two-banner-line export the magic number was presumably copied from
    ("two banner lines + header",
     render(make_rows(3), preamble="# survey HRS1508\n# exported by detector v3\n")),
    # no header at all
    ("no header", render(make_rows(3), header=False)),
    # blank lines scattered before the header
    ("blank, banner, blank + header",
     render(make_rows(3), preamble="\n# note\n\n")),
])
def test_three_annotations_read_back_as_three(label, text, tmp_path):
    path = tmp_path / "ann.csv"
    path.write_text(text)

    frame = read_annotation_frame(path)
    assert len(frame) == 3, f"{label}: expected 3 records, got {len(frame)}"

    # No phantom record: the header must not survive as data.
    assert "Imagename" not in set(frame["Imagename"].astype(str))
    assert list(frame["Imagename"]) == ["img1.jpg", "img2.jpg", "img3.jpg"]

    # And nothing lost off the front.
    assert frame["TL_x"].tolist() == [10.0, 20.0, 30.0]


def test_parse_annotation_groups_by_image(tmp_path):
    path = tmp_path / "ann.csv"
    path.write_text(render(make_rows(3)))

    by_image = parse_annotation(path)

    # `.jpg` is stripped so the key matches the bare metadata frame name.
    assert sorted(by_image) == ["img1", "img2", "img3"]
    assert by_image["img2"]["Species"] == ["fish"]
    assert by_image["img2"]["Confidence"] == [0.9]


def test_several_detections_on_one_image_are_all_kept(tmp_path):
    rows = make_rows(3)
    for row in rows:
        row["Imagename"] = "img1.jpg"
    path = tmp_path / "ann.csv"
    path.write_text(render(rows))

    by_image = parse_annotation(path)
    assert list(by_image) == ["img1"]
    assert len(by_image["img1"]["bbox"]) == 3


def test_an_empty_file_is_not_an_error(tmp_path):
    path = tmp_path / "ann.csv"
    path.write_text("\n\n")
    assert read_annotation_frame(path).empty


def test_a_header_only_file_yields_no_records(tmp_path):
    path = tmp_path / "ann.csv"
    path.write_text(render([]))
    assert read_annotation_frame(path).empty


# --------------------------------------------------------------------------- #
# the sniff itself                                                            #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("text, expected", [
    (render(make_rows(1)), (0, True)),
    (render(make_rows(1), preamble="\n\n"), (2, True)),
    (render(make_rows(1), preamble="# banner\n# banner\n"), (2, True)),
    (render(make_rows(1), header=False), (0, False)),
    (render(make_rows(1), fieldnames=DETECTOR_HEADER), (0, True)),
])
def test_split_preamble(text, expected):
    assert split_preamble(text) == expected


def test_a_data_row_with_one_odd_coordinate_is_still_data(tmp_path):
    """The sniff must take *all four* bbox columns to be non-numeric.

    A detection with one blank coordinate is damaged data, not a header — and
    reading it as a header would silently drop it (the old failure mode).
    """
    rows = make_rows(2)
    rows[0]["TL_y"] = ""
    path = tmp_path / "ann.csv"
    path.write_text(render(rows, header=False))

    assert split_preamble(path.read_text()) == (0, False)
    assert len(read_annotation_frame(path)) == 2


# --------------------------------------------------------------------------- #
# writer -> reader round trip (the writer no longer emits two blank lines)     #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("n", [0, 1, 3, 50])
def test_writer_reader_round_trip_preserves_the_count(n, tmp_path):
    path = tmp_path / "ann.csv"
    write_annotation_rows(make_rows(n), str(path))

    frame = read_annotation_frame(path)
    assert len(frame) == n


def test_the_writer_emits_an_ordinary_csv(tmp_path):
    """No leading blank lines — that shape is what created the phantom record."""
    path = tmp_path / "ann.csv"
    write_annotation_rows(make_rows(2), str(path))

    lines = path.read_text().splitlines()
    assert lines[0].split(",")[:2] == ["Detection", "Imagename"]
    assert len(lines) == 3


def test_round_trip_preserves_species_and_confidence(tmp_path):
    path = tmp_path / "ann.csv"
    write_annotation_rows(make_rows(2, species="scallop", confidence=0.42), str(path))

    by_image = parse_annotation(path)
    assert by_image["img1"]["Species"] == ["scallop"]
    assert by_image["img1"]["Confidence"] == [0.42]


# --------------------------------------------------------------------------- #
# the bounding-box corner ring (task 11)                                      #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("rect", [
    (10.0, 20.0, 30.0, 40.0),
    (0.0, 0.0, 1.0, 1.0),
    (123.0, 306.0, 182.0, 374.0),        # a real row from test_detector_output.csv
    (422.875, 325.125, 584.375, 567.375),
])
def test_bbox_survives_editor_to_csv_to_editor(rect, tmp_path):
    """rect -> _rect_to_bbox -> CSV -> parse_annotation's ring -> rect."""
    x0, y0, x1, y1 = rect

    # what the editor holds, and what the writer derives from it
    assert bbox_ring_to_rect(rect_to_bbox_ring(*rect)) == rect

    path = tmp_path / "ann.csv"
    row = make_rows(1)[0]
    row.update(TL_x=x0, TL_y=y0, BR_x=x1, BR_y=y1)
    write_annotation_rows([row], str(path))

    ring = parse_annotation(path)["img1"]["bbox"][0]["bbox"]
    # the reader's ring is the writer's ring
    assert ring == rect_to_bbox_ring(*rect)
    assert bbox_ring_to_rect(ring) == rect


def test_the_reader_ring_order_is_the_documented_one(tmp_path):
    path = tmp_path / "ann.csv"
    row = make_rows(1)[0]
    row.update(TL_x=1.0, TL_y=2.0, BR_x=3.0, BR_y=4.0)
    write_annotation_rows([row], str(path))

    ring = parse_annotation(path)["img1"]["bbox"][0]["bbox"]
    assert ring == [1.0, 4.0, 3.0, 4.0, 3.0, 2.0, 1.0, 2.0]


# --------------------------------------------------------------------------- #
# the real sample file                                                        #
# --------------------------------------------------------------------------- #

SAMPLE = ("/home/epinux/dev/groundtruther_test_dataset/groundtruther_test_dataset"
          "/test_detector_output.csv")


@pytest.mark.skipif(not pd.io.common.file_exists(SAMPLE),
                    reason="sample dataset not present")
def test_the_sample_detector_export_keeps_every_row():
    """7 278 rows in the file; the old reader returned 7 277."""
    expected = len(pd.read_csv(SAMPLE))
    assert len(read_annotation_frame(SAMPLE)) == expected

    # the row the old reader ate
    frame = read_annotation_frame(SAMPLE)
    assert frame.iloc[0]["Imagename"] == "201503.20150619.181142496.204638.jpg"
