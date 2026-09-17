"""Per-key validation of the GroundTruther YAML configuration.

Stateless and Qt-free (see ``CLAUDE.md``) so it can be unit-tested without
QGIS.  :func:`check_settings` walks the settings dict produced by
``configure.load_config`` and returns a :class:`ConfigReport` that grades every
key **individually**:

* ``errors``   — the plugin genuinely cannot run without them
  (``HabCam.imagepath``, ``HabCam.imagemetadata``).
* ``warnings`` — an *optional* key that is set but unusable (a stale soundings
  file, an export directory on an unmounted drive, a non-numeric ``epsg``, …).
  These degrade one feature; they must never stop the dock from opening.

Unset optional keys are silent — that is the normal state of a partially
configured install.

The contrast with :mod:`groundtruther.config_model` matters: the pydantic model
validates the config as *one object*, so a single stale path raises and
invalidates everything (the bug this module exists to fix).  The model stays the
schema of record — ``tests/unit/test_config_check.py`` asserts that :data:`SPEC`
covers exactly its fields, so the two cannot silently drift.

:func:`degrade` turns a report into a *usable* settings dict: only the offending
keys are blanked, everything the user got right is kept.
"""
from __future__ import annotations

import copy
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

import yaml

__all__ = [
    "Finding", "ConfigReport", "check_settings", "degrade",
    "merge_settings", "write_settings",
    "as_int", "as_float", "as_bool", "as_path_str",
    "ERROR", "WARNING", "SPEC", "SECTIONS",
]

ERROR = "error"
WARNING = "warning"

#: Mount points under which a missing path usually means "drive not plugged in".
REMOVABLE_PREFIXES = ("/run/media", "/media", "/mnt", "/Volumes")


# ---------------------------------------------------------------------------
# Spec — one entry per config key
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class KeySpec:
    """How one config key is validated and what it degrades to.

    Attributes:
        section: Top-level YAML section, e.g. ``"HabCam"``.
        name: Key inside that section, e.g. ``"imagepath"``.
        kind: One of ``dir``, ``file``, ``parent_dir``, ``url``, ``bool``,
            ``int``, ``float``, ``str``.
        required: When true an unset or invalid value is an :data:`ERROR`;
            otherwise it is a :data:`WARNING` (and silent when unset).
        blank: Value :func:`degrade` writes when this key fails validation —
            chosen so existing consumers take their "not configured" branch.
        minimum / maximum: Inclusive numeric bounds (``int`` / ``float`` only).
    """

    section: str
    name: str
    kind: str
    required: bool = False
    blank: Any = ""
    minimum: float | None = None
    maximum: float | None = None

    @property
    def key(self) -> str:
        return f"{self.section}.{self.name}"


SPEC: tuple[KeySpec, ...] = (
    # --- HabCam: the only genuinely required section -----------------------
    KeySpec("HabCam", "imagepath", "dir", required=True),
    KeySpec("HabCam", "imagemetadata", "file", required=True),
    KeySpec("HabCam", "imageannotation", "file"),
    # --- Mbes --------------------------------------------------------------
    KeySpec("Mbes", "soundings", "file"),
    KeySpec("Mbes", "reference_surface", "file"),
    # --- Export ------------------------------------------------------------
    KeySpec("Export", "kmldir", "dir"),
    # --- Processing --------------------------------------------------------
    KeySpec("Processing", "gpu_avaibility", "bool", blank=False),
    KeySpec("Processing", "grass_api_endpoint", "url"),
    KeySpec("Processing", "grass_api_key", "str"),
    # --- Filesystem --------------------------------------------------------
    KeySpec("Filesystem", "filemanager", "file"),
    # --- Video -------------------------------------------------------------
    KeySpec("Video", "videofile", "file"),
    KeySpec("Video", "videometadata", "file"),
    KeySpec("Video", "videoannotation", "file"),
    # --- Session (the file is created on first save, so only its parent
    #     directory has to exist) ------------------------------------------
    KeySpec("Session", "groundtruther_project", "parent_dir"),
    # --- Roughness ---------------------------------------------------------
    KeySpec("Roughness", "base_url", "url"),
    KeySpec("Roughness", "route", "str"),
    KeySpec("Roughness", "direct_url", "url"),
    KeySpec("Roughness", "res_mm", "float", blank=None, minimum=0.0),
    KeySpec("Roughness", "n_water", "float", blank=None, minimum=0.0),
    KeySpec("Roughness", "georeference", "bool", blank=False),
    KeySpec("Roughness", "epsg", "int", blank=None, minimum=1024, maximum=999999),
    KeySpec("Roughness", "heading_offset_deg", "float", blank=None),
    KeySpec("Roughness", "mirror", "bool", blank=False),
    KeySpec("Roughness", "dem_max_side", "int", blank=None, minimum=1),
    KeySpec("Roughness", "dem_trim_border", "int", blank=None, minimum=0),
    KeySpec("Roughness", "dem_clip_sigma", "float", blank=None, minimum=0.0),
    KeySpec("Roughness", "dem_erode", "int", blank=None, minimum=0),
)

