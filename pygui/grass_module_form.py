"""Schema-driven PyQt form builder for arbitrary GRASS modules.

PyQt port of the FastGIS web client's on-demand form builder
(``app/static/grass_runner/js/schema.js``).  Given a module *interface schema*
(as returned by ``gt.grass_api.describe_module``), it renders the appropriate
widgets so any non-blacklisted GRASS module gets a native dialog, keeping the
GRASS look & feel.

Widget mapping (mirrors ``_makeParamField`` / ``_makeFlagItem``):

* parameter with ``options`` (enum)        -> ``QComboBox``
* parameter ``gisprompt.age == "old"``     -> editable ``QComboBox`` populated
                                              from ``g.list`` of that type
* parameter ``type`` integer/float/double  -> ``QLineEdit`` with a numeric
                                              validator (empty allowed = omit)
* other / ``gisprompt.age == "new"``       -> ``QLineEdit`` (placeholder hints)
* flag                                      -> ``QCheckBox``

The pure helpers (:func:`param_kind`, :func:`build_args`) carry no Qt state and
are unit-testable without a display.
"""
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLabel, QLineEdit, QComboBox,
    QCheckBox, QGroupBox,
)
from qgis.PyQt.QtGui import QIntValidator, QDoubleValidator

# g.list-able element types worth populating as autocomplete (mirrors schema.js)
GLIST_TYPES = {
    "raster", "vector", "region", "group", "icon", "colr", "labels",
    "raster_3d", "stds", "rast", "vect", "rast3d",
}
# Flags grouped at the bottom of the form
_SPECIAL_FLAGS = ("overwrite", "verbose", "quiet")


# --------------------------------------------------------------------------- #
# Pure helpers (no Qt state)                                                   #
# --------------------------------------------------------------------------- #

def param_kind(p: dict) -> str:
    """Classify a parameter into a widget kind.

    Returns one of: ``"enum"``, ``"old"``, ``"integer"``, ``"float"``, ``"text"``.
    """
    gp = p.get("gisprompt") or {}
    if p.get("options"):
        return "enum"
    if gp.get("age") == "old" and gp.get("prompt"):
        return "old"
    if p.get("type") == "integer":
        return "integer"
    if p.get("type") in ("float", "double"):
        return "float"
    return "text"


def build_args(params: dict, flags: list[str]) -> list[str]:
    """Flatten ``params``/``flags`` into GRASS CLI args (mirrors JS ``buildArgs``)."""
    args = [f"-{f}" if len(f) == 1 else f"--{f}" for f in flags]
    args += [f"{k}={v}" for k, v in params.items()]
    return args


# --------------------------------------------------------------------------- #
# Widget                                                                       #
# --------------------------------------------------------------------------- #

