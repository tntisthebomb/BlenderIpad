#!/usr/bin/env python3
"""Start the real editor through its tablet entrypoint, without injected bpy setup."""
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from threading import Thread
import argparse
import json
import os
import struct
from playwright.sync_api import sync_playwright
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--runtime',type=Path,default=ROOT/'.cache/blender-webgpu-browser')
parser.add_argument('--stress-startup',action='store_true')
parser.add_argument('--interact',action='store_true')
parser.add_argument('--slow-readback',action='store_true')
parser.add_argument('--cpu-throttle',type=float,default=1)
parser.add_argument('--no-shader-seed',action='store_true')
parser.add_argument('--capture-shaders',type=Path)
parser.add_argument('--check-runtime-error',action='store_true')
options=parser.parse_args()
if options.cpu_throttle<1:parser.error('--cpu-throttle must be >= 1')
suffix='-stress' if options.stress_startup else ''
class Handler(SimpleHTTPRequestHandler):
    # Model the incorrect WASM MIME header seen on the physical iPad. The
    # exact original type was not reported. Exercise real engine streaming.
    extensions_map={**SimpleHTTPRequestHandler.extensions_map,'.wasm':'application/octet-stream'}
    def log_message(self,*args):pass
server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(options.runtime.resolve())))
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
        if options.stress_startup:
            context.add_init_script(path=ROOT/'tests/fixtures/tablet_startup_stress.js')
        if options.no_shader_seed:context.add_init_script('window.blenderDisableStartupShaderCache=true')
        if options.slow_readback:
            context.add_init_script('''
              window.delayedReadbacks=0;
              const map=GPUBuffer.prototype.mapAsync;
              GPUBuffer.prototype.mapAsync=function(...args){
                delayedReadbacks++;
                return Promise.all([Reflect.apply(map,this,args),new Promise(resolve=>setTimeout(resolve,350))]).then(([result])=>result);
              };
            ''')
        page=context.new_page();page.set_default_timeout(180000)
        if options.cpu_throttle>1:
            context.new_cdp_session(page).send('Emulation.setCPUThrottlingRate',{'rate':options.cpu_throttle})
        errors=[];workers=[]
        diagnostics=(ROOT/('.cache/blender-tablet-startup'+suffix+'-console.log')).open('w')
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
        assert stats['nativeQueueSubmissions']>0 and stats['nativeBridgeEvents']>0,stats
        assert 'complete' in stats['nativeInitStages'],stats
        assert page.evaluate('blenderEditor.browserStartupYieldCount>=2 && blenderEditor.browserStartupComplete===true'),'Native cooperative startup did not execute'
        page.wait_for_function("blenderStartupStats.snapshot().firstSubmission==='completed' && blenderStartupStats.snapshot().watchdogStatus==='monitoring editor'")
        assert len(workers)==4,workers
        assert stats['pythonStartupCheckpoints']>=100,stats
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
        state['shaderCache']=page.evaluate('window.blenderStartupShaderCacheReport')
        if options.no_shader_seed:
            assert state['shaderCache']['status']=='disabled for validation',state['shaderCache']
        elif state['shaderCache']['status']=='native translations loaded':
            assert state['shaderCache']['hits']>0,'The native engine did not consume its bundled translations'
        if options.stress_startup:
            page.wait_for_function('firstFrameProfile.finishedAt>0')
            profile=page.evaluate('firstFrameProfile')
            profile['nativeYields']=page.evaluate('blenderEditor.browserStartupYieldCount??0')
            profile['pythonStartupCheckpoints']=stats['pythonStartupCheckpoints']
            (ROOT/'.cache/blender-tablet-startup-stress-profile.json').write_text(json.dumps(profile,indent=2)+'\n')
            print('STARTUP_STRESS '+json.dumps(profile),flush=True)
            assert profile.get('launchStartedAbsoluteTime',0)>0,'Launch timing did not survive isolation reload'
            assert profile['rafTicks']>=3 and profile['timerTicks']>=3,profile
            assert 0<profile['maxHeartbeatGapMs']<5000,profile
            assert 0<profile['maxLaunchHeartbeatGapMs']<5000,profile
        screenshot=ROOT/('.cache/blender-tablet-startup'+suffix+'-frame.png')
        page.locator('#canvas').screenshot(path=str(screenshot))
        picture=Image.open(screenshot).convert('RGB')
        assert len(picture.getcolors(picture.width*picture.height))>64,'Blank tablet editor'
        assert not errors,errors
        assert not page.evaluate('editorOutput.some(line=>line.includes("wasm streaming compile failed") || line.includes("falling back to ArrayBuffer instantiation"))'), 'Real engine fell back to buffering its WASM'
        (ROOT/('.cache/blender-tablet-startup'+suffix+'-report.json')).write_text(json.dumps(state,indent=2)+'\n')
        if options.interact:
            from tablet_stock_interactions import exercise_stock_editor
            interactions=exercise_stock_editor(page,context,ROOT/'.cache')
            (ROOT/'.cache/tablet-stock-interaction-result.json').write_text(json.dumps(interactions,indent=2)+'\n')
            if options.slow_readback:assert page.evaluate('delayedReadbacks>0'),'Real GPU readback was not exercised'
            assert not errors,errors
            print('PASS: stock tablet UI cube selection, touch orbit, transform and Edit Mode; delayed readbacks='+str(page.evaluate('window.delayedReadbacks??0')),flush=True)
        if options.capture_shaders:
            options.capture_shaders.write_text(json.dumps(page.evaluate('Array.from(globalThis.__WGSL_CACHE__??[])'),indent=2)+'\n')
        if options.check_runtime_error:
            assert options.interact,'Runtime-error recovery needs the native project saved by the interaction test'
            saved=page.evaluate("({size:blenderEditor.FS.stat('/projects/tablet-stock-interaction.blend').size,magic:Array.from(blenderEditor.FS.readFile('/projects/tablet-stock-interaction.blend').slice(0,7))})")
            assert saved['size']>1000 and (bytes(saved['magic'])==b'BLENDER' or bytes(saved['magic'][:4])==b'\x28\xb5\x2f\xfd'),saved
            # Saving from the Console uses native front-buffer screenshot reads.
            # Check real thumbnail pixels, not merely successful file creation.
            blend=bytes(page.evaluate("Array.from(blenderEditor.FS.readFile('/projects/tablet-stock-interaction.blend'))"))
            assert blend[:9]==b'BLENDER_v','Expected the native wasm32 uncompressed file header'
            offset=12;thumbnail=None
            while offset+20<=len(blend):
                code,length=struct.unpack_from('<4sI',blend,offset)
                block=blend[offset+20:offset+20+length]
                assert len(block)==length,'Truncated native saved block'
                if code==b'TEST':thumbnail=block;break
                offset+=20+length
            assert thumbnail is not None,'Native screen thumbnail was not saved'
            width,height=struct.unpack_from('<ii',thumbnail)
            assert 0<width<=1024 and 0<height<=1024,(width,height)
            pixels=thumbnail[8:8+width*height*4]
            assert len(pixels)==width*height*4,'Truncated native thumbnail pixels'
            colors={pixels[i:i+3] for i in range(0,len(pixels),4)}
            assert len(colors)>16,('Blank front-buffer screenshot thumbnail',len(colors))
            print('PASS: native Console save includes a nonblank presented-frame thumbnail '+str((width,height,len(colors))),flush=True)
            page.evaluate("setTimeout(()=>{throw new WebAssembly.RuntimeError('post-viewport error fixture');},0)")
            page.wait_for_function("document.body.dataset.error?.includes('post-viewport error fixture')")
            page.wait_for_function("blenderStartupStats.snapshot().watchdogStatus==='finished'")
            assert page.locator('#status').is_visible() and page.locator('#recover-files').is_visible()
            assert page.evaluate("blenderEditor.FS.stat('/projects/tablet-stock-interaction.blend').size")==saved['size']
            assert len(errors)==1 and 'post-viewport error fixture' in errors[0],errors
            print('PASS: uncaught post-viewport WebAssembly error shows recovery controls and preserves the actual native saved project.',flush=True)
        page.reload()
        page.wait_for_selector('#start-editor',state='visible')
        assert not page.evaluate('window.blenderEditor'),'Reload automatically restarted the native engine'
        assert page.locator('#startup-stats-title').inner_text()=='Previous editing session — Blender is stopped'
        assert 'Viewport presented' in page.locator('#startup-stats-text').inner_text()
        context.close();browser.close();diagnostics.close()
finally:server.shutdown();server.server_close()
print('PASS: real stock tablet editor startup, four prewarmed workers, bounded viewport, no float32 filtering feature and reload gating. Physical Safari acceptance remains separate.')
