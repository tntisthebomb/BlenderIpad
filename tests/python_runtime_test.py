#!/usr/bin/env python3
"""Exercise a compiled interpreter in the browser, including files and errors."""
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
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        super().end_headers()

server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, directory=str(ROOT / ".cache/python-browser")))
Thread(target=server.serve_forever, daemon=True).start()
try:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH", "/usr/lib/chromium/chromium"), args=["--no-sandbox"])
        context = browser.new_context()
        page = context.new_page()
        page_errors = []
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.goto(f"http://127.0.0.1:{server.server_port}/runtime.html")
        page.wait_for_function("document.body.dataset.ready === 'true' || document.body.dataset.error", timeout=90000)
        assert page.locator("body").get_attribute("data-ready") == "true", page.locator("body").get_attribute("data-error")
        assert page.evaluate("crossOriginIsolated")
        script = """
import sys, json, math, decimal, _decimal, zlib, bz2, hashlib, pathlib
import xml.etree.ElementTree as E
assert sys.version_info[:3] == (3, 13, 13)
assert sys.platform == 'emscripten'
assert json.loads(json.dumps({'name':'iPad é'}))['name'] == 'iPad é'
assert math.isclose(math.sin(math.pi/2), 1)
assert decimal.Decimal('0.1') + decimal.Decimal('0.2') == decimal.Decimal('0.3')
data = bytes(range(256))*512
assert zlib.decompress(zlib.compress(data)) == data
assert bz2.decompress(bz2.compress(data)) == data
assert hashlib.sha256(b'abc').hexdigest() == 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'
assert E.fromstring('<scene><mesh/></scene>')[0].tag == 'mesh'
import threading
thread_result = []
worker = threading.Thread(target=lambda: thread_result.extend(range(512)))
worker.start()
worker.join(5)
assert not worker.is_alive() and thread_result == list(range(512))
pathlib.Path('/scene.json').write_text(json.dumps({'vertices':[[0,0,0],[1,0,0],[0,1,0]]}))
assert len(json.loads(pathlib.Path('/scene.json').read_text())['vertices']) == 3
print('NATIVE_PYTHON_OK')
"""
        assert page.evaluate("script => runNativePython(script)", script) == 0
        assert "NATIVE_PYTHON_OK" in page.evaluate("runtimeOutput")
        # Python errors must remain failures rather than being swallowed by JS.
        assert page.evaluate("runNativePython('raise ValueError(\"expected error\")')") == -1
        assert any("expected error" in line for line in page.evaluate("runtimeErrors"))
        context.set_offline(True)
        assert page.evaluate("runNativePython(\"import json,pathlib; assert len(json.loads(pathlib.Path('/scene.json').read_text())['vertices']) == 3; print('OFFLINE_PYTHON_OK')\")") == 0
        assert "OFFLINE_PYTHON_OK" in page.evaluate("runtimeOutput")
        assert page.evaluate("nativePython._python_runtime_finalize()") == 0
        assert not page_errors, page_errors
        browser.close()
    print("PASS: real CPython browser C API, zipped stdlib, UTF-8, arithmetic, decimal, compression, hashing, XML, native thread execution, memory-filesystem I/O, error propagation and execution after network disconnect.")
finally:
    server.shutdown()
    server.server_close()
