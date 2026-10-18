#!/usr/bin/env python3
"""Local preview server for the article, with the one thing `python3 -m http.server` lacks: HTTP Range requests.

  python3 docs/qoralo-blog/tools/serve.py [PORT]        then open  http://127.0.0.1:PORT/docs/qoralo-blog/

Without Range support a browser cannot seek in the video or the audio (it gets the whole file with a plain 200).
Any real static host (Caddy, nginx, GitHub Pages) supports ranges already; this is only for previewing locally.
Also sends no-store so edits show up on reload. Listens on 127.0.0.1 only and serves the repository root.
"""
import http.server, os, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(ROOT), **k)

    def end_headers(self):
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_head(self):
        rng = self.headers.get("Range")
        path = self.translate_path(self.path)
        m = re.fullmatch(r"bytes=(\d*)-(\d*)", rng.strip()) if rng else None
        if not m or not os.path.isfile(path) or not (m.group(1) or m.group(2)):
            return super().send_head()
        size = os.path.getsize(path)
        a, b = m.groups()
        if a == "":                       # suffix range: the last N bytes
            start, end = max(size - int(b), 0), size - 1
        else:
            start, end = int(a), min(int(b) if b else size - 1, size - 1)
        if start >= size or start > end:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{size}")
            self.end_headers()
            return None
        f = open(path, "rb")
        f.seek(start)
        self._left = end - start + 1
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(self._left))
        self.end_headers()
        return f

    def copyfile(self, source, outputfile):
        left = getattr(self, "_left", None)
        try:
            if left is None:
                return super().copyfile(source, outputfile)
            while left > 0:
                chunk = source.read(min(65536, left))
                if not chunk:
                    break
                outputfile.write(chunk)
                left -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):   # the browser stopped reading (it does that while seeking)
            pass
        finally:
            self._left = None

    def log_message(self, *a):
        pass

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8766
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler) as s:
        print(f"serving {ROOT} at http://127.0.0.1:{port}/docs/qoralo-blog/  (Range requests supported)")
        s.serve_forever()
