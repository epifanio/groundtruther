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
        reference_surface: Optional GeoTIFF DEM / bathymetry raster. When set,
            the query builder's 3-D viewer clips this raster to the selected
            sampling shape instead of gridding the soundings; if absent or
            unreadable it falls back to the soundings surface. Kept as a plain
            string (not a validated ``FilePath``) so an empty / not-yet-present
            path never invalidates the whole config.
    """

    soundings: Optional[FilePath] = None
    reference_surface: Optional[str] = None


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
        grass_api_endpoint: Base URL of the FastGIS GRASS API server, e.g.
            ``https://api.fastgis.eu``.  Leave empty to disable GRASS features.
        grass_api_key: API key (``fgk_...``) sent as the ``X-API-Key`` header on
            every GRASS API request.  Required by the FastGIS API; leave empty to
            disable GRASS features.
    """
    gpu_avaibility: bool = False
    grass_api_endpoint: Optional[AnyUrl] = None
    grass_api_key: Optional[str] = None

# class Mapviewer(BaseModel):
#     basemap: Optional[AnyUrl] = None


class RoughnessSettings(BaseModel):
    """Per-frame seafloor-roughness service settings (all optional).

    Roughness is computed server-side from HabCam stereo pairs.  GroundTruther
    reaches it through the FastGIS roughness route (reusing the GRASS
    ``grass_api_endpoint`` + ``grass_api_key`` credentials), or — when running
    *on* the GPU host — directly via ``direct_url`` to skip the tunnel.

    Named ``RoughnessSettings`` (not ``Roughness``) to avoid the pydantic
    field-name-equals-class-name pitfall noted on ``VideoSettings`` /
    ``SessionSettings``.

    Attributes:
        base_url: FastGIS base URL for the roughness route.  Leave empty to
            fall back to ``Processing.grass_api_endpoint``.
        route: Roughness route path appended to the base URL
            (default ``/roughness`` when empty).
        direct_url: Optional on-host GPU service URL
            (e.g. ``http://127.0.0.1:7871/roughness``).  Default OFF (empty) —
            when set, GT POSTs here directly with no auth, skipping FastGIS.
        res_mm: Optional default DEM resolution (mm) passed to the service.
        n_water: Optional default refractive index of water.
    """

    base_url: Optional[str] = None
    route: Optional[str] = None
    direct_url: Optional[str] = None
    res_mm: Optional[float] = None
    n_water: Optional[float] = None

    # --- UTM georeferencing (optional) ---
    # When ``georeference`` is on, GT attaches a ``geo`` object (built from the
    # frame's nav: Xutm_adj→easting, Yutm_adj→northing [layback-corrected HabCam
    # seafloor position = habcam_lon/lat, NOT raw ship sXutm/sYutm],
    # Heading/bearing→heading_deg) to
    # the request; the service returns a geotransform so the micro-DEM and
    # orthophoto can be written as GeoTIFFs and added to QGIS.
    #
    # The mount is known (image bottom→top = heading, image-right = starboard), so
    # position AND rotation are correct out of the box — no calibration loop.
    # ``heading_offset_deg`` is a residual fine-tune (default 0); ``mirror`` is the
    # only escape hatch — set true once if a mosaic comes out port/starboard
    # flipped.  ``dem_max_side`` caps the returned grid resolution.
    georeference: bool = False
    epsg: int = 32619
    heading_offset_deg: float = 0.0
    mirror: bool = False
    dem_max_side: int = 512

    # --- 3-D mesh edge-spike mitigation ---
    # The stereo DEM is unreliable at the grid border and around no-data holes,
    # producing height spikes draped with stretched texture. These tune how the
    # Micro-DEM 3D mesh masks them: drop ``dem_trim_border`` outer rings, reject
    # cells more than ``dem_clip_sigma`` robust sigmas from the median, and erode
    # ``dem_erode`` rings off every no-data/outlier boundary. Masked cells are
    # flattened (median) and made transparent in the texture.
    dem_trim_border: int = 2
    dem_clip_sigma: float = 5.0
    dem_erode: int = 1


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


class SessionSettings(BaseModel):
    """Session-state persistence settings.

    Named ``SessionSettings`` (not ``Session``) to avoid the pydantic bug where
    a field name matching the nested model class name breaks ``Optional[T]``
    coercion — the same reason ``VideoSettings`` is not called ``Video``.

    Attributes:
        groundtruther_project: Path to a JSON file storing restorable UI/session
            state (image index, zoom, query-builder selection, video position,
            dock layout).  Written when the QGIS project is saved / the plugin
            closes, and loaded at plugin start.  It may not exist yet (created on
            first save), so it is a plain string rather than a validated
            ``FilePath``.
    """

    groundtruther_project: Optional[str] = None


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
    Session: Optional[SessionSettings] = None
    Roughness: Optional[RoughnessSettings] = None
