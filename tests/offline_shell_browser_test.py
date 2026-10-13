#!/usr/bin/env python3
"""Check the real service worker with small, explicitly non-Blender fixtures."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import os
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PAGE = '''<!doctype html><title>Offline infrastructure fixture</title>
<script>(async()=>{
  await navigator.serviceWorker.register('./service-worker.js');
  await navigator.serviceWorker.ready;
  if (!navigator.serviceWorker.controller) location.reload();
  else document.body.dataset.ready='true';
})().catch(error=>document.body.dataset.error=String(error));</script><body></body>'''

class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *args): pass

with TemporaryDirectory(prefix='offline-shell-', dir=ROOT/'.cache') as directory:
    base = Path(directory)
    fixtures = {}
    for name in ('one', 'two'):
        folder = base / name
        folder.mkdir()
        (folder/'index.html').write_text(PAGE)
        (folder/'editor.html').write_text(PAGE)
        worker = (ROOT/'native/browser/service-worker.js').read_text()
        (folder/'service-worker.js').write_text(worker.replace('__BUILD_CACHE__', 'fixture-'+name))
        fixtures[name] = {}
        for asset in ('blender-core.js', 'blender-core.wasm', 'blender-core.data',
                      'manifest.webmanifest', 'icon.svg', 'editor_files.js'):
            content = ('Infrastructure fixture '+name+' '+asset).encode()
            (folder/asset).write_bytes(content)
            fixtures[name][asset] = content.decode()
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=directory))
    Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=os.environ.get(
                'CHROMIUM_PATH', '/usr/lib/chromium/chromium'), args=['--no-sandbox'])
            try:
                context = browser.new_context()
                pages = {}
                for name in ('one', 'two'):
                    page = context.new_page()
                    pages[name] = page
                    page.goto(f'http://127.0.0.1:{server.server_port}/{name}/')
                    page.wait_for_function('document.body.dataset.ready || document.body.dataset.error')
                    assert page.evaluate('crossOriginIsolated && !!navigator.serviceWorker.controller')
                context.set_offline(True)
                for name, page in pages.items():
                    page.reload()
                    page.wait_for_function('document.body.dataset.ready || document.body.dataset.error')
                    assert page.evaluate('crossOriginIsolated && !!navigator.serviceWorker.controller')
                    for asset, expected in fixtures[name].items():
                        actual = page.evaluate('async asset=>{const response=await fetch(asset);'
                            'return {body:await response.text(),policy:response.headers.get("Cross-Origin-Embedder-Policy")}}', asset)
                        assert actual == {'body':expected, 'policy':'require-corp'}, (name, asset, actual)
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
print('PASS: real service-worker offline navigation, cached fixture bytes, isolation headers and independent installation caches. Blender editor/storage acceptance remains separate.')
