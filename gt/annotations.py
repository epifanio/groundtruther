"""Stateless image-annotation CSV reader / writer.

No Qt, no QGIS, no plugin state — so it can be unit-tested directly.
``groundtruther.ioutils`` re-exports :func:`parse_annotation` for the two call
sites that already import it from there.

The format
----------
Eleven columns, **matched by position, not by name** — a detector export and
GroundTruther's own save use different spellings for the same fields
(``id`` / ``Detection``, ``frame_id`` / ``Frame_Identifier``,
``detection_confidence`` / ``Confidence``), but agree on the order:

    Detection, Imagename, Frame_Identifier, TL_x, TL_y, BR_x, BR_y,
    detection_Confidence, Target_Length, Species, Confidence

Three shapes are read (issue #28).  The reader used to hard-code
``skiprows=[0, 1]``, which was right for none of them:

=========================================  ===========================
shape                                      what the old reader did
=========================================  ===========================
one header line (detector export)          ate the header **and the
                                           first detection** — silent
                                           data loss
two blank lines + header (what
GroundTruther itself wrote until #28)      ate the two blank lines, so
                                           the **header survived as a
                                           data row**
two banner/comment lines + header          read correctly
=========================================  ===========================

So the leading lines are now sniffed instead: blank and comment lines are
dropped, and the first line that remains is a header only if it cannot be a
data row.  :func:`write_annotation_rows` writes an ordinary CSV — header, then
rows, no leading blanks — and the sniff still accepts every legacy file.
"""
from __future__ import annotations

import csv
import io

import pandas as pd


#: The eleven columns, in the order every producer of this format writes them.
ANNOTATION_COLUMNS = [
    "Detection",
    "Imagename",
    "Frame_Identifier",
    "TL_x",
    "TL_y",
    "BR_x",
    "BR_y",
    "detection_Confidence",
    "Target_Length",
    "Species",
    "Confidence",
]

#: Columns that hold bounding-box pixel coordinates.  A line whose *every* one
#: of these fails to parse as a number cannot be a data row, so it is a header.
_BBOX_COLUMNS = ("TL_x", "TL_y", "BR_x", "BR_y")

_COMMENT_PREFIXES = ("#", "//")


def _log_info(message: str) -> None:
    """Log to the QGIS message log when running inside QGIS; else stay quiet."""
    try:
        from qgis.core import Qgis, QgsMessageLog
    except ImportError:          # unit tests, scripts
        return
    QgsMessageLog.logMessage(message, "GroundTruther", Qgis.Info)


def _is_number(value: str) -> bool:
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True


def _looks_like_header(fields: list) -> bool:
    """True if *fields* cannot be a data row.

    Deliberately conservative: it takes **all four** bounding-box columns
    failing to parse as numbers.  A real detection always has four numeric
    coordinates, so one odd value (an empty cell, a stray ``NA``) still reads as
    data rather than being mistaken for a header.
    """
    positions = [ANNOTATION_COLUMNS.index(c) for c in _BBOX_COLUMNS]
    if len(fields) <= max(positions):
        # Too few columns to be a detection at all; treat as a banner line.
        return True
    return not any(_is_number(fields[i]) for i in positions)


def split_preamble(text: str) -> tuple[int, bool]:
    """Describe the top of an annotation CSV.

    Returns ``(skip, has_header)`` — how many physical lines to discard before
    the records, and whether the first line after them is a header.
    """
    lines = text.splitlines()
    skip = 0
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith(_COMMENT_PREFIXES):
            skip += 1
            continue
        break
    else:
        return skip, False                      # nothing but blanks/comments

    first = lines[skip]
    try:
        fields = next(csv.reader(io.StringIO(first)))
    except (csv.Error, StopIteration):
        return skip, False
    return skip, _looks_like_header(fields)


def read_annotation_frame(annotation_file) -> pd.DataFrame:
    """Read an annotation CSV into a DataFrame with :data:`ANNOTATION_COLUMNS`.

    Handles all three preamble shapes and always keeps every record.  Column
    *names* in the file are ignored — the mapping is positional.
    """
    if hasattr(annotation_file, "read"):
        text = annotation_file.read()
        if isinstance(text, bytes):
            text = text.decode("utf-8", "replace")
    else:
        with open(annotation_file, "r", newline="") as fh:
            text = fh.read()

    skip, has_header = split_preamble(text)
    _log_info(
        f"parse_annotation: {skip} preamble line(s), "
        f"{'a header row' if has_header else 'no header row'}"
    )

    # Cut the preamble off here rather than via pandas' ``skiprows``: whether
    # that counts blank lines depends on ``skip_blank_lines``, and getting it
    # wrong either way is exactly the bug being fixed.
    records = text.splitlines()[skip + (1 if has_header else 0):]
    if not any(line.strip() for line in records):
        return pd.DataFrame(columns=ANNOTATION_COLUMNS)

    return pd.read_csv(
        io.StringIO("\n".join(records)),
        names=ANNOTATION_COLUMNS,
        header=None,
        skip_blank_lines=True,
    )


def rect_to_bbox_ring(x0: float, y0: float, x1: float, y1: float) -> list:
    """A rectangle as the eight-value corner ring this format stores.

    ``[TL_x, BR_y, BR_x, BR_y, BR_x, TL_y, TL_x, TL_y]`` — the same order
    :func:`parse_annotation` builds when reading, so a box round-trips.
    """
    return [x0, y1, x1, y1, x1, y0, x0, y0]


def bbox_ring_to_rect(coords: list) -> tuple[float, float, float, float]:
    """Invert :func:`rect_to_bbox_ring` -> ``(x0, y0, x1, y1)``, normalised."""
    xs = coords[0::2]
    ys = coords[1::2]
    return min(xs), min(ys), max(xs), max(ys)


def _bbox_ring(row, columns, name):
    return {name: [row[i] for i in columns]}


def parse_annotation(annotation_file) -> dict:
    """Read an annotation CSV into ``{imagename: {bbox, Species, Confidence}}``.

    ``Imagename`` is stripped of its ``.jpg`` suffix to match the bare frame
    name the metadata uses.  ``bbox`` is the four-corner ring
    ``[TL_x, BR_y, BR_x, BR_y, BR_x, TL_y, TL_x, TL_y]`` that
    :func:`bbox_ring_to_rect` inverts.
    """
    imageannotation = read_annotation_frame(annotation_file)
    imageannotation["Imagename"] = (
        imageannotation["Imagename"].astype("string").str.replace(
            ".jpg", "", regex=False)
    )
    # Ensure numeric columns are actually numeric (CSV may leave them as strings)
    for col in ("TL_x", "TL_y", "BR_x", "BR_y", "Confidence"):
        imageannotation[col] = pd.to_numeric(imageannotation[col], errors="coerce")
    columns = ["TL_x", "BR_y", "BR_x", "BR_y", "BR_x", "TL_y", "TL_x", "TL_y"]
    imageannotation["bbox"] = imageannotation.apply(
        _bbox_ring, columns=columns, name="bbox", axis=1
    )
    annotations_by_image = (
        imageannotation.groupby("Imagename")
        .agg({"bbox": list, "Species": list, "Confidence": list})
        .to_dict("index")
    )
    return annotations_by_image


def write_annotation_rows(rows, path: str) -> None:
    """Write *rows* (dicts keyed by :data:`ANNOTATION_COLUMNS`) as a plain CSV.

    An ordinary header-then-rows CSV.  Until #28 this wrote ``"\\n\\n"`` first,
    which is what the old ``skiprows=[0, 1]`` reader was built around; between
    them they turned the header into a phantom record on every reload.
    """
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=ANNOTATION_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
