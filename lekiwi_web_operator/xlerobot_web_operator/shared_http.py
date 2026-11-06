"""Extra web routes on the native server. No control HTTP/WS relay or listener."""

import http.client
import json
import math
import re
import stat
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from urllib.parse import urlsplit

from lekiwi_web_operator.http_server import (
    OperatorRequestHandler,
    _json_reply,
    _error_reply,
)
from lekiwi_web_operator.robot_api import error_result, ok_result
from xlerobot_web_operator.map_library import MapLibrary
from xlerobot_web_operator.web_assets import ROOT, FILES as WEB_FILES
from xlerobot_web_operator.monitor_assets import FILES as MONITOR_FILES, asset

OBSERVER_READ_ROUTES = {"/api/events", "/api/health", "/api/diagnostics", "/api/alerts"}
CAMERA_CHANNELS_DECLARATION = 'const CAMERA_CHANNELS = Object.freeze({"top":"top","left_wrist":"left_wrist","right_wrist":"right_wrist"}); // gateway-camera-profile'
DEVICE_ROLES = (
    "lekiwi_motor",
    "lekiwi_arm",
    "lekiwi_arm_left",
    "lekiwi_arm_right",
    "ydlidar",
)


def configured_device_ready(path):
    """Inspect only an explicit /dev character-device path; never open a bus."""
    if path is None:
        return None
    if (
        not isinstance(path, str)
        or not re.fullmatch(r"/dev/[A-Za-z0-9_./:+-]{1,240}", path)
        or ".." in PurePosixPath(path).parts
    ):
        return False
    try:
        resolved = Path(path).resolve(strict=True)
        if not resolved.is_relative_to(Path("/dev")):
            return False
        return stat.S_ISCHR(resolved.stat().st_mode)
    except (OSError, RuntimeError, ValueError):
        return False


def camera_channels(value=None):
    """Only known aliases for the native binary camera IDs; no arbitrary code."""
    defaults = {"top": "top", "left_wrist": "left_wrist", "right_wrist": "right_wrist"}
    if value is None:
        return defaults
    choices = {
        "top": {"top", "front"},
        "left_wrist": {"left_wrist", "wrist"},
        "right_wrist": {"right_wrist"},
    }
    if (
        not isinstance(value, dict)
        or set(value) - set(choices)
        or any(
            target is not None
            and (not isinstance(target, str) or target not in choices[role])
            for role, target in value.items()
        )
    ):
        raise ValueError("Invalid camera channel profile")
    return {role: value.get(role) for role in defaults}


