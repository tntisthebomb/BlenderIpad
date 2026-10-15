#!/usr/bin/env python3
"""An incorrect local-server MIME type must not disable real WASM streaming."""
from pathlib import Path
from tempfile import TemporaryDirectory
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from threading import Thread
import os
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
class Handler(SimpleHTTPRequestHandler):
 extensions_map={**SimpleHTTPRequestHandler.extensions_map,'.wasm':'application/octet-stream'}
 def log_message(self,*args):pass
PAGE='''<!doctype html><meta charset="utf-8"><body><script>
(async()=>{await navigator.serviceWorker.register('./service-worker.js');await navigator.serviceWorker.ready;
 if(!navigator.serviceWorker.controller)location.reload();else document.body.dataset.ready='true';})();
</script></body>'''
with TemporaryDirectory(dir=ROOT/'.cache',prefix='wasm-mime-') as folder:
 base=Path(folder)
 for name in ['index.html','editor.html']:(base/name).write_text(PAGE)
 (base/'service-worker.js').write_text((ROOT/'native/browser/service-worker.js').read_text().replace('__BUILD_CACHE__','mime-regression'))
 for name in ['blender-core.js','blender-core.data','manifest.webmanifest','icon.svg','icon-192.png','icon-512.png','editor_files.js','editor_input.js','startup_stats.js','ipad-startup.html']:
  (base/name).write_text('Explicitly small infrastructure fixture')
 wasm=bytes([0,97,115,109,1,0,0,0])
 for name in ['blender-core.wasm','uncached.wasm']:(base/name).write_bytes(wasm)
 server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=folder))
 Thread(target=server.serve_forever,daemon=True).start()
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/lib/chromium/chromium'),args=['--no-sandbox'])
   context=browser.new_context();page=context.new_page();url=f'http://127.0.0.1:{server.server_port}'
   raw=context.request.get(url+'/blender-core.wasm')
   assert raw.headers['content-type']=='application/octet-stream' and raw.body()==wasm
   page.goto(url+'/');page.wait_for_function('document.body.dataset.ready')
   # Stored headers remain wrong, modeling the already installed iPad cache.
   stored=page.evaluate('''async()=>{
    const cache=await caches.open((await caches.keys())[0]);
    return (await cache.match(new URL('blender-core.wasm',location.href))).headers.get('Content-Type');
   }''')
   assert stored=='application/octet-stream',stored
   def streamed(path):
    return page.evaluate('''async path=>{
     const response=await fetch(path);const type=response.headers.get('Content-Type');
     const policy=response.headers.get('Cross-Origin-Embedder-Policy');
     const result=await WebAssembly.instantiateStreaming(Promise.resolve(response),{});
     return {type,policy,compiled:result.instance instanceof WebAssembly.Instance};
    }''',path)
   assert streamed('blender-core.wasm?fresh=1')=={'type':'application/wasm','policy':'require-corp','compiled':True}
   assert streamed('uncached.wasm')['compiled'] is True
   missing=page.evaluate('async()=>{const r=await fetch("missing.wasm");return {status:r.status,type:r.headers.get("Content-Type")};}')
   assert missing['status']==404 and 'application/wasm' not in missing['type'],missing
   context.set_offline(True)
   assert streamed('blender-core.wasm?offline=1')['compiled'] is True
   # Successful streaming is the regression; no JS runtime/engine is mocked.
   assert page.evaluate('crossOriginIsolated')
   browser.close()
 finally:server.shutdown();server.server_close()
print('PASS: real WASM streaming with incorrect cached/network MIME headers, query URLs, offline use, preserved isolation and unmasked 404 responses.')