#: Section order used when building a complete settings skeleton.
SECTIONS: tuple[str, ...] = tuple(
    dict.fromkeys(spec.section for spec in SPEC))


# ---------------------------------------------------------------------------
# Report types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Finding:
    """One problem with one config key.

    Attributes:
        key: Dotted config key, e.g. ``"HabCam.imagepath"``.
        value: The offending value as it appeared in the file.
        reason: Human-readable explanation, already carrying any hint.
        severity: :data:`ERROR` or :data:`WARNING`.
    """

    key: str
    value: Any
    reason: str
    severity: str = WARNING

    def __str__(self) -> str:
        return f"{self.key}: {self.reason}"


@dataclass
class ConfigReport:
    """Result of :func:`check_settings` — findings split by severity."""

    errors: list[Finding] = field(default_factory=list)
    warnings: list[Finding] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True when nothing *blocks* startup (warnings are allowed)."""
        return not self.errors

    @property
    def findings(self) -> list[Finding]:
        """Errors first, then warnings."""
        return [*self.errors, *self.warnings]

    def bad_keys(self) -> list[str]:
        """Every key that failed, errors first."""
        return [f.key for f in self.findings]

    def summary(self, include_warnings: bool = True) -> str:
        """Render the findings as one bulleted line per key."""
        items = self.findings if include_warnings else self.errors
        return "\n".join(f"  • {f}" for f in items)

    def message(self) -> str:
        """A user-facing message naming the offending keys and their values.

        Empty when there is nothing to report, so callers can use it directly
        as a "show a dialog?" test.
        """
        parts: list[str] = []
        if self.errors:
            parts.append(
                "GroundTruther cannot start with the current configuration.\n"
                "Open Settings (wizard icon) and fix:\n"
                + self.summary(include_warnings=False))
        if self.warnings:
            header = ("These optional settings are unusable and their features "
                      "are disabled:\n" if self.errors else
                      "Some optional settings are unusable; the features that "
                      "use them are disabled:\n")
            parts.append(header + "\n".join(
                f"  • {f}" for f in self.warnings))
        return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Value helpers — also used by consumers to coerce config values safely
# ---------------------------------------------------------------------------

def _is_unset(value: Any) -> bool:
    """True for ``None`` and empty/whitespace-only strings."""
    return value is None or (isinstance(value, str) and not value.strip())


def as_path_str(value: Any) -> str:
    """Return *value* as a path string — ``""`` when unset.

    Guards ``Path(None)`` / f-string interpolation of ``None`` at the call
    sites that read paths straight out of the settings dict.
    """
    if _is_unset(value):
        return ""
    return str(value).strip() if isinstance(value, str) else str(value)


def as_int(value: Any, default: int | None = None) -> int | None:
    """Best-effort ``int(value)``, falling back to *default*.

    Accepts ints, floats and numeric strings; anything else (``None``, ``""``,
    ``"abc"``, a list) yields *default* instead of raising.  *default* may be
    ``None`` for callers that mean "leave it unset".
    """
    if isinstance(value, bool) or _is_unset(value):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default


def as_float(value: Any, default: float | None = None) -> float | None:
    """Best-effort ``float(value)``, falling back to *default*.

    *default* may be ``None`` for callers that mean "leave it unset".
    """
    if isinstance(value, bool) or _is_unset(value):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_bool(value: Any, default: bool = False) -> bool:
    """Interpret *value* as a boolean, falling back to *default*.

    Understands YAML-ish strings (``yes``/``no``/``on``/``off``/``true``/
    ``false``/``1``/``0``) as well as real bools and numbers.
    """
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in ("true", "yes", "on", "1"):
            return True
        if text in ("false", "no", "off", "0", ""):
            return False
    return default


def _removable_hint(path: str) -> str:
    """``" (the drive may not be mounted)"`` for paths on removable media."""
    try:
        resolved = os.path.abspath(os.path.expanduser(path))
    except (TypeError, ValueError):
        return ""
    for prefix in REMOVABLE_PREFIXES:
        if resolved == prefix or resolved.startswith(prefix + os.sep):
            return " (the drive may not be mounted)"
    return ""


def _type_name(value: Any) -> str:
    return type(value).__name__


# ---------------------------------------------------------------------------
# Per-key checks
# ---------------------------------------------------------------------------

def _check_path(spec: KeySpec, value: Any) -> str | None:
    """Return a failure reason for a ``dir`` / ``file`` / ``parent_dir`` key."""
    if not isinstance(value, (str, os.PathLike)):
        return f"expected a path, got {_type_name(value)}: {value!r}"
    path = Path(os.path.expanduser(str(value).strip()))
    if spec.kind == "parent_dir":
        parent = path.parent
        if not parent.exists():
            return (f"parent directory does not exist: {str(parent)!r}"
                    + _removable_hint(str(parent)))
        return None
    if not path.exists():
        what = "directory" if spec.kind == "dir" else "file"
        return f"{what} does not exist: {str(path)!r}" + _removable_hint(str(path))
    if spec.kind == "dir" and not path.is_dir():
        return f"not a directory: {str(path)!r}"
    if spec.kind == "file" and not path.is_file():
        return f"not a file: {str(path)!r}"
    if not os.access(path, os.R_OK):
        return f"not readable: {str(path)!r}"
    return None


def _check_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return f"expected a URL string, got {_type_name(value)}: {value!r}"
    parsed = urlparse(value.strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return f"not a valid http(s) URL: {value!r}"
    return None


def _check_number(spec: KeySpec, value: Any) -> str | None:
    want = "an integer" if spec.kind == "int" else "a number"
    if isinstance(value, bool):
        return f"expected {want}, got bool: {value!r}"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return f"expected {want}, got {_type_name(value)}: {value!r}"
    if spec.kind == "int" and number != int(number):
        return f"expected {want}, got {value!r}"
    if spec.minimum is not None and number < spec.minimum:
        return f"below the minimum {_fmt_num(spec.minimum)}: {value!r}"
    if spec.maximum is not None and number > spec.maximum:
        return f"above the maximum {_fmt_num(spec.maximum)}: {value!r}"
    return None


def _fmt_num(number: float) -> str:
    return str(int(number)) if float(number).is_integer() else str(number)


def _check_bool(value: Any) -> str | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, str) and value.strip().lower() in (
            "true", "false", "yes", "no", "on", "off", "1", "0"):
        return None
    if isinstance(value, (int, float)) and value in (0, 1):
        return None
    return f"expected true or false, got {_type_name(value)}: {value!r}"


def _check_str(value: Any) -> str | None:
    if isinstance(value, str):
        return None
    return f"expected a string, got {_type_name(value)}: {value!r}"


_CHECKERS = {
    "dir": _check_path,
    "file": _check_path,
    "parent_dir": _check_path,
}


def _check_value(spec: KeySpec, value: Any) -> str | None:
    """Dispatch *value* to the checker for ``spec.kind``."""
    if spec.kind in _CHECKERS:
        return _CHECKERS[spec.kind](spec, value)
    if spec.kind == "url":
        return _check_url(value)
    if spec.kind in ("int", "float"):
        return _check_number(spec, value)
    if spec.kind == "bool":
        return _check_bool(value)
    return _check_str(value)


# ---------------------------------------------------------------------------
# Reading / writing the config document
# ---------------------------------------------------------------------------

def merge_settings(existing, updates):
    """Deep-merge *updates* into *existing* and return a new dict.

    Section by section, key by key: keys the Settings dialog does not know
    about (the whole ``Roughness`` section, ``Video.videoannotation`` when the
    dialog has no widget for it, …) survive untouched.  ``existing`` may be
    ``None`` (no config file yet).
    """
    merged = copy.deepcopy(existing) if isinstance(existing, dict) else {}
    for section, values in (updates or {}).items():
        if not isinstance(values, dict):
            merged[section] = values
            continue
        current = merged.get(section)
        if not isinstance(current, dict):
            current = {}
        current.update(values)
        merged[section] = current
    return merged


def write_settings(config_path, settings):
    """Write *settings* to *config_path* as YAML.

    ``yaml.safe_dump`` quotes whatever needs quoting, so a path containing
    ``:`` or ``#`` round-trips — unlike the raw ``key: {{value}}`` template
    this replaced.  ``sort_keys=False`` keeps the section order of the dict.
    """
    with open(config_path, "w", encoding="utf8") as yaml_file:
        yaml.safe_dump(settings, yaml_file, sort_keys=False,
                       default_flow_style=False, allow_unicode=True)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def check_settings(settings: Any, spec: Iterable[KeySpec] = SPEC) -> ConfigReport:
    """Grade every key of *settings* individually.

    Parameters
    ----------
    settings:
        The raw dict from ``configure.load_config`` (``None`` is tolerated).
    spec:
        Key specification to apply; defaults to :data:`SPEC`.

    Returns
    -------
    ConfigReport
        ``report.errors`` blocks startup, ``report.warnings`` degrades a single
        feature.  An unset *optional* key produces no finding at all.
    """
    report = ConfigReport()
    if settings is None:
        report.errors.append(Finding(
            "config", None,
            "no configuration loaded (missing or unparseable config.yaml)",
            ERROR))
        return report
    if not isinstance(settings, dict):
        report.errors.append(Finding(
            "config", settings,
            f"expected a mapping of sections, got {_type_name(settings)}", ERROR))
        return report

    bad_sections: set[str] = set()
    for section in SECTIONS:
        body = settings.get(section, None)
        if body is not None and not isinstance(body, dict):
            bad_sections.add(section)
            required = any(s.required for s in SPEC if s.section == section)
            finding = Finding(
                section, body,
                f"expected a mapping of settings, got {_type_name(body)}",
                ERROR if required else WARNING)
            (report.errors if required else report.warnings).append(finding)

    for item in spec:
        if item.section in bad_sections:
            continue
        body = settings.get(item.section) or {}
        value = body.get(item.name, None)
        if _is_unset(value):
            if item.required:
                report.errors.append(Finding(
                    item.key, value, "not set", ERROR))
            continue
        reason = _check_value(item, value)
        if reason is None:
            continue
        severity = ERROR if item.required else WARNING
        finding = Finding(item.key, value, reason, severity)
        (report.errors if severity == ERROR else report.warnings).append(finding)

    return report


def degrade(settings: Any, report: ConfigReport,
            spec: Iterable[KeySpec] = SPEC) -> dict:
    """Return a *usable* copy of *settings* with only the bad keys blanked.

    This is the heart of the fix: a stale ``HabCam.imagepath`` blanks that one
    key and leaves ``Mbes.soundings`` — and the MBES query builder — working.
    Every section named in :data:`SPEC` is present in the result, so
    ``settings["Video"]["videofile"]``-style lookups elsewhere cannot raise
    ``KeyError``.
    """
    specs = list(spec)
    out: dict = copy.deepcopy(settings) if isinstance(settings, dict) else {}
    for item in specs:
        if not isinstance(out.get(item.section), dict):
            out[item.section] = {}
    bad = set(report.bad_keys())
    for item in specs:
        section = out[item.section]
        if item.key in bad or item.section in bad:
            section[item.name] = item.blank
        elif item.name not in section:
            section[item.name] = item.blank
    return out
