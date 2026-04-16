#!/usr/bin/env bash
# Regenerate Ui_*.py from Qt Designer .ui files using pyuic6 (QGIS 4 / Qt6).
# Run from the repo root.  Requires pyuic6 on PATH (available in gtenv or
# the QGIS 4 OSGeo4W shell).
#
# Post-generation patches applied automatically:
#   1. Replace "from PyQt6 import" with "from qgis.PyQt import"
#   2. Replace "import resources_rc" with "import groundtruther.resources_rc"
#   3. Replace unavailable QWebView (QtWebKit removed in Qt6) with QTextBrowser

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

echo "Done."
