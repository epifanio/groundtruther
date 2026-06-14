"""Stateless HTTP client for the FastGIS GRASS API (https://api.fastgis.eu).

All functions are pure: they take a base ``endpoint`` URL and an ``api_key``
(plus an ``env_id`` for environment-scoped operations) and return the parsed
JSON payload.  No Qt, no QGIS, no plugin state — callers handle UI feedback.

This replaces the legacy flat, unauthenticated API.  Key differences:

* every request carries an ``X-API-Key`` header (raises on missing key);
* GRASS operations are scoped to an ``env_id`` (a server-side UUID binding a
  gisdb/location/mapset to the calling user);
* the old ``{"status": ..., "data": ...}`` envelope is gone — success is a bare
  JSON body, failure is an HTTP 4xx/5xx with ``{"detail": ...}`` which we surface
  as :class:`GrassApiError`.
"""
import requests

from groundtruther.configure import log_exception

_TIMEOUT_SHORT = 30    # list / metadata / query calls
_TIMEOUT_LONG = 300    # location creation, synchronous compute (e.g. /grass/exec)

DEFAULT_ENDPOINT = "https://api.fastgis.eu"


class GrassApiError(Exception):
    """Raised on any GRASS API failure (network, auth, or HTTP 4xx/5xx).

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


def _headers(api_key: str, *, json_body: bool = False) -> dict:
    h = {"accept": "application/json", "X-API-Key": api_key}
    if json_body:
        h["Content-Type"] = "application/json"
    return h


def _request(method: str, endpoint: str, path: str, api_key: str, *,
             params=None, json=None, files=None, timeout: int = _TIMEOUT_SHORT):
    """Perform an authenticated request and return the parsed JSON body.

    Raises :class:`GrassApiError` on missing endpoint/key, network failure, or
    a non-2xx response.  Returns ``None`` for an empty 2xx body.
    """
    if not (endpoint and endpoint.strip()):
        raise GrassApiError("No GRASS API endpoint configured")
    if not (api_key and api_key.strip()):
        raise GrassApiError("No GRASS API key configured")

    url = f"{endpoint.rstrip('/')}{path}"
    try:
        response = requests.request(
            method, url,
            headers=_headers(api_key, json_body=json is not None),
            params=params, json=json, files=files, timeout=timeout,
        )
    except requests.exceptions.RequestException as exc:
        log_exception(f"grass_api {method} {path}: network error", exc, warn=True)
        raise GrassApiError(f"Cannot reach the GRASS API server: {exc}") from exc

    if not response.ok:
        detail = _extract_detail(response)
        log_exception(
            f"grass_api {method} {path}: HTTP {response.status_code}: {detail}",
            GrassApiError(detail, response.status_code), warn=True)
        raise GrassApiError(detail, response.status_code)

    if not response.content:
        return None
    try:
        return response.json()
    except ValueError as exc:
        raise GrassApiError(f"Non-JSON response from {path}") from exc


def _extract_detail(response) -> str:
    """Best-effort extraction of an error message from a failed response."""
    try:
        body = response.json()
    except ValueError:
        return response.text[:300] or f"HTTP {response.status_code}"
    if isinstance(body, dict):
        detail = body.get("detail", body)
        # FastAPI 422 detail is a list of {loc,msg,type} dicts
        if isinstance(detail, list):
            return "; ".join(d.get("msg", str(d)) for d in detail)
        return str(detail)
    return str(body)


# --------------------------------------------------------------------------- #
# Identity                                                                     #
# --------------------------------------------------------------------------- #

def whoami(endpoint: str, api_key: str) -> dict:
    """Return the authenticated user (``GET /auth/me``); validates the key."""
    return _request("GET", endpoint, "/auth/me", api_key)


# --------------------------------------------------------------------------- #
# Environments                                                                 #
# --------------------------------------------------------------------------- #

def list_envs(endpoint: str, api_key: str) -> list[dict]:
    """Return the caller's environments (``GET /grass/env``)."""
    payload = _request("GET", endpoint, "/grass/env", api_key)
    return (payload or {}).get("environments", [])


