from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ("/", "/health"):
            self.send_error(404)
            return
        body = json.dumps(
            {
                "service": "orion-release-metadata",
                "revision": os.getenv("ORION_BUILD_REVISION", "clean-baseline"),
                "status": "ready",
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        return


HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
