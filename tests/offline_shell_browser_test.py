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

def wait_async(page, expression, arg=None):
    # Playwright's truthiness polling treats an async predicate's Promise as
    # truthy before its boolean result resolves. Await it inside the page.
    page.evaluate('''async ({expression,arg})=>{
      const predicate=eval(expression),deadline=performance.now()+30000;
      while(!(await predicate(arg))){
        if(performance.now()>deadline) throw new Error('Asynchronous acceptance condition timed out');
        await new Promise(resolve=>setTimeout(resolve,25));
      }
    }''',{'expression':expression,'arg':arg})

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
                      'manifest.webmanifest', 'icon.svg', 'icon-192.png','icon-512.png','editor_files.js'):
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
                    page.goto(f'http://127.0.0.1:{server.server_port}/{name}/index.html')
                    page.reload()
                    page.wait_for_function('document.body.dataset.ready || document.body.dataset.error')
                    assert page.evaluate('crossOriginIsolated && !!navigator.serviceWorker.controller')
                    for asset, expected in fixtures[name].items():
                        actual = page.evaluate('async asset=>{const response=await fetch(asset);'
                            'return {body:await response.text(),policy:response.headers.get("Cross-Origin-Embedder-Policy")}}', asset)
                        assert actual == {'body':expected, 'policy':'require-corp'}, (name, asset, actual)
                context.set_offline(False)
                page = pages['one']
                folder = base / 'one'
                old_asset = fixtures['one']['blender-core.wasm']
                worker = (ROOT/'native/browser/service-worker.js').read_text()
                # A failed update must discard its incomplete cache and leave
                # the running installation usable, including after going offline.
                (folder/'service-worker.js').write_text(worker.replace('__BUILD_CACHE__', 'failed-update'))
                (folder/'blender-core.wasm').unlink()
                page.evaluate('async()=>{const registration=await navigator.serviceWorker.getRegistration();'
                    'await registration.update();'
                    'const candidate=registration.installing;'
                    'if(candidate && candidate.state!=="redundant") await new Promise(resolve=>'
                    'candidate.addEventListener("statechange",()=>{if(candidate.state==="redundant") resolve()}));}')
                assert not page.evaluate('async()=> (await caches.keys()).some(key=>key.endsWith("failed-update"))')
                context.set_offline(True)
                assert page.evaluate('async()=>await (await fetch("blender-core.wasm")).text()') == old_asset
                context.set_offline(False)
                # A complete update waits while any old runtime remains open.
                # Its later asset fetches must keep returning that same build.
                new_asset = 'Updated infrastructure fixture one blender-core.wasm'
                (folder/'blender-core.wasm').write_text(new_asset)
                (folder/'service-worker.js').write_text(worker.replace('__BUILD_CACHE__', 'complete-update'))
                page.evaluate('async()=>{const registration=await navigator.serviceWorker.getRegistration();'
                    'await registration.update();}')
                wait_async(page,'async()=>!!(await navigator.serviceWorker.getRegistration()).waiting')
                assert page.evaluate('async()=>await (await fetch("blender-core.wasm")).text()') == old_asset
                page.close()
                # Observe activation from the other scope before opening a new
                # client, which could otherwise keep the previous worker alive.
                wait_async(pages['two'],'async()=>{const registration=await navigator.serviceWorker.getRegistration("../one/");'
                    'if(registration?.active?.state!=="activated" || registration.waiting || registration.installing) return false;'
                    'return await new Promise(resolve=>{const channel=new MessageChannel();'
                    'const timer=setTimeout(()=>{channel.port1.close();resolve(false)},1000);'
                    'channel.port1.onmessage=event=>{clearTimeout(timer);channel.port1.close();resolve(event.data.cache.endsWith("complete-update"))};'
                    'registration.active.postMessage({type:"BUILD_INFO"},[channel.port2]);});}')
                page = context.new_page()
                page.goto(f'http://127.0.0.1:{server.server_port}/one/')
                page.wait_for_function('document.body.dataset.ready || document.body.dataset.error')
                wait_async(page,'async expected=>await (await fetch("blender-core.wasm")).text()===expected', arg=new_asset)
                context.set_offline(True)
                page.reload()
                page.wait_for_function('document.body.dataset.ready || document.body.dataset.error')
                actual=page.evaluate('async()=>await (await fetch("blender-core.wasm")).text()')
                assert actual == new_asset, (actual,page.evaluate('async()=>await caches.keys()'),
                    page.evaluate('()=>new Promise(resolve=>{const channel=new MessageChannel();'
                    'channel.port1.onmessage=event=>resolve(event.data);'
                    'navigator.serviceWorker.controller.postMessage({type:"BUILD_INFO"},[channel.port2]);})'))
                assert page.evaluate('async()=>!(await caches.keys()).some(key=>key.endsWith("fixture-one"))')
                assert pages['two'].evaluate('async()=>await (await fetch("blender-core.wasm")).text()') == fixtures['two']['blender-core.wasm']
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
print('PASS: offline navigation, isolation, independent caches, failed-update rollback and coherent updates after old runtime closure. Blender editor/storage acceptance remains separate.')
