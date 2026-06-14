"""r.geomorphon runner — a preset of the generic schema-driven module runner.

The bespoke form is gone: the dialog is now built on demand from the module's
interface schema (see ``pygui/grass_module_runner.py``) and executed
asynchronously via the FastGIS task queue.
"""
from groundtruther.pygui.grass_module_runner import ModuleRunnerWidget


class GeoMorphonWidget(ModuleRunnerWidget):
    """Run ``r.geomorphon`` against the active GRASS environment."""

    def __init__(self, parent):
        super().__init__(parent, "r.geomorphon")
