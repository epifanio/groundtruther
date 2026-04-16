#!/usr/bin/env bash
# Regenerate Ui_*.py from Qt Designer .ui files using pyuic6 (QGIS 4 / Qt6).
# Run from the repo root.  Requires pyuic6 on PATH (available in gtenv or
# the QGIS 4 OSGeo4W shell).
#
# Post-generation patches applied automatically:
#   1. Replace "from PyQt6 import" with "from qgis.PyQt import"
#   2. Replace "import resources_rc" with "import groundtruther.resources_rc"
#   3. Replace unavailable QWebView (QtWebKit removed in Qt6) with QTextBrowser
#   4. Convert every scoped PyQt6 enum expression to integer-constructor form
#      e.g. QtWidgets.QSizePolicy.Policy.Expanding  ->  QtWidgets.QSizePolicy.Policy(7)
#      This is required because qgis.PyQt (the QGIS 4 shim) does not expose Qt6
#      enum inner-classes through the expected scoped attribute chain at runtime.

set -e

UI_FILES=(
    "qtui/app_settings_ui.ui:pygui/Ui_app_settings_ui.py"
    "qtui/epsg_ui.ui:pygui/Ui_epsg_ui.py"
    "qtui/grass_mdi_ui.ui:pygui/Ui_grass_mdi_ui.py"
    "qtui/groundtruther_dockwidget_base.ui:pygui/Ui_groundtruther_dockwidget_base.py"
    "qtui/image_metadata_ui.ui:pygui/Ui_image_metadata_ui.py"
    "qtui/paramscale_api_ui.ui:pygui/Ui_paramscale_ui.py"
    "qtui/query_builder_ui.ui:pygui/Ui_query_builder_ui.py"
    "qtui/geomorphon_api_ui.ui:pygui/Ui_geomorphon_ui.py"
    "qtui/grassapi_settings_ui.ui:pygui/Ui_grass_settings_ui.py"
    "qtui/grm_lsi_ui.ui:pygui/Ui_grm_lsi_ui.py"
    "qtui/hbc_browser_ui.ui:pygui/Ui_hbc_browser_ui.py"
    "qtui/kmlsave_ui.ui:pygui/Ui_kmlsave_ui.py"
)

# 1. Generate
for entry in "${UI_FILES[@]}"; do
    src="${entry%%:*}"
    dst="${entry##*:}"
    pyuic6 "$src" -o "$dst"
    echo "Generated: $dst"
done

# 2. Fix imports: PyQt6 -> qgis.PyQt
for entry in "${UI_FILES[@]}"; do
    dst="${entry##*:}"
    sed -i 's/^from PyQt6 import/from qgis.PyQt import/' "$dst"
done

# 3. Fix resources_rc import
for entry in "${UI_FILES[@]}"; do
    dst="${entry##*:}"
    sed -i 's/^import resources_rc$/import groundtruther.resources_rc/' "$dst"
done

# 4. Replace QWebView (QtWebKit removed in Qt6) with QTextBrowser
#    Affects: Ui_geomorphon_ui.py, Ui_paramscale_ui.py
python3 - <<'PYEOF'
import pathlib, re

targets = [
    'pygui/Ui_geomorphon_ui.py',
    'pygui/Ui_paramscale_ui.py',
]
for fname in targets:
    p = pathlib.Path(fname)
    if not p.exists():
        continue
    text = p.read_text(encoding='utf-8')
    # Remove broken QtWebKitWidgets import line
    text = re.sub(r'^from QtWebKitWidgets.*\n', '', text, flags=re.MULTILINE)
    # Replace QWebView instantiation + setUrl with QTextBrowser
    text = re.sub(
        r'self\.webView = QWebView\(parent=self\.manual\)\n'
        r'        self\.webView\.setUrl\(QtCore\.QUrl\("about:blank"\)\)\n',
        'self.webView = QtWidgets.QTextBrowser(self.manual)\n',
        text
    )
    p.write_text(text, encoding='utf-8')
    print(f'Patched QWebView -> QTextBrowser: {fname}')
