"""Stateless HTTP client for the GroundTruther GRASS REST API.

All methods are pure functions that take an ``endpoint`` URL and a
``gisenv`` dict (as returned by the ``/api/gisenv`` endpoint) and
return the parsed JSON payload, or raise on error.  No Qt, no QGIS,
no plugin state — callers handle the UI feedback.
"""
import requests

from groundtruther.configure import log_exception

_HEADERS = {
    "accept": "application/json",
    "Content-Type": "application/json",
}

_HEADERS_FORM = {
    "accept": "application/json",
    "content-type": "application/x-www-form-urlencoded",
}

_TIMEOUT_SHORT = 30   # list / metadata calls
_TIMEOUT_LONG  = 300  # compute-heavy module calls


def _location_block(gisenv: dict) -> dict:
    """Return the standard ``location`` sub-dict expected by the API."""
    return {
        "location_name": gisenv["LOCATION_NAME"],
        "mapset_name":   gisenv["MAPSET"],
        "gisdb":         gisenv["GISDBASE"],
    }


def get_raster_list(endpoint: str, gisenv: dict) -> list[str]:
    """Return the list of raster layer names in the current GRASS mapset.

    Returns an empty list on any error (already logged).
    """
    params = {
        "location_name": gisenv["LOCATION_NAME"],
        "mapset_name":   gisenv["MAPSET"],
        "gisdb":         gisenv["GISDBASE"],
    }
    try:
        response = requests.get(
            f"{endpoint}/api/get_rvg_list",
            params=params, headers=_HEADERS_FORM, timeout=_TIMEOUT_SHORT,
        )
        return response.json().get("data", {}).get("raster", [])
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
        log_exception("get_raster_list: network error", exc, warn=True)
        return []
    except (ValueError, KeyError) as exc:
        log_exception("get_raster_list: unexpected API response", exc)
        return []


def r_what(endpoint: str, gisenv: dict, layers: list[str],
           lat: float, lon: float, lonlat: bool = False) -> dict | None:
    """Query raster values at a point via ``/api/r_what``.

    Returns the parsed payload dict, or ``None`` on any error.
    """
    params = {"lonlat": "true" if lonlat else "false"}
    json_data = {
        "location": _location_block(gisenv),
        "coors": [lon, lat],
        "grass_layers": layers,
    }
    try:
        response = requests.post(
            f"{endpoint}/api/r_what",
            params=params, headers=_HEADERS, json=json_data, timeout=_TIMEOUT_SHORT,
        )
        return response.json()
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
        log_exception("r_what: network error", exc, warn=True)
        return None
    except ValueError as exc:
        log_exception("r_what: non-JSON response", exc)
        return None


def m_proj(endpoint: str, gisenv: dict,
           coords: list[list[float]]) -> list[list[float]] | None:
    """Reproject a list of [lon, lat] pairs via ``/api/m_proj``.

    Returns the projected coordinate list, or ``None`` on any error.
    """
    json_data = {
        "location": _location_block(gisenv),
        "coors": coords,
    }
    try:
        response = requests.post(
            f"{endpoint}/api/m_proj",
            headers=_HEADERS, json=json_data, timeout=_TIMEOUT_SHORT,
        )
        return response.json()["data"]
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
        log_exception("m_proj: network error", exc, warn=True)
        return None
    except (ValueError, KeyError) as exc:
        log_exception("m_proj: unexpected API response", exc)
        return None


def set_region_bounds(endpoint: str, gisenv: dict,
                      north: float, south: float,
                      east: float, west: float) -> dict | None:
    """Set the GRASS computational region to a bounding box.

    Returns the parsed payload dict, or ``None`` on any error.
    """
    json_data = {
        "location": _location_block(gisenv),
        "bounds": {"n": north, "s": south, "e": east, "w": west},
        "resolution": {"resolution": 0},
    }
    try:
        response = requests.post(
            f"{endpoint}/api/set_region_bounds",
            headers=_HEADERS, json=json_data, timeout=_TIMEOUT_SHORT,
        )
        return response.json()
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
        log_exception("set_region_bounds: network error", exc, warn=True)
        return None
    except (ValueError, KeyError) as exc:
        log_exception("set_region_bounds: unexpected API response", exc)
        return None


def get_location_list(endpoint: str, gisdb: str) -> dict:
    """Return the dict of locations (and their mapsets) from the API.

    Returns ``{'status': 'FAILED', 'data': <reason>}`` on any error.
    Never raises.
    """
    params = {"gisdb": gisdb}
    try:
        response = requests.get(
            f"{endpoint}/api/get_location_list",
            params=params, headers=_HEADERS_FORM, timeout=_TIMEOUT_SHORT,
        )
        return response.json()
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
        log_exception("get_location_list: network error", exc, warn=True)
        return {"status": "FAILED", "data": str(exc)}
    except ValueError as exc:
        log_exception("get_location_list: non-JSON response", exc)
        return {"status": "FAILED", "data": str(exc)}


