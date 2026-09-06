"""Tiny HTTP listener for the smoke test's outgoing-webhook check.

Appends one JSON line per POST to the file given as argv[1]. Listens on 0.0.0.0:8099.
"""
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

LOG = sys.argv[1]


class H(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n).decode(errors="replace")
        with open(LOG, "a") as f:
            f.write(json.dumps({"path": self.path, "body": body}) + "\n")
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *a):
        pass


HTTPServer(("0.0.0.0", 8099), H).serve_forever()
