"""Tests for gt.deps_check — the runtime-dependency probe.

No QGIS, no Qt, and no dependency of the plugin's own needs to be installed:
every test either injects a probe or probes the standard library and a module
synthesised in ``tmp_path``.  That matters, because this check runs on exactly
the machine where nothing is installed.
"""
import sys
import textwrap

import pytest

from groundtruther.gt.deps_check import (
    REQUIREMENTS,
    REQUIREMENTS_TXT,
    DependencyReport,
    Requirement,
    check_dependencies,
    is_available,
    missing_modules,
    parse_requirements,
)


# --------------------------------------------------------------------------- #
# the probe itself                                                            #
# --------------------------------------------------------------------------- #
def test_is_available_on_the_standard_library():
    assert is_available("json") is True
    assert is_available("groundtruther_no_such_module_xyz") is False


def test_a_broken_find_spec_is_reported_as_absent(monkeypatch):
    """find_spec raises for several kinds of broken install; all mean 'absent'."""
    import groundtruther.gt.deps_check as deps_check

    for exc in (ImportError("boom"), ValueError("no spec"), AttributeError("x"),
                TypeError("x")):
        monkeypatch.setattr(deps_check.importlib.util, "find_spec",
                            lambda name, _e=exc: (_ for _ in ()).throw(_e))
        assert deps_check.is_available("anything") is False


def test_the_probe_does_not_import_the_module(tmp_path, monkeypatch):
    """The whole point: importing numba or cv2 can cost seconds or abort."""
    module = tmp_path / "gt_probe_canary.py"
    module.write_text(textwrap.dedent("""
        raise RuntimeError("importing this module is a test failure")
    """))
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.delitem(sys.modules, "gt_probe_canary", raising=False)

    assert is_available("gt_probe_canary") is True
    assert "gt_probe_canary" not in sys.modules


def test_missing_modules_filters_to_the_absent_ones():
    assert missing_modules(["json", "groundtruther_no_such_module_xyz", "os"]) == (
        "groundtruther_no_such_module_xyz",)


# --------------------------------------------------------------------------- #
# check_dependencies                                                          #
# --------------------------------------------------------------------------- #
def _probe_for(installed):
    """A probe that knows only *installed* import names."""
    return lambda module: module in installed


def test_everything_present():
    every_module = {r.module for r in REQUIREMENTS}
    report = check_dependencies(probe=_probe_for(every_module))

    assert report.ok is True
    assert report.can_load is True
    assert report.missing == ()
    assert len(report.present) == len(REQUIREMENTS)
    assert report.missing_packages == ()
    assert report.disabled_features == ()
    assert report.summary() == (
        f"all {len(REQUIREMENTS)} runtime dependencies are available")


def test_nothing_present_is_the_plugin_manager_install():
    report = check_dependencies(probe=_probe_for(set()))

    assert report.ok is False
    assert report.can_load is False
    assert report.present == ()
    assert len(report.missing) == len(REQUIREMENTS)
    assert "numpy" in report.missing_packages
    assert "prevent the plugin from loading at all" in report.summary()


def test_some_missing():
    installed = {r.module for r in REQUIREMENTS} - {"numba", "av"}
    report = check_dependencies(probe=_probe_for(installed))

    assert report.ok is False
    assert report.missing_packages == ("av", "numba")
    assert report.missing_modules == ("av", "numba")
    assert len(report.present) == len(REQUIREMENTS) - 2
    # av is guarded (the player falls back to OpenCV); numba is not.
    assert tuple(r.package for r in report.blocking_missing) == ("numba",)
    assert report.can_load is False
    assert "numba" in report.summary() and "av" in report.summary()


def test_only_an_optional_dependency_missing_still_loads():
    installed = {r.module for r in REQUIREMENTS} - {"av"}
    report = check_dependencies(probe=_probe_for(installed))

    assert report.ok is False
    assert report.blocking_missing == ()
    assert report.can_load is True
    assert "prevent the plugin from loading" not in report.summary()


