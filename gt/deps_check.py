"""Which of the plugin's runtime Python dependencies are actually importable.

Installed through the QGIS Plugin Manager, GroundTruther gets no ``.venv``:
``__init__.py``'s ``_bootstrap_venv()`` is a no-op when the venv is absent, and
QGIS 4 runs on a system Python where PEP-668 forbids ``pip install``.  Every one
of the 20 packages in ``dependencies/requirements.txt`` then fails to import.
This module is the *detection* half of making that failure honest: it reports
what is missing and what each missing package costs.  The dialog, the log line
and the disabling are the caller's (``publish-0-4`` WP-4).

Two rules shape the implementation:

* **Probe, never import.**  ``importlib.util.find_spec`` answers "is this
  installed?" without executing the package.  Importing ``numba`` or ``cv2``
  costs seconds and, with a mismatched native library, can abort the QGIS
  process outright — unacceptable in a check that runs at plugin load.
* **A pip name is not an import name.**  ``opencv-python-headless`` imports as
  ``cv2``, ``scikit-image`` as ``skimage``, ``PyYAML`` as ``yaml``,
  ``PyOpenGL`` as ``OpenGL``, ``Jinja2`` as ``jinja2``.  :data:`REQUIREMENTS`
  carries both names explicitly; nothing is derived from the other.

Usage::

    report = check_dependencies()
    if not report.ok:
        log(report.summary())              # WP-4 owns the real wording
        for req in report.missing:
            ...                            # req.package, req.feature

No Qt and no ``qgis`` here (D-008) — this check must be able to run before
anything else in the plugin works, and it is unit-tested without QGIS.
"""
from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

#: ``dependencies/requirements.txt``, the pip-side source of truth.  Read only
#: by :func:`parse_requirements` — never at import time, and never by
#: :func:`check_dependencies`, which must work inside a release zip whatever
#: happens to that file.
REQUIREMENTS_TXT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "dependencies", "requirements.txt")


@dataclass(frozen=True)
class Requirement:
    """One runtime dependency, in both of its names."""

    #: The name as written in ``dependencies/requirements.txt`` (no version
    #: specifier) — what a user types after ``pip install``.
    package: str
    #: The top-level module name to probe — what ``import`` takes.
    module: str
    #: What this package powers, for a message that says what stops working.
    feature: str
    #: True when a module-level ``import`` on the chain from
    #: ``groundtruther.py`` reaches this package, i.e. its absence stops the
    #: dock from being constructed at all, so no amount of feature-disabling
    #: rescues it.  False when every import of it is guarded by
    #: ``try/except ImportError`` or sits inside a function.
    blocks_load: bool


#: The 20 runtime dependencies of ``dependencies/requirements.txt``, in that
#: file's order.  ``osgeo``/``gdal``/``qgis`` are deliberately absent there (they
#: ship with QGIS) and so are absent here.
#:
#: ``blocks_load`` was read off the static module-level import graph at
#: ``master`` 4f4d6b5: **15 of the 20** are reached by an unguarded module-level
#: import, mostly through ``pygui/querybuilder_gui.py``, which the dock imports
#: eagerly.  Of the other five, ``av``, ``cv2`` and ``PyOpenGL`` are guarded by
#: ``try``/``except ImportError``, and ``pydantic`` and ``starlette`` are not on
#: the chain at all.  A test asserts the package set still matches
#: ``requirements.txt``; it cannot assert ``blocks_load``, so re-read the graph
#: if the import structure changes.  (An earlier version of this comment, and of
#: the plan's banner, said 16: a miscount in the prose, never in the tuple.)
REQUIREMENTS: tuple[Requirement, ...] = (
    Requirement("numpy", "numpy", "all numeric work", True),
    Requirement("pandas", "pandas", "image, video and annotation tables", True),
    Requirement("pyarrow", "pyarrow", "reading the Parquet metadata tables", True),
    Requirement("scikit-image", "skimage", "reading seafloor imagery", True),
    Requirement("scipy", "scipy", "nearest-image lookup (KDTree) and roughness", True),
    Requirement("opencv-python-headless", "cv2",
                "video decode fallback and the seabed ribbon", False),
    Requirement("av", "av",
                "preferred video decode backend (deinterlaces interlaced sources)",
                False),
    Requirement("pyqtgraph", "pyqtgraph", "the image viewer and every plot", True),
    Requirement("PyOpenGL", "OpenGL", "3-D views in the query builder", False),
    Requirement("matplotlib", "matplotlib", "query-builder figures", True),
    Requirement("plotnine", "plotnine", "query-builder statistical plots", True),
    Requirement("pyproj", "pyproj", "coordinate transforms for footprints", True),
    Requirement("simplekml", "simplekml", "KML export", True),
    Requirement("requests", "requests", "every call to the GRASS/FastGIS service", True),
    Requirement("geojson", "geojson", "GeoJSON output from the query builder", True),
    Requirement("PyYAML", "yaml", "reading and writing config/config.yaml", True),
    Requirement("pydantic", "pydantic", "validating the configuration", False),
    Requirement("starlette", "starlette",
                "declared in requirements.txt; no module imports it at 0.4", False),
    Requirement("Jinja2", "jinja2", "KML templating", True),
    Requirement("numba", "numba", "the point-in-polygon JIT used by the query builder",
                True),
)


