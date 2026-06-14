"""grm_lsi runner — a preset of the generic schema-driven module runner.

The dialog is built on demand from the module's interface schema (see
``pygui/grass_module_runner.py``) and executed asynchronously via the FastGIS
task queue.

NOTE: ``grm_lsi`` is not currently installed on the FastGIS server, so the form
will report the module as unavailable until it is added (e.g. via
``g.extension``).  Adjust the module name below if it is installed under a
different name.
"""
from groundtruther.pygui.grass_module_runner import ModuleRunnerWidget


class GrmLsiWidget(ModuleRunnerWidget):
    """Run ``grm_lsi`` against the active GRASS environment."""

    def __init__(self, parent):
        super().__init__(parent, "grm_lsi")
