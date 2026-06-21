"""Stateless HTTP client for the FastGIS seafloor-roughness route.

Per-frame seafloor surface roughness is computed server-side from HabCam stereo
pairs (RAFT-Stereo on a GPU microservice).  FastGIS exposes a *roughness* route
that proxies that microservice over the Cloudflare tunnel; GroundTruther sends
only a ``frame_key`` (the HabCam image id it already has for the current browser
frame) and the server reads the stereo image from its own mounted archive.

Like :mod:`groundtruther.gt.grass_api`, every function here is pure: it takes a
base ``endpoint`` URL and an ``api_key`` (sent as the ``X-API-Key`` header) and
returns the parsed JSON payload.  No Qt, no QGIS, no plugin state.

Two transports, same request/response contract:

* **FastGIS route** (default): ``POST {endpoint}{route}`` with ``X-API-Key`` —
  FastGIS forwards to the GPU service and passes the JSON straight back.
* **direct fast-path** (opt-in, GT running *on* the GPU host): ``POST
  {direct_url}`` (e.g. ``http://127.0.0.1:7871/roughness``) with no auth header,
  skipping the tunnel.

Response contract (pass-through from the GPU service)::

    quality: "ok" | "insufficient_coverage" | "spectrum_fit_failed"
    gamma2, w2, k_ref_rad_per_m, fit_band_rad_per_m, fit_r2,
    rms_height_mm, slope_variance, rugosity, altitude_mm, valid_fraction,
    disparity_density, dx_mm, dem_shape, extent_mm, matcher, n_water,
    micro_dem_png_b64   # only when return_dem=True

When ``quality != "ok"`` the roughness fields are ``null``.

Interpretation (for callers): ``gamma2`` (spectral exponent) is the trustworthy
acoustic input; ``rms_height_mm`` and ``w2`` are PROVISIONAL (absolute
calibration still open).  ``altitude_mm`` is a good QA cross-check against the
metadata Altimeter.
"""
import requests

from groundtruther.configure import log_exception

# The FastGIS roughness route path (relative to the API endpoint).  Confirmed
# live against the FastGIS OpenAPI: POST /seafloor/roughness (RoughnessRequest:
# frame_key required; res_mm/n_water/return_dem optional).  Kept overridable
# per-call / via config so the plugin can be repointed without a code change.
DEFAULT_ROUTE = "/seafloor/roughness"

# Sibling health probe (GET, X-API-Key) for connectivity diagnostics.
HEALTH_ROUTE = "/seafloor/health"

# Mosaic route — composite contiguous frames into one georeferenced UTM raster.
MOSAIC_ROUTE = "/seafloor/mosaic"

# Cold model load on the GPU service can take ~14 s on the first call; steady
# state is ~0.5 s.  Use a generous timeout so the first frame doesn't spuriously
# fail.  The async QgsTask wrapper keeps the UI responsive meanwhile.
_TIMEOUT = 60

# A mosaic composites many frames (and pays the same cold-load on the first call),
# so give it a longer ceiling than the single-frame route.
_TIMEOUT_MOSAIC = 180

#: Valid values of the response ``quality`` field.
QUALITY_OK = "ok"
QUALITY_INSUFFICIENT = "insufficient_coverage"
QUALITY_FIT_FAILED = "spectrum_fit_failed"


class RoughnessError(Exception):
    """Raised on any roughness-route failure (network, auth, or HTTP 4xx/5xx).

    Mirrors :class:`groundtruther.gt.grass_api.GrassApiError` so mixins can
    handle both consistently.

    Attributes
    ----------
    detail:
        Human-readable message (the server's ``detail`` field when available).
    status:
        HTTP status code, or ``None`` for network-level failures.
    """

    def __init__(self, detail: str, status: int | None = None):
        super().__init__(detail)
        self.detail = detail
        self.status = status

    def __str__(self) -> str:
        return f"[{self.status}] {self.detail}" if self.status else self.detail


