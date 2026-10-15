#!/usr/bin/env python3
"""Prove recovery records survive a blocked page and a manual tab closure."""
import argparse,json,os,time
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--browser',choices=('chromium','webkit'),default='chromium')
options=parser.parse_args()
class Handler(SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
 def end_headers(self):
  self.send_header('Cross-Origin-Opener-Policy','same-origin')
  self.send_header('Cross-Origin-Embedder-Policy','require-corp')
  super().end_headers()
with TemporaryDirectory(dir=ROOT/'.cache',prefix='watchdog-') as directory:
 base=Path(directory)
 for name in ('startup_stats.js','startup_watchdog.js'):(base/name).write_bytes((ROOT/'native/browser'/name).read_bytes())
 (base/'index.html').write_text('<!doctype html><meta charset="utf-8"><body><script src="startup_stats.js"></script></body>')
 (base/'reader.html').write_text('''<!doctype html><meta charset="utf-8"><body>Recovery reader<script>
 window.readRecovery=()=>new Promise((resolve,reject)=>{
  const request=indexedDB.open('blender-startup-recovery-v1',1);
  request.onsuccess=()=>{const db=request.result,transaction=db.transaction('attempts','readonly');
   const read=transaction.objectStore('attempts').get('last');read.onsuccess=()=>resolve(read.result);
   transaction.oncomplete=()=>db.close();};request.onerror=()=>reject(request.error);
 });</script>''')
 (base/'watchdog-failing.js').write_text("Object.defineProperty(globalThis,'indexedDB',{value:{open(){throw Error('quota fixture');}}});\n"+(base/'startup_watchdog.js').read_text())
 # Fixture-only probe: mark durable transaction completion in shared memory.
 # The blocked page can see this without running any event-loop callbacks.
 (base/'startup_watchdog.js').write_text((base/'startup_watchdog.js').read_text()+'''
 const productionMessage=onmessage,productionSend=postMessage.bind(self);let testProbe=null;
 onmessage=event=>{if(event.data.kind==='test-probe')testProbe=new Int32Array(event.data.buffer);else productionMessage(event);};
 self.postMessage=message=>{if(message.kind==='sample'&&message.maxHeartbeatGapMs>=2000&&testProbe)Atomics.store(testProbe,0,1);productionSend(message);};
 ''')
 server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=directory));Thread(target=server.serve_forever,daemon=True).start()
 try:
  with sync_playwright() as p:
   launch={'args':['--no-sandbox'],'executable_path':os.environ.get('CHROMIUM_PATH','/usr/lib/chromium/chromium')} if options.browser=='chromium' else {}
   browser=getattr(p,options.browser).launch(**launch);context=browser.new_context();errors=[]
   page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
   origin=f'http://127.0.0.1:{server.server_port}'
   page.goto(origin+'/');assert page.evaluate('crossOriginIsolated')
   page.evaluate('''()=>{window.probeBuffer=new SharedArrayBuffer(4);window.probeView=new Int32Array(probeBuffer);
    const NativeWorker=Worker;globalThis.Worker=class extends NativeWorker{
      constructor(url,options){super(url,options);this.postMessage({kind:'test-probe',buffer:probeBuffer});}
    };
   }''')
   page.evaluate("blenderStartupStats.start();blenderStartupStats.phase('Preparing viewport fixture');blenderStartupStats.line('last useful native breadcrumb')")
   page.wait_for_function("blenderStartupStats.snapshot().watchdogStatus==='recording'")
   attempt=page.evaluate('blenderStartupStats.snapshot().attemptId')
   # This browser page cannot run its timer or save recovery records while
   # this synchronous task blocks. The other worker must save independently.
   page.evaluate("window.probeSawCommit=false;setTimeout(()=>{const end=performance.now()+7000;while(performance.now()<end){if(Atomics.load(probeView,0))probeSawCommit=true;}},250)")
   reader=context.new_page();reader.goto(origin+'/reader.html')
   deadline=time.monotonic()+15;saved=None
   while time.monotonic()<deadline:
    saved=reader.evaluate('readRecovery()')
    if saved and saved['maxHeartbeatGapMs']>=2000:break
    reader.wait_for_timeout(250)
   assert saved['attemptId']==attempt and saved['maxHeartbeatGapMs']>=2000,saved
   assert saved['checkpoint']['phase']=='Preparing viewport fixture',saved
   assert 'last useful native breadcrumb' in saved['checkpoint']['lines'],saved
   assert page.evaluate('probeSawCommit'),'Worker did not durably save while the main event loop was blocked'
   page.close()
   # Simulate losing the page's local checkpoint too: the worker's durable
   # record must be sufficient for recovery without starting the engine.
   reader.evaluate('localStorage.removeItem("blender-startup-stats-last")');reader.close()
   restored=context.new_page();restored.goto(origin+'/')
   restored.wait_for_function('blenderStartupStats.previousRecovery()?.maxHeartbeatGapMs>=2000')
   assert restored.locator('#startup-stats-title').inner_text()=='Previous startup — Blender is stopped',restored.locator('#startup-stats-title').inner_text()
   assert 'Recovery recorder: saved' in restored.locator('#startup-stats-text').inner_text()
   assert not restored.evaluate('window.blenderEditor || window.createBlenderCore')
   before=restored.evaluate('localStorage.getItem("blender-startup-stats-last")');restored.wait_for_timeout(1200)
   assert restored.evaluate('localStorage.getItem("blender-startup-stats-last")')==before
   # A successful viewport shuts down the recorder rather than retaining a
   # diagnostic worker / continuing database writes during normal editing.
   restored.evaluate("blenderStartupStats.start();blenderStartupStats.phase('Viewport presented')")
   restored.wait_for_function("blenderStartupStats.snapshot().watchdogStatus==='finished'")
   restored.evaluate("blenderStartupStats.start()")
   restored.wait_for_function("blenderStartupStats.snapshot().watchdogStatus==='recording'")
   restored.evaluate("blenderStartupStats.phase('Viewport presented')")
   restored.wait_for_function("blenderStartupStats.snapshot().watchdogStatus==='finished'")
   restored.close()
   context.add_init_script('''const OriginalWorker=Worker;globalThis.Worker=class extends OriginalWorker{
    constructor(url,options){super(String(url).endsWith('startup_watchdog.js')?new URL('watchdog-failing.js',location.href):url,options);}
   };''')
   failed=context.new_page();failed.on('pageerror',lambda e:errors.append(str(e)));failed.goto(origin+'/')
   failed.evaluate('blenderStartupStats.start()')
   failed.wait_for_function("blenderStartupStats.snapshot().watchdogStatus.startsWith('storage unavailable:')")
   failed.close()
   context.add_init_script('''const ParentWorker=Worker;globalThis.Worker=class extends ParentWorker{
    constructor(url,options){super(new URL('missing-watchdog.js',location.href),options);}
   };''')
   missing=context.new_page();missing.on('pageerror',lambda e:errors.append(str(e)));missing.goto(origin+'/')
   missing.evaluate('blenderStartupStats.start()')
   missing.wait_for_function("blenderStartupStats.snapshot().watchdogStatus==='unavailable'")
   assert not errors,errors
   (ROOT/'work/memory').mkdir(parents=True,exist_ok=True)
   (ROOT/'work/memory'/('watchdog-'+options.browser+'-evidence.json')).write_text(json.dumps(saved,indent=2)+'\n')
   browser.close()
 finally:server.shutdown();server.server_close()
print('PASS: '+options.browser+' independent worker persistence during main-thread block, manual closure recovery, idle preservation, recorder shutdown and visible storage failure. No GPU engine loaded in this fixture.')
