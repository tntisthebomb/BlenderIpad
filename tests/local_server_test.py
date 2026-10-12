#!/usr/bin/env python3
"""Exercise HTTP .local hosting, older MIME mappings and actionable startup failures."""
import os
from pathlib import Path
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]

class Handler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map,
                      ".mjs": "application/octet-stream", ".js": "text/javascript",
                      ".wasm": "application/octet-stream"}

    def log_message(self, *args):
        pass

server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, directory=str(ROOT / "web")))
Thread(target=server.serve_forever, daemon=True).start()
try:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=os.environ.get("CHROMIUM_PATH", "/usr/lib/chromium/chromium"),
            args=["--no-sandbox", "--no-proxy-server",
                  "--host-resolver-rules=MAP users-ipad.local 127.0.0.1"])
        page = browser.new_page()
        page.goto(f"http://users-ipad.local:{server.server_port}/")
        page.get_by_text("5 source checks passed · Blender 5.2.2").wait_for()
        page.get_by_text("Local server mode · keep WorldWideWeb running", exact=True).wait_for()
        assert not page.evaluate("isSecureContext")
        page.locator("#viewport").click()
        for key in ["g", "x", "ArrowRight", "Enter"]:
            page.keyboard.press(key)
        assert page.locator('[data-field="location-0"]').inner_text() == "X 0.10"

        page.route("**/math-runtime.js", lambda route: route.fulfill(
            status=200, content_type="application/octet-stream", body="export const rejected = 1;"))
        page.reload()
        page.get_by_text("Math test could not start", exact=True).wait_for()
        assert "JavaScript could not load" in page.locator("#checks").inner_text()

        page.unroute("**/math-runtime.js")
        page.route("**/engine/blender-math.wasm", lambda route: route.fulfill(status=404, body="not found"))
        page.reload()
        page.get_by_text("Blender math failed to load", exact=True).wait_for()
        assert "HTTP 404" in page.locator("#checks").inner_text()
        browser.close()
    print("PASS: HTTP .local startup and keyboard input; module MIME and missing-engine failures are visible.")
finally:
    server.shutdown()
    server.server_close()
