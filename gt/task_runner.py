"""Async GRASS module execution via the FastGIS task queue.

Wraps ``grass_api.submit_task`` + polling of ``grass_api.get_task`` in a
:class:`QgsTask` so long-running GRASS modules run off the UI thread, surface
progress in the QGIS task-manager bar, and can be cancelled.

Typical use::

    from groundtruther.gt.task_runner import run_module_task
    task = run_module_task(
        endpoint, api_key, env_id, "r.geomorphon",
        params={"elevation": "dem", "forms": "geo"},
        on_progress=lambda msg: report.append(msg),
        on_success=lambda payload: report.append("done"),
        on_error=lambda detail: report.append("ERROR: " + detail),
    )
"""
import time

from qgis.core import QgsApplication, QgsTask
from qgis.PyQt.QtCore import pyqtSignal

from groundtruther.gt import grass_api

# Terminal Celery / FastGIS task states (see app/tasks/grass_tasks.py)
_OK_STATES = {"SUCCESS"}
_FAIL_STATES = {"FAILURE", "GRASS_FAILURE", "REVOKED"}


def _state_of(payload: dict) -> str:
    return (payload or {}).get("state") or (payload or {}).get("status") or ""


def _format_failure(payload: dict) -> str:
    """Build a readable error from a failed task payload."""
    result = (payload or {}).get("result") or (payload or {}).get("info") or {}
    if isinstance(result, dict):
        stderr = result.get("stderr")
        if isinstance(stderr, list):
            stderr = "\n".join(stderr)
        if stderr:
            return str(stderr)
        if result.get("error"):
            return str(result["error"])
    return f"task {_state_of(payload) or 'failed'}"


class GrassModuleTask(QgsTask):
    """Submit a GRASS module run and poll it to completion off the UI thread."""

    progressed = pyqtSignal(str)   # human-readable progress line
    succeeded = pyqtSignal(dict)   # final task payload (stdout/stderr/returncode)
    errored = pyqtSignal(str)      # error detail

    def __init__(self, endpoint, api_key, env_id, module, *,
                 params=None, flags=None, args=None,
                 poll_interval=1.0, description=None):
        super().__init__(description or f"GRASS {module}", QgsTask.Flag.CanCancel)
        self.endpoint = endpoint
        self.api_key = api_key
        self.env_id = env_id
        self.module = module
        self.params = params
        self.flags = flags
        self.args = args
        self.poll_interval = poll_interval
        self._task_id = None
        self._result = None
        self._error = None

    def run(self) -> bool:
        """Worker-thread body: submit then poll.  Returns True on success."""
        try:
            sub = grass_api.submit_task(
                self.endpoint, self.api_key, self.env_id, self.module,
                params=self.params, flags=self.flags, args=self.args)
            self._task_id = sub.get("task_id")
            self.progressed.emit(f"{self.module}: submitted (task {self._task_id})")

            while True:
                if self.isCanceled():
                    self._safe_cancel()
                    self._error = "cancelled by user"
                    return False
                payload = grass_api.get_task(self.endpoint, self.api_key, self._task_id)
                state = _state_of(payload)
                self.progressed.emit(f"{self.module}: {state or 'running'}")
                if state in _OK_STATES:
                    self._result = payload
                    return True
                if state in _FAIL_STATES:
                    self._error = _format_failure(payload)
                    return False
                time.sleep(self.poll_interval)
        except grass_api.GrassApiError as exc:
            self._error = str(exc)
            return False

    def _safe_cancel(self) -> None:
        if not self._task_id:
            return
        try:
            grass_api.cancel_task(self.endpoint, self.api_key, self._task_id)
        except grass_api.GrassApiError:
            pass

    def finished(self, ok: bool) -> None:
        """Main-thread completion callback (emits the terminal signal)."""
        if ok and self._result is not None:
            self.succeeded.emit(self._result)
        else:
            self.errored.emit(self._error or "unknown error")


def run_module_task(endpoint, api_key, env_id, module, *,
                    params=None, flags=None, args=None,
                    on_progress=None, on_success=None, on_error=None,
                    poll_interval=1.0, description=None) -> GrassModuleTask:
    """Create, wire, and dispatch a :class:`GrassModuleTask`.

    Returns the task (already added to the QGIS task manager) so the caller can
    keep a reference / cancel it.  The optional callbacks run on the UI thread.
    """
    task = GrassModuleTask(
        endpoint, api_key, env_id, module,
        params=params, flags=flags, args=args,
        poll_interval=poll_interval, description=description)
    if on_progress:
        task.progressed.connect(on_progress)
    if on_success:
        task.succeeded.connect(on_success)
    if on_error:
        task.errored.connect(on_error)
    QgsApplication.taskManager().addTask(task)
    return task
