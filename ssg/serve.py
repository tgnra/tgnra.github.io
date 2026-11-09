"""Local preview: serve dist/ and rebuild when content, assets or config change."""

import functools
import http.server
import io
import threading
import time
import traceback
from pathlib import Path

from .build import build

WATCH = ("content", "assets", "site.toml")

# Live reload: the page polls /__livereload for the build counter and reloads
# when it changes. Injected here, at serve time only, so built files stay clean.
RELOAD_PATH = "/__livereload"
RELOAD_JS = b"""<script>
(function () {
  var seen = null;
  function poll() {
    fetch("/__livereload", { cache: "no-store" }).then(function (r) { return r.text(); })
      .then(function (v) { if (seen !== null && v !== seen) location.reload(); seen = v; })
      .catch(function () {}).then(function () { setTimeout(poll, 500); });
  }
  poll();
})();
</script>"""
build_id = 0


def _snapshot(root):
    stamps = {}
    for name in WATCH:
        p = root / name
        for f in [p] if p.is_file() else p.rglob("*") if p.is_dir() else []:
            stamps[f] = f.stat().st_mtime_ns
    return stamps


def _rebuild(root, drafts, base_url):
    global build_id
    try:
        build(root, drafts=drafts, base_url=base_url)
    except Exception:
        traceback.print_exc()
    build_id += 1  # also after a failed build, so the page shows the new state


def _watch(root, drafts, base_url):
    last = _snapshot(root)
    while True:
        time.sleep(0.5)
        now = _snapshot(root)
        if now != last:
            last = now
            _rebuild(root, drafts, base_url)


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?")[0] == RELOAD_PATH:
            body = str(build_id).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def send_head(self):
        # Inject the reload script into HTML pages; everything else is served as-is.
        path = Path(self.translate_path(self.path))
        if path.is_dir():
            path = path / "index.html"
        if path.suffix != ".html" or not path.is_file():
            return super().send_head()
        body = path.read_bytes()
        body = body.replace(b"</body>", RELOAD_JS + b"</body>", 1)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        return io.BytesIO(body)

    def send_error(self, code, message=None, explain=None):
        page = Path(self.directory) / "404.html"
        if code == 404 and page.exists():
            body = page.read_bytes().replace(b"</body>", RELOAD_JS + b"</body>", 1)
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            super().send_error(code, message, explain)

    def log_message(self, fmt, *args):
        pass


def serve(root=".", port=8000, drafts=False, base_url=None):
    root = Path(root).resolve()
    _rebuild(root, drafts, base_url)
    threading.Thread(target=_watch, args=(root, drafts, base_url), daemon=True).start()
    handler = functools.partial(Handler, directory=str(root / "dist"))
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), handler) as httpd:
        print(f"serving http://localhost:{port}/ (ctrl+c to stop)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
