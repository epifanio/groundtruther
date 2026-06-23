"""Reusable formula cheat-sheet popup.

A small flat ``ⓘ`` button that opens a scrollable, **non-modal**, Ctrl+wheel
zoomable dialog showing a reference PNG (Quantity · Formula · Symbols · Source)
bundled in ``resources/cheatsheets/``.  Used behind the roughness / backscatter /
classification UIs so the math + symbol definitions are one click away.

The PNGs are static assets regenerated from the renderer at
``epinux/wiki/assets/cheatsheets/render_cheatsheets.py`` (source of truth); GT
ships copies and never depends on that path at runtime.
"""
import os
from pathlib import Path

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QPixmap
from qgis.PyQt.QtWidgets import (
    QDialog, QLabel, QScrollArea, QToolButton, QVBoxLayout,
)

CHEATS_DIR = str(Path(__file__).resolve().parents[1] / "resources" / "cheatsheets")


class _ZoomLabel(QLabel):
    """QLabel that Ctrl+wheel-zooms its pixmap (sheets are wide)."""

    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self._src = pixmap
        self._scale = 1.0
        self.setPixmap(pixmap)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def wheelEvent(self, event):
        ctrl = event.modifiers() & Qt.KeyboardModifier.ControlModifier
        if ctrl and not self._src.isNull():
            step = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
            self._scale = max(0.25, min(6.0, self._scale * step))
            scaled = self._src.scaledToWidth(
                int(self._src.width() * self._scale),
                Qt.TransformationMode.SmoothTransformation)
            self.setPixmap(scaled)
            self.resize(scaled.size())
            event.accept()
        else:
            super().wheelEvent(event)


class CheatSheetButton(QToolButton):
    """Auto-raise ``ⓘ`` button → opens *png* in a non-modal popup dialog."""

    def __init__(self, png: str, title: str, parent=None):
        super().__init__(parent)
        self._png = os.path.join(CHEATS_DIR, png)
        self._title = title
        self._dlg = None
        from groundtruther.mixins.toolbar_icons import iconize
        iconize(self, "circle-info.svg", f"Formulae & symbols — {title}")
        self.setAutoRaise(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(self._show)

    def _show(self):
        # Reuse an already-open dialog rather than stacking duplicates.
        if self._dlg is not None:
            try:
                self._dlg.raise_()
                self._dlg.activateWindow()
                return
            except RuntimeError:        # C++ side already gone
                self._dlg = None

        dlg = QDialog(self.window())
        dlg.setWindowTitle(self._title)
        dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(False)

        pix = QPixmap(self._png)
        if pix.isNull():
            placeholder = QLabel(f"Cheat sheet not found:\n{self._png}")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            scroll.setWidget(placeholder)
        else:
            scroll.setWidget(_ZoomLabel(pix))
            scroll.setToolTip("Ctrl + scroll to zoom")
        lay.addWidget(scroll)
        dlg.resize(1150, 820)

        self._dlg = dlg
        dlg.destroyed.connect(self._on_closed)
        dlg.show()                      # non-modal: keep it open beside results

    def _on_closed(self, *_args):
        self._dlg = None
