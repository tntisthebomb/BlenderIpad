"""A partial initial download must expose recovery, not wait forever."""
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import os
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
class Handler(SimpleHTTPRequestHandler):
    def log_message(self,*args): pass
with TemporaryDirectory(dir=ROOT/'.cache') as directory:
    base=Path(directory)
    (base/'index.html').write_bytes((ROOT/'native/browser/blender_editor.html').read_bytes())
    (base/'editor.html').write_bytes((base/'index.html').read_bytes())
    (base/'editor_files.js').write_bytes((ROOT/'native/browser/editor_files.js').read_bytes())
    (base/'editor_input.js').write_bytes((ROOT/'native/browser/editor_input.js').read_bytes())
    (base/'service-worker.js').write_text((ROOT/'native/browser/service-worker.js').read_text().replace('__BUILD_CACHE__','failed-first-install'))
    (base/'blender-core.js').write_text('window.createBlenderCore=()=>{throw new Error("This fixture has no engine")};')
    for name in ('blender-core.data','manifest.webmanifest','icon.svg','icon-192.png','icon-512.png'):
        (base/name).write_text('Installation infrastructure fixture')
    # Deliberately omit the WASM file. No fixture claims to run Blender.
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=directory))
    Thread(target=server.serve_forever,daemon=True).start()
    try:
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/lib/chromium/chromium'),args=['--no-sandbox'])
            try:
                page=browser.new_page()
                page.goto(f'http://127.0.0.1:{server.server_port}/')
                page.wait_for_function('document.body.dataset.error',timeout=30000)
                assert 'could not finish downloading' in page.locator('body').get_attribute('data-error')
                assert page.locator('#retry-startup').is_visible()
                assert page.locator('#error-device-report').is_visible()
                assert not page.evaluate('!!window.blenderEditor')
                assert not page.evaluate('async()=> (await caches.keys()).some(key=>key.endsWith("failed-first-install"))')
            finally: browser.close()
    finally: server.shutdown();server.server_close()
print('PASS: failed first installation reports the missing build and offers retry/report; incomplete cache discarded.')
