#!/usr/bin/env python3
"""Publish the fixed read-only operating history integration over HTTPS."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import ssl
from urllib.parse import urlsplit

import operating_history


class Handler(BaseHTTPRequestHandler):
    server_version = 'ARWC-Operating-History/1.0'
    sys_version = ''

    def send_json(self, status, value):
        payload = json.dumps(value, separators=(',', ':')).encode() + b'\n'
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if urlsplit(self.path).path == operating_history.PATH:
            operating_history.respond(self)
        else:
            self.send_json(404, {'error': 'resource not found'})

    def unsupported(self):
        if urlsplit(self.path).path == operating_history.PATH:
            self.send_response(405)
            self.send_header('Allow', 'GET')
            self.send_header('Content-Length', '0')
            self.end_headers()
        else:
            self.send_json(404, {'error': 'resource not found'})

    do_POST = unsupported
    do_PUT = unsupported
    do_PATCH = unsupported
    do_DELETE = unsupported
    do_HEAD = unsupported


def main():
    server = ThreadingHTTPServer(('0.0.0.0', 443), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain('/tmp/server.crt', '/tmp/server.key')
    server.socket = context.wrap_socket(server.socket, server_side=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
