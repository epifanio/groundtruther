"""What the plugin says at startup when its dependencies are not installed.

The subject is the top-level ``__init__.py``: the venv name it looks for, and
the wording it hands the one dialog.  ``conftest.py`` registers
``groundtruther`` as a namespace package *without* executing ``__init__.py``
(that is what keeps ``gt/`` imports QGIS-free), so this loads the file directly
from its path under a private module name.  That works because nothing at its
module level needs the package context: the relative imports are all inside
:func:`classFactory`, which is not called here — calling it would import the
dock, and so QGIS.
"""
import importlib.util
import pathlib
import sys

import pytest

from groundtruther.gt.deps_check import check_dependencies

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


@pytest.fixture(scope="module")
def plugin_init():
    """The top-level ``__init__.py``, loaded on its own."""
    spec = importlib.util.spec_from_file_location(
        "groundtruther_plugin_init", ROOT / "__init__.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    yield module
    del sys.modules[spec.name]


def _report(missing_modules):
    """A report in which exactly *missing_modules* are absent."""
    return check_dependencies(probe=lambda m: m not in set(missing_modules))


def test_the_venv_name_is_the_one_setup_wsl_creates(plugin_init):
    """The two halves of the convention must name the same directory.

    ``setup_wsl.sh --venv`` used to create ``gtenv`` while this looked for
    ``.venv``, so the documented fallback install produced a venv the plugin
    never loaded.
    """
    assert plugin_init.VENV_DIRNAME == ".venv"
    # Comments are allowed to mention the old name — they explain the bug.
    commands = "\n".join(
        line for line in (ROOT / "setup_wsl.sh").read_text().splitlines()
        if not line.lstrip().startswith("#"))
    assert "/.venv" in commands
    assert "gtenv" not in commands


def test_the_bootstrap_reports_whether_it_found_anything(plugin_init):
    """It returns the directory it added, or None — and never raises.

    ``None`` is the Plugin Manager case, and the thing the log line
    distinguishes: a silent no-op was the whole bug.
    """
    expected = (ROOT / ".venv" / "lib"
                / f"python{sys.version_info.major}.{sys.version_info.minor}"
                / "site-packages")
    result = plugin_init._bootstrap_venv()
    if expected.is_dir():
        assert result == str(expected)
    else:
        assert result is None


def test_the_message_names_every_missing_package_not_just_the_first(plugin_init):
    """The import chain dies at the first one; the message must name them all.

    Measured on QGIS 4.2.1 (macOS), the first missing module is ``pyqtgraph``,
    not ``numpy`` — which is why this list is computed, never hard-coded.
    """
    report = _report(["pyqtgraph", "numba", "plotnine"])
    html, details = plugin_init._missing_dependency_message(report)
    for package in ("pyqtgraph", "numba", "plotnine"):
        assert package in html
        assert package in details
    assert "3 of the 20" in html


def test_the_message_counts_only_what_actually_blocks_the_load(plugin_init):
    """Leading with the whole missing count would overstate the cause.

    The macOS case: 10 of the 20 missing, of which only 6 block.  The headline
    must say 6, and the other 4 must be named as feature losses instead.
    """
    report = _report(["pyqtgraph", "numba", "av", "cv2"])
    html, details = plugin_init._missing_dependency_message(report)
    assert "2 of the 20" in html          # pyqtgraph + numba block
    assert "2 more are missing" in html   # av + cv2 only disable features
    assert "REQUIRED  pyqtgraph" in details
    assert "optional  av" in details


def test_the_message_says_what_each_missing_package_costs(plugin_init):
    """The details pane carries the feature, so the user knows what it buys."""
    report = _report(["skimage"])
    _, details = plugin_init._missing_dependency_message(report)
    assert "scikit-image" in details        # the pip name, what you install
    assert "import skimage" in details      # the import name, what failed
    assert "reading seafloor imagery" in details


def test_the_message_links_the_install_docs(plugin_init):
    """A user told what is missing still needs to be told what to do."""
    html, _ = plugin_init._missing_dependency_message(_report(["numpy"]))
    expected = plugin_init.install_docs_url()
    assert expected in html
    assert f'href="{expected}"' in html


@pytest.mark.parametrize("platform, page", [
    ("darwin", "macos/"),
    ("win32", "windows/"),
    ("linux", "linux/"),
    ("linux2", "linux/"),          # older builds still report this
])
def test_each_platform_gets_its_own_install_page(plugin_init, platform, page):
    """The route differs per OS, so the link must too.

    Sending every reader to the index makes each of them find their own page
    first, and the one thing we know about them is which OS they are on.
    """
    assert plugin_init.install_docs_url(platform) == \
        plugin_init.INSTALL_DOCS_URL + page


@pytest.mark.parametrize("platform", ["freebsd14", "cygwin", "aix", ""])
def test_an_unlisted_platform_falls_back_to_the_index(plugin_init, platform):
    """Better the index than a 404: there is no page for these."""
    assert plugin_init.install_docs_url(platform) == plugin_init.INSTALL_DOCS_URL


def test_the_link_is_a_page_that_the_nav_actually_publishes(plugin_init):
    """Guard against the link and the docs drifting apart.

    `mkdocs.yml`'s nav is the list of pages that exist; a URL built from a name
    that is not in it would 404 on the published site. Checked without the
    network, against the repository's own nav.
    """
    import pathlib
    import re
    nav = pathlib.Path(__file__).parents[2] / "website" / "mkdocs.yml"
    text = nav.read_text(encoding="utf-8")
    for platform, _ in plugin_init._INSTALL_DOCS_BY_PLATFORM:
        url = plugin_init.install_docs_url(platform)
        slug = url.rstrip("/").rsplit("/", 1)[-1]
        assert re.search(rf"installation/{re.escape(slug)}\.md", text), \
            f"{url} has no installation/{slug}.md in the mkdocs nav"


def test_a_present_install_is_reported_as_loadable(plugin_init):
    """With nothing missing there is nothing to say and nothing to block."""
    report = check_dependencies(probe=lambda m: True)
    assert report.ok and report.can_load


def test_only_a_blocking_absence_stops_the_load(plugin_init):
    """``av`` and ``cv2`` are guarded imports — their absence must not block.

    The distinction is ``blocks_load``; getting it backwards would either hide a
    fatal failure or refuse to load over a missing video codec.
    """
    guarded = _report(["av", "cv2", "OpenGL"])
    assert not guarded.ok
    assert guarded.can_load

    fatal = _report(["pyqtgraph"])
    assert not fatal.can_load


def test_the_stub_plugin_offers_only_what_cannot_fail(plugin_init):
    """It must satisfy QGIS's plugin protocol without constructing anything."""
    stub = plugin_init._MissingDependenciesPlugin(None, _report(["pyqtgraph"]))
    assert callable(stub.initGui) and callable(stub.unload)
    # unload before initGui must be safe: QGIS calls it on a failed load.
    stub.unload()


def test_the_dialog_is_shown_once_not_once_per_import(plugin_init):
    """16 missing packages must not mean 16 dialogs."""
    stub = plugin_init._MissingDependenciesPlugin(None, _report(["pyqtgraph"]))
    shown = []
    stub.explain = lambda: shown.append(1)
    stub.explain_once()
    stub.explain_once()
    stub.explain_once()
    assert len(shown) == 1


def test_logging_outside_qgis_is_silent_rather_than_fatal(plugin_init):
    """``_log`` is reached from ``classFactory``; it must never be the failure."""
    plugin_init._log("probe", "Critical")
    plugin_init._log_report(_report(["pyqtgraph"]), None)
    plugin_init._log_report(check_dependencies(probe=lambda m: True), "/some/venv")