def _extract_detail(response) -> str:
    """Best-effort extraction of an error message from a failed response."""
    try:
        body = response.json()
    except ValueError:
        return (response.text or "")[:300] or f"HTTP {response.status_code}"
    if isinstance(body, dict):
        detail = body.get("detail", body)
        if isinstance(detail, list):   # FastAPI 422 detail: [{loc,msg,type}, ...]
            return "; ".join(d.get("msg", str(d)) for d in detail)
        return str(detail)
    return str(body)


def _build_body(frame_key, res_mm, n_water, return_dem, geo=None, *,
                dem_format=None, dem_max_side=None, include_orthophoto=False,
                include_left_height=False, include_left_preview=False) -> dict:
    """Assemble the request JSON; GT sends the key plus only the knobs in use.

    Optional outputs are off by default — request only what will be rendered:

    * ``dem_format`` (``png``|``mm``|``both``) — ``mm`` returns a real float
      height grid (``micro_dem``) for the 3-D mesh; ``png`` the 8-bit preview.
    * ``include_orthophoto`` — the photo on the DEM's world grid (1:1 texture).
    * ``include_left_height`` / ``include_left_preview`` — the per-left-pixel
      height raster + rectified-left preview for the 2-D JPEG overlay.
    * ``geo`` — the UTM-georeferencing object from
      :func:`groundtruther.gt.roughness_geo.build_geo`, forwarded verbatim.
    """
    if not (frame_key and str(frame_key).strip()):
        raise RoughnessError("A frame_key is required")
    body: dict = {"frame_key": str(frame_key)}
    if res_mm is not None:
        body["res_mm"] = float(res_mm)
    if n_water is not None:
        body["n_water"] = float(n_water)
    if return_dem:
        body["return_dem"] = True
    if dem_format:
        body["dem_format"] = str(dem_format)
    if dem_max_side is not None:
        body["dem_max_side"] = int(dem_max_side)
    if include_orthophoto:
        body["include_orthophoto"] = True
    if include_left_height:
        body["include_left_height"] = True
    if include_left_preview:
        body["include_left_preview"] = True
    if geo:
        body["geo"] = geo
    return body


def roughness_for_frame(frame_key, *, endpoint: str | None = None,
                        api_key: str | None = None, route: str = DEFAULT_ROUTE,
                        direct_url: str | None = None,
                        res_mm: float | None = None, n_water: float | None = None,
                        return_dem: bool = False, geo: dict | None = None,
                        dem_format: str | None = None,
                        dem_max_side: int | None = None,
                        include_orthophoto: bool = False,
                        include_left_height: bool = False,
                        include_left_preview: bool = False,
                        timeout: int = _TIMEOUT) -> dict:
    """Compute roughness for one HabCam frame and return the parsed JSON dict.

    Parameters
    ----------
    frame_key:
        The HabCam image id for the current frame (e.g.
        ``"201503.20150619.181140656.204627"``, ``"204627"``, or the filename).
        Only the key is sent; the server reads the stereo image itself.
    endpoint, api_key:
        FastGIS base URL and ``X-API-Key`` (the same credentials the GRASS client
        uses).  Required unless ``direct_url`` is given.
    route:
        Roughness route path appended to ``endpoint`` (default ``/roughness``).
    direct_url:
        When set, POST straight to this URL (the on-host GPU service) with no
        auth header, skipping the FastGIS tunnel.  Same request/response.
    res_mm, n_water, return_dem:
        Optional compute knobs.  Set ``return_dem=True`` only when the caller
        wants the micro-DEM preview overlay (``micro_dem_png_b64``).
    geo:
        Optional UTM-georeferencing object (easting/northing/heading_deg/epsg +
        mount calibration); when present the service returns a geotransform so
        the micro-DEM / orthophoto can be written as GeoTIFFs.
    timeout:
        Socket timeout in seconds (default 60; first call can be ~14 s cold).

    Raises
    ------
    RoughnessError
        On missing config, network failure, non-2xx response, or non-JSON body.
        A ``quality != "ok"`` response is NOT an error — it returns normally with
        null roughness fields.
    """
    body = _build_body(
        frame_key, res_mm, n_water, return_dem, geo,
        dem_format=dem_format, dem_max_side=dem_max_side,
        include_orthophoto=include_orthophoto,
        include_left_height=include_left_height,
        include_left_preview=include_left_preview)

    if direct_url and direct_url.strip():
        url = direct_url.strip()
        headers = {"accept": "application/json", "Content-Type": "application/json"}
    else:
        if not (endpoint and endpoint.strip()):
            raise RoughnessError("No roughness endpoint configured")
        if not (api_key and api_key.strip()):
            raise RoughnessError("No API key configured")
        url = f"{endpoint.rstrip('/')}/{route.lstrip('/')}"
        headers = {"accept": "application/json", "Content-Type": "application/json",
                   "X-API-Key": api_key}

    try:
        response = requests.post(url, headers=headers, json=body, timeout=timeout)
    except requests.exceptions.RequestException as exc:
        log_exception("roughness_for_frame: network error", exc, warn=True)
        raise RoughnessError(f"Cannot reach the roughness service: {exc}") from exc

    if not response.ok:
        detail = _extract_detail(response)
        log_exception(
            f"roughness_for_frame: HTTP {response.status_code}: {detail}",
            RoughnessError(detail, response.status_code), warn=True)
        raise RoughnessError(detail, response.status_code)

    try:
        payload = response.json()
    except ValueError as exc:
        raise RoughnessError("Non-JSON response from the roughness service") from exc
    if not isinstance(payload, dict):
        raise RoughnessError("Unexpected roughness response (expected a JSON object)")
    return payload