def create_mapset(endpoint: str, gisdb: str, location_name: str,
                  mapset_name: str, overwrite: bool = False) -> dict:
    """Create a new GRASS mapset via the API.

    Returns the parsed payload dict, or a FAILED dict on error.
    """
    params = {
        "location_name": location_name,
        "mapset_name": mapset_name,
        "gisdb": gisdb,
        "overwrite_mapset": "true" if overwrite else "false",
    }
    try:
        response = requests.get(
            f"{endpoint}/api/create_mapset",
            params=params, headers=_HEADERS_FORM, timeout=_TIMEOUT_SHORT,
        )
        return response.json()
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
        log_exception("create_mapset: network error", exc, warn=True)
        return {"status": "FAILED", "data": str(exc)}
    except ValueError as exc:
        log_exception("create_mapset: non-JSON response", exc)
        return {"status": "FAILED", "data": str(exc)}


def create_location_epsg(endpoint: str, gisdb: str, location_name: str,
                         epsg_code: str,
                         mapset_name: str = "PERMANENT",
                         overwrite_location: bool = False,
                         overwrite_mapset: bool = False) -> dict:
    """Create a new GRASS location from an EPSG code.

    Returns the parsed payload dict, or a FAILED dict on error.
    """
    params = {
        "location_name": location_name,
        "mapset_name": mapset_name,
        "gisdb": gisdb,
        "epsg_code": epsg_code,
        "overwrite_location": "true" if overwrite_location else "false",
        "overwrite_mapset": "true" if overwrite_mapset else "false",
    }
    try:
        response = requests.get(
            f"{endpoint}/api/create_location_epsg",
            params=params, headers=_HEADERS_FORM, timeout=60,
        )
        return response.json()
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
        log_exception("create_location_epsg: network error", exc, warn=True)
        return {"status": "FAILED", "data": str(exc)}
    except ValueError as exc:
        log_exception("create_location_epsg: non-JSON response", exc)
        return {"status": "FAILED", "data": str(exc)}


def create_location_georef(endpoint: str, gisdb: str, location_name: str,
                            georef_path: str,
                            mapset_name: str = "PERMANENT",
                            output_raster_layer: str = "",
                            overwrite_location: bool = False,
                            overwrite_mapset: bool = False) -> dict:
    """Create a new GRASS location from a georeferenced file (multipart upload).

    Returns the parsed payload dict, or a FAILED dict on error.
    """
    params = {
        "location_name": location_name,
        "mapset_name": mapset_name,
        "gisdb": gisdb,
        "overwrite_location": "true" if overwrite_location else "false",
        "overwrite_mapset": "true" if overwrite_mapset else "false",
        "output_raster_layer": output_raster_layer,
    }
    headers = {"accept": "application/json"}
    try:
        with open(georef_path, "rb") as fh:
            files = {"georef": fh}
            response = requests.post(
                f"{endpoint}/api/create_location_file",
                params=params, headers=headers, files=files,
            )
        return response.json()
    except FileNotFoundError as exc:
        log_exception("create_location_georef: file not found", exc, warn=True)
        return {"status": "FAILED", "data": str(exc)}
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
        log_exception("create_location_georef: network error", exc, warn=True)
        return {"status": "FAILED", "data": str(exc)}
    except ValueError as exc:
        log_exception("create_location_georef: non-JSON response", exc)
        return {"status": "FAILED", "data": str(exc)}


def set_gisenv(endpoint: str, gisdb: str, location_name: str,
               mapset_name: str) -> dict:
    """Activate a GRASS location/mapset via the ``/api/gisenv`` endpoint.

    Returns the parsed payload dict (caller checks ``payload['status']``).
    Returns a FAILED dict on any network error.
    """
    params = {
        "location_name": location_name,
        "mapset_name": mapset_name,
        "gisdb": gisdb,
    }
    headers = {"accept": "application/json"}
    try:
        response = requests.get(
            f"{endpoint}/api/gisenv",
            params=params, headers=headers, timeout=_TIMEOUT_SHORT,
        )
        return response.json()
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
        log_exception("set_gisenv: network error", exc, warn=True)
        return {"status": "FAILED", "data": str(exc)}
    except ValueError as exc:
        log_exception("set_gisenv: non-JSON response", exc)
        return {"status": "FAILED", "data": str(exc)}


def run_module(endpoint: str, module_name: str, params: dict) -> dict:
    """POST to ``/api/<module_name>`` and return the parsed JSON payload.

    Returns ``{'status': 'FAILED', 'data': <reason>}`` on network errors
    and ``{'status': 'SUCCESS'}`` when the response is not JSON (binary
    output modules).  Never raises.
    """
    headers = {
        "accept": "application/json",
        "content-type": "application/x-www-form-urlencoded",
    }
    try:
        response = requests.post(
            f"{endpoint}/api/{module_name}",
            headers=headers, params=params, timeout=_TIMEOUT_LONG,
        )
        return response.json()
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
        log_exception(f"run_module({module_name}): network error", exc, warn=True)
        return {"status": "FAILED", "data": str(exc)}
    except ValueError as exc:
        log_exception(f"run_module({module_name}): non-JSON response (binary output?)", exc, warn=True)
        return {"status": "SUCCESS"}
