#!/usr/bin/env python3
"""Check visible startup breadcrumbs, API transparency and durable recovery."""
from pathlib import Path
from tempfile import TemporaryDirectory
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from functools import partial
from threading import Thread
import os,json
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
class Handler(SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
with TemporaryDirectory(dir=ROOT/'.cache',prefix='startup-stats-') as directory:
 base=Path(directory)
 css=(ROOT/'native/browser/blender_editor.html').read_text().split('<style>')[1].split('</style>')[0]
 (base/'index.html').write_text('<!doctype html><meta charset="utf-8"><style>'+css+'</style><body><button id="behind-stats" style="position:fixed;bottom:40px;left:20px" onclick="this.dataset.clicked=\'true\'">Underlying control</button><script src="startup_stats.js"></script></body>')
 (base/'worker.js').write_text("onmessage=event=>{if(event.data.cmd==='load')postMessage({cmd:'loaded'});else postMessage({size:event.data.buffer.byteLength});};")
 (base/'startup_watchdog.js').write_bytes((ROOT/'native/browser/startup_watchdog.js').read_bytes())
 (base/'startup_stats.js').write_bytes((ROOT/'native/browser/startup_stats.js').read_bytes())
 server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=directory))
 Thread(target=server.serve_forever,daemon=True).start()
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/lib/chromium/chromium'),args=['--no-sandbox'])
   context=browser.new_context();page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   url=f'http://127.0.0.1:{server.server_port}/';page.goto(url)
   # Upgrading the existing v4 page must show its old checkpoint even though
   # that schema has no recorder attempt ID.
   page.evaluate('''()=>{const legacy=blenderStartupStats.snapshot();
    delete legacy.attemptId;delete legacy.watchdogStatus;legacy.version='startup-stats-v4';
    legacy.phase='Legacy v4 viewport';legacy.lines=['legacy native breadcrumb'];
    localStorage.setItem('blender-startup-stats-last',JSON.stringify(legacy));}''')
   page.reload()
   assert 'Legacy v4 viewport' in page.locator('#startup-stats-text').inner_text()
   assert 'legacy native breadcrumb' in page.locator('#startup-stats-text').inner_text()
   page.evaluate('localStorage.removeItem("blender-startup-stats-last")');page.reload()
   assert page.locator('#startup-stats').is_visible()
   page.locator('#behind-stats').click()
   assert page.locator('#behind-stats').get_attribute('data-clicked')=='true','Stats must not block editor/recovery controls'
   assert 'not available yet' in page.locator('#startup-stats-text').inner_text()
   assert not page.evaluate('localStorage.getItem("blender-startup-stats-last")')
   page.evaluate('''async()=>{
    blenderStartupStats.start();blenderStartupStats.phase('Starting native Blender');
    window.trackedMemory=new WebAssembly.Memory({initial:2});
    const result=await WebAssembly.instantiate(new Uint8Array([0,97,115,109,1,0,0,0]),{env:{memory:trackedMemory}});
    if(!(result.instance instanceof WebAssembly.Instance))throw Error('Changed WebAssembly result');
    if(!blenderStartupStats.snapshot().mainInstanceReady)throw Error('Main instantiation completion not recorded');
    const worker=new Worker('/worker.js');
    await new Promise(resolve=>{worker.onmessage=resolve;worker.postMessage({cmd:'load'});});
    await new Promise(resolve=>setTimeout(resolve,0));
    const workerState=blenderStartupStats.snapshot();
    if(workerState.workersReady!==1||workerState.workersRequested!==1)throw Error('Worker readiness not observed');
    const buffer=new ArrayBuffer(8);
    const size=await new Promise(resolve=>{
      worker.onmessage=event=>resolve(event.data.size);
      worker.postMessage({buffer},[buffer]);
    });
    if(size!==8||buffer.byteLength!==0)throw Error('Worker transfer list or handler changed');
    worker.terminate();
    const marker={};window.observedBeforeCall=false;
    let resolveCompletion;window.queueObservers=0;window.drawCheckpoint=false;
    const completion=new Promise(resolve=>resolveCompletion=resolve);
    const pass={setPipeline(p){if(p!==marker)throw Error('Pipeline argument changed');},
      draw(...args){
        if(this!==pass||args.join(',')!=='3,1,0,0')throw Error('Draw receiver or arguments changed');
        const saved=JSON.parse(localStorage.getItem('blender-startup-stats-last'));
        drawCheckpoint=saved.operation==='Encoding draw'&&saved.operationStatus==='in progress';return marker;
      },end(){return marker;}};
    window.traceFixturePass=pass;
    const encoder={beginRenderPass(d){if(this!==encoder)throw Error('Encoder receiver changed');return pass;},finish(){return marker;}};
    const queue={submit(commands){if(this!==queue||commands[0]!==marker)throw Error('Queue arguments or receiver changed');return marker;},
      onSubmittedWorkDone(){queueObservers++;return completion;}};
window.originalError=new Error('fixture failure');
    const device={queue,createCommandEncoder(){return encoder;},
      createShaderModule(d){if(this!==device)throw Error('Wrong receiver');return marker;},
      createBuffer(d){return marker;},createTexture(d){return marker;},
      createRenderPipeline(d){
       const saved=JSON.parse(localStorage.getItem('blender-startup-stats-last'));
       observedBeforeCall=saved.label==='frozen-shader'&&saved.operation==='Compiling render pipeline';
       return marker;
      },
      createComputePipeline(){throw originalError;}
    };
    blenderStartupStats.instrumentDevice(device);
    if(device.createShaderModule({label:'shader'})!==marker)throw Error('Changed shader result');
    device.createBuffer({size:1048576});device.createTexture({});
    if(device.createRenderPipeline({label:'frozen-shader'})!==marker)throw Error('Changed pipeline result');
    const again=device.createCommandEncoder;blenderStartupStats.instrumentDevice(device);
    if(device.createCommandEncoder!==again)throw Error('Instrumented device twice');
    if(device.createCommandEncoder()!==encoder)throw Error('Changed encoder result');
    if(encoder.beginRenderPass({label:'native-aa-pass'})!==pass)throw Error('Changed pass result');
    pass.setPipeline(marker);
    if(pass.draw(3,1,0,0)!==marker||!drawCheckpoint)throw Error('Draw result or pre-call checkpoint changed');
    if(pass.end()!==marker||encoder.finish()!==marker)throw Error('Encoder API result changed');
    if(queue.submit([marker])!==marker||queue.submit([marker])!==marker)throw Error('Changed queue return');
    if(queueObservers!==1)throw Error('Added repeated completion observers');
    if(blenderStartupStats.snapshot().firstSubmission!=='waiting for callback')throw Error('Marked GPU complete too early');
    resolveCompletion();await completion;
    if(blenderStartupStats.snapshot().firstSubmission!=='completed')throw Error('Completion callback was not recorded');
    const queueSubmit=queue.submit;blenderStartupStats.instrumentQueue(queue);
    if(queue.submit!==queueSubmit)throw Error('Native queue callback wrapped the same queue twice');
    const nativeQueue={writeBuffer(...args){if(this!==nativeQueue||args[0]!==marker||args[1]!==16)throw Error('Upload arguments changed');return marker;}};
    blenderStartupStats.instrumentQueue(nativeQueue);
    if(nativeQueue.writeBuffer(marker,16)!==marker)throw Error('Changed native queue upload result');
    const surface={configure(d){if(this!==surface||d!==marker)throw Error('Canvas receiver/argument changed');return marker;},
      getCurrentTexture(){return marker;},unconfigure(){throw originalError;}};
    blenderStartupStats.instrumentCanvas(surface);
    if(surface.configure(marker)!==marker||surface.getCurrentTexture()!==marker)throw Error('Changed canvas API result');
    try{surface.unconfigure();throw Error('Swallowed canvas exception');}catch(error){if(error!==originalError)throw error;}
    blenderStartupStats.nativeBridge('queue-submit-enter','in progress','native fixture');
    const nativeCheckpoint=JSON.parse(localStorage.getItem('blender-startup-stats-last'));
    if(nativeCheckpoint.nativeQueueSubmissions!==1||nativeCheckpoint.operationStatus!=='in progress')throw Error('Native entry was not durably checkpointed');
    blenderStartupStats.nativeBridge('queue-submit-returned','call returned','native fixture');
    blenderStartupStats.line('Browser startup: Importing bl_ui.properties_scene');
    if(blenderStartupStats.snapshot().pythonStartupCheckpoints!==1)throw Error('Python checkpoint missing');
    if(blenderStartupStats.snapshot().label!=='Importing bl_ui.properties_scene')throw Error('Python stage missing');
    blenderStartupStats.line('Browser startup: Loading key maps');
    if(blenderStartupStats.snapshot().pythonStartupCheckpoints!==1)throw Error('Coarse stage counted as Python checkpoint');
    blenderStartupStats.line('GPU initialization: create infos');
    if(blenderStartupStats.snapshot().nativeInitStages[0]!=='create infos')throw Error('Native initialization stage missing');
    try{device.createComputePipeline({label:'failed-compute'});throw Error('Swallowed exception');}
    catch(error){if(error!==originalError)throw error;}
    trackedMemory.grow(1);
    // A large file package must not produce thousands of synchronous DOM /
    // storage updates merely to display its dependency counter.
    const save=Storage.prototype.setItem;let writes=0;
    Storage.prototype.setItem=function(...args){writes++;return Reflect.apply(save,this,args);};
    for(let count=10000;count>0;count--)blenderStartupStats.dependencies(count);
    if(writes!==0)throw Error('Dependency burst caused synchronous checkpoint writes');
    blenderStartupStats.dependencies(0);
    if(writes!==1)throw Error('Completed dependencies did not save their checkpoint');
    Storage.prototype.setItem=save;
    blenderStartupStats.dependencies(17);
    blenderStartupStats.line('Last engine message');
   }''')
   assert page.evaluate('observedBeforeCall')
   page.wait_for_function("document.querySelector('#startup-stats-text').textContent.includes('Last engine message')")
   view=page.locator('#startup-stats-text').inner_text()
   assert 'Starting native Blender' in view and 'failed-compute' in view,view
   assert '17' in view and 'Last engine message' in view and 'cumulative (not live usage)' in view,view
   snapshot=page.evaluate('blenderStartupStats.snapshot()')
   assert snapshot['wasmMemoryBytes']==3*65536,snapshot
   assert [snapshot[k] for k in ('shaderModules','renderPipelines','computePipelines','texturesCreated','buffersCreated')]==[1,1,1,1,1]
   assert snapshot['bufferBytesRequested']==1048576
   assert [snapshot[k] for k in ('commandEncoders','renderPasses','drawCalls','queueSubmissions')]==[1,1,1,2],snapshot
   assert snapshot['firstSubmission']=='completed',snapshot
   page.evaluate('''()=>{
    blenderStartupStats.phase('Viewport presented');
    const save=Storage.prototype.setItem;let writes=0;
    Storage.prototype.setItem=function(...args){writes++;return Reflect.apply(save,this,args);};
    for(let i=0;i<10000;i++)traceFixturePass.draw(3,1,0,0);
    Storage.prototype.setItem=save;
    if(writes!==0)throw Error('Steady editor draw path wrote synchronous recovery checkpoints');
   }''')
   page.locator('#toggle-startup-stats').click();assert page.locator('#startup-stats-text').is_hidden()
   page.locator('#toggle-startup-stats').click();assert page.locator('#startup-stats-text').is_visible()
   page.evaluate('blenderStartupStats.failure("Failed to compile shader, generated metal: "+"source".repeat(8000)+" - error useful compiler explanation")')
   assert 'useful compiler explanation' in page.locator('#startup-stats-text').inner_text()
   page.close()
   restored=context.new_page();restored.goto(url)
   assert restored.locator('#startup-stats-title').inner_text()=='Previous startup — Blender is stopped'
   assert 'useful compiler explanation' in restored.locator('#startup-stats-text').inner_text()
   assert 'failed-compute' in restored.locator('#startup-stats-text').inner_text()
   saved=restored.evaluate('localStorage.getItem("blender-startup-stats-last")')
   restored.wait_for_timeout(1200)
   assert restored.evaluate('localStorage.getItem("blender-startup-stats-last")')==saved,'Idle must retain previous checkpoint'
   assert not restored.evaluate('window.blenderEditor || window.createBlenderCore')
   assert not errors,errors
   browser.close()
 finally:server.shutdown();server.server_close()
print('PASS: persistent stats, pre-call checkpoint, real growing WASM memory, counters, original API returns/errors, recovery after tab closure and no idle overwrite.')
