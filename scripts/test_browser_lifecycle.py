#!/usr/bin/env python3
"""Verify native runtime/destructor lifetime across actual scheduler pauses."""
import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from setup_browser import CACHE, ROOT, toolchain, run

if __name__ == '__main__':
    build = CACHE / 'lifecycle-probe'
    build.mkdir(exist_ok=True)
    run('em++', ROOT / 'tests/browser_lifecycle_probe.cc', '-O2',
        '-sEXIT_RUNTIME=1', '-sASSERTIONS=2', '-sFORCE_FILESYSTEM=1',
        '-sMODULARIZE=1', '-sEXPORT_NAME=createLifecycle', '-sENVIRONMENT=web',
        "-sDEFAULT_LIBRARY_FUNCS_TO_INCLUDE=['$ENV']",
        "-sEXPORTED_FUNCTIONS=['_main','_lifecycle_ticks']",
        "-sEXPORTED_RUNTIME_METHODS=['callMain','FS','runtimeKeepalivePush','runtimeKeepalivePop']",
        '--pre-js', ROOT / 'native/browser/core_browser_env.js',
        '-o', build / 'lifecycle.js', env=toolchain())
    (build / 'index.html').write_text('''<!doctype html><script src="lifecycle.js"></script>
<script>createLifecycle({noInitialRun:true}).then(module=>window.lifecycle=module)
 .catch(error=>window.lifecycleError=String(error));</script>''')
    class Handler(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=str(build)))
    Thread(target=server.serve_forever, daemon=True).start()
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=os.environ.get(
                'CHROMIUM_PATH', '/usr/lib/chromium/chromium'), args=['--no-sandbox'])
            page = browser.new_page()
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(f'http://127.0.0.1:{server.server_port}/')
            page.wait_for_function('window.lifecycle || window.lifecycleError')
            assert not page.evaluate('window.lifecycleError'), page.evaluate('window.lifecycleError')
            page.evaluate("lifecycle.FS.writeFile('/recovery.blend',new Uint8Array([66,76,69,78,68]));lifecycle.runBlenderMain([])")
            page.wait_for_function('lifecycle._lifecycle_ticks()>1')
            for _ in range(3):
                page.evaluate('lifecycle.pauseBlenderLoop();lifecycle.pauseBlenderLoop()')
                ticks = page.evaluate('lifecycle._lifecycle_ticks()')
                page.wait_for_timeout(150)
                assert page.evaluate('lifecycle._lifecycle_ticks()') == ticks
                assert not page.evaluate('!!lifecycle.destructorRan')
                assert page.evaluate("Array.from(lifecycle.FS.readFile('/recovery.blend'))") == [66,76,69,78,68]
                page.evaluate('lifecycle.resumeBlenderLoop();lifecycle.resumeBlenderLoop()')
                page.wait_for_function('ticks=>lifecycle._lifecycle_ticks()>ticks', arg=ticks)
            page.evaluate('lifecycle.pauseBlenderLoop()')
            page.wait_for_timeout(150)
            assert not page.evaluate('!!lifecycle.destructorRan')
            assert not errors, errors
            browser.close()
        print('PASS: real native scheduler pauses/resumes without static teardown; recovery bytes survive.')
    finally:
        server.shutdown()
        server.server_close()