class SharedRequestHandler(OperatorRequestHandler):
    """Native Host/Origin, WS identity, size limits and lease checks remain in force."""

    def _serve_static(self, path):
        if path == "/mobile":
            return self._send(
                200,
                "text/html; charset=utf-8",
                b'<meta http-equiv="refresh" content="0;url=/mobile/">',
            )
        if path in MONITOR_FILES:
            data, mime = asset(path)
            return self._send(200, mime, data)
        if not path.startswith("/mobile/"):
            return super()._serve_static(path)
        relative = "/" + path[len("/mobile/") :]
        name = WEB_FILES.get(relative)
        if name is None:
            return self._send(*_error_reply(404, "없는 모바일 파일입니다"))
        file = ROOT / name
        data = file.read_bytes()
        if relative == "/native/connection.js":
            text = data.decode("utf8")
            if text.count(CAMERA_CHANNELS_DECLARATION) != 1:
                return self._send(*_error_reply(503, "카메라 채널 설정을 확인하세요"))
            declaration = (
                "const CAMERA_CHANNELS = Object.freeze("
                + json.dumps(self.server.mobile.camera_channels, separators=(",", ":"))
                + "); // gateway-camera-profile"
            )
            data = text.replace(CAMERA_CHANNELS_DECLARATION, declaration).encode("utf8")
        mime = {
            ".html": "text/html",
            ".js": "text/javascript",
            ".css": "text/css",
            ".svg": "image/svg+xml",
        }[file.suffix]
        return self._send(200, mime + "; charset=utf-8", data)

    def _get_api(self, path, query):
        if path in OBSERVER_READ_ROUTES or path.startswith("/api/events/"):
            if not self._is_same_origin():
                return _error_reply(403, "다른 사이트에서 온 요청은 받지 않습니다")
            return self.observer_reply()
        if path == "/api/mobile/diagnostics":
            envelope, confirmed = self.device_geometry()
            return _json_reply(
                200,
                {
                    "devices": self.device_status(),
                    "envelope": envelope,
                    "geometry_confirmed": confirmed,
                    "physical_motion_verified": False,
                },
            )
        if path in ("/api/library", "/api/maps/export"):
            try:
                if path == "/api/library":
                    return _json_reply(200, self.server.mobile.library.read())
                return (
                    200,
                    "application/zip",
                    self.server.mobile.library.export(query.get("name", [""])[0]),
                )
            except (ValueError, OSError):
                return _error_reply(400, "지도를 내보낼 수 없습니다")
        return super()._get_api(path, query)

    def _run_post(self, path, client_id, body):
        if path == "/api/library/route":
            if not self.server.robot.is_operator(client_id):
                return error_result(
                    "not_operator", "지도 정보를 바꾸려면 조종 권한을 받으세요"
                )
            if self.server.robot.get_info().get("is_read_only"):
                return error_result("read_only", "보기 전용에서는 저장할 수 없습니다")
            try:
                saved = self.server.mobile.library.save(
                    body.get("name"), body.get("label", ""), body.get("route", [])
                )
                return ok_result("지도 정보를 저장했습니다", map=saved)
            except (ValueError, OSError):
                return error_result("bad_request", "지도 이름과 경로를 확인하세요")
        autonomous = path in (
            "/api/explore/start",
            "/api/nav/goal",
            "/api/nav/initial_pose",
        ) or (
            path == "/api/process/start"
            and body.get("name") in ("mapping", "navigation")
        )
        starts = (
            autonomous
            or path == "/api/process/start"
            or (path == "/api/motor/power" and body.get("enabled") is True)
        )
        if starts:
            required = ("lekiwi_motor", "ydlidar") if autonomous else ("lekiwi_motor",)
            devices = self.device_status()
            missing = [role for role in required if devices.get(role) is not True]
            if missing:
                return error_result(
                    "conflict",
                    "필요한 장치 경로를 확인할 수 없습니다: " + ", ".join(missing),
                )
        return super()._run_post(path, client_id, body)

    def device_status(self):
        probe = getattr(self.server.mobile, "device_probe", None)
        if probe:
            return probe()
        profile = getattr(self.server.mobile, "device_profile", {})
        paths = profile.get("device_paths", {}) if isinstance(profile, dict) else {}
        if not isinstance(paths, dict):
            paths = {}
        return {role: configured_device_ready(paths.get(role)) for role in DEVICE_ROLES}

    def device_geometry(self):
        profile = getattr(self.server.mobile, "device_profile", {})
        profile = profile if isinstance(profile, dict) else {}
        envelope = profile.get("envelope")
        if not isinstance(envelope, dict):
            return None, False
        values = {
            key: envelope[key]
            for key in ("width", "depth", "height", "radius")
            if key in envelope
        }
        if not all(key in values for key in ("width", "depth", "height")) or any(
            type(value) not in (int, float) or not math.isfinite(value) or value <= 0
            for value in values.values()
        ):
            return None, False
        return values, profile.get("geometry_confirmed") is True

    def observer_reply(self):
        """GET-only observation. Never forward browser credentials."""
        port = getattr(self.server.mobile, "observer_port", 18095)
        if type(port) is not int or not 1 <= port <= 65535:
            return _error_reply(502, "운영 로그 서버 설정을 확인하세요")
        parsed = urlsplit(self.path)
        target = parsed.path + ("?" + parsed.query if parsed.query else "")
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        try:
            conn.request("GET", target, headers={"Origin": f"http://127.0.0.1:{port}"})
            result = conn.getresponse()
            if 300 <= result.status < 400:
                raise ValueError("Observer redirect rejected")
            body = result.read(8 * 1024 * 1024 + 1)
            if len(body) > 8 * 1024 * 1024:
                raise ValueError("Observation response too large")
            return (
                result.status,
                result.getheader("Content-Type", "application/json"),
                body,
            )
        except (OSError, ValueError, http.client.HTTPException):
            return _error_reply(502, "운영 로그 서버에 연결할 수 없습니다")
        finally:
            conn.close()


def make_request_handler(config_path, *, map_dir, library, observer_port=18095):
    """Read configuration before startup; attach it before any connection is accepted."""
    config = json.loads(Path(config_path).read_text(encoding="utf8"))
    if (
        not isinstance(config, dict)
        or type(observer_port) is not int
        or not 1 <= observer_port <= 65535
    ):
        raise ValueError("Invalid shared web configuration")
    state = SimpleNamespace(
        camera_channels=camera_channels(config.get("camera_channels")),
        device_profile=config.get("device_profile", {}),
        observer_port=observer_port,
        library=MapLibrary(map_dir, library),
    )

    class ConfiguredHandler(SharedRequestHandler):
        def __init__(self, request, client_address, server):
            # Native server owns every connection and the one Hub.
            server.mobile = state
            super().__init__(request, client_address, server)

    return ConfiguredHandler
