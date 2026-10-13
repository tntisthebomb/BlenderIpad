#!/usr/bin/env python3
"""Validate shader execution and readback through actual WASM WebGPU bindings."""
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
        self.send_header('Cross-Origin-Opener-Policy','same-origin')
        self.send_header('Cross-Origin-Embedder-Policy','require-corp')
        super().end_headers()

server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler,
    directory=os.environ.get('WEBGPU_PROBE_DIR', str(ROOT / '.cache/webgpu-native-probe'))))
Thread(target=server.serve_forever, daemon=True).start()
try:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=os.environ.get(
            'CHROMIUM_PATH', '/usr/lib/chromium/chromium'), args=[
            '--no-sandbox', '--enable-unsafe-webgpu', '--enable-features=Vulkan',
            '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
        page = browser.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(f'http://127.0.0.1:{server.server_port}/index.html')
        page.wait_for_function('document.body.dataset.done || document.body.dataset.error', timeout=60000)
        assert page.locator('body').get_attribute('data-done') == 'true', page.locator('body').get_attribute('data-error')
        if os.environ.get('WEBGPU_EXPECT_PYTHON') == '1':
            assert page.locator('body').get_attribute('data-python') == 'true'
        assert not errors, errors
        browser.close()
    print('PASS: native WASM WebGPU adapter/device, pipeline, buffers, dispatch and asynchronous numerical readback.')
finally:
    server.shutdown()
    server.server_close()
