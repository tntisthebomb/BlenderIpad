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
    (base/'startup_stats.js').write_bytes((ROOT/'native/browser/startup_stats.js').read_bytes())
    (base/'startup_shaders.js').write_bytes((ROOT/'native/browser/startup_shaders.js').read_bytes())
    (base/'tablet_touch.js').write_bytes((ROOT/'native/browser/tablet_touch.js').read_bytes())
    (base/'service-worker.js').write_text((ROOT/'native/browser/service-worker.js').read_text().replace('__BUILD_CACHE__','failed-first-install'))
    (base/'blender-core.js').write_text('window.createBlenderCore=()=>{throw new Error("This fixture has no engine")};')
    for name in ('startup_watchdog.js','startup_shader_seed.json','engine_identity.json','ipad-startup.html','blender-core.data','manifest.webmanifest','icon.svg','icon-192.png','icon-512.png'):
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
                # The iPad local-server address must offer usable loopback
                # links with the same port and nested extraction path.
                insecure=browser.new_page()
                def route_local(route):
                    path=route.request.url.split('?',1)[0]
                    if path.endswith('.js'):
                        route.fulfill(status=200,content_type='application/javascript',body='')
                    else:
                        route.fulfill(status=200,content_type='text/html',body=(base/'index.html').read_text())
                insecure.route('http://tablet.local:8765/**',route_local)
                insecure.goto('http://tablet.local:8765/editor/index.html?preview=1#start')
                insecure.wait_for_function('document.body.dataset.error')
                assert not insecure.evaluate('isSecureContext')
                assert insecure.locator('#local-addresses').is_visible()
                assert insecure.locator('#try-localhost').get_attribute('href')=='http://localhost:8765/editor/index.html?preview=1#start'
                assert insecure.locator('#try-loopback').get_attribute('href')=='http://127.0.0.1:8765/editor/index.html?preview=1#start'
                assert insecure.url.startswith('http://tablet.local:8765/'),insecure.url
            finally: browser.close()
    finally: server.shutdown();server.server_close()
print('PASS: failed first installation reports the missing build and offers retry/report; incomplete cache discarded.')
