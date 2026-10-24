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

"""grm_lsi runner — a preset of the generic schema-driven module runner.

The dialog is built on demand from the module's interface schema (see
``pygui/grass_module_runner.py``) and executed asynchronously via the FastGIS
task queue.

NOTE: ``grm_lsi`` is not currently installed on the FastGIS server, so the form
will report the module as unavailable until it is added (e.g. via
``g.extension``).  Adjust the module name below if it is installed under a
different name.
"""
from groundtruther.pygui.grass_module_runner import ModuleRunnerWidget


class GrmLsiWidget(ModuleRunnerWidget):
    """Run ``grm_lsi`` against the active GRASS environment."""

    def __init__(self, parent):
        super().__init__(parent, "grm_lsi")