def _post_json(body: dict, *, endpoint, api_key, route, direct_url, timeout,
               what: str = "roughness") -> dict:
    """POST *body* to the FastGIS *route* (or *direct_url*) and return parsed JSON.

    Same transport/auth contract as :func:`roughness_for_frame` (X-API-Key over the
    FastGIS tunnel, or an unauthenticated direct POST when *direct_url* is set).
    """
    if direct_url and direct_url.strip():
        url = direct_url.strip()
        headers = {"accept": "application/json", "Content-Type": "application/json"}
    else:
        if not (endpoint and endpoint.strip()):
            raise RoughnessError(f"No {what} endpoint configured")
        if not (api_key and api_key.strip()):
            raise RoughnessError("No API key configured")
        url = f"{endpoint.rstrip('/')}/{route.lstrip('/')}"
        headers = {"accept": "application/json", "Content-Type": "application/json",
                   "X-API-Key": api_key}
    try:
        response = requests.post(url, headers=headers, json=body, timeout=timeout)
    except requests.exceptions.RequestException as exc:
        log_exception(f"{what}: network error", exc, warn=True)
        raise RoughnessError(f"Cannot reach the roughness service: {exc}") from exc
    if not response.ok:
        detail = _extract_detail(response)
        log_exception(f"{what}: HTTP {response.status_code}: {detail}",
                      RoughnessError(detail, response.status_code), warn=True)
        raise RoughnessError(detail, response.status_code)
    try:
        payload = response.json()
    except ValueError as exc:
        raise RoughnessError(f"Non-JSON response from the {what} service") from exc
    if not isinstance(payload, dict):
        raise RoughnessError(f"Unexpected {what} response (expected a JSON object)")
    return payload


def _build_mosaic_body(reference_key, window, mode, out_gsd_m, epsg, *,
                       max_side=None, interp=None, supersample=None,
                       alpha=False, nodata=None) -> dict:
    """Assemble the mode-A mosaic request JSON (reference + window + controls)."""
    if not (reference_key and str(reference_key).strip()):
        raise RoughnessError("A reference_key is required")
    body: dict = {"reference_key": str(reference_key), "window": int(window),
                  "mode": str(mode)}
    if out_gsd_m is not None:
        body["out_gsd_m"] = float(out_gsd_m)
    if epsg is not None:
        body["epsg"] = int(epsg)
    if max_side is not None:
        body["max_side"] = int(max_side)
    if interp:
        body["interp"] = str(interp)
    if supersample is not None:
        body["supersample"] = int(supersample)
    if alpha:
        body["alpha"] = True
    if nodata is not None:
        body["nodata"] = float(nodata)
    return body


