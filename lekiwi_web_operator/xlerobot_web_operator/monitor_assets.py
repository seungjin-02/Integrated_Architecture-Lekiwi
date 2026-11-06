"""Fixed monitor asset allowlist shared by shared web and loopback servers."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "web" / "monitor"
FILES = {
    "/monitor/": ("index.html", "text/html; charset=utf-8"),
    "/monitor/index.html": ("index.html", "text/html; charset=utf-8"),
    "/monitor/monitor.css": ("monitor.css", "text/css; charset=utf-8"),
}
for name in (
    "monitor.js", "raw-events.js", "raw-contract.js", "dashboard-ui.js",
    "display-contract.js", "fixtures.js", "mock-adapter.js", "robot-copy.js",
):
    FILES[f"/monitor/{name}"] = (name, "text/javascript; charset=utf-8")
for name, mime in (
    ("Geist.ttf", "font/ttf"),
    ("GeistMono.ttf", "font/ttf"),
    ("PretendardVariable.woff2", "font/woff2"),
):
    FILES[f"/monitor/fonts/{name}"] = (f"fonts/{name}", mime)


def asset(path):
    name, mime = FILES[path]
    return (ROOT / name).read_bytes(), mime
