#!/usr/bin/env python3
"""Prove recovery records survive a blocked page and a manual tab closure."""
import argparse,faulthandler,json,os,time
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--browser',choices=('chromium','webkit'),default='chromium')
options=parser.parse_args()
faulthandler.dump_traceback_later(90,exit=True)
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
 function checksum(text){let value=2166136261;for(let i=0;i<text.length;i++)value=Math.imul(value^text.charCodeAt(i),16777619)>>>0;return value.toString(16);}
 window.readRecovery=async()=>{
  const root=await navigator.storage.getDirectory(),records=[];
  for(const name of ['blender-startup-recovery-a.json','blender-startup-recovery-b.json']){
   try{const file=await(await root.getFileHandle(name)).getFile(),data=JSON.parse(await file.text());
    if(data.checksum===checksum(data.payload))records.push(JSON.parse(data.payload));}catch{}
  }
  return records.sort((a,b)=>b.observedAt-a.observedAt)[0];
 };</script>''')
 (base/'watchdog-failing.js').write_text("Object.defineProperty(navigator,'storage',{value:{getDirectory(){return Promise.reject(Error('quota fixture'));}}});\n"+(base/'startup_watchdog.js').read_text())
 # Fixture-only probe: mark a flushed synchronous-file write in shared memory.
 # The blocked page can see this without running any event-loop callbacks.
 worker=(base/'startup_watchdog.js').read_text()
 worker=worker.replace('const written=handle.write(bytes,{at:0});',
   'self.__commitProbe?.(1,record);const written=handle.write(bytes,{at:0});self.__commitProbe?.(2,record);')
 worker=worker.replace('handle.truncate(bytes.byteLength);handle.flush();slot=1-slot;',
   'handle.truncate(bytes.byteLength);handle.flush();self.__commitProbe?.(3,record);slot=1-slot;')
 (base/'startup_watchdog.js').write_text(worker+"""
 const productionMessage=onmessage;let testProbe=null;
 onmessage=event=>{if(event.data.kind==='test-probe')testProbe=new Int32Array(event.data.buffer);else productionMessage(event);};
 self.__commitProbe=(stage,record)=>{if(record.maxHeartbeatGapMs>=2000&&testProbe){Atomics.store(testProbe,stage,1);if(stage===3)Atomics.store(testProbe,0,1);}};
 """)
 server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=directory));Thread(target=server.serve_forever,daemon=True).start()
 try:
  with sync_playwright() as p:
   launch={'args':['--no-sandbox'],'executable_path':os.environ.get('CHROMIUM_PATH','/usr/lib/chromium/chromium')} if options.browser=='chromium' else {}
   print('Launching '+options.browser,flush=True)
   if options.browser=='webkit':
    # WebKit's temporary/private contexts reject OPFS. Match the ordinary
    # persistent Safari profile used on the physical iPad.
    context=p.webkit.launch_persistent_context(str(base/'browser-profile'),**launch)
    browser=context.browser
   else:
    browser=p.chromium.launch(**launch);context=browser.new_context()
   errors=[]
   print('Browser context ready',flush=True)
   page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
   origin=f'http://127.0.0.1:{server.server_port}'
   page.goto(origin+'/');assert page.evaluate('crossOriginIsolated')
   print('Fixture page ready',flush=True)
   page.evaluate('''()=>{window.probeBuffer=new SharedArrayBuffer(16);window.probeView=new Int32Array(probeBuffer);
    const NativeWorker=Worker;globalThis.Worker=class extends NativeWorker{
      constructor(url,options){super(url,options);this.postMessage({kind:'test-probe',buffer:probeBuffer});}
      postMessage(message,...rest){if(message.kind==='start')window.recorderShared=message.shared;return super.postMessage(message,...rest);}
    };
   }''')
   page.evaluate("blenderStartupStats.start();blenderStartupStats.phase('Preparing viewport fixture');blenderStartupStats.line('last useful native breadcrumb')")
   try:page.wait_for_function("blenderStartupStats.snapshot().watchdogStatus==='recording'")
   except Exception:
    print('Recorder initialization failure:',page.evaluate('({state:blenderStartupStats.snapshot(),storage:typeof navigator.storage,directory:typeof navigator.storage?.getDirectory,secure:isSecureContext})'),errors,flush=True);raise
   print('Recorder ready',flush=True)
   attempt=page.evaluate('blenderStartupStats.snapshot().attemptId')
   # A burst must retain the exact pre-call shared breadcrumb without forcing
   # thousands of storage IPC calls, layout reads or text replacements.
   burst=page.evaluate('''()=>{
    const read=()=>{const h=new Int32Array(recorderShared,0,4);
      return JSON.parse(new TextDecoder().decode(new Uint8Array(recorderShared,16,Atomics.load(h,1)).slice())).checkpoint;};
    const marker={},queue={writeBuffer(){const saved=read();
      if(saved.operation!=='GPU queue writeBuffer'||saved.operationStatus!=='in progress')throw Error('Missing pre-call shared checkpoint');return marker;}};
    blenderStartupStats.instrumentQueue(queue);
    const observer=new MutationObserver(()=>{});observer.observe(document.querySelector('#startup-stats'),{childList:true,subtree:true});
    const original=Storage.prototype.setItem;let writes=0;
    Storage.prototype.setItem=function(...args){writes++;return Reflect.apply(original,this,args);};
    const before=performance.now();
    try{for(let i=0;i<1000;i++)if(queue.writeBuffer(marker,0)!==marker)throw Error('Upload return changed');}
    finally{Storage.prototype.setItem=original;}
    const elapsed=performance.now()-before,mutations=observer.takeRecords().length;observer.disconnect();
    const saved=read();
    if(saved.operationStatus!=='call returned')throw Error('Missing returned shared checkpoint');
    if(writes>Math.ceil(elapsed/1000)+1)throw Error('Upload burst forced localStorage writes: '+writes);
    if(mutations>2*(Math.ceil(elapsed/250)+1))throw Error('Upload burst forced DOM mutations: '+mutations);
    return {calls:1000,writes,mutations,elapsedMs:elapsed,preCallAndReturnPreserved:true};
   }''')
   print('Diagnostic burst:',json.dumps(burst),flush=True)

   # This browser page cannot run its timer or save recovery records while
   # this synchronous task blocks. The other worker must save independently.
   page.evaluate("window.probeSawCommit=false;window.probeFinished=false;setTimeout(()=>{const end=performance.now()+7000;while(performance.now()<end){if(Atomics.load(probeView,0))probeSawCommit=true;}window.probeSeenStages=Array.from(probeView);probeFinished=true;},250)")
   page.wait_for_function('probeFinished',timeout=15000)
   probe=page.evaluate('({sawCommit:probeSawCommit,seenDuringBlock:probeSeenStages,stages:Array.from(probeView),snapshot:blenderStartupStats.snapshot()})')
   print('Blocked-page probe:',json.dumps(probe),flush=True)
   assert probe['sawCommit'],'Worker did not durably save while the main event loop was blocked'
   print('PASS: synchronous write flushed while main thread was blocked',flush=True)
   # Apple WebKit can hold an exclusive file lock for the access handle.
   # Close the writer before reading, exactly as manual-tab recovery does.
   page.close()
   print('Writer tab closed',flush=True)
   reader=context.new_page();reader.goto(origin+'/reader.html')
   saved=reader.evaluate('readRecovery()')
   print('Recovery file read',flush=True)
   assert saved and saved['attemptId']==attempt and saved['maxHeartbeatGapMs']>=2000,saved
   assert saved['checkpoint']['phase']=='Preparing viewport fixture',saved
   assert 'last useful native breadcrumb' in saved['checkpoint']['lines'],saved
   assert saved['checkpoint']['lastNativeMarker']['text']=='last useful native breadcrumb',saved
   # Simulate losing the page's local checkpoint too: the worker's durable
   # record must be sufficient for recovery without starting the engine.
   reader.evaluate('localStorage.removeItem("blender-startup-stats-last")');reader.close()
   restored=context.new_page();restored.goto(origin+'/')
   restored.wait_for_function('blenderStartupStats.previousRecovery()?.maxHeartbeatGapMs>=2000')
   assert restored.locator('#startup-stats-title').inner_text()=='Previous startup — Blender is stopped',restored.locator('#startup-stats-title').inner_text()
   assert 'Recovery recorder: saved' in restored.locator('#startup-stats-text').inner_text()
   assert not restored.evaluate('window.blenderEditor || window.createBlenderCore')
   print('Previous startup restored without engine',flush=True)
   before=restored.evaluate('localStorage.getItem("blender-startup-stats-last")');restored.wait_for_timeout(1200)
   assert restored.evaluate('localStorage.getItem("blender-startup-stats-last")')==before
   # A successful viewport shuts down the recorder rather than retaining a
   # diagnostic worker / continuing file writes during normal editing.
   restored.evaluate("blenderStartupStats.start();blenderStartupStats.phase('Viewport presented')")
   restored.wait_for_function("blenderStartupStats.snapshot().watchdogStatus==='finished'")
   restored.evaluate("blenderStartupStats.start()")
   restored.wait_for_function("blenderStartupStats.snapshot().watchdogStatus==='recording'")
   restored.evaluate("blenderStartupStats.phase('Viewport presented')")
   restored.wait_for_function("blenderStartupStats.snapshot().watchdogStatus==='finished'")
   restored.close()
   print('Recorder shutdown and restart verified',flush=True)
   # Opt-in tablet editing retains independent recovery after the first frame.
   # The last input and subsequent native/graphics failure must survive closure.
   editing=context.new_page();editing.goto(origin+'/')
   editing.evaluate("blenderStartupStats.monitorEditing(true);blenderStartupStats.start()")
   editing.wait_for_function("blenderStartupStats.snapshot().watchdogStatus==='recording'")
   editing.evaluate("""()=>{
    const canvas=document.createElement('canvas');canvas.id='canvas';document.body.append(canvas);
    blenderStartupStats.phase('Viewport presented');
    canvas.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,pointerType:'touch'}));
    blenderStartupStats.line('WGPU_STATS frame=17 dt=23.0ms tex=9/12MB');
   }""")
   editing.wait_for_function("blenderStartupStats.snapshot().watchdogStatus==='monitoring editor'")
   editing.evaluate("setTimeout(()=>{const until=performance.now()+3500;while(performance.now()<until){}window.editingProbeFinished=true;},250)")
   editing.wait_for_function('window.editingProbeFinished',timeout=10000)
   editing.wait_for_function('blenderStartupStats.snapshot().watchdogMaxGapMs>=2000')
   editing.evaluate("blenderStartupStats.failure('post-viewport runtime fixture')")
   editing.wait_for_function("blenderStartupStats.snapshot().watchdogStatus==='finished'")
   editing.close()
   reader=context.new_page();reader.goto(origin+'/reader.html')
   editing_saved=reader.evaluate('readRecovery()')
   assert editing_saved['ended'] and editing_saved['checkpoint']['editorActive'],editing_saved
   assert editing_saved['checkpoint']['lastInteraction']['type']=='pointerdown',editing_saved
   assert editing_saved['checkpoint']['nativeFrame']==17,editing_saved
   assert editing_saved['checkpoint']['nativeTextureBytes']==12*1048576,editing_saved
   assert editing_saved['checkpoint']['error']=='post-viewport runtime fixture',editing_saved
   reader.close()
   print('Post-viewport input, independent stalled-editor recording and durable runtime failure verified',flush=True)
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
   print('Storage and missing-worker failure paths verified',flush=True)
   (ROOT/'work/memory').mkdir(parents=True,exist_ok=True)
   (ROOT/'work/memory'/('watchdog-'+options.browser+'-evidence.json')).write_text(json.dumps(saved,indent=2)+'\n')
   browser.close()
 finally:server.shutdown();server.server_close()
faulthandler.cancel_dump_traceback_later()
print('PASS: '+options.browser+' independent synchronous-file persistence during main-thread block, manual closure recovery, idle preservation, recorder shutdown and visible storage failure. No GPU engine loaded in this fixture.')
