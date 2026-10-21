#!/usr/bin/env python3
"""Check the production native pool against real WebGPU queue ordering."""
import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parents[1]
class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *args): pass
server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=str(ROOT / '.cache/frame-buffer-pool-probe')))
Thread(target=server.serve_forever, daemon=True).start()
try:
    with sync_playwright() as p:
        executable = os.environ.get('CHROMIUM_PATH', '/usr/lib/chromium/chromium')
        environment = dict(os.environ)
        driver = Path(executable).resolve().parent / 'vk_swiftshader_icd.json'
        if driver.exists(): environment['VK_ICD_FILENAMES'] = str(driver)
        browser = p.chromium.launch(executable_path=executable, env=environment, args=[
            '--no-sandbox', '--enable-unsafe-webgpu', '--enable-features=Vulkan',
            '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
        page = browser.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(f'http://127.0.0.1:{server.server_port}/')
        page.wait_for_function('document.body.dataset.passed || document.body.dataset.error', timeout=60000)
        assert not page.evaluate('document.body.dataset.error'), page.evaluate('document.body.dataset.error')
        assert page.evaluate('labeledPoolFrames')==60,'Native command-buffer labels were dropped by the bridge'
        assert not errors, errors
        browser.close()
finally:
    server.shutdown(); server.server_close()
print('PASS: production native buffer pool, 60 in-flight frame values, no unsubmitted reuse, bounded bytes/handles, large-buffer bypass release before GPU completion, ordered small texture updates, row padding, mip/layer offsets and 3D uploads.')
