#!/usr/bin/env python3
"""
A/B Test Bridge Server

Serves audio files from a directory over HTTP with CORS headers,
so the HTML blind test tool can load local files without using
the browser's file input dialog (which may not work on some
Wayland compositors like niri).

Usage:
    python3 abtest-bridge.py [目录路径]

Then open abtest.html in your browser and use "网络加载" section.
"""

import http.server
import json
import os
import sys
import mimetypes
from pathlib import Path

PORT = 8899

AUDIO_EXTS = {'.mp3', '.flac', '.wav', '.ogg', '.m4a', '.aac', '.wma', '.opus'}


class AudioBridgeHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler that adds CORS and a JSON file-listing API."""

    def do_GET(self):
        if self.path == '/api/list':
            self._send_file_list()
        else:
            super().do_GET()

    def do_OPTIONS(self):
        self._send_cors_headers()
        self.send_response(204)
        self.end_headers()

    def _send_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')

    def end_headers(self):
        self._send_cors_headers()
        super().end_headers()

    def _send_file_list(self):
        files = []
        for f in sorted(Path('.').iterdir()):
            if not f.is_file():
                continue
            ext = f.suffix.lower()
            if ext not in AUDIO_EXTS:
                continue
            size = f.stat().st_size
            files.append({
                'name': f.name,
                'size': size,
                'sizeStr': self._fmt_size(size),
            })
        body = json.dumps(files, ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    @staticmethod
    def _fmt_size(n: int) -> str:
        for unit in ('B', 'KB', 'MB', 'GB'):
            if n < 1024:
                return f"{n:.1f} {unit}"
            n /= 1024
        return f"{n:.1f} TB"

    def log_message(self, fmt, *args):
        sys.stderr.write(f"[bridge] {args[0]} {args[1]} {args[2]}\n")


if __name__ == '__main__':
    target_dir = sys.argv[1] if len(sys.argv) > 1 else '.'
    os.chdir(target_dir)
    server = http.server.HTTPServer(('127.0.0.1', PORT), AudioBridgeHandler)

    print(f"\n  {'='*50}")
    print(f"  Audio AB Test Bridge Server")
    print(f"  {'='*50}")
    print(f"  提供目录: {os.path.abspath('.')}")
    print(f"  监听地址: http://127.0.0.1:{PORT}")
    print(f"  文件列表: http://127.0.0.1:{PORT}/api/list")
    print(f"  {'='*50}")
    print(f"\n  按 Ctrl+C 停止服务器\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  服务器已停止")
        server.server_close()
