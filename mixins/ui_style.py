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

"""Shared metric/metadata panel styling (roughness + image/video metadata).

One source of truth so the panels look consistent.  Only SEMANTIC colours are
set (green / red / muted grey) — neutral values inherit the theme text colour so
the panels read correctly on both light and dark QGIS themes.
"""
C_OK = "#3aa84a"        # trustworthy / in-tolerance
C_WARN = "#d9534f"      # unreliable
C_MUTED = "#9aa0a6"     # labels / indicative / secondary

VALUE_CSS = "font-size: 13px;"
LABEL_CSS = f"color: {C_MUTED}; font-size: 13px;"