def mosaic_by_reference(reference_key, *, window: int = 5, mode: str = "flat",
                        out_gsd_m: float | None = None, epsg: int | None = None,
                        max_side: int | None = None, interp: str | None = None,
                        supersample: int | None = None, alpha: bool = False,
                        nodata: float | None = None,
                        endpoint: str | None = None, api_key: str | None = None,
                        route: str = MOSAIC_ROUTE, direct_url: str | None = None,
                        timeout: int = _TIMEOUT_MOSAIC) -> dict:
    """Mosaic **mode A** — composite the ±*window* contiguous frames around
    *reference_key* into one georeferenced UTM raster.

    The service pulls the nav itself (easting/northing/heading/altimeter) for the
    window, **skips gaps** (frames with no image in the archive), and returns
    ``{mosaic_png_b64, geotransform, epsg, shape, bands, nodata, has_alpha, mode,
    n_frames, frames_skipped, out_gsd_m, ...}``.

    Controls (defaults are the service's):
      * ``mode`` — ``"flat"`` (altitude/f scale, fast) or ``"ortho"`` (relief-corrected)
      * ``out_gsd_m`` — output GSD (default 0.003 = 3 mm); lower → sharper / nearer native
      * ``max_side`` — output side cap (default 4096; raise to 8192 for big fine strips)
      * ``interp`` — ``"linear"`` (browse) / ``"area"`` (anti-aliased coarse) /
        ``"lanczos"``|``"cubic"`` (sharp near-native, with a fine ``out_gsd_m``)
      * ``alpha`` — when True, a 4-band RGBA mosaic (``bands=4``) so QGIS shows
        transparency automatically; otherwise the response carries ``nodata`` for the
        border (set it on the GeoTIFF bands).

    Write the GeoTIFF from ``mosaic_png_b64 + geotransform + epsg`` (branch on
    ``bands`` for 3 vs 4); honour ``frames_skipped``.  Keep ``epsg=32619``.

    Transport/auth identical to :func:`roughness_for_frame`.  Raises
    :class:`RoughnessError` on missing config, network failure, or non-2xx.
    """
    body = _build_mosaic_body(reference_key, window, mode, out_gsd_m, epsg,
                              max_side=max_side, interp=interp,
                              supersample=supersample, alpha=alpha, nodata=nodata)
    return _post_json(body, endpoint=endpoint, api_key=api_key, route=route,
                      direct_url=direct_url, timeout=timeout, what="mosaic")


def health(endpoint: str, api_key: str, *, route: str = HEALTH_ROUTE,
           timeout: int = 10) -> dict:
    """Probe the roughness service health (``GET /seafloor/health``).

    Returns the parsed JSON body; raises :class:`RoughnessError` on any failure.
    Useful for a quick "is the GPU service reachable?" check before computing.
    """
    if not (endpoint and endpoint.strip()):
        raise RoughnessError("No roughness endpoint configured")
    if not (api_key and api_key.strip()):
        raise RoughnessError("No API key configured")
    url = f"{endpoint.rstrip('/')}/{route.lstrip('/')}"
    try:
        response = requests.get(
            url, headers={"accept": "application/json", "X-API-Key": api_key},
            timeout=timeout)
    except requests.exceptions.RequestException as exc:
        raise RoughnessError(f"Cannot reach the roughness service: {exc}") from exc
    if not response.ok:
        raise RoughnessError(_extract_detail(response), response.status_code)
    try:
        return response.json()
    except ValueError as exc:
        raise RoughnessError("Non-JSON response from the roughness service") from exc


def is_ok(result: dict | None) -> bool:
    """True when *result* carries usable roughness (``quality == "ok"``)."""
    return bool(result) and result.get("quality") == QUALITY_OK


def quality_message(result: dict | None) -> str:
    """Human-readable one-liner for a non-ok / missing result, else ``""``."""
    if is_ok(result):
        return ""
    quality = (result or {}).get("quality")
    if quality == QUALITY_INSUFFICIENT:
        return "no roughness — low stereo coverage"
    if quality == QUALITY_FIT_FAILED:
        return "no roughness — spectrum fit failed"
    if quality:
        return f"no roughness — {quality}"
    return "no roughness"
