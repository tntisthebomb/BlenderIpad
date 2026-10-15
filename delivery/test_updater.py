from pathlib import Path
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from tempfile import TemporaryDirectory
from threading import Thread
from playwright.sync_api import sync_playwright
import os
root=Path(os.environ.get('DELIVERY_SOURCE_ROOT',Path(__file__).resolve().parents[1]))
class Handler(SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
with TemporaryDirectory(prefix='blender-updater-') as folder:
 folder=Path(folder);app=folder/'app';app.mkdir();(folder/'monitor').mkdir()
 (folder/'monitor/index.html').write_text('<title>Outside application scope</title>')
 (app/'ipad-update.html').write_bytes(Path(__file__).with_name('ipad-update.html').read_bytes())
 pagehtml='''<!doctype html><script>(async()=>{await navigator.serviceWorker.register('./service-worker.js');await navigator.serviceWorker.ready;if(!navigator.serviceWorker.controller)location.reload();else document.body.dataset.ready='true'})();</script><body></body>'''
 (app/'index.html').write_text(pagehtml);(app/'editor.html').write_text(pagehtml)
 worker=(root/'native/browser/service-worker.js').read_text()
 def version(name):
  (app/'service-worker.js').write_text(worker.replace('__BUILD_CACHE__',name))
 for name in ['blender-core.js','blender-core.wasm','blender-core.data','manifest.webmanifest','icon.svg','icon-192.png','icon-512.png','editor_files.js','editor_input.js','ipad-startup.html']:(app/name).write_text('Offline fixture '+name)
 version('updater-old')
 server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(folder)));Thread(target=server.serve_forever,daemon=True).start()
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/lib/chromium/chromium'),args=['--no-sandbox']);context=browser.new_context()
   origin=f'http://127.0.0.1:{server.server_port}'
   legacy=context.new_page();legacy.goto(origin+'/app/');legacy.wait_for_function('document.body.dataset.ready')
   observer=context.new_page();observer.goto(origin+'/monitor/')
   helper=context.new_page();errors=[];helper.on('pageerror',lambda e:errors.append(str(e)))
   helper.goto(origin+'/app/ipad-update.html')
   assert helper.locator('body').get_attribute('data-state')=='ready'
   assert not helper.evaluate('window.createBlenderCore || window.blenderEditor')
   # Failed installation must retain the previous cached engine.
   version('updater-failed');(app/'blender-core.wasm').unlink()
   helper.locator('#install').click();helper.wait_for_function('document.body.dataset.state==="failed"',timeout=30000)
   assert 'previous offline build' in helper.locator('#status').inner_text() or 'Failed' in helper.locator('#status').inner_text() or 'failed' in helper.locator('#status').inner_text(),helper.locator('#status').inner_text()
   assert helper.evaluate('async()=>await (await fetch("blender-core.wasm")).text()')=='Offline fixture blender-core.wasm'
   assert not helper.evaluate('async()=> (await caches.keys()).some(k=>k.endsWith("updater-failed"))')
   # Install the complete replacement, but keep the old client coherent.
   (app/'blender-core.wasm').write_text('New engine bytes, not executable fixture')
   version('updater-new')
   helper.locator('#install').click();helper.wait_for_function('document.body.dataset.state==="waiting"',timeout=30000)
   assert helper.evaluate('async()=>await (await fetch("blender-core.wasm")).text()')=='Offline fixture blender-core.wasm'
   assert 'Close this tab' in helper.locator('#status').inner_text()
   assert not errors,errors
   helper.close();legacy.close()
   observer.evaluate('''async()=>{
    const deadline=performance.now()+30000;
    while(true){const r=await navigator.serviceWorker.getRegistration('/app/');
      if(r?.active?.state==='activated' && !r.installing && !r.waiting)return;
      if(performance.now()>deadline)throw Error('Replacement did not activate after client closure');
      await new Promise(resolve=>setTimeout(resolve,25));}
   }''')
   context.set_offline(True);restored=context.new_page();restored.goto(origin+'/app/');restored.wait_for_function('document.body.dataset.ready')
   assert restored.evaluate('async()=>await (await fetch("blender-core.wasm")).text()')=='New engine bytes, not executable fixture'
   context.close();browser.close()
 finally:server.shutdown();server.server_close()
print('PASS engine-free updater: failed download retains old cache; replacement waits for old clients; closing clients activates coherent offline replacement (infrastructure fixtures only).')