def is_available(module: str) -> bool:
    """True when *module* can be imported, decided without importing it.

    ``find_spec`` raises rather than returning ``None`` for several kinds of
    broken installation (a missing parent package, a module whose ``__spec__``
    is ``None``, an import hook that fails).  All of those mean the same thing
    to a caller — the module is not usable — so they are reported as absence.
    """
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, AttributeError, ValueError, TypeError):
        return False


@dataclass(frozen=True)
class DependencyReport:
    """The outcome of one probe pass over a set of requirements."""

    present: tuple[Requirement, ...]
    missing: tuple[Requirement, ...]

    @property
    def ok(self) -> bool:
        """True when nothing is missing."""
        return not self.missing

    @property
    def blocking_missing(self) -> tuple[Requirement, ...]:
        """Missing requirements whose absence stops the plugin loading at all."""
        return tuple(r for r in self.missing if r.blocks_load)

    @property
    def can_load(self) -> bool:
        """True when nothing *required to construct the dock* is missing."""
        return not self.blocking_missing

    @property
    def missing_packages(self) -> tuple[str, ...]:
        """pip names of what is missing — what a user would install."""
        return tuple(r.package for r in self.missing)

    @property
    def missing_modules(self) -> tuple[str, ...]:
        """Import names of what is missing."""
        return tuple(r.module for r in self.missing)

    @property
    def disabled_features(self) -> tuple[str, ...]:
        """One line per missing requirement: what stops working, deduplicated."""
        seen: list[str] = []
        for req in self.missing:
            if req.feature not in seen:
                seen.append(req.feature)
        return tuple(seen)

    def summary(self) -> str:
        """A one-line plain-text statement of the result.

        A fallback for a log line; the user-facing wording is WP-4's.
        """
        if self.ok:
            return (f"all {len(self.present)} runtime dependencies are available")
        head = (f"{len(self.missing)} of {len(self.present) + len(self.missing)} "
                f"runtime dependencies are missing: "
                f"{', '.join(self.missing_packages)}")
        blocking = self.blocking_missing
        if blocking:
            head += (f" — {len(blocking)} of them "
                     f"({', '.join(r.package for r in blocking)}) "
                     f"prevent the plugin from loading at all")
        return head


def check_dependencies(
    requirements: Sequence[Requirement] | None = None,
    probe: Callable[[str], bool] | None = None,
) -> DependencyReport:
    """Probe *requirements* and report what is present and what is missing.

    *requirements* defaults to :data:`REQUIREMENTS`, *probe* to
    :func:`is_available`; both are injectable so a test can describe a machine
    it is not running on.  Each module is probed once, in the declared order.
    """
    reqs = tuple(REQUIREMENTS if requirements is None else requirements)
    check = is_available if probe is None else probe
    present, missing = [], []
    for req in reqs:
        (present if check(req.module) else missing).append(req)
    return DependencyReport(tuple(present), tuple(missing))


def parse_requirements(path: str | None = None) -> tuple[str, ...]:
    """pip names listed in ``dependencies/requirements.txt``, in file order.

    Comments, blank lines and version specifiers are stripped.  This exists so a
    test can prove :data:`REQUIREMENTS` has not drifted from the file; the
    runtime check never reads the file, because the mapping to import names
    cannot be derived from it anyway.
    """
    target = REQUIREMENTS_TXT if path is None else path
    if not os.path.isfile(target):
        return ()
    names: list[str] = []
    with open(target, "r", encoding="utf-8") as handle:
        for raw in handle:
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            name = line
            for sep in ("===", "~=", ">=", "<=", "==", "!=", ">", "<", "[", ";"):
                name = name.split(sep, 1)[0]
            name = name.strip()
            if name:
                names.append(name)
    return tuple(names)


def missing_modules(modules: Iterable[str]) -> tuple[str, ...]:
    """Of *modules*, those that are not importable — a probe with no table.

    For a caller that knows exactly which imports a single feature needs.
    """
    return tuple(m for m in modules if not is_available(m))
