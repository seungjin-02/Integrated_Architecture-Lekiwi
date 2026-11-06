"""Bounded nonblocking producer queue; SQLite I/O belongs to its worker only."""

import queue
import threading
import uuid
from pathlib import Path

from .events import EventValidationError, StructuredEvent
from .store import EventStore


class Collector:
    def __init__(self, directory, *, max_queue=1000):
        if type(max_queue) is not int or not 1 <= max_queue <= 100_000:
            raise ValueError("invalid_queue_size")
        self.directory = Path(directory)
        self.dbpath = self.directory / "events.sqlite3"
        self.run_id = uuid.uuid4().hex
        self._queue = queue.Queue(maxsize=max_queue)
        self._lock = threading.Lock()
        self._closing = threading.Event()
        self._finished = threading.Event()
        self._ready = threading.Event()
        self._counts = dict(
            written=0, duplicates=0, conflicts=0, dropped=0, rejected=0, pending=0
        )
        self._error = None
        self._failed = False
        self._thread = threading.Thread(
            target=self._run, name="xlerobot-event-collector", daemon=True
        )
        self._thread.start()

    def submit(self, event):
        try:
            # Capture a detached sanitized snapshot before handing work to the
            # writer. A caller may mutate its own event immediately afterwards.
            event = StructuredEvent.from_dict(
                event.to_dict() if isinstance(event, StructuredEvent) else event
            )
        except (
            EventValidationError,
            TypeError,
            ValueError,
            OverflowError,
            RecursionError,
        ):
            with self._lock:
                self._counts["rejected"] += 1
            return False
        with self._lock:
            if self._closing.is_set() or self._failed:
                self._counts["dropped"] += 1
                return False
            try:
                self._queue.put_nowait(event)
            except queue.Full:
                self._counts["dropped"] += 1
                return False
            self._counts["pending"] += 1
            return True

    def _run(self):
        store = None
        try:
            try:
                store = EventStore(self.dbpath)
            except Exception:
                with self._lock:
                    self._failed = True
                    self._error = "store_unavailable"
                self._ready.set()
                return
            self._ready.set()
            while not self._closing.is_set() or not self._queue.empty():
                try:
                    event = self._queue.get(timeout=0.05)
                except queue.Empty:
                    continue
                try:
                    result = store.append(event)
                    with self._lock:
                        self._counts[
                            {
                                "written": "written",
                                "duplicate": "duplicates",
                                "conflict": "conflicts",
                            }[result]
                        ] += 1
                except Exception:
                    with self._lock:
                        self._counts["dropped"] += 1
                        self._error = "store_write_failed"
                finally:
                    with self._lock:
                        self._counts["pending"] -= 1
                    self._queue.task_done()
        finally:
            if store is not None:
                try:
                    store.close()
                except Exception:
                    with self._lock:
                        self._error = "store_close_failed"
            # If initialization failed, make queued losses explicit.
            with self._lock:
                if self._failed:
                    self._counts["dropped"] += self._counts["pending"]
                    self._counts["pending"] = 0
                    while not self._queue.empty():
                        self._queue.get_nowait()
                        self._queue.task_done()
            self._finished.set()
            self._ready.set()

    def status(self):
        with self._lock:
            return {
                "enabled": not self._failed and not self._closing.is_set(),
                "ready": self._ready.is_set() and not self._failed,
                "run_id": self.run_id,
                **self._counts,
                "error": self._error,
                "closing": self._closing.is_set(),
                "closed": self._finished.is_set(),
            }

    def close(self, timeout=2.0):
        if type(timeout) not in (int, float) or not 0 <= timeout <= 30:
            raise ValueError("invalid_close_timeout")
        self._closing.set()
        self._thread.join(timeout)
        if not self._finished.is_set():
            with self._lock:
                self._error = "flush_timeout"
        return self.status()
