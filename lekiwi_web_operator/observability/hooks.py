"""Optional native RobotApi instrumentation; never owns robot control or ROS.

Only a bounded in-memory enqueue occurs on the native caller's thread. A daemon
worker invokes the injected transport; collection failures cannot alter native
method return values or exceptions. Async native operations remain unconfirmed.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from functools import wraps
import queue
import re
import threading
import uuid

COMMAND_METHODS = frozenset(
    {
        "start",
        "shutdown",
        "acquire_control",
        "release_control",
        "touch_operator",
        "client_disconnected",
        "set_teleop",
        "set_motor_power",
        "emergency_stop",
        "arm_start",
        "arm_stop",
        "arm_relax",
        "arm_fold",
        "end_arm_session",
        "relay_leader",
        "calibration_follower",
        "start_process",
        "stop_process",
        "save_map",
        "start_exploration",
        "stop_exploration",
        "set_initial_pose",
        "send_nav_goal",
        "cancel_nav_goal",
        "set_navigation_speed",
        "reset_odometry",
    }
)
_correlation = ContextVar("native_observation_correlation", default=(None, None))
_identifier = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")
_credentials = re.compile(
    r"(?i)(authorization\s*[:=]\s*(?:bearer\s+)?|"
    r"(?:access[_ -]?code|api[_ -]?key|password|passwd|token|secret|cookie)\s*[:=]\s*)"
    r"(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)"
)
_bearer = re.compile(r"(?i)\bbearer\s+[^\s,;]+")


def _text(value, limit=2048):
    if not isinstance(value, str):
        return None
    value = _credentials.sub(lambda match: match[1] + "[REDACTED]", value[:limit])
    return _bearer.sub("Bearer [REDACTED]", value)


@contextmanager
def command_context(trace_id=None, command_id=None):
    """Explicit adapter correlation. Values are IDs, never credentials or URLs.

    Context stays on this execution context. Threads started by the native engine
    do not inherit it; their later events deliberately have no inferred command.
    """
    for value in (trace_id, command_id):
        if value is not None and (
            not isinstance(value, str) or not _identifier.fullmatch(value)
        ):
            raise ValueError("Invalid correlation identifier")
    token = _correlation.set(
        (trace_id or uuid.uuid4().hex, command_id or uuid.uuid4().hex)
    )
    try:
        yield _correlation.get()
    finally:
        _correlation.reset(token)


class HookEmitter:
    """Nonblocking producer with bounded queue and bounded close wait.

    The sink may block or fail. Only this worker calls it. Dropped counts describe
    the observation path, never a robot/control failure. Accepted means queued,
    not persisted; the transport exposes its own durability status.
    """

    def __init__(self, sink, max_queue=1024):
        if not callable(sink):
            raise ValueError("A callable observation sink is required")
        if type(max_queue) is not int or not 1 <= max_queue <= 100000:
            raise ValueError("Invalid hook queue size")
        self.run_id = uuid.uuid4().hex
        self._sink = sink
        self._queue = queue.Queue(maxsize=max_queue)
        self._lock = threading.Lock()
        self._sequence = self._accepted = self._dropped = self._delivered = 0
        self._closed = self._closing = False
        self._error = None
        self._thread = threading.Thread(
            target=self._run, name="native-event-hooks", daemon=True
        )
        self._thread.start()

    def emit(self, stage, *, method=None, outcome=None, reason_code=None, payload=None):
        """Best effort only: no exception may cross an instrumentation boundary."""
        try:
            trace_id, command_id = _correlation.get()
            with self._lock:
                if self._closing:
                    self._dropped += 1
                    return False
                self._sequence += 1
                event = {
                    "event_id": uuid.uuid4().hex,
                    "source": "native_engine",
                    "run_id": self.run_id,
                    "sequence": self._sequence,
                    "occurred_at": datetime.now(timezone.utc).isoformat(),
                    "trace_id": trace_id,
                    "command_id": command_id,
                    "stage": stage,
                    "outcome": outcome or "unknown",
                    "reason_code": reason_code,
                    "payload": {"method": method, **(payload or {})},
                }
                try:
                    self._queue.put_nowait(event)
                except queue.Full:
                    self._dropped += 1
                    self._error = "queue_full"
                    return False
                self._accepted += 1
                return True
        except Exception:
            return False

    def native_event(self, event):
        """Listener for existing native facts, not a risk/severity classifier."""
        try:
            if type(event) is not dict:
                return
            kind = event.get("type")
            if kind not in {"event", "log"}:
                return
            payload = {"native_type": kind}
            if event.get("level") in {"info", "warn", "error"}:
                payload["native_level"] = event["level"]
            for key in ("message", "process"):
                text = _text(event.get(key))
                if text is not None:
                    payload[key] = text
            lines = event.get("lines")
            if isinstance(lines, (list, tuple)):
                payload["lines"] = [
                    text for line in lines[:8] if (text := _text(line, 512)) is not None
                ]
            stamp = event.get("time")
            if type(stamp) in (int, float) and -1e15 < stamp < 1e15:
                payload["native_time"] = stamp
            self.emit("observed", outcome="unknown", payload=payload)
        except Exception:
            pass

    def status(self):
        with self._lock:
            return {
                "accepted": self._accepted,
                "delivered": self._delivered,
                "dropped": self._dropped,
                "pending": self._queue.qsize(),
                "closed": self._closed,
                "error": self._error,
            }

    def _run(self):
        try:
            while True:
                try:
                    event = self._queue.get(timeout=0.05)
                except queue.Empty:
                    with self._lock:
                        if self._closing:
                            break
                    continue
                try:
                    accepted = self._sink(event)
                    with self._lock:
                        if accepted is False:
                            self._dropped += 1
                            self._error = "sink_rejected"
                        else:
                            self._delivered += 1
                except Exception:
                    with self._lock:
                        self._dropped += 1
                        self._error = "sink_failed"
                finally:
                    self._queue.task_done()
        finally:
            with self._lock:
                self._closed = True

    def close(self, timeout=2):
        if type(timeout) not in (int, float) or not 0 <= timeout <= 30:
            raise ValueError("Invalid hook shutdown timeout")
        with self._lock:
            self._closing = True
        self._thread.join(timeout)
        if self._thread.is_alive():
            with self._lock:
                self._error = "close_timeout"


class NativeObservedService:
    """Transparent facade over ONE existing RobotService instance.

    Reads and unlisted methods are delegated unchanged. No drivers, publishers,
    timers, control ownership, safety policy, or retry logic are added here.
    """

    def __init__(self, service, emitter):
        self._service = service
        self._emitter = emitter
        self._wrapped = {}
        try:
            service.add_listener(emitter.native_event)
        except Exception:
            self._safe_emit(
                "observed", outcome="unknown", reason_code="listener_unavailable"
            )

    def __getattr__(self, name):
        original = getattr(self._service, name)
        if name not in COMMAND_METHODS or not callable(original):
            return original
        if name not in self._wrapped:

            @wraps(original)
            def call(*args, **kwargs):
                previous = _correlation.get()
                token = None
                if previous == (None, None):
                    token = _correlation.set((uuid.uuid4().hex, uuid.uuid4().hex))
                try:
                    self._safe_emit("received", method=name)
                    self._safe_emit("started", method=name)
                    try:
                        result = original(*args, **kwargs)
                    except BaseException as error:
                        self._safe_emit(
                            "failed",
                            method=name,
                            outcome="unknown",
                            reason_code="native_exception",
                            payload={"exception_type": type(error).__name__[:100]},
                        )
                        raise
                    payload = {"result_kind": "none" if result is None else "returned"}
                    outcome = "unknown"
                    reason = None
                    if type(result) is dict:
                        if type(result.get("ok")) is bool:
                            payload["returned_ok"] = result["ok"]
                            outcome = "accepted" if result["ok"] else "rejected"
                        code = result.get("code")
                        if isinstance(code, str) and _identifier.fullmatch(code):
                            reason = code
                    self._safe_emit(
                        "completed",
                        method=name,
                        outcome=outcome,
                        reason_code=reason,
                        payload=payload,
                    )
                    return result
                finally:
                    if token is not None:
                        _correlation.reset(token)

            self._wrapped[name] = call
        return self._wrapped[name]

    def _safe_emit(self, *args, **kwargs):
        try:
            self._emitter.emit(*args, **kwargs)
        except BaseException:
            # Instrumentation must preserve even native shutdown/signal behavior.
            pass
