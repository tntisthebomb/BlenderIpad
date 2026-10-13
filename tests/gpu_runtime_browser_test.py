#!/usr/bin/env python3
"""Validate real Blender GPU startup separately from editor drawing."""
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

server = ThreadingHTTPServer(('127.0.0.1', 0), partial(
    Handler, directory=str(ROOT / '.cache/gpu-runtime-tests')))
Thread(target=server.serve_forever, daemon=True).start()
try:
    with (ROOT / '.cache/gpu-runtime-browser.log').open('w') as diagnostics:
        def record(kind, message):
            diagnostics.write(kind + ': ' + str(message) + '\n')
            diagnostics.flush()
        with sync_playwright() as playwright:
            executable = os.environ.get('CHROMIUM_PATH', '/usr/lib/chromium/chromium')
            environment = dict(os.environ)
            driver = Path(executable).resolve().parent / 'vk_swiftshader_icd.json'
            if driver.exists(): environment['VK_ICD_FILENAMES'] = str(driver)
            browser = playwright.chromium.launch(executable_path=executable, env=environment,
                args=['--no-sandbox', '--enable-unsafe-webgpu', '--enable-features=Vulkan',
                      '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
            try:
                page = browser.new_page()
                errors = []
                output = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.on('console', lambda message: (
                    output.append(message.text), record(message.type, message.text)))
                page.on('crash', lambda: record('crash', 'Browser renderer crashed'))
                page.goto(f'http://127.0.0.1:{server.server_port}/index.html')
                page.wait_for_function('document.body.dataset.done || document.body.dataset.error',
                                       timeout=120000)
                assert page.locator('body').get_attribute('data-done') == 'true', output
                assert 'Actual Blender GPU registration and builtin warm-up completed.' in output, output
                assert 'Shader binding mapping preserves native slots, array names and resource types.' in output, output
                assert not errors, errors
            finally:
                browser.close()
    print('PASS: actual Blender WebGPU context, shader registration, builtin warm-up and GPU shutdown. Drawing remains a separate acceptance test.')
finally:
    server.shutdown()
    server.server_close()