def create_env_epsg(endpoint: str, api_key: str, *, epsg: int, location: str,
                    mapset: str = "PERMANENT", persist: bool = True,
                    db_driver: str | None = None, gisdb: str | None = None) -> dict:
    """Create a location+environment from an EPSG code (``POST /grass/env/epsg``)."""
    body = {"epsg": int(epsg), "location": location, "mapset": mapset,
            "persist": persist}
    if db_driver:
        body["db_driver"] = db_driver
    if gisdb:
        body["gisdb"] = gisdb
    return _request("POST", endpoint, "/grass/env/epsg", api_key,
                    json=body, timeout=_TIMEOUT_LONG)


def create_env_dataset(endpoint: str, api_key: str, *, file_path: str,
                       location: str, mapset: str = "PERMANENT",
                       persist: bool = True, db_driver: str | None = None) -> dict:
    """Create a location+environment from a georeferenced file (multipart upload)."""
    data = {"location": location, "mapset": mapset,
            "persist": str(persist).lower()}
    if db_driver:
        data["db_driver"] = db_driver
    try:
        with open(file_path, "rb") as fh:
            files = {"file": fh, **{k: (None, v) for k, v in data.items()}}
            return _request("POST", endpoint, "/grass/env/dataset", api_key,
                            files=files, timeout=_TIMEOUT_LONG)
    except FileNotFoundError as exc:
        raise GrassApiError(f"Dataset file not found: {file_path}") from exc


def create_mapset(endpoint: str, api_key: str, env_id: str, *, mapset: str,
                  copy_from_permanent: bool = False) -> dict:
    """Create a mapset in an env's location (``POST /grass/env/{id}/mapsets``).

    Returns a *new* env payload scoped to the created mapset.
    """
    body = {"mapset": mapset, "copy_from_permanent": copy_from_permanent}
    return _request("POST", endpoint, f"/grass/env/{env_id}/mapsets", api_key,
                    json=body, timeout=_TIMEOUT_LONG)


def delete_env(endpoint: str, api_key: str, env_id: str) -> dict:
    """Delete an environment (``DELETE /grass/env/{id}``)."""
    return _request("DELETE", endpoint, f"/grass/env/{env_id}", api_key)


# --------------------------------------------------------------------------- #
# Context / inventory                                                          #
# --------------------------------------------------------------------------- #

def gisenv(endpoint: str, api_key: str, env_id: str,
           variable: str | None = None) -> dict:
    """Return GRASS gisenv variables (``GET /grass/env/{id}/general/gisenv``)."""
    params = {"variable": variable} if variable else None
    payload = _request("GET", endpoint, f"/grass/env/{env_id}/general/gisenv",
                       api_key, params=params)
    return (payload or {}).get("variables", {})


def list_maps(endpoint: str, api_key: str, env_id: str, *,
              type: str = "raster,vector", mapset: str | None = None,
              pattern: str | None = None) -> list[str]:
    """List raster/vector map names (g.list via ``.../general/list``)."""
    params = {"type": type}
    if mapset:
        params["mapset"] = mapset
    if pattern:
        params["pattern"] = pattern
    payload = _request("GET", endpoint, f"/grass/env/{env_id}/general/list",
                       api_key, params=params)
    return (payload or {}).get("items", [])


def layers(endpoint: str, api_key: str, env_id: str) -> list[dict]:
    """Return typed layer metadata (``GET /grass/env/{id}/layers``)."""
    payload = _request("GET", endpoint, f"/grass/env/{env_id}/layers", api_key)
    return (payload or {}).get("layers", [])


# --------------------------------------------------------------------------- #
# Geo operations                                                               #
# --------------------------------------------------------------------------- #

def reproject(endpoint: str, api_key: str, env_id: str,
              points: list[dict], source_crs: str, target_crs: str) -> list[dict]:
    """Reproject ``[{"x":..,"y":..}, ...]`` (``POST /grass/env/{id}/reproject``).

    Returns ``[{"x","y","source","target"}, ...]``.
    """
    body = {"points": points, "source_crs": source_crs, "target_crs": target_crs}
    payload = _request("POST", endpoint, f"/grass/env/{env_id}/reproject",
                       api_key, json=body)
    return (payload or {}).get("points", [])


