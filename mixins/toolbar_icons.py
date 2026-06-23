"""Two-state tinted toolbar icons from SVG files.

Usage::

    from groundtruther.mixins.toolbar_icons import make_toggle_icon, make_icon

    action.setIcon(make_toggle_icon("file-image.svg"))   # checkable action
    action.setIcon(make_icon("arrows-rotate.svg"))        # plain action

Prefer ``iconize(widget, svg)`` or ``apply_icon(target, svg)`` over a bare
``setIcon`` — those register the target so it re-tints **live** when the OS / QGIS
UI theme switches between light and dark (no plugin reload needed).
"""
import os
import weakref

_ICONS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "qtui", "icons")

# Base tints are picked from the active Qt palette at icon-build time so the set
# adapts to light vs dark themes — covers both the OS style and the QGIS UI theme
# (Default / Night Mapping / Blend of Gray), which both drive the app palette.
#
# Light theme: a neutral mid-gray reads well on a pale toolbar.
# Dark theme : a much brighter gray so the icon doesn't disappear into the dark.
_COLOR_OFF_LIGHT = (150, 150, 150, 200)   # neutral gray on a light toolbar
_COLOR_OFF_DARK  = (205, 205, 205, 235)   # bright gray on a dark toolbar
# Checked / active state — QGIS-ish blue, nudged brighter on dark themes.
_COLOR_ON_LIGHT  = (65, 165, 230, 255)
_COLOR_ON_DARK   = (95, 185, 250, 255)


def _is_dark_theme() -> bool:
    """True when the active Qt palette is dark (perceived window luminance < 50%)."""
    try:
        from qgis.PyQt.QtWidgets import QApplication
        from qgis.PyQt.QtGui import QPalette
        app = QApplication.instance()
        if app is None:
            return False
        c = app.palette().color(QPalette.ColorRole.Window)
        return (0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()) < 128
    except Exception:
        return False


def _color_off() -> tuple:
    return _COLOR_OFF_DARK if _is_dark_theme() else _COLOR_OFF_LIGHT


def _color_on() -> tuple:
    return _COLOR_ON_DARK if _is_dark_theme() else _COLOR_ON_LIGHT


# --- live re-tint on theme change ------------------------------------------
# Each iconized target is registered (weakly) with its SVG + size; when the app
# palette changes (OS dark mode, or QGIS UI theme switch) every registered icon
# is rebuilt at the new tint.  Targets that have been deleted are pruned.
#
# We listen on the application ``paletteChanged`` signal ONLY.  We deliberately
# do NOT install an event filter on the QApplication: a filter on the app object
# receives *every* event for *every* object in QGIS and runs Python per-event,
# which makes the whole UI hang (especially during startup).
_REGISTRY = []          # list of (weakref_to_target, svg_name, size)
_HOOKS = []             # list of weakrefs to callables run after each retint
_SIGNAL_CONNECTED = False


def _retint_target(target, svg_name, size) -> None:
    """Rebuild + apply one target's icon at the current theme."""
    try:
        checkable = bool(target.isCheckable())
    except Exception:
        checkable = False
    icon = make_toggle_icon(svg_name, size) if checkable else make_icon(svg_name, size)
    target.setIcon(icon)


def retint_all() -> None:
    """Rebuild every registered icon for the current palette; prune dead ones."""
    alive = []
    for ref, svg, size in _REGISTRY:
        target = ref()
        if target is None:
            continue
        try:
            _retint_target(target, svg, size)
            alive.append((ref, svg, size))
        except RuntimeError:        # underlying C++ object already gone
            continue
    _REGISTRY[:] = alive
    live_hooks = []
    for hook in _HOOKS:
        cb = hook()
        if cb is None:
            continue
        live_hooks.append(hook)
        try:
            cb()
        except Exception:
            pass
    _HOOKS[:] = live_hooks


def add_retint_hook(callback) -> None:
    """Register *callback* (no args) to run after each live re-tint (held weakly).

    Use for icons that can't be expressed as a single registered target — e.g.
    the video player's cached play / pause icons, which the hook rebuilds and
    re-applies according to the current playback state.
    """
    try:
        ref = weakref.WeakMethod(callback)
    except TypeError:
        ref = weakref.ref(callback)
    _HOOKS.append(ref)
    _install_watcher()


def _register_icon(target, svg_name, size) -> None:
    try:
        ref = weakref.ref(target)
    except TypeError:
        ref = (lambda t=target: t)      # not weakref-able → hold strongly
    _REGISTRY.append((ref, svg_name, size))
    _install_watcher()


def _install_watcher() -> None:
    """Connect (once) the application ``paletteChanged`` signal to a re-tint.

    Cheap: the signal only fires when the application palette actually changes
    (OS dark-mode toggle, QGIS UI-theme switch), never per ordinary event.
    """
    global _SIGNAL_CONNECTED
    if _SIGNAL_CONNECTED:
        return
    try:
        from qgis.PyQt.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            return
        if hasattr(app, "paletteChanged"):
            app.paletteChanged.connect(_on_palette_changed)
        _SIGNAL_CONNECTED = True          # don't retry even if the signal is absent
    except Exception:
        pass


def _on_palette_changed(*_args) -> None:
    retint_all()


def apply_icon(target, svg_name: str, size: int = 22):
    """Set a theme-adaptive icon on *target* and register it for live re-tint.

    Drop-in for ``target.setIcon(make_toggle_icon(...))`` / ``make_icon(...)`` —
    two-state for checkable targets, single otherwise — that also follows later
    light/dark theme switches.  Text is left untouched.
    """
    _register_icon(target, svg_name, size)
    _retint_target(target, svg_name, size)
    return target


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
            _tinted_pixmap(path, _color_off(), size),
            QIcon.Mode.Normal, QIcon.State.Off)
        icon.addPixmap(
            _tinted_pixmap(path, _color_on(), size),
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
        icon.addPixmap(_tinted_pixmap(path, _color_off(), size))
        return icon
    except Exception:
        return QIcon(_icon_path(svg_name))


def iconize(widget, svg_name: str, tooltip: str = None, *, size: int = 22):
    """Make *widget* an on-theme, icon-only control.

    Works for ``QAction``, ``QPushButton`` and ``QToolButton``.  Applies the
    tinted SVG icon (two-state for checkable widgets, single for the rest), moves
    the current text into the tooltip (unless *tooltip* is given), and — for
    push/tool buttons — clears the text + switches to icon-only display.  Toolbar
    ``QAction`` text is kept (so menus/accessibility still read), since toolbars
    already render icon-only.
    """
    from qgis.PyQt.QtWidgets import QAbstractButton, QToolButton
    from qgis.PyQt.QtCore import Qt
    try:
        checkable = bool(widget.isCheckable())
    except Exception:
        checkable = False
    icon = make_toggle_icon(svg_name, size) if checkable else make_icon(svg_name, size)
    tip = tooltip or widget.toolTip() or widget.text()
    widget.setIcon(icon)
    _register_icon(widget, svg_name, size)       # follow live theme switches
    if tip:
        widget.setToolTip(tip)
    if isinstance(widget, QAbstractButton):
        widget.setText("")                       # icon-only; tooltip is the label
        if isinstance(widget, QToolButton):
            widget.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
    return widget
