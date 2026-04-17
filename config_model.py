"""Pydantic configuration models for the GroundTruther plugin.

The top-level model is ``HabcamSettings``, which mirrors the structure of
``config/config.yaml``.  Pydantic validates paths and URLs on load so the
rest of the plugin can assume they are well-formed.
"""
from pydantic import AnyUrl, BaseModel, DirectoryPath, FilePath, IPvAnyAddress
from typing import Optional, Union


class HabCam(BaseModel):
    """HabCam image collection settings.

    Attributes:
        imagepath: Directory containing JPEG image files.
        imagemetadata: CSV file with per-image metadata (lat, lon, depth, …).
        imageannotation: Optional CSV file mapping image names to bounding-box
            annotations (species labels + confidence scores).
    """

    imagepath: DirectoryPath
    imagemetadata: FilePath
    imageannotation: Optional[FilePath] = None


class Mbes(BaseModel):
    """Multibeam echo-sounder data settings.

    Attributes:
        soundings: Optional path to a soundings file used by the query builder.
    """

    soundings: Optional[FilePath] = None


class Export(BaseModel):
    """Export / output directory settings.

    Attributes:
        kmldir: Directory where KMZ report files are saved.
    """

    kmldir: Optional[DirectoryPath] = None
    # vrtdir: Optional[DirectoryPath] = None


class Processing(BaseModel):
    """Processing / compute settings.

    Attributes:
        gpu_avaibility: Whether a CUDA-capable GPU is available for spatial
            selection acceleration (cudf/cuspatial).
        grass_api_endpoint: Base URL of the GRASS GIS REST API server, e.g.
            ``http://localhost:8000``.  Leave empty to disable GRASS features.
    """
    gpu_avaibility: bool = False
    grass_api_endpoint: Optional[AnyUrl] = None

# class Mapviewer(BaseModel):
#     basemap: Optional[AnyUrl] = None


class Filesystem(BaseModel):
    """Filesystem / OS integration settings.

    Attributes:
        filemanager: Path to an external file-manager executable used by the
            KML report builder to open the export directory.
    """

    filemanager: Optional[FilePath] = None


class VideoSettings(BaseModel):
    """Video playback and annotation settings (all fields optional).

    Named ``VideoSettings`` (not ``Video``) to avoid the pydantic v1 bug
    where a field name that matches the nested model class name causes
    ``Optional[T]`` coercion to silently fail.

    Attributes:
        videofile: Path to the primary video file (MP4/H.264 recommended).
        videometadata: CSV file with per-frame geo-location data.
            Required columns: ``frame_index``, ``timestamp``, ``latitude``,
            ``longitude``.  Optional: ``depth``, ``altitude``, ``heading``,
            ``pitch``, ``roll``.
        videoannotation: CSV file mapping frame indices to bounding-box
            annotations.  Required columns: ``frame_index``, ``bboxes``
            (JSON list of ``[x0,y0,x1,y1]``), ``species`` (JSON list of
            strings), ``confidences`` (JSON list of floats).
    """

    videofile: Optional[str] = None
    videometadata: Optional[str] = None
    videoannotation: Optional[str] = None


class HabcamSettings(BaseModel):
    """Root configuration model — mirrors ``config/config.yaml``.

    All path fields are validated by Pydantic on load; invalid paths will
    raise a ``ValidationError`` rather than surfacing later as obscure
    ``FileNotFoundError`` exceptions.
    """

    HabCam: Union[HabCam]
    Mbes: Mbes
    Export: Union[Export]
    # Mapviewer: Mapviewer
    Processing: Union[Processing]
    Filesystem: Filesystem
    Video: Optional[VideoSettings] = None
