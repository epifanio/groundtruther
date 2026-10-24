# GroundTruther — a toolset for seafloor characterization
#
# Copyright (C) 2023-2026 Massimo Di Stefano <epiesasha@me.com>
# https://github.com/epifanio/groundtruther
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Stateless HTTP client for the seafloor-roughness route.

Per-frame seafloor surface roughness is computed server-side from HabCam stereo
pairs (RAFT-Stereo on a GPU microservice).  Two deployments proxy that
microservice over the Cloudflare tunnel under the same ``/seafloor/*`` paths —
FastGIS (keyed) and ``seafloor-gateway`` (keyless) — and GroundTruther sends
only a ``frame_key`` (the HabCam image id it already has for the current browser
frame); the server reads the stereo image from its own mounted archive.

Like :mod:`groundtruther.gt.grass_api`, every function here is pure: it takes a
base ``endpoint`` URL and an optional ``api_key`` (sent as the ``X-API-Key``
header when there is one) and returns the parsed JSON payload.  No Qt, no QGIS,
no plugin state.  Unlike ``grass_api``, the key is *optional* here: the
``/grass/*`` routes are keyed without exception (D-002), the seafloor ones are
not.

Two transports and two auth shapes, same request/response contract:

* **composed route** (default): ``POST {endpoint}{route}``.  Authentication is
  *inferred from the configuration*: when an API key is configured the
  ``X-API-Key`` header is sent (the keyed FastGIS deployment at
  ``api.fastgis.eu``); when none is, **no auth header is sent at all** — which
  is what the keyless ``seafloor-gateway`` deployment at ``seafloor.fastgis.eu``
  expects, being unauthenticated by design (D-011).  An empty header is never
  sent: the key is either present and non-blank, or absent.
* **direct fast-path** (opt-in, GT running *on* the GPU host): ``POST
  {direct_url}`` (e.g. ``http://127.0.0.1:7871/roughness``) with no auth header,
  skipping both the tunnel and the ``endpoint``+``route`` composition.

A keyless *remote* gateway is therefore a supported configuration of the
composed route (``base_url`` + ``route``, no key), not a use of ``direct_url``:
``direct_url`` is the on-host fast path, takes one full URL per route, and
sibling routes have to be derived from it by hand.  If the server does want a
key and none was configured, it answers 401/403 and :class:`RoughnessError`
says so in as many words.

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

# The roughness route path (relative to the API endpoint).  Confirmed live
# against the FastGIS OpenAPI: POST /seafloor/roughness (RoughnessRequest:
# frame_key required; res_mm/n_water/return_dem optional), and served under the
# same path by the keyless seafloor-gateway (seafloor.fastgis.eu).  Kept
# overridable per-call / via config so the plugin can be repointed without a
# code change.
DEFAULT_ROUTE = "/seafloor/roughness"

# Sibling health probe (GET, keyed or keyless) for connectivity diagnostics.
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


def _headers(api_key: str | None) -> dict:
    """The request headers, with ``X-API-Key`` only when a key is configured.

    Keylessness is *inferred*: a key that is absent, ``None`` or blank means the
    header is left out entirely rather than sent empty, because the keyless
    ``seafloor-gateway`` deployment is unauthenticated by design (D-011) and an
    empty ``X-API-Key`` is a credential the proxy would have to reject.
    """
    headers = {"accept": "application/json", "Content-Type": "application/json"}
    if api_key and api_key.strip():
        headers["X-API-Key"] = api_key.strip()
    return headers


def _target(endpoint, api_key, route, direct_url, what: str = "roughness"):
    """Resolve one request's ``(url, headers)`` for either transport.

    ``direct_url`` wins and is used verbatim (the on-host fast path).  Otherwise
    the URL is composed from ``endpoint`` + ``route``; only the endpoint is
    required, since the gateway may be keyless.
    """
    if direct_url and direct_url.strip():
        return direct_url.strip(), _headers(None)
    if not (endpoint and endpoint.strip()):
        raise RoughnessError(f"No {what} endpoint configured")
    return f"{endpoint.rstrip('/')}/{route.lstrip('/')}", _headers(api_key)


def _raise_for_response(response, what: str, keyed: bool, *,
                        log_as: str | None = None) -> None:
    """Raise :class:`RoughnessError` for a non-2xx *response*.

    When the service answers 401/403 and no key was sent, say that plainly: it
    is the one failure a keyless configuration causes that a local guard used to
    catch, and "Unauthorized" alone would not point at the missing key.  *what*
    names the service in that message; *log_as* labels the log line.
    """
    detail = _extract_detail(response)
    if response.status_code in (401, 403) and not keyed:
        detail = (f"{detail} — this {what} service requires an API key and none "
                  f"is configured (set Processing.grass_api_key, or point "
                  f"Roughness.base_url at a keyless gateway)")
    log_exception(f"{log_as or what}: HTTP {response.status_code}: {detail}",
                  RoughnessError(detail, response.status_code), warn=True)
    raise RoughnessError(detail, response.status_code)


def _build_body(frame_key, res_mm, n_water, return_dem, geo=None, *,
                dem_format=None, dem_max_side=None, include_orthophoto=False,
                include_left_height=False, include_left_preview=False,
                include_spectrum=False) -> dict:
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
    if include_spectrum:
        body["include_spectrum"] = True
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
                        include_spectrum: bool = False,
                        timeout: int = _TIMEOUT) -> dict:
    """Compute roughness for one HabCam frame and return the parsed JSON dict.

    Parameters
    ----------
    frame_key:
        The HabCam image id for the current frame (e.g.
        ``"201503.20150619.181140656.204627"``, ``"204627"``, or the filename).
        Only the key is sent; the server reads the stereo image itself.
    endpoint, api_key:
        Base URL of the seafloor API and its ``X-API-Key`` (the same credentials
        the GRASS client uses).  ``endpoint`` is required unless ``direct_url``
        is given; ``api_key`` is optional — omit it for the keyless
        ``seafloor-gateway`` deployment and no auth header is sent.
    route:
        Roughness route path appended to ``endpoint``
        (default ``/seafloor/roughness``).
    direct_url:
        When set, POST straight to this URL (the on-host GPU service) with no
        auth header, skipping both the tunnel and the ``endpoint``+``route``
        composition.  For a keyless *remote* gateway use ``endpoint`` without a
        key instead; this is the on-host fast path.  Same request/response.
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
        On a missing endpoint, network failure, non-2xx response, or non-JSON
        body.  A missing API key is no longer an error here: the request simply
        goes out unauthenticated, and a service that wanted one answers 401/403.
        A ``quality != "ok"`` response is NOT an error — it returns normally with
        null roughness fields.
    """
    body = _build_body(
        frame_key, res_mm, n_water, return_dem, geo,
        dem_format=dem_format, dem_max_side=dem_max_side,
        include_orthophoto=include_orthophoto,
        include_left_height=include_left_height,
        include_left_preview=include_left_preview,
        include_spectrum=include_spectrum)

    url, headers = _target(endpoint, api_key, route, direct_url)

    try:
        response = requests.post(url, headers=headers, json=body, timeout=timeout)
    except requests.exceptions.RequestException as exc:
        log_exception("roughness_for_frame: network error", exc, warn=True)
        raise RoughnessError(f"Cannot reach the roughness service: {exc}") from exc

    if not response.ok:
        _raise_for_response(response, "roughness", "X-API-Key" in headers,
                            log_as="roughness_for_frame")

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

    Same transport/auth contract as :func:`roughness_for_frame`: ``X-API-Key``
    when a key is configured, no auth header when none is (the keyless gateway),
    and an unauthenticated POST to *direct_url* when that is set.
    """
    url, headers = _target(endpoint, api_key, route, direct_url, what)
    try:
        response = requests.post(url, headers=headers, json=body, timeout=timeout)
    except requests.exceptions.RequestException as exc:
        log_exception(f"{what}: network error", exc, warn=True)
        raise RoughnessError(f"Cannot reach the roughness service: {exc}") from exc
    if not response.ok:
        _raise_for_response(response, what, "X-API-Key" in headers)
    try:
        payload = response.json()
    except ValueError as exc:
        raise RoughnessError(f"Non-JSON response from the {what} service") from exc
    if not isinstance(payload, dict):
        raise RoughnessError(f"Unexpected {what} response (expected a JSON object)")
    return payload


def _build_mosaic_body(reference_key, window, mode, out_gsd_m, epsg, *,
                       max_side=None, interp=None, supersample=None,
                       alpha=False, nodata=None, overlap_threshold=None,
                       illumination_correct=None, gain_compensate=None) -> dict:
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
    if overlap_threshold is not None:
        body["overlap_threshold"] = float(overlap_threshold)
    # Radiometric corrections (pixel/auto): default ON server-side, so send the
    # bool only when set explicitly (lets the user turn them OFF).
    if illumination_correct is not None:
        body["illumination_correct"] = bool(illumination_correct)
    if gain_compensate is not None:
        body["gain_compensate"] = bool(gain_compensate)
    return body


def mosaic_by_reference(reference_key, *, window: int = 5, mode: str = "auto",
                        out_gsd_m: float | None = None, epsg: int | None = None,
                        max_side: int | None = None, interp: str | None = None,
                        supersample: int | None = None, alpha: bool = False,
                        nodata: float | None = None,
                        overlap_threshold: float | None = None,
                        illumination_correct: bool | None = None,
                        gain_compensate: bool | None = None,
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
      * ``mode`` — ``"auto"`` (default; picks ``pixel``/``flat`` per window from the
        nav-predicted overlap vs ``overlap_threshold``) · ``"flat"`` (altitude/f
        scale, fast) · ``"ortho"`` (relief-corrected) · ``"pixel"`` (register by
        image content). Response echoes ``mode_requested``/``mode``/``nav_overlap``
        and, for pixel, ``register.{pixel_pairs,n_pairs}``.
      * ``overlap_threshold`` — for ``auto``: median per-frame overlap ≥ this → pixel,
        else flat (default 0.6)
      * ``illumination_correct`` — flat-field the strobe vignette + equalize
        brightness (default ON; the main brightness fix). Normalizes radiometry —
        turn OFF for absolute-radiometry work.
      * ``gain_compensate`` — Brown–Lowe overlap gain compensation (default ON).
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
                              supersample=supersample, alpha=alpha, nodata=nodata,
                              overlap_threshold=overlap_threshold,
                              illumination_correct=illumination_correct,
                              gain_compensate=gain_compensate)
    return _post_json(body, endpoint=endpoint, api_key=api_key, route=route,
                      direct_url=direct_url, timeout=timeout, what="mosaic")


def health(endpoint: str, api_key: str | None = None, *,
           route: str = HEALTH_ROUTE, timeout: int = 10) -> dict:
    """Probe the roughness service health (``GET /seafloor/health``).

    Same auth shape as the POST routes: ``X-API-Key`` when a key is configured,
    no auth header when none is (the keyless gateway).  Returns the parsed JSON
    body; raises :class:`RoughnessError` on any failure.  Useful for a quick "is
    the GPU service reachable?" check before computing.
    """
    if not (endpoint and endpoint.strip()):
        raise RoughnessError("No roughness endpoint configured")
    url = f"{endpoint.rstrip('/')}/{route.lstrip('/')}"
    headers = _headers(api_key)
    headers.pop("Content-Type", None)      # a GET carries no body
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
    except requests.exceptions.RequestException as exc:
        raise RoughnessError(f"Cannot reach the roughness service: {exc}") from exc
    if not response.ok:
        _raise_for_response(response, "roughness", "X-API-Key" in headers,
                            log_as="health")
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
