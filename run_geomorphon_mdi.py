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

"""r.geomorphon runner — a preset of the generic schema-driven module runner.

The bespoke form is gone: the dialog is now built on demand from the module's
interface schema (see ``pygui/grass_module_runner.py``) and executed
asynchronously via the FastGIS task queue.
"""
from groundtruther.pygui.grass_module_runner import ModuleRunnerWidget


class GeoMorphonWidget(ModuleRunnerWidget):
    """Run ``r.geomorphon`` against the active GRASS environment."""

    def __init__(self, parent):
        super().__init__(parent, "r.geomorphon")