PYEOF

# 5. Convert scoped PyQt6 enum expressions to integer-constructor form.
#
#    pyuic6 emits:   QtWidgets.QSizePolicy.Policy.Expanding
#    We produce:     QtWidgets.QSizePolicy.Policy(7)
#
#    Strategy: evaluate every scoped enum expression directly against PyQt6
#    (which is available in the virtualenv that provides pyuic6).  Read the
#    .value attribute — PyQt6 enums are plain enum.Enum (not IntEnum), so
#    int(member) fails; .value always works.  Expressions that do not
#    evaluate to an enum member (e.g. QtCore.QMetaObject.connectSlotsByName,
#    QtCore.Qt.AlignmentFlag as a class) cause an AttributeError and are
#    left unchanged, so false-positive regex matches are harmless.
#
#    Bitwise-OR flag combinations are handled as a single expression:
#    QtCore.Qt.TextInteractionFlag.TextSelectableByMouse|...TextSelectableByKeyboard
#    -> QtCore.Qt.TextInteractionFlag(3)
python3 - <<'PYEOF'
import re
import pathlib

from PyQt6 import QtCore, QtGui, QtWidgets
try:
    from PyQt6 import QtPrintSupport as _QPS
    _NS = {'QtCore': QtCore, 'QtGui': QtGui, 'QtWidgets': QtWidgets, 'QtPrintSupport': _QPS}
except ImportError:
    _NS = {'QtCore': QtCore, 'QtGui': QtGui, 'QtWidgets': QtWidgets}

# One scoped enum reference: Module.Something.Something[.Something...]
# The negative lookahead (?!\() prevents re-matching an already-patched
# EnumClass(int) expression at the EnumClass level.
_MOD = r'(?:QtCore|QtGui|QtWidgets|QtPrintSupport)'
_SINGLE = _MOD + r'(?:\.[A-Za-z_][A-Za-z0-9_]*){2,}(?!\()'

# Full expression: one or more single refs joined by bitwise OR
_EXPR_RE = re.compile(r'(?<![.\w])(' + _SINGLE + r'(?:\|' + _SINGLE + r')*)')


def _replace(m: re.Match) -> str:
    expr = m.group(1)
    try:
        val = eval(expr, _NS)       # evaluate against real PyQt6
        int_val = val.value         # .value works for all enum/flag members
    except Exception:
        return expr                 # not an enum member — leave unchanged
    # Derive the enum-class path from the leftmost reference in the expression
    first_ref = re.match(_SINGLE, expr).group(0)
    class_path = first_ref.rsplit('.', 1)[0]
    return f'{class_path}({int_val})'


targets = [
    'pygui/Ui_app_settings_ui.py',
    'pygui/Ui_epsg_ui.py',
    'pygui/Ui_grass_mdi_ui.py',
    'pygui/Ui_groundtruther_dockwidget_base.py',
    'pygui/Ui_image_metadata_ui.py',
    'pygui/Ui_paramscale_ui.py',
    'pygui/Ui_query_builder_ui.py',
    'pygui/Ui_geomorphon_ui.py',
    'pygui/Ui_grass_settings_ui.py',
    'pygui/Ui_grm_lsi_ui.py',
    'pygui/Ui_hbc_browser_ui.py',
    'pygui/Ui_kmlsave_ui.py',
]

for fname in targets:
    p = pathlib.Path(fname)
    if not p.exists():
        continue
    text = p.read_text(encoding='utf-8')
    new_text = _EXPR_RE.sub(_replace, text)
    if new_text != text:
        p.write_text(new_text, encoding='utf-8')
        print(f'Patched enum expressions: {fname}')
    else:
        print(f'No enum expressions to patch: {fname}')
PYEOF

echo "Done."
