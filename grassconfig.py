"""GRASS environment selection / creation dialog (FastGIS API).

Reworked for the FastGIS GRASS API: instead of the old gisdb + location +
mapset picker, the user selects an *environment* (``env_id``) from the ones they
own, or creates a new one (from an EPSG code or a georeferenced dataset) and new
mapsets within it.  The selected ``env_id`` is what every GRASS operation runs
against.

Connection parameters (endpoint + API key) come from the plugin Settings
(``Processing.grass_api_endpoint`` / ``Processing.grass_api_key``); the endpoint
field here is editable as an override.

The dialog reuses the Designer widgets from ``GrassSettings`` but repurposes
them:

* ``grass_location_list``  -> "My environments" combo (userData = env_id)
* ``set_location``         -> "Use Environment" (activate the selected env_id)
* ``reload``               -> refresh the environment list
* ``new_location_name`` / ``choice_epsg`` / ``epsg_code`` / ``choice_georef`` /
  ``georef_file`` / ``create_location`` -> create environment
* ``new_mapset`` / ``create_mapset``    -> create a mapset in the active env

Obsolete widgets (gisdb path, mapset list, second location list, output-layer
name) are hidden.
"""
import json

from qgis.PyQt.QtWidgets import QDialog, QFileDialog, QButtonGroup
from qgis.core import Qgis, QgsMessageLog

from pygui.grass_settings_gui import GrassSettings
from epsg_list import codelist
from search_epsg import SearchEpsgDialog

from groundtruther.config.config import config
from groundtruther.configure import load_config, log_exception
from groundtruther.gt import grass_api
from groundtruther.gt.grass_api import GrassApiError


