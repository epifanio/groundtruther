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
