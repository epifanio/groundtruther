"""Shared pytest setup for the GroundTruther test suite.

The plugin's code is imported as the ``groundtruther`` package, but the repo root
*is* that package (it also contains a ``groundtruther.py`` module). So we register
``groundtruther`` as a namespace package pointing at the repo root, and stub
``groundtruther.configure`` with a no-op ``log_exception`` — that lets the
stateless ``gt/`` helpers be imported for **unit tests without pulling in QGIS**
(the real ``configure`` imports ``qgis.PyQt``).

GUI tests import QGIS themselves (guarded by ``importorskip``); integration tests
hit the live API and are opt-in.
"""
import sys
import types
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

# 1. Make `groundtruther` resolve to the repo as a package.
if "groundtruther" not in sys.modules:
    pkg = types.ModuleType("groundtruther")
    pkg.__path__ = [str(ROOT)]
    sys.modules["groundtruther"] = pkg

# 2. Stub `groundtruther.configure` so importing gt.* stays QGIS-free.
if "groundtruther.configure" not in sys.modules:
    cfg = types.ModuleType("groundtruther.configure")
    cfg.log_exception = lambda *a, **k: None
    cfg.error_message = lambda *a, **k: None
    sys.modules["groundtruther.configure"] = cfg

# 3. Make `groundtruther.gt` a package pointing at gt/.
if "groundtruther.gt" not in sys.modules:
    gt = types.ModuleType("groundtruther.gt")
    gt.__path__ = [str(ROOT / "gt")]
    sys.modules["groundtruther.gt"] = gt