def sample(endpoint: str, api_key: str, env_id: str, *, layers: list[str],
           point: dict | None = None, points: list[dict] | None = None,
           crs: str | None = None, distance: float | None = None,
           include_empty: bool = True, fmt: str = "grouped") -> dict:
    """Sample raster/vector values at point(s) (``POST /grass/env/{id}/sample``).

    Replaces the old ``r_what``: pass input ``crs`` and the server reprojects to
    the env's native CRS automatically.  Raster values are under
    ``results.raster[].samples[].value``.
    """
    body: dict = {"layers": layers, "include_empty": include_empty, "format": fmt}
    if point is not None:
        body["point"] = point
    if points is not None:
        body["points"] = points
    if crs is not None:
        body["crs"] = crs
    if distance is not None:
        body["distance"] = distance
    return _request("POST", endpoint, f"/grass/env/{env_id}/sample", api_key,
                    json=body)


def set_region(endpoint: str, api_key: str, env_id: str, *,
               north: float | None = None, south: float | None = None,
               east: float | None = None, west: float | None = None,
               res: float | None = None, **extra) -> dict:
    """Set the computational region (``POST /grass/env/{id}/region``).

    Bounds must already be in the env's native CRS.  Any of north/south/east/
    west/res plus extras (rows, cols, nsres, ewres, align, raster, vector).
    """
    body = {k: v for k, v in
            dict(north=north, south=south, east=east, west=west, res=res,
                 **extra).items() if v is not None}
    if not body:
        raise GrassApiError("at least one region parameter is required")
    return _request("POST", endpoint, f"/grass/env/{env_id}/region", api_key,
                    json=body)


# --------------------------------------------------------------------------- #
# Modules (catalog, schema, execution)                                         #
# --------------------------------------------------------------------------- #

def list_modules(endpoint: str, api_key: str) -> list[dict]:
    """Return the module catalog (``GET /grass/modules``) as ``[{name,label,type}]``."""
    payload = _request("GET", endpoint, "/grass/modules", api_key)
    return (payload or {}).get("modules", [])


def describe_module(endpoint: str, api_key: str, module_name: str) -> dict:
    """Return a module's interface schema (``GET /grass/modules/{name}/schema``).

    The schema (``{module,label,description,parameters[],flags[],...}``) is what
    the dynamic PyQt form builder consumes.  Env-independent.
    """
    payload = _request("GET", endpoint, f"/grass/modules/{module_name}/schema",
                       api_key)
    return (payload or {}).get("schema", payload or {})


def submit_task(endpoint: str, api_key: str, env_id: str, module: str, *,
                args: list | None = None, flags: list | None = None,
                params: dict | None = None) -> dict:
    """Submit an async module run (``POST /grass/env/{id}/tasks``).

    Returns ``{task_id, state, ...}``.  Pass either ``args`` (precompiled) or
    structured ``flags``/``params``.
    """
    body: dict = {"module": module}
    if args:
        body["args"] = args
    if flags:
        body["flags"] = flags
    if params:
        body["params"] = params
    return _request("POST", endpoint, f"/grass/env/{env_id}/tasks", api_key,
                    json=body)


def get_task(endpoint: str, api_key: str, task_id: str) -> dict:
    """Poll task status/result (``GET /grass/tasks/{task_id}``)."""
    return _request("GET", endpoint, f"/grass/tasks/{task_id}", api_key)


def cancel_task(endpoint: str, api_key: str, task_id: str) -> dict:
    """Cancel/revoke a task (``DELETE /grass/tasks/{task_id}``)."""
    return _request("DELETE", endpoint, f"/grass/tasks/{task_id}", api_key)


def exec_module(endpoint: str, api_key: str, env_id: str, module: str,
                args: list[str]) -> dict:
    """Run a module synchronously via the generic ``POST /grass/exec``.

    Accepts pre-compiled CLI ``args`` (``["input=dem", "output=x", "-f"]``) and
    imposes no family-prefix restriction — used for non-prefixed modules such as
    ``grm_lsi``.
    """
    body = {"env_id": env_id, "module": module, "args": args}
    return _request("POST", endpoint, "/grass/exec", api_key, json=body,
                    timeout=_TIMEOUT_LONG)
