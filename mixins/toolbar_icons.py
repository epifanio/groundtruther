"""Two-state tinted toolbar icons from SVG files.

Usage::

    from groundtruther.mixins.toolbar_icons import make_toggle_icon, make_icon

    action.setIcon(make_toggle_icon("file-image.svg"))   # checkable action
    action.setIcon(make_icon("arrows-rotate.svg"))        # plain action
"""
import os

_ICONS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "qtui", "icons")

# Unchecked / inactive state
_COLOR_OFF = (150, 150, 150, 200)   # neutral gray, slightly transparent

# Checked / active state
_COLOR_ON  = (65, 165, 230, 255)    # QGIS-ish light blue, fully opaque


def _icon_path(name: str) -> str:
    return os.path.join(_ICONS_DIR, name)


def _tinted_pixmap(svg_path: str, rgba: tuple, size: int = 22):
    """Render *svg_path* into a *size*×*size* pixmap filled with *rgba*."""
    from qgis.PyQt.QtGui import QPixmap, QPainter, QColor
    from qgis.PyQt.QtCore import Qt
    from qgis.PyQt.QtSvg import QSvgRenderer

    renderer = QSvgRenderer(svg_path)
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    renderer.render(painter)
    # Replace every visible pixel's color while preserving its alpha
    painter.setCompositionMode(
        QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(pix.rect(), QColor(*rgba))
    painter.end()
    return pix


def make_toggle_icon(svg_name: str, size: int = 22):
    """Return a QIcon with dim gray (off) and blue (on) states for a checkable action."""
    from qgis.PyQt.QtGui import QIcon
    try:
        path = _icon_path(svg_name)
        icon = QIcon()
        icon.addPixmap(
            _tinted_pixmap(path, _COLOR_OFF, size),
            QIcon.Mode.Normal, QIcon.State.Off)
        icon.addPixmap(
            _tinted_pixmap(path, _COLOR_ON, size),
            QIcon.Mode.Normal, QIcon.State.On)
        return icon
    except Exception:
        return QIcon(_icon_path(svg_name))


def make_icon(svg_name: str, size: int = 22):
    """Return a plain QIcon tinted with the 'off' color for non-checkable actions."""
    from qgis.PyQt.QtGui import QIcon
    try:
        path = _icon_path(svg_name)
        icon = QIcon()
        icon.addPixmap(_tinted_pixmap(path, _COLOR_OFF, size))
        return icon
    except Exception:
        return QIcon(_icon_path(svg_name))
