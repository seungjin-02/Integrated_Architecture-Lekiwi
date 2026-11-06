"""Disk layout is separate from the stable browser URL contract."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "web" / "mobile"
FILES = {
    "/": "index.html",
    "/mobile.css": "css/mobile.css",
    "/mobile.js": "js/mobile.js",
    "/mission.js": "js/mission.js",
    "/exploration_mission.js": "js/exploration_mission.js",
    "/icon.svg": "icon.svg",
    "/native/connection.js": "js/native/connection.js",
    "/native/format.js": "js/native/format.js",
    "/native/widgets/map_view.js": "js/native/widgets/map_view.js",
    "/native/widgets/canvas.js": "js/native/widgets/canvas.js",
}
