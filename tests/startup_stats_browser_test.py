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
 (base/'startup_stats.js').write_bytes((ROOT/'native/browser/startup_stats.js').read_bytes())
 server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=directory))
 Thread(target=server.serve_forever,daemon=True).start()
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/lib/chromium/chromium'),args=['--no-sandbox'])
   context=browser.new_context();page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   url=f'http://127.0.0.1:{server.server_port}/';page.goto(url)
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
    const marker={};window.observedBeforeCall=false;window.originalError=new Error('fixture failure');
    const device={
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
   view=page.locator('#startup-stats-text').inner_text()
   assert 'Starting native Blender' in view and 'failed-compute' in view,view
   assert '17' in view and 'Last engine message' in view and 'cumulative (not live usage)' in view,view
   snapshot=page.evaluate('blenderStartupStats.snapshot()')
   assert snapshot['wasmMemoryBytes']==3*65536,snapshot
   assert [snapshot[k] for k in ('shaderModules','renderPipelines','computePipelines','texturesCreated','buffersCreated')]==[1,1,1,1,1]
   assert snapshot['bufferBytesRequested']==1048576
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
