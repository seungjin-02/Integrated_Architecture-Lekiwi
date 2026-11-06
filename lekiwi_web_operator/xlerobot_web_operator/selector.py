"""Shared-engine entry page: links only, no service or robot operations."""

import argparse
import ipaddress
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/":
            self.send_error(404)
            return
        try:
            hostname = urlsplit("//" + self.headers.get("Host", "localhost")).hostname
        except ValueError:
            self.send_error(400)
            return
        try:
            is_ip = ipaddress.ip_address(hostname) is not None
        except (ValueError, TypeError):
            is_ip = False
        if not hostname or not (
            is_ip
            or hostname in ("localhost", "127.0.0.1")
            or hostname.endswith(".local")
        ):
            self.send_error(400)
            return
        css = """*{box-sizing:border-box}body{background:#101820;color:#f1f5f9;font:16px/1.6 system-ui,sans-serif;max-width:1000px;margin:auto;padding:64px 24px}h1{font-size:clamp(25px,4vw,34px);line-height:1.3;letter-spacing:-.03em;margin:0 0 12px}body>p{margin:0 0 32px;text-align:center}h1{text-align:center}.muted{color:#afbecb}section{border:1px solid #415363;border-radius:20px;padding:28px;background:#14212c}.choices{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px}.choice{display:flex;flex-direction:column;min-width:0;padding:24px;border:1px solid #415363;border-radius:14px;background:#192b38}.choice h2{font-size:21px;line-height:1.4;margin:0 0 12px;word-break:keep-all}.choice p{color:#afbecb;font-size:14px;margin:0 0 24px;word-break:keep-all}.choice a{display:flex;align-items:center;justify-content:center;min-height:52px;margin-top:auto;padding:12px 14px;border-radius:10px;background:#9ce6ca;color:#082b22;font-weight:650;text-decoration:none;text-align:center;font-size:15px;word-break:keep-all}.choice a:focus-visible{outline:3px solid #a6ddff;outline-offset:4px}section>.muted{font-size:14px;line-height:1.8;margin:24px 0 0;max-width:none}@media(max-width:640px){body{padding:32px 18px}.choices{grid-template-columns:1fr;gap:16px}section{padding:18px}.choice{padding:20px}.choice h2{font-size:20px}.choice p{margin-bottom:20px}}"""
        css += """
body{min-height:100vh;background:radial-gradient(ellipse at 15% 0%,#164b5138,transparent 50%),radial-gradient(ellipse at 90% 30%,#315c9c22,transparent 45%),#101820}h1{font-weight:750}body>p{font-size:15px;color:#9db4c5}section{position:relative;background:linear-gradient(145deg,#172833dd,#111e2add);box-shadow:0 24px 72px #0003;border-color:#385365}.choice{text-align:center;align-items:center;position:relative;overflow:hidden;padding:30px 24px;background:linear-gradient(160deg,#203a46,#172934);transition:transform .18s ease,border-color .18s ease,box-shadow .18s ease}.choice::before{content:"";position:absolute;top:0;left:18%;right:18%;height:2px;background:linear-gradient(90deg,transparent,#8cdec5,transparent)}.choice:nth-child(2){background:linear-gradient(160deg,#24364e,#192836)}.choice:nth-child(2)::before{background:linear-gradient(90deg,transparent,#8fb9f4,transparent)}.choice:hover{transform:translateY(-3px);border-color:#82cdb3;box-shadow:0 12px 28px #0003}.choice:nth-child(2):hover{border-color:#90b7ec}.choice h2{font-size:22px;margin-top:16px}.choice p{min-height:46px;max-width:28ch;line-height:1.7;margin-bottom:24px}.choice a{width:100%;max-width:330px}.choice:nth-child(2) a{background:#b4cff4;color:#152d4b}.mode-icon{width:64px;height:64px;border:1px solid #8de5c133;border-radius:18px;display:grid;place-items:center;background:#83dfbb12;color:#a3efd4}.choice:nth-child(2) .mode-icon{color:#bdd7ff;border-color:#a4caff33;background:#9bc2ff12}.mode-icon svg{width:30px;height:30px;fill:none;stroke:currentColor;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}.mode-label{font-size:11px;font-weight:650;letter-spacing:.12em;color:#8de0c3;margin-top:14px}.choice:nth-child(2) .mode-label{color:#a9c9f5}section>.muted{text-align:center;padding-top:22px;border-top:1px solid #42566566}a{transition:filter .15s ease}a:hover{filter:brightness(1.08)}@media(prefers-reduced-motion:reduce){.choice,a{transition:none}.choice:hover{transform:none}}@media(max-width:640px){.choice{padding:24px 20px}.choice p{min-height:0}.mode-icon{width:54px;height:54px;border-radius:15px}.choice h2{font-size:21px}}
"""
        host = escape(hostname, quote=True)
        body = f"""<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>XLeRobot 제어 모드 선택</title><style>{css}</style>
<h1>XLeRobot 제어 모드 선택</h1><p class="muted">두 화면이 하나의 로보시지 엔진을 공유합니다.</p>
<section><div class="choices"><div class="choice"><div class="mode-icon" aria-hidden="true"><svg viewBox="0 0 32 32"><rect x="8" y="3" width="16" height="26" rx="3"/><path d="M14 7h4M14 25h4"/></svg></div><span class="mode-label">MOBILE CONTROL</span><h2>XLeRobot 제어센터</h2><p>Seung Jin 제작 · 모바일 특화 및 간편제어</p><a href="http://{host}:8080/mobile/">XLeRobot 제어센터 열기 ↗</a></div><div class="choice"><div class="mode-icon" aria-hidden="true"><svg viewBox="0 0 32 32"><rect x="3" y="5" width="26" height="18" rx="3"/><path d="M16 23v5M10 28h12M3 18h26"/></svg></div><span class="mode-label">BROWSER CONTROL</span><h2>로보시지 제어센터</h2><p>로보시지 제작 · 웹 브라우저 특화 및 집중제어</p><a href="http://{host}:8080/">로보시지 제어센터 열기 ↗</a></div></div>
<p class="muted">화면 이동은 엔진을 재시작하지 않습니다. 수동 조작을 종료한 뒤 이동하고, 새 화면에서 제어권을 받으세요.</p></section></html>""".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=18091)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Shared UI selector: http://127.0.0.1:{args.port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
