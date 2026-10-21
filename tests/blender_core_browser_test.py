#!/usr/bin/env python3
"""Run bpy modeling and native .blend I/O in the browser's actual Blender WASM."""
import json
import argparse
import hashlib
import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--runtime',type=Path,default=ROOT/'.cache/blender-core-browser')
parser.add_argument('--webgpu',action='store_true')
options=parser.parse_args()


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *args): pass
    def end_headers(self):
        self.send_header('Cross-Origin-Opener-Policy', 'same-origin')
        self.send_header('Cross-Origin-Embedder-Policy', 'require-corp')
        super().end_headers()

server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler,
    directory=str(options.runtime.resolve())))
Thread(target=server.serve_forever, daemon=True).start()
diagnostics = (ROOT / '.cache/blender-core-browser-console.log').open('w')
def record(kind, message):
    diagnostics.write(kind + ': ' + str(message) + '\n')
    diagnostics.flush()
try:
    with sync_playwright() as playwright:
        executable=os.environ.get('CHROMIUM_PATH','/usr/lib/chromium/chromium')
        environment=dict(os.environ)
        driver=Path(executable).resolve().parent/'vk_swiftshader_icd.json'
        if driver.exists():environment['VK_ICD_FILENAMES']=str(driver)
        arguments=['--no-sandbox']
        if options.webgpu:arguments+=['--enable-unsafe-webgpu','--enable-features=Vulkan','--use-angle=swiftshader','--enable-unsafe-swiftshader']
        browser = playwright.chromium.launch(executable_path=executable,env=environment,args=arguments)
        context = browser.new_context()
        page = context.new_page()
        errors = []
        page.on('console', lambda message: record(message.type, message.text))
        page.on('requestfailed', lambda request: record('request-failed', request.url + ' ' + str(request.failure)))
        page.on('crash', lambda: record('crash', 'Browser renderer crashed'))
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('pageerror', lambda error: record('page-error', error))
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
        if options.webgpu:
            proof={'checks':checks,'scene_test_sha256':hashlib.sha256((ROOT/'tests/blender_core_scene.py').read_bytes()).hexdigest(),
                   'files':{name:hashlib.sha256((options.runtime/name).read_bytes()).hexdigest() for name in ('blender-core.js','blender-core.wasm','blender-core.data')}}
            (options.runtime/'core-validation-browser.json').write_text(json.dumps(proof,indent=2)+'\n')

        browser.close()
    print('PASS: real browser Blender bpy, modeling, modifier, animation, PNG image I/O, original startup load and native .blend roundtrip after network disconnect.')
finally:
    diagnostics.close()
    server.shutdown()
    server.server_close()
