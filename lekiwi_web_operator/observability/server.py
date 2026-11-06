"""Loopback raw-event intake and read-only dashboard. CORE is not connected."""

import argparse
import hmac
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit, unquote

from .collector import Collector
from .store import EventStore
from .events import normalize_event, StructuredEvent

ASSETS = Path(__file__).resolve().parents[1] / "web" / "monitor"


def wire_event(event):
    result = dict(event)
    normalized = {key: value for key, value in event.items() if key != "record_id"}
    result["content_hash"] = StructuredEvent.from_dict(normalized).content_hash()
    result["raw_json"] = json.dumps(event, ensure_ascii=True, separators=(",", ":"))
    result["sequence"] = str(event["sequence"])
    return result


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, status, value, mime="application/json; charset=utf-8"):
        body = (
            value
            if isinstance(value, bytes)
            else json.dumps(value, ensure_ascii=True).encode()
        )
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'",
        )
        self.end_headers()
        self.wfile.write(body)

    def local(self):
        expected = f"127.0.0.1:{self.server.server_port}"
        return (
            self.headers.get("Host") == expected
            and self.headers.get("Origin", "http://" + expected) == "http://" + expected
        )

    def do_GET(self):
        if not self.local():
            return self.reply(403, {"error": "origin_rejected"})
        parsed = urlsplit(self.path)
        path = parsed.path
        try:
            if path == "/api/health":
                return self.reply(
                    200,
                    {
                        "collector": self.server.collector.status(),
                        "store": self.server.store.stats(),
                        "core_connected": False,
                    },
                )
            if path == "/api/events":
                q = parse_qs(parsed.query)
                if set(q) - {
                    "limit",
                    "after",
                    "source",
                    "since",
                    "until",
                    "trace_id",
                } or any(len(v) != 1 for v in q.values()):
                    raise ValueError()
                args = {k: v[0] for k, v in q.items()}
                args["limit"] = int(args.get("limit", 100))
                args["after"] = int(args.get("after", 0))
                if not 1 <= args["limit"] <= 200 or args["after"] < 0:
                    raise ValueError()
                page = self.server.store.list_events(**args)
                page["events"] = [wire_event(event) for event in page["events"]]
                return self.reply(200, page)
            if path == "/api/diagnostics":
                return self.reply(200, {"diagnostics": self.server.store.diagnostics()})
            if path.startswith("/api/events/"):
                result = self.server.store.get_event(
                    unquote(path.removeprefix("/api/events/"))
                )
                return (
                    self.reply(200, wire_event(result))
                    if result
                    else self.reply(404, {"error": "not_found"})
                )
            if path == "/api/alerts":
                return self.reply(200, {"count": 0, "limit": 100, "alerts": []})
            if path == "/":
                self.send_response(302)
                self.send_header("Location", "/monitor/")
                self.end_headers()
                return
            from xlerobot_web_operator.monitor_assets import FILES

            if path not in FILES:
                return self.reply(404, {"error": "not_found"})
            filename, mime = FILES[path]
            return self.reply(200, (ASSETS / filename).read_bytes(), mime)
        except (ValueError, TypeError):
            return self.reply(400, {"error": "invalid_query"})
        except Exception:
            return self.reply(503, {"error": "observation_unavailable"})

    def do_POST(self):
        if not self.local():
            return self.reply(403, {"error": "origin_rejected"})
        if self.path != "/api/ingest":
            return self.reply(404, {"error": "not_found"})
        if not hmac.compare_digest(
            self.headers.get("Authorization", ""), "Bearer " + self.server.token
        ):
            return self.reply(401, {"error": "unauthorized"})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if (
                not 0 < size <= 65536
                or self.headers.get("Content-Type") != "application/json"
            ):
                raise ValueError()
            event = json.loads(self.rfile.read(size))
            if not isinstance(event, dict):
                raise ValueError()
            event.pop("observed_at", None)
            event = normalize_event(event)
            accepted = self.server.collector.submit(event)
            # Intake is queued, not durably acknowledged. Sender retains spool.
            return self.reply(
                202 if accepted else 503, {"accepted": accepted, "durable": False}
            )
        except (ValueError, TypeError):
            return self.reply(400, {"error": "invalid_event"})


def make_server(directory, token, port=18095):
    if not isinstance(token, str) or len(token) < 16:
        raise ValueError(
            "An explicit event token of at least 16 characters is required"
        )
    collector = Collector(Path(directory))
    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        server.daemon_threads = True
        server.token = token
        server.collector = collector
        server.store = EventStore(Path(directory) / "events.sqlite3")
        return server
    except Exception:
        collector.close()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("private/native-events"))
    parser.add_argument("--port", type=int, default=18095)
    args = parser.parse_args()
    server = make_server(
        args.data_dir, os.environ.get("XLEROBOT_EVENT_TOKEN", ""), args.port
    )
    print(f"Observation dashboard: http://127.0.0.1:{args.port}/monitor/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        server.collector.close()


if __name__ == "__main__":
    main()
