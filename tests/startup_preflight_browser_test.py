#!/usr/bin/env python3
"""Check startup gating with explicitly small infrastructure fixtures, not Blender."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import json
import os
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
class Handler(SimpleHTTPRequestHandler):
    def log_message(self,*args): pass

GPU='''
const limits={maxStorageTexturesPerShaderStage:4,maxStorageBuffersPerShaderStage:8,maxBufferSize:1073741824};
let resolveLost;const lost=new Promise(resolve=>resolveLost=resolve);
const device=Object.assign(new EventTarget(),{features:new Set(['depth32float-stencil8','indirect-first-instance']),limits,lost,destroy(){window.destroyedDevices=(window.destroyedDevices||0)+1;resolveLost({reason:'destroyed',message:'retired'});}});
window.triggerGPUFailure=message=>{const event=new Event('uncapturederror',{cancelable:true});event.error={message};device.dispatchEvent(event);};
Object.defineProperty(navigator,'gpu',{value:{requestAdapter:async()=>({features:device.features,limits,
  requestDevice:async options=>{window.requestedFeatures=options.requiredFeatures;window.deviceRequests=(window.deviceRequests||0)+1;return device;}})}});
Object.defineProperty(navigator,'platform',{get:()=> 'MacIntel'});
Object.defineProperty(navigator,'maxTouchPoints',{get:()=>5});
Object.defineProperty(navigator,'clipboard',{value:{writeText:async()=>{throw new Error('Clipboard denied fixture')}}});
'''
ENGINE='''window.createBlenderCore=async options=>({
  getBlenderMemoryBytes:()=>134217728,pauseBlenderLoop(){window.pausedLoops=(window.pausedLoops||0)+1;},resumeBlenderLoop(){},
  runBlenderMain:async args=>{window.fixtureOptions={lowResource:options.browserLowResource,args};options.print('WGPU_FIRST_CONTENT');}
});'''
with TemporaryDirectory(dir=ROOT/'.cache',prefix='startup-preflight-') as directory:
    base=Path(directory)
    for name in ['blender_editor.html','editor_files.js','editor_input.js','ipad-startup.html']:
        (base/('index.html' if name=='blender_editor.html' else name)).write_bytes((ROOT/'native/browser'/name).read_bytes())
    (base/'editor.html').write_bytes((base/'index.html').read_bytes())
    (base/'blender-core.js').write_text(ENGINE)
    (base/'service-worker.js').write_text((ROOT/'native/browser/service-worker.js').read_text().replace('__BUILD_CACHE__','startup-test'))
    for name in ['blender-core.wasm','blender-core.data','manifest.webmanifest','icon.svg','icon-192.png','icon-512.png']:
        (base/name).write_text('Not a Blender runtime; startup infrastructure fixture only')
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=directory))
    Thread(target=server.serve_forever,daemon=True).start()
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/lib/chromium/chromium'),args=['--no-sandbox'])
            context=browser.new_context(viewport={'width':1180,'height':820},device_scale_factor=2,has_touch=True)
            context.add_init_script(GPU)
            page=context.new_page();requests=[];errors=[]
            page.on('request',lambda r:requests.append(r.url))
            page.on('pageerror',lambda error:errors.append(str(error)))
            origin=f'http://127.0.0.1:{server.server_port}'
            page.goto(origin+'/ipad-startup.html')
            def report():return json.loads(page.locator('#report').input_value())
            assert report()['engineStarted'] is False
            assert not page.evaluate('navigator.serviceWorker.controller')
            assert not any('blender-core' in url or 'service-worker.js' in url for url in requests),requests
            page.locator('#check').click()
            page.wait_for_function('JSON.parse(document.querySelector("#report").value).adapterLimits')
            assert report()['adapterLimits']['maxStorageTexturesPerShaderStage']==4
            assert not page.evaluate('window.deviceRequests'), 'Preflight must not create a graphics device'
            page.locator('#copy').click()
            assert 'Report selected' in page.locator('#message').inner_text()
            assert page.locator('#report').evaluate('(e)=>e.selectionEnd-e.selectionStart')>100
            with page.expect_download() as pending:page.locator('#download').click()
            assert json.loads(Path(pending.value.path()).read_text())['engineStarted'] is False
            requests.clear()
            page.goto(origin+'/')
            page.wait_for_selector('#start-editor',state='visible')
            assert not any('blender-core' in url or 'service-worker.js' in url for url in requests),requests
            assert not page.evaluate('window.createBlenderCore || window.blenderEditor')
            page.reload()
            page.wait_for_selector('#start-editor',state='visible')
            page.locator('#start-editor').click()
            # First install isolation reload carries exactly one explicit launch.
            page.wait_for_function('document.body.dataset.started',timeout=30000)
            assert page.evaluate('crossOriginIsolated')
            assert page.evaluate('requestedFeatures.includes("indirect-first-instance")')
            assert page.evaluate('fixtureOptions.lowResource') is True
            args=page.evaluate('fixtureOptions.args')
            assert args[args.index('--threads')+1]=='1',args
            size=page.evaluate('({w:canvas.width,h:canvas.height})')
            assert size['w']<=1280 and size['h']<=800 and size['w']*size['h']<=1024000,size
            assert page.evaluate('blenderDeviceReport.startup.memoryBytes')==134217728
            page.reload()
            page.wait_for_selector('#start-editor',state='visible')
            assert not page.evaluate('window.blenderEditor'), 'A reload must not automatically restart the heavy engine'
            assert page.evaluate('blenderDeviceReport.previousAttempt.phase')=='Viewport presented'
            assert not errors,errors
            context.close()
            unsupported=browser.new_context(has_touch=True)
            unsupported.add_init_script(GPU.replace("'depth32float-stencil8','indirect-first-instance'", "'depth32float-stencil8'"))
            page=unsupported.new_page()
            page.goto(origin+'/')
            page.locator('#start-editor').click()
            page.wait_for_function('document.body.dataset.error',timeout=30000)
            assert 'indirect drawing' in page.locator('body').inner_text()
            assert not page.evaluate('window.deviceRequests || window.blenderEditor')
            unsupported.close()
            failure=browser.new_context(has_touch=True)
            failure.add_init_script(GPU)
            page=failure.new_page();page.goto(origin+'/')
            page.locator('#start-editor').click()
            page.wait_for_function('document.body.dataset.started',timeout=30000)
            # WebKit appends the useful compiler reason after its entire MSL.
            huge='Failed to compile the shader source, generated metal: '+('source '*8000)+' - error program_source:42: invalid test shader'
            page.evaluate('message=>triggerGPUFailure(message)',huge)
            page.wait_for_function('window.destroyedDevices===1')
            assert page.evaluate('window.pausedLoops')==1
            assert page.locator('#status-message').inner_text()=='program_source:42: invalid test shader'
            assert 'invalid test shader' in page.evaluate('blenderDeviceReport.startup.error')
            assert len(page.evaluate('blenderDeviceReport.startup.error'))<=16100
            assert 'Graphics device lost' not in page.locator('#status-message').inner_text(), 'Intentional destruction must preserve original error'
            # Simulate loss of the tab's session storage; durable checkpoints
            # remain readable in an idle tab without launching Blender again.
            page.evaluate('sessionStorage.clear()')
            fresh=failure.new_page();fresh.goto(origin+'/')
            fresh.wait_for_selector('#start-editor',state='visible')
            assert 'invalid test shader' in fresh.evaluate('blenderDeviceReport.previousAttempt.error')
            assert not fresh.evaluate('window.blenderEditor || window.deviceRequests')
            fresh.goto(origin+'/ipad-startup.html')
            recovered=json.loads(fresh.locator('#report').input_value())
            assert 'invalid test shader' in recovered['previousAttempts']['blender-startup-last']['error']
            assert not fresh.evaluate('window.deviceRequests')
            failure.close();browser.close()
    finally:server.shutdown();server.server_close()
print('PASS: engine-free preflight, selectable/downloadable report, no GPU device, iPad explicit start, bounded viewport and no restart loop (infrastructure fixtures only).')
