#!/usr/bin/env python3
"""Start the real editor through its tablet entrypoint, without injected bpy setup."""
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from threading import Thread
import json
import os
from playwright.sync_api import sync_playwright
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
class Handler(SimpleHTTPRequestHandler):
    # Model the incorrect WASM MIME header seen on the physical iPad. The
    # exact original type was not reported. Exercise real engine streaming.
    extensions_map={**SimpleHTTPRequestHandler.extensions_map,'.wasm':'application/octet-stream'}
    def log_message(self,*args):pass
server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(ROOT/'.cache/blender-webgpu-browser')))
Thread(target=server.serve_forever,daemon=True).start()
try:
    with sync_playwright() as p:
        executable=os.environ.get('CHROMIUM_PATH','/usr/lib/chromium/chromium')
        environment=dict(os.environ)
        driver=Path(executable).resolve().parent/'vk_swiftshader_icd.json'
        if driver.exists():environment['VK_ICD_FILENAMES']=str(driver)
        browser=p.chromium.launch(executable_path=executable,env=environment,args=[
            '--no-sandbox','--enable-unsafe-webgpu','--enable-features=Vulkan',
            '--use-angle=swiftshader','--enable-unsafe-swiftshader'])
        context=browser.new_context(viewport={'width':1180,'height':820},device_scale_factor=2,has_touch=True)
        context.add_init_script('''
          window.tabletTextureRequests=[];
          const texture=GPUDevice.prototype.createTexture;
          GPUDevice.prototype.createTexture=function(d){
            tabletTextureRequests.push({format:d.format,size:JSON.parse(JSON.stringify(d.size))});
            return texture.call(this,d);
          };
          Object.defineProperty(navigator,'platform',{get:()=> 'MacIntel'});
          Object.defineProperty(navigator,'maxTouchPoints',{get:()=>5});
          const request=GPUAdapter.prototype.requestDevice;
          GPUAdapter.prototype.requestDevice=function(options={}) {
            return request.call(this,{...options,requiredFeatures:
              [...(options.requiredFeatures || [])].filter(f=>f!=='float32-filterable')});
          };
        ''')
        page=context.new_page();page.set_default_timeout(180000)
        errors=[];workers=[]
        diagnostics=(ROOT/'.cache/blender-tablet-startup-console.log').open('w')
        page.on('console',lambda message:(diagnostics.write(message.type+': '+message.text+'\n'),diagnostics.flush()))
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('worker',lambda worker:workers.append(worker.url) if 'blender-core.js' in worker.url else None)
        page.goto(f'http://127.0.0.1:{server.server_port}/')
        page.wait_for_selector('#start-editor',state='visible')
        assert not page.evaluate('window.createBlenderCore || window.blenderEditor')
        page.locator('#start-editor').click()
        page.wait_for_function('document.body.dataset.rendered || document.body.dataset.error',timeout=300000)
        assert not page.evaluate('document.body.dataset.error'),page.evaluate('window.editorErrors')
        page.wait_for_function('document.body.dataset.started',timeout=300000)
        assert page.locator('#startup-stats').is_visible()
        page.wait_for_function('blenderStartupStats.snapshot().wasmMemoryBytes===blenderEditor.getBlenderMemoryBytes()')
        stats=page.evaluate('blenderStartupStats.snapshot()')
        assert stats['shaderModules']>0 and stats['renderPipelines']>0,stats
        assert stats['texturesCreated']>0 and stats['buffersCreated']>0,stats
        assert stats['phase']=='Viewport presented',stats
        assert stats['wasmMode']=='streaming' and stats['wasmMimeType']=='application/wasm',stats
        assert stats['drawCalls']>0 and stats['queueSubmissions']>0,stats
        page.wait_for_function("blenderStartupStats.snapshot().firstSubmission==='completed' && blenderStartupStats.snapshot().watchdogStatus==='finished'")
        assert len(workers)==4,workers
        assert stats['mainInstanceReady'] and stats['workersReady']==stats['workersRequested']==4,stats
        state=page.evaluate('''({report:blenderDeviceReport,ready:blenderEditor.projectStorageReady,
          wasmMemoryBytes:blenderEditor.getBlenderMemoryBytes(),width:canvas.width,height:canvas.height})''')
        assert state['ready'] is True and state['wasmMemoryBytes']>0,state
        assert state['width']<=1280 and state['height']<=800,state
        assert 'float32-filterable' not in state['report']['features'],state
        targets=page.evaluate("tabletTextureRequests.filter(d=>d.format==='rgba16float' && d.size.width>128 && d.size.height>128)")
        assert targets,'Real viewport targets were not observed'
        assert all(t['size']['width']<=state['width'] and t['size']['height']<=state['height'] for t in targets),targets
        state['viewportTargets']=targets
        screenshot=ROOT/'.cache/blender-tablet-startup-frame.png'
        page.locator('#canvas').screenshot(path=str(screenshot))
        picture=Image.open(screenshot).convert('RGB')
        assert len(picture.getcolors(picture.width*picture.height))>64,'Blank tablet editor'
        assert not errors,errors
        assert not page.evaluate('editorOutput.some(line=>line.includes("wasm streaming compile failed") || line.includes("falling back to ArrayBuffer instantiation"))'), 'Real engine fell back to buffering its WASM'
        (ROOT/'.cache/blender-tablet-startup-report.json').write_text(json.dumps(state,indent=2)+'\n')
        page.reload()
        page.wait_for_selector('#start-editor',state='visible')
        assert not page.evaluate('window.blenderEditor'),'Reload automatically restarted the native engine'
        assert page.locator('#startup-stats-title').inner_text()=='Previous startup — Blender is stopped'
        assert 'Viewport presented' in page.locator('#startup-stats-text').inner_text()
        context.close();browser.close();diagnostics.close()
finally:server.shutdown();server.server_close()
print('PASS: real stock tablet editor startup, four prewarmed workers, bounded viewport, no float32 filtering feature and reload gating. Physical Safari acceptance remains separate.')
