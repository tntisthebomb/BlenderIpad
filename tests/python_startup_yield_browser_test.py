#!/usr/bin/env python3
"""Verify real CPython/native suspension, stack preservation and four workers."""
import argparse
import json
import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--browser', default='chromium', choices=('chromium', 'webkit'))
options = parser.parse_args()

class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *args): pass
    def end_headers(self):
        self.send_header('Cross-Origin-Opener-Policy', 'same-origin')
        self.send_header('Cross-Origin-Embedder-Policy', 'require-corp')
        super().end_headers()

server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=str(ROOT / '.cache/python-startup-yield-probe')))
Thread(target=server.serve_forever, daemon=True).start()
try:
    with sync_playwright() as p:
        launch = ({'executable_path': os.environ.get('CHROMIUM_PATH', '/usr/lib/chromium/chromium'),
                   'args': ['--no-sandbox']} if options.browser == 'chromium' else {})
        browser = getattr(p, options.browser).launch(**launch)
        page = browser.new_page()
        errors, workers = [], []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('worker', lambda worker: workers.append(worker.url))
        page.goto(f'http://127.0.0.1:{server.server_port}/')
        page.wait_for_function('document.body.dataset.done || document.body.dataset.error', timeout=180000)
        assert not page.evaluate('document.body.dataset.error'), page.evaluate('document.body.dataset.error')
        assert not errors, errors
        assert len(workers) == 4, workers
        result = page.evaluate('result')
        result['observedWorkers'] = len(workers)
        print('PASS: ' + options.browser + ' embedded CPython with nested native callbacks, intact stacks, browser painting and synchronous disabled/completed paths ' + json.dumps(result), flush=True)
        browser.close()
finally:
    server.shutdown()
    server.server_close()
