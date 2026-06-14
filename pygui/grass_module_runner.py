"""Generic GRASS module runner widget.

Combines the schema-driven :class:`~groundtruther.pygui.grass_module_form.GrassModuleForm`
with the async :func:`~groundtruther.gt.task_runner.run_module_task` to provide a
self-building dialog that can run *any* GRASS module against the active
environment.  The three named runners (r.geomorphon, r.param.scale, grm_lsi)
subclass this with a preset module name.

External interface kept compatible with the old bespoke runner widgets so the
MDI wiring in ``grass_mdi_gui`` is unchanged:

* constructed as ``Widget(parent)`` where *parent* is the dockwidget;
* exposes ``get_rvr_list()`` (build/refresh the form for the active env);
* exposes an ``exit`` button (the MDI code connects it to the show/hide toggle).

Modules run against the environment's *current computational region* (set via
the GRASS settings dialog / region tool), so no region argument is sent.
"""
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QScrollArea, QLabel,
)
from qgis.core import Qgis, QgsMessageLog

from groundtruther.configure import log_exception
from groundtruther.gt import grass_api
from groundtruther.gt.grass_api import GrassApiError
from groundtruther.gt.task_runner import run_module_task
from groundtruther.pygui.grass_module_form import GrassModuleForm


class ModuleRunnerWidget(QWidget):
    """A self-building, schema-driven runner for one GRASS module."""

    def __init__(self, parent, module_name: str):
        super().__init__(parent)
        self.parent = parent
        self.module_name = module_name
        self._form = None
        self._task = None

        layout = QVBoxLayout(self)
        self._header = QLabel(module_name)
        self._header.setStyleSheet("font-weight: bold;")
        layout.addWidget(self._header)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setWidget(QLabel("Click 'Reload' to load the module form."))
        layout.addWidget(self._scroll, 1)

        row = QHBoxLayout()
        self.reload_layers = QPushButton("Reload")
        self.run = QPushButton("Run")
        self.cancel = QPushButton("Cancel")
        self.cancel.setEnabled(False)
        self.exit = QPushButton("Close")
        row.addWidget(self.reload_layers)
        row.addWidget(self.run)
        row.addWidget(self.cancel)
        row.addStretch(1)
        row.addWidget(self.exit)
        layout.addLayout(row)

        self.reload_layers.clicked.connect(self.get_rvr_list)
        self.run.clicked.connect(self.run_module)
        self.cancel.clicked.connect(self._cancel)
        # `exit` is connected by the MDI host (view toggle).

    # ------------------------------------------------------------------ #
    # Helpers                                                             #
    # ------------------------------------------------------------------ #

    def _report(self, html: str) -> None:
        try:
            self.parent.grassWidgetContents.grass_mdi.gis_tool_report.setHtml(html)
        except AttributeError:
            QgsMessageLog.logMessage(html, 'GroundTruther', Qgis.Info)

    def _conn(self):
        return self.parent.grass_dialog.connection()

    # ------------------------------------------------------------------ #
    # Form build / refresh (named get_rvr_list for MDI compatibility)    #
    # ------------------------------------------------------------------ #

    def get_rvr_list(self):
        """Build the form (once) from the module schema and populate map lists."""
        endpoint, api_key, env_id = self._conn()
        if not env_id:
            self._report("<b>No GRASS environment selected.</b> "
                         "Open GRASS settings and choose an environment.")
            return
        if self._form is None:
            try:
                schema = grass_api.describe_module(endpoint, api_key, self.module_name)
            except GrassApiError as exc:
                log_exception(f"describe_module({self.module_name})", exc, warn=True)
                self._report(f"<b>Module '{self.module_name}' unavailable:</b> {exc}")
                return
            self._form = GrassModuleForm(schema)
            self._scroll.setWidget(self._form)
        # populate existing-object combos
        try:
            items = {t: grass_api.list_maps(endpoint, api_key, env_id, type=t)
                     for t in self._form.needed_gisprompt_types()}
            self._form.set_existing_items(items)
        except GrassApiError as exc:
            log_exception(f"{self.module_name}: list_maps", exc, warn=True)

    # ------------------------------------------------------------------ #
    # Execution                                                          #
    # ------------------------------------------------------------------ #

    def run_module(self):
        endpoint, api_key, env_id = self._conn()
        if not env_id:
            self._report("<b>No GRASS environment selected.</b>")
            return
        if self._form is None:
            self.get_rvr_list()
            if self._form is None:
                return
        missing = self._form.missing_required()
        if missing:
            self._report("Please fill required parameters: " + ", ".join(missing))
            return
        params, flags = self._form.collect_values()
        self._report(f"… running {self.module_name} …")
        self.run.setEnabled(False)
        self.cancel.setEnabled(True)
        self._task = run_module_task(
            endpoint, api_key, env_id, self.module_name,
            params=params, flags=flags,
            on_progress=self._report,
            on_success=self._on_success,
            on_error=self._on_error,
            description=f"GRASS {self.module_name}")

    def _on_success(self, payload: dict):
        self.run.setEnabled(True)
        self.cancel.setEnabled(False)
        result = payload.get("result") if isinstance(payload.get("result"), dict) else payload
        stdout = result.get("stdout") or []
        stderr = result.get("stderr") or []
        text = "\n".join(stdout) + ("\n" + "\n".join(stderr) if stderr else "")
        self._report(f"<b>{self.module_name} finished.</b><pre>{text}</pre>")
        # Refresh the queryable raster list now that outputs may exist.
        try:
            self.parent.grassWidgetContents.load_grass_layers()
        except Exception as exc:  # noqa: BLE001 — best-effort refresh
            log_exception(f"{self.module_name}: refresh layers", exc, warn=True)
        self.get_rvr_list()

    def _on_error(self, detail: str):
        self.run.setEnabled(True)
        self.cancel.setEnabled(False)
        self._report(f"<b>{self.module_name} failed:</b><pre>{detail}</pre>")

    def _cancel(self):
        if self._task is not None:
            self._task.cancel()
            self._report(f"Cancelling {self.module_name} …")
