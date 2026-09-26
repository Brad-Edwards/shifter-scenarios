#!/usr/bin/env python3
"""Run the constrained release-preview contribution in an isolated browser."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import threading

from playwright.sync_api import sync_playwright

os.environ.setdefault("HOME", "/tmp")
os.environ.setdefault("XDG_CONFIG_HOME", "/tmp")


class ReviewOrigin(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return

    def do_GET(self) -> None:
        if self.path == "/review/":
            body = b"""<!doctype html><meta charset=utf-8><title>FieldKest release preview</title>
<main id=release>Preparing compatibility review</main><script>
navigator.serviceWorker.register('/review/attachments/controlled-worker.js', {scope:'/review/'}).then(async () => {
  await navigator.serviceWorker.ready;
  if (!navigator.serviceWorker.controller) { location.reload(); return; }
  const result = await fetch('/review/contribution').then(r => r.json());
  document.querySelector('#release').textContent = result.compatibility_summary;
  window.reviewContribution = result;
});
</script>"""
            headers = {"Content-Type": "text/html; charset=utf-8"}
        elif self.path == "/review/attachments/controlled-worker.js":
            body = b"""self.addEventListener('fetch', event => {
  if (new URL(event.request.url).pathname === '/review/contribution') {
    event.respondWith(new Response(JSON.stringify({compatibility_summary:'fieldlink.connector/v3 compatible', renderer_identity:'svc-preview-reviewer'}), {headers:{'Content-Type':'application/json'}}));
  }
});"""
            headers = {"Content-Type": "application/javascript", "Service-Worker-Allowed": "/review/"}
        else:
            self.send_error(404)
            return
        self.send_response(200)
        for name, value in headers.items(): self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


server = ThreadingHTTPServer(("127.0.0.1", 0), ReviewOrigin)
threading.Thread(target=server.serve_forever, daemon=True).start()
try:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=os.environ["FIELDKEST_CHROMIUM"],
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        context = browser.new_context(service_workers="allow")
        page = context.new_page()
        page.goto(f"http://127.0.0.1:{server.server_port}/review/")
        page.wait_for_function("window.reviewContribution !== undefined", timeout=15000)
        contribution = page.evaluate("window.reviewContribution")
        contribution["browser_engine"] = browser.browser_type.name
        contribution["browser_version"] = browser.version
        contribution["worker_scope"] = "/review/"
        print(json.dumps(contribution, sort_keys=True, separators=(",", ":")))
        browser.close()
finally:
    server.shutdown()
