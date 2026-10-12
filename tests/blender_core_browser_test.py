#!/usr/bin/env python3
"""Run bpy modeling and native .blend I/O in the browser's actual Blender WASM."""
import json
import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]

class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *args): pass
    def end_headers(self):
        self.send_header('Cross-Origin-Opener-Policy', 'same-origin')
        self.send_header('Cross-Origin-Embedder-Policy', 'require-corp')
        super().end_headers()

server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler,
    directory=str(ROOT / '.cache/blender-core-browser')))
Thread(target=server.serve_forever, daemon=True).start()
try:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=os.environ.get(
            'CHROMIUM_PATH', '/usr/lib/chromium/chromium'), args=['--no-sandbox'])
        context = browser.new_context()
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(f'http://127.0.0.1:{server.server_port}/core.html')
        page.wait_for_function("document.body.dataset.ready || document.body.dataset.error", timeout=180000)
        assert page.locator('body').get_attribute('data-ready') == 'true', page.locator('body').get_attribute('data-error')
        assert page.evaluate('crossOriginIsolated')
        # All computation and resources must work after the network disconnects.
        # This does not test an offline app reload or persistent browser storage.
        context.set_offline(True)
        page.evaluate('runCoreScene()')
        page.wait_for_function("coreExit !== null || document.body.dataset.error", timeout=180000)
        assert page.evaluate('coreExit') == 0, page.evaluate('coreErrors')
        checks = json.loads(page.evaluate("blenderCore.FS.readFile('/scene-output/result.json', {encoding:'utf8'})"))
        assert checks['version'] == [5, 2, 2]
        assert checks['image_io'] is True
        assert all(value is True for key, value in checks.items() if key != 'version'), checks
        assert page.evaluate("new TextDecoder().decode(blenderCore.FS.readFile('/scene-output/offline-scene.blend').slice(0,7))") == 'BLENDER'
        assert not errors, errors
        browser.close()
    print('PASS: real browser Blender bpy, modeling, modifier, animation, PNG image I/O, original startup load and native .blend roundtrip after network disconnect.')
finally:
    server.shutdown()
    server.server_close()