def test_the_order_of_the_table_is_preserved():
    report = check_dependencies(probe=_probe_for(set()))
    assert report.missing_packages == tuple(r.package for r in REQUIREMENTS)


def test_requirements_can_be_injected():
    reqs = (Requirement("fictional-pkg", "fictional_mod", "nothing real", False),)
    report = check_dependencies(reqs, probe=_probe_for(set()))

    assert report.missing_packages == ("fictional-pkg",)
    assert report.disabled_features == ("nothing real",)


def test_disabled_features_deduplicates():
    reqs = (
        Requirement("a", "mod_a", "video playback", False),
        Requirement("b", "mod_b", "video playback", False),
        Requirement("c", "mod_c", "KML export", False),
    )
    report = check_dependencies(reqs, probe=_probe_for(set()))
    assert report.disabled_features == ("video playback", "KML export")


# --------------------------------------------------------------------------- #
# pip name vs import name                                                     #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("package,module", [
    ("opencv-python-headless", "cv2"),
    ("scikit-image", "skimage"),
    ("PyYAML", "yaml"),
    ("PyOpenGL", "OpenGL"),
    ("Jinja2", "jinja2"),
])
def test_the_known_name_mismatches_are_mapped_explicitly(package, module):
    by_package = {r.package: r.module for r in REQUIREMENTS}
    assert by_package[package] == module


def test_a_package_whose_import_name_differs_is_found_by_its_import_name():
    """Probing by pip name would report scikit-image and PyYAML as missing."""
    installed = {r.module for r in REQUIREMENTS}          # import names only
    report = check_dependencies(probe=_probe_for(installed))
    assert report.ok is True

    installed_by_pip_name = {r.package for r in REQUIREMENTS}
    mismatched = check_dependencies(probe=_probe_for(installed_by_pip_name))
    assert "scikit-image" in mismatched.missing_packages
    assert "PyYAML" in mismatched.missing_packages


# --------------------------------------------------------------------------- #
# the table has not drifted from dependencies/requirements.txt                #
# --------------------------------------------------------------------------- #
def test_the_table_matches_requirements_txt_exactly():
    listed = parse_requirements()
    assert listed, f"could not read {REQUIREMENTS_TXT}"
    assert tuple(r.package for r in REQUIREMENTS) == listed


def test_there_are_twenty_runtime_dependencies():
    assert len(REQUIREMENTS) == 20


def test_every_requirement_is_fully_described():
    for req in REQUIREMENTS:
        assert req.package and req.module and req.feature
        assert isinstance(req.blocks_load, bool)
    assert len({r.module for r in REQUIREMENTS}) == len(REQUIREMENTS)


def test_parse_requirements_strips_comments_and_specifiers(tmp_path):
    path = tmp_path / "requirements.txt"
    path.write_text(textwrap.dedent("""\
        # a comment
        numpy
        opencv-python-headless>=4.8
        av>=11  # trailing comment
        pydantic>=1.9

        requests[socks]==2.31.0
        pandas ; python_version >= "3.9"
    """))
    assert parse_requirements(str(path)) == (
        "numpy", "opencv-python-headless", "av", "pydantic", "requests", "pandas")


def test_parse_requirements_on_a_missing_file_is_empty(tmp_path):
    assert parse_requirements(str(tmp_path / "nope.txt")) == ()


# --------------------------------------------------------------------------- #
# D-008: importable with no QGIS                                              #
# --------------------------------------------------------------------------- #
def test_the_module_pulls_in_no_qgis_and_no_qt():
    import groundtruther.gt.deps_check  # noqa: F401 - already imported above

    assert not [name for name in sys.modules
                if name == "qgis" or name.startswith(("qgis.", "PyQt6.", "PyQt5."))]


def test_a_real_probe_over_the_real_table_returns_a_report():
    """Whatever this machine has installed, the probe must answer."""
    report = check_dependencies()
    assert isinstance(report, DependencyReport)
    assert len(report.present) + len(report.missing) == len(REQUIREMENTS)
