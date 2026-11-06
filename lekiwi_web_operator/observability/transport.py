"""Bounded native-hook sink; durable local spool precedes HTTP intake."""

import json
import math
import os
from pathlib import Path
import queue
import threading
import time
import stat
from urllib.parse import urlsplit, quote
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
from urllib.error import HTTPError
from .events import normalize_event, StructuredEvent


class _NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def _write_all(file, data):
    offset = 0
    while offset < len(data):
        count = file.write(data[offset:])
        if type(count) is not int or not 0 < count <= len(data) - offset:
            raise OSError("short_write")
        offset += count


def _private_file(path):
    if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
        raise ValueError("Linked spool rejected")
    descriptor = os.open(
        path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600
    )
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise ValueError("Spool must be a regular file")
    return os.fdopen(descriptor, "r+b", buffering=0)


class DurableSink:
    def __init__(
        self, directory, endpoint, token, max_queue=1000, max_bytes=64 * 1024 * 1024
    ):
        url = urlsplit(endpoint)
        if (
            url.scheme != "http"
            or url.hostname != "127.0.0.1"
            or url.path != "/api/ingest"
            or url.query
            or url.fragment
            or url.username
        ):
            raise ValueError("Use a loopback /api/ingest endpoint")
        if (
            not isinstance(token, str)
            or not 16 <= len(token) <= 4096
            or any(ord(c) < 32 or ord(c) > 126 for c in token)
        ):
            raise ValueError("An explicit event token is required")
        if type(max_queue) is not int or not 1 <= max_queue <= 100000:
            raise ValueError("Invalid transport queue size")
        if type(max_bytes) is not int or not 1 <= max_bytes <= 1024**3:
            raise ValueError("Invalid spool size")
        directory = Path(directory).absolute()
        for component in (directory, *directory.parents):
            if (
                component.is_symlink()
                or getattr(component, "is_junction", lambda: False)()
            ):
                raise ValueError("Linked spool directory rejected")
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = directory / "native-spool.jsonl"
        if self.path.is_symlink():
            raise ValueError("Linked spool rejected")
        self.endpoint, self.token, self.max_bytes = endpoint, token, max_bytes
        self.queue = queue.Queue(maxsize=max_queue)
        self.stop = threading.Event()
        self._state = threading.Lock()
        self._fatal = False
        self.error = None
        self.dropped = self.written = self.delivered = 0
        self._opener = build_opener(ProxyHandler({}), _NoRedirects())
        self._lease = _private_file(directory / ".native-spool.lock")
        try:
            if os.name == "nt":
                import msvcrt

                if os.fstat(self._lease.fileno()).st_size == 0:
                    _write_all(self._lease, b"0")
                self._lease.seek(0)
                msvcrt.locking(self._lease.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._lease.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self._lease.close()
            raise ValueError("Another producer owns this spool directory") from None
        self.thread = threading.Thread(
            target=self._run, daemon=True, name="native-event-delivery"
        )
        try:
            self.thread.start()
        except Exception:
            self._lease.close()
            raise

    def submit(self, event):
        if self.stop.is_set() or self._fatal:
            self.dropped += 1
            return False
        try:
            normalized = normalize_event(event)
            normalized.pop("observed_at", None)
            data = (
                json.dumps(
                    normalized,
                    ensure_ascii=True,
                    allow_nan=False,
                    separators=(",", ":"),
                )
                + "\n"
            ).encode()
            if len(data) > 65536:
                raise ValueError()
            with self._state:
                if self.stop.is_set() or self._fatal:
                    self.dropped += 1
                    return False
                self.queue.put_nowait(data)
            return True
        except (ValueError, TypeError, OverflowError, RecursionError, queue.Full):
            self.dropped += 1
            self.error = "queue_or_event_rejected"
            return False

    __call__ = submit

    def _run(self):
        offset = 0  # Replays retained evidence after restart; collector deduplicates.
        retry_at = 0
        try:
            with _private_file(self.path) as spool:
                spool.seek(0, 2)
                size = spool.tell()
                if size > self.max_bytes:
                    self.error = "spool_size_limit"
                    return
                if size:
                    spool.seek(-1, 2)
                    if spool.read(1) != b"\n":
                        self.error = "spool_corrupt"
                        return
                while not self.stop.is_set() or not self.queue.empty():
                    try:
                        # A retained backlog already provides work. Only wait for
                        # new producer data when caught up, or backing off after
                        # an intake failure; otherwise replay incurred 50ms/event.
                        replay_ready = offset < size and time.monotonic() >= retry_at
                        data = self.queue.get(timeout=0 if replay_ready else 0.05)
                    except queue.Empty:
                        data = None
                    if data is not None:
                        try:
                            spool.seek(0, 2)
                            if spool.tell() + len(data) > self.max_bytes:
                                raise OSError()
                            _write_all(spool, data)
                            os.fsync(spool.fileno())
                            size = spool.tell()
                            self.written += 1
                        except OSError:
                            self.error = "spool_write_failed"
                            self._fatal = True
                            self.dropped += 1
                        finally:
                            self.queue.task_done()
                    if self._fatal:
                        break
                    if self.stop.is_set() or time.monotonic() < retry_at:
                        continue
                    spool.seek(offset)
                    line = spool.readline(65537)
                    if not line:
                        continue
                    if len(line) > 65536 or not line.endswith(b"\n"):
                        self.error = "spool_corrupt"
                        retry_at = time.monotonic() + 5
                        continue
                    try:
                        request = Request(
                            self.endpoint,
                            data=line,
                            headers={
                                "Authorization": "Bearer " + self.token,
                                "Content-Type": "application/json",
                            },
                            method="POST",
                        )
                        with self._opener.open(request, timeout=1) as response:
                            if response.status != 202:
                                raise OSError()
                        source_event = StructuredEvent.from_dict(json.loads(line))
                        event_id = source_event.event_id
                        receipt = (
                            self.endpoint.removesuffix("/ingest")
                            + "/events/"
                            + quote(event_id, safe="")
                        )
                        # Intake is asynchronous: a 202 may precede the SQLite
                        # commit. Briefly poll the receipt instead of replaying
                        # the POST and waiting one second for every new event.
                        receipt_deadline = time.monotonic() + 0.5
                        while True:
                            try:
                                with self._opener.open(receipt, timeout=1) as response:
                                    raw = response.read(131073)
                                    if len(raw) > 131072 or response.status != 200:
                                        raise OSError()
                                    if (
                                        json.loads(raw).get("content_hash")
                                        != source_event.content_hash()
                                    ):
                                        raise OSError()
                                break
                            except HTTPError as error:
                                error.close()
                                if (
                                    error.code != 404
                                    or time.monotonic() >= receipt_deadline
                                ):
                                    raise
                                time.sleep(0.01)
                        offset += len(line)
                        self.delivered += 1
                        self.error = None
                    except Exception:
                        self.error = "intake_unavailable"
                        retry_at = time.monotonic() + 1
        except Exception:
            self.error = "spool_unavailable"
        finally:
            with self._state:
                self._fatal = True
                while True:
                    try:
                        self.queue.get_nowait()
                    except queue.Empty:
                        break
                    self.dropped += 1
                    self.queue.task_done()
            self._lease.close()

    def status(self):
        return {
            "written": self.written,
            "confirmed_persisted": self.delivered,
            "dropped": self.dropped,
            "pending": self.queue.qsize(),
            "error": self.error,
            "closed": not self.thread.is_alive(),
        }

    def close(self, timeout=2):
        if (
            type(timeout) not in (int, float)
            or not math.isfinite(timeout)
            or not 0 <= timeout <= 30
        ):
            raise ValueError("Invalid transport shutdown timeout")
        self.stop.set()
        self.thread.join(timeout)
        if self.thread.is_alive():
            self.error = "flush_timeout"
        return self.status()