class GrassConfigDialog(QDialog, GrassSettings):
    """Select or create a FastGIS GRASS environment for the plugin to use."""

    def __init__(self, parent=None):
        super().__init__()
        QDialog.__init__(self, parent)
        self.setupUi(self)
        self.parent = parent

        self.config = config
        self.endpoint = ""
        self.api_key = ""
        self.env_id = None          # active environment id
        self.active_env = None      # active environment payload
        self.grassenabled = False
        self._envs = {}             # env_id -> payload

        self._load_conn()
        self.grass_api_endpoint.setText(self.endpoint)

        # Hide widgets that no longer apply under the env model
        for name in ("grass_gisdb", "location_mapset_list",
                     "grass_location_list2", "layer_name", "label_10"):
            w = getattr(self, name, None)
            if w is not None:
                w.hide()

        # Relabel reused controls
        self.set_location.setText("Use Environment")
        self.create_location.setText("Create Environment")
        try:
            self.groupBox_2.setTitle("GRASS Environments")
        except AttributeError:
            pass

        # EPSG search helper
        self.searchepsg_dialog = SearchEpsgDialog()
        self.search_epsg.clicked.connect(self.show_searchepsg_dialog)

        self.command_output.hide()
        self.grass_new_location_groupbox.hide()
        self.grass_new_mapset_groupbox.hide()
        self.new_grass_location_dialog.clicked.connect(self.show_hide_new_grass_location)
        self.show_output_log.clicked.connect(self.show_hide_output_log)

        self.set_location.clicked.connect(self.use_selected_env)
        self.set_georef_file.clicked.connect(self.openFileNameDialog)
        self.reload.clicked.connect(self.refresh_envs)
        self.create_location.clicked.connect(self.create_environment)
        self.create_mapset.clicked.connect(self.create_new_grass_mapset)
        self.exit.clicked.connect(self.close)

        self.epsg_code.addItems(codelist)
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        self.button_group.addButton(self.choice_epsg)
        self.button_group.addButton(self.choice_georef)
        self.choice_epsg.toggled.connect(self.enable_widget)
        self.choice_georef.toggled.connect(self.enable_widget)

        self.refresh_envs()

    # ------------------------------------------------------------------ #
    # Connection / settings                                               #
    # ------------------------------------------------------------------ #

    def _load_conn(self):
        """Read endpoint + API key from the plugin settings (no validation)."""
        settings = load_config(self.config) or {}
        proc = settings.get("Processing", {}) or {}
        self.endpoint = proc.get("grass_api_endpoint") or grass_api.DEFAULT_ENDPOINT
        self.api_key = proc.get("grass_api_key") or ""

    def _creds(self):
        """Return ``(endpoint, api_key)``; the endpoint field overrides settings."""
        endpoint = self.grass_api_endpoint.text().strip() or self.endpoint
        return endpoint, self.api_key

    def showEvent(self, event):
        """Refresh connection + environment list each time the dialog opens."""
        self._load_conn()
        if not self.grass_api_endpoint.text().strip():
            self.grass_api_endpoint.setText(self.endpoint)
        self.refresh_envs()
        super().showEvent(event)

    # ------------------------------------------------------------------ #
    # Environment listing / selection                                     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _env_label(env: dict) -> str:
        loc = env.get("location", "?")
        mapset = env.get("mapset", "?")
        return f"{loc} / {mapset}  ({str(env.get('env_id', ''))[:8]})"

    def refresh_envs(self):
        """Populate the environment combo from ``GET /grass/env``."""
        endpoint, api_key = self._creds()
        if not api_key:
            self._report(
                "No GRASS API key configured.\nSet it in Settings (Processing).",
                ok=False)
            self.grass_location_list.clear()
            return
        keep = self.env_id
        try:
            envs = grass_api.list_envs(endpoint, api_key)
        except GrassApiError as exc:
            self._report(str(exc), ok=False)
            self.grass_location_list.clear()
            return
        self._envs = {e["env_id"]: e for e in envs if e.get("env_id")}
        self.grass_location_list.clear()
        for env in envs:
            self.grass_location_list.addItem(self._env_label(env), env.get("env_id"))
        # Restore previous selection if still present
        if keep and keep in self._envs:
            idx = self.grass_location_list.findData(keep)
            if idx >= 0:
                self.grass_location_list.setCurrentIndex(idx)
        self._report(f"{len(envs)} environment(s) available", ok=True)

    def use_selected_env(self):
        """Activate the environment currently selected in the combo."""
        idx = self.grass_location_list.currentIndex()
        env_id = self.grass_location_list.itemData(idx) if idx >= 0 else None
        if not env_id:
            self.grassenabled = False
            self._report("No environment selected.", ok=False)
            return
        self.env_id = env_id
        self.active_env = self._envs.get(env_id)
        self.grassenabled = True
        label = self.grass_location_list.itemText(idx)
        QgsMessageLog.logMessage(
            f"Active GRASS environment: {label} ({env_id})",
            'GroundTruther', Qgis.Info)
        self._report(f"Active environment:\n{label}\nenv_id: {env_id}", ok=True)

    def get_active_env(self):
        """Return the active ``env_id`` (or ``None`` if none selected)."""
        return self.env_id

    # ------------------------------------------------------------------ #
    # Environment / mapset creation                                       #
    # ------------------------------------------------------------------ #

    def create_environment(self):
        """Create a new environment from an EPSG code or a georef dataset."""
        endpoint, api_key = self._creds()
        location = self.new_location_name.text().strip()
        if not location:
            self._report("Please enter a name for the new environment (location).",
                         ok=False)
            return
        try:
            if self.choice_georef.isChecked():
                path = self.georef_file.text().strip()
                if not path:
                    self._report("Please choose a georeferenced dataset file.",
                                 ok=False)
                    return
                env = grass_api.create_env_dataset(
                    endpoint, api_key, file_path=path, location=location,
                    persist=True)
            else:
                try:
                    epsg = int(self.epsg_code.currentText().strip())
                except ValueError:
                    self._report("Invalid EPSG code.", ok=False)
                    return
                env = grass_api.create_env_epsg(
                    endpoint, api_key, epsg=epsg, location=location, persist=True)
        except GrassApiError as exc:
            self._report(str(exc), ok=False)
            return
        self._report(json.dumps(env, indent=2, sort_keys=True), ok=True)
        self.env_id = env.get("env_id")
        self.refresh_envs()

    def create_new_grass_mapset(self):
        """Create a new mapset within the active environment's location."""
        endpoint, api_key = self._creds()
        if not self.env_id:
            self._report("Select an environment first (Use Environment).", ok=False)
            return
        mapset = self.new_mapset.text().strip()
        if not mapset:
            self._report("Please enter a name for the new mapset.", ok=False)
            return
        try:
            env = grass_api.create_mapset(
                endpoint, api_key, self.env_id, mapset=mapset)
        except GrassApiError as exc:
            self._report(str(exc), ok=False)
            return
        self._report(json.dumps(env, indent=2, sort_keys=True), ok=True)
        # A new mapset is itself a new env; make it active and refresh
        self.env_id = env.get("env_id")
        self.refresh_envs()

    # ------------------------------------------------------------------ #
    # UI helpers                                                           #
    # ------------------------------------------------------------------ #

    def _report(self, message: str, ok: bool):
        """Show *message* in the output box and colour the status frame."""
        self.command_output.setText(message)
        self.set_status_color("SUCCESS" if ok else "FAILED")
        if not ok:
            QgsMessageLog.logMessage(message, 'GroundTruther', Qgis.Warning)

    def set_status_color(self, status):
        if status == "SUCCESS":
            self.frame.setStyleSheet(
                "QFrame { border: 1px solid black; border-radius: 1px;"
                " background-color: rgb(51, 209, 122); }")
        else:
            self.frame.setStyleSheet(
                "QFrame { border: 1px solid black; border-radius: 1px;"
                " background-color: rgb(237, 51, 59); }")

    def show_searchepsg_dialog(self):
        self.searchepsg_dialog.exec()

    def enable_widget(self):
        if self.choice_epsg.isChecked():
            self.georef_file.setEnabled(False)
            self.set_georef_file.setEnabled(False)
            self.epsg_code.setEnabled(True)
        if self.choice_georef.isChecked():
            self.epsg_code.setEnabled(False)
            self.georef_file.setEnabled(True)
            self.set_georef_file.setEnabled(True)

    def show_hide_output_log(self):
        self.command_output.setVisible(not self.command_output.isVisible())

    def show_hide_new_grass_location(self):
        visible = self.grass_new_location_groupbox.isVisible()
        self.grass_new_location_groupbox.setVisible(not visible)
        self.grass_new_mapset_groupbox.setVisible(not visible)

    def openFileNameDialog(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Select a georeferenced dataset", "",
            "Raster/Vector (*.tif *.tiff *.gpkg *.shp *.zip);;All Files (*)")
        if file_name:
            QgsMessageLog.logMessage(
                f"georef file selected: {file_name}", 'GroundTruther', Qgis.Info)
            self.georef_file.setText(file_name)
