import numpy as np
import pandas as pd


def bbox_parser(row, columns, name):
    return {name: [row[i] for i in columns]}


def parse_annotation(annotation_file):
    names = [
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
    imageannotation = pd.read_csv(annotation_file, skiprows=[0, 1], names=names)
    imageannotation["Imagename"] = imageannotation["Imagename"].str.replace(
        ".jpg", "", regex=False
    )
    columns = ["TL_x", "BR_y", "BR_x", "BR_y", "BR_x", "TL_y", "TL_x", "TL_y"]
    imageannotation["bbox"] = imageannotation.apply(
        bbox_parser, columns=columns, name="bbox", axis=1
    )
    annotations_by_image = (
        imageannotation.groupby("Imagename")
        .agg({"bbox": list, "Species": list, "Confidence": list})
        .to_dict("index")
    )
    return annotations_by_image
