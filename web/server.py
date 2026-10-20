#!/usr/bin/env python3
"""Servidor HTTP local do catálogo Overdrive para Windows (somente biblioteca padrão)."""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit
import argparse
import json
import os
import re

ROOT = Path(__file__).resolve().parent.parent
ID = re.compile(r"^[A-Za-z0-9_-]{1,100}$")

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        route = urlsplit(self.path).path
        if route == "/":
            self.send_response(302)
            self.send_header("Location", "/web/")
            self.end_headers()
            return
        if route.startswith("/api/releases/"):
            game_id = unquote(route.removeprefix("/api/releases/"))
            if not ID.fullmatch(game_id):
                self.send_error(400, "ID invalido")
                return
            target = ROOT / "app" / "data" / "releases" / (game_id + ".json")
            if not target.is_file():
                self.send_error(404, "Sem releases locais")
                return
            try:
                data = target.read_bytes()
            except OSError:
                self.send_error(500)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
            return
        super().do_GET()

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    os.chdir(ROOT)
    with ThreadingHTTPServer(("127.0.0.1", args.port), Handler) as httpd:
        print(f"Overdrive PC: http://127.0.0.1:{args.port}/web/", flush=True)
        httpd.serve_forever()

if __name__ == "__main__":
    main()