class GrassModuleForm(QWidget):
    """A form widget built on demand from a GRASS module interface schema.

    Use :meth:`needed_gisprompt_types` to learn which ``g.list`` element types
    the form references, fetch them (e.g. via ``grass_api.list_maps``), then call
    :meth:`set_existing_items` to populate the autocomplete combos.
    """

    def __init__(self, schema: dict, parent=None):
        super().__init__(parent)
        self.schema = schema or {}
        # name -> (widget, kind, required)
        self._params: dict[str, tuple] = {}
        # name -> checkbox
        self._flags: dict[str, QCheckBox] = {}
        # gisprompt type -> [editable combos to populate]
        self._old_combos: dict[str, list[QComboBox]] = {}
        self._build()

    # ---- construction ------------------------------------------------------ #

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)

        desc = self.schema.get("label") or self.schema.get("description")
        if desc:
            lbl = QLabel(desc)
            lbl.setWordWrap(True)
            lbl.setStyleSheet("font-weight: bold;")
            root.addWidget(lbl)

        # Group parameters by guisection
        sections: dict[str, list] = {}
        for p in self.schema.get("parameters", []):
            sections.setdefault(p.get("guisection") or "", []).append(p)

        for sec, params in sections.items():
            box = QGroupBox(sec or "Parameters", self)
            form = QFormLayout(box)
            for p in params:
                form.addRow(self._param_label(p), self._make_param_widget(p))
            root.addWidget(box)

        flags = self.schema.get("flags", [])
        if flags:
            main = [f for f in flags if f.get("name") not in _SPECIAL_FLAGS]
            extra = [f for f in flags if f.get("name") in _SPECIAL_FLAGS]
            box = QGroupBox("Flags", self)
            fl = QVBoxLayout(box)
            for f in main + extra:
                fl.addWidget(self._make_flag_widget(f))
            root.addWidget(box)

        root.addStretch(1)

    @staticmethod
    def _param_label(p: dict) -> str:
        return f"{p['name']} *" if p.get("required") else p["name"]

    def _make_param_widget(self, p: dict) -> QWidget:
        name = p["name"]
        kind = param_kind(p)
        default = p.get("default")
        tip = p.get("label") or p.get("description") or ""

        if kind == "enum":
            w = QComboBox(self)
            if not p.get("required") or default is None:
                w.addItem("" if default is None else str(default), "")
            for o in p["options"]:
                w.addItem(str(o), str(o))
            if default is not None:
                i = w.findData(str(default))
                if i >= 0:
                    w.setCurrentIndex(i)
        elif kind == "old":
            w = QComboBox(self)
            w.setEditable(True)
            w.setInsertPolicy(QComboBox.InsertPolicy(0))  # NoInsert
            if default:
                w.setCurrentText(str(default))
            gp_type = p["gisprompt"]["prompt"]
            w.lineEdit().setPlaceholderText(
                f"{gp_type}[,{gp_type}…]" if p.get("multiple") else f"existing {gp_type}")
            self._old_combos.setdefault(gp_type, []).append(w)
        else:
            w = QLineEdit(self)
            if kind == "integer":
                w.setValidator(QIntValidator(self))
            elif kind == "float":
                w.setValidator(QDoubleValidator(self))
            if default is not None:
                w.setText(str(default))
            gp = p.get("gisprompt") or {}
            if gp.get("age") == "new":
                w.setPlaceholderText(f"new {gp.get('prompt', 'name')}")
            elif p.get("multiple"):
                w.setPlaceholderText("value[,value…]")

        if tip:
            w.setToolTip(tip)
        self._params[name] = (w, kind, bool(p.get("required")))
        return w

    def _make_flag_widget(self, f: dict) -> QCheckBox:
        name = f["name"]
        text = f"-{name}"
        hint = f.get("label") or f.get("description")
        if hint:
            text += f"  —  {hint}"
        cb = QCheckBox(text, self)
        self._flags[name] = cb
        return cb

    # ---- population / collection ------------------------------------------ #

    def needed_gisprompt_types(self) -> list[str]:
        """Element types referenced by 'old' params that should be g.list-ed."""
        return [t for t in self._old_combos if t in GLIST_TYPES]

    def set_existing_items(self, items_by_type: dict[str, list[str]]) -> None:
        """Populate autocomplete combos for existing GRASS objects.

        ``items_by_type`` maps a gisprompt type (e.g. ``"raster"``) to the list of
        existing object names.  Preserves any text the user already typed.
        """
        for gp_type, combos in self._old_combos.items():
            items = items_by_type.get(gp_type)
            if items is None:
                continue
            for combo in combos:
                current = combo.currentText()
                combo.clear()
                combo.addItems(items)
                combo.setCurrentText(current)

    def _widget_value(self, widget, kind) -> str:
        if isinstance(widget, QComboBox):
            if kind == "enum":
                data = widget.currentData()
                return (data if data is not None else widget.currentText()).strip()
            return widget.currentText().strip()
        return widget.text().strip()

    def collect_values(self) -> tuple[dict, list[str]]:
        """Return ``(params, flags)`` from current widget state (non-empty only)."""
        params = {}
        for name, (widget, kind, _req) in self._params.items():
            val = self._widget_value(widget, kind)
            if val:
                params[name] = val
        flags = [name for name, cb in self._flags.items() if cb.isChecked()]
        return params, flags

    def missing_required(self) -> list[str]:
        """Names of required parameters left empty."""
        missing = []
        for name, (widget, kind, req) in self._params.items():
            if req and not self._widget_value(widget, kind):
                missing.append(name)
        return missing

    def build_args(self) -> list[str]:
        """CLI args for the generic ``/grass/exec`` path."""
        params, flags = self.collect_values()
        return build_args(params, flags)
