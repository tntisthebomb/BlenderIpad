"""Exercise the actual oneTBB scheduler and pthread workers offline."""
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from threading import Thread
import os
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
class Handler(SimpleHTTPRequestHandler):
    def log_message(self,*args): pass
    def end_headers(self):
        self.send_header('Cross-Origin-Opener-Policy','same-origin')
        self.send_header('Cross-Origin-Embedder-Policy','require-corp')
        super().end_headers()
server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(ROOT/'.cache/tbb-probe')))
Thread(target=server.serve_forever,daemon=True).start()
try:
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/lib/chromium/chromium'),args=['--no-sandbox'])
        try:
            context=browser.new_context();page=context.new_page();errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(f'http://127.0.0.1:{server.server_port}/')
            page.wait_for_function('document.body.dataset.ready || document.body.dataset.error')
            assert not page.locator('body').get_attribute('data-error')
            assert page.evaluate('crossOriginIsolated')
            context.set_offline(True)
            page.evaluate('tbb.callMain([])')
            page.wait_for_function('document.body.dataset.exit || document.body.dataset.error',timeout=60000)
            assert page.locator('body').get_attribute('data-exit')=='0'
            assert any('PASS: real oneTBB' in text for text in page.evaluate('output'))
            assert not errors,errors
        finally: browser.close()
finally: server.shutdown();server.server_close()
print('PASS: actual oneTBB two-thread tasks and repeatable numeric results after network disconnect.')
