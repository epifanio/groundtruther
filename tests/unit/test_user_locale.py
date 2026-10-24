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

"""``groundtruther.user_locale`` — an absent locale key must not crash the plugin.

**The fault this pins down.** The Plugin Builder boilerplate read the UI language
as ``QSettings().value('locale/userLocale')[0:2]``. ``value()`` returns **None**
when that key has never been written, so the slice raised ``TypeError: 'NoneType'
object is not subscriptable`` inside ``GroundTruther.__init__`` — the plugin died
before doing anything, with a message naming neither the setting nor the plugin.

It stayed invisible because the two situations that trigger it are the two where
nobody was looking. A QGIS profile that has never saved its settings has no such
key; and every headless ``QgsApplication`` sets no organisation name, so its
``QSettings`` reads an empty store. The headless load checks this project relies
on passed only because missing dependencies diverted ``classFactory`` to
``_MissingDependenciesPlugin``, which never reaches that line. Install every
dependency and the same check fails here.

Fixing it does **not** make a complete install verifiable headlessly: measured,
the next line to fail is ``self.iface.addToolBar(...)``, and ``qgis.utils.iface``
is None without a GUI. This is one unguarded slice, no more.

**Why the test looks like this.** ``groundtruther.py`` imports ``qgis.PyQt``, so
``tests/unit`` cannot import it (D-008 keeps that guarantee for ``gt/`` only).
Rather than give up a real assertion and settle for matching source text, the
function's own source is lifted out with ``ast`` and executed against a stub
``QSettings``. What runs here is the shipped code, not a copy of it.
"""
import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "groundtruther.py").read_text(encoding="utf-8")


class _Settings:
    """The one method ``user_locale`` uses."""

    def __init__(self, stored):
        self._stored = stored

    def value(self, key):
        assert key == "locale/userLocale"
        return self._stored


def _load():
    """Execute just ``user_locale`` from the shipped file, with Qt stubbed out."""
    tree = ast.parse(SOURCE)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "user_locale":
            module = ast.Module(body=[node], type_ignores=[])
            ns = {"QSettings": lambda: _Settings(None)}
            exec(compile(module, "<groundtruther.py>", "exec"), ns)
            return ns["user_locale"]
    raise AssertionError("groundtruther.py no longer defines user_locale()")


user_locale = _load()


@pytest.mark.parametrize("stored, expected", [
    ("en_US", "en"),
    ("nb_NO", "nb"),
    ("pt_BR", "pt"),
    ("de", "de"),
])
def test_a_recorded_locale_is_cut_to_two_letters(stored, expected):
    """The behaviour the boilerplate had, which must survive the fix."""
    assert user_locale(_Settings(stored)) == expected


@pytest.mark.parametrize("stored", [None, ""])
def test_an_absent_locale_key_yields_empty_rather_than_raising(stored):
    """The bug itself: ``None[0:2]`` is a TypeError, and it killed the plugin.

    Empty is the right answer, not a guessed default: it finds no translation
    file, which is exactly what an unrecognised language does.
    """
    assert user_locale(_Settings(stored)) == ""


def test_the_raw_slice_is_gone_from_the_file():
    """Guard the shape of the call, not only this function's behaviour.

    The fault was one expression in ``__init__``; nothing stops it being written
    again the next time that file is touched.
    """
    assert "QSettings().value('locale/userLocale')[0:2]" not in SOURCE
    assert "user_locale()" in SOURCE


def test_the_plugin_still_builds_a_translation_path_from_it():
    """The fix must not quietly disable translation loading."""
    assert "GroundTruther_{}.qm" in SOURCE
    assert "locale = user_locale()" in SOURCE
